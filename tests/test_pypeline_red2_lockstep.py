from dataclasses import fields

import pytest

from pypeline_red2 import red2_stepper as abi
from pypeline_red2.red2_processor import Red2Processor
from pypeline_red2.oracle import (
    RED2_LOCKSTEP_V1,
    architectural_diffs,
    load_compiled_program,
    load_processor,
    mutate_state,
    run_compiled_lockstep,
    run_lockstep,
)
from red2_engine.mured import Direction, MuredMachine, MuredOpcode, Word
from red2_engine.pipelinec_vectors import EncodedArchitecturalState, RED2ABICodec
from thor_compile.red2 import load_faithful_machine
from thor_lang.normalization import normalize_expr
from thor_lang.parser import parse_expr


def _machine(source: str, *, quantum: int = 100) -> MuredMachine:
    return load_faithful_machine(
        normalize_expr(parse_expr(source)),
        quantum=quantum,
        memory_words=128,
        control_words=32,
    )


def _reverse_app_underflow_machine() -> MuredMachine:
    machine = MuredMachine.load(
        [Word(MuredOpcode.LAMBDA, "x"), Word(MuredOpcode.VAR, 0)],
        quantum=3,
        memory_words=32,
        control_words=8,
    )
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.pc = 3
    state.fsp = 3
    state.direction = Direction.B
    return machine


def test_red2_lockstep_v1_is_explicit() -> None:
    assert RED2_LOCKSTEP_V1 == 1


def test_program_image_is_deterministic_and_preserves_initial_architecture() -> None:
    left = _machine("(CAR {PAIR (+ 2 3) 9})")
    right = _machine("(CAR {PAIR (+ 2 3) 9})")
    left_codec = RED2ABICodec()
    right_codec = RED2ABICodec()

    left_image = left_codec.encode_program(left)
    right_image = right_codec.encode_program(right)
    assert left_image == right_image

    codec, image, processor = load_processor(left)
    assert processor.checkpoint() == image.state
    assert processor.checkpoint() == codec.encode_state(left.state)
    assert image.working_memory_limit == left.working_memory_limit


def test_program_image_includes_oracle_builtin_pair_selectors() -> None:
    codec = RED2ABICodec()
    image = codec.encode_program(_machine("7"))
    selectors = {
        codec.literal(item.selector_id): (codec.literal(item.tag_id), item.offset)
        for item in image.struct_selectors
    }
    assert selectors["CAR"] == ("PAIR", 2)
    assert selectors["CDR"] == ("PAIR", 1)


def test_architectural_diff_localizes_memory_and_control_entries() -> None:
    codec, image, _processor = load_processor(_machine("(+ 2 3)"))
    state = image.state
    memory = list(state.memory)
    memory[0] ^= 1
    control = list(state.control_stack)
    control[2] = 7
    changed = mutate_state(state, memory=tuple(memory), control_stack=tuple(control), q=state.q + 1)

    diffs = architectural_diffs(state, changed)
    assert [(item.field, item.index) for item in diffs] == [
        ("memory", 0),
        ("control_stack", 2),
        ("q", None),
    ]


def test_scheduler_stop_status_is_an_architectural_difference() -> None:
    _codec, image, _processor = load_processor(_machine("7"))
    diffs = architectural_diffs(
        image.state,
        image.state,
        oracle_status_value=abi.STATUS_COMPLETE,
        processor_status_value=abi.STATUS_QUANTUM_EXHAUSTED,
    )
    assert [(item.field, item.index) for item in diffs] == [("status", None)]


def test_typed_fault_code_is_an_architectural_difference() -> None:
    _codec, image, _processor = load_processor(_machine("7"))
    diffs = architectural_diffs(
        image.state,
        image.state,
        oracle_status_value=abi.STATUS_FAULT,
        processor_status_value=abi.STATUS_FAULT,
        oracle_fault_value=abi.FAULT_INVALID_ADDRESS,
        processor_fault_value=abi.FAULT_CONTROL_UNDERFLOW,
    )
    assert [(item.field, item.oracle, item.processor) for item in diffs] == [
        ("fault", abi.FAULT_INVALID_ADDRESS, abi.FAULT_CONTROL_UNDERFLOW),
    ]


def test_live_matching_typed_fault_terminates_lockstep_without_divergence() -> None:
    result = run_lockstep(_reverse_app_underflow_machine(), max_transitions=4)
    assert result.matches
    assert result.transitions == 1
    assert result.status == abi.STATUS_FAULT


def test_live_mismatched_typed_fault_reports_exact_fault_divergence(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Red2Processor.run_to_commit

    def run_to_commit_with_wrong_fault(
        self: Red2Processor,
        max_clocks: int | None = None,
    ) -> bool:
        committed = original(self, max_clocks)
        if not committed and self.fault == abi.FAULT_CONTROL_UNDERFLOW:
            self.fault = abi.FAULT_INVALID_ADDRESS
        return committed

    monkeypatch.setattr(Red2Processor, "run_to_commit", run_to_commit_with_wrong_fault)
    result = run_lockstep(_reverse_app_underflow_machine(), max_transitions=4)
    assert not result.matches
    assert result.divergence is not None
    assert result.divergence.transition == 1
    assert [(item.field, item.oracle, item.processor) for item in result.divergence.diffs] == [
        ("fault", abi.FAULT_CONTROL_UNDERFLOW, abi.FAULT_INVALID_ADDRESS),
    ]


def test_host_call_fields_are_architectural_differences() -> None:
    _codec, image, _processor = load_processor(_machine("(CLOCK)"))
    state = image.state
    for field, value in (
        ("pending_host_op", abi.HOST_CLOCK),
        ("pending_host_argument", 7),
    ):
        changed = mutate_state(state, **{field: value})
        diffs = architectural_diffs(state, changed)
        assert [(item.field, item.index) for item in diffs] == [(field, None)]


def test_every_scalar_architectural_field_is_compared() -> None:
    _codec, image, _processor = load_processor(_machine("7"))
    state = image.state
    scalar_fields = [
        field.name
        for field in fields(EncodedArchitecturalState)
        if field.name not in {"memory", "control_stack"}
    ]
    for name in scalar_fields:
        value = getattr(state, name)
        changed = mutate_state(state, **{name: value + 1})
        diffs = architectural_diffs(state, changed)
        assert [(item.field, item.index) for item in diffs] == [(name, None)]


_PROGRAM_CORPUS = [
    ("straight-line", "7", 10),
    ("closure", "((LAMBDA (x) (+ x 1)) 6)", 20),
    ("primitive", "(+ 2 3)", 10),
    ("lazy", "(IF TRUE 7 (BAD BAD))", 10),
    ("recursive", "(LETREC ((x y) (y 9)) x)", 10),
    ("structure", "(CAR {PAIR (+ 2 3) (BAD BAD)})", 20),
    ("equality", "(EQUAL? {PAIR 1 2} {PAIR 1 2})", 30),
    ("q-exhaustion", "((LAMBDA (x) (+ x 1)) 6)", 0),
]


@pytest.mark.parametrize(("category", "source", "quantum"), _PROGRAM_CORPUS)
def test_compiled_corpus_has_deterministic_encoded_images(
    category: str,
    source: str,
    quantum: int,
) -> None:
    left = _machine(source, quantum=quantum)
    right = _machine(source, quantum=quantum)
    left_codec = RED2ABICodec()
    right_codec = RED2ABICodec()
    assert left_codec.encode_program(left) == right_codec.encode_program(right), category


@pytest.mark.parametrize(("category", "source", "quantum"), _PROGRAM_CORPUS)
def test_compiled_program_categories_run_in_committed_lockstep(
    category: str,
    source: str,
    quantum: int,
) -> None:
    result = run_lockstep(_machine(source, quantum=quantum), max_transitions=512)
    assert result.matches, (category, result.divergence.format() if result.divergence else None)
    assert result.transitions > 0


def test_definition_mapping_order_does_not_change_compiled_image() -> None:
    expr = normalize_expr(parse_expr("(F 6)"))
    f = normalize_expr(parse_expr("(LAMBDA (x) (+ x 1))"))
    g = normalize_expr(parse_expr("(LAMBDA (x) (+ x 2))"))
    left = load_compiled_program(
        expr,
        quantum=20,
        definitions={"F": f, "G": g},
        memory_words=128,
        control_words=32,
    )
    right = load_compiled_program(
        expr,
        quantum=20,
        definitions={"G": g, "F": f},
        memory_words=128,
        control_words=32,
    )
    assert left.image == right.image


def test_compiled_definition_image_relocation_and_execution_match() -> None:
    definitions = {
        "F": normalize_expr(parse_expr("(LAMBDA (x) (+ x 1))")),
    }
    expr = normalize_expr(parse_expr("(F 6)"))
    left = load_compiled_program(
        expr,
        quantum=20,
        definitions=definitions,
        memory_words=128,
        control_words=32,
    )
    right = load_compiled_program(
        expr,
        quantum=20,
        definitions=definitions,
        memory_words=128,
        control_words=32,
    )
    assert left.image == right.image
    assert left.processor.checkpoint() == left.image.state

    result = run_lockstep(
        left.machine,
        max_transitions=512,
        codec=left.codec,
        processor=left.processor,
    )
    assert result.matches, result.divergence.format() if result.divergence else None
    assert result.status == abi.STATUS_COMPLETE


def test_run_compiled_lockstep_uses_canonical_loader_path() -> None:
    result = run_compiled_lockstep(
        normalize_expr(parse_expr("((LAMBDA (x) (+ x 1)) 6)")),
        quantum=20,
        memory_words=128,
        control_words=32,
        max_transitions=512,
    )
    assert result.matches, result.divergence.format() if result.divergence else None
    assert result.status == abi.STATUS_COMPLETE


def test_q_exhaustion_recharge_is_compared_as_same_machine_transition() -> None:
    source = "((LAMBDA (x) (+ x 1)) 6)"
    exhausted = _machine(source, quantum=1)
    assert exhausted.run_until_suspend().reason.value == "quantum_exhausted"

    machine = _machine(source, quantum=1)
    result = run_lockstep(
        machine,
        max_transitions=1024,
        recharge_quantum=20,
    )
    assert result.matches, result.divergence.format() if result.divergence else None
    assert result.status == abi.STATUS_COMPLETE
    assert result.transitions > 1


def test_divergence_report_names_exact_transition_context_and_field() -> None:
    from pypeline_red2.oracle import compare_checkpoint

    machine = _machine("(+ 2 3)")
    codec, _image, processor = load_processor(machine)
    processor.q += 1
    divergence = compare_checkpoint(
        machine,
        processor,
        codec,
        transition=17,
        oracle_opcode="int",
    )
    assert divergence is not None
    assert divergence.transition == 17
    assert [(item.field, item.index) for item in divergence.diffs] == [("q", None)]
    report = divergence.format()
    assert "transition 17" in report
    assert "oracle_opcode=int" in report
    assert "processor_microstate=0" in report
    assert "q:" in report


def test_invalid_host_resume_maps_to_typed_invalid_resume_fault() -> None:
    def invalid_host_service(_name: str, _argument: Word | None) -> Word:
        return Word(MuredOpcode.APP, 0, True)

    result = run_lockstep(
        _machine("(CLOCK)", quantum=10),
        max_transitions=128,
        host_service=invalid_host_service,
    )
    assert result.matches
    assert result.status == abi.STATUS_FAULT


def test_io_program_runs_in_lockstep_with_deterministic_host_service() -> None:
    effects: list[tuple[str, int | None]] = []

    def host(name: str, argument: Word | None) -> Word:
        effects.append((name, None if argument is None else int(argument.data)))
        if name == "CLOCK":
            return Word(MuredOpcode.INT, 1234)
        if name == "UART-RX":
            return Word(MuredOpcode.CHAR, "z")
        return Word(MuredOpcode.SYM, "NIL")

    machine = _machine(
        "(IO-BIND (CLOCK) (LAMBDA (now) (IO-THEN (UART-TX (MOD now 256)) (IO-RETURN now))))",
        quantum=100,
    )
    result = run_lockstep(machine, max_transitions=1024, host_service=host)
    assert result.matches, result.divergence.format() if result.divergence else None
    assert effects == [("CLOCK", None), ("UART-TX", 210)]
    assert result.status == abi.STATUS_COMPLETE

import pytest

from abstract_red2_machine.machine import AbstractRED2Machine
from concrete_red2_machine import abi
from concrete_red2_machine.machine import (
    PRIM0_ROLE_IF,
    PRIM0_ROLE_Y,
    RED2_PURE_V1,
    SCALAR_OP_DEC,
    SCALAR_OP_EQ,
    ConcreteRED2Machine,
)
from concrete_red2_machine.pipelinec_vectors import RED2ABICodec
from abstract_red2_machine.loader import load_faithful_machine
from thor.ast import Definition, StructDef
from thor.normalization import normalize_expr, normalize_program
from thor.parser import parse_expr, parse_program
from thor.primitives import install_struct_definition


def _processor(machine: AbstractRED2Machine, codec: RED2ABICodec) -> ConcreteRED2Machine:
    encoded = codec.encode_state(machine.state)
    if_id = codec.literal_id("IF")
    y_id = codec.literal_id("Y")
    role_limit = max(if_id, y_id)
    roles = [0] * (role_limit + 1)
    roles[if_id] = PRIM0_ROLE_IF
    roles[y_id] = PRIM0_ROLE_Y

    scalar_names = ("=", "1-")
    scalar_ids = [codec.literal_id(name) for name in scalar_names]
    scalar_ops = [0] * (max(scalar_ids) + 1)
    scalar_ops[codec.literal_id("=")] = SCALAR_OP_EQ
    scalar_ops[codec.literal_id("1-")] = SCALAR_OP_DEC

    selectors = dict(machine.struct_selectors)
    selectors["CAR"] = ("PAIR", 2)
    selectors["CDR"] = ("PAIR", 1)
    selector_ids = [codec.literal_id(name) for name in selectors]
    selector_tags = [0] * (max(selector_ids, default=0) + 1)
    selector_offsets = [0] * len(selector_tags)
    for name, (tag, offset) in selectors.items():
        literal_id = codec.literal_id(name)
        selector_tags[literal_id] = codec.literal_id(tag)
        selector_offsets[literal_id] = offset

    return ConcreteRED2Machine(
        encoded,
        prim0_roles=tuple(roles),
        scalar_ops=tuple(scalar_ops),
        true_literal_id=codec.literal_id("TRUE"),
        false_literal_id=codec.literal_id("FALSE"),
        nil_literal_id=codec.literal_id("NIL"),
        if_reconstruct_literal_id=codec.literal_id("__IF_RECONSTRUCT__"),
        struct_selector_tags=tuple(selector_tags),
        struct_selector_offsets=tuple(selector_offsets),
        struct_selector_result_literal_id=codec.literal_id("__STRUCT_SELECTOR_RESULT__"),
        cons_literal_id=codec.literal_id("CONS"),
        pair_literal_id=codec.literal_id("PAIR"),
        equality_literal_id=codec.literal_id("EQUAL?"),
        equal_star_literal_id=codec.literal_id("__EQUAL_STAR__"),
        equal_if_literal_id=codec.literal_id("__EQUAL_IF__"),
        equality_continue_literal_id=codec.literal_id("__EQUALITY_CONTINUE__"),
        equal_stuck_literal_id=codec.literal_id("__EQUAL_STUCK__"),
    )


def _machine_from_source(
    source: str,
    *,
    quantum: int,
    memory_words: int = 512,
    control_words: int = 128,
) -> AbstractRED2Machine:
    if "==" not in source and "|=" not in source:
        return load_faithful_machine(
            normalize_expr(parse_expr(source)),
            quantum=quantum,
            memory_words=memory_words,
            control_words=control_words,
        )

    program = normalize_program(parse_program(source))
    definitions = {}
    action = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
        else:
            action = form
    assert action is not None
    return load_faithful_machine(
        action,
        quantum=quantum,
        definitions=definitions,
        memory_words=memory_words,
        control_words=control_words,
    )


def _run_lockstep(
    source: str,
    *,
    quantum: int,
    memory_words: int = 512,
    control_words: int = 128,
    max_commits: int = 20_000,
) -> tuple[AbstractRED2Machine, ConcreteRED2Machine, RED2ABICodec]:
    machine = _machine_from_source(
        source,
        quantum=quantum,
        memory_words=memory_words,
        control_words=control_words,
    )
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    commits = 0
    while not machine.state.halted:
        assert commits < max_commits, (source, "commit budget exceeded")
        machine.step()
        assert processor.run_to_commit(), (source, commits, processor.fault)
        assert processor.checkpoint() == codec.encode_state(machine.state), (
            source,
            commits,
        )
        commits += 1
    assert processor.halted
    return machine, processor, codec


def _equality_frame_index(processor: ConcreteRED2Machine) -> int:
    index = processor.c
    while index >= 0:
        entry = processor.control_stack[index]
        if entry and abi.control_tag(entry) == abi.CONTROL_EQUALITY:
            return index
        index -= 1
    return -1


def test_red2_pure_v1_is_explicit() -> None:
    assert RED2_PURE_V1 == 1


@pytest.mark.parametrize(
    "source",
    [
        "(EQUAL? (F 1 2) (F 1 2))",
        "(EQUAL? (F 1 2) (F 1 3))",
        "(EQUAL? (LAMBDA (x y) (F x y)) (LAMBDA (a b) (F a b)))",
        "(EQUAL? {PAIR {PAIR 1 2} {PAIR 3 4}} {PAIR {PAIR 1 2} {PAIR 3 4}})",
        "(LETREC ((x {PAIR 1 2})) (EQUAL? x x))",
        "(LETREC ((f (LAMBDA (x) x))) (EQUAL? f f))",
    ],
)
def test_nested_shared_and_closure_equality_match_every_oracle_commit(source: str) -> None:
    _run_lockstep(source, quantum=100)


def test_deep_application_equality_is_bounded_iterative_and_matches_oracle() -> None:
    arguments = " ".join(str(index) for index in range(1, 49))
    source = f"(EQUAL? (F {arguments}) (F {arguments}))"
    _run_lockstep(
        source,
        quantum=200,
        memory_words=2048,
        control_words=256,
        max_commits=50_000,
    )


def test_zero_quantum_keeps_public_equality_residual_without_private_frame() -> None:
    machine = _machine_from_source(
        "(EQUAL? (LAMBDA (x) (F x)) (LAMBDA (y) (F y)))",
        quantum=0,
    )
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    while not machine.state.halted:
        machine.step()
        assert processor.run_to_commit(), processor.fault
        assert processor.checkpoint() == codec.encode_state(machine.state)
        assert _equality_frame_index(processor) == -1
    assert processor.c == -1
    assert processor.q == 0


def test_structural_equality_restores_quantum_and_balances_temporary_control() -> None:
    source = "(EQUAL? (F 1 2) (F 1 2))"
    machine = _machine_from_source(source, quantum=37)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    saw_frame = False
    equality_index = -1
    entry_q = -1
    entry_env = -1
    entry_free_space = -1

    while not machine.state.halted:
        machine.step()
        assert processor.run_to_commit(), processor.fault
        assert processor.checkpoint() == codec.encode_state(machine.state)
        frame_index = _equality_frame_index(processor)
        if frame_index >= 0 and not saw_frame:
            saw_frame = True
            equality_index = frame_index
            entry_q = processor.q
            entry_env = processor.env
            entry_free_space = processor.free_space
        elif saw_frame and frame_index < 0:
            assert processor.q == entry_q
            assert processor.env == entry_env
            assert processor.free_space == entry_free_space
            assert processor.c == equality_index - 2
            break

    assert saw_frame


def test_repeated_equality_reuses_one_fixed_scratch_envelope() -> None:
    source = """
loop == (lambda (n)
  (if (= n 0)
      TRUE
      (if (EQUAL? (F 1 2) (F 1 2))
          (loop (1- n))
          FALSE)))
(loop 8)
"""
    machine = _machine_from_source(
        source,
        quantum=1000,
        memory_words=4096,
        control_words=512,
    )
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    peaks: list[int] = []
    active = False
    start_fsp = -1
    peak_fsp = -1
    start_frame = -1

    for commit in range(100_000):
        if machine.state.halted:
            break
        machine.step()
        assert processor.run_to_commit(), (commit, processor.fault)
        assert processor.checkpoint() == codec.encode_state(machine.state), commit
        frame_index = _equality_frame_index(processor)
        if frame_index >= 0 and not active:
            active = True
            start_fsp = processor.fsp
            peak_fsp = processor.fsp
            start_frame = frame_index
        elif frame_index >= 0:
            peak_fsp = max(peak_fsp, processor.fsp)
        elif active:
            peaks.append(peak_fsp - start_fsp)
            assert processor.c == start_frame - 2
            active = False
    else:
        pytest.fail("repeated equality exceeded commit budget")

    assert processor.halted
    assert len(peaks) == 8
    assert peaks[1:] == [peaks[0]] * 7
    assert processor.c == -1

import pytest

from abstract_red2_machine.machine import (
    AbstractRED2Machine,
    AbstractRED2MachineState,
    Direction,
    MuredOpcode,
    MuredStopReason,
    Word,
)
from concrete_red2_machine import abi
from concrete_red2_machine.machine import (
    PRIM0_ROLE_IF,
    PRIM0_ROLE_Y,
    RED2_QUANTUM_V1,
    SCALAR_OP_ADD,
    SCALAR_OP_DEC,
    SCALAR_OP_EQ,
    ConcreteRED2Machine,
)
from concrete_red2_machine.pipelinec_vectors import RED2ABICodec
from thor_compile.red2 import load_faithful_machine
from thor_lang.normalization import normalize_expr
from thor_lang.parser import parse_expr


def _processor(machine: AbstractRED2Machine, codec: RED2ABICodec) -> ConcreteRED2Machine:
    encoded = codec.encode_state(machine.state)
    if_id = codec.literal_id("IF")
    y_id = codec.literal_id("Y")
    roles = [0] * (max(if_id, y_id) + 1)
    roles[if_id] = PRIM0_ROLE_IF
    roles[y_id] = PRIM0_ROLE_Y

    scalar_ids = [codec.literal_id(name) for name in ("+", "=", "1-")]
    scalar_ops = [0] * (max(scalar_ids) + 1)
    scalar_ops[codec.literal_id("+")] = SCALAR_OP_ADD
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
        working_memory_limit=machine.working_memory_limit,
    )


def _source_machine(source: str, quantum: int) -> AbstractRED2Machine:
    return load_faithful_machine(
        normalize_expr(parse_expr(source)),
        quantum=quantum,
        memory_words=256,
        control_words=64,
    )


def _expected_status(stop_reason: MuredStopReason) -> int:
    if stop_reason is MuredStopReason.COMPLETE:
        return abi.STATUS_COMPLETE
    if stop_reason is MuredStopReason.QUANTUM_EXHAUSTED:
        return abi.STATUS_QUANTUM_EXHAUSTED
    if stop_reason is MuredStopReason.HOST_CALL:
        return abi.STATUS_HOST_CALL
    raise AssertionError(stop_reason)


def _run_one_suspension_lockstep(
    machine: AbstractRED2Machine,
    processor: ConcreteRED2Machine,
    codec: RED2ABICodec,
) -> MuredStopReason:
    stop = machine.run_until_suspend(cycle_limit=machine.state.cycles + 100_000)
    status = processor.run_until_suspend(max_clocks=1_000_000)
    assert status == _expected_status(stop.reason)
    assert processor.checkpoint() == codec.encode_state(machine.state)
    return stop.reason


def test_red2_quantum_v1_is_explicit() -> None:
    assert RED2_QUANTUM_V1 == 1


@pytest.mark.parametrize(
    "source",
    [
        "((LAMBDA (x) x) 7)",
        "(+ (+ 1 2) (+ 3 4))",
        "(IF TRUE (+ 1 2) (BAD BAD))",
        "(LETREC ((x 7)) x)",
        "(CAR {PAIR (+ 1 2) (BAD BAD)})",
        "(EQUAL? (F 1 2) (F 1 2))",
    ],
)
@pytest.mark.parametrize("quantum", range(0, 4))
def test_quantum_suspension_matches_oracle_residual_exactly(
    source: str,
    quantum: int,
) -> None:
    machine = _source_machine(source, quantum)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    reason = _run_one_suspension_lockstep(machine, processor, codec)
    if quantum == 0:
        assert reason is MuredStopReason.QUANTUM_EXHAUSTED
        assert processor.q == 0
        assert processor.halted == 1
        assert processor.c == -1


def test_repeated_recharge_matches_oracle_and_uninterrupted_result_without_reload() -> None:
    source = "(+ (+ (+ 1 2) 3) 4)"
    uninterrupted_machine = _source_machine(source, 64)
    uninterrupted_codec = RED2ABICodec()
    uninterrupted = _processor(uninterrupted_machine, uninterrupted_codec)
    assert _run_one_suspension_lockstep(
        uninterrupted_machine, uninterrupted, uninterrupted_codec
    ) is MuredStopReason.COMPLETE
    uninterrupted_result = uninterrupted_codec.decode_word(
        uninterrupted.memory[uninterrupted.pc]
    )

    machine = _source_machine(source, 1)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    processor_identity = id(processor)
    memory_identity = id(processor.memory)
    control_identity = id(processor.control_stack)
    suspensions = 0

    while True:
        reason = _run_one_suspension_lockstep(machine, processor, codec)
        if reason is MuredStopReason.COMPLETE:
            break
        assert reason is MuredStopReason.QUANTUM_EXHAUSTED
        assert processor.status() == abi.STATUS_QUANTUM_EXHAUSTED
        machine.recharge_quantum(1)
        status = processor.recharge_quantum(1)
        assert status == abi.STATUS_RUNNING, (
            suspensions,
            processor.fault,
            processor.microstate,
            processor._task4_phase,
            processor._task_sp,
            processor._task_mat_count,
        )
        assert id(processor) == processor_identity
        assert id(processor.memory) == memory_identity
        assert id(processor.control_stack) == control_identity
        assert processor.checkpoint() == codec.encode_state(machine.state)
        suspensions += 1
        assert suspensions < 16

    assert suspensions >= 2
    assert processor.status() == abi.STATUS_COMPLETE
    assert codec.decode_word(processor.memory[processor.pc]) == uninterrupted_result


def test_recharge_preserves_diamond_sharing_and_omits_garbage_exactly() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 32,
        control_stack=[None] * 8,
        pc=0,
        fsp=7,
        env=32,
        free_space=32,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        halted=True,
    )
    state.memory[0] = Word(MuredOpcode.APP, 3, False)
    state.memory[1] = Word(MuredOpcode.APP, 3, False)
    state.memory[2] = Word(MuredOpcode.SYM, "F", True)
    state.memory[3] = Word(MuredOpcode.INT, 7, True)
    state.memory[4] = Word(MuredOpcode.SYM, "__POISON__", True)
    state.memory[5] = Word(MuredOpcode.INT, 12345, True)
    state.memory[6] = Word(MuredOpcode.APP, 5, False)
    state.memory[7] = Word(MuredOpcode.SYM, "GARBAGE", True)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    memory_identity = id(processor.memory)

    machine.recharge_quantum(0)
    assert processor.recharge_quantum(0) == abi.STATUS_RUNNING

    assert id(processor.memory) == memory_identity
    assert processor.checkpoint() == codec.encode_state(machine.state)
    assert codec.decode_word(processor.memory[0]).data == 3
    assert codec.decode_word(processor.memory[1]).data == 3


def test_recharge_relocates_rblock_without_relocating_integer_literal_exactly() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 32,
        control_stack=[None] * 8,
        pc=10,
        fsp=14,
        env=32,
        free_space=32,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        halted=True,
    )
    state.memory[10] = Word(MuredOpcode.RBLOCK, 13, False)
    state.memory[11] = Word(MuredOpcode.RUP, 1, False)
    state.memory[12] = Word(MuredOpcode.VAR, 0, True)
    state.memory[13] = Word(MuredOpcode.SYM, "x", False)
    state.memory[14] = Word(MuredOpcode.INT, 13, True)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    machine.recharge_quantum(0)
    assert processor.recharge_quantum(0) == abi.STATUS_RUNNING

    assert processor.checkpoint() == codec.encode_state(machine.state)
    assert codec.decode_word(processor.memory[0]).data == 3
    assert codec.decode_word(processor.memory[4]).data == 13


def test_recharge_capacity_failure_is_transactional() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=3,
        free_space=3,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        halted=True,
    )
    state.memory[0] = Word(MuredOpcode.APP, 2, False)
    state.memory[1] = Word(MuredOpcode.SYM, "F", True)
    state.memory[2] = Word(MuredOpcode.INT, 1, True)
    machine = AbstractRED2Machine(state, working_memory_limit=3)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    before = processor.checkpoint()
    memory_identity = id(processor.memory)

    status = processor.recharge_quantum(1)

    assert status == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert processor.checkpoint() == before
    assert id(processor.memory) == memory_identity


def test_structural_equality_uses_more_clocks_but_same_semantic_quantum() -> None:
    atomic_machine = _source_machine("(EQUAL? 1 1)", 5)
    atomic_codec = RED2ABICodec()
    atomic = _processor(atomic_machine, atomic_codec)
    compound_machine = _source_machine("(EQUAL? (F 1 2) (F 1 2))", 5)
    compound_codec = RED2ABICodec()
    compound = _processor(compound_machine, compound_codec)

    assert _run_one_suspension_lockstep(atomic_machine, atomic, atomic_codec) is MuredStopReason.COMPLETE
    assert _run_one_suspension_lockstep(
        compound_machine, compound, compound_codec
    ) is MuredStopReason.COMPLETE

    assert atomic.q == compound.q == 4
    assert compound.clocks > atomic.clocks


def test_selector_child_return_at_zero_quantum_matches_oracle_commit_for_commit() -> None:
    machine = _source_machine("(CAR {PAIR (+ 1 2) (BAD BAD)})", 1)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    for commit in range(1000):
        if machine.state.halted:
            break
        machine.step()
        assert processor.run_to_commit(), (commit, processor.fault)
        assert processor.checkpoint() == codec.encode_state(machine.state), commit
    else:
        pytest.fail("selector q=0 reconstruction did not halt within 1000 commits")

    assert machine.state.halted


def test_live_q0_status_is_running_until_residual_halts() -> None:
    machine = _source_machine("(+ 1 2)", 0)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    assert processor.q == 0
    assert processor.halted == 0
    assert processor.status() == abi.STATUS_RUNNING
    assert processor.run_to_commit()
    assert processor.status() == abi.STATUS_RUNNING

    while not processor.halted:
        assert processor.run_to_commit()
    assert processor.status() == abi.STATUS_QUANTUM_EXHAUSTED

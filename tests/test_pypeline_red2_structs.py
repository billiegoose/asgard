from pypeline_red2 import red2_stepper as abi
from pypeline_red2.red2_processor import (
    MICRO_TASK4,
    TASK4_STRUCT,
    TASK4_STRUCT_SELECTOR_RESULT,
    Red2Processor,
)
from red2_engine.mured import (
    Direction,
    MuredMachine,
    MuredMachineState,
    MuredOpcode,
    Word,
    _SubgraphFrame,
)
from red2_engine.pipelinec_vectors import RED2ABICodec


def _processor(machine: MuredMachine, codec: RED2ABICodec) -> Red2Processor:
    encoded = codec.encode_state(machine.state)
    car_id = codec.literal_id("CAR")
    cdr_id = codec.literal_id("CDR")
    selector_limit = max(car_id, cdr_id)
    selector_tags = [0] * (selector_limit + 1)
    selector_offsets = [0] * (selector_limit + 1)
    pair_id = codec.literal_id("PAIR")
    selector_tags[car_id] = pair_id
    selector_offsets[car_id] = 2
    selector_tags[cdr_id] = pair_id
    selector_offsets[cdr_id] = 1
    return Red2Processor(
        encoded,
        struct_selector_tags=tuple(selector_tags),
        struct_selector_offsets=tuple(selector_offsets),
        struct_selector_result_literal_id=codec.literal_id("__STRUCT_SELECTOR_RESULT__"),
        cons_literal_id=codec.literal_id("CONS"),
        pair_literal_id=pair_id,
    )


def _step_both(
    machine: MuredMachine,
    processor: Red2Processor,
    codec: RED2ABICodec,
) -> None:
    machine.step()
    assert processor.run_to_commit(), processor.fault
    assert processor.checkpoint() == codec.encode_state(machine.state)


def test_struct_without_selector_saves_quantum_and_allocates_ubv_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 6,
        pc=0,
        fsp=5,
        env=16,
        c=-1,
        direction=Direction.F,
        q=7,
        phi=2,
        argcnt=0,
    )
    state.memory[0] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[1] = Word(MuredOpcode.APP, 8, False)
    state.memory[5] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.q == 0
    assert processor.phi == 3
    assert processor.env == 15
    assert processor.memory[15] == codec.encode_word(Word(MuredOpcode.UBV, 3, False))


def test_struct_with_selector_app_contracts_like_lambda_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 20,
        control_stack=[None] * 6,
        pc=0,
        fsp=6,
        env=20,
        c=0,
        direction=Direction.F,
        q=4,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[1] = Word(MuredOpcode.VAR, 0, True)
    state.memory[6] = Word(MuredOpcode.APP, 12, False)
    state.control_stack[0] = 20
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.q == 3
    assert processor.env == 18
    assert processor.memory[18] == codec.encode_word(Word(MuredOpcode.CLOSURE, 20, False))
    assert processor.memory[19] == codec.encode_word(Word(None, 12, False))


def test_struct_with_selector_and_zero_quantum_reconstructs_lazily_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 6,
        pc=0,
        fsp=5,
        env=16,
        c=0,
        direction=Direction.F,
        q=0,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[1] = Word(MuredOpcode.VAR, 0, True)
    state.memory[5] = Word(MuredOpcode.APP, 9, False)
    state.control_stack[0] = 14
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.q == 0
    assert processor.phi == 1
    assert processor.env == 15
    assert processor.memory[15] == codec.encode_word(Word(MuredOpcode.UBV, 1, False))
    assert processor.argcnt == 0
    assert processor.c == 1


def test_struct_reverse_restores_quantum_and_binder_depth_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 6,
        pc=0,
        fsp=5,
        env=16,
        c=-1,
        direction=Direction.F,
        q=9,
        phi=0,
        argcnt=0,
    )
    state.memory[0] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[1] = Word(MuredOpcode.VAR, 0, True)
    state.memory[5] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)
    copied_struct = machine.state.fsp
    machine.state.pc = copied_struct
    machine.state.direction = Direction.B
    processor.pc = copied_struct
    processor.direction = 1

    _step_both(machine, processor, codec)

    assert processor.q == 9
    assert processor.phi == 0
    assert processor.c == -1


def test_join_publishes_lazy_struct_ep_field_before_reclaim_and_reuse() -> None:
    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 8,
        pc=4,
        fsp=7,
        env=28,
        free_space=28,
        c=0,
        direction=Direction.B,
        q=10,
        phi=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[6] = Word(MuredOpcode.EP, 29, False)
    state.memory[7] = Word(MuredOpcode.VAR, 0, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim=None,
        fire=0,
    )
    machine = MuredMachine(state)
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.APP, 5, False))
    assert processor.memory[5] == codec.encode_word(
        Word(MuredOpcode.STRUCT, "PAIR", False)
    )
    assert processor.memory[6] == codec.encode_word(Word(MuredOpcode.INT, 41, False))
    assert processor.memory[7] == codec.encode_word(Word(MuredOpcode.VAR, 0, True))
    assert processor.free_space == 32
    assert processor.env == 32

    published = tuple(processor.memory[3:8])
    for address in range(28, 32):
        processor.memory[address] = codec.encode_word(
            Word(MuredOpcode.INT, 9000 + address, False)
        )
    assert tuple(processor.memory[3:8]) == published


def test_join_late_malformed_struct_descriptor_is_architecturally_atomic() -> None:
    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 8,
        pc=4,
        fsp=8,
        env=28,
        free_space=28,
        c=0,
        direction=Direction.B,
        q=10,
        phi=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[6] = Word(MuredOpcode.EP, 29, False)
    state.memory[7] = Word(MuredOpcode.INT, 99, True)
    state.memory[8] = Word(MuredOpcode.VAR, 0, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim=None,
        fire=0,
    )
    machine = MuredMachine(state)
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION
    assert processor.checkpoint() == before

    assert processor._task_memory[6] == codec.encode_word(
        Word(MuredOpcode.INT, 41, False)
    )
    assert processor.memory[6] == codec.encode_word(Word(MuredOpcode.EP, 29, False))


def test_selector_result_overlapping_lambda_preserves_surviving_argument_continuation() -> None:
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 6,
        pc=3,
        fsp=7,
        env=16,
        free_space=16,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        argcnt=1,
        prim="__STRUCT_SELECTOR_RESULT__",
        fire=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 5, False)
    state.memory[4] = Word(MuredOpcode.PRIM_1, "CAR", True)
    state.memory[5] = Word(MuredOpcode.LAMBDA, 0, False)
    state.memory[6] = Word(MuredOpcode.LAMBDA, 0, False)
    state.memory[7] = Word(MuredOpcode.INT, 9, True)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    machine._fire_primitive()
    processor._task4_begin(TASK4_STRUCT, TASK4_STRUCT_SELECTOR_RESULT)
    processor.microstate = MICRO_TASK4
    assert processor.run_to_commit(), processor.fault

    assert processor.checkpoint() == codec.encode_state(machine.state)
    assert processor.pc == 3
    assert processor.fsp == 2
    assert processor.direction == abi.DIRECTION_FORWARD
    assert processor.argcnt == 1

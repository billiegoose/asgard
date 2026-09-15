from pypeline_red2 import red2_stepper as abi
from pypeline_red2.red2_processor import RED2_RECURSIVE_V1, Red2Processor
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
    return Red2Processor(codec.encode_state(machine.state))


def _step_both(
    machine: MuredMachine,
    processor: Red2Processor,
    codec: RED2ABICodec,
) -> None:
    machine.step()
    assert processor.run_to_commit(), processor.fault
    assert processor.checkpoint() == codec.encode_state(machine.state)


def test_red2_recursive_v1_is_explicit() -> None:
    assert RED2_RECURSIVE_V1 == 1


def test_rblock_and_rup_with_quantum_construct_rec_context_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 24,
        control_stack=[None] * 6,
        pc=0,
        fsp=5,
        env=24,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 3, False)
    state.memory[1] = Word(MuredOpcode.RUP, 1, False)
    state.memory[2] = Word(MuredOpcode.VAR, 0, True)
    state.memory[3] = Word(MuredOpcode.SYM, "x", False)
    state.memory[4] = Word(MuredOpcode.INT, 1, True)
    state.memory[5] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)
    _step_both(machine, processor, codec)

    assert processor.env == 21
    assert processor.memory[21] == codec.encode_word(Word(MuredOpcode.REC, 4, False))
    assert processor.memory[22] == codec.encode_word(Word(None, 21, False))
    assert processor.memory[23] == codec.encode_word(Word(None, 0, False))


def test_rblock_and_rup_at_zero_quantum_prepare_reconstruction_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 20,
        control_stack=[None] * 6,
        pc=0,
        fsp=5,
        env=20,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=2,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 3, False)
    state.memory[1] = Word(MuredOpcode.RUP, 1, False)
    state.memory[2] = Word(MuredOpcode.VAR, 0, True)
    state.memory[3] = Word(MuredOpcode.SYM, "x", False)
    state.memory[4] = Word(MuredOpcode.INT, 1, True)
    state.memory[5] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)
    _step_both(machine, processor, codec)

    assert processor.phi == 3
    assert processor.env == 19
    assert processor.c == 0
    assert abi.control_tag(processor.control_stack[0]) == abi.CONTROL_ADDRESS
    assert abi.control_field(processor.control_stack[0], 0) == 19


def test_two_binding_rec_context_uses_oracle_physical_order() -> None:
    state = MuredMachineState(
        memory=[None] * 32,
        control_stack=[None] * 6,
        pc=0,
        fsp=8,
        env=32,
        c=-1,
        direction=Direction.F,
        q=4,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 4, False)
    state.memory[1] = Word(MuredOpcode.RBLOCK, 6, False)
    state.memory[2] = Word(MuredOpcode.RUP, 2, False)
    state.memory[3] = Word(MuredOpcode.VAR, 1, True)
    state.memory[4] = Word(MuredOpcode.SYM, "x", False)
    state.memory[5] = Word(MuredOpcode.VAR, 0, True)
    state.memory[6] = Word(MuredOpcode.SYM, "y", False)
    state.memory[7] = Word(MuredOpcode.VAR, 1, True)
    state.memory[8] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    for _ in range(3):
        _step_both(machine, processor, codec)

    assert processor.env == 26
    assert processor.memory[26] == codec.encode_word(Word(MuredOpcode.REC, 7, False))
    assert processor.memory[29] == codec.encode_word(Word(MuredOpcode.REC, 5, False))


def test_recursive_context_preserves_outer_pnp_bridge() -> None:
    state = MuredMachineState(
        memory=[None] * 48,
        control_stack=[None] * 12,
        pc=0,
        fsp=8,
        env=46,
        free_space=42,
        c=-1,
        direction=Direction.F,
        q=4,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 4, False)
    state.memory[1] = Word(MuredOpcode.RBLOCK, 6, False)
    state.memory[2] = Word(MuredOpcode.RUP, 2, False)
    state.memory[3] = Word(MuredOpcode.VAR, 1, True)
    state.memory[4] = Word(MuredOpcode.SYM, "x", False)
    state.memory[5] = Word(MuredOpcode.INT, 1, True)
    state.memory[6] = Word(MuredOpcode.SYM, "y", False)
    state.memory[7] = Word(MuredOpcode.INT, 2, True)
    state.memory[8] = Word(MuredOpcode.STOP)
    state.memory[46] = Word(MuredOpcode.INT, 99, False)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    for _ in range(3):
        _step_both(machine, processor, codec)

    assert processor.env == 35
    assert processor.memory[41] == codec.encode_word(Word(MuredOpcode.PNP, 46, False))
    assert processor.memory[35] == codec.encode_word(Word(MuredOpcode.REC, 7, False))
    assert processor.memory[38] == codec.encode_word(Word(MuredOpcode.REC, 5, False))


def test_head_var_landing_on_rec_enters_binding_and_charges_quantum() -> None:
    state = MuredMachineState(
        memory=[None] * 24,
        control_stack=[None] * 6,
        pc=0,
        fsp=6,
        env=18,
        c=-1,
        direction=Direction.F,
        q=2,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.VAR, 0, True)
    state.memory[5] = Word(MuredOpcode.INT, 7, True)
    state.memory[6] = Word(MuredOpcode.STOP)
    state.memory[18] = Word(MuredOpcode.REC, 5, False)
    state.memory[19] = Word(None, 18, False)
    state.memory[20] = Word(None, 2, False)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.q == 1
    assert processor.pc == 5


def test_app_var_landing_on_rec_emits_non_head_recp() -> None:
    state = MuredMachineState(
        memory=[None] * 20,
        control_stack=[None] * 6,
        pc=0,
        fsp=2,
        env=14,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.APP_VAR, 0, False)
    state.memory[1] = Word(MuredOpcode.INT, 1, True)
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[14] = Word(MuredOpcode.REC, 8, False)
    state.memory[15] = Word(None, 14, False)
    state.memory[16] = Word(None, 4, False)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.RECP, 14, False))
    assert processor.q == 3


def test_non_head_recp_is_passive_without_quantum_charge() -> None:
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=12,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.RECP, 12, False)
    state.memory[1] = Word(MuredOpcode.INT, 1, True)
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[12] = Word(MuredOpcode.REC, 7, False)
    state.memory[13] = Word(None, 12, False)
    state.memory[14] = Word(None, 4, False)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.q == 3
    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.RECP, 12, False))


def test_reverse_recp_with_quantum_becomes_app_and_saves_context_path() -> None:
    state = MuredMachineState(
        memory=[None] * 20,
        control_stack=[None] * 6,
        pc=4,
        fsp=4,
        env=14,
        c=-1,
        direction=Direction.B,
        q=2,
        phi=0,
    )
    state.memory[4] = Word(MuredOpcode.RECP, 14, False)
    state.memory[14] = Word(MuredOpcode.REC, 8, False)
    state.memory[15] = Word(None, 14, False)
    state.memory[16] = Word(None, 1, False)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.q == 1
    assert processor.pc == 4
    assert processor.memory[4] == codec.encode_word(Word(MuredOpcode.APP, 8, False))


def test_reverse_rblock_enters_binding_subgraph_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 24,
        control_stack=[None] * 8,
        pc=6,
        fsp=8,
        env=20,
        c=0,
        direction=Direction.B,
        q=0,
        phi=1,
        argcnt=1,
    )
    state.memory[4] = Word(MuredOpcode.SYM, "x", False)
    state.memory[5] = Word(MuredOpcode.INT, 1, True)
    state.memory[6] = Word(MuredOpcode.RBLOCK, 4, False)
    state.memory[8] = Word(MuredOpcode.STOP)
    state.control_stack[0] = 20
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.pc == 4
    assert processor.argcnt == -1
    assert processor.direction == abi.DIRECTION_FORWARD


def test_head_recp_at_zero_quantum_reconstructs_letrec_wrapper_exactly() -> None:
    state = MuredMachineState(
        memory=[None] * 40,
        control_stack=[None] * 10,
        pc=8,
        fsp=12,
        env=28,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 4, False)
    state.memory[1] = Word(MuredOpcode.RBLOCK, 6, False)
    state.memory[2] = Word(MuredOpcode.RUP, 2, False)
    state.memory[3] = Word(MuredOpcode.VAR, 1, True)
    state.memory[4] = Word(MuredOpcode.SYM, "x", False)
    state.memory[5] = Word(MuredOpcode.VAR, 0, True)
    state.memory[6] = Word(MuredOpcode.SYM, "y", False)
    state.memory[7] = Word(MuredOpcode.VAR, 1, True)
    state.memory[8] = Word(MuredOpcode.RECP, 31, True)
    state.memory[12] = Word(MuredOpcode.STOP)
    state.memory[28] = Word(MuredOpcode.REC, 7, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 0, False)
    state.memory[31] = Word(MuredOpcode.REC, 5, False)
    state.memory[32] = Word(None, 28, False)
    state.memory[33] = Word(None, 0, False)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[13] == codec.encode_word(Word(MuredOpcode.RBLOCK, 4, False))
    assert processor.memory[14] == codec.encode_word(Word(MuredOpcode.RBLOCK, 6, False))
    assert processor.memory[15] == codec.encode_word(Word(MuredOpcode.RUP, 2, False))
    assert processor.memory[16] == codec.encode_word(Word(MuredOpcode.VAR, 1, True))
    assert processor.direction == abi.DIRECTION_REVERSE
    assert processor.pc == 15
    assert processor.q == 0
    assert processor.phi == 2


def test_reverse_recp_at_zero_quantum_sets_up_join_and_reconstruction_exactly() -> None:
    codec = RED2ABICodec()
    car_id = codec.literal_id("CAR")
    state = MuredMachineState(
        memory=[None] * 40,
        control_stack=[None] * 12,
        pc=10,
        fsp=10,
        env=28,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        prim="CAR",
        fire=2,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 4, False)
    state.memory[1] = Word(MuredOpcode.RUP, 1, False)
    state.memory[2] = Word(MuredOpcode.VAR, 0, True)
    state.memory[4] = Word(MuredOpcode.SYM, "x", False)
    state.memory[5] = Word(MuredOpcode.INT, 7, True)
    state.memory[9] = Word(MuredOpcode.STOP)
    state.memory[10] = Word(MuredOpcode.RECP, 28, False)
    state.memory[28] = Word(MuredOpcode.REC, 5, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 0, False)
    machine = MuredMachine(state)
    encoded = codec.encode_state(machine.state)
    processor = Red2Processor(encoded)
    processor.prim_id = car_id

    machine.step()
    assert processor.run_to_commit(), processor.fault
    expected = codec.encode_state(machine.state)
    assert processor.checkpoint() == expected

    assert processor.memory[11] == codec.encode_word(Word(MuredOpcode.JOIN, 10, False, 1))
    assert processor.memory[12] == codec.encode_word(Word(MuredOpcode.RBLOCK, 4, False))
    assert processor.memory[13] == codec.encode_word(Word(MuredOpcode.RUP, 1, False))
    assert processor.memory[14] == codec.encode_word(Word(MuredOpcode.VAR, 0, True))
    assert processor.c == 1
    assert processor.free_space == 26
    assert processor.prim_id == 0
    assert processor.fire == 0
    assert processor.direction == abi.DIRECTION_REVERSE
    assert processor.pc == 13
    assert processor.q == 0


def test_reverse_recp_zero_quantum_follows_oracle_through_join_return() -> None:
    codec = RED2ABICodec()
    car_id = codec.literal_id("CAR")
    state = MuredMachineState(
        memory=[None] * 40,
        control_stack=[None] * 12,
        pc=10,
        fsp=10,
        env=28,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        prim="CAR",
        fire=2,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 4, False)
    state.memory[1] = Word(MuredOpcode.RUP, 1, False)
    state.memory[2] = Word(MuredOpcode.VAR, 0, True)
    state.memory[4] = Word(MuredOpcode.SYM, "x", False)
    state.memory[5] = Word(MuredOpcode.INT, 7, True)
    state.memory[9] = Word(MuredOpcode.STOP)
    state.memory[10] = Word(MuredOpcode.RECP, 28, False)
    state.memory[28] = Word(MuredOpcode.REC, 5, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 0, False)
    machine = MuredMachine(state)
    processor = Red2Processor(codec.encode_state(machine.state))
    processor.prim_id = car_id

    for step in range(8):
        machine.step()
        assert processor.run_to_commit(), (
            step,
            processor.fault,
            processor.microstate,
            processor._task4_kind,
            processor._task4_phase,
        )
        assert processor.checkpoint() == codec.encode_state(machine.state), step

    assert processor.memory[10] == codec.encode_word(machine.state.memory[10])
    assert processor.free_space == 28
    assert processor.env == 28
    assert processor.c == -1
    assert processor.prim_id == car_id
    assert processor.fire == 1


def test_join_publishes_recursive_residual_before_reclaim_exactly() -> None:
    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 8,
        pc=4,
        fsp=21,
        env=28,
        free_space=28,
        c=0,
        direction=Direction.B,
        q=0,
        phi=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.EP, 28, True)
    state.memory[10] = Word(MuredOpcode.RBLOCK, 20, False)
    state.memory[11] = Word(MuredOpcode.RUP, 1, False)
    state.memory[12] = Word(MuredOpcode.VAR, 0, True)
    state.memory[20] = Word(MuredOpcode.SYM, "x", False)
    state.memory[21] = Word(MuredOpcode.INT, 7, True)
    state.memory[28] = Word(MuredOpcode.REC, 21, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 10, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim=None,
        fire=0,
    )
    machine = MuredMachine(state)
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    residual = 22
    assert processor.memory[3] == codec.encode_word(
        Word(MuredOpcode.APP, residual, False)
    )
    assert processor.memory[residual] == codec.encode_word(
        Word(MuredOpcode.RBLOCK, 20, False)
    )
    assert processor.memory[residual + 1] == codec.encode_word(
        Word(MuredOpcode.RUP, 1, False)
    )
    assert processor.memory[residual + 2] == codec.encode_word(
        Word(MuredOpcode.VAR, 0, True)
    )
    assert processor.fsp == residual + 2
    assert processor.free_space == 32
    assert processor.env == 32

    published_parent = processor.memory[3]
    published_words = tuple(processor.memory[residual : residual + 3])
    for address in range(28, 32):
        processor.memory[address] = codec.encode_word(
            Word(MuredOpcode.INT, 9000 + address, False)
        )
    assert processor.memory[3] == published_parent
    assert tuple(processor.memory[residual : residual + 3]) == published_words


def test_join_self_recursive_binding_rewrites_rec_ep_to_letrec_var_exactly() -> None:
    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 8,
        pc=4,
        fsp=21,
        env=28,
        free_space=28,
        c=0,
        direction=Direction.B,
        q=0,
        phi=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.EP, 28, True)
    state.memory[10] = Word(MuredOpcode.RBLOCK, 20, False)
    state.memory[11] = Word(MuredOpcode.RUP, 1, False)
    state.memory[12] = Word(MuredOpcode.VAR, 0, True)
    state.memory[20] = Word(MuredOpcode.SYM, "x", False)
    state.memory[21] = Word(MuredOpcode.EP, 28, True)
    state.memory[28] = Word(MuredOpcode.REC, 21, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 10, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim=None,
        fire=0,
    )
    machine = MuredMachine(state)
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    residual = 22
    assert processor.memory[21] == codec.encode_word(Word(MuredOpcode.VAR, 0, True))
    assert processor.memory[3] == codec.encode_word(
        Word(MuredOpcode.APP, residual, False)
    )
    assert processor.memory[residual] == codec.encode_word(
        Word(MuredOpcode.RBLOCK, 20, False)
    )
    assert processor.memory[residual + 1] == codec.encode_word(
        Word(MuredOpcode.RUP, 1, False)
    )
    assert processor.memory[residual + 2] == codec.encode_word(
        Word(MuredOpcode.VAR, 0, True)
    )

    published_parent = processor.memory[3]
    published_binding = processor.memory[21]
    published_words = tuple(processor.memory[residual : residual + 3])
    for address in range(28, 32):
        processor.memory[address] = codec.encode_word(
            Word(MuredOpcode.INT, 9000 + address, False)
        )
    assert processor.memory[3] == published_parent
    assert processor.memory[21] == published_binding
    assert tuple(processor.memory[residual : residual + 3]) == published_words


def test_join_shared_recursive_aliases_materialize_one_residual_root_exactly() -> None:
    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 8,
        pc=4,
        fsp=21,
        env=28,
        free_space=28,
        c=0,
        direction=Direction.B,
        q=0,
        phi=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.APP, 8, False)
    state.memory[6] = Word(MuredOpcode.APP, 8, False)
    state.memory[7] = Word(MuredOpcode.SYM, "F", True)
    state.memory[8] = Word(MuredOpcode.EP, 28, True)
    state.memory[10] = Word(MuredOpcode.RBLOCK, 20, False)
    state.memory[11] = Word(MuredOpcode.RUP, 1, False)
    state.memory[12] = Word(MuredOpcode.VAR, 0, True)
    state.memory[20] = Word(MuredOpcode.SYM, "x", False)
    state.memory[21] = Word(MuredOpcode.EP, 28, True)
    state.memory[28] = Word(MuredOpcode.REC, 21, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 10, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim=None,
        fire=0,
    )
    machine = MuredMachine(state)
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    residual = 22
    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.APP, 5, False))
    assert processor.memory[5] == codec.encode_word(
        Word(MuredOpcode.APP, residual, False)
    )
    assert processor.memory[6] == codec.encode_word(
        Word(MuredOpcode.APP, residual, False)
    )
    assert processor.memory[21] == codec.encode_word(Word(MuredOpcode.VAR, 0, True))
    assert processor.memory[residual] == codec.encode_word(
        Word(MuredOpcode.RBLOCK, 20, False)
    )
    assert processor.memory[residual + 1] == codec.encode_word(
        Word(MuredOpcode.RUP, 1, False)
    )
    assert processor.memory[residual + 2] == codec.encode_word(
        Word(MuredOpcode.VAR, 0, True)
    )
    assert processor.fsp == residual + 2
    assert processor.free_space == 32
    assert processor.env == 32

    first_alias = processor.memory[5]
    second_alias = processor.memory[6]
    published_binding = processor.memory[21]
    published_words = tuple(processor.memory[residual : residual + 3])
    for address in range(28, 32):
        processor.memory[address] = codec.encode_word(
            Word(MuredOpcode.INT, 9000 + address, False)
        )
    assert processor.memory[5] == first_alias
    assert processor.memory[6] == second_alias
    assert processor.memory[21] == published_binding
    assert tuple(processor.memory[residual : residual + 3]) == published_words


def test_rup_late_malformed_second_rec_is_architecturally_atomic() -> None:
    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 8,
        pc=2,
        fsp=6,
        env=20,
        free_space=20,
        c=-1,
        direction=Direction.F,
        q=4,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.RBLOCK, 10, False)
    state.memory[1] = Word(MuredOpcode.RBLOCK, 12, False)
    state.memory[2] = Word(MuredOpcode.RUP, 2, False)
    state.memory[6] = Word(MuredOpcode.STOP)
    state.memory[20] = Word(MuredOpcode.REC, 13, False)
    state.memory[21] = Word(None, 0, False)
    state.memory[22] = Word(None, 0, False)
    state.memory[23] = Word(MuredOpcode.REC, 11, False)
    state.memory[24] = Word(MuredOpcode.INT, 99, False)
    state.memory[25] = Word(None, 0, False)
    machine = MuredMachine(state)
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION
    assert processor.checkpoint() == before

    assert processor._task_memory[21] == codec.encode_word(Word(None, 20, False))
    assert processor._task_memory[22] == codec.encode_word(Word(None, 0, False))
    assert processor.memory[21] == codec.encode_word(Word(None, 0, False))
    assert processor.memory[22] == codec.encode_word(Word(None, 0, False))

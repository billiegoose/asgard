import pytest

from pypeline_red2 import red2_stepper as abi
from pypeline_red2.red2_processor import (
    RED2_CLOSURES_V1,
    SCALAR_OP_ADD,
    SCALAR_OP_DIV,
    SCALAR_OP_INC,
    Red2Processor,
)
from red2_engine.mured import (
    Direction,
    IllegalTransition,
    InvalidAddress,
    MuredMachine,
    MuredOpcode,
    Word,
    _SavedDefinitionPath,
    _SubgraphFrame,
)
from red2_engine.pipelinec_vectors import RED2ABICodec
from thor_lang.parser import parse_expr


def _machine(words: list[Word], *, memory_words: int = 64) -> MuredMachine:
    return MuredMachine.load(
        words, quantum=10, memory_words=memory_words, control_words=16
    )


def _processor(machine: MuredMachine, codec: RED2ABICodec) -> Red2Processor:
    return Red2Processor(codec.encode_state(machine.state))


def _step_both(
    machine: MuredMachine, processor: Red2Processor, codec: RED2ABICodec
) -> None:
    machine.step()
    assert processor.run_to_commit()
    assert processor.checkpoint() == codec.encode_state(machine.state)


def test_red2_closures_v1_is_explicit() -> None:
    assert RED2_CLOSURES_V1 == 1


def test_reverse_app_enters_typed_subgraph_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [Word(MuredOpcode.APP, 8, False), Word(MuredOpcode.INT, 1, True)]
    )
    state = machine.state
    state.direction = Direction.B
    state.pc = 0
    state.fsp = 1
    state.memory[1] = Word(MuredOpcode.INT, 1, True)
    state.control_stack[0] = state.env
    state.c = 0
    state.memory[8] = Word(MuredOpcode.INT, 9, True)
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_closure_pushes_environment_marker_and_jumps_to_code() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.CLOSURE, 40, False)
    state.memory[1] = Word(None, 8, False)
    state.memory[8] = Word(MuredOpcode.INT, 7, True)
    state.pc = 0
    state.env = 48
    state.free_space = 48
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_ep_forward_matches_result_and_control_path() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.INT, 7, False)
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_ep_reverse_shareable_target_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.INT, 7, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_reverse_ep_atomic_advances_active_primitive_countdown_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.INT, 7, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    state.prim = "+"
    state.fire = 2
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.pc == 0
    assert processor.fire == 1
    assert processor.prim_id == codec.literal_id("+")
    assert processor.memory[1] == codec.encode_word(Word(MuredOpcode.INT, 7, False))


def test_reverse_ep_atomic_fires_scalar_at_countdown_zero_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.INT, 7, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    state.prim = "1+"
    state.fire = 1
    encoded = codec.encode_state(state)
    literal_id = codec.literal_id("1+")
    scalar_ops = [0] * (literal_id + 1)
    scalar_ops[literal_id] = SCALAR_OP_INC
    processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))

    _step_both(machine, processor, codec)

    assert processor.memory[1] == codec.encode_word(Word(MuredOpcode.INT, 8, True))
    assert processor.pc == 0
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_reverse_ep_q_zero_clears_deferred_primitive_and_moves_backward_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.INT, 2, False)
    state.direction = Direction.B
    state.pc = 1
    state.q = 0
    state.control_stack[0] = state.env
    state.c = 0
    state.prim = "CONS"
    state.fire = 1
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[1] == codec.encode_word(Word(MuredOpcode.INT, 2, False))
    assert processor.pc == 0
    assert processor.q == 0
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_reverse_ep_immediate_scalar_fault_is_failure_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[2] = Word(MuredOpcode.INT, 7, True)
    state.memory[40] = Word(MuredOpcode.INT, 0, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    state.prim = "/"
    state.fire = 1
    encoded = codec.encode_state(state)
    literal_id = codec.literal_id("/")
    scalar_ops = [0] * (literal_id + 1)
    scalar_ops[literal_id] = SCALAR_OP_DIV
    processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_UNSUPPORTED_VALUE
    assert processor.checkpoint() == before


def test_app_var_closure_saves_environment_path_like_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.APP_VAR, 0, False)])
    state = machine.state
    state.env = 40
    state.free_space = 40
    state.memory[40] = Word(MuredOpcode.CLOSURE, 40, False)
    state.memory[41] = Word(None, 0, False)
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_app_var_ep_saves_environment_path_like_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.APP_VAR, 0, False)])
    state = machine.state
    state.env = 40
    state.free_space = 40
    state.memory[40] = Word(MuredOpcode.EP, 42, False)
    state.memory[42] = Word(MuredOpcode.INT, 7, False)
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_typed_join_single_head_var_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.VAR, 2, True)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_typed_join_compacts_atomic_result_and_restores_frontier() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.INT, 41, True)
    state.memory[9] = Word(MuredOpcode.INT, 7, True)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)
    assert processor.fsp == 3
    assert processor.free_space == 32
    assert processor.env == 32


def test_typed_join_publishes_atomic_ep_before_frontier_restore() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[9] = Word(MuredOpcode.INT, 7, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)
    assert processor.memory[5] == codec.encode_word(Word(MuredOpcode.INT, 41, True))
    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.INT, 41, False))
    assert processor.free_space == 32
    assert processor.env == 32


def test_saved_primitive_join_compacts_single_word_defined_symbol_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.SYM, "DEFINED", True, 12)
    state.memory[12] = Word(MuredOpcode.INT, 99, True)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(
        env=32, free_space=32, prim="+", fire=2
    )
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.fsp == 3
    assert processor.memory[3] == codec.encode_word(
        Word(MuredOpcode.SYM, "DEFINED", False, 12)
    )
    assert processor.fire == 1



def test_join_discards_completed_definition_paths_above_typed_frame_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.INT, 41, True)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(
        env=32, free_space=32, prim=None, fire=0
    )
    state.control_stack[1] = _SavedDefinitionPath(22)
    state.c = 1
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.c == -1
    assert processor.control_stack[0] == 0
    assert processor.control_stack[1] == 0



def test_typed_primitive_join_restores_and_advances_countdown_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 2, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim="+", fire=2)
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)
    assert processor.fire == 1
    assert processor.prim_id == codec.literal_id("+")


def test_typed_primitive_join_fires_when_restored_countdown_reaches_zero_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 2, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim="1+", fire=1)
    state.c = 0
    encoded = codec.encode_state(state)
    literal_id = codec.literal_id("1+")
    scalar_ops = [0] * (literal_id + 1)
    scalar_ops[literal_id] = SCALAR_OP_INC
    processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.INT, 3, True))
    assert processor.pc == 2
    assert processor.fsp == 3
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_typed_primitive_join_q_zero_clears_deferred_primitive_without_dispatching() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 2, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.q = 0
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim="CONS", fire=1)
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.INT, 2, False))
    assert processor.fsp == 3
    assert processor.pc == 2
    assert processor.q == 0
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_typed_primitive_join_q_zero_clears_completed_scalar_without_contracting() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 2, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.q = 0
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim="1+", fire=1)
    state.c = 0
    encoded = codec.encode_state(state)
    literal_id = codec.literal_id("1+")
    scalar_ops = [0] * (literal_id + 1)
    scalar_ops[literal_id] = SCALAR_OP_INC
    processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.INT, 2, False))
    assert processor.q == 0
    assert processor.pc == 2
    assert processor.fsp == 3
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_typed_binary_primitive_join_fires_with_surviving_left_operand_exactly() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.INT, 7, True)
    state.memory[5] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[6] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 2, False)
    state.pc = 5
    state.fsp = 6
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim="+", fire=1)
    state.c = 0
    encoded = codec.encode_state(state)
    literal_id = codec.literal_id("+")
    scalar_ops = [0] * (literal_id + 1)
    scalar_ops[literal_id] = SCALAR_OP_ADD
    processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.INT, 9, True))
    assert processor.pc == 2
    assert processor.fsp == 3
    assert processor.q == 9
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_typed_binary_primitive_join_q_zero_preserves_left_operand_and_skips_contraction() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.INT, 7, True)
    state.memory[5] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[6] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 2, False)
    state.pc = 5
    state.fsp = 6
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.q = 0
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim="+", fire=1)
    state.c = 0
    encoded = codec.encode_state(state)
    literal_id = codec.literal_id("+")
    scalar_ops = [0] * (literal_id + 1)
    scalar_ops[literal_id] = SCALAR_OP_ADD
    processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.INT, 2, False))
    assert processor.memory[4] == codec.encode_word(Word(MuredOpcode.INT, 7, True))
    assert processor.pc == 2
    assert processor.fsp == 4
    assert processor.q == 0
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_join_immediate_scalar_fault_is_failure_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.INT, 7, True)
    state.memory[5] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[6] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 0, False)
    state.pc = 5
    state.fsp = 6
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim="/", fire=1)
    state.c = 0
    encoded = codec.encode_state(state)
    literal_id = codec.literal_id("/")
    scalar_ops = [0] * (literal_id + 1)
    scalar_ops[literal_id] = SCALAR_OP_DIV
    processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_UNSUPPORTED_VALUE
    assert processor.checkpoint() == before


def test_join_overwidth_control_frame_fault_is_typed_and_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.INT, 7, True)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    processor = _processor(machine, codec)
    processor.control_stack[0] = 1 << abi.CONTROL_WIDTH
    processor.c = 0
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_join_invalid_ep_parent_is_failure_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[3] = Word(MuredOpcode.EP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[9] = Word(MuredOpcode.INT, 7, False)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION
    assert processor.checkpoint() == before


def test_typed_join_rejects_saved_environment_inside_reclaimed_region() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.INT, 41, True)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=30, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)
    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION


def test_typed_join_materializes_escaping_closure_before_reclaim() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.EP, 28, True)
    state.memory[20] = Word(MuredOpcode.LAMBDA, "z", False)
    state.memory[21] = Word(MuredOpcode.VAR, 1, True)
    state.memory[28] = Word(MuredOpcode.CLOSURE, 30, False)
    state.memory[29] = Word(None, 20, False)
    state.memory[30] = Word(MuredOpcode.INT, 42, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.pc = 4
    state.fsp = 21
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.APP, 22, False))
    assert processor.memory[22] == codec.encode_word(
        Word(MuredOpcode.LAMBDA, "z", False)
    )
    assert processor.memory[23] == codec.encode_word(Word(MuredOpcode.INT, 42, True))
    assert processor.free_space == 32
    assert processor.env == 32

    published_parent = processor.memory[3]
    published_lambda = processor.memory[22]
    published_body = processor.memory[23]
    for address in range(28, 32):
        processor.memory[address] = codec.encode_word(
            Word(MuredOpcode.INT, 9000 + address, False)
        )

    assert processor.memory[3] == published_parent
    assert processor.memory[22] == published_lambda
    assert processor.memory[23] == published_body
    assert processor._signed_data(processor.memory[3]) == 22


def test_typed_join_publishes_shared_app_target_before_reclaim() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[4] = Word(MuredOpcode.STOP)
    state.memory[5] = Word(MuredOpcode.APP, 9, False)
    state.memory[6] = Word(MuredOpcode.JOIN, 5, False)
    state.memory[7] = Word(MuredOpcode.APP, 10, False)
    state.memory[8] = Word(MuredOpcode.APP, 10, False)
    state.memory[9] = Word(MuredOpcode.SYM, "F", True)
    state.memory[10] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.pc = 6
    state.fsp = 10
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[5] == codec.encode_word(Word(MuredOpcode.APP, 7, False))
    assert processor.memory[7] == codec.encode_word(Word(MuredOpcode.APP, 10, False))
    assert processor.memory[8] == codec.encode_word(Word(MuredOpcode.APP, 10, False))
    assert processor.memory[10] == codec.encode_word(Word(MuredOpcode.INT, 41, True))
    assert processor.free_space == 32
    assert processor.env == 32


def test_typed_join_multiword_result_remains_graph_owned() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.INT, 7, False)
    state.memory[6] = Word(MuredOpcode.SYM, "F", True)
    state.pc = 4
    state.fsp = 6
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.APP, 5, False))
    assert processor.fsp == 6
    assert processor.free_space == 32
    assert processor.env == 32


def test_typed_join_publishes_ep_to_ubv_as_graph_var_before_reclaim() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.UBV, 3, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.phi = 7
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(
        Word(MuredOpcode.APP_VAR, 4, False)
    )
    assert processor.free_space == 32
    assert processor.env == 32


def test_repeated_fixed_live_closure_join_reuses_bounded_workspace() -> None:
    # Match the oracle lifetime suite's fixed-live-state interpretation: repeat the
    # same semantic JOIN boundary at increasing counts, rather than using an Omega
    # program whose authoritative environment allocator grows on every beta step.
    for repetitions in (1, 8, 64):
        codec = RED2ABICodec()
        machine = _machine([Word(MuredOpcode.INT, 0, True)], memory_words=64)
        processor = _processor(machine, codec)
        machine_boundaries: set[tuple[int, int, int, int]] = set()
        processor_boundaries: set[tuple[int, int, int, int]] = set()

        for value in range(repetitions):
            state = machine.state
            state.memory[2] = Word(MuredOpcode.STOP)
            state.memory[3] = Word(MuredOpcode.APP, 9, False)
            state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
            state.memory[5] = Word(MuredOpcode.EP, 28, True)
            state.memory[20] = Word(MuredOpcode.LAMBDA, "z", False)
            state.memory[21] = Word(MuredOpcode.VAR, 1, True)
            state.memory[28] = Word(MuredOpcode.CLOSURE, 30, False)
            state.memory[29] = Word(None, 20, False)
            state.memory[30] = Word(MuredOpcode.INT, value, False)
            state.memory[31] = Word(MuredOpcode.PNP, 64, False)
            state.pc = 4
            state.fsp = 21
            state.env = 28
            state.free_space = 28
            state.direction = Direction.B
            state.control_stack[0] = _SubgraphFrame(
                env=32, free_space=32, prim=None, fire=0
            )
            state.c = 0

            processor.memory[2] = codec.encode_word(Word(MuredOpcode.STOP))
            processor.memory[3] = codec.encode_word(Word(MuredOpcode.APP, 9, False))
            processor.memory[4] = codec.encode_word(Word(MuredOpcode.JOIN, 3, False))
            processor.memory[5] = codec.encode_word(Word(MuredOpcode.EP, 28, True))
            processor.memory[20] = codec.encode_word(Word(MuredOpcode.LAMBDA, "z", False))
            processor.memory[21] = codec.encode_word(Word(MuredOpcode.VAR, 1, True))
            processor.memory[28] = codec.encode_word(Word(MuredOpcode.CLOSURE, 30, False))
            processor.memory[29] = codec.encode_word(Word(None, 20, False))
            processor.memory[30] = codec.encode_word(Word(MuredOpcode.INT, value, False))
            processor.memory[31] = codec.encode_word(Word(MuredOpcode.PNP, 64, False))
            processor.pc = 4
            processor.fsp = 21
            processor.env = 28
            processor.free_space = 28
            processor.direction = abi.DIRECTION_REVERSE
            processor.control_stack[0] = codec.encode_control_entry(
                _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)
            )
            processor.c = 0

            _step_both(machine, processor, codec)

            assert state.memory[3] == Word(MuredOpcode.APP, 22, False)
            assert state.memory[22] == Word(MuredOpcode.LAMBDA, "z", False)
            assert state.memory[23] == Word(MuredOpcode.INT, value, True)
            machine_boundaries.add((state.fsp, state.free_space, state.env, state.c))
            processor_boundaries.add(
                (processor.fsp, processor.free_space, processor.env, processor.c)
            )

            # Physically reuse/poison the reclaimed child arena. The published
            # closure must remain wholly graph-owned and exact afterwards.
            for address in range(28, 32):
                poison = Word(MuredOpcode.INT, 9000 + address, False)
                state.memory[address] = poison
                processor.memory[address] = codec.encode_word(poison)
            assert state.memory[3] == Word(MuredOpcode.APP, 22, False)
            assert state.memory[22] == Word(MuredOpcode.LAMBDA, "z", False)
            assert state.memory[23] == Word(MuredOpcode.INT, value, True)

        assert machine_boundaries == {(23, 32, 32, -1)}
        assert processor_boundaries == {(23, 32, 32, -1)}


def test_typed_join_published_closure_has_no_pointer_into_reclaimed_child_region() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.EP, 28, True)
    state.memory[20] = Word(MuredOpcode.LAMBDA, "z", False)
    state.memory[21] = Word(MuredOpcode.VAR, 1, True)
    state.memory[28] = Word(MuredOpcode.CLOSURE, 30, False)
    state.memory[29] = Word(None, 20, False)
    state.memory[30] = Word(MuredOpcode.INT, 42, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.pc = 4
    state.fsp = 21
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(
        env=32, free_space=32, prim=None, fire=0
    )
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    reclaimed = range(28, 32)
    published_root = state.memory[3]
    assert published_root == Word(MuredOpcode.APP, 22, False)
    assert published_root.data not in reclaimed
    assert state.memory[22] == Word(MuredOpcode.LAMBDA, "z", False)
    assert state.memory[23] == Word(MuredOpcode.INT, 42, True)

    for address in reclaimed:
        poison = Word(MuredOpcode.INT, 9000 + address, False)
        state.memory[address] = poison
        processor.memory[address] = codec.encode_word(poison)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.APP, 22, False))
    assert processor.memory[22] == codec.encode_word(Word(MuredOpcode.LAMBDA, "z", False))
    assert processor.memory[23] == codec.encode_word(Word(MuredOpcode.INT, 42, True))



def test_lambda_beta_ep_argument_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.LAMBDA, None, True)])
    state = machine.state
    state.fsp = 2
    state.memory[2] = Word(MuredOpcode.EP, 40, True)
    state.memory[40] = Word(MuredOpcode.INT, 9, False)
    state.argcnt = 1
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_lambda_beta_app_argument_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.LAMBDA, None, True)])
    state = machine.state
    state.fsp = 2
    state.memory[2] = Word(MuredOpcode.APP, 7, True)
    state.argcnt = 1
    state.control_stack[0] = 33
    state.c = 0
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_var_head_ep_to_ubv_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.VAR, 0, True)])
    state = machine.state
    state.env = 40
    state.free_space = 40
    state.memory[40] = Word(MuredOpcode.EP, 42, False)
    state.memory[42] = Word(MuredOpcode.UBV, 0, False)
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_var_head_ep_to_closure_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.VAR, 0, True)])
    state = machine.state
    state.env = 40
    state.free_space = 40
    state.memory[40] = Word(MuredOpcode.EP, 42, False)
    state.memory[42] = Word(MuredOpcode.CLOSURE, 44, False)
    state.memory[43] = Word(None, 8, False)
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_var_direct_closure_jumps_to_environment_cell_like_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.VAR, 0, True)])
    state = machine.state
    state.env = 40
    state.free_space = 40
    state.memory[40] = Word(MuredOpcode.CLOSURE, 44, False)
    state.memory[41] = Word(None, 8, False)
    processor = _processor(machine, codec)
    _step_both(machine, processor, codec)


def test_app_var_multi_hop_pnp_lookup_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.APP_VAR, 0, False)])
    state = machine.state
    state.env = 40
    state.free_space = 40
    state.memory[40] = Word(MuredOpcode.PNP, 48, False)
    state.memory[48] = Word(MuredOpcode.PNP, 56, False)
    state.memory[56] = Word(MuredOpcode.INT, 12, False)
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.s_a == 56
    assert processor.s_d == 0


def test_reverse_ep_multi_hop_chain_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.EP, 48, False)
    state.memory[48] = Word(MuredOpcode.EP, 56, False)
    state.memory[56] = Word(MuredOpcode.INT, 7, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[1] == codec.encode_word(Word(MuredOpcode.INT, 7, False))


def test_real_reverse_app_child_join_round_trip_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [
            Word(MuredOpcode.INT, 0, False),
            Word(MuredOpcode.APP, 8, False),
            Word(MuredOpcode.INT, 1, True),
        ]
    )
    state = machine.state
    parent_env = state.env
    state.direction = Direction.B
    state.pc = 1
    state.fsp = 2
    state.control_stack[0] = parent_env
    state.c = 0
    state.memory[8] = Word(MuredOpcode.INT, 9, True)
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)
    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.JOIN, 1, False))
    _step_both(machine, processor, codec)
    _step_both(machine, processor, codec)

    assert processor.memory[1] == codec.encode_word(Word(MuredOpcode.INT, 9, False))
    assert processor.pc == 0
    assert processor.env == parent_env
    assert processor.free_space == parent_env
    assert processor.c == -1


def test_nested_real_app_subgraph_join_sequence_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [
            Word(MuredOpcode.INT, 0, False),
            Word(MuredOpcode.APP, 8, False),
            Word(MuredOpcode.INT, 1, True),
        ]
    )
    state = machine.state
    parent_env = state.env
    state.direction = Direction.B
    state.pc = 1
    state.fsp = 2
    state.control_stack[0] = parent_env
    state.c = 0
    state.memory[8] = Word(MuredOpcode.APP, 12, False)
    state.memory[9] = Word(MuredOpcode.INT, 7, True)
    state.memory[12] = Word(MuredOpcode.INT, 42, True)
    processor = _processor(machine, codec)

    # Outer APP creates its own frame and JOIN.
    _step_both(machine, processor, codec)
    assert isinstance(state.control_stack[0], _SubgraphFrame)
    assert state.memory[3] == Word(MuredOpcode.JOIN, 1, False)
    assert (state.pc, state.fsp, state.c) == (8, 3, 0)

    # Execute the child APP and its following head atom. The copied APP becomes
    # the next reverse transition and therefore creates a second real subgraph.
    _step_both(machine, processor, codec)
    _step_both(machine, processor, codec)
    assert state.memory[4] == Word(MuredOpcode.APP, 12, False)
    assert (state.pc, state.direction) == (4, Direction.B)

    _step_both(machine, processor, codec)
    assert isinstance(state.control_stack[0], _SubgraphFrame)
    assert isinstance(state.control_stack[1], _SubgraphFrame)
    assert state.memory[6] == Word(MuredOpcode.JOIN, 4, False)
    assert (state.pc, state.fsp, state.c) == (12, 6, 1)

    # Inner child evaluates, then its generated JOIN returns into the outer child.
    _step_both(machine, processor, codec)
    assert (state.pc, state.direction) == (6, Direction.B)
    _step_both(machine, processor, codec)
    assert state.memory[4] == Word(MuredOpcode.INT, 42, False)
    assert state.memory[5] == Word(MuredOpcode.INT, 7, True)
    assert (state.pc, state.c) == (3, 0)
    assert state.env == parent_env
    assert state.free_space == parent_env

    # Outer generated JOIN publishes the two-word child result and restores the
    # original parent environment, frontier, and control depth exactly.
    _step_both(machine, processor, codec)
    assert state.memory[1] == Word(MuredOpcode.APP, 4, False)
    assert state.memory[4] == Word(MuredOpcode.INT, 42, False)
    assert state.memory[5] == Word(MuredOpcode.INT, 7, True)
    assert state.pc == 0
    assert state.env == parent_env
    assert state.free_space == parent_env
    assert state.c == -1


def test_app_var_malformed_ep_fault_is_architecturally_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.APP_VAR, 0, False)])
    state = machine.state
    state.env = 40
    state.free_space = 40
    state.memory[40] = Word(MuredOpcode.EP, -1, False)
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_reverse_ep_malformed_chain_fault_is_architecturally_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.EP, -1, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_reverse_app_collision_fault_preserves_saved_parent_path() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.APP, 8, False)]
    )
    state = machine.state
    state.pc = 1
    state.fsp = 5
    state.env = 6
    state.free_space = 6
    state.direction = Direction.B
    state.control_stack[0] = 6
    state.c = 0
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert processor.checkpoint() == before


def test_forward_app_control_overflow_fault_does_not_publish_graph_result() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.APP, 8, False)])
    processor = _processor(machine, codec)
    processor.c = len(processor.control_stack) - 1
    processor.control_stack[processor.c] = abi.pack_control_entry(
        abi.CONTROL_ADDRESS, processor.env, 0, 0, 0
    )
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_CONTROL_OVERFLOW
    assert processor.checkpoint() == before


def test_reverse_app_overwidth_control_entry_fault_is_typed_and_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.APP, 8, False)]
    )
    state = machine.state
    state.pc = 1
    state.direction = Direction.B
    processor = _processor(machine, codec)
    processor.control_stack[0] = 1 << abi.CONTROL_WIDTH
    processor.c = 0
    before = processor.checkpoint()

    assert processor.run_to_commit(max_clocks=16) is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_reverse_app_wrong_control_tag_fault_does_not_consume_entry() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.APP, 8, False)]
    )
    state = machine.state
    state.pc = 1
    state.direction = Direction.B
    processor = _processor(machine, codec)
    processor.control_stack[0] = abi.pack_control_entry(
        abi.CONTROL_SUBGRAPH, processor.env, processor.free_space, 0, 0
    )
    processor.c = 0
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION
    assert processor.checkpoint() == before


def test_reverse_app_invalid_fsp_fault_preserves_saved_parent_path() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.APP, 8, False)]
    )
    state = machine.state
    state.pc = 1
    state.direction = Direction.B
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)
    processor.fsp = len(processor.memory)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_reverse_app_invalid_frontier_fault_preserves_saved_parent_path() -> None:
    codec = RED2ABICodec()
    machine = _machine(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.APP, 8, False)]
    )
    state = machine.state
    state.pc = 1
    state.direction = Direction.B
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)
    processor.free_space = len(processor.memory) + 1
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert processor.checkpoint() == before


def test_reverse_ep_overwidth_control_entry_fault_is_typed_and_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.INT, 7, False)
    state.direction = Direction.B
    state.pc = 1
    processor = _processor(machine, codec)
    processor.control_stack[0] = 1 << abi.CONTROL_WIDTH
    processor.c = 0
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_reverse_ep_closure_invalid_fsp_fault_is_architecturally_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.CLOSURE, 44, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)
    processor.fsp = len(processor.memory)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_reverse_ep_closure_invalid_frontier_fault_is_architecturally_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    state = machine.state
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.EP, 40, False)
    state.memory[40] = Word(MuredOpcode.CLOSURE, 44, False)
    state.direction = Direction.B
    state.pc = 1
    state.control_stack[0] = state.env
    state.c = 0
    processor = _processor(machine, codec)
    processor.free_space = len(processor.memory) + 1
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert processor.checkpoint() == before


def test_forward_ep_malformed_chain_fault_matches_oracle_and_is_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    machine.state.memory[0] = Word(MuredOpcode.EP, 40, False)
    machine.state.memory[40] = Word(MuredOpcode.EP, -1, False)
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    with pytest.raises(InvalidAddress, match="EP requires an environment address"):
        machine.step()
    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_INVALID_ADDRESS
    assert processor.checkpoint() == before


def test_forward_ep_cycle_fault_matches_oracle_and_is_atomic() -> None:
    codec = RED2ABICodec()
    machine = _machine([Word(MuredOpcode.INT, 0, True)])
    machine.state.memory[0] = Word(MuredOpcode.EP, 40, False)
    machine.state.memory[40] = Word(MuredOpcode.EP, 48, False)
    machine.state.memory[48] = Word(MuredOpcode.EP, 40, False)
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    with pytest.raises(IllegalTransition, match="cyclic EP environment chain"):
        machine.step()
    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION
    assert processor.checkpoint() == before

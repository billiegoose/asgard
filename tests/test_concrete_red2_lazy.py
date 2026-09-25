import pytest

from abstract_red2_machine.machine import (
    AbstractRED2Machine,
    AbstractRED2MachineState,
    Direction,
    MuredOpcode,
    Word,
    _SubgraphFrame,
)
from concrete_red2_machine import abi
from concrete_red2_machine.machine import (
    PRIM0_ROLE_IF,
    PRIM0_ROLE_Y,
    RED2_LAZY_V1,
    ConcreteRED2Machine,
)
from concrete_red2_machine.pipelinec_vectors import RED2ABICodec


def _processor(machine: AbstractRED2Machine, codec: RED2ABICodec) -> ConcreteRED2Machine:
    true_id = codec.literal_id("TRUE")
    false_id = codec.literal_id("FALSE")
    nil_id = codec.literal_id("NIL")
    if_id = codec.literal_id("IF")
    y_id = codec.literal_id("Y")
    reconstruct_id = codec.literal_id("__IF_RECONSTRUCT__")
    encoded = codec.encode_state(machine.state)
    role_image = [0] * (max(if_id, y_id) + 1)
    role_image[if_id] = PRIM0_ROLE_IF
    role_image[y_id] = PRIM0_ROLE_Y
    return ConcreteRED2Machine(
        encoded,
        prim0_roles=tuple(role_image),
        true_literal_id=true_id,
        false_literal_id=false_id,
        nil_literal_id=nil_id,
        if_reconstruct_literal_id=reconstruct_id,
    )


def _step_both(
    machine: AbstractRED2Machine,
    processor: ConcreteRED2Machine,
    codec: RED2ABICodec,
) -> None:
    machine.step()
    assert processor.run_to_commit()
    assert processor.checkpoint() == codec.encode_state(machine.state)


def test_red2_lazy_v1_is_explicit() -> None:
    assert RED2_LAZY_V1 == 1


@pytest.mark.parametrize(("quantum", "argcnt"), [(0, 1), (3, 0)])
def test_y_without_budget_or_argument_is_passive_exactly(
    quantum: int,
    argcnt: int,
) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=1 if argcnt else 0,
        fsp=3 if argcnt else 2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=quantum,
        phi=0,
        argcnt=argcnt,
    )
    if argcnt:
        state.memory[0] = Word(MuredOpcode.INT, 7, True)
        state.memory[1] = Word(MuredOpcode.PRIM_0, "Y", True)
        state.memory[3] = Word(MuredOpcode.INT, 7, True)
    else:
        state.memory[0] = Word(MuredOpcode.PRIM_0, "Y", True)
        state.memory[2] = Word(MuredOpcode.STOP)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


def test_y_immediate_unfold_matches_oracle_and_points_to_original_code() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=1,
        fsp=3,
        env=12,
        c=-1,
        direction=Direction.F,
        q=4,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.SYM, "F", True, 9)
    state.memory[1] = Word(MuredOpcode.PRIM_0, "Y", True)
    state.memory[3] = Word(MuredOpcode.SYM, "F", True, 9)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[3] == codec.encode_word(Word(MuredOpcode.APP, 0, False))
    assert processor.memory[4] == codec.encode_word(Word(MuredOpcode.SYM, "F", True, 9))
    assert processor.fsp == 3
    assert processor.c == 0
    assert abi.control_tag(processor.control_stack[0]) == abi.CONTROL_ADDRESS
    assert abi.control_field(processor.control_stack[0], 0) == 12


def test_repeated_y_immediate_unfold_reuses_one_scratch_cell() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=1,
        fsp=3,
        env=12,
        c=-1,
        direction=Direction.F,
        q=4,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.SYM, "F", True, 9)
    state.memory[1] = Word(MuredOpcode.PRIM_0, "Y", True)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    recursive = codec.encode_word(Word(MuredOpcode.APP, 0, False))
    headed_f = codec.encode_word(Word(MuredOpcode.SYM, "F", True, 9))

    boundaries: set[tuple[int, int, int]] = set()
    for iteration in range(32):
        state.pc = 1
        state.fsp = 3
        state.c = -1
        state.q = 4
        state.argcnt = 1
        state.direction = Direction.F
        state.memory[3] = Word(MuredOpcode.SYM, "F", True, 9)
        state.memory[4] = None
        for index in range(len(state.control_stack)):
            state.control_stack[index] = None

        processor.pc = 1
        processor.fsp = 3
        processor.c = -1
        processor.q = 4
        processor.argcnt = 1
        processor.direction = abi.DIRECTION_FORWARD
        processor.memory[3] = headed_f
        processor.memory[4] = 0
        for index in range(len(processor.control_stack)):
            processor.control_stack[index] = 0
        processor.microstate = 0
        processor.fault = abi.FAULT_NONE

        _step_both(machine, processor, codec)

        scratch = processor.fsp + 1
        boundaries.add((processor.fsp, scratch, processor.c))
        assert processor.memory[3] == recursive
        assert processor.memory[scratch] == headed_f
        processor.memory[scratch] = codec.encode_word(
            Word(MuredOpcode.INT, iteration, True)
        )
        assert processor.memory[3] == recursive

    assert boundaries == {(3, 4, 0)}


def test_y_app_unfold_does_not_push_an_extra_path() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 16,
        control_stack=[None] * 4,
        pc=1,
        fsp=5,
        env=16,
        c=0,
        direction=Direction.F,
        q=4,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.APP, 8, True)
    state.memory[1] = Word(MuredOpcode.PRIM_0, "Y", True)
    state.memory[5] = Word(MuredOpcode.APP, 8, True)
    state.memory[8] = Word(MuredOpcode.INT, 1, True)
    state.control_stack[0] = 13
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.c == 0
    assert abi.control_field(processor.control_stack[0], 0) == 13
    assert processor.memory[5] == codec.encode_word(Word(MuredOpcode.APP, 0, False))


@pytest.mark.parametrize("overflow", ["scratch", "control"])
def test_y_immediate_capacity_fault_is_failure_atomic(overflow: str) -> None:
    control = [None] * 4
    c = -1
    env = 4 if overflow == "scratch" else 10
    free_space = 4 if overflow == "scratch" else 10
    if overflow == "control":
        control = [17]
        c = 0
    state = AbstractRED2MachineState(
        memory=[None] * (8 if overflow == "scratch" else 10),
        control_stack=control,
        pc=1,
        fsp=3,
        env=env,
        free_space=free_space,
        c=c,
        direction=Direction.F,
        q=2,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.SYM, "F", True)
    state.memory[1] = Word(MuredOpcode.PRIM_0, "Y", True)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault in (abi.FAULT_GRAPH_ENV_COLLISION, abi.FAULT_CONTROL_OVERFLOW)
    assert processor.checkpoint() == before


@pytest.mark.parametrize("condition", ["TRUE", "FALSE"])
def test_if_boolean_app_selection_matches_oracle_without_join(condition: str) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 16,
        control_stack=[None] * 6,
        pc=4,
        fsp=5,
        env=16,
        c=1,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[2] = Word(MuredOpcode.APP, 9, False)
    state.memory[3] = Word(MuredOpcode.APP, 10, False)
    state.memory[4] = Word(MuredOpcode.SYM, condition, False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[9] = Word(MuredOpcode.INT, 99, True)
    state.memory[10] = Word(MuredOpcode.INT, 42, True)
    state.control_stack[0] = 14
    state.control_stack[1] = 15
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.c == -1
    assert processor.direction == abi.DIRECTION_FORWARD
    assert processor.pc == (10 if condition == "TRUE" else 9)
    assert processor.env == (15 if condition == "TRUE" else 14)


def test_if_dead_malformed_app_branch_is_never_dereferenced() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 16,
        control_stack=[None] * 4,
        pc=4,
        fsp=5,
        env=16,
        c=0,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[2] = Word(MuredOpcode.APP, 999, False)
    state.memory[3] = Word(MuredOpcode.INT, 7, False)
    state.memory[4] = Word(MuredOpcode.SYM, "TRUE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.control_stack[0] = 14
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[2] == codec.encode_word(Word(MuredOpcode.INT, 7, True))
    assert processor.fault == abi.FAULT_NONE


def test_if_selected_shared_ep_atom_matches_oracle() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 24,
        control_stack=[None] * 6,
        pc=4,
        fsp=5,
        env=24,
        c=0,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[2] = Word(MuredOpcode.INT, 9, False)
    state.memory[3] = Word(MuredOpcode.EP, 12, False)
    state.memory[4] = Word(MuredOpcode.SYM, "TRUE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[12] = Word(MuredOpcode.INT, 42, False, closure_slot=True)
    state.control_stack[0] = 20
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


def test_if_selected_ep_closure_enters_captured_branch_without_join() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 24,
        control_stack=[None] * 6,
        pc=4,
        fsp=5,
        env=24,
        c=0,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[2] = Word(MuredOpcode.INT, 9, False)
    state.memory[3] = Word(MuredOpcode.EP, 12, False)
    state.memory[4] = Word(MuredOpcode.SYM, "TRUE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[12] = Word(MuredOpcode.CLOSURE, 18, False)
    state.memory[13] = Word(None, 8)
    state.memory[8] = Word(MuredOpcode.INT, 42, True)
    state.control_stack[0] = 20
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.pc == 12
    assert processor.fsp == 1
    assert processor.env == 20
    assert processor.c == -1
    assert processor.direction == abi.DIRECTION_FORWARD


def test_if_selected_ep_cycle_faults_without_architectural_commit() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 16,
        control_stack=[None] * 4,
        pc=4,
        fsp=5,
        env=16,
        c=0,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[2] = Word(MuredOpcode.INT, 9, False)
    state.memory[3] = Word(MuredOpcode.EP, 12, False)
    state.memory[4] = Word(MuredOpcode.SYM, "TRUE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[12] = Word(MuredOpcode.EP, 13, False)
    state.memory[13] = Word(MuredOpcode.EP, 12, False)
    state.control_stack[0] = 20
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.run_to_commit(max_clocks=4096) is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION
    assert processor.checkpoint() == before


def test_join_completion_fires_if_through_lazy_dispatcher() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 32,
        control_stack=[None] * 8,
        pc=4,
        fsp=5,
        env=28,
        free_space=28,
        c=0,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
    )
    state.memory[0] = Word(MuredOpcode.STOP)
    state.memory[1] = Word(MuredOpcode.INT, 9, False)
    state.memory[2] = Word(MuredOpcode.INT, 7, False)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.SYM, "TRUE", False)
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim="IF",
        fire=1,
    )
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[1] == codec.encode_word(Word(MuredOpcode.INT, 7, True))
    assert processor.fsp == 1
    assert processor.pc == 1
    assert processor.q == 2
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_reverse_ep_completion_fires_if_through_lazy_dispatcher() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 16,
        control_stack=[None] * 4,
        pc=3,
        fsp=3,
        env=16,
        c=0,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[0] = Word(MuredOpcode.STOP)
    state.memory[1] = Word(MuredOpcode.INT, 9, False)
    state.memory[2] = Word(MuredOpcode.INT, 7, False)
    state.memory[3] = Word(MuredOpcode.EP, 12, False)
    state.memory[12] = Word(MuredOpcode.SYM, "TRUE", False)
    state.control_stack[0] = 16
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    assert processor.memory[1] == codec.encode_word(Word(MuredOpcode.INT, 7, True))
    assert processor.fsp == 1
    assert processor.pc == 1
    assert processor.q == 2
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_if_boolean_fire_at_zero_quantum_skips_both_branches() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=4,
        fsp=5,
        env=12,
        c=1,
        direction=Direction.B,
        q=0,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.APP, 8, False)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.SYM, "TRUE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.control_stack[0] = 10
    state.control_stack[1] = 11
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


@pytest.mark.parametrize(
    ("false_branch", "true_branch"),
    [
        (Word(MuredOpcode.APP, 9, False), Word(MuredOpcode.APP, 10, False)),
        (Word(MuredOpcode.APP, 9, False), Word(MuredOpcode.EP, 12, False)),
        (Word(MuredOpcode.INT, 7, False), Word(MuredOpcode.APP, 10, False)),
        (Word(MuredOpcode.APP, 9, False), Word(MuredOpcode.INT, 7, False)),
        (Word(MuredOpcode.INT, 6, False), Word(MuredOpcode.INT, 7, False)),
    ],
)
def test_if_non_boolean_reconstruction_boundary_matches_oracle(
    false_branch: Word,
    true_branch: Word,
) -> None:
    path_count = int(false_branch.opcode in (MuredOpcode.APP, MuredOpcode.EP)) + int(
        true_branch.opcode in (MuredOpcode.APP, MuredOpcode.EP)
    )
    state = AbstractRED2MachineState(
        memory=[None] * 16,
        control_stack=[None] * 8,
        pc=4,
        fsp=5,
        env=16,
        c=path_count - 1,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
        prim="IF",
        fire=1,
    )
    state.memory[2] = false_branch
    state.memory[3] = true_branch
    state.memory[4] = Word(MuredOpcode.SYM, "MAYBE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    if path_count:
        state.control_stack[0] = 20
    if path_count > 1:
        state.control_stack[1] = 21
    if true_branch.opcode in (MuredOpcode.APP, MuredOpcode.EP) and path_count == 1:
        state.control_stack[0] = 21
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)

    if path_count:
        assert processor.q == 0
        assert processor.prim_id == codec.literal_id("__IF_RECONSTRUCT__")
        assert processor.fire == path_count
        assert processor.c == path_count
        assert abi.control_tag(processor.control_stack[0]) == abi.CONTROL_SAVED_QUANTUM
        assert abi.control_field(processor.control_stack[0], 0) == 3
    else:
        assert processor.q == 3
        assert processor.prim_id == 0
        assert processor.fire == 0
        assert processor.c == -1

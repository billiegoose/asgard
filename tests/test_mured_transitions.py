import pytest

from red2_engine.mured import (
    ControlStackUnderflow,
    Direction,
    IllegalTransition,
    InvalidAddress,
    MuredMachine,
    MuredMachineState,
    MuredOpcode,
    Word,
)


def base_machine() -> MuredMachine:
    return MuredMachine.load(
        [Word(MuredOpcode.LAMBDA, "x"), Word(MuredOpcode.VAR, 0)],
        quantum=3,
        memory_words=32,
        control_words=8,
    )


def test_app_forward_copies_word_saves_env_and_advances() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[0] = Word(MuredOpcode.APP, 9)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP, 9)
    assert state.fsp == 3
    assert state.control_stack[0] == 32
    assert state.c == 0
    assert state.pc == 1
    assert state.direction is Direction.F
    assert state.cycles == 1


def test_app_var_forward_resolves_ubv_and_pushes_corrected_app_var() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[0] = Word(MuredOpcode.APP_VAR, 0, False)
    state.memory[30] = Word(MuredOpcode.UBV, 1)
    state.env = 30
    state.phi = 4

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP_VAR, 3, False)
    assert state.fsp == 3
    assert state.pc == 1
    assert state.direction is Direction.F
    assert state.cycles == 1


def test_app_var_forward_resolves_closure_and_pushes_control_path() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[0] = Word(MuredOpcode.APP_VAR, 0, False)
    state.memory[30] = Word(MuredOpcode.CLOSURE, 28)
    state.memory[31] = Word(None, 7)
    state.env = 30

    machine.step()

    assert state.control_stack[0] == 28
    assert state.c == 0
    assert state.memory[3] == Word(MuredOpcode.APP, 7, False)
    assert state.fsp == 3
    assert state.pc == 1
    assert state.direction is Direction.F
    assert state.cycles == 1


def test_app_var_forward_rejects_bool_payload() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[0] = Word(MuredOpcode.APP_VAR, True, False)
    state.memory[30] = Word(MuredOpcode.UBV, 1)
    state.memory[31] = Word(MuredOpcode.UBV, 1)
    state.env = 30
    state.phi = 4

    with pytest.raises(
        InvalidAddress, match="APP_VAR requires a non-negative variable index"
    ):
        machine.step()


def test_app_reverse_creates_join_with_parent_pointer() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.memory[9] = Word(MuredOpcode.VAR, 0)
    state.pc = 3
    state.fsp = 3
    state.env = 20
    state.control_stack[0] = 27
    state.c = 0
    state.direction = Direction.B

    machine.step()

    assert state.env == 27
    assert state.c == -1
    assert state.memory[4] == Word(MuredOpcode.JOIN, 3)
    assert state.fsp == 4
    assert state.pc == 9
    assert state.direction is Direction.F


def test_app_var_reverse_only_decrements_pc() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP_VAR, 0, False)
    state.pc = 3
    state.fsp = 3
    state.env = 20
    state.direction = Direction.B

    machine.step()

    assert state.pc == 2
    assert state.fsp == 3
    assert state.env == 20
    assert state.direction is Direction.B


def test_lookup_skips_ubv_closure_and_follows_parent_pointer() -> None:
    machine = base_machine()
    state = machine.state
    state.env = 20
    state.memory[20] = Word(MuredOpcode.UBV, 3)
    state.memory[21] = Word(MuredOpcode.CLOSURE, 28)
    state.memory[22] = Word(None, 7)
    state.memory[23] = Word(MuredOpcode.PNP, 27)
    state.memory[27] = Word(MuredOpcode.UBV, 1)

    assert machine.lookup(0) == 20
    assert machine.lookup(1) == 21
    assert machine.lookup(2) == 27
    assert state.s_d == 0
    assert state.s_a == 27


def test_lambda_contracts_against_result_app() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.control_stack[0] = 32
    state.c = 0
    state.fsp = 3

    machine.step()

    assert state.q == 2
    assert state.fsp == 2
    assert state.c == -1
    assert state.env == 30
    assert state.memory[30] == Word(MuredOpcode.CLOSURE, 32)
    assert state.memory[31] == Word(None, 9)
    assert state.pc == 1


def test_lambda_contracts_against_result_app_var_without_popping_control() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP_VAR, 1, False)
    state.control_stack[0] = 22
    state.c = 0
    state.fsp = 3
    state.env = 30
    state.phi = 4

    machine.step()

    assert state.q == 2
    assert state.fsp == 2
    assert state.c == 0
    assert state.control_stack[0] == 22
    assert state.env == 29
    assert state.memory[29] == Word(MuredOpcode.UBV, 3, False)
    assert state.pc == 1


def test_lambda_without_redex_copies_and_allocates_ubv() -> None:
    machine = base_machine()
    state = machine.state

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.LAMBDA, "x")
    assert state.fsp == 3
    assert state.memory[31] == Word(MuredOpcode.UBV, 1)
    assert state.env == 31
    assert state.phi == 1
    assert state.pc == 1


def test_int_forward_head_copies_itself_then_begins_reverse_traversal() -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=0,
        fsp=1,
        env=8,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.INT, 42, True)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    original_q = state.q
    original_phi = state.phi

    machine.step()

    copied = state.memory[state.fsp]
    assert copied == Word(MuredOpcode.INT, 42, True)
    assert (state.direction, state.pc, state.q, state.phi) == (
        Direction.B,
        state.fsp - 1,
        original_q,
        original_phi,
    )


def test_int_forward_non_head_copies_itself_and_advances_through_source_spine() -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=0,
        fsp=1,
        env=8,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.INT, 7, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    original_pc = state.pc

    machine.step()

    copied = state.memory[state.fsp]
    assert copied == Word(MuredOpcode.INT, 7, False)
    assert (state.direction, state.pc) == (Direction.F, original_pc + 1)


def test_int_reverse_changes_only_pc() -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=5,
        fsp=1,
        env=8,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
    )
    state.memory[4] = Word(MuredOpcode.STOP)
    state.memory[5] = Word(MuredOpcode.INT, 7, False)
    machine = MuredMachine(state)
    original_state = (
        state.direction,
        state.fsp,
        state.env,
        state.c,
        state.q,
        state.phi,
    )

    machine.step()

    assert state.pc == 4
    assert (
        state.direction,
        state.fsp,
        state.env,
        state.c,
        state.q,
        state.phi,
    ) == original_state


@pytest.mark.parametrize("payload", ["bad", None])
def test_int_forward_rejects_non_integer_payloads(payload: str | None) -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=0,
        fsp=1,
        env=8,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.INT, payload, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    with pytest.raises(IllegalTransition, match="INT requires an integer value"):
        machine.step()


def test_var_uses_lookup_and_executes_environment_value() -> None:
    machine = base_machine()
    state = machine.state
    state.pc = 1
    state.env = 31
    state.memory[31] = Word(MuredOpcode.UBV, 1)
    state.phi = 1

    machine.step()

    assert state.s_d == 0
    assert state.s_a == 31
    assert state.pc == 31


def test_ubv_emits_var_and_switches_to_reverse() -> None:
    machine = base_machine()
    state = machine.state
    state.pc = 31
    state.env = 31
    state.memory[31] = Word(MuredOpcode.UBV, 1)
    state.memory[3] = Word(MuredOpcode.LAMBDA, "x")
    state.phi = 1
    state.fsp = 3

    machine.step()

    assert state.memory[4] == Word(MuredOpcode.VAR, 0, True)
    assert state.fsp == 4
    assert state.pc == 3
    assert state.direction is Direction.B


def test_join_inserts_argument_root_and_walks_parent_backward() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[4] = Word(MuredOpcode.JOIN, 3)
    state.memory[5] = Word(MuredOpcode.INT, 0)
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.pc = 4
    state.fsp = 5
    state.direction = Direction.B

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP, 5)
    assert state.s_a == 5
    assert state.pc == 2


def test_join_converts_reduced_var_to_app_var_and_reclaims_tail() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.memory[4] = Word(MuredOpcode.JOIN, 3)
    state.memory[5] = Word(MuredOpcode.VAR, 0)
    state.pc = 4
    state.fsp = 5
    state.direction = Direction.B

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP_VAR, 0, False)
    assert state.s_a == 5
    assert state.fsp == 3
    assert state.pc == 2


def test_closure_adds_parent_path_and_jumps_to_code() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[20] = Word(MuredOpcode.CLOSURE, 27)
    state.memory[21] = Word(None, 9)
    state.memory[9] = Word(MuredOpcode.VAR, 0)
    state.pc = 20
    state.env = 20

    machine.step()

    assert state.env == 19
    assert state.memory[19] == Word(MuredOpcode.PNP, 27)
    assert state.pc == 9


def test_stop_is_reverse_only_and_points_pc_at_result_root() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.LAMBDA, "x")
    state.pc = 2
    state.fsp = 3
    state.direction = Direction.B

    machine.step()

    assert state.halted is True
    assert state.pc == 3
    assert state.cycles == 1


def test_reverse_app_requires_saved_environment() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.pc = 3
    state.fsp = 3
    state.direction = Direction.B

    with pytest.raises(ControlStackUnderflow):
        machine.step()
    assert state.cycles == 0


def test_stop_rejects_forward_execution() -> None:
    machine = base_machine()
    state = machine.state
    state.pc = 2

    with pytest.raises(IllegalTransition, match="STOP requires backward execution"):
        machine.step()

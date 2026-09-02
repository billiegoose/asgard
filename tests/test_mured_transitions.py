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


@pytest.mark.parametrize(
    ("opcode", "payload"),
    [
        (MuredOpcode.FLOAT, 1.5),
        (MuredOpcode.CHAR, "a"),
    ],
)
def test_passive_float_and_char_forward_head_copy_exact_word_and_reverse(
    opcode: MuredOpcode,
    payload: float | str,
) -> None:
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
    state.memory[0] = Word(opcode, payload, True)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    copied = state.memory[state.fsp]
    assert copied == Word(opcode, payload, True)
    assert (state.direction, state.pc) == (Direction.B, state.fsp - 1)


@pytest.mark.parametrize(
    ("opcode", "payload"),
    [
        (MuredOpcode.FLOAT, 2.5),
        (MuredOpcode.CHAR, "z"),
    ],
)
def test_passive_float_and_char_forward_non_head_copies_and_advances(
    opcode: MuredOpcode,
    payload: float | str,
) -> None:
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
    state.memory[0] = Word(opcode, payload, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    copied = state.memory[state.fsp]
    assert copied == Word(opcode, payload, False)
    assert (state.direction, state.pc) == (Direction.F, 1)


@pytest.mark.parametrize(
    "opcode",
    [MuredOpcode.FLOAT, MuredOpcode.CHAR],
)
def test_passive_float_and_char_reverse_only_decrement_pc(opcode: MuredOpcode) -> None:
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
    state.memory[5] = Word(opcode, 7.0 if opcode is MuredOpcode.FLOAT else "q", False)
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


@pytest.mark.parametrize(
    ("opcode", "payload"),
    [
        (MuredOpcode.SYM, "FOO"),
    ],
)
def test_sym_forward_head_copies_itself_then_begins_reverse_traversal(
    opcode: MuredOpcode,
    payload: str,
) -> None:
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
    state.memory[0] = Word(opcode, payload, True)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    copied = state.memory[state.fsp]
    assert copied == Word(opcode, payload, True)
    assert (state.direction, state.pc) == (Direction.B, state.fsp - 1)


@pytest.mark.parametrize(
    ("opcode", "payload"),
    [
        (MuredOpcode.SYM, "bar"),
    ],
)
def test_sym_forward_non_head_copies_and_advances(
    opcode: MuredOpcode,
    payload: str,
) -> None:
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
    state.memory[0] = Word(opcode, payload, False, 5)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    copied = state.memory[state.fsp]
    assert copied == Word(opcode, payload, False, 5)
    assert (state.direction, state.pc) == (Direction.F, 1)


def test_sym_reverse_non_head_with_definition_only_decrements_pc() -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=3,
        fsp=3,
        env=8,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.SYM, "bar", False, 5)
    machine = MuredMachine(state)
    original_state = (
        state.memory[3],
        tuple(state.control_stack),
        state.c,
        state.pc,
        state.direction,
    )

    machine.step()

    assert state.pc == 2
    assert state.memory[3] == original_state[0]
    assert tuple(state.control_stack) == original_state[1]
    assert state.c == original_state[2]
    assert state.direction is original_state[4]


def test_sym_head_with_definition_and_zero_quantum_remains_passive() -> None:
    state = MuredMachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=0,
        fsp=1,
        env=12,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.SYM, "FOO", True, 9)
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[9] = Word(MuredOpcode.INT, 42, True)
    state.memory[10] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[state.fsp] == Word(MuredOpcode.SYM, "FOO", True, 9)
    assert (state.direction, state.pc) == (Direction.B, state.fsp - 1)


def test_sym_head_with_definition_forward_enters_reverse_copy_path() -> None:
    state = MuredMachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=0,
        fsp=1,
        env=12,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
    )
    state.memory[0] = Word(MuredOpcode.SYM, "FOO", True, 9)
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[9] = Word(MuredOpcode.INT, 42, True)
    state.memory[10] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[state.fsp] == Word(MuredOpcode.SYM, "FOO", True, 9)
    assert state.direction is Direction.B
    assert state.pc == state.fsp
    assert state.q == 3


def test_sym_reverse_definition_converts_to_app_and_pushes_control_path() -> None:
    state = MuredMachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=2,
        fsp=2,
        env=12,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.SYM, "FOO", True, 9)
    state.memory[9] = Word(MuredOpcode.INT, 42, True)
    state.memory[10] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[2] == Word(MuredOpcode.APP, 1, True, 9)
    assert state.control_stack[0] == 12
    assert state.c == 0
    assert state.direction is Direction.B
    assert state.pc == 2


def test_defined_symbol_app_reverse_enters_definition_code() -> None:
    state = MuredMachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=2,
        fsp=2,
        env=12,
        c=0,
        direction=Direction.B,
        q=3,
        phi=0,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.APP, 1, True, 9)
    state.memory[9] = Word(MuredOpcode.INT, 42, True)
    state.memory[10] = Word(MuredOpcode.STOP)
    state.control_stack[0] = 12
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[2] == Word(MuredOpcode.STOP)
    assert state.pc == 9
    assert state.direction is Direction.F
    assert state.q == 2
    assert state.control_stack[0] == 12


def test_sym_reverse_only_decrements_pc() -> None:
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
    state.memory[5] = Word(MuredOpcode.SYM, "baz", False)
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


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (1, "SYM requires a non-empty symbol name"),
        (True, "SYM requires a non-empty symbol name"),
        ("", "SYM requires a non-empty symbol name"),
    ],
)
def test_sym_forward_rejects_malformed_payloads(
    payload: int | bool | str,
    message: str,
) -> None:
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
    state.memory[0] = Word(MuredOpcode.SYM, payload, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    with pytest.raises(IllegalTransition, match=message):
        machine.step()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (1, "FLOAT requires a floating-point value"),
        (True, "FLOAT requires a floating-point value"),
        ("bad", "FLOAT requires a floating-point value"),
    ],
)
def test_float_forward_rejects_malformed_payloads(
    payload: int | bool | str,
    message: str,
) -> None:
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
    state.memory[0] = Word(MuredOpcode.FLOAT, payload, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    with pytest.raises(IllegalTransition, match=message):
        machine.step()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("", "CHAR requires a single-character string"),
        ("ab", "CHAR requires a single-character string"),
        (1, "CHAR requires a single-character string"),
    ],
)
def test_char_forward_rejects_malformed_payloads(
    payload: int | str,
    message: str,
) -> None:
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
    state.memory[0] = Word(MuredOpcode.CHAR, payload, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    with pytest.raises(IllegalTransition, match=message):
        machine.step()


def test_int_forward_non_head_copies_itself_and_advances_through_source_spine() -> None:
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

def test_prim_forward_pushes_word_and_sets_registers() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.PRIM_2, 1, False)],
        quantum=3,
        memory_words=32,
        control_words=8,
    )
    machine.step()
    assert machine.state.memory[2] == Word(MuredOpcode.PRIM_2, 1, False)
    assert machine.state.fsp == 2
    assert machine.state.prim == 1
    assert machine.state.fire == 0
    assert machine.state.pc == 1
    assert machine.state.direction is Direction.F

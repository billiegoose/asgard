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
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


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
    assert state.argcnt == 1
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
    assert state.argcnt == 1
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
    assert state.argcnt == 1
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
    state.argcnt = 4

    machine.step()

    assert state.env == 27
    assert state.c == -1
    assert state.memory[4] == Word(MuredOpcode.JOIN, 3)
    assert state.fsp == 4
    assert state.pc == 9
    assert state.direction is Direction.F
    assert state.argcnt == 0


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
    state.argcnt = 1

    machine.step()

    assert state.q == 2
    assert state.fsp == 2
    assert state.c == -1
    assert state.env == 30
    assert state.memory[30] == Word(MuredOpcode.CLOSURE, 32)
    assert state.memory[31] == Word(None, 9)
    assert state.pc == 1
    assert state.argcnt == 0


def test_lambda_contracts_against_result_app_var_without_popping_control() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP_VAR, 1, False)
    state.control_stack[0] = 22
    state.c = 0
    state.fsp = 3
    state.env = 30
    state.phi = 4
    state.argcnt = 1

    machine.step()

    assert state.q == 2
    assert state.fsp == 2
    assert state.c == 0
    assert state.control_stack[0] == 22
    assert state.env == 29
    assert state.memory[29] == Word(MuredOpcode.UBV, 3, False)
    assert state.pc == 1
    assert state.argcnt == 0


def test_lambda_without_redex_copies_and_allocates_ubv() -> None:
    machine = base_machine()
    state = machine.state
    state.argcnt = 2

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.LAMBDA, "x")
    assert state.fsp == 3
    assert state.memory[31] == Word(MuredOpcode.UBV, 1)
    assert state.env == 31
    assert state.phi == 1
    assert state.pc == 1
    assert state.argcnt == 0


def test_struct_without_selector_saves_quantum_and_allocates_ubv() -> None:
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

    machine.step()

    assert state.memory[6] == Word(MuredOpcode.STRUCT, "PAIR", False)
    assert state.fsp == 6
    assert state.q == 0
    assert state.phi == 3
    assert state.env == 15
    assert state.memory[15] == Word(MuredOpcode.UBV, 3, False)
    assert state.c == 0
    assert state.control_stack[0] is not None
    assert state.pc == 1
    assert state.argcnt == 0


def test_struct_reverse_restores_quantum_and_binder_depth() -> None:
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

    machine.step()
    copied_struct = state.fsp
    state.pc = copied_struct
    state.direction = Direction.B

    machine.step()

    assert state.q == 9
    assert state.c == -1
    assert state.phi == 0
    assert state.pc == copied_struct - 1
    assert state.direction is Direction.B


def test_struct_with_selector_app_contracts_like_lambda() -> None:
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

    machine.step()

    assert state.q == 3
    assert state.fsp == 5
    assert state.c == -1
    assert state.env == 18
    assert state.memory[18] == Word(MuredOpcode.CLOSURE, 20, False)
    assert state.memory[19] == Word(None, 12, False)
    assert state.pc == 1
    assert state.argcnt == 0


def test_struct_with_selector_and_zero_quantum_reconstructs_lazily() -> None:
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

    machine.step()

    assert state.q == 0
    assert state.memory[6] == Word(MuredOpcode.STRUCT, "PAIR", False)
    assert state.fsp == 6
    assert state.phi == 1
    assert state.env == 15
    assert state.memory[15] == Word(MuredOpcode.UBV, 1, False)
    assert state.argcnt == 0
    assert state.c == 1
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
    assert state.argcnt == 1
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
    assert state.argcnt == 1
    assert (state.direction, state.pc) == (Direction.F, 1)


def test_sym_reverse_non_head_with_definition_remains_passive() -> None:
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
    state.memory[3] = Word(MuredOpcode.SYM, "FOO", False, 5)
    machine = MuredMachine(state)

    machine.step()

    assert state.pc == 2
    assert state.memory[3] == Word(MuredOpcode.SYM, "FOO", False, 5)
    assert state.control_stack == [None] * 4
    assert state.c == -1
    assert state.direction is Direction.B


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
        argcnt=3,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.SYM, "FOO", True, 9)
    state.memory[9] = Word(MuredOpcode.INT, 42, True)
    state.memory[10] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[2] == Word(MuredOpcode.APP, 1, True, 9)
    assert state.argcnt == 2
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
    state.argcnt = 2

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP, 5)
    assert state.s_a == 5
    assert state.pc == 2
    assert state.argcnt == 2


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


@pytest.mark.parametrize(
    ("opcode", "name", "arity"),
    [
        (MuredOpcode.PRIM_1, "NOT", 1),
        (MuredOpcode.PRIM_2, "+", 2),
    ],
)
def test_head_strict_primitive_primes_without_firing(
    opcode: MuredOpcode,
    name: str,
    arity: int,
) -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=arity,
    )
    state.memory[0] = Word(opcode, name, True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(opcode, name, True)
    assert state.argcnt == arity + 1
    assert state.prim == name
    assert state.fire == arity
    assert (state.direction, state.pc) == (Direction.B, 2)
    assert state.q == 3


@pytest.mark.parametrize(
    ("argcnt", "quantum"),
    [
        (1, 3),
        (2, 0),
    ],
)
def test_head_binary_primitive_stays_unprimed_without_arity_or_quantum(
    argcnt: int,
    quantum: int,
) -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=quantum,
        phi=0,
        argcnt=argcnt,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_2, "+", True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.PRIM_2, "+", True)
    assert state.argcnt == argcnt + 1
    assert state.prim is None
    assert state.fire == 0
    assert (state.direction, state.pc) == (Direction.B, 2)


def test_non_head_strict_primitive_is_passive() -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=2,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_2, "+", False)
    state.memory[1] = Word(MuredOpcode.INT, 1, True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.PRIM_2, "+", False)
    assert state.argcnt == 3
    assert state.prim is None
    assert state.fire == 0
    assert (state.direction, state.pc) == (Direction.F, 1)


def test_head_if_primes_only_the_condition() -> None:
    state = MuredMachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=0,
        fsp=3,
        env=12,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=3,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[4] == Word(MuredOpcode.PRIM_0, "IF", True)
    assert state.argcnt == 4
    assert state.q == 3
    assert state.prim == "IF"
    assert state.fire == 1
    assert (state.direction, state.pc) == (Direction.B, 3)


def test_head_if_with_zero_quantum_is_passive() -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=0,
        argcnt=3,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.PRIM_0, "IF", True)
    assert state.q == 0
    assert state.prim is None
    assert state.fire == 0
    assert (state.direction, state.pc) == (Direction.B, 2)


def test_head_if_with_too_few_arguments_is_passive() -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=2,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.PRIM_0, "IF", True)
    assert state.q == 3
    assert state.prim is None
    assert state.fire == 0
    assert (state.direction, state.pc) == (Direction.B, 2)


def test_non_head_y_is_passive() -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_0, "Y", False)
    state.memory[1] = Word(MuredOpcode.INT, 7, True)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.PRIM_0, "Y", False)
    assert state.argcnt == 2
    assert state.q == 3
    assert (state.direction, state.pc) == (Direction.F, 1)


def test_head_y_with_no_argument_is_passive() -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=0,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_0, "Y", True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.PRIM_0, "Y", True)
    assert state.argcnt == 1
    assert state.q == 3
    assert state.prim is None
    assert state.fire == 0
    assert (state.direction, state.pc) == (Direction.B, 2)


def test_head_y_with_zero_quantum_is_passive() -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=1,
        fsp=3,
        env=10,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.INT, 7, True)
    state.memory[1] = Word(MuredOpcode.PRIM_0, "Y", True)
    state.memory[3] = Word(MuredOpcode.INT, 7, True)
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[4] == Word(MuredOpcode.PRIM_0, "Y", True)
    assert state.argcnt == 2
    assert state.q == 0
    assert (state.direction, state.pc) == (Direction.B, 3)


def test_head_y_rewrites_non_app_argument_with_temporary_head_copy() -> None:
    state = MuredMachineState(
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
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP, 0, False)
    assert state.memory[4] == Word(MuredOpcode.SYM, "F", True, 9)
    assert state.fsp == 3
    assert state.q == 3
    assert state.c == 0
    assert state.control_stack[0] == 12
    assert state.argcnt == 1
    assert state.prim is None
    assert state.fire == 0
    assert (state.direction, state.pc) == (Direction.F, 4)


def test_head_y_rewrites_app_argument_and_follows_code_without_extra_path_push(
) -> None:
    state = MuredMachineState(
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
    machine = MuredMachine(state)

    machine.step()

    assert state.memory[5] == Word(MuredOpcode.APP, 0, False)
    assert state.fsp == 5
    assert state.q == 3
    assert state.c == 0
    assert state.control_stack[0] == 13
    assert state.argcnt == 1
    assert (state.direction, state.pc) == (Direction.F, 8)


def test_primitive_reverse_only_walks_backward() -> None:
    state = MuredMachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=5,
        fsp=5,
        env=10,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=4,
        prim="+",
        fire=2,
    )
    state.memory[4] = Word(MuredOpcode.STOP)
    state.memory[5] = Word(MuredOpcode.PRIM_2, "+", True)
    machine = MuredMachine(state)

    machine.step()

    assert state.pc == 4
    assert state.argcnt == 4
    assert state.prim == "+"
    assert state.fire == 2
    assert state.direction is Direction.B


def test_reverse_app_saves_active_primitive_context_before_argument_reduction() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.memory[9] = Word(MuredOpcode.INT, 2, True)
    state.pc = 3
    state.fsp = 3
    state.env = 20
    state.control_stack[0] = 27
    state.c = 0
    state.direction = Direction.B
    state.prim = "+"
    state.fire = 2

    machine.step()

    assert state.env == 27
    assert state.c >= 1
    assert state.prim is None
    assert state.fire == 0
    assert state.memory[4] == Word(MuredOpcode.JOIN, 3, False, 1)
    assert (state.direction, state.pc) == (Direction.F, 9)


def test_nested_app_join_does_not_restore_outer_primitive_context() -> None:
    expr = parse_expr("(INTEGER? (FOO X))")
    machine = MuredMachine.from_expr(
        expr,
        quantum=20,
        memory_words=128,
        control_words=32,
    )

    machine.run()

    assert to_source(machine.result_expr()) == "(INTEGER? (FOO X))"


def test_join_restores_primitive_context_compacts_int_and_decrements_fire() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.memory[9] = Word(MuredOpcode.INT, 2, True)
    state.pc = 3
    state.fsp = 3
    state.env = 20
    state.control_stack[0] = 27
    state.c = 0
    state.direction = Direction.B
    state.prim = "+"
    state.fire = 2

    machine.step()
    state.memory[5] = Word(MuredOpcode.INT, 2, True)
    state.pc = 4
    state.fsp = 5
    state.direction = Direction.B

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.INT, 2, False)
    assert state.fsp == 3
    assert state.c == -1
    assert state.prim == "+"
    assert state.fire == 1
    assert state.pc == 2


@pytest.mark.parametrize(
    ("primitive", "operand", "expected"),
    [
        (
            "1+",
            Word(MuredOpcode.FLOAT, 1.5, False),
            Word(MuredOpcode.FLOAT, 2.5, True),
        ),
        (
            "FLOOR",
            Word(MuredOpcode.FLOAT, 3.75, False),
            Word(MuredOpcode.INT, 3, True),
        ),
        (
            "EVEN?",
            Word(MuredOpcode.INT, 8, False),
            Word(MuredOpcode.SYM, "TRUE", True),
        ),
        (
            "NOT",
            Word(MuredOpcode.SYM, "TRUE", False),
            Word(MuredOpcode.SYM, "FALSE", True),
        ),
        (
            "CHAR?",
            Word(MuredOpcode.CHAR, "a", False),
            Word(MuredOpcode.SYM, "TRUE", True),
        ),
    ],
)
def test_unary_strict_primitive_fire_overwrites_and_reclaims(
    primitive: str,
    operand: Word,
    expected: Word,
) -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=4,
        env=8,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
        prim=primitive,
        fire=0,
    )
    state.memory[2] = operand
    state.memory[3] = Word(MuredOpcode.PRIM_1, primitive, True)

    MuredMachine(state)._fire_primitive()

    assert state.memory[2] == expected
    assert state.fsp == 2
    assert state.q == 2
    assert state.pc == 1
    assert state.prim is None
    assert state.fire == 0


@pytest.mark.parametrize(
    ("primitive", "second", "first", "expected"),
    [
        (
            "+",
            Word(MuredOpcode.FLOAT, 0.5, False),
            Word(MuredOpcode.INT, 2, False),
            Word(MuredOpcode.FLOAT, 2.5, True),
        ),
        (
            "/",
            Word(MuredOpcode.INT, 2, False),
            Word(MuredOpcode.INT, 7, False),
            Word(MuredOpcode.FLOAT, 3.5, True),
        ),
        (
            "<",
            Word(MuredOpcode.FLOAT, 2.5, False),
            Word(MuredOpcode.INT, 2, False),
            Word(MuredOpcode.SYM, "TRUE", True),
        ),
        (
            "=",
            Word(MuredOpcode.CHAR, "a", False),
            Word(MuredOpcode.CHAR, "a", False),
            Word(MuredOpcode.SYM, "TRUE", True),
        ),
    ],
)
def test_binary_strict_primitive_fire_handles_atomic_result_types(
    primitive: str,
    second: Word,
    first: Word,
    expected: Word,
) -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=5,
        env=8,
        c=-1,
        direction=Direction.B,
        q=4,
        phi=0,
        prim=primitive,
        fire=0,
    )
    state.memory[2] = second
    state.memory[3] = first
    state.memory[4] = Word(MuredOpcode.PRIM_2, primitive, True)

    MuredMachine(state)._fire_primitive()

    assert state.memory[2] == expected
    assert state.fsp == 2
    assert state.q == 3
    assert state.pc == 1


@pytest.mark.parametrize(
    ("condition", "selected", "kept_path"),
    [
        ("TRUE", Word(MuredOpcode.APP, 10, False), 21),
        ("FALSE", Word(MuredOpcode.APP, 9, False), 20),
    ],
)
def test_if_boolean_fire_selects_one_lazy_branch_and_reclaims_spine(
    condition: str,
    selected: Word,
    kept_path: int,
) -> None:
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 6,
        pc=4,
        fsp=5,
        env=16,
        c=1,
        direction=Direction.B,
        q=3,
        phi=0,
        prim="IF",
        fire=0,
    )
    state.memory[2] = Word(MuredOpcode.APP, 9, False)
    state.memory[3] = Word(MuredOpcode.APP, 10, False)
    state.memory[4] = Word(MuredOpcode.SYM, condition, False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.control_stack[0] = 20
    state.control_stack[1] = 21

    MuredMachine(state)._fire_primitive()

    assert state.fsp == 1
    assert state.pc == selected.data
    assert state.q == 2
    assert state.env == kept_path
    assert state.c == -1
    assert state.control_stack[0] is None
    assert state.control_stack[1] is None
    assert state.argcnt == 0
    assert state.direction is Direction.F
    assert state.prim is None
    assert state.fire == 0


def test_if_boolean_fire_with_exhausted_quantum_reconstructs() -> None:
    state = MuredMachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=4,
        fsp=5,
        env=12,
        c=1,
        direction=Direction.B,
        q=0,
        phi=0,
        prim="IF",
        fire=0,
    )
    state.memory[2] = Word(MuredOpcode.APP, 8, False)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.SYM, "TRUE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.control_stack[0] = 10
    state.control_stack[1] = 11
    before = list(state.memory)

    MuredMachine(state)._fire_primitive()

    assert state.memory == before
    assert state.fsp == 5
    assert state.pc == 1
    assert state.q == 0
    assert state.c == -1
    assert state.control_stack[0] is None
    assert state.control_stack[1] is None
    assert state.prim is None
    assert state.fire == 0


def test_if_non_boolean_fire_starts_zero_quantum_branch_reconstruction() -> None:
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 8,
        pc=4,
        fsp=5,
        env=16,
        c=1,
        direction=Direction.B,
        q=3,
        phi=0,
        prim="IF",
        fire=0,
    )
    state.memory[2] = Word(MuredOpcode.APP, 9, False)
    state.memory[3] = Word(MuredOpcode.APP, 10, False)
    state.memory[4] = Word(MuredOpcode.SYM, "MAYBE", False)
    state.memory[5] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.control_stack[0] = 20
    state.control_stack[1] = 21

    MuredMachine(state)._fire_primitive()

    assert state.q == 0
    assert state.pc == 3
    assert state.prim == "__IF_RECONSTRUCT__"
    assert state.fire == 2
    assert state.c == 2
    assert state.control_stack[1] == 20
    assert state.control_stack[2] == 21


def test_wrong_type_strict_fire_leaves_compact_spine_unchanged() -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=5,
        env=8,
        c=-1,
        direction=Direction.B,
        q=4,
        phi=0,
        prim="MOD",
        fire=0,
    )
    state.memory[2] = Word(MuredOpcode.FLOAT, 2.0, False)
    state.memory[3] = Word(MuredOpcode.INT, 7, False)
    state.memory[4] = Word(MuredOpcode.PRIM_2, "MOD", True)
    before = list(state.memory)

    MuredMachine(state)._fire_primitive()

    assert state.memory == before
    assert state.fsp == 5
    assert state.q == 4
    assert state.pc == 1


def test_strict_fire_with_exhausted_quantum_leaves_compact_spine_unchanged() -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=5,
        env=8,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        prim="-",
        fire=0,
    )
    state.memory[2] = Word(MuredOpcode.INT, 2, False)
    state.memory[3] = Word(MuredOpcode.INT, 7, False)
    state.memory[4] = Word(MuredOpcode.PRIM_2, "-", True)
    before = list(state.memory)

    MuredMachine(state)._fire_primitive()

    assert state.memory == before
    assert state.fsp == 5
    assert state.q == 0
    assert state.pc == 1


def test_deferred_strict_primitive_fire_remains_unreduced() -> None:
    state = MuredMachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=4,
        env=8,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
        prim="TAG",
        fire=0,
    )
    state.memory[2] = Word(MuredOpcode.SYM, "NIL", False)
    state.memory[3] = Word(MuredOpcode.PRIM_1, "TAG", True)
    before = list(state.memory)

    MuredMachine(state)._fire_primitive()

    assert state.memory == before
    assert state.fsp == 4
    assert state.q == 3
    assert state.pc == 1


def test_primitive_rejects_malformed_name() -> None:
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
    state.memory[0] = Word(MuredOpcode.PRIM_1, "", True)
    state.memory[1] = Word(MuredOpcode.STOP)

    with pytest.raises(
        IllegalTransition,
        match="PRIM requires a non-empty primitive name",
    ):
        MuredMachine(state).step()

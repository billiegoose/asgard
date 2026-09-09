import pytest

from red2_engine.mured import (
    Direction,
    GraphEnvironmentCollision,
    IllegalTransition,
    InvalidAddress,
    MuredMachine,
    MuredOpcode,
    Word,
)


def test_load_places_problem_stop_and_registers() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.LAMBDA, "x"), Word(MuredOpcode.VAR, 0)],
        quantum=7,
        memory_words=16,
        control_words=4,
    )

    state = machine.state
    assert state.memory[:3] == [
        Word(MuredOpcode.LAMBDA, "x"),
        Word(MuredOpcode.VAR, 0),
        Word(MuredOpcode.STOP),
    ]
    assert state.pc == 0
    assert state.fsp == 2
    assert state.env == 16
    assert state.c == -1
    assert state.direction is Direction.F
    assert state.q == 7
    assert state.phi == 0
    assert state.argcnt == 0
    assert state.prim is None
    assert state.fire == 0
    assert state.s_a is None
    assert state.s_d is None
    assert state.cycles == 0
    assert state.halted is False


def test_load_rejects_problem_that_meets_environment() -> None:
    with pytest.raises(
        GraphEnvironmentCollision, match="graph and environment collide"
    ):
        MuredMachine.load(
            [Word(MuredOpcode.VAR, 0)] * 4,
            quantum=1,
            memory_words=4,
        )


def test_step_rejects_variable_lookup_past_empty_environment() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.VAR, 0)],
        quantum=1,
        memory_words=8,
    )

    with pytest.raises(InvalidAddress, match="invalid μRED address: 8"):
        machine.step()
    assert machine.state.cycles == 0


def test_step_allows_rblock_argcnt_minus_one_sentinel() -> None:
    machine = MuredMachine.load([Word(MuredOpcode.INT, 1, False)], quantum=1)
    machine.state.argcnt = -1

    machine.step()

    assert machine.state.argcnt == 0
    assert machine.state.cycles == 1


@pytest.mark.parametrize(("field", "value"), [("argcnt", -2), ("fire", -1)])
def test_step_rejects_invalid_machine_counters(field: str, value: int) -> None:
    machine = MuredMachine.load([Word(MuredOpcode.INT, 1, True)], quantum=1)
    setattr(machine.state, field, value)

    with pytest.raises(IllegalTransition, match="μRED counters"):
        machine.step()
    assert machine.state.cycles == 0


def test_step_rejects_empty_primitive_register_name() -> None:
    machine = MuredMachine.load([Word(MuredOpcode.INT, 1, True)], quantum=1)
    machine.state.prim = ""

    with pytest.raises(IllegalTransition, match="prim register requires a symbol name"):
        machine.step()
    assert machine.state.cycles == 0


def test_live_quantum_suspension_recharges_same_machine_without_reconstruction(
) -> None:
    from red2_engine.mured import MuredStopReason
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    machine = MuredMachine.from_expr(
        parse_expr("(+ (+ (+ 1 2) 3) 4)"),
        quantum=1,
        memory_words=128,
        control_words=32,
    )
    identity = id(machine)
    suspensions = 0

    while True:
        stop = machine.run_until_suspend(
            cycle_limit=machine.state.cycles + 100_000
        )
        if stop.reason is MuredStopReason.COMPLETE:
            break
        assert stop.reason is MuredStopReason.QUANTUM_EXHAUSTED
        assert machine.state.halted is False
        assert machine.state.q == 0
        suspensions += 1
        machine.recharge_quantum(1)

    assert suspensions >= 2
    assert id(machine) == identity
    assert to_source(machine.result_expr()) == "10"


def test_checkpoint_quantum_reconstructs_and_restarts_same_machine() -> None:
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    machine = MuredMachine.from_expr(
        parse_expr("(+ (+ 1 2) (+ 3 4))"),
        quantum=1,
        memory_words=128,
        control_words=32,
    )
    identity = id(machine)

    machine.run(cycle_limit=100_000)
    assert machine.state.halted is True
    assert to_source(machine.result_expr()) != "10"

    # Restart the bounded prefix, make live progress, then checkpoint that
    # partially reduced state through the ordinary q=0 reconstruction path.
    machine.recharge_quantum(2)
    machine.run_until_suspend(cycle_limit=machine.state.cycles + 100_000)
    assert machine.state.halted is False

    machine.checkpoint_quantum(10)

    assert id(machine) == identity
    assert machine.state.halted is False
    assert machine.state.q == 10
    machine.run(cycle_limit=machine.state.cycles + 100_000)
    assert to_source(machine.result_expr()) == "10"


def test_recharging_quantum_relinearizes_inline_struct_fields() -> None:
    from red2_engine.mured import Direction, MuredMachineState, MuredOpcode, Word
    from thor_lang.pretty import to_source

    state = MuredMachineState(
        memory=[None] * 32,
        control_stack=[None] * 8,
        pc=0,
        fsp=3,
        env=32,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        halted=True,
    )
    state.memory[0] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[1] = Word(MuredOpcode.INT, 2, False)
    state.memory[2] = Word(MuredOpcode.INT, 1, False)
    state.memory[3] = Word(MuredOpcode.VAR, 0, True)
    machine = MuredMachine(state)

    assert to_source(machine.result_expr()) == "[1 | 2]"

    machine.recharge_quantum(1)
    machine.run()

    assert to_source(machine.result_expr()) == "[1 | 2]"


def test_recharging_quantum_resumes_same_mured_machine() -> None:
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    machine = MuredMachine.from_expr(
        parse_expr("(+ (+ 1 2) 3)"),
        quantum=1,
        memory_words=128,
        control_words=32,
    )

    identity = id(machine)
    machine.run()
    assert to_source(machine.result_expr()) == "(+ 3 3)"
    assert machine.state.q == 0

    machine.recharge_quantum(1)
    machine.run()

    assert id(machine) == identity
    assert to_source(machine.result_expr()) == "6"


def test_recharging_quantum_preserves_static_faithful_definitions() -> None:
    from thor_compile.red2 import (
        load_faithful_machine,
        prepare_faithful_definitions,
    )
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    prepared = prepare_faithful_definitions(
        {"F": parse_expr("(LAMBDA (x) (+ x 1))")},
        memory_words=256,
    )
    machine = load_faithful_machine(
        parse_expr("(F 4)"),
        quantum=1,
        definitions=prepared,
        memory_words=256,
        control_words=64,
    )
    static_before = tuple(machine.state.memory[prepared.static_start :])
    identity = id(machine)

    machine.run()
    assert to_source(machine.result_expr()) == "((LAMBDA (x) (+ x 1)) 4)"

    for _ in range(3):
        machine.recharge_quantum(1)
        machine.run(cycle_limit=machine.state.cycles + 100_000)

    assert id(machine) == identity
    assert to_source(machine.result_expr()) == "5"
    assert tuple(machine.state.memory[prepared.static_start :]) == static_before


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("(IO-RETURN [1 2])", "[1 2]"),
        ("(IO-RETURN (LAMBDA (x) x))", "(LAMBDA (x) x)"),
        ("(IO-THEN (IO-RETURN 1) (IO-RETURN 2))", "2"),
    ],
)
def test_native_io_combinators_reduce_inside_one_mured_machine(
    source: str,
    expected: str,
) -> None:
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    machine = MuredMachine.from_expr(
        parse_expr(source),
        quantum=100,
        memory_words=512,
        control_words=128,
    )
    identity = id(machine)

    machine.run(cycle_limit=100_000)

    assert id(machine) == identity
    assert to_source(machine.result_expr()) == expected


def test_io_bind_structured_value_is_out_of_scope_for_current_host_io() -> None:
    from thor_lang.parser import parse_expr

    machine = MuredMachine.from_expr(
        parse_expr(
            "((LAMBDA (outer) "
            "(IO-BIND "
            "(IO-RETURN (LAMBDA (x) (+ x outer))) "
            "(LAMBDA (f) (IO-RETURN (f 1))))) 41)"
        ),
        quantum=100,
        memory_words=512,
        control_words=128,
    )

    with pytest.raises(IllegalTransition, match="IO-BIND supports only atomic"):
        machine.run(cycle_limit=100_000)


def test_clock_host_primitive_suspends_and_resumes_same_machine() -> None:
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    machine = MuredMachine.from_expr(
        parse_expr("(IO-BIND (CLOCK) (LAMBDA (now) (IO-RETURN now)))"),
        quantum=100,
        memory_words=512,
        control_words=128,
    )
    identity = id(machine)

    machine.run(cycle_limit=100_000)

    assert id(machine) == identity
    assert machine.state.halted is False
    assert machine.pending_host_call is not None
    assert machine.pending_host_call.name == "CLOCK"
    assert machine.pending_host_call.argument_address is None
    quantum_before_resume = machine.state.q

    machine.resume_host_call(Word(MuredOpcode.INT, 1_700_000_000_789))
    assert machine.state.q == quantum_before_resume - 1
    assert machine.pending_host_call is None

    machine.run(cycle_limit=machine.state.cycles + 100_000)

    assert id(machine) == identity
    assert to_source(machine.result_expr()) == "1700000000789"


def test_uart_tx_host_primitive_suspends_after_strict_argument_reduction() -> None:
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    machine = MuredMachine.from_expr(
        parse_expr("(IO-THEN (UART-TX (+ 64 1)) (IO-RETURN 7))"),
        quantum=100,
        memory_words=512,
        control_words=128,
    )

    machine.run(cycle_limit=100_000)

    call = machine.pending_host_call
    assert call is not None
    assert call.name == "UART-TX"
    assert call.argument_address is not None
    assert machine.state.memory[call.argument_address] == Word(
        MuredOpcode.INT, 65, False
    )
    quantum_before_resume = machine.state.q

    machine.resume_host_call(Word(MuredOpcode.SYM, "NIL"))
    assert machine.state.q == quantum_before_resume - 1

    machine.run(cycle_limit=machine.state.cycles + 100_000)

    assert to_source(machine.result_expr()) == "7"


def test_resume_host_call_requires_pending_call() -> None:
    machine = MuredMachine.load([Word(MuredOpcode.INT, 1, True)], quantum=1)

    with pytest.raises(IllegalTransition, match="no pending host call"):
        machine.resume_host_call(Word(MuredOpcode.INT, 2))


def test_run_until_suspend_does_not_expose_internal_if_reconstruction_q_zero() -> None:
    from red2_engine.mured import MuredStopReason
    from thor_lang.parser import parse_expr
    from thor_lang.pretty import to_source

    machine = MuredMachine.from_expr(
        parse_expr("(IF TRUE (+ 1 2) (+ 3 4))"),
        quantum=20,
        memory_words=128,
        control_words=32,
    )

    stop = machine.run_until_suspend(cycle_limit=100_000)

    assert stop.reason is MuredStopReason.COMPLETE
    assert to_source(machine.result_expr()) == "3"

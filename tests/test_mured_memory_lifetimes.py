from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from red2_engine.io_runtime import Red2IoHost, Red2RechargeEvent, run_red2_io_action
from red2_engine.mured import (
    Direction,
    IllegalTransition,
    MuredMachine,
    MuredOpcode,
    MuredStopReason,
    Word,
    _SubgraphFrame,
)
from thor_compile.red2 import load_faithful_machine
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_expr, parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition


@dataclass
class FakeHost(Red2IoHost):
    rx_values: list[int | None] = field(default_factory=list)
    clock_value: int = 123
    writes: list[bytes] = field(default_factory=list)

    def uart_rx(self) -> int | None:
        if not self.rx_values:
            return None
        return self.rx_values.pop(0)

    def uart_tx(self, data: bytes) -> None:
        self.writes.append(data)

    def clock_ms(self) -> int:
        return self.clock_value


def prepare(source: str) -> tuple[Expr, dict[str, Expr]]:
    program = normalize_program(parse_program(source))
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    definitions.pop("CAR", None)
    definitions.pop("CDR", None)
    action: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
        else:
            action = form
    assert action is not None
    return action, definitions


def run_expr(
    source: str,
    *,
    quantum: int = 10_000,
    memory_words: int = 512,
    poison: bool = False,
) -> MuredMachine:
    machine = MuredMachine.from_expr(
        parse_expr(source),
        quantum=quantum,
        memory_words=memory_words,
        control_words=128,
        memory_diagnostics=True,
        poison_reclaimed_environment=poison,
    )
    machine.run(cycle_limit=200_000)
    return machine


def assert_diagnostics(machine: MuredMachine, expected: set[str]) -> None:
    events = machine.memory_events()
    assert events
    assert all(isinstance(event.cycle, int) for event in events)
    assert expected <= {event.name for event in events}
    snapshot = machine.memory_snapshot()
    assert snapshot.graph_words > 0
    assert snapshot.peak_graph_words >= snapshot.graph_words
    assert snapshot.peak_environment_words >= snapshot.environment_words
    assert snapshot.minimum_gap > 0


def test_memory_diagnostics_are_disabled_by_default() -> None:
    machine = MuredMachine.from_expr(parse_expr("((LAMBDA (x) x) 42)"), quantum=10)
    machine.run()

    assert machine.memory_events() == ()
    assert to_source(machine.result_expr()) == "42"


def test_strict_nested_application_records_join_and_environment_allocation() -> None:
    machine = run_expr("(+ ((LAMBDA (z) z) 7) 1)", poison=True)

    assert to_source(machine.result_expr()) == "8"
    assert_diagnostics(
        machine,
        {"SUBGRAPH_ENTER", "JOIN_RETURN", "ENV_ALLOC", "ENV_RECLAIM"},
    )


def test_captured_closure_survives_poisoned_environment_debug_mode() -> None:
    machine = run_expr(
        "(((LAMBDA (x) ((LAMBDA (f) (f 0)) "
        "  ((LAMBDA (y) (LAMBDA (z) x)) 1))) 42))",
        poison=True,
    )

    assert to_source(machine.result_expr()) == "42"
    assert "ENV_ALLOC" in {event.name for event in machine.memory_events()}


def test_strict_arithmetic_y_countdown_records_graph_rewinds() -> None:
    machine = run_expr(
        "((Y (LAMBDA (self) (LAMBDA (n) "
        "(IF (= n 0) 0 (+ 1 (self (1- n))))))) 6)",
        memory_words=768,
    )

    assert to_source(machine.result_expr()) == "6"
    snapshot = machine.memory_snapshot()
    assert snapshot.graph_rewinds > 0
    assert snapshot.frontier_restores > 0


def test_if_does_not_evaluate_unselected_app_branch() -> None:
    machine = run_expr("(IF TRUE 1 ((LAMBDA (x) x) DOES-NOT-RUN))")

    assert to_source(machine.result_expr()) == "1"
    assert_diagnostics(machine, {"GRAPH_REWIND"})


def test_io_then_and_io_bind_recursion_record_io_events() -> None:
    source = """
    loop ==
      (LAMBDA (n)
        (IF (= n 5)
            (IO-RETURN n)
            (IO-BIND (CLOCK)
              (LAMBDA (now)
                (IO-THEN (UART-TX 46) (loop (+ n 1)))))))
    (loop 0)
    """
    action, definitions = prepare(source)
    host = FakeHost(clock_value=123)
    result = run_red2_io_action(
        action,
        definitions=definitions,
        quantum=20_000,
        host=host,
        memory_words=512,
        recharge_on={Red2RechargeEvent.QUANTUM_EXHAUSTED},
    )

    assert to_source(result) == "5"
    assert b"".join(host.writes) == b"....."


def test_io_bind_atomic_clock_loop_runs_5000_iterations_without_checkpoint() -> None:
    source = """
    loop ==
      (LAMBDA (n)
        (IF (= n 5000)
            (IO-RETURN n)
            (IO-BIND (CLOCK)
              (LAMBDA (now) (loop (+ n 1))))))
    (loop 0)
    """
    action, definitions = prepare(source)
    machine = load_faithful_machine(
        action,
        quantum=1000,
        definitions=definitions,
        memory_words=65_536,
        control_words=1024,
        memory_diagnostics=True,
    )

    while True:
        stop = machine.run_until_suspend(cycle_limit=machine.state.cycles + 100_000)
        if stop.reason is MuredStopReason.HOST_CALL:
            assert stop.host_call is not None
            assert stop.host_call.name == "CLOCK"
            machine.resume_host_call(Word(MuredOpcode.INT, 123))
            machine.refresh_quantum(1000)
            continue
        if stop.reason is MuredStopReason.QUANTUM_EXHAUSTED:
            machine.recharge_quantum(1000)
            continue
        assert stop.reason is MuredStopReason.COMPLETE
        break

    assert to_source(machine.result_expr()) == "5000"
    snapshot = machine.memory_snapshot()
    assert snapshot.host_checkpoints == 0
    assert snapshot.frontier_restores > 0
    assert snapshot.minimum_gap > 0
    io_events = [event for event in machine.memory_events() if event.name == "IO_BIND"]
    assert len(io_events) == 5000
    assert all(event.data.get("reserved_upper_arena") is False for event in io_events)


def test_io_bind_atomic_host_value_does_not_reserve_upper_environment_graphs() -> None:
    action, definitions = prepare("(IO-BIND (CLOCK) (LAMBDA (x) (IO-RETURN x)))")
    machine = load_faithful_machine(
        action,
        quantum=1000,
        definitions=definitions,
        memory_words=256,
        memory_diagnostics=True,
    )
    stop = machine.run_until_suspend()
    assert stop.host_call is not None
    machine.resume_host_call(Word(MuredOpcode.INT, 99))
    machine.run_until_suspend()

    io_events = [event for event in machine.memory_events() if event.name == "IO_BIND"]
    assert io_events
    assert all(event.data.get("reserved_upper_arena") is False for event in io_events)


def test_io_bind_application_value_is_out_of_scope_for_current_host_io() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("(IO-BIND (IO-RETURN [1 2]) (LAMBDA (xs) (IO-RETURN xs)))"),
        quantum=100,
        memory_words=512,
        control_words=128,
        memory_diagnostics=True,
    )

    with pytest.raises(IllegalTransition, match="IO-BIND supports only atomic"):
        machine.run(cycle_limit=100_000)

    io_events = [event for event in machine.memory_events() if event.name == "IO_BIND"]
    assert not any(
        event.data.get("reserved_upper_arena") is True for event in io_events
    )


def test_io_bind_rejects_non_whitelisted_direct_values() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=32,
        control_words=8,
        memory_diagnostics=True,
    )
    state = machine.state
    state.memory[0] = Word(MuredOpcode.APP, 8)
    state.memory[1] = Word(MuredOpcode.RBLOCK, 20, True)
    state.memory[8] = Word(MuredOpcode.LAMBDA, "x")
    state.memory[9] = Word(MuredOpcode.VAR, 0, True)
    state.c = -1
    machine._push_control(32)
    state.pc = 1
    state.fsp = 1
    state.env = 32
    state.env_frontier = 32
    state.direction = Direction.B
    state.prim = "IO-BIND"
    state.fire = 2

    with pytest.raises(IllegalTransition, match="IO-BIND supports only atomic"):
        machine._fire_io_sequence("IO-BIND")


def test_restore_skips_when_result_lambda_body_references_child_environment() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.APP, 10, False)
    state.memory[3] = Word(MuredOpcode.LAMBDA, "x", True)
    state.memory[4] = Word(MuredOpcode.EP, 29, True)
    state.memory[10] = Word(MuredOpcode.INT, 1, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.fsp = 10
    state.env = 28
    state.env_frontier = 28
    frame = _SubgraphFrame(env=64, env_frontier=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.env_frontier == 28
    assert state.env == 64
    assert state.memory[29] == Word(MuredOpcode.INT, 41, False)


def test_restore_skips_when_letrec_result_body_references_child_environment() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.RBLOCK, 20, True)
    state.memory[3] = Word(MuredOpcode.RUP, 1, False)
    state.memory[4] = Word(MuredOpcode.EP, 29, True)
    state.memory[20] = Word(MuredOpcode.SYM, "x", False)
    state.memory[21] = Word(MuredOpcode.INT, 1, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.fsp = 21
    state.env = 28
    state.env_frontier = 28
    frame = _SubgraphFrame(env=64, env_frontier=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.env_frontier == 28
    assert state.env == 64
    assert state.memory[29] == Word(MuredOpcode.INT, 41, False)


@pytest.mark.parametrize(
    "block_data, fsp",
    [
        (-2, 4),
        (10, 4),
    ],
)
def test_restore_skips_malformed_letrec_binding_body_addresses(
    block_data: int,
    fsp: int,
) -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.RBLOCK, block_data, True)
    state.memory[3] = Word(MuredOpcode.RUP, 1, False)
    state.memory[4] = Word(MuredOpcode.INT, 1, True)
    state.fsp = fsp
    state.env = 28
    state.env_frontier = 28
    frame = _SubgraphFrame(env=64, env_frontier=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.env_frontier == 28


def test_restore_skips_malformed_letrec_missing_result_body() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[0] = Word(MuredOpcode.SYM, "x", False)
    state.memory[1] = Word(MuredOpcode.INT, 1, True)
    state.memory[2] = Word(MuredOpcode.RBLOCK, 0, True)
    state.memory[3] = Word(MuredOpcode.RUP, 1, False)
    state.fsp = 3
    state.env = 28
    state.env_frontier = 28
    frame = _SubgraphFrame(env=64, env_frontier=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.env_frontier == 28


def test_malformed_subgraph_frame_ordering_for_primitive_join_is_rejected() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 1, True)],
        quantum=10,
        memory_words=32,
        control_words=4,
    )
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.INT, 2, True)
    state.pc = 4
    state.fsp = 5
    state.env = 32
    state.env_frontier = 32
    state.direction = Direction.B

    with pytest.raises(IllegalTransition, match="saved context"):
        machine.step()

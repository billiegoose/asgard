from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from red2_engine.io_runtime import Red2IoHost, Red2RechargeEvent, run_red2_io_action
from red2_engine.mured import (
    Direction,
    IllegalTransition,
    MuredHostCall,
    MuredMachine,
    MuredOpcode,
    MuredStopReason,
    Word,
    _SavedDefinitionPath,
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
        "(((LAMBDA (x) ((LAMBDA (f) (f 0))   ((LAMBDA (y) (LAMBDA (z) x)) 1))) 42))",
        poison=True,
    )

    assert to_source(machine.result_expr()) == "42"
    assert "ENV_ALLOC" in {event.name for event in machine.memory_events()}


def test_strict_arithmetic_y_countdown_records_graph_rewinds() -> None:
    machine = run_expr(
        "((Y (LAMBDA (self) (LAMBDA (n) (IF (= n 0) 0 (+ 1 (self (1- n))))))) 6)",
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
    state.free_space = 32
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
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.free_space == 28
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
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.free_space == 28
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
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.free_space == 28


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
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    restored = machine._restore_environment_region(frame, result_address=2)

    assert restored is False
    assert state.free_space == 28


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
    state.free_space = 32
    state.direction = Direction.B

    with pytest.raises(IllegalTransition, match="saved context"):
        machine.step()


@pytest.mark.parametrize("words", [1, 3], ids=["binding", "block"])
@pytest.mark.parametrize(
    "adjacent,gap,success",
    [
        (True, 8, True),
        (False, 8, True),
        (True, None, True),  # exact fit: adjacent arenas without overlap
        (False, None, True),
        (False, 2, False),  # marker fits, but the entire binding/block does not
        (True, 1, False),
        (False, 1, False),
    ],
    ids=[
        "adjacent",
        "pnp",
        "adjacent-exact",
        "pnp-exact",
        "marker-only",
        "adjacent-exhausted",
        "pnp-exhausted",
    ],
)
def test_environment_reservation_uses_free_space_atomically(
    words: int,
    adjacent: bool,
    gap: int | None,
    success: bool,
) -> None:
    from copy import deepcopy

    from red2_engine.mured import GraphEnvironmentCollision

    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=1,
        memory_words=32,
        memory_diagnostics=True,
    )
    state = machine.state
    state.free_space = 16
    state.env = 16 if adjacent else 24
    state.memory[state.env] = Word(MuredOpcode.INT, 73, False)
    state.memory[state.env + 1] = Word(MuredOpcode.PNP, 32, False)
    footprint = words + (not adjacent)
    state.fsp = 16 - (footprint + 1 if gap is None else gap)
    machine._validate_state()
    assert machine.lookup(0) == state.env
    payload = [Word(MuredOpcode.INT, n, False) for n in range(words)]
    before = deepcopy(vars(machine))

    def allocate() -> int:
        if words == 1:
            return machine._allocate_environment(payload[0])
        return machine._allocate_environment_block(payload)

    if not success:
        with pytest.raises(GraphEnvironmentCollision):
            allocate()
        # Includes all registers, arena words, control entries, pending host
        # state, events and diagnostic high-water/counter storage.
        assert vars(machine) == before
        return

    address = allocate()
    expected = 16 - footprint
    assert address == state.env == state.free_space == expected
    assert state.memory[address : address + words] == payload
    if not adjacent:
        assert state.memory[15] == Word(MuredOpcode.PNP, 24, False)
    binding = machine.lookup(words)
    assert binding == (16 if adjacent else 24)
    assert state.memory[binding] == Word(MuredOpcode.INT, 73, False)
    if gap is None:
        assert state.free_space == state.fsp + 1
    assert [event.data["opcode"] for event in machine.memory_events()] == (
        ([] if adjacent else ["PNP"]) + (["int"] if words == 1 else ["BLOCK"])
    )


def test_subgraph_frame_saves_and_restores_independent_free_space() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=1,
        memory_words=40,
        memory_diagnostics=True,
    )
    state = machine.state
    state.free_space = 24
    state.env = 32
    state.memory[32] = Word(MuredOpcode.INT, 73, False)
    state.memory[33] = Word(MuredOpcode.PNP, 40, False)
    machine._enter_subgraph(32, 0, 0)
    frame = state.control_stack[state.c]
    assert isinstance(frame, _SubgraphFrame)
    assert type(frame.free_space) is int
    assert frame.env == frame.free_space == state.free_space == 23
    assert state.memory[23] == Word(MuredOpcode.PNP, 32, False)
    state.env = 40
    assert frame.free_space == state.free_space == 23
    machine._allocate_environment(Word(MuredOpcode.INT, 9, False))
    assert state.free_space == 21
    assert machine._pop_subgraph_frame(False) == frame
    assert machine._restore_environment_region(frame, result_address=None)
    assert type(state.free_space) is int
    assert state.free_space == 23
    assert state.env == 23
    assert machine.lookup(0) == 32
    state.env = 40
    assert state.free_space == 23
    event = next(e for e in machine.memory_events() if e.name == "SUBGRAPH_ENTER")
    assert event.data["parent_env"] == 32
    assert event.data["env"] == 23
    assert event.data["free_space"] == 23


def test_publish_child_atomic_ep_before_exact_region_return() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.fsp = 2
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    published = machine._publish_child_result(frame, 2)

    assert published == 2
    assert state.memory[2] == Word(MuredOpcode.INT, 41, True)
    assert machine._restore_environment_region(frame, published)
    assert state.free_space == 32
    assert state.env == 64
    assert all(state.memory[address] is None for address in range(28, 32))


def test_publish_child_closure_materializes_captured_binding_before_reuse() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    # Child result is an EP to a closure in the dying region.  Its code is
    # lambda z. x, with x captured as 42 in that same region.
    state.memory[2] = Word(MuredOpcode.EP, 28, True)
    state.memory[20] = Word(MuredOpcode.LAMBDA, "z", False)
    state.memory[21] = Word(MuredOpcode.VAR, 1, True)
    state.memory[28] = Word(MuredOpcode.CLOSURE, 30, False)
    state.memory[29] = Word(None, 20, False)
    state.memory[30] = Word(MuredOpcode.INT, 42, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.fsp = 21
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    published = machine._publish_child_result(frame, 2)
    before_reuse, _ = machine._decompile(published, (), frozenset())
    assert to_source(before_reuse) == "(LAMBDA (z) 42)"

    assert machine._restore_environment_region(frame, published)
    for address in range(28, 32):
        state.memory[address] = Word(MuredOpcode.INT, 9000 + address, False)
    after_reuse, _ = machine._decompile(published, (), frozenset())
    assert to_source(after_reuse) == "(LAMBDA (z) 42)"


def test_publish_child_shared_app_rewrites_shared_ep_once_before_reuse() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.APP, 10, False)
    state.memory[3] = Word(MuredOpcode.APP, 10, False)
    state.memory[4] = Word(MuredOpcode.SYM, "F", True)
    state.memory[10] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.fsp = 10
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    before, _ = machine._decompile(2, (), frozenset())
    published = machine._publish_child_result(frame, 2)

    assert to_source(before) == "(F 41 41)"
    assert published == 2
    assert state.memory[2] == Word(MuredOpcode.APP, 10, False)
    assert state.memory[3] == Word(MuredOpcode.APP, 10, False)
    assert state.memory[10] == Word(MuredOpcode.INT, 41, True)
    assert not machine._graph_references_environment_interval(published, 28, 32)
    assert machine._restore_environment_region(frame, published)
    for address in range(28, 32):
        state.memory[address] = Word(MuredOpcode.INT, 9000 + address, False)
    after, _ = machine._decompile(published, (), frozenset())
    assert to_source(after) == "(F 41 41)"


def test_publish_child_struct_lazy_ep_field_before_reuse() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STRUCT, "PAIR", False)
    state.memory[3] = Word(MuredOpcode.EP, 29, False)
    state.memory[4] = Word(MuredOpcode.VAR, 0, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.fsp = 4
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    before, _ = machine._decompile(2, (), frozenset())
    published = machine._publish_child_result(frame, 2)

    assert to_source(before) == "{PAIR 41}"
    assert published == 2
    assert state.memory[3] == Word(MuredOpcode.INT, 41, False)
    assert not machine._graph_references_environment_interval(published, 28, 32)
    assert machine._restore_environment_region(frame, published)
    for address in range(28, 32):
        state.memory[address] = Word(MuredOpcode.INT, 9000 + address, False)
    after, _ = machine._decompile(published, (), frozenset())
    assert to_source(after) == "{PAIR 41}"


def test_publish_child_letrec_residual_body_ep_before_reuse() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.RBLOCK, 10, False)
    state.memory[3] = Word(MuredOpcode.RUP, 1, False)
    state.memory[4] = Word(MuredOpcode.EP, 29, True)
    state.memory[10] = Word(MuredOpcode.SYM, "x", False)
    state.memory[11] = Word(MuredOpcode.INT, 1, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.fsp = 11
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=64, free_space=32, prim=None, fire=0)

    before, _ = machine._decompile(2, (), frozenset())
    published = machine._publish_child_result(frame, 2)

    assert to_source(before) == "(LETREC ((x 1)) 41)"
    assert published == 2
    assert state.memory[4] == Word(MuredOpcode.INT, 41, True)
    assert not machine._graph_references_environment_interval(published, 28, 32)
    assert machine._restore_environment_region(frame, published)
    for address in range(28, 32):
        state.memory[address] = Word(MuredOpcode.INT, 9000 + address, False)
    after, _ = machine._decompile(published, (), frozenset())
    assert to_source(after) == "(LETREC ((x 1)) 41)"


def test_typed_join_publishes_before_exact_return_without_scan_helper() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
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
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim=None,
        fire=0,
    )
    state.c = 0

    def forbidden_scan(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("typed JOIN must not call scan-and-skip restore")

    machine._restore_environment_region = forbidden_scan  # type: ignore[method-assign]

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP, 5, False)
    assert state.memory[5] == Word(MuredOpcode.INT, 41, True)
    assert state.free_space == 32
    assert state.env == 32
    assert state.pc == 2
    assert state.c == -1
    assert all(state.memory[address] is None for address in range(28, 32))
    event = next(e for e in machine.memory_events() if e.name == "JOIN_RETURN")
    assert event.data["restored_frontier"] is True


def test_typed_primitive_join_publishes_then_restores_saved_countdown() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False, 1)
    state.memory[5] = Word(MuredOpcode.EP, 29, True)
    state.memory[9] = Word(MuredOpcode.INT, 7, True)
    state.memory[29] = Word(MuredOpcode.INT, 2, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(
        env=32,
        free_space=32,
        prim="+",
        fire=2,
    )
    state.c = 0

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.INT, 2, False)
    assert state.fsp == 3
    assert state.free_space == 32
    assert state.env == 32
    assert state.prim == "+"
    assert state.fire == 1
    assert state.pc == 2
    assert state.c == -1
    assert all(state.memory[address] is None for address in range(28, 32))


def test_typed_join_rejects_saved_environment_inside_reclaimed_region() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=8,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    state.memory[4] = Word(MuredOpcode.JOIN, 3, False)
    state.memory[5] = Word(MuredOpcode.INT, 41, True)
    state.memory[30] = Word(MuredOpcode.INT, 73, False)
    state.pc = 4
    state.fsp = 5
    state.env = 28
    state.free_space = 28
    state.direction = Direction.B
    state.control_stack[0] = _SubgraphFrame(
        env=30,
        free_space=32,
        prim=None,
        fire=0,
    )
    state.c = 0
    before = list(state.memory[28:32])

    with pytest.raises(IllegalTransition, match="saved environment"):
        machine.step()

    assert state.free_space == 28
    assert state.memory[28:32] == before


def _task3_audit_fixture() -> tuple[MuredMachine, _SubgraphFrame]:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=10,
        memory_words=64,
        control_words=12,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.INT, 1, True)
    state.memory[3] = Word(MuredOpcode.INT, 2, True)
    state.fsp = 20
    state.env = 28
    state.free_space = 28
    return machine, _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)


def test_diagnostic_root_audit_rejects_published_result_dangling_ep() -> None:
    machine, frame = _task3_audit_fixture()
    machine.state.memory[2] = Word(MuredOpcode.EP, 29, True)
    machine.state.memory[29] = Word(MuredOpcode.INT, 41, False)

    with pytest.raises(IllegalTransition, match="reclaimed environment address 29"):
        machine._audit_typed_subgraph_return_roots(frame, 2, 3)


def test_diagnostic_root_audit_rejects_transitive_live_parent_graph_reference() -> None:
    machine, frame = _task3_audit_fixture()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 10, False)
    state.memory[4] = Word(MuredOpcode.SYM, "F", True)
    state.memory[10] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)

    with pytest.raises(IllegalTransition, match="reclaimed environment address 29"):
        machine._audit_typed_subgraph_return_roots(frame, 2, 3)


@pytest.mark.parametrize(
    "entry",
    [
        40,
        _SavedDefinitionPath(40),
        _SubgraphFrame(env=40, free_space=40, prim=None, fire=0),
    ],
    ids=["saved-app-path", "saved-definition-path", "outer-subgraph-frame"],
)
def test_diagnostic_root_audit_rejects_saved_environment_roots(entry: object) -> None:
    machine, frame = _task3_audit_fixture()
    state = machine.state
    state.memory[40] = Word(MuredOpcode.EP, 29, False)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    state.control_stack[0] = entry  # type: ignore[assignment]
    state.c = 0

    with pytest.raises(IllegalTransition, match="reclaimed environment address 29"):
        machine._audit_typed_subgraph_return_roots(frame, 2, 3)


@pytest.mark.parametrize("owner", ["closure", "rec"])
def test_diagnostic_root_audit_follows_older_untagged_environment_payloads(
    owner: str,
) -> None:
    machine, frame = _task3_audit_fixture()
    state = machine.state
    state.control_stack[0] = 40
    state.c = 0
    state.memory[12] = Word(MuredOpcode.EP, 29, True)
    state.memory[13] = Word(MuredOpcode.INT, 7, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    if owner == "closure":
        state.memory[40] = Word(MuredOpcode.CLOSURE, 64, False)
        state.memory[41] = Word(None, 12, False)
    else:
        state.memory[40] = Word(MuredOpcode.REC, 13, False)
        state.memory[41] = Word(None, 64, False)
        state.memory[42] = Word(None, 12, False)

    with pytest.raises(IllegalTransition, match="reclaimed environment address 29"):
        machine._audit_typed_subgraph_return_roots(frame, 2, 3)


def test_diagnostic_root_audit_rejects_static_definition_reference() -> None:
    machine, frame = _task3_audit_fixture()
    state = machine.state
    machine.working_memory_limit = 56
    state.memory[56] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)

    with pytest.raises(IllegalTransition, match="reclaimed environment address 29"):
        machine._audit_typed_subgraph_return_roots(frame, 2, 3)


def test_diagnostic_root_audit_rejects_pending_host_argument_reference() -> None:
    machine, frame = _task3_audit_fixture()
    state = machine.state
    state.memory[12] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)
    machine.pending_host_call = MuredHostCall("UART-TX", 12)

    with pytest.raises(IllegalTransition, match="reclaimed environment address 29"):
        machine._audit_typed_subgraph_return_roots(frame, 2, 3)


def test_diagnostic_root_audit_ignores_unreachable_arena_reference() -> None:
    machine, frame = _task3_audit_fixture()
    state = machine.state
    state.memory[18] = Word(MuredOpcode.EP, 29, True)
    state.memory[29] = Word(MuredOpcode.INT, 41, False)

    machine._audit_typed_subgraph_return_roots(frame, 2, 3)
    assert machine._restore_typed_subgraph_region(frame)
    assert state.free_space == 32
    assert all(state.memory[address] is None for address in range(28, 32))


def test_subgraph_entry_normalizes_parent_path_to_saved_free_space() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=4,
        memory_words=40,
        control_words=8,
        memory_diagnostics=True,
    )
    state = machine.state
    state.free_space = 24
    state.env = 32
    state.memory[32] = Word(MuredOpcode.INT, 73, False)
    state.memory[33] = Word(MuredOpcode.PNP, 40, False)

    machine._enter_subgraph(32, 0, 0)

    frame = state.control_stack[state.c]
    assert isinstance(frame, _SubgraphFrame)
    assert frame.env == frame.free_space == 23
    assert state.env == state.free_space == 23
    assert state.memory[23] == Word(MuredOpcode.PNP, 32, False)
    assert machine.lookup(0) == 32
    event = next(e for e in machine.memory_events() if e.name == "SUBGRAPH_ENTER")
    assert event.data["parent_env"] == 32
    assert event.data["env"] == 23
    assert event.data["free_space"] == 23


def test_publish_child_recursive_residual_before_reuse() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=0,
        memory_words=64,
        control_words=8,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    # The result is a reference to the selected binding of a one-binding
    # recursive environment. Publication must turn that environment-owned REC
    # into a graph-owned LETREC residual before the REC triple is reclaimed.
    state.memory[2] = Word(MuredOpcode.EP, 28, True)
    state.memory[10] = Word(MuredOpcode.RBLOCK, 20, False)
    state.memory[11] = Word(MuredOpcode.RUP, 1, False)
    state.memory[12] = Word(MuredOpcode.VAR, 0, True)
    state.memory[20] = Word(MuredOpcode.SYM, "x", False)
    state.memory[21] = Word(MuredOpcode.INT, 7, True)
    state.memory[28] = Word(MuredOpcode.REC, 21, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 10, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.fsp = 21
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)

    published = machine._publish_child_result(frame, 2)
    before_reuse, _ = machine._decompile(published, (), frozenset())

    assert published != 2
    assert to_source(before_reuse) == "(LETREC ((x 7)) x)"
    assert not machine._graph_references_environment_interval(published, 28, 32)
    machine._audit_typed_subgraph_return_roots(frame, published, published)
    assert machine._restore_typed_subgraph_region(frame)
    for address in range(28, 32):
        state.memory[address] = Word(MuredOpcode.INT, 9000 + address, False)
    after_reuse, _ = machine._decompile(published, (), frozenset())
    assert to_source(after_reuse) == "(LETREC ((x 7)) x)"


def test_publish_child_self_recursive_binding_residualizes_rec_as_letrec_var() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=0,
        memory_words=64,
        control_words=8,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    state.memory[2] = Word(MuredOpcode.EP, 28, True)
    state.memory[10] = Word(MuredOpcode.RBLOCK, 20, False)
    state.memory[11] = Word(MuredOpcode.RUP, 1, False)
    state.memory[12] = Word(MuredOpcode.VAR, 0, True)
    state.memory[20] = Word(MuredOpcode.SYM, "x", False)
    # A previously forced recursive binding can point back to its own REC.
    # Publication must express that reference in LETREC lexical scope.
    state.memory[21] = Word(MuredOpcode.EP, 28, True)
    state.memory[28] = Word(MuredOpcode.REC, 21, False)
    state.memory[29] = Word(None, 28, False)
    state.memory[30] = Word(None, 10, False)
    state.memory[31] = Word(MuredOpcode.PNP, 64, False)
    state.fsp = 21
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)

    published = machine._publish_child_result(frame, 2)
    before_reuse, _ = machine._decompile(published, (), frozenset())

    assert to_source(before_reuse) == "(LETREC ((x x)) x)"
    # C RECONSTRUCT copies RBLOCK descriptors; it does not clone binding bodies.
    assert state.memory[published] == Word(MuredOpcode.RBLOCK, 20, False)
    assert state.memory[21] == Word(MuredOpcode.VAR, 0, True)
    assert not machine._graph_references_environment_interval(published, 28, 32)
    machine._audit_typed_subgraph_return_roots(frame, published, published)
    assert machine._restore_typed_subgraph_region(frame)
    for address in range(28, 32):
        state.memory[address] = Word(MuredOpcode.INT, 9000 + address, False)
    after_reuse, _ = machine._decompile(published, (), frozenset())
    assert to_source(after_reuse) == "(LETREC ((x x)) x)"


def test_publish_child_shared_recursive_aliases_keep_one_residual_root() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=0,
        memory_words=64,
        control_words=8,
        memory_diagnostics=True,
        poison_reclaimed_environment=True,
    )
    state = machine.state
    # Two live application descriptors share one environment-owned recursive
    # value. Publication must materialize the LETREC residual once and preserve
    # that alias rather than cloning the recursive graph per reference.
    state.memory[2] = Word(MuredOpcode.APP, 8, False)
    state.memory[3] = Word(MuredOpcode.APP, 8, False)
    state.memory[4] = Word(MuredOpcode.SYM, "F", True)
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
    state.fsp = 21
    state.env = 28
    state.free_space = 28
    frame = _SubgraphFrame(env=32, free_space=32, prim=None, fire=0)

    published = machine._publish_child_result(frame, 2)

    assert published == 2
    first = state.memory[2]
    second = state.memory[3]
    assert first is not None and first.opcode is MuredOpcode.APP
    assert second is not None and second.opcode is MuredOpcode.APP
    assert first.data == second.data
    assert type(first.data) is int
    residual = first.data
    assert state.memory[residual] == Word(MuredOpcode.RBLOCK, 20, False)
    assert state.memory[residual + 1] == Word(MuredOpcode.RUP, 1, False)
    assert state.memory[residual + 2] == Word(MuredOpcode.VAR, 0, True)
    assert state.fsp == residual + 2
    before_reuse, _ = machine._decompile(published, (), frozenset())
    assert to_source(before_reuse) == (
        "(F (LETREC ((x x)) x) (LETREC ((x x)) x))"
    )
    assert not machine._graph_references_environment_interval(published, 28, 32)
    machine._audit_typed_subgraph_return_roots(frame, published, published)
    assert machine._restore_typed_subgraph_region(frame)
    for address in range(28, 32):
        state.memory[address] = Word(MuredOpcode.INT, 9000 + address, False)
    after_reuse, _ = machine._decompile(published, (), frozenset())
    assert to_source(after_reuse) == to_source(before_reuse)
    assert state.memory[2] == Word(MuredOpcode.APP, residual, False)
    assert state.memory[3] == Word(MuredOpcode.APP, residual, False)

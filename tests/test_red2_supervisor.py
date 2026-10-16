"""Repeated complete quanta must reclaim space without replaying effects."""

from pathlib import Path

import pytest

from abstract_red2_machine.loader import load_faithful_machine
from abstract_red2_machine.machine import AbstractRED2Machine
from abstract_red2_machine.supervisor import AbstractProcessor
from concrete_red2_machine.cli import _prepare_program
from concrete_red2_machine.oracle import load_compiled_program
from concrete_red2_machine.supervisor import ConcreteProcessor
from red2.supervisor import SupervisorLimitError, SupervisorStats, supervise
from thor.pretty import to_source

COUNTDOWN = "((Y (LAMBDA (self n) (if (= n 0) 0 (self (- n 1))))) 100)"


def processor(model: str, source: str, memory_words: int = 256):
    action, definitions = _prepare_program(source)
    if model == "abstract":
        machine = load_faithful_machine(
            action,
            definitions=definitions,
            quantum=20,
            memory_words=memory_words,
            control_words=256,
        )
        return AbstractProcessor(machine)
    loaded = load_compiled_program(
        action,
        definitions=definitions,
        quantum=20,
        memory_words=memory_words,
        control_words=256,
    )
    return ConcreteProcessor(loaded.concrete, loaded.codec)


@pytest.mark.parametrize("model", ["abstract", "concrete"])
def test_countdown_restarts_in_same_small_machine(model: str, monkeypatch) -> None:
    adapter = processor(model, COUNTDOWN)
    machine = adapter.machine
    state = machine.state if model == "abstract" else machine
    arena = state.memory
    control = state.control_stack
    identities = (id(machine), id(arena), id(control))
    limit = machine.working_memory_limit
    definitions = tuple(arena[limit:])
    restart = adapter.restart
    restarted = 0

    def checked_restart(quantum):
        nonlocal restarted
        assert state.halted and state.q == 0
        count = restart(quantum)
        assert (id(machine), id(state.memory), id(state.control_stack)) == identities
        assert state.env == state.free_space == limit
        assert state.c == -1 and state.phi == 0 and state.argcnt == 0
        assert not state.halted and state.q == quantum
        assert tuple(state.memory[limit:]) == definitions
        restarted += 1
        return count

    monkeypatch.setattr(adapter, "restart", checked_restart)
    counters = SupervisorStats()
    assert to_source(supervise(adapter, stats=counters)) == "0"
    assert counters.quantum_restarts == restarted >= 25
    assert counters.max_residual_words < limit


@pytest.mark.parametrize("model", ["abstract", "concrete"])
@pytest.mark.parametrize("quantum", [1, 5, 10, 20])
def test_arbitrary_boundaries_keep_if_captured_branches(
    model: str, quantum: int
) -> None:
    source = COUNTDOWN.replace("100)", "3)")
    assert to_source(supervise(processor(model, source, 1024), quantum=quantum)) == "0"


@pytest.mark.parametrize("model", ["abstract", "concrete"])
@pytest.mark.parametrize("quantum", [1, 5, 20])
def test_defined_symbol_metadata_stays_on_argument(model: str, quantum: int) -> None:
    source = """
    limit == 1000
    (IF (>= 1000 limit)
        ((LAMBDA (x) x) 65)
        ((LAMBDA (x) x) 66))
    """
    assert to_source(supervise(processor(model, source), quantum=quantum)) == "65"


class Host:
    def __init__(self, clock_step=1000):
        self.reads = [65, 66]
        self.writes = []
        self.clock = 0
        self.clock_step = clock_step

    def uart_rx(self):
        return self.reads.pop(0)

    def uart_tx(self, data):
        self.writes.append(data)

    def clock_ms(self):
        self.clock += self.clock_step
        return self.clock


@pytest.mark.parametrize("model", ["abstract", "concrete"])
@pytest.mark.parametrize("quantum", [1, 2, 5, 20])
def test_effects_are_not_replayed_or_recharged(model: str, quantum: int) -> None:
    source = """
    (IO-BIND (UART-RX) (LAMBDA (a)
      (IO-THEN (UART-TX a)
        (IO-BIND (UART-RX) (LAMBDA (b)
          (IO-THEN (UART-TX b) (IO-RETURN 42)))))))
    """
    host = Host()
    counters = SupervisorStats()
    result = supervise(
        processor(model, source), host=host, quantum=quantum, stats=counters
    )
    assert to_source(result) == "42"
    assert host.writes == [b"A", b"B"]
    assert host.reads == []
    assert counters.host_calls == 4
    if quantum == 1:
        assert counters.quantum_restarts >= 8


class EnoughDotsError(Exception):
    pass


@pytest.mark.parametrize(
    ("model", "dots", "clock_step", "period", "quantum"),
    [
        ("abstract", 500, 1000, 1000, 20),
        ("concrete", 20, 1000, 1000, 20),
        ("abstract", 100, 1, 5, 5),
        ("concrete", 20, 1, 5, 5),
    ],
)
def test_clock_dots_runs_across_many_quanta(
    model: str,
    dots: int,
    clock_step: int,
    period: int,
    quantum: int,
    monkeypatch,
) -> None:
    source = (
        Path(__file__).resolve().parents[1] / "examples/clock-dots.thor"
    ).read_text()
    source = source.replace("SECOND-MS == 1000", f"SECOND-MS == {period}")
    host = Host(clock_step)
    adapter = processor(model, source)
    counters = SupervisorStats()
    last_tx_clock = 0

    def output(data):
        nonlocal last_tx_clock
        assert data == b"."
        assert host.clock - last_tx_clock >= period
        last_tx_clock = host.clock
        host.writes.append(data)
        if len(host.writes) == dots:
            raise EnoughDotsError

    host.uart_tx = output
    if model == "abstract":

        def forbidden(*args, **kwargs):
            raise AssertionError("host boundary must not refill the quantum")

        # start() is the only initial setting; no later host-boundary refresh.
        original_start = adapter.start

        def start(quantum):
            original_start(quantum)
            monkeypatch.setattr(adapter.machine, "refresh_quantum", forbidden)
            monkeypatch.setattr(adapter.machine, "checkpoint_quantum", forbidden)

        monkeypatch.setattr(adapter, "start", start)
    with pytest.raises(EnoughDotsError):
        supervise(adapter, host=host, stats=counters, quantum=quantum)
    assert len(host.writes) == dots
    assert counters.quantum_restarts >= dots // 2
    assert host.clock >= dots * period


@pytest.mark.parametrize("model", ["abstract", "concrete"])
def test_explicit_quantum_limit_stops_at_reconstructed_boundary(model: str) -> None:
    adapter = processor(model, COUNTDOWN)
    with pytest.raises(SupervisorLimitError, match="exhausted 2 quanta"):
        supervise(adapter, max_quanta=2)
    state = adapter.machine.state if model == "abstract" else adapter.machine
    assert state.halted and state.q == 0


def test_concrete_restart_does_not_use_abstract_evaluation(monkeypatch) -> None:
    adapter = processor("concrete", COUNTDOWN)

    def forbidden(*args, **kwargs):
        raise AssertionError("Concrete must perform its own reconstruction and restart")

    for name in ("step", "run", "run_until_suspend", "recharge_quantum"):
        monkeypatch.setattr(AbstractRED2Machine, name, forbidden)
    assert to_source(supervise(adapter)) == "0"


@pytest.mark.parametrize("model", ["abstract", "concrete"])
def test_cli_supervision_defaults_to_small_quanta(model: str, capsys) -> None:
    from abstract_red2_machine.cli import main as abstract_main
    from concrete_red2_machine.cli import main as concrete_main

    main = abstract_main if model == "abstract" else concrete_main
    assert main(["--supervise", "--memory-words", "256", "--expr", COUNTDOWN]) == 0
    assert capsys.readouterr().out == "0\n"


@pytest.mark.parametrize("model", ["abstract", "concrete"])
def test_cli_uart_keeps_stdout_for_device_bytes(model: str, capsys) -> None:
    from abstract_red2_machine.cli import main as abstract_main
    from concrete_red2_machine.cli import main as concrete_main

    main = abstract_main if model == "abstract" else concrete_main
    assert (
        main(
            [
                "--supervise",
                "--quantum",
                "1",
                "--memory-words",
                "256",
                "--expr",
                "(IO-THEN (UART-TX 65) (UART-TX 66))",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == "AB"

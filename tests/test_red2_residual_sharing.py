"""Residual sharing must preserve values, lexical scope, and effect multiplicity."""

from pathlib import Path

import pytest

from abstract_red2_machine.loader import load_faithful_machine
from abstract_red2_machine.machine import AbstractRED2Machine
from abstract_red2_machine.supervisor import AbstractProcessor
from concrete_red2_machine import abi
from concrete_red2_machine.cli import _prepare_program
from concrete_red2_machine.oracle import load_concrete_machine, run_lockstep
from concrete_red2_machine.supervisor import ConcreteProcessor
from red2.representation import MuredOpcode, Word
from red2.supervisor import SupervisorStats, supervise
from thor.pretty import to_source

ROOT = Path(__file__).resolve().parents[1]


def machine(
    source: str, quantum: int = 20, *, poison: bool = True
) -> AbstractRED2Machine:
    action, definitions = _prepare_program(source)
    return load_faithful_machine(
        action,
        definitions=definitions,
        quantum=quantum,
        memory_words=512,
        control_words=256,
        poison_reclaimed_environment=poison,
    )


def processor(
    model: str, source: str, quantum: int = 20
) -> AbstractProcessor | ConcreteProcessor:
    abstract = machine(source, quantum)
    if model == "abstract":
        return AbstractProcessor(abstract)
    codec, _, concrete = load_concrete_machine(abstract)
    return ConcreteProcessor(concrete, codec)


@pytest.mark.parametrize("model", ["abstract", "concrete"])
@pytest.mark.parametrize("quantum", [5, 20, 50, 100, 200])
def test_original_fibonacci_keeps_deferred_arithmetic_shared(
    model: str, quantum: int
) -> None:
    source = (
        (ROOT / "examples/fibonacci.thor")
        .read_text()
        .replace("fib-six == (fib 6)", "fib-six == (fib 30)")
    )
    stats = SupervisorStats()
    result = supervise(
        processor(model, source, quantum),
        quantum=quantum,
        stats=stats,
        max_quanta=200,
    )
    assert to_source(result) == "832040"
    assert stats.quantum_restarts > 0


@pytest.mark.parametrize("quantum", [5, 20])
def test_sharing_matches_at_every_committed_transition_and_restart(
    quantum: int,
) -> None:
    source = (
        (ROOT / "examples/fibonacci.thor")
        .read_text()
        .replace("fib-six == (fib 6)", "fib-six == (fib 10)")
    )
    abstract = machine(source, quantum, poison=False)
    codec, _, concrete = load_concrete_machine(abstract)
    for _ in range(100):
        result = run_lockstep(
            abstract, codec=codec, concrete=concrete, max_transitions=20_000
        )
        assert result.matches, (
            result.divergence.format() if result.divergence is not None else result
        )
        if result.status == abi.STATUS_COMPLETE:
            assert to_source(abstract.result_expr()) == "55"
            return
        assert result.status == abi.STATUS_QUANTUM_EXHAUSTED
        abstract.recharge_quantum(quantum)
        assert concrete.recharge_quantum(quantum) == abi.STATUS_RUNNING
        assert concrete.checkpoint() == codec.encode_state(abstract.state)
    pytest.fail("Fibonacci did not finish within 100 quanta")


@pytest.mark.parametrize("model", ["abstract", "concrete"])
@pytest.mark.parametrize("quantum", [1, 5, 20])
def test_open_arithmetic_retains_each_callers_bindings(
    model: str, quantum: int
) -> None:
    source = """
    ((LAMBDA (f) (+ (f 3) (f 5)))
      (LAMBDA (x) (+ x x)))
    """
    result = supervise(
        processor(model, source, quantum), quantum=quantum, max_quanta=100
    )
    assert to_source(result) == "16"


@pytest.mark.parametrize("model", ["abstract", "concrete"])
@pytest.mark.parametrize("quantum", [1, 5, 20])
def test_sharing_does_not_force_an_unused_effect(model: str, quantum: int) -> None:
    source = "(IF TRUE (+ (+ 1 2) (+ 3 4)) (UART-TX 65))"
    # No host: entering the unselected UART branch would fail immediately.
    result = supervise(
        processor(model, source, quantum), quantum=quantum, max_quanta=100
    )
    assert to_source(result) == "10"


class Host:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def uart_tx(self, data: bytes) -> None:
        self.writes.append(data)

    def uart_rx(self) -> int | None:
        raise AssertionError("unexpected UART read")

    def clock_ms(self) -> int:
        raise AssertionError("unexpected clock read")


@pytest.mark.parametrize("model", ["abstract", "concrete"])
@pytest.mark.parametrize("quantum", [1, 5, 20])
def test_two_references_to_same_uart_graph_still_write_twice(
    model: str, quantum: int
) -> None:
    abstract = machine(
        "(IO-THEN (UART-TX 65) (IO-THEN (UART-TX 65) (IO-RETURN 42)))",
        quantum,
    )
    memory = abstract.state.memory
    roots = [
        address - 1
        for address, word in enumerate(memory)
        if word is not None
        and word.opcode is MuredOpcode.PRIM_1
        and word.data == "UART-TX"
    ]
    assert len(roots) == 2
    changed = 0
    for address, word in enumerate(memory):
        if (
            word is not None
            and word.opcode is MuredOpcode.APP
            and word.data == roots[1]
        ):
            memory[address] = Word(word.opcode, roots[0], word.head, word.definition)
            changed += 1
    assert changed == 1
    adapter: AbstractProcessor | ConcreteProcessor
    if model == "abstract":
        adapter = AbstractProcessor(abstract)
    else:
        codec, _, concrete = load_concrete_machine(abstract)
        adapter = ConcreteProcessor(concrete, codec)
    host = Host()
    result = supervise(adapter, host=host, quantum=quantum, max_quanta=100)
    assert to_source(result) == "42"
    assert host.writes == [b"A", b"A"]

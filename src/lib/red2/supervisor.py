"""Scheduling above RED2: finish each quantum before recycling its workspace."""

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Protocol

from thor.ast import Expr

DEFAULT_SUPERVISOR_QUANTUM = 20


class SupervisorError(RuntimeError):
    """The supervised processor cannot safely continue."""


class SupervisorLimitError(SupervisorError):
    """An explicit execution limit was reached without completing the program."""


class QuantumStop(StrEnum):
    COMPLETE = auto()
    EXHAUSTED = auto()
    HOST_CALL = auto()


class SupervisorHost(Protocol):
    def uart_rx(self) -> int | None: ...

    def uart_tx(self, data: bytes) -> None: ...

    def clock_ms(self) -> int: ...


class SupervisedProcessor(Protocol):
    def start(self, quantum: int) -> None: ...

    def run(self) -> QuantumStop: ...

    def resume_host(self, host: SupervisorHost) -> None: ...

    def restart(self, quantum: int) -> int: ...

    def result(self) -> Expr: ...


@dataclass(slots=True)
class SupervisorStats:
    completed_quanta: int = 0
    quantum_restarts: int = 0
    host_calls: int = 0
    max_residual_words: int = 0


def supervise(
    processor: SupervisedProcessor,
    *,
    quantum: int = DEFAULT_SUPERVISOR_QUANTUM,
    host: SupervisorHost | None = None,
    stats: SupervisorStats | None = None,
    max_quanta: int | None = None,
) -> Expr:
    """Run a fresh processor, restarting only fully reconstructed residuals.

    Host suspensions consume the current budget; they never refresh it. Restart
    must copy/relocate the residual graph and reset temporary machine state, not
    merely change q. An exact-budget final value takes one extra pass to establish
    completion. Infinite programs can be stopped by their host or explicit limits.
    """
    if type(quantum) is not int or not 0 < quantum < 1 << 32:
        raise ValueError("supervisor quantum must be positive and fit 32 bits")
    if max_quanta is not None and (type(max_quanta) is not int or max_quanta <= 0):
        raise ValueError("max_quanta must be positive")
    counters = stats if stats is not None else SupervisorStats()
    completed = 0
    processor.start(quantum)
    while True:
        stop = processor.run()
        if stop is QuantumStop.HOST_CALL:
            if host is None:
                raise SupervisorError("program requested I/O without a supervisor host")
            processor.resume_host(host)
            counters.host_calls += 1
            continue
        completed += 1
        counters.completed_quanta += 1
        if stop is QuantumStop.COMPLETE:
            return processor.result()
        if stop is not QuantumStop.EXHAUSTED:
            raise SupervisorError(f"unknown processor stop: {stop}")
        if max_quanta is not None and completed >= max_quanta:
            raise SupervisorLimitError(f"program exhausted {max_quanta} quanta")
        words = processor.restart(quantum)
        counters.quantum_restarts += 1
        counters.max_residual_words = max(counters.max_residual_words, words)

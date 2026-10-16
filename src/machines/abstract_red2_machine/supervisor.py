"""Quantum supervisor adapter for the abstract RED2 reference processor."""

from abstract_red2_machine.io_runtime import dispatch_red2_host_call
from abstract_red2_machine.machine import AbstractRED2Machine, MuredStopReason
from red2.supervisor import (
    QuantumStop,
    SupervisorError,
    SupervisorHost,
    SupervisorLimitError,
)
from thor.ast import Expr


class AbstractProcessor:
    def __init__(self, machine: AbstractRED2Machine, *, max_steps: int | None = None):
        self.machine = machine
        self.max_steps = max_steps

    def start(self, quantum: int) -> None:
        state = self.machine.state
        if state.cycles or state.halted or self.machine.pending_host_call is not None:
            raise SupervisorError("supervisor requires a fresh abstract processor")
        self.machine.refresh_quantum(quantum)

    def run(self) -> QuantumStop:
        limit = self.max_steps
        if limit is None:
            limit = self.machine.state.cycles + 2_000_000
        stop = self.machine.run_until_suspend(cycle_limit=limit)
        return {
            MuredStopReason.COMPLETE: QuantumStop.COMPLETE,
            MuredStopReason.QUANTUM_EXHAUSTED: QuantumStop.EXHAUSTED,
            MuredStopReason.HOST_CALL: QuantumStop.HOST_CALL,
        }[stop.reason]

    def resume_host(self, host: SupervisorHost) -> None:
        call = self.machine.pending_host_call
        if call is None:
            raise SupervisorError("abstract processor has no pending host call")
        value = dispatch_red2_host_call(self.machine, call, host)
        self.machine.resume_host_call(value)

    def restart(self, quantum: int) -> int:
        if not self.machine.state.halted or self.machine.state.q != 0:
            raise SupervisorError("restart requires a completed exhausted quantum")
        self.machine.recharge_quantum(quantum)
        if self.max_steps is not None and self.machine.state.cycles >= self.max_steps:
            raise SupervisorLimitError("abstract supervisor step limit reached")
        return self.machine.state.fsp

    def result(self) -> Expr:
        return self.machine.result_expr()

"""Quantum supervisor adapter using the concrete processor's own restart engine."""

from abstract_red2_machine.machine import AbstractRED2Machine
from concrete_red2_machine import abi
from concrete_red2_machine.io_runtime import dispatch_encoded_host_call
from concrete_red2_machine.machine import ConcreteRED2Machine
from concrete_red2_machine.pipelinec_vectors import RED2ABICodec
from red2.supervisor import (
    QuantumStop,
    SupervisorError,
    SupervisorHost,
    SupervisorLimitError,
)
from thor.ast import Expr


class ConcreteProcessor:
    def __init__(
        self,
        machine: ConcreteRED2Machine,
        codec: RED2ABICodec,
        *,
        max_clocks: int = 100_000_000,
    ):
        self.machine = machine
        self.codec = codec
        self.max_clocks = max_clocks

    def _checked(self, status: int) -> int:
        if status == abi.STATUS_FAULT:
            raise SupervisorError(
                f"concrete RED2 fault={self.machine.fault} "
                f"microstate={self.machine.microstate}"
            )
        return status

    def start(self, quantum: int) -> None:
        if self.machine.clocks or self.machine.commits:
            raise SupervisorError("supervisor requires a fresh concrete processor")
        self._checked(self.machine.refresh_quantum(quantum))

    def run(self) -> QuantumStop:
        remaining = self.max_clocks - self.machine.clocks
        if remaining <= 0:
            raise SupervisorLimitError("concrete supervisor clock limit reached")
        status = self._checked(self.machine.run_until_suspend(remaining))
        if status == abi.STATUS_RUNNING:
            raise SupervisorLimitError("concrete supervisor clock limit reached")
        return {
            abi.STATUS_COMPLETE: QuantumStop.COMPLETE,
            abi.STATUS_QUANTUM_EXHAUSTED: QuantumStop.EXHAUSTED,
            abi.STATUS_HOST_CALL: QuantumStop.HOST_CALL,
        }[status]

    def resume_host(self, host: SupervisorHost) -> None:
        value = dispatch_encoded_host_call(
            self.codec,
            self.machine.checkpoint(),
            host,
            working_memory_limit=self.machine.working_memory_limit,
        )
        self._checked(self.machine.resume_host_call(value))

    def restart(self, quantum: int) -> int:
        if not self.machine.halted or self.machine.q != 0:
            raise SupervisorError("restart requires a completed exhausted quantum")
        remaining = self.max_clocks - self.machine.clocks
        if remaining <= 0:
            raise SupervisorLimitError("concrete supervisor clock limit reached")
        self._checked(self.machine.recharge_quantum(quantum, max_clocks=remaining))
        if self.machine.halted:
            raise SupervisorLimitError("concrete restart clock limit reached")
        return self.machine.fsp

    def result(self) -> Expr:
        # Decoding/printing only: evaluation and graph restart stay in Concrete.
        state = self.codec.decode_state(self.machine.checkpoint())
        view = AbstractRED2Machine(
            state,
            working_memory_limit=self.machine.working_memory_limit,
        )
        return view.result_expr()

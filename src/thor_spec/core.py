from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, auto


class MachineStatus(StrEnum):
    """Execution status for the reference machine."""

    RUNNING = auto()
    HALTED = auto()


class FuelExhaustedError(RuntimeError):
    """Raised when a machine cannot reach a halt state within its fuel budget."""


@dataclass(frozen=True, slots=True)
class StepResult[StateT]:
    """Result of one abstract machine transition."""

    state: StateT
    status: MachineStatus = MachineStatus.RUNNING


type StepFunction[StateT] = Callable[[StateT], StepResult[StateT]]


@dataclass(slots=True)
class Machine[StateT]:
    """Small fuel-bounded execution loop for thesis-defined transition rules."""

    state: StateT
    step_once: StepFunction[StateT]
    status: MachineStatus = MachineStatus.RUNNING
    steps: int = 0

    def step(self) -> None:
        if self.status is MachineStatus.HALTED:
            return

        result = self.step_once(self.state)
        self.state = result.state
        self.status = result.status
        self.steps += 1

    def run(self, *, fuel: int) -> StateT:
        if fuel < 0:
            msg = "fuel must be non-negative"
            raise ValueError(msg)

        for _ in range(fuel):
            if self.status is MachineStatus.HALTED:
                return self.state
            self.step()

        if self.status is MachineStatus.HALTED:
            return self.state

        msg = f"machine did not halt within {fuel} step(s)"
        raise FuelExhaustedError(msg)

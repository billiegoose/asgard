from __future__ import annotations

import pytest

from thor_engine.core import FuelExhaustedError, Machine, MachineStatus, StepResult


def test_machine_runs_until_halted() -> None:
    def step_once(state: int) -> StepResult[int]:
        next_state = state + 1
        status = MachineStatus.HALTED if next_state == 3 else MachineStatus.RUNNING
        return StepResult(next_state, status)

    machine = Machine(0, step_once)

    assert machine.run(fuel=5) == 3
    assert machine.steps == 3
    assert machine.status is MachineStatus.HALTED


def test_machine_raises_when_fuel_is_exhausted() -> None:
    def step_once(state: int) -> StepResult[int]:
        return StepResult(state + 1)

    machine = Machine(0, step_once)

    with pytest.raises(FuelExhaustedError, match="within 2 step"):
        machine.run(fuel=2)

    assert machine.state == 2
    assert machine.steps == 2


def test_machine_rejects_negative_fuel() -> None:
    machine = Machine(0, lambda state: StepResult(state, MachineStatus.HALTED))

    with pytest.raises(ValueError, match="non-negative"):
        machine.run(fuel=-1)

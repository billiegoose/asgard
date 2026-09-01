import pytest

from red2_engine.mured import (
    Direction,
    GraphEnvironmentCollision,
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

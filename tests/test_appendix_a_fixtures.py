from pathlib import Path

from thor_engine.golden import run_source


def assert_fixture_parity(path: str, expected: str, quantum: int) -> None:
    source = Path(path).read_text()
    thor = run_source(source, model="thor", quantum=quantum)
    red2 = run_source(source, model="red2", quantum=quantum)
    assert thor == expected
    assert red2 == expected


def test_sine_core_fixture_parity() -> None:
    assert_fixture_parity("tests/fixtures/appendix_a/sine_core.thor", "0", quantum=5000)


def test_game_core_fixture_parity() -> None:
    assert_fixture_parity("tests/fixtures/appendix_a/game_core.thor", "1", quantum=5000)

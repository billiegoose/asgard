from pathlib import Path

from thor_engine.golden import run_source


def fixture_source_without_benchmark() -> str:
    source = Path("tests/fixtures/appendix_a/sine_full.thor").read_text()
    return source.rsplit("sine-benchmark", maxsplit=1)[0]


def test_sine_full_fixture_matches_between_thor_and_red2() -> None:
    source = Path("tests/fixtures/appendix_a/sine_full.thor").read_text()
    thor = run_source(source, model="thor", quantum=20000)
    red2 = run_source(source, model="red2", quantum=20000)
    assert thor == red2
    assert thor in {"0", "0.0"}


def test_sine_full_recursive_taylor_helpers_match_between_models() -> None:
    source = fixture_source_without_benchmark()
    assert run_source(
        f"{source}\n(sine-number-of-terms epsilon pi)",
        model="thor",
        quantum=20000,
    ) == "7"
    assert run_source(
        f"{source}\n(sine-number-of-terms epsilon pi)",
        model="red2",
        quantum=20000,
    ) == "7"
    assert run_source(
        f"{source}\n(horners-rule sine-coefficient 7 0)",
        model="thor",
        quantum=20000,
    ) == "1.0"
    assert run_source(
        f"{source}\n(horners-rule sine-coefficient 7 0)",
        model="red2",
        quantum=20000,
    ) == "1.0"

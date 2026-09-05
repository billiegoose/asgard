import pytest
from pytest import CaptureFixture, MonkeyPatch

from red2_engine.cli import main as red2_main


@pytest.mark.parametrize(
    ("source", "quantum", "expected"),
    [
        ("((LAMBDA (x) x) 42)", 10, "42\n"),
        ("1.5", 10, "1.5\n"),
        ("#\\a", 10, "#\\a\n"),
        ("FOO", 10, "FOO\n"),
        ("(+ 2 3)", 20, "5\n"),
        ("{PAIR 1 2}", 10, "[1 | 2]\n"),
        ("({PAIR 1 2} (LAMBDA (a b) a))", 10, "1\n"),
        ("(LETREC ((x 7)) x)", 1, "7\n"),
        (
            "(LETREC ((x [1 | y]) (y [2 | x])) x)",
            1,
            "[1 | (LETREC ((x [1 | y]) (y [2 | x])) y)]\n",
        ),
    ],
)
def test_red2_faithful_cli_runs_supported_expression_corpus(
    source: str,
    quantum: int,
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    assert red2_main(["--faithful", "--quantum", str(quantum), "--expr", source]) == 0
    captured = capsys.readouterr()
    assert captured.out == expected
    assert captured.err == ""


def test_red2_faithful_cli_runs_top_level_definition(
    capsys: CaptureFixture[str],
) -> None:
    source = "inc == (LAMBDA (x) (+ x 1))\n(inc 41)"

    assert red2_main(["--faithful", "--quantum", "20", "--expr", source]) == 0

    captured = capsys.readouterr()
    assert captured.out == "42\n"
    assert captured.err == ""


def test_red2_faithful_cli_runs_cross_definition_reference(
    capsys: CaptureFixture[str],
) -> None:
    source = "one == 1\ninc == (LAMBDA (x) (+ x one))\n(inc 41)"

    assert red2_main(["--faithful", "--quantum", "20", "--expr", source]) == 0

    captured = capsys.readouterr()
    assert captured.out == "42\n"
    assert captured.err == ""


def test_red2_cli_default_route_remains_compatibility_mode(
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run_source(*args: object, **kwargs: object) -> str:
        calls.append("compat")
        return "compat-result"

    monkeypatch.setattr("red2_engine.cli.run_source", fake_run_source)

    # Patch the IO probe to fail in the same narrow way the normal fallback handles.
    from thor_engine.io_runtime import IoRuntimeError

    def reject_io(*args: object, **kwargs: object) -> int:
        raise IoRuntimeError("not an IO action: test")

    monkeypatch.setattr("red2_engine.cli._run_io_source", reject_io)

    assert red2_main(["--expr", "42"]) == 0
    captured = capsys.readouterr()
    assert calls == ["compat"]
    assert captured.out == "compat-result\n"


def test_red2_faithful_cli_rejects_compatibility_byte_limits(
    capsys: CaptureFixture[str],
) -> None:
    assert (
        red2_main(
            [
                "--faithful",
                "--stack-size-in-bytes",
                "1000",
                "--expr",
                "42",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "byte resource limits are not supported by --faithful" in captured.err

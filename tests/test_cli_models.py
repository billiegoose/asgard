from io import StringIO
from pathlib import Path

from pytest import CaptureFixture, MonkeyPatch

from red2_engine.cli import main as red2_main
from thor_compile.cli import main as compile_main
from thor_engine.cli import main as thor_main


def test_thor_cli_runs_pure_expr(capsys: CaptureFixture[str]) -> None:
    assert thor_main(["--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out == "5\n"


def test_red2_cli_runs_pure_expr(capsys: CaptureFixture[str]) -> None:
    assert red2_main(["--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out == "5\n"


def test_red2_cli_accepts_resource_limits(capsys: CaptureFixture[str]) -> None:
    assert (
        red2_main(
            [
                "--quantum",
                "20",
                "--stack-size-in-bytes",
                "1000000",
                "--heap-size-in-bytes",
                "1000000",
                "--expr",
                "(+ 2 3)",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    assert captured.out == "5\n"
    assert captured.err == ""


def test_thor_cli_rejects_explicit_resource_limits(
    capsys: CaptureFixture[str],
) -> None:
    assert thor_main(["--stack-size-in-bytes", "1", "--expr", "(+ 2 3)"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "resource limits are currently supported for red2 only" in captured.err


def test_red2_cli_reports_stack_overflow(capsys: CaptureFixture[str]) -> None:
    assert (
        red2_main(
            [
                "--stack-size-in-bytes",
                "1",
                "--heap-size-in-bytes",
                "1000000",
                "--expr",
                "((LAMBDA (X) X) 42)",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "RED2 stack overflow" in captured.err


def test_thor_cli_runs_io_quiet_by_default(capsys: CaptureFixture[str]) -> None:
    assert thor_main(["--expr", "(UART-TX 65)"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "A"
    assert captured.err == ""


def test_red2_cli_runs_io_quiet_by_default(
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("B"))

    assert red2_main(["--expr", "(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "B"
    assert captured.err == ""


def test_red2_cli_io_accepts_resource_limits(capsys: CaptureFixture[str]) -> None:
    assert (
        red2_main(
            [
                "--stack-size-in-bytes",
                "1000000",
                "--heap-size-in-bytes",
                "1000000",
                "--expr",
                "(UART-TX (+ 60 5))",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.out == "A"
    assert captured.err == ""


def test_cli_verbose_reports_io_result(capsys: CaptureFixture[str]) -> None:
    assert thor_main(["--verbose", "--expr", "(UART-TX 65)"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "A"
    assert captured.err == "io result: NIL\n"


def test_thor_cli_uses_clock_file(
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    clock = tmp_path / "clock.txt"
    clock.write_text("1700000000123\n")

    assert thor_main(["--clock", str(clock), "--expr", "(CLOCK)"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_red2_cli_uses_clock_file(
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    clock = tmp_path / "clock.txt"
    clock.write_text("1700000000456\n")

    assert red2_main(["--clock", str(clock), "--expr", "(CLOCK)"]) == 0

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_thor_cli_runs_file_as_io_action(
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    source = tmp_path / "hello.thor"
    source.write_text("(UART-TX 65)\n")

    assert thor_main([str(source)]) == 0

    captured = capsys.readouterr()
    assert captured.out == "A"
    assert captured.err == ""


def test_thor_cli_runs_pure_file(
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    source = tmp_path / "add.thor"
    source.write_text("(+ 2 3)\n")

    assert thor_main([str(source), "--quantum", "20"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "5\n"
    assert captured.err == ""


def test_red2_cli_runs_pure_file(
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    source = tmp_path / "add.thor"
    source.write_text("(+ 2 3)\n")

    assert red2_main([str(source), "--quantum", "20"]) == 0

    captured = capsys.readouterr()
    assert captured.out == "5\n"
    assert captured.err == ""


def test_compile_cli_file_bundles_top_level_definitions(
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    source = tmp_path / "inc.thor"
    source.write_text("inc == (lambda (x) (+ x 1))\n(inc 41)\n")
    output = tmp_path / "inc.red2"

    assert compile_main([str(source), "--output", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "wrote RED2 bytecode" in captured.err
    assert output.read_bytes()[4:6] == b"\x02\x00"


def test_compile_cli_rejects_program_without_expression(
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output = tmp_path / "bad.red2"

    assert compile_main(["--expr", "answer == 42", "--output", str(output)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "compile requires a final expression" in captured.err

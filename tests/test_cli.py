from pathlib import Path

from pytest import CaptureFixture

from abstract_red2_machine.cli import main as abs_main
from thor_compile.cli import main as compile_main
from thor_interpreter.cli import main as thor_main


def test_thor_cli_runs_expression(capsys: CaptureFixture[str]) -> None:
    assert thor_main(["--expr", "(+ 2 3)", "--quantum", "20"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "5\n"
    assert captured.err == ""


def test_red2_cli_runs_expression(capsys: CaptureFixture[str]) -> None:
    assert abs_main(["--expr", "(+ 2 3)", "--quantum", "20"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "5\n"
    assert captured.err == ""


def test_compile_cli_writes_red2_bytecode(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    output = tmp_path / "add.red2"
    assert compile_main(["--expr", "(+ 2 3)", "--output", str(output)]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"wrote RED2 bytecode: {output}\n"
    assert output.read_bytes().startswith(b"RED2")

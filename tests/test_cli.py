from pathlib import Path

from pytest import CaptureFixture

from abstract_red2_machine.cli import main as abs_main
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

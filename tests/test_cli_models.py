from __future__ import annotations

from pytest import CaptureFixture

from thor_spec.cli import main


def test_cli_runs_thor_model_expr(capsys: CaptureFixture[str]) -> None:
    assert main(["--model", "thor", "--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out.strip() == "5"


def test_cli_runs_red2_model_expr(capsys: CaptureFixture[str]) -> None:
    assert main(["--model", "red2", "--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out.strip() == "5"

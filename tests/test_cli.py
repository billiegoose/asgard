from __future__ import annotations

from pytest import CaptureFixture

from thor_spec.cli import main


def test_cli_help(capsys: CaptureFixture[str]) -> None:
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "Executable specification tooling" in captured.out

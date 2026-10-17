"""A rejected image or failed flash write must never trigger a board restart."""

import json
import subprocess

import pytest
from scripts.boards.red2_standalone import run


def test_explicit_quantum_overrides_program_budget():
    source = run.ROOT / "examples/uart-alphanumerics.thor"
    assert run.quantum_for(source, None) == 20
    assert run.quantum_for(source, 5) == 5
    # Invalid explicit values must reach the compiler's rejection, not silently
    # select a different budget before programming the board.
    assert run.quantum_for(source, 0) == 0


def test_external_program_does_not_inherit_budget_by_filename(tmp_path):
    assert run.quantum_for(tmp_path / "uart-alphanumerics.thor", None) == 5


@pytest.fixture
def runner(monkeypatch, tmp_path):
    source = tmp_path / "program.thor"
    source.write_text("(UART-TX 65)")
    tool = tmp_path / "tools/fpgatool/fpgatool.py"
    tool.parent.mkdir(parents=True)
    tool.touch()
    monkeypatch.setattr(run, "ROOT", tmp_path)
    monkeypatch.setattr(run.shutil, "which", lambda name: "/mock/programmer")
    monkeypatch.setattr(
        run,
        "compile_image",
        lambda *args: (b"image", {"command_count": 1, "sha256": "digest"}),
    )
    monkeypatch.setattr(run.sys, "argv", ["fpga", str(source)])
    return tmp_path


def test_image_rejection_never_touches_board(runner, monkeypatch):
    attempts = []

    def reject(*args):
        raise ValueError("image does not match hardware")

    monkeypatch.setattr(run, "verify", reject)
    monkeypatch.setattr(
        run.subprocess, "run", lambda *args, **kw: attempts.append(args)
    )
    with pytest.raises(ValueError, match="does not match hardware"):
        run.main()
    assert attempts == []


def test_failed_flash_write_never_restarts_board(runner, monkeypatch):
    attempts = []
    monkeypatch.setattr(run, "verify", lambda *args: None)

    def fail(command, **kwargs):
        attempts.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(run.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        run.main()
    assert len(attempts) == 1
    assert "program-data" in attempts[0]
    assert "--reset" not in attempts[0]
    receipt_path = next(runner.glob("build/red2-standalone/programs/*/deployment.json"))
    receipt = json.loads(receipt_path.read_text())
    assert not receipt["passed"]
    assert receipt["stages"] == []
    assert "error" in receipt

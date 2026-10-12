"""The synthesis gate must validate the arithmetic profile it emits."""

import importlib
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize(
    ("floating", "checker"),
    [
        (None, "check_syn_integer_profile.py"),
        ("0", "check_syn_integer_profile.py"),
        ("1", "check_syn_sim.py"),
    ],
)
def test_synthesis_gate_selects_matching_native_profile(monkeypatch, floating, checker):
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(repo / "scripts"))
    gate = importlib.import_module("check_syn")
    if floating is None:
        monkeypatch.delenv("RED2_SYN_FLOAT", raising=False)
    else:
        monkeypatch.setenv("RED2_SYN_FLOAT", floating)
    monkeypatch.setattr(gate, "_pipelinec_environment", lambda *_: {"profile": floating})
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="PASS", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", run)
    result = gate._run_native_sim(None, repo)
    assert result.returncode == 0
    assert calls[0][0][1] == str(repo / "scripts" / checker)
    assert calls[0][1]["env"] == {"profile": floating}

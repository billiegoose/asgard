import hashlib
import importlib.util
import json
import select
import subprocess
import sys
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/boards/red2_basys3/host.py"
SPEC = importlib.util.spec_from_file_location("red2_progress_host", SOURCE)
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


def test_checkpoint_survives_abrupt_process_termination(tmp_path):
    path = tmp_path / "result.progress.json"
    code = """
import importlib.util,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('host',sys.argv[1])
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
progress=host.ReplayProgress(Path(sys.argv[2]))
progress.update({'compared_clocks':100,'completed_pass':False},'running',1.0)
print('CHECKPOINT_READY',flush=True)
sys.stdin.read()
"""
    process = subprocess.Popen(
        [sys.executable, "-u", "-c", code, str(SOURCE), str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert select.select([process.stdout], [], [], 5)[0], "missing ready marker"
        assert process.stdout.readline().strip() == "CHECKPOINT_READY"
        process.kill()
        process.wait(timeout=5)
        checkpoint = json.loads(path.read_text())
        assert checkpoint["compared_clocks"] == 100
        assert checkpoint["pid"] == process.pid
        assert not checkpoint["completed_pass"]
        assert not checkpoint["resume_supported"]
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


def test_existing_checkpoint_is_never_overwritten_by_another_run(tmp_path):
    path = tmp_path / "result.progress.json"
    progress = host.ReplayProgress(path)
    progress.update({"compared_clocks": 100}, "running", 1)
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        host.ReplayProgress(path)
    assert path.read_bytes() == original


def test_failed_checkpoint_update_preserves_last_valid_record(tmp_path):
    path = tmp_path / "result.progress.json"
    progress = host.ReplayProgress(path)
    progress.update({"compared_clocks": 100}, "running", 1)
    original = path.read_bytes()
    with pytest.raises(TypeError):
        progress.update({"invalid": object()}, "running", 2)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def test_mismatched_reply_is_not_counted_as_a_confirmed_clock(tmp_path, monkeypatch):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "provenance.json").write_text(
        json.dumps({"candidate_source_sha256": "fixture"})
    )
    vectors = tmp_path / "vectors.txt"
    vectors.write_text("7 1\n7 2\n")
    vectors.with_suffix(".json").write_text(
        json.dumps(
            {
                "candidate_sha256": "fixture",
                "input_width": 722,
                "output_width": 626,
                "cycles": 2,
                "vectors_sha256": hashlib.sha256(vectors.read_bytes()).hexdigest(),
            }
        )
    )

    class Link:
        calls = 0

        def __init__(self, *args):
            pass

        def exchange(self, command, sequence):
            self.calls += 1
            return 1 if self.calls == 1 else 99

        def close(self):
            pass

    log = tmp_path / "result.json"
    monkeypatch.setattr(host, "SerialLink", Link)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "host.py",
            "--port",
            "fixture",
            "--prepared",
            str(prepared),
            "--log",
            str(log),
            str(vectors),
        ],
    )
    with pytest.raises(ValueError, match="clock 1"):
        host.main()
    result = json.loads(log.read_text())
    checkpoint = json.loads(log.with_suffix(".progress.json").read_text())
    assert result["compared_clocks"] == checkpoint["compared_clocks"] == 1
    assert not result["completed_pass"]
    assert checkpoint["state"] == "failed"

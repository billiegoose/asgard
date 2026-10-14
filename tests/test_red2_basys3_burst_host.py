import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from scripts.boards.red2_basys3.burst_monitor import clock_burst_command

SOURCE = Path(__file__).resolve().parents[1] / "scripts/boards/red2_basys3/host.py"
SPEC = importlib.util.spec_from_file_location("red2_burst_host", SOURCE)
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


def setup_run(tmp_path, monkeypatch, *, capable=True, rows="7 1\n7 2\n0 3\n7 4\n"):
    prepared = tmp_path / "prepared"
    prepared.mkdir()
    options = prepared / "board-placement-options.json"
    options.write_text(json.dumps({"burst_clock": capable}))
    (prepared / "provenance.json").write_text(
        json.dumps(
            {
                "candidate_source_sha256": "fixture",
                "files_sha256": {
                    options.name: hashlib.sha256(options.read_bytes()).hexdigest()
                },
            }
        )
    )
    vectors = tmp_path / "vectors.txt"
    vectors.write_text(rows)
    vectors.with_suffix(".json").write_text(
        json.dumps(
            {
                "candidate_sha256": "fixture",
                "input_width": 722,
                "output_width": 626,
                "cycles": len(rows.splitlines()),
                "vectors_sha256": hashlib.sha256(vectors.read_bytes()).hexdigest(),
            }
        )
    )
    log = tmp_path / "result.json"
    monkeypatch.syspath_prepend(str(SOURCE.parent))
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
            "--burst-clock",
            str(vectors),
        ],
    )
    return log, options


@pytest.mark.parametrize("mismatch", [False, True])
def test_burst_replay_records_only_confirmed_endpoints(tmp_path, monkeypatch, mismatch):
    log, _ = setup_run(tmp_path, monkeypatch)
    calls = []

    class Link:
        def __init__(self, *args):
            pass

        def exchange(self, command, sequence):
            calls.append((command, sequence))
            return [2, 99 if mismatch else 3, 4][len(calls) - 1]

        def close(self):
            pass

    monkeypatch.setattr(host, "SerialLink", Link)
    if mismatch:
        with pytest.raises(ValueError, match="clock 2"):
            host.main()
    else:
        host.main()
    result = json.loads(log.read_text())
    checkpoint = json.loads(log.with_suffix(".progress.json").read_text())
    assert calls[0] == (clock_burst_command(7, 2), 0)
    assert result["executed_clocks"] == (2 if mismatch else 4)
    assert result["compared_samples"] == (1 if mismatch else 3)
    assert result["last_compared_clock"] == (1 if mismatch else 3)
    assert "compared_clocks" not in result
    assert result["comparison_scope"] == "packet endpoints only"
    assert result["completed_pass"] is not mismatch
    assert checkpoint["state"] == ("failed" if mismatch else "passed")
    assert checkpoint["executed_clocks"] == result["executed_clocks"]


@pytest.mark.parametrize("reason", ["unsupported", "changed_options", "native_10"])
def test_invalid_burst_configuration_fails_before_opening_serial(
    tmp_path, monkeypatch, reason
):
    log, options = setup_run(
        tmp_path,
        monkeypatch,
        capable=reason != "unsupported",
        rows="A 0\n" if reason == "native_10" else "7 1\n7 2\n",
    )
    if reason == "changed_options":
        options.write_text("{}")

    def forbidden(*args):
        pytest.fail("serial opened before preflight rejection")

    monkeypatch.setattr(host, "SerialLink", forbidden)
    with pytest.raises(SystemExit if reason == "unsupported" else ValueError):
        host.main()
    assert not log.exists()

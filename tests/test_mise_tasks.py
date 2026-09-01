from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path

import pytest


def run_mise_task(
    task: str,
    *args: str,
    stdin: str = "",
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["mise", "run", task, *args],
        input=stdin,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def test_mise_thor_runs_hangman_quietly() -> None:
    result = run_mise_task(
        "thor",
        "examples/hangman.thor",
        "--quantum",
        "5000",
        stdin="A\nS\nG\nR\nD\n",
    )

    assert result.returncode == 0
    assert "WORD: ASGARD\n" in result.stdout
    assert "WIN\n" in result.stdout
    assert result.stderr == ""


def test_mise_red2_runs_hangman_quietly() -> None:
    result = run_mise_task(
        "red2",
        "examples/hangman.thor",
        "--quantum",
        "5000",
        stdin="A\nS\nG\nR\nD\n",
    )

    assert result.returncode == 0
    assert "WORD: ASGARD\n" in result.stdout
    assert "WIN\n" in result.stdout
    assert result.stderr == ""


def test_mise_rust_runs_hangman_quietly() -> None:
    result = run_mise_task(
        "rust",
        "examples/hangman.thor",
        "--quantum",
        "5000",
        stdin="A\nS\nG\nR\nD\n",
    )

    assert result.returncode == 0
    assert "WORD: ASGARD\n" in result.stdout
    assert "WIN\n" in result.stdout
    assert result.stderr == ""


def test_mise_rust_verbose_reports_io_result() -> None:
    result = run_mise_task(
        "rust",
        "examples/hangman.thor",
        "--quantum",
        "5000",
        "--verbose",
        stdin="A\nS\nG\nR\nD\n",
    )

    assert result.returncode == 0
    assert "WORD: ASGARD\n" in result.stdout
    assert "WIN\n" in result.stdout
    assert "io result: NIL\n" in result.stderr


def test_mise_wasm_runs_hangman_quietly() -> None:
    result = run_mise_task(
        "wasm",
        "examples/hangman.thor",
        "--quantum",
        "5000",
        stdin="A\nS\nG\nR\nD\n",
        timeout=60.0,
    )

    assert result.returncode == 0
    assert "WORD: ASGARD\n" in result.stdout
    assert "WIN\n" in result.stdout
    assert result.stderr == ""


def test_mise_rust_accepts_clock_flag(tmp_path: Path) -> None:
    source = tmp_path / "clock.thor"
    source.write_text(
        """
        (IO-BIND (CLOCK)
          (LAMBDA (now)
            (UART-TX (MOD now 256))))
        """
    )
    clock = tmp_path / "clock.txt"
    clock.write_text("1700000000065\n")

    result = run_mise_task("rust", str(source), "--clock", str(clock))

    assert result.returncode == 0
    assert result.stdout == "A"
    assert result.stderr == ""


def test_mise_rust_hangman_waits_with_open_stdin_and_no_keys() -> None:
    process = subprocess.Popen(
        [
            "mise",
            "run",
            "rust",
            "examples/hangman.thor",
            "--quantum",
            "5000",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=5.0)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=2.0)

    assert "GUESS LETTERS; ESC QUITS\n" in stdout
    assert "primitive" not in stderr
    assert stderr == ""


def test_mise_rust_caesar_waits_with_open_stdin_and_no_keys() -> None:
    process = subprocess.Popen(
        [
            "mise",
            "run",
            "rust",
            "examples/uart-caesar-plus4.thor",
            "--quantum",
            "5000",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=5.0)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=2.0)

    assert stdout == ""
    assert "primitive" not in stderr
    assert stderr == ""


def test_mise_rust_breakout_ball_moves_with_open_stdin_and_no_keys() -> None:
    process = subprocess.Popen(
        [
            "mise",
            "run",
            "rust",
            "examples/breakout.thor",
            "--quantum",
            "50000",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            process.wait(timeout=8.0)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=2.0)
    assert "BREAKOUT 20x12\n" in stdout
    assert stdout.count("o") >= 2
    assert "\x1b[11;12Ho" in stdout
    assert stderr == ""


def test_mise_wasm_runs_recorded_breakout_playthrough_with_controlled_clock(
    tmp_path: Path,
) -> None:
    clock = tmp_path / "breakout-clock.txt"
    clock.write_text("1700000000000\n")
    driver = tmp_path / "drive_breakout.py"
    steps = [
        (1_700_000_000_000 + (tick * 500), " ", 0.05)
        for tick in range(1, 11)
    ] + [(1_700_000_005_500, "q", 0.0)]
    driver.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "import time\n"
        f"clock = Path({str(clock)!r})\n"
        f"steps = {steps!r}\n"
        "time.sleep(2.0)\n"
        "for timestamp, keys, delay in steps:\n"
        "    clock.write_text(f'{timestamp}\\n')\n"
        "    sys.stdout.write(keys)\n"
        "    sys.stdout.flush()\n"
        "    time.sleep(delay)\n"
    )

    command = (
        f"python3 {driver} | "
        f"mise run wasm examples/breakout.thor --clock {clock} --quantum 50000"
    )
    result = subprocess.run(
        ["bash", "-c", command],
        check=False,
        text=True,
        capture_output=True,
        timeout=90.0,
    )

    assert result.returncode == 0
    assert "BREAKOUT 20x12\n" in result.stdout
    assert result.stdout.count("o") >= 10
    assert "QUIT\n" in result.stdout
    assert result.stderr == ""


def test_mise_wasm_runs_breakout_with_controlled_clock(tmp_path: Path) -> None:
    clock = tmp_path / "breakout-clock.txt"
    clock.write_text("1700000000200\n")

    result = run_mise_task(
        "wasm",
        "examples/breakout.thor",
        "--quantum",
        "12000",
        "--clock",
        str(clock),
        stdin=" q",
        timeout=90.0,
    )

    assert result.returncode == 0
    assert "BREAKOUT 20x12\n" in result.stdout
    assert "QUIT\n" in result.stdout
    assert "\x1b[" in result.stdout
    assert result.stderr == ""


def test_mise_parity_reports_diagnostics() -> None:
    result = run_mise_task(
        "parity",
        "examples/fibonacci.thor",
        "--quantum",
        "75",
    )

    assert result.returncode == 0
    assert result.stdout != ""
    assert "parity" in result.stderr


def test_mise_python_tasks_accept_clock_flag(tmp_path: Path) -> None:
    source = tmp_path / "clock.thor"
    source.write_text("(IO-BIND (CLOCK) (LAMBDA (now) (UART-TX 65)))\n")
    clock = tmp_path / "clock.txt"
    clock.write_text("1700000000123\n")

    thor = run_mise_task("thor", str(source), "--clock", str(clock))
    red2 = run_mise_task("red2", str(source), "--clock", str(clock))

    assert thor.returncode == 0
    assert thor.stdout == "A"
    assert thor.stderr == ""
    assert red2.returncode == 0
    assert red2.stdout == "A"
    assert red2.stderr == ""


def test_mise_red2_clock_dots_runs_until_timeout_without_io_action_error() -> None:
    with pytest.raises(subprocess.TimeoutExpired) as timeout_info:
        run_mise_task(
            "red2",
            "--quantum",
            "100000",
            "examples/clock-dots.thor",
            timeout=3.0,
        )

    stdout = _timeout_text(timeout_info.value.stdout)
    stderr = _timeout_text(timeout_info.value.stderr)
    assert "." in stdout
    assert "not an IO action" not in stderr
    assert "RecursionError" not in stderr


def _timeout_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def test_mise_hdl_prints_placeholder() -> None:
    result = run_mise_task("hdl", "examples/hangman.thor")

    assert result.returncode == 0
    assert result.stdout == "todo\n"
    assert result.stderr == ""

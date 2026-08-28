from __future__ import annotations

import subprocess


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


def test_mise_hdl_prints_placeholder() -> None:
    result = run_mise_task("hdl", "examples/hangman.thor")

    assert result.returncode == 0
    assert result.stdout == "todo\n"
    assert result.stderr == ""

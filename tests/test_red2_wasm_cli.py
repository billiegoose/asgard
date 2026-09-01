from __future__ import annotations

import os
import select
import signal
import subprocess
import time
from pathlib import Path

from thor_spec.ast import Definition, Expr, StructDef
from thor_spec.normalization import normalize_program
from thor_spec.parser import parse_program
from thor_spec.red2.binary import encode_bundle
from thor_spec.red2.compiler import compile_definitions, compile_expr


def write_bytecode(tmp_path: Path, source: str) -> Path:
    program = normalize_program(parse_program(source))
    definitions: dict[str, Expr] = {}
    final: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            continue
        else:
            final = form
    assert final is not None
    path = tmp_path / "program.red2"
    path.write_bytes(
        encode_bundle(compile_expr(final), compile_definitions(definitions))
    )
    return path


def run_rust_vm_until_stdout_contains(
    path: Path,
    expected: str,
    quantum: int = 20,
    *,
    timeout: float = 20.0,
) -> tuple[str, str]:
    command = [
        "cargo",
        "run",
        "-p",
        "red2-wasm",
        "--quiet",
        "--",
        str(path),
        "--quantum",
        str(quantum),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    expected_bytes = expected.encode()
    stdout = bytearray()
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                break
            assert process.stdout is not None
            readable, _, _ = select.select([process.stdout], [], [], 0.05)
            if not readable:
                continue
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                break
            stdout.extend(chunk)
            if expected_bytes in stdout:
                break
        if expected_bytes not in stdout:
            decoded_stdout = stdout.decode(errors="replace")
            raise AssertionError(
                f"did not see {expected!r} within {timeout}s; "
                f"stdout={decoded_stdout!r}"
            )
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        remaining_stdout, stderr = process.communicate(timeout=2.0)
    stdout.extend(remaining_stdout)
    return stdout.decode(errors="replace"), stderr.decode(errors="replace")


def run_rust_vm(
    path: Path,
    quantum: int = 20,
    *,
    verbose: bool = False,
    stdin: str = "",
    timeout: float = 20.0,
    clock: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        "cargo",
        "run",
        "-p",
        "red2-wasm",
        "--quiet",
        "--",
        str(path),
        "--quantum",
        str(quantum),
    ]
    if clock is not None:
        command.extend(["--clock", str(clock)])
    if verbose:
        command.append("--verbose")
    return subprocess.run(
        command,
        input=stdin,
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def test_rust_red2_vm_runs_primitive_bytecode_with_stdout_reserved(
    tmp_path: Path,
) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(+ 2 3)"))

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_rust_red2_vm_runs_simple_lambda_bytecode_with_stdout_reserved(
    tmp_path: Path,
) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "((LAMBDA (X) (+ X 1)) 41)"))

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_rust_red2_vm_resolves_bundled_top_level_definition(
    tmp_path: Path,
) -> None:
    result = run_rust_vm(
        write_bytecode(tmp_path, "inc == (lambda (x) (+ x 1))\n(inc 41)")
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_rust_red2_vm_runs_if_and_range_predicate(tmp_path: Path) -> None:
    source = """
    choose == (lambda (x)
      (if (AND (>= x 65) (<= x 90))
          (+ x 4)
          x))
    (choose 65)
    """
    result = run_rust_vm(write_bytecode(tmp_path, source))

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_rust_red2_vm_runs_recursive_countdown(tmp_path: Path) -> None:
    source = """
    down == (lambda (n)
      (if (= n 0)
          99
          (down (1- n))))
    (down 4)
    """
    result = run_rust_vm(write_bytecode(tmp_path, source), quantum=100)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_rust_red2_vm_io_runs_caesar_cipher_with_stdout_as_uart(
    tmp_path: Path,
) -> None:
    bytecode = write_bytecode(
        tmp_path,
        Path("examples/uart-caesar-plus4.thor").read_text(),
    )

    result = run_rust_vm(
        bytecode,
        quantum=5000,
        stdin="abcXYZ!\x1b",
    )

    assert result.returncode == 0
    assert result.stdout == "efgBCD!"
    assert "io result: NIL" not in result.stderr
    assert "red2 result:" not in result.stderr
    assert result.stderr == ""


def test_rust_red2_vm_uart_rx_returns_nil_when_open_stdin_has_no_ready_byte(
    tmp_path: Path,
) -> None:
    bytecode = write_bytecode(tmp_path, "(UART-RX)")
    command = [
        "cargo",
        "run",
        "-p",
        "red2-wasm",
        "--quiet",
        "--",
        str(bytecode),
        "--quantum",
        "100",
        "--verbose",
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        process.wait(timeout=5.0)
        stdout, stderr = process.communicate(timeout=1.0)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

    assert process.returncode == 0
    assert stdout == ""
    assert stderr == "io result: NIL\n"


def test_rust_red2_vm_io_runs_hangman_with_newlines_ignored(
    tmp_path: Path,
) -> None:
    bytecode = write_bytecode(tmp_path, Path("examples/hangman.thor").read_text())

    result = run_rust_vm(
        bytecode,
        quantum=5000,
        stdin="A\nS\nG\nR\nD\n",
    )

    assert result.returncode == 0
    assert "GUESS LETTERS; ESC QUITS\n" in result.stdout
    assert "WORD: ASGARD\n" in result.stdout
    assert "GUESSED:\n" in result.stdout
    assert "HIT\n" not in result.stdout
    assert "MISS\n" not in result.stdout
    assert "LOSE\n" not in result.stdout
    assert "WIN\n" in result.stdout
    assert "io result: NIL" not in result.stderr
    assert "red2 result:" not in result.stderr
    assert result.stderr == ""


def test_rust_red2_vm_io_runs_hangman_tracks_wrong_guesses(
    tmp_path: Path,
) -> None:
    bytecode = write_bytecode(tmp_path, Path("examples/hangman.thor").read_text())

    result = run_rust_vm(
        bytecode,
        quantum=5000,
        stdin="x\ny\nz\nA\nS\nG\nR\nD\n",
    )

    assert result.returncode == 0
    assert "GUESSED: XYZ\n" in result.stdout
    assert "GUESSED: XYZASGRD" not in result.stdout
    assert "LOSE\n" not in result.stdout
    assert "WIN\n" in result.stdout
    assert "io result: NIL" not in result.stderr
    assert "red2 result:" not in result.stderr
    assert result.stderr == ""


def test_rust_red2_vm_io_clock_uses_latest_file_value(tmp_path: Path) -> None:
    bytecode = write_bytecode(
        tmp_path,
        """
        (IO-BIND (CLOCK)
          (LAMBDA (now)
            (UART-TX (MOD now 256))))
        """,
    )
    clock = tmp_path / "clock.txt"
    clock.write_text("bad\n1700000000065\n")

    result = run_rust_vm(bytecode, quantum=100, clock=clock)

    assert result.returncode == 0
    assert result.stdout == "A"
    assert result.stderr == ""


def test_rust_red2_vm_io_clock_defaults_to_system_time(tmp_path: Path) -> None:
    bytecode = write_bytecode(
        tmp_path,
        """
        (IO-BIND (CLOCK)
          (LAMBDA (now)
            (if (> now 1000000000000)
                (UART-TX 89)
                (UART-TX 78))))
        """,
    )

    result = run_rust_vm(bytecode, quantum=100)

    assert result.returncode == 0
    assert result.stdout == "Y"
    assert result.stderr == ""


def test_rust_red2_vm_io_runs_breakout_with_controlled_clock(tmp_path: Path) -> None:
    bytecode = write_bytecode(tmp_path, Path("examples/breakout.thor").read_text())
    clock = tmp_path / "breakout-clock.txt"
    clock.write_text("1700000000200\n")

    result = run_rust_vm(
        bytecode,
        quantum=12000,
        stdin=" q",
        clock=clock,
        timeout=30.0,
    )

    assert result.returncode == 0
    assert "BREAKOUT 20x12\n" in result.stdout
    assert "QUIT\n" in result.stdout
    assert "\x1b[" in result.stdout
    assert result.stderr == ""


def test_rust_red2_vm_breakout_arrow_keys_move_paddle(tmp_path: Path) -> None:
    bytecode = write_bytecode(tmp_path, Path("examples/breakout.thor").read_text())
    clock = tmp_path / "breakout-clock.txt"
    clock.write_text("1700000000000\n")

    left = run_rust_vm(
        bytecode,
        quantum=12000,
        stdin="\x1b[Dq",
        clock=clock,
    )
    right = run_rust_vm(
        bytecode,
        quantum=12000,
        stdin="\x1b[Cq",
        clock=clock,
    )

    assert left.returncode == 0
    assert right.returncode == 0
    assert "#      _____       #" in left.stdout
    assert "#        _____     #" in right.stdout
    assert left.stderr == ""
    assert right.stderr == ""


def test_rust_red2_vm_breakout_erases_a_brick_only_after_a_hit(
    tmp_path: Path,
) -> None:
    bytecode = write_bytecode(tmp_path, Path("examples/breakout.thor").read_text())
    clock = tmp_path / "breakout-clock.txt"
    clock.write_text("1700000000000\n")
    command = [
        "cargo",
        "run",
        "-p",
        "red2-wasm",
        "--quiet",
        "--",
        str(bytecode),
        "--quantum",
        "12000",
        "--clock",
        str(clock),
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout = bytearray()
    expected = b"\x1b[3;8H1 "
    deadline = time.monotonic() + 5.0
    tick = 1
    try:
        while time.monotonic() < deadline:
            clock.write_text(f"{1_700_000_000_000 + tick * 500}\n")
            tick += 1
            assert process.stdout is not None
            readable, _, _ = select.select([process.stdout], [], [], 0.02)
            if readable:
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                stdout.extend(chunk)
                if expected in stdout:
                    break
        assert expected in stdout
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        remaining_stdout, stderr = process.communicate(timeout=2.0)
    stdout.extend(remaining_stdout)
    text = stdout.decode(errors="replace")

    assert "\x1b[7;15H " in text
    assert "\x1b[7;16H " in text
    assert "\x1b[7;17H " in text
    assert "\x1b[7;14H " not in text
    assert "\x1b[3;8H1 " in text
    assert stderr.decode(errors="replace") == ""


def test_rust_red2_vm_runs_deep_io_then_chain_without_host_stack_growth(
    tmp_path: Path,
) -> None:
    action = "(IO-RETURN NIL)"
    for _ in range(300):
        action = f"(IO-THEN (UART-TX 65) {action})"

    result = run_rust_vm(write_bytecode(tmp_path, action), quantum=5000, timeout=30.0)

    assert result.returncode == 0
    assert result.stdout == "A" * 300
    assert result.stderr == ""


def test_rust_red2_vm_clock_dots_emits_dot_without_io_action_error(
    tmp_path: Path,
) -> None:
    bytecode = write_bytecode(tmp_path, Path("examples/clock-dots.thor").read_text())

    stdout, stderr = run_rust_vm_until_stdout_contains(
        bytecode,
        ".",
        quantum=100000,
        timeout=8.0,
    )

    assert "." in stdout
    assert "unknown IO action" not in stderr
    assert "not an IO action" not in stderr


def test_rust_red2_vm_errors_on_stuck_numeric_primitive(tmp_path: Path) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(+ 1 frog)"), quantum=100)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "primitive + argument 2 is stuck: frog" in result.stderr


def test_rust_red2_vm_errors_on_stuck_unary_primitive(tmp_path: Path) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(MINUS frog)"), quantum=100)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "primitive MINUS argument 1 is stuck: frog" in result.stderr


def test_rust_red2_vm_errors_on_stuck_io_primitive(tmp_path: Path) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(UART-TX frog)"), quantum=100)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "UART-TX argument is stuck: frog" in result.stderr


def test_rust_red2_vm_errors_on_stuck_if_condition(tmp_path: Path) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(if frog 1 2)"), quantum=100)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "IF condition is stuck: frog" in result.stderr


def test_rust_red2_vm_errors_on_stuck_and_argument(tmp_path: Path) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(AND frog TRUE)"), quantum=100)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "AND argument 1 is stuck: frog" in result.stderr


def test_rust_red2_vm_verbose_reports_io_result(tmp_path: Path) -> None:
    result = run_rust_vm(
        write_bytecode(tmp_path, "(UART-TX 65)"),
        quantum=100,
        verbose=True,
    )

    assert result.returncode == 0
    assert result.stdout == "A"
    assert result.stderr == "io result: NIL\n"


def test_rust_red2_vm_verbose_reports_non_io_result(tmp_path: Path) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(+ 2 3)"), verbose=True)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == "red2 result: 5\n"

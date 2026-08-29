from __future__ import annotations

import subprocess
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

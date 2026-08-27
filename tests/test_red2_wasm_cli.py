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
    io_mode: bool = False,
    stdin: str = "",
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
    if io_mode:
        command.append("--io")
    return subprocess.run(
        command,
        input=stdin,
        check=False,
        text=True,
        capture_output=True,
    )


def test_rust_red2_vm_runs_primitive_bytecode_with_stdout_reserved(
    tmp_path: Path,
) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "(+ 2 3)"))

    assert result.returncode == 0
    assert result.stdout == ""
    assert "red2 result: 5" in result.stderr


def test_rust_red2_vm_runs_simple_lambda_bytecode_with_stdout_reserved(
    tmp_path: Path,
) -> None:
    result = run_rust_vm(write_bytecode(tmp_path, "((LAMBDA (X) (+ X 1)) 41)"))

    assert result.returncode == 0
    assert result.stdout == ""
    assert "red2 result: 42" in result.stderr


def test_rust_red2_vm_resolves_bundled_top_level_definition(
    tmp_path: Path,
) -> None:
    result = run_rust_vm(
        write_bytecode(tmp_path, "inc == (lambda (x) (+ x 1))\n(inc 41)")
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert "red2 result: 42" in result.stderr


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
    assert "red2 result: 69" in result.stderr


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
    assert "red2 result: 99" in result.stderr


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
        io_mode=True,
        stdin="abcXYZ!\x1b",
    )

    assert result.returncode == 0
    assert result.stdout == "efgBCD!"
    assert "io result: NIL" in result.stderr
    assert "red2 result:" not in result.stderr

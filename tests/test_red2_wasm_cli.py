from __future__ import annotations

import subprocess
from pathlib import Path

from thor_spec.parser import parse_expr
from thor_spec.red2.binary import encode_program_image
from thor_spec.red2.compiler import compile_expr


def write_bytecode(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "program.red2"
    path.write_bytes(encode_program_image(compile_expr(parse_expr(source))))
    return path


def run_rust_vm(path: Path, quantum: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "cargo",
            "run",
            "-p",
            "red2-wasm",
            "--quiet",
            "--",
            str(path),
            "--quantum",
            str(quantum),
        ],
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

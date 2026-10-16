"""Whole archived compiler/reducer execution, rather than hand-built fixtures."""

import json
import subprocess
from pathlib import Path

import pytest
from tools.hilton_reference import program


@pytest.fixture(scope="module")
def horse(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return program.build(tmp_path_factory.mktemp("horse-build"))


def execute(
    horse: Path,
    directory: Path,
    source: str,
    *,
    quantum: int = 100_000,
    memory: int = 2048,
    trace_limit: int = 1000,
    compile_only: bool = False,
    passes: int = 1,
) -> subprocess.CompletedProcess[str]:
    path = directory / "input.lam"
    path.write_text(source + "\n")
    return subprocess.run(
        [
            str(horse),
            str(program.runner.ARCHIVE / "PRELUDE.LAM"),
            str(path),
            str(quantum),
            str(memory),
            str(directory / "graphs.jsonl"),
            str(directory / "trace.jsonl"),
            str(trace_limit),
            str(int(compile_only)),
            str(passes),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("(+ 2 3)", "5"),
        ("((lambda (x) x) 65)", "65"),
        ("((lambda (x) (+ x x)) (+ 20 1))", "42"),
        ("((lambda (x) ((lambda (y) x) 99)) 65)", "65"),
        ("(define double (lambda (x) (+ x x))) (double 21)", "42"),
        ("(car (cons 65 nil))", "65"),
        ("(if (< 4 5) 65 66)", "65"),
        ("(letrec ((f (lambda (n) (if (= n 0) 1 (* n (f (1- n))))))) (f 5))", "120"),
        ("((rec (lambda (self n) (if (= n 0) 0 (self (- n 1))))) 100)", "0"),
    ],
)
def test_whole_program(horse: Path, tmp_path: Path, source: str, expected: str) -> None:
    result = execute(horse, tmp_path, source)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_graphs_have_real_compiler_nodes_and_instruction_state(
    horse: Path,
    tmp_path: Path,
) -> None:
    result = execute(horse, tmp_path, "(+ 2 3)")
    assert result.returncode == 0, result.stderr
    compiled, reduced = [
        json.loads(line)
        for line in (tmp_path / "graphs.jsonl").read_text().splitlines()
    ]
    assert [(n["type"], n["operand"], n["class"]) for n in compiled["nodes"]] == [
        ("INT", 3, 1),
        ("INT", 2, 1),
        ("PRIM_2", "+", 2),
    ]
    assert reduced["nodes"] == [
        {
            "address": reduced["root"],
            "class": 2,
            "type": "INT",
            "operand": 5,
        }
    ]
    assert reduced["reductions"] == 1
    trace = [
        json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()
    ]
    assert trace[0]["instruction"][0]["operand"] == 3
    assert trace[-1]["stage"] == "trace-end"
    assert trace[-1]["truncated"] is False


def test_trace_limit_is_explicit(horse: Path, tmp_path: Path) -> None:
    result = execute(horse, tmp_path, "(+ 2 3)", trace_limit=1)
    assert result.returncode == 0, result.stderr
    rows = [json.loads(s) for s in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    assert rows[-1]["truncated"] is True
    assert rows[-1]["observed_steps"] > rows[-1]["written_steps"] == 1


def test_bounded_pure_recursion_fails_on_real_memory_exhaustion(
    horse: Path,
    tmp_path: Path,
) -> None:
    result = execute(
        horse,
        tmp_path,
        "((rec (lambda (self n) (if (= n 0) 0 (self (- n 1))))) 100)",
        memory=256,
    )
    assert result.returncode == 70
    assert "OUT OF GRAPH MEMORY" in result.stderr
    assert not result.stdout
    rows = [json.loads(s) for s in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert rows[-1]["stage"] == "fault"


def test_invalid_source_is_failure_even_at_eof(horse: Path, tmp_path: Path) -> None:
    result = execute(horse, tmp_path, "(+ 2")
    assert result.returncode == 65
    assert "Parse Error" in result.stderr


def test_compile_only_does_not_contract(horse: Path, tmp_path: Path) -> None:
    result = execute(horse, tmp_path, "(+ 2 3)", compile_only=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "(+ 2 3)"
    graphs = (tmp_path / "graphs.jsonl").read_text().splitlines()
    assert len(graphs) == 1
    assert json.loads(graphs[0])["stage"] == "compiled"


def test_quantum_zero_returns_residual(horse: Path, tmp_path: Path) -> None:
    result = execute(horse, tmp_path, "(+ 2 3)", quantum=0)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "(+ 2 3)"
    graphs = [
        json.loads(s) for s in (tmp_path / "graphs.jsonl").read_text().splitlines()
    ]
    assert graphs[-1]["reductions"] == 0


def test_small_quanta_recycle_memory_and_finish(horse: Path, tmp_path: Path) -> None:
    result = execute(
        horse,
        tmp_path,
        "((rec (lambda (self n) (if (= n 0) 0 (self (- n 1))))) 100)",
        quantum=20,
        memory=256,
        passes=100,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-1] == "0"
    rows = [json.loads(s) for s in (tmp_path / "graphs.jsonl").read_text().splitlines()]
    results = [row for row in rows if row["stage"] == "result"]
    assert len(results) > 1
    assert max(row["peak_environment_words"] for row in results) < 50
    assert any(row["stage"] == "restarted" for row in rows)

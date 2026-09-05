from __future__ import annotations

import csv
import importlib.util
import io
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/benchmark_python_engines.py"
SPEC = importlib.util.spec_from_file_location("benchmark_python_engines", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
bench = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bench
SPEC.loader.exec_module(bench)


def _rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


def test_all_benchmarks_emit_adjacent_backend_pairs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        bench.main(["--benchmark", "all", "--warmups", "0", "--iterations", "1"]) == 0
    )
    captured = capsys.readouterr()
    rows = _rows(captured.out)

    assert [row["benchmark"] for row in rows] == [
        "tak",
        "tak",
        "list",
        "list",
        "struct",
        "struct",
        "game",
        "game",
    ]
    assert [row["backend"] for row in rows] == ["thor", "red2"] * 4
    assert [row["result"] for row in rows] == [
        "15",
        "15",
        "300",
        "300",
        "300",
        "300",
        "8",
        "8",
    ]
    assert [row["work_unit_name"] for row in rows] == [
        "thor_contractions",
        "mured_cycles",
    ] * 4
    assert all(row["iterations"] == "1" for row in rows)
    assert all(float(row["speedup_vs_thor"]) > 0 for row in rows)
    assert all(rows[index]["speedup_vs_thor"] == "1.000000" for index in (0, 2, 4, 6))


def test_single_benchmark_emits_only_two_rows(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        bench.main(["--benchmark", "tak", "--warmups", "0", "--iterations", "1"]) == 0
    )
    rows = _rows(capsys.readouterr().out)
    assert [(row["benchmark"], row["backend"]) for row in rows] == [
        ("tak", "thor"),
        ("tak", "red2"),
    ]


def test_prepare_reads_parses_and_normalizes_source_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parse_calls = 0
    normalize_calls = 0
    real_parse = bench.parse_program
    real_normalize = bench.normalize_program

    def counted_parse(source: str) -> object:
        nonlocal parse_calls
        parse_calls += 1
        return real_parse(source)

    def counted_normalize(program: object) -> object:
        nonlocal normalize_calls
        normalize_calls += 1
        return real_normalize(program)

    monkeypatch.setattr(bench, "parse_program", counted_parse)
    monkeypatch.setattr(bench, "normalize_program", counted_normalize)

    prepared = bench.prepare_benchmark(bench.BENCHMARKS["tak"])

    assert prepared.spec.name == "tak"
    assert parse_calls == 1
    assert normalize_calls == 1


def test_csv_header_is_exact() -> None:
    assert bench.CSV_HEADER == (
        "benchmark",
        "backend",
        "result",
        "iterations",
        "median_seconds",
        "best_seconds",
        "speedup_vs_thor",
        "work_units",
        "work_unit_name",
    )


def test_invalid_numeric_bounds_raise_system_exit() -> None:
    for args in (
        ["--warmups", "-1"],
        ["--iterations", "0"],
        ["--quantum", "0"],
        ["--cycle-limit", "0"],
    ):
        with pytest.raises(SystemExit):
            bench.main(args)


def test_failure_buffers_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(*args: object, **kwargs: object) -> list[dict[str, object]]:
        raise RuntimeError("boom")

    monkeypatch.setattr(bench, "benchmark", fail)
    assert bench.main(["--benchmark", "tak"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "benchmark failed: boom" in captured.err

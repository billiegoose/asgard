from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/benchmark.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("benchmark_report", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
bench = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bench
SPEC.loader.exec_module(bench)


def _python_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    expected = {"tak": "15", "list": "300", "struct": "300", "game": "8"}
    for index, name in enumerate(("tak", "list", "struct", "game"), start=1):
        rows.extend(
            [
                {
                    "benchmark": name,
                    "backend": "thor",
                    "result": expected[name],
                    "iterations": 5,
                    "median_seconds": f"{index / 10:.9f}",
                    "best_seconds": f"{index / 11:.9f}",
                    "speedup_vs_thor": "1.000000",
                    "work_units": index * 100,
                    "work_unit_name": "thor_contractions",
                },
                {
                    "benchmark": name,
                    "backend": "red2",
                    "result": expected[name],
                    "iterations": 5,
                    "median_seconds": f"{index / 20:.9f}",
                    "best_seconds": f"{index / 21:.9f}",
                    "speedup_vs_thor": "2.000000",
                    "work_units": index * 200,
                    "work_unit_name": "mured_cycles",
                },
            ]
        )
    return rows


def _breakout_rows() -> list[tuple[str, float, float]]:
    return [
        ("thor", 2.0, 1.9),
        ("red2", 1.0, 0.9),
        ("rust", 0.8, 0.7),
        ("wasm", 0.5, 0.4),
    ]


def _fake_python_benchmark(*args: object, **kwargs: object) -> list[dict[str, object]]:
    return _python_rows()


def _fake_breakout_benchmark(_iterations: int) -> list[tuple[str, float, float]]:
    return _breakout_rows()


def test_render_report_contains_both_benchmark_tables() -> None:
    report = bench.render_report(
        _python_rows(),
        _breakout_rows(),
        warmups=1,
        python_iterations=5,
        breakout_iterations=3,
        quantum=5_000_000,
        cycle_limit=2_000_000,
        recorded_at="2026-09-07T18:00:00-04:00",
        platform_label="Darwin arm64",
        python_version="3.14.7",
    )

    assert "# Benchmarks" in report
    assert "mise run benchmark" in report
    assert "## In-process Python reducer and VM battery" in report
    assert "| tak | 100.00 ms | 50.00 ms | 2.00x | 100 | 200 |" in report
    assert "## End-to-end Breakout backend benchmark" in report
    assert "| WASM RED2 | 500.00 ms | 400.00 ms | 4.00x |" in report


def test_main_updates_report_only_after_both_suites_succeed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report_path = tmp_path / "benchmarks.md"
    report_path.write_text("old report\n")
    monkeypatch.setattr(bench, "REPORT_PATH", report_path)
    monkeypatch.setattr(bench.python_bench, "benchmark", _fake_python_benchmark)

    def fail_breakout(_iterations: int) -> list[tuple[str, float, float]]:
        raise RuntimeError("breakout failed")

    monkeypatch.setattr(bench.breakout_bench, "benchmark", fail_breakout)

    assert bench.main([]) == 1
    assert report_path.read_text() == "old report\n"


def test_main_runs_both_suites_and_replaces_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    report_path = tmp_path / "benchmarks.md"
    report_path.write_text("old report\n")
    monkeypatch.setattr(bench, "REPORT_PATH", report_path)
    monkeypatch.setattr(bench.python_bench, "benchmark", _fake_python_benchmark)
    monkeypatch.setattr(
        bench.breakout_bench,
        "benchmark",
        _fake_breakout_benchmark,
    )

    assert bench.main([]) == 0
    text = report_path.read_text()
    assert text.startswith("# Benchmarks\n")
    assert "old report" not in text
    assert "Latest Python results" in text
    assert "Latest Breakout results" in text

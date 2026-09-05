from __future__ import annotations

import argparse
import csv
import io
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from thor_compile.red2 import load_faithful_machine
from thor_engine.golden import _initial_definitions
from thor_engine.semantics import ThorDefinitionCache, _Reducer, translate
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition

ROOT = Path(__file__).resolve().parents[1]
CSV_HEADER = (
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


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    path: Path
    expected: str


@dataclass(frozen=True)
class PreparedBenchmark:
    spec: BenchmarkSpec
    thor_expr: Expr
    thor_definitions: ThorDefinitionCache
    red2_expr: Expr
    red2_definitions: dict[str, Expr]


@dataclass(frozen=True)
class Sample:
    result: str
    seconds: float
    work_units: int


BENCHMARKS: dict[str, BenchmarkSpec] = {
    "tak": BenchmarkSpec("tak", ROOT / "benchmarks/tak.thor", "15"),
    "list": BenchmarkSpec("list", ROOT / "benchmarks/list-build-sum.thor", "300"),
    "struct": BenchmarkSpec("struct", ROOT / "benchmarks/struct-build-sum.thor", "300"),
    "game": BenchmarkSpec(
        "game", ROOT / "tests/fixtures/appendix_a/game_full.thor", "8"
    ),
}


def prepare_benchmark(spec: BenchmarkSpec) -> PreparedBenchmark:
    source = spec.path.read_text()
    program = normalize_program(parse_program(source))
    thor_definitions = _initial_definitions(model="thor")
    red2_definitions = _initial_definitions(model="red2")
    expr: Expr | None = None

    for form in program.forms:
        if isinstance(form, Definition):
            thor_definitions[form.name] = form.expr
            red2_definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, thor_definitions)
            install_struct_definition(form.tag, form.accessors, red2_definitions)
        else:
            if expr is not None:
                raise ValueError("benchmark source must contain exactly one expression")
            expr = form

    if expr is None:
        raise ValueError("benchmark source must contain one expression")
    return PreparedBenchmark(
        spec,
        translate(expr),
        ThorDefinitionCache.from_definitions(thor_definitions),
        expr,
        red2_definitions,
    )


def _run_thor(prepared: PreparedBenchmark, *, quantum: int) -> Sample:
    reducer = _Reducer(prepared.thor_definitions.definitions, quantum)
    started = time.perf_counter()
    reduced = reducer.reduce(prepared.thor_expr, (), 0)
    elapsed = time.perf_counter() - started
    rendered = to_source(reduced)
    return Sample(rendered, elapsed, reducer.steps)


def _run_red2(
    prepared: PreparedBenchmark,
    *,
    quantum: int,
    cycle_limit: int,
) -> Sample:
    machine = load_faithful_machine(
        prepared.red2_expr,
        quantum=quantum,
        definitions=dict(prepared.red2_definitions),
    )
    started = time.perf_counter()
    machine.run(cycle_limit=cycle_limit)
    elapsed = time.perf_counter() - started
    rendered = to_source(machine.result_expr())
    return Sample(rendered, elapsed, machine.state.cycles)


def _expect(sample: Sample, expected: str, *, benchmark: str, backend: str) -> None:
    if sample.result != expected:
        raise RuntimeError(
            f"{benchmark}/{backend} produced {sample.result!r}; expected {expected!r}"
        )


def _measure_backend(
    prepared: PreparedBenchmark,
    backend: str,
    *,
    warmups: int,
    iterations: int,
    quantum: int,
    cycle_limit: int,
) -> tuple[list[float], int, str]:
    if backend == "thor":

        def run() -> Sample:
            return _run_thor(prepared, quantum=quantum)

        work_unit_name = "thor_contractions"
    elif backend == "red2":

        def run() -> Sample:
            return _run_red2(
                prepared,
                quantum=quantum,
                cycle_limit=cycle_limit,
            )

        work_unit_name = "mured_cycles"
    else:
        raise ValueError(f"unknown backend: {backend}")

    for _ in range(warmups):
        _expect(
            run(),
            prepared.spec.expected,
            benchmark=prepared.spec.name,
            backend=backend,
        )

    samples: list[float] = []
    work_units: int | None = None
    for _ in range(iterations):
        sample = run()
        _expect(
            sample,
            prepared.spec.expected,
            benchmark=prepared.spec.name,
            backend=backend,
        )
        samples.append(sample.seconds)
        if work_units is None:
            work_units = sample.work_units
        elif work_units != sample.work_units:
            raise RuntimeError(
                f"{prepared.spec.name}/{backend} work counter changed across samples"
            )
    assert work_units is not None
    return samples, work_units, work_unit_name


def benchmark(
    names: Sequence[str],
    *,
    warmups: int,
    iterations: int,
    quantum: int,
    cycle_limit: int,
) -> list[dict[str, object]]:
    prepared = [prepare_benchmark(BENCHMARKS[name]) for name in names]

    for item in prepared:
        _expect(
            _run_thor(item, quantum=quantum),
            item.spec.expected,
            benchmark=item.spec.name,
            backend="thor",
        )
        _expect(
            _run_red2(item, quantum=quantum, cycle_limit=cycle_limit),
            item.spec.expected,
            benchmark=item.spec.name,
            backend="red2",
        )

    rows: list[dict[str, object]] = []
    for item in prepared:
        backend_rows: dict[str, tuple[list[float], int, str]] = {}
        for backend in ("thor", "red2"):
            backend_rows[backend] = _measure_backend(
                item,
                backend,
                warmups=warmups,
                iterations=iterations,
                quantum=quantum,
                cycle_limit=cycle_limit,
            )

        thor_median = statistics.median(backend_rows["thor"][0])
        for backend in ("thor", "red2"):
            samples, work_units, work_unit_name = backend_rows[backend]
            median = statistics.median(samples)
            rows.append(
                {
                    "benchmark": item.spec.name,
                    "backend": backend,
                    "result": item.spec.expected,
                    "iterations": iterations,
                    "median_seconds": f"{median:.9f}",
                    "best_seconds": f"{min(samples):.9f}",
                    "speedup_vs_thor": f"{thor_median / median:.6f}",
                    "work_units": work_units,
                    "work_unit_name": work_unit_name,
                }
            )
    return rows


def _render_csv(rows: Sequence[dict[str, object]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_HEADER, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the pure Python THOR and faithful RED2 engines."
    )
    parser.add_argument(
        "--benchmark",
        choices=("all", *BENCHMARKS),
        default="all",
    )
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--quantum", type=int, default=5_000_000)
    parser.add_argument("--cycle-limit", type=int, default=2_000_000)
    args = parser.parse_args(argv)

    if args.warmups < 0:
        parser.error("--warmups must be >= 0")
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    if args.quantum < 1:
        parser.error("--quantum must be >= 1")
    if args.cycle_limit < 1:
        parser.error("--cycle-limit must be >= 1")

    names = tuple(BENCHMARKS) if args.benchmark == "all" else (args.benchmark,)
    try:
        rows = benchmark(
            names,
            warmups=args.warmups,
            iterations=args.iterations,
            quantum=args.quantum,
            cycle_limit=args.cycle_limit,
        )
    except Exception as exc:
        print(f"benchmark failed: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(_render_csv(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

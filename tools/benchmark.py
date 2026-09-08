from __future__ import annotations

import argparse
import platform
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import benchmark_python_engines as python_bench
from videos import benchmark_breakout as breakout_bench

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "benchmarks.md"

WORKLOAD_DESCRIPTIONS = {
    "tak": "Recursive application, nested IF, comparison, decrement, and arithmetic.",
    "list": (
        "Dynamic PAIR/list allocation followed by recursive NULL?, CAR, and "
        "CDR traversal."
    ),
    "struct": (
        "Dynamic user-defined STRUCT allocation and generated selector traversal."
    ),
    "game": (
        "Appendix-A GAME path with lists, STRUCTs, LETREC, pruning, and "
        "minimax-style recursion."
    ),
}

BREAKOUT_BACKEND_NAMES = {
    "thor": "THOR",
    "red2": "Python RED2",
    "rust": "Rust RED2",
    "wasm": "WASM RED2",
}


def _duration(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.2f} ms"
    return f"{seconds:.3f} s"


def _python_rows_by_benchmark(
    rows: Sequence[dict[str, object]],
) -> dict[str, dict[str, dict[str, object]]]:
    grouped: dict[str, dict[str, dict[str, object]]] = {}
    for row in rows:
        benchmark = str(row["benchmark"])
        backend = str(row["backend"])
        grouped.setdefault(benchmark, {})[backend] = dict(row)
    return grouped


def render_report(
    python_rows: Sequence[dict[str, object]],
    breakout_rows: Sequence[tuple[str, float, float]],
    *,
    warmups: int,
    python_iterations: int,
    breakout_iterations: int,
    quantum: int,
    cycle_limit: int,
    recorded_at: str,
    platform_label: str,
    python_version: str,
) -> str:
    grouped = _python_rows_by_benchmark(python_rows)
    breakout_baseline = next(
        mean for model, mean, _best in breakout_rows if model == "thor"
    )

    lines = [
        "# Benchmarks",
        "",
        (
            "This is the canonical benchmark report for Asgard. Regenerate both "
            "result tables with:"
        ),
        "",
        "```sh",
        "mise run benchmark",
        "```",
        "",
        (
            "The lower-level `benchmark-python` and `benchmark-breakout` tasks "
            "remain available for targeted diagnostics, but only `mise run "
            "benchmark` updates this file."
        ),
        "",
        "## In-process Python reducer and VM battery",
        "",
        (
            "This battery compares the pure Python THOR reducer with the faithful "
            "Python RED2 machine. It is conformance-first: every workload must "
            "produce the expected result on both backends before measured rows "
            "are accepted."
        ),
        "",
        "### Workloads",
        "",
        "| Name | Source | Expected | What it stresses |",
        "| --- | --- | ---: | --- |",
    ]
    for name, spec in python_bench.BENCHMARKS.items():
        source = spec.path.relative_to(ROOT)
        description = WORKLOAD_DESCRIPTIONS[name]
        lines.append(
            f"| `{name}` | `{source}` | `{spec.expected}` | {description} |"
        )

    lines.extend(
        [
            "",
            "### Methodology",
            "",
            (
                "Source reading, parsing, normalization, definition preparation, "
                "and backend-specific setup happen outside the timed region. The "
                "runner performs an untimed parity preflight on THOR and RED2 "
                "before warmups or measured samples. If either backend raises, "
                "exceeds configured resources, or produces the wrong result, the "
                "benchmark command fails and `benchmarks.md` is not replaced."
            ),
            "",
            (
                "For THOR, the expression and visible definitions are translated "
                "before timing; each sample times only reducer execution. For "
                "RED2, a fresh faithful machine is compiled and loaded before "
                "timing; each sample times only `MuredMachine.run()`. Result "
                "reconstruction and `to_source` rendering happen after the timer "
                "stops. Warmups follow the same execution path but are excluded "
                "from statistics. Median measured time is the primary timing "
                "statistic; best time is diagnostic."
            ),
            "",
            (
                "`thor_contractions` and `mured_cycles` are backend-native work "
                "counters and are not directly comparable instruction counts. No "
                "backend is expected or required to win every workload."
            ),
            "",
            "### Latest Python results",
            "",
            (
                f"Recorded `{recorded_at}` on `{platform_label}` with Python "
                f"`{python_version}`. Defaults: {warmups} warmup(s), "
                f"{python_iterations} measured iteration(s), quantum {quantum}, "
                f"RED2 cycle limit {cycle_limit}."
            ),
            "",
            (
                "| Benchmark | THOR median | RED2 median | RED2 speedup vs THOR | "
                "THOR contractions | μRED cycles |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in python_bench.BENCHMARKS:
        thor = grouped[name]["thor"]
        red2 = grouped[name]["red2"]
        thor_seconds = float(str(thor["median_seconds"]))
        red2_seconds = float(str(red2["median_seconds"]))
        speedup = float(str(red2["speedup_vs_thor"]))
        thor_work = int(thor["work_units"])
        red2_work = int(red2["work_units"])
        lines.append(
            f"| {name} | {_duration(thor_seconds)} | {_duration(red2_seconds)} | "
            f"{speedup:.2f}x | {thor_work:,} | {red2_work:,} |"
        )

    lines.extend(
        [
            "",
            "## End-to-end Breakout backend benchmark",
            "",
            (
                "This benchmark measures a materially different boundary. It "
                "drives `examples/breakout.thor` through subprocesses using a "
                "deterministic 70-tick input stream and controlled latest-value "
                "clock, followed by `q`. It includes command startup, source "
                "preparation, IO handling, terminal output, `mise` overhead, and "
                "backend-specific host/runtime costs across THOR, Python RED2, "
                "Rust RED2, and WASM RED2."
            ),
            "",
            (
                "Python RED2 executes the effectful program on one persistent "
                "faithful `MuredMachine`; UART and CLOCK effects suspend and "
                "resume that same machine. The contraction quantum is a "
                "scheduler/watchdog budget and is recharged after successful host "
                "dispatch by default."
            ),
            "",
            (
                "Faithful loaders default to 1,048,576 graph/environment words "
                "and 8,192 control entries. Environment allocation is currently "
                "monotonic and there is no graph/environment garbage collector, "
                "so sufficiently long-lived programs can still exhaust the arena."
            ),
            "",
            (
                "The scheduler distinguishes genuine external quantum exhaustion "
                "from temporary `q = 0` states used internally during faithful "
                "IF/STRUCT reconstruction; those internal states complete normally "
                "rather than surfacing as host-visible scheduler suspensions."
            ),
            "",
            "### Default-capacity acceptance checks",
            "",
            (
                "Current regression coverage also exercises deterministic Breakout, "
                "Pong, and repeated CLOCK polling under the standard faithful arena "
                "and host-dispatch recharge policy. These checks guard the practical "
                "interactive workload envelope separately from the timing tables."
            ),
            "",
            "### Latest Breakout results",
            "",
            (
                f"Recorded as part of the same `{recorded_at}` benchmark run with "
                f"{breakout_iterations} measured iteration(s) per backend."
            ),
            "",
            "| Backend | Mean | Best | Speedup vs THOR |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for model, mean, best in breakout_rows:
        display = BREAKOUT_BACKEND_NAMES[model]
        speedup = breakout_baseline / mean
        lines.append(
            f"| {display} | {_duration(mean)} | {_duration(best)} | {speedup:.2f}x |"
        )

    lines.extend(
        [
            "",
            (
                "These end-to-end timings are diagnostic rather than a performance "
                "contract. Process startup, host load, filesystem state, and "
                "terminal/runtime overhead can move them between runs."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _write_report_atomically(text: str) -> None:
    temporary = REPORT_PATH.with_suffix(".md.tmp")
    temporary.write_text(text)
    temporary.replace(REPORT_PATH)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run all canonical Asgard benchmarks and update benchmarks.md."
    )
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--python-iterations", type=int, default=5)
    parser.add_argument("--breakout-iterations", type=int, default=3)
    parser.add_argument("--quantum", type=int, default=5_000_000)
    parser.add_argument("--cycle-limit", type=int, default=2_000_000)
    args = parser.parse_args(argv)

    if args.warmups < 0:
        parser.error("--warmups must be >= 0")
    if args.python_iterations < 1:
        parser.error("--python-iterations must be >= 1")
    if args.breakout_iterations < 1:
        parser.error("--breakout-iterations must be >= 1")
    if args.quantum < 1:
        parser.error("--quantum must be >= 1")
    if args.cycle_limit < 1:
        parser.error("--cycle-limit must be >= 1")

    try:
        python_rows = python_bench.benchmark(
            tuple(python_bench.BENCHMARKS),
            warmups=args.warmups,
            iterations=args.python_iterations,
            quantum=args.quantum,
            cycle_limit=args.cycle_limit,
        )
        breakout_rows = breakout_bench.benchmark(args.breakout_iterations)
        recorded_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
        platform_label = f"{platform.system()} {platform.machine()}"
        python_version = platform.python_version()
        report = render_report(
            python_rows,
            breakout_rows,
            warmups=args.warmups,
            python_iterations=args.python_iterations,
            breakout_iterations=args.breakout_iterations,
            quantum=args.quantum,
            cycle_limit=args.cycle_limit,
            recorded_at=recorded_at,
            platform_label=platform_label,
            python_version=python_version,
        )
    except Exception as exc:
        print(f"benchmark failed: {exc}", file=sys.stderr)
        return 1

    _write_report_atomically(report)
    sys.stdout.write(report)
    print(f"updated {REPORT_PATH.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

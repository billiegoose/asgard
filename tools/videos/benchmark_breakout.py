import argparse
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TICK_MS = 100
START_MS = 1_700_000_000_000
MODEL_COMMANDS = {
    "thor": "mise run thor",
    "red2": "mise run red2",
    "rust": "mise run rust",
    "wasm": "mise run wasm",
}


def breakout_input() -> str:
    keys_by_tick = {
        10: "\x1b[C",
        11: "\x1b[C",
        12: "\x1b[C",
        23: "\x1b[D",
        24: "\x1b[D",
        25: "\x1b[D",
        26: "\x1b[D",
        38: "\x1b[C",
        39: "\x1b[C",
        51: "\x1b[D",
        52: "\x1b[D",
        53: "\x1b[D",
        66: "\x1b[C",
        67: "\x1b[C",
        68: "\x1b[C",
    }
    return "".join(keys_by_tick.get(tick, " ") for tick in range(1, 71)) + "q"


def run_once(model: str, clock: Path, stdin: str) -> float:
    command = [
        "mise",
        "run",
        model,
        "examples/breakout.thor",
        "--clock",
        str(clock),
        "--quantum",
        "50000",
    ]
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=ROOT,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
        timeout=300.0,
    )
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"{model} failed with {result.returncode}: {result.stderr[-1000:]}"
        )
    if "BREAKOUT 20x12" not in result.stdout or "QUIT" not in result.stdout:
        raise RuntimeError(f"{model} did not produce expected Breakout output")
    return elapsed


def benchmark(iterations: int) -> list[tuple[str, float, float]]:
    stdin = breakout_input()
    rows: list[tuple[str, float, float]] = []
    with tempfile.TemporaryDirectory(prefix="asgard-breakout-benchmark-") as tmp:
        clock = Path(tmp) / "clock.txt"
        clock.write_text(f"{START_MS + 7_200}\n")
        for model in MODEL_COMMANDS:
            samples = [run_once(model, clock, stdin) for _ in range(iterations)]
            rows.append((model, statistics.mean(samples), min(samples)))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark Breakout backends.")
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args(argv)
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")

    rows = benchmark(args.iterations)
    baseline = next(mean for model, mean, _ in rows if model == "thor")
    print("model,mean_seconds,best_seconds,speedup_vs_thor")
    for model, mean, best in rows:
        print(f"{model},{mean:.3f},{best:.3f},{baseline / mean:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Breakout Backend Benchmarks

`benchmark-breakout` is an end-to-end command benchmark for the terminal
Breakout example. It runs the same deterministic input stream against THOR,
Python RED2, Rust RED2, and WASM RED2: 70 input ticks using the recording's
left/right key pattern followed by `q`, with a controlled latest-value clock
file.

Unlike [`python-engine-benchmarks.md`](python-engine-benchmarks.md), this is not
a reducer/VM microbenchmark. It includes source preparation, IO action handling,
subprocess and `mise` startup, terminal output, and backend-specific host/runtime
overhead.

Run it from the repository root:

```sh
mise run benchmark-breakout --iterations 1
uv run python tools/videos/benchmark_breakout.py --iterations 1
```

## Current status after native Python RED2 IO

The historical results below are **not representative of the current Python
RED2 implementation**. On 2026-09-05, after Python RED2 gained its own native,
iterative IO action runner around `MuredMachine`, the existing command-level
benchmark no longer completed its Python RED2 sample within the benchmark's
300-second timeout.

A current diagnostic run showed:

- THOR completed the deterministic benchmark input in about **2.66 seconds** of
  wall-clock time.
- Python RED2 completed an immediate `q` Breakout smoke in about **13.32
  seconds**.
- Python RED2 did **not** complete the full 70-input benchmark within **300
  seconds**. A 30-second probe had already emitted `QUIT`, but the process had
  not exited.

That means the old table should not be interpreted as a current backend
ranking. The current behavior needs profiling before this benchmark can again
be used for Python RED2 performance comparisons. In particular, the fact that
`QUIT` is emitted before the process terminates suggests the benchmark is now
capturing substantial work beyond the visible end of the playthrough.

For a current comparison of the pure Python THOR reducer and faithful Python
RED2 VM, use:

```sh
mise run benchmark-python
```

That benchmark deliberately excludes IO, clocks, subprocess startup, and
terminal rendering and therefore measures a different, much narrower boundary.

## Historical result: 2026-09-01

Before the native RED2 IO runner, and after caching Python RED2 definition
compilation/parsing per IO run, this machine produced:

| Backend | Mean seconds | Best seconds | Speedup vs THOR |
| --- | ---: | ---: | ---: |
| THOR | 16.576 | 16.576 | 1.00x |
| Python RED2 | 1.719 | 1.719 | 9.64x |
| Rust RED2 | 1.120 | 1.120 | 14.81x |
| WASM RED2 | 0.850 | 0.850 | 19.50x |

The command output was:

```text
model,mean_seconds,best_seconds,speedup_vs_thor
thor,16.576,16.576,1.00x
red2,1.719,1.719,9.64x
rust,1.120,1.120,14.81x
wasm,0.850,0.850,19.50x
```

An even earlier run on 2026-08-29 measured Python RED2 at 157.970 seconds
versus THOR at 93.051 seconds. At that point the RED2 slowdown was dominated by
recompiling and reparsing all RED2 definitions for each pure IO sub-expression.
Caching removed that particular cost, producing the 2026-09-01 result above.

Those measurements remain useful as historical architecture checkpoints, but
they should not be compared directly with the current native-IO implementation
without first fixing or replacing the command-level benchmark path.

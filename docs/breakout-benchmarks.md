# Breakout Backend Benchmarks

Benchmarks run the same deterministic Breakout workload against each backend:
70 clock ticks, the same left/right keyboard inputs used by the recordings, and
`q` to exit. The benchmark uses a controlled latest-value clock file so backend
runtime dominates instead of wall-clock sleeping.

Run the benchmark from the repository root:

```sh
mise run benchmark-breakout --iterations 1
uv run python tools/videos/benchmark_breakout.py --iterations 1
```

Measured on this machine on 2026-09-01 after caching Python RED2 definition
compilation/parsing per IO run:

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

Before the Python RED2 IO cache, the same benchmark measured Python RED2 at
157.970s versus THOR at 93.051s on 2026-08-29. The RED2 slowdown was dominated
by repeatedly recompiling and reparsing all RED2 definitions for each pure IO
sub-expression.

Notes:

- `Python RED2` is now faster than the Python THOR reference for this Breakout
  workload because compiled and parsed RED2 definitions are reused for the whole
  IO run.
- `Rust RED2` remains faster than Python RED2, but the gap is now much smaller
  for this command-level measurement.
- `WASM RED2` is included as an additional data point; it can be faster than the
  native Rust task in this command-level measurement because task overhead,
  build cache state, and host process startup are included.

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

## Current status

As of 2026-09-05, Python RED2 Breakout works again and the deterministic
benchmark completes normally. The regression came from the native Python RED2
IO runner repeatedly rebuilding faithful μRED state for tiny pure reductions.
Two independent forms of repeated work were responsible:

1. Every pure reduction recompiled and relocated the complete static top-level
   definition environment.
2. Breakout requested 53,277 pure reductions, but only 1,623 distinct
   `(expression, quantum)` pairs occurred in the deterministic run. In other
   words, about 97% of those requests repeated an identical pure computation.

The repair keeps effects outside `MuredMachine`: static definitions are compiled
and relocated once per `run_red2_io_action(...)`, and pure faithful results are
memoized only for that IO run using `(Expr, quantum)` as the key. The cache is
not shared across runs, and every cache miss still executes through
`load_faithful_machine(...)`, `MuredMachine.run(...)`, and
`MuredMachine.result_expr()`.

Profiling before the repair showed why the regression was so severe. An
immediate-quit run made 909 pure machine loads while only about 0.33 seconds of
profiled time was spent in actual μRED execution; compilation/loading consumed
tens of seconds. A full deterministic Breakout run made 53,277 pure reductions
and previously took roughly 27-29 seconds even after static-definition caching.
Before static-definition caching it exceeded the 300-second benchmark timeout.

After both caches, the same deterministic workload completes in about 2-3
seconds on the development machine. One representative command-level sample
was:

| model | seconds | speedup vs THOR |
| --- | ---: | ---: |
| THOR | 1.529 | 1.00x |
| Python RED2 | 2.692 | 0.57x |
| Rust | 1.226 | 1.25x |
| WASM | 0.924 | 1.66x |

The exact timings vary between runs, so these are diagnostic numbers rather
than a performance contract. Python RED2 is still slower than THOR in the
current command-level benchmark, and the historical 1.719-second RED2 result
below came from an older engine architecture, so it should not be treated as a
current target without a like-for-like investigation.

The deterministic RED2 output also reaches the real quit path: the final bytes
end in `QUIT\n`. This matters because the initial help text itself contains
`Q QUITS`, so merely searching for the word `QUIT` is not sufficient evidence
that the scripted `q` was processed.

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

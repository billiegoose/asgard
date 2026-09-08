# Benchmarks

This is the canonical benchmark report for Asgard. Regenerate both result tables with:

```sh
mise run benchmark
```

The lower-level `benchmark-python` and `benchmark-breakout` tasks remain available for targeted diagnostics, but only `mise run benchmark` updates this file.

## In-process Python reducer and VM battery

This battery compares the pure Python THOR reducer with the faithful Python RED2 machine. It is conformance-first: every workload must produce the expected result on both backends before measured rows are accepted.

### Workloads

| Name | Source | Expected | What it stresses |
| --- | --- | ---: | --- |
| `tak` | `benchmarks/tak.thor` | `15` | Recursive application, nested IF, comparison, decrement, and arithmetic. |
| `list` | `benchmarks/list-build-sum.thor` | `300` | Dynamic PAIR/list allocation followed by recursive NULL?, CAR, and CDR traversal. |
| `struct` | `benchmarks/struct-build-sum.thor` | `300` | Dynamic user-defined STRUCT allocation and generated selector traversal. |
| `game` | `tests/fixtures/appendix_a/game_full.thor` | `8` | Appendix-A GAME path with lists, STRUCTs, LETREC, pruning, and minimax-style recursion. |

### Methodology

Source reading, parsing, normalization, definition preparation, and backend-specific setup happen outside the timed region. The runner performs an untimed parity preflight on THOR and RED2 before warmups or measured samples. If either backend raises, exceeds configured resources, or produces the wrong result, the benchmark command fails and `benchmarks.md` is not replaced.

For THOR, the expression and visible definitions are translated before timing; each sample times only reducer execution. For RED2, a fresh faithful machine is compiled and loaded before timing; each sample times only `MuredMachine.run()`. Result reconstruction and `to_source` rendering happen after the timer stops. Warmups follow the same execution path but are excluded from statistics. Median measured time is the primary timing statistic; best time is diagnostic.

`thor_contractions` and `mured_cycles` are backend-native work counters and are not directly comparable instruction counts. No backend is expected or required to win every workload.

### Latest Python results

Recorded `2026-09-07T19:00:08-04:00` on `Darwin x86_64` with Python `3.14.7`. Defaults: 1 warmup(s), 5 measured iteration(s), quantum 5000000, RED2 cycle limit 2000000.

| Benchmark | THOR median | RED2 median | RED2 speedup vs THOR | THOR contractions | μRED cycles |
| --- | ---: | ---: | ---: | ---: | ---: |
| tak | 21.26 ms | 4.23 ms | 5.02x | 965 | 1,299 |
| list | 431.70 ms | 152.53 ms | 2.83x | 36,249 | 38,827 |
| struct | 98.19 ms | 74.28 ms | 1.32x | 6,050 | 17,596 |
| game | 409.15 ms | 286.72 ms | 1.43x | 10,766 | 97,148 |

## End-to-end Breakout backend benchmark

This benchmark measures a materially different boundary. It drives `examples/breakout.thor` through subprocesses using a deterministic 70-tick input stream and controlled latest-value clock, followed by `q`. It includes command startup, source preparation, IO handling, terminal output, `mise` overhead, and backend-specific host/runtime costs across THOR, Python RED2, Rust RED2, and WASM RED2.

Python RED2 executes the effectful program on one persistent faithful `MuredMachine`; UART and CLOCK effects suspend and resume that same machine. The contraction quantum is a scheduler/watchdog budget and is recharged after successful host dispatch by default.

Faithful loaders default to 1,048,576 graph/environment words and 8,192 control entries. Environment allocation is currently monotonic and there is no graph/environment garbage collector, so sufficiently long-lived programs can still exhaust the arena.

The scheduler distinguishes genuine external quantum exhaustion from temporary `q = 0` states used internally during faithful IF/STRUCT reconstruction; those internal states complete normally rather than surfacing as host-visible scheduler suspensions.

### Default-capacity acceptance checks

Current regression coverage also exercises deterministic Breakout, Pong, and repeated CLOCK polling under the standard faithful arena and host-dispatch recharge policy. These checks guard the practical interactive workload envelope separately from the timing tables.

### Latest Breakout results

Recorded as part of the same `2026-09-07T19:00:08-04:00` benchmark run with 3 measured iteration(s) per backend.

| Backend | Mean | Best | Speedup vs THOR |
| --- | ---: | ---: | ---: |
| THOR | 1.458 s | 1.382 s | 1.00x |
| Python RED2 | 831.65 ms | 793.02 ms | 1.75x |
| Rust RED2 | 1.019 s | 1.006 s | 1.43x |
| WASM RED2 | 792.67 ms | 749.59 ms | 1.84x |

These end-to-end timings are diagnostic rather than a performance contract. Process startup, host load, filesystem state, and terminal/runtime overhead can move them between runs.

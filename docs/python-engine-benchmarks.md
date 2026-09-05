# Python Engine Benchmarks

Asgard includes a small in-process benchmark battery for comparing the pure Python THOR reducer with the faithful Python RED2 machine. The battery is conformance-first: every selected workload must produce the expected result on both backends before any timing rows are reported.

Run the complete battery with:

```sh
mise run benchmark-python
```

Select one workload with, for example:

```sh
mise run benchmark-python --benchmark tak --warmups 1 --iterations 5 --quantum 5000000 --cycle-limit 2000000
```

## Workloads

| Name | Source | Expected | What it stresses |
| --- | --- | ---: | --- |
| `tak` | `benchmarks/tak.thor` | `15` | Recursive application, nested `IF`, comparison, decrement, and arithmetic without list or user-STRUCT operations. |
| `list` | `benchmarks/list-build-sum.thor` | `300` | Dynamic PAIR/list allocation with `CONS`, followed by recursive `NULL?`, `CAR`, and `CDR` traversal. |
| `struct` | `benchmarks/struct-build-sum.thor` | `300` | Dynamic user-defined `STRUCT` allocation and generated selector traversal over a 24-node chain. |
| `game` | `tests/fixtures/appendix_a/game_full.thor` | `8` | The mixed Appendix-A GAME path: lists, user STRUCTs, LETREC, pruning, and minimax-style recursion. |

These are intentionally small, orthogonal workloads rather than one realistic application. That makes backend differences and correctness defects easier to localize. The STRUCT case also serves as a regression workload for the previously discovered recursive dynamic-STRUCT lifetime bug in the faithful Python RED2 model.

## Correctness and timing boundary

For each selected workload, source reading, parsing, normalization, definition preparation, and backend-specific setup happen outside the timed region.

The runner performs an untimed parity preflight on THOR and RED2 before warmups or measured samples. If either backend raises an exception, exceeds its configured resources, or produces the wrong checksum, the whole command fails and no successful partial CSV comparison is printed.

For THOR, the expression and visible definitions are translated before timing; each sample then times only the reducer executing that prepared expression. For RED2, a fresh faithful machine is compiled and loaded before timing; each sample then times only `MuredMachine.run()`. Result reconstruction and `to_source` rendering happen after the timer stops, while every warmup and measured sample is still checked for the expected result.

This intentionally measures reducer/VM execution rather than parsing, compilation/loading, or serialization overhead. Warmups exercise the same execution path but are excluded from statistics. The primary reported statistic is the median measured time.

## Breakout benchmark

This battery is separate from `mise run benchmark-breakout`. `benchmark-python` is an in-process, pure, deterministic comparison of the two Python engines and excludes runtime IO, clocks, subprocess startup, Rust, and WASM. `benchmark-breakout` is the existing command-level benchmark that drives deterministic Breakout across THOR, RED2, Rust, and WASM through subprocesses and its clock/input path. It remains useful for end-to-end backend comparisons, but it measures a materially different boundary.

<!-- benchmark-results:start -->
## Latest measured results

Recorded `2026-09-05T16:45:18-04:00` on `Darwin x86_64` with Python `3.14.7`.
Times are median reducer/VM execution times from the default run (one warmup, five measured iterations).

| Benchmark | THOR | RED2 | Speedup vs THOR |
| --- | ---: | ---: | ---: |
| tak | 20.09 ms | 13.35 ms | 1.50× |
| list | 459.86 ms | 563.78 ms | 0.82× |
| struct | 101.95 ms | 145.30 ms | 0.70× |
| game | 426.84 ms | 256.04 ms | 1.67× |
<!-- benchmark-results:end -->

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

For each selected workload, the source file is read, parsed, normalized, and split into definitions plus one expression before benchmarking. Parsing and normalization are therefore outside the timed region.

The runner performs an untimed parity preflight on THOR and RED2 before warmups or measured samples. If either backend raises an exception, exceeds its configured resources, or produces the wrong checksum, the whole command fails and no successful partial CSV comparison is printed.

A measured THOR sample includes backend-specific definition translation performed by `reduce_expr`, reduction, and rendering the result with `to_source`. A measured RED2 sample includes AST-to-μRED compilation/loading, machine execution through the explicit cycle limit, result reconstruction, and rendering with `to_source`. This quantity is best described as backend pipeline time, not only reducer-loop time.

Warmups run through the same backend path and must still produce the expected checksum, but they are excluded from statistics. The primary reported statistic is the median measured time. The best measured time is included as a diagnostic secondary statistic.

## Output and work counters

Successful output is CSV with two adjacent backend rows per workload. `speedup_vs_thor` is computed independently within each workload as THOR median divided by the backend median, so the THOR row is `1.0`. It is descriptive only: no backend is required to win any workload for the benchmark command to succeed.

The native work counters are deliberately backend-specific:

- THOR reports `thor_contractions` from `ReductionResult.steps`.
- RED2 reports `mured_cycles` from the faithful machine cycle counter.

These are different native units and must not be treated as directly comparable instruction counts. They are useful for checking deterministic work within the same backend and workload, not for comparing one THOR contraction with one μRED cycle.

## Breakout benchmark

This battery is separate from `mise run benchmark-breakout`. `benchmark-python` is an in-process, pure, deterministic comparison of the two Python engines and excludes runtime IO, clocks, subprocess startup, Rust, and WASM. `benchmark-breakout` is the existing command-level benchmark that drives deterministic Breakout across THOR, RED2, Rust, and WASM through subprocesses and its clock/input path. It remains useful for end-to-end backend comparisons, but it measures a materially different boundary.

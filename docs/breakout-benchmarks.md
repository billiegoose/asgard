# Breakout Backend Benchmarks

`benchmark-breakout` is an end-to-end command benchmark for the terminal
Breakout example. It runs the same deterministic input stream against THOR,
Python RED2, Rust RED2, and WASM RED2: 70 input ticks using the recording's
left/right key pattern followed by `q`, with a controlled latest-value clock
file.

Unlike [`python-engine-benchmarks.md`](python-engine-benchmarks.md), this is not
a reducer/VM microbenchmark. It includes source preparation, IO handling,
subprocess and `mise` startup, terminal output, and backend-specific host/runtime
overhead.

Run it from the repository root:

```sh
mise run benchmark-breakout --iterations 1
uv run python tools/videos/benchmark_breakout.py --iterations 1
```

## Current Python RED2 execution model

Python RED2 runs an effectful program on one persistent faithful `MuredMachine`.
`UART-RX`, `UART-TX`, `UART-TX-BYTES`, and `CLOCK` are machine suspension
points. When one is reached, the machine returns a host-call request; the host
performs the effect and resumes the same graph, environment, control stack, and
register state. IO continuations are not converted into fresh AST reduction
requests and no replacement machine is loaded between effects.

The contraction quantum is a scheduler/watchdog budget. The default RED2 IO
policy replenishes the configured quantum after every successful host dispatch.
If the machine genuinely exhausts its quantum before another host dispatch,
that exhaustion is surfaced unless callers explicitly enable the
`quantum-exhausted` recharge event.

Faithful loaders currently default to 1,048,576 graph/environment words and
8,192 control entries. Environment allocation is monotonic and there is not yet
a graph/environment garbage collector, so sufficiently long-running programs
can still exhaust the finite arena. The larger default is intended to make
interactive examples practical; it is not a substitute for future reclamation.

The scheduler also distinguishes genuine external quantum exhaustion from the
temporary `q = 0` states used internally by faithful `IF`/`STRUCT`
reconstruction. Those internal states must complete normally rather than being
exposed as scheduler suspensions.

## Current result

Measured on 2026-09-06 with three deterministic iterations:

| Backend | Mean seconds | Best seconds | Speedup vs THOR |
| --- | ---: | ---: | ---: |
| THOR | 1.432 | 1.408 | 1.00x |
| Python RED2 | 1.240 | 1.232 | 1.15x |
| Rust RED2 | 1.041 | 1.034 | 1.38x |
| WASM RED2 | 0.786 | 0.763 | 1.82x |

Raw command output:

```text
model,mean_seconds,best_seconds,speedup_vs_thor
thor,1.432,1.408,1.00x
red2,1.240,1.232,1.15x
rust,1.041,1.034,1.38x
wasm,0.786,0.763,1.82x
```

These timings are diagnostic rather than a performance contract. Command
startup, host load, filesystem state, and terminal/runtime overhead can move the
numbers between runs.

The deterministic RED2 run reaches the real quit path: its final output ends in
`QUIT\n`. That is stronger evidence than merely finding the word `QUIT`, since
the initial help text also contains `Q QUITS`.

## Default-capacity acceptance checks

With the current faithful defaults and the default host-dispatch recharge
policy:

- deterministic Breakout completes its scripted quit path in 194,740 μRED
  cycles and uses about 15,646 working graph/environment words;
- deterministic Pong completes its scripted quit path in 27,863 μRED cycles and
  uses about 7,163 working graph/environment words;
- `examples/clock-dots.thor` continues through repeated CLOCK polling long
  enough to emit normally under the default arena instead of failing almost
  immediately from monotonic environment growth.

Breakout and Pong therefore fit comfortably inside the default arena. Infinite
or very long-lived recursive IO programs remain bounded by the current absence
of graph/environment reclamation.

# Asgard

An executable Python specification for THOR and RED2, the reduction models
presented in Michael Lee Hilton's 1990 dissertation, *Implementation of
Declarative Languages*.

The prototype favors readable, traceable semantics over production compiler
features.  The Python THOR interpreter is the reference model; the Python RED2
machine compiles the same source expressions to a linear instruction graph and
is checked against THOR with parity tests and a small golden corpus. See
[`docs/thor-red2-prototype.md`](docs/thor-red2-prototype.md) for thesis
traceability notes and known omissions. See
[`docs/thor-primitives.md`](docs/thor-primitives.md) for the current primitive
surface and candidate future additions. See
[`docs/red2-incremental-memory-reclamation.md`](docs/red2-incremental-memory-reclamation.md)
for the current source-to-runtime account of RED2 graph/environment reclamation,
coarse residual reconstruction, and the executable Hilton C reference evidence.

## Local Setup

This project is configured for local tools only:

```sh
mise trust
mise install
uv sync
```

If `mise` is not installed yet, `uv sync` will still create/use `.venv` with a
compatible Python when possible.

For the synthesizable RED2 machine, initialize the pinned fpgatool submodule
and install the enhanced compiler:

```sh
git submodule update --init tools/fpgatool
uv sync --group fpga
python scripts/setup_pipelinec.py
```

Compiler source requirements, patch fingerprints, and overrides are documented
in [tools/pipelinec/README.md](tools/pipelinec/README.md).

The hardware top defaults to `RED2_SYN_FLOAT=0`, omitting optional floating-point
arithmetic while retaining integer division. The qualified dedicated controller
maps to **15,803 core LUTs** and ten DSPs. The complete
[Basys 3 target](scripts/boards/red2_basys3/README.md) maps to **16,752 LUTs**;
its routed image uses **16,368 physical LUT sites**, leaving **4,432 spare**.
Both clock domains pass the 10 MHz timing requirement.

The physical board passes 15 complete programs, including function application,
graph construction/access, integer arithmetic and equal/unequal nested lists,
plus lifecycle handling and the equality checkpoint. Burst replay executes
4,631,059 engine clocks and compares all 626 public output bits at 22,878 packet
endpoints. See [the current hardware evidence](docs/handoffs/red2-shared-multiplier-board-results.json).

The [live board runner](scripts/boards/red2_basys3/README.md#run-thor-on-the-board)
also compiles fresh THOR programs, executes graph reductions on the FPGA and
reads back results. For example, `((LAMBDA (x) (+ x 2)) 40)` returns `42` on the
physical board. UART/CLOCK host operations use the existing I/O adapter.
The recursive [Fibonacci example](examples/fibonacci.thor) also runs on the
physical board and returns `8` for `fib 6`.

The lowered candidate remains separate from the maintained top. Saved-JOIN list
equality is supported; direct/EP private primitive firing remains outside that
support. The board profile has finite graph/control memory. Set
`RED2_SYN_FLOAT=1` to include the existing floating-point module. The native `syn`
CLI and full native parity suite retain floating-point support by default. The
synthesis gate selects the matching profile checks.

## CLI Examples

Run one expression with the THOR reference interpreter:

```sh
uv run thor --expr "(+ 2 3)" --quantum 20
# 5
```

Run the same expression through the RED2 prototype:

```sh
uv run abs --expr "(+ 2 3)" --quantum 20
# 5
```

RED2 resource limits can be configured on Python RED2 execution paths:

```sh
uv run abs --expr "(+ 2 3)" --stack-size-in-bytes 1048576 --heap-size-in-bytes 16777216
```

The THOR interpreter currently rejects explicit resource-limit flags because its values live in Python-managed memory rather than a modeled VM heap.

Python RED2 models graph/result storage growing upward through `fsp` and environment
storage growing downward through `free_space`; logical `env` is a separate lookup
path. Ordinary contractions reclaim known-dead graph suffixes and proven-safe child
environment regions incrementally. Host checkpoints/quantum recharge are a separate
coarse residual-reconstruction mechanism and preserve the same machine and
exactly-once host-effect ordering.

The abstract and concrete Python processors also support a supervisor that runs
successive finite quanta to completion:

```sh
uv run abs --supervise --memory-words 256 --expr \
  '((Y (LAMBDA (self n) (if (= n 0) 0 (self (- n 1))))) 100)'
uv run con --supervise --memory-words 256 --expr \
  '((Y (LAMBDA (self n) (if (= n 0) 0 (self (- n 1))))) 100)'
uv run abs --supervise --quantum 5 --memory-words 256 examples/clock-dots.thor
uv run con --supervise --quantum 5 --memory-words 256 examples/clock-dots.thor
```

`--supervise` defaults to a quantum of 20; `--quantum N` changes it and
`--max-quanta N` provides an optional execution limit. The supervisor services
I/O without refilling the current quantum. On exhaustion it waits for complete
residual reconstruction, copies/relocates that residual into the problem area,
resets temporary environment/control state, and starts the next quantum on the
same processor. Static definitions and device state survive. A final result
that uses its exact budget takes one additional pass to establish completion.
Residual graphs and reconstruction workspace must still fit the selected arena;
a smaller quantum does not guarantee lower peak memory for every program.
In particular, the clock polling example uses quantum 5 because some quantum-20
boundaries require more than 256 words of temporary reconstruction space.

The Python processors preserve sharing of closed, pure scalar residual graphs
across reconstruction. Repeated references to a completed arithmetic residual
reuse its graph; when that graph later evaluates to an atom, eligible graph
roots retain the value. This extends Hilton's atomic environment sharing without
forcing arithmetic early or sharing effects, open expressions, or structures.
The original Fibonacci(30) example completes with 512 memory words at quanta
5, 20, 50, 100, and 200; it still exceeds the 256-word configuration. This
optimization has not been ported to the synthesizable processor or FPGA image.

Without `--supervise`, existing single-quantum behavior is preserved. The shared
Python scheduler is `red2.supervisor.supervise`, with `AbstractProcessor` and
`ConcreteProcessor` adapters. The concrete adapter uses its own word-level
reconstruction/restart engine; the abstract evaluator does not run on its behalf.
`run_red2_io_action(..., supervised=True)` enables the same policy for embedded
abstract I/O callers. Synthesizable/FPGA supervision is a separate integration;
these changes do not modify the qualified hardware image.

Use `mise run` as the canonical command surface for source-file examples and
project checks:

```sh
uv run thor --expr "(+ 2 3)" --quantum 20
uv run abs --expr "(+ 2 3)" --quantum 20
mise run thor examples/hangman.thor --quantum 5000
mise run abs examples/hangman.thor --quantum 5000
mise run fpga examples/clock-dots.thor
mise run parity examples/fibonacci.thor --quantum 75
mise run hdl examples/hangman.thor
mise run verify
```

`mise run fpga <file>` compiles a program for the installed standalone Basys 3
machine, programs and verifies its data flash through fpgatool, and restarts the
FPGA to load it. The program persists across power cycles. This requires the
standalone hardware to have already been flashed and its qualified build artifacts
to be available; it does not rebuild hardware. The current graph holds 256 words
and selects a program budget from the [board profiles](scripts/boards/red2_standalone/programs.toml):
20 for alphanumerics, 5 for clock-dots and Caesar, and 5 for unlisted programs.
Use `--quantum N` to override the budget, or
`--compile-only` to check a program without touching the board. See the
[standalone board guide](scripts/boards/red2_standalone/README.md) for setup and
limits.

Successful executable model tasks write simulated UART/device output to stdout
and are quiet on stderr by default. Add `--verbose` to `mise run thor`, `abs`, `con`, `syn`
`mise run parity` is diagnostic by nature and always reports parity details on
stderr.

Run a source expression containing definitions, structure declarations, and a
final expression with the Python CLIs when inspecting implementation details:

```sh
uv run thor --expr "((LAMBDA (X) X) 42)" --quantum 20
uv run abs --expr "((LAMBDA (X) X) 42)" --quantum 20
```

Compare THOR and RED2 at each contraction-prefix quantum from `0` through `N`:

```sh
mise run parity examples/fibonacci.thor --quantum 75
```

Parity comparison continues through the requested quantum even if prefixes
diverge. It reports each mismatch range with the THOR/RED2 expressions at that
range's first quantum and the range's reconvergence point, if any. It exits 0
when the final quantum matches and exits 1 when the final quantum still differs.

Run canonical UART examples through the task surface:

```sh
mise run thor examples/uart-alphanumerics.thor
mise run abs examples/uart-caesar-plus4.thor
```

Watch the Python RED2 Breakout recording:

[![Asgard Breakout asciicast](https://asciinema.org/a/ZA2OrmB0Mc9aAdfq.svg)](https://asciinema.org/a/ZA2OrmB0Mc9aAdfq)

Run terminal Breakout with a controlled latest-value clock source:

```sh
mise run thor examples/breakout.thor --clock /tmp/asgard-clock
mise run abs examples/breakout.thor --clock /tmp/asgard-clock
mise run abs examples/pong.thor --clock /tmp/asgard-clock
```

The `--clock` file is newline-delimited millisecond timestamps; the runtime uses
the latest valid value and ignores malformed lines. Without `--clock`, runners
that support `CLOCK` use the host system clock.

## Useful Commands

Use the task surface for normal runs:

```sh
mise run thor examples/hangman.thor --quantum 5000
mise run abs examples/hangman.thor --quantum 5000
mise run parity examples/fibonacci.thor --quantum 75
mise run hdl examples/hangman.thor
mise run verify
```

```sh
uv run thor --help
uv run abs --help
```

## Prototype Scope

- `src/lib/thor/` defines the backend-independent THOR language: AST nodes,
  parsing, pretty-printing, normalization, primitives, and version metadata.
- `src/lib/red2/` defines shared RED2 vocabulary and compilation: live graph
  words/opcodes, compiler-image instructions, and THOR-to-RED2 compilation.
- `src/machines/thor_interpreter/` implements direct THOR execution, golden/parity
  helpers, IO runtime, lockstep comparison, and the `thor` CLI.
- `src/machines/abstract_red2_machine/` implements the faithful Abstract RED2
  Machine, its loader/IO runtime, and the `abs` CLI.
- `src/machines/concrete_red2_machine/` implements the bounded fixed-width Python
  architectural machine, RED2 hardware ABI/codec, lockstep oracle, and `con` CLI.
- `src/machines/synthesizable_red2_machine/` contains the synthesizable
  Pypeline/PipelineC machine used by the `syn` simulator and synthesis gate.
  It can execute recursive, closure-using, primitive-using pure THOR programs
  through at least `examples/fibonacci.thor` entirely on the Synthesizable RED2
  state machine (`fib 6` => `8`). This is a milestone rather than a claim of
  complete RED2 hardware semantics: quantum-exhaustion recharge/resume,
  host-call `CMD_RESUME`, and remaining explicitly unimplemented semantic paths
  are still outside that proven boundary, so `RED2_SYNTH_SEMANTICS_COMPLETE`
  remains `0`.
- `tools/vscode-thor/` contains the local VS Code-compatible THOR syntax
  extension.

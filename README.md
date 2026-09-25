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

Use `mise run` as the canonical command surface for source-file examples and
project checks:

```sh
uv run thor --expr "(+ 2 3)" --quantum 20
uv run abs --expr "(+ 2 3)" --quantum 20
mise run thor examples/hangman.thor --quantum 5000
mise run abs examples/hangman.thor --quantum 5000
mise run parity examples/fibonacci.thor --quantum 75
mise run hdl examples/hangman.thor
mise run verify
```

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
- `tools/vscode-thor/` contains the local VS Code-compatible THOR syntax
  extension.

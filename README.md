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
[`docs/red2-bytecode.md`](docs/red2-bytecode.md) for the serializable `.red2`
bytecode format.

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
uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)"
# 5
```

Run the same expression through the RED2 prototype:

```sh
uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"
# 5
```

Use `mise run` as the canonical command surface for source-file examples and
project checks:

```sh
uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)"
uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"
mise run thor examples/hangman.thor --quantum 5000
mise run red2 examples/hangman.thor --quantum 5000
mise run parity examples/fibonacci.thor --quantum 75
printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000
printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000
mise run hdl examples/hangman.thor
mise run verify
```

Successful executable model tasks write simulated UART/device output to stdout
and are quiet on stderr by default. Add `--verbose` to `mise run thor`, `red2`,
`rust`, or `wasm` when diagnostic output such as final IO results is needed.
`mise run parity` is diagnostic by nature and always reports parity details on
stderr.

Run a source file containing definitions, structure declarations, and expression
forms with the Python CLI when inspecting implementation details:

```sh
uv run thor-spec --file tests/golden/thor_examples.thor
uv run thor-spec --model red2 --trace --expr "((LAMBDA (X) X) 42)"
```

Compare THOR and RED2 at each contraction-prefix quantum from `0` through `N`:

```sh
mise run parity examples/fibonacci.thor --quantum 75
uv run thor-spec --model parity --quantum 10 --expr "((LAMBDA (X) X) 42)"
```

`--model parity` continues through the requested quantum even if prefixes
diverge. It reports each mismatch range with the THOR/RED2 expressions at that
range's first quantum and the range's reconvergence point, if any. It exits 0
when the final quantum matches and exits 1 when the final quantum still differs.

Run canonical UART examples through the task surface:

```sh
mise run thor examples/uart-alphanumerics.thor
mise run red2 examples/uart-caesar-plus4.thor
printf 'abcXYZ!\033' | mise run rust examples/uart-caesar-plus4.thor
printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000
```

Watch the Breakout recording:

[![Asgard Breakout asciicast](https://asciinema.org/a/oaQSOF9foLO34D6v.svg)](https://asciinema.org/a/oaQSOF9foLO34D6v)

Run terminal Breakout with a controlled latest-value clock source:

```sh
mise run thor examples/breakout.thor --clock /tmp/asgard-clock
mise run red2 examples/breakout.thor --clock /tmp/asgard-clock
```

The `--clock` file is newline-delimited millisecond timestamps; the runtime uses
the latest valid value and ignores malformed lines. Rust/Wasm CLOCK support is
deferred.

`--trace` writes deterministic metadata to stderr; stdout remains result-only so
it can be compared directly in scripts outside task-managed UART examples.

## Useful Commands

Use the task surface for normal runs:

```sh
mise run thor examples/hangman.thor --quantum 5000
mise run red2 examples/hangman.thor --quantum 5000
mise run parity examples/fibonacci.thor --quantum 75
printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000
printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000
mise run hdl examples/hangman.thor
mise run verify
```

Lower-level bytecode commands remain useful when inspecting the `.red2` format
or debugging an executor directly:

```sh
uv run thor-spec --help
uv run thor-spec compile-red2 --expr "(+ 2 3)" --output /tmp/add.red2
uv run thor-spec run-red2 --bytecode /tmp/add.red2 --quantum 20
cargo run -p red2-wasm -- /tmp/add.red2 --quantum 20
cargo build -p red2-wasm --target wasm32-wasi
wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/add.red2 --quantum 20
```

## Prototype Scope

- `models/python/thor_spec/parser.py`, `pretty.py`, and `semantics.py`
  implement the THOR source syntax and Chapter 3-style abstract interpreter
  used as the executable reference.
- `models/python/thor_spec/red2/` contains the RED2 instruction contract,
  compiler, Python machine, and result decompiler used for parity checks.
- `models/python/thor_spec/golden.py` provides `run_source(...)`, the shared
  CLI/golden corpus harness for comparing THOR and RED2 behavior.
- `models/python/pypeline_red2/` contains a fixed-width RED2 stepper artifact
  for hardware-oriented exploration; the default test suite does not require
  FPGA vendor tools.
- `models/rust-red2/` contains the native/WASI Rust RED2 bytecode executor.
- `tools/vscode-thor/` contains the local VS Code-compatible THOR syntax
  extension.

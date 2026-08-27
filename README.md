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

Run a source file containing definitions, structure declarations, and expression
forms:

```sh
uv run thor-spec --file tests/golden/thor_examples.thor
uv run thor-spec --model red2 --trace --expr "((LAMBDA (X) X) 42)"
```

Compare THOR and RED2 at each contraction-prefix quantum from `0` through `N`:

```sh
uv run thor-spec --model parity --quantum 10 --expr "((LAMBDA (X) X) 42)"
```

`--model parity` continues through the requested quantum even if prefixes
diverge. It reports each mismatch range with the THOR/RED2 expressions at that
range's first quantum and the range's reconvergence point, if any. It exits 0
when the final quantum matches and exits 1 when the final quantum still differs.

Run the final expression as a simulated IO action, with UART bytes on stdout and
diagnostics on stderr:

```sh
printf A | uv run thor-spec --io --model thor \
  --expr "(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))"
# stdout: A
# stderr: io result: NIL

uv run thor-spec --io --model thor --file examples/uart-alphanumerics.thor
uv run thor-spec --io --model thor --file examples/uart-caesar-plus4.thor
uv run thor-spec --io --model thor --file examples/hangman.thor
```

Run interactive UART examples on the Rust RED2 VM, keeping stdout reserved for
UART bytes:

```sh
uv run thor-spec compile-red2 --file examples/uart-caesar-plus4.thor --output /tmp/caesar.red2
printf 'abcXYZ!\033' | cargo run -p red2-wasm --quiet -- /tmp/caesar.red2 --io
# stdout: efgBCD!
# stderr: io result: NIL

uv run thor-spec compile-red2 --file examples/hangman.thor --output /tmp/hangman.red2
printf 'ASGRD' | cargo run -p red2-wasm --quiet -- /tmp/hangman.red2 --io --quantum 1000
# stdout includes: WIN
# stderr: io result: NIL
```

`--trace` writes deterministic metadata to stderr; stdout remains result-only so
it can be compared directly in scripts outside IO mode, and remains UART-only in
IO mode.

## Useful Commands

```sh
uv run thor-spec --help
uv run thor-spec compile-red2 --expr "(+ 2 3)" --output /tmp/add.red2
uv run thor-spec run-red2 --bytecode /tmp/add.red2 --quantum 20
cargo run -p red2-wasm -- /tmp/add.red2 --quantum 20
cargo build -p red2-wasm --target wasm32-wasi
wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/add.red2 --quantum 20
uv run thor-spec compile-red2 --file examples/uart-caesar-plus4.thor --output /tmp/caesar.red2
printf 'abcXYZ!\033' | cargo run -p red2-wasm --quiet -- /tmp/caesar.red2 --io
uv run thor-spec compile-red2 --file examples/hangman.thor --output /tmp/hangman.red2
printf 'ASGRD' | cargo run -p red2-wasm --quiet -- /tmp/hangman.red2 --io --quantum 1000
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## Prototype Scope

- `src/thor_spec/parser.py`, `pretty.py`, and `semantics.py` implement the THOR
  source syntax and Chapter 3-style abstract interpreter used as the executable
  reference.
- `src/thor_spec/red2/` contains the RED2 instruction contract, compiler, Python
  machine, and result decompiler used for parity checks.
- `src/thor_spec/golden.py` provides `run_source(...)`, the shared CLI/golden
  corpus harness for comparing THOR and RED2 behavior.
- `pypeline_red2/` contains a fixed-width RED2 stepper artifact for
  hardware-oriented exploration; the default test suite does not require FPGA
  vendor tools.

# RED2 Bytecode Format

This document defines the first serializable `.red2` bytecode container used by
Asgard's Python RED2 compiler and machine. The format is intentionally simple so
a future Rust RED2 VM can read it and compile to WASM before any FPGA flash image
is attempted.

## Status

Version 2 stores a self-contained RED2 bundle: one entry `ProgramImage`, zero or
more named top-level definition images, a deterministic file-local literal
table, per-program metadata for debugging/decompilation, and a CRC32 checksum.

It is an interchange format for simulators and VM work. It is not yet a final
FPGA memory-map or flash partition format.

## CLI

Compile THOR source to `.red2`:

```sh
uv run compile --expr "(+ 2 3)" --output /tmp/add.red2
```

Run a `.red2` image with the Rust RED2 VM:

```sh
cargo run -p red2-wasm -- /tmp/add.red2 --quantum 20
```

The compiler command serializes the final expression and bundles top-level THOR
definitions from the same source file/expression into the bytecode container.

## Container Layout

All integer fields are little-endian.

```text
magic       4 bytes   ASCII "RED2"
version     u16       1
flags       u16       reserved, currently 0
entry_index u32       program-table index of the entry image
prog_count  u32       number of program records
lit_count   u32       number of literal table records
meta_count  u32       reserved global metadata count, currently 0
meta_size   u32       reserved global metadata byte length, currently 0
reserved    8 bytes   zeroed
programs    prog_count program records
literals    lit_count literal records
checksum    u32       CRC32 of all preceding bytes
```

## Program Records

Each program record begins with:

```text
name        u32       string literal table index, or 0xffffffff for anonymous entry
entry       u32       entry instruction index within this program
word_count  u32       number of instruction records in this program
meta_count  u32       number of metadata records for this program
words       word_count instruction records
metadata    meta_count metadata records
```

## Instruction Records

Each instruction record is 8 bytes:

```text
opcode      u8
flags       u8        bit 0 = head flag
kind        u16       data kind
data        u32       immediate or literal table index
```

Data kinds:

- `0` — signed integer immediate stored in `data`.
- `1` — string literal table index.
- `2` — float literal table index.
- `3` — no data.

This record shape is deliberately close to the existing 32-bit RED2 word model
while allowing deterministic string/float payloads in a file-local table.

## Literal Records

Each literal record begins with:

```text
kind        u8
length      u32
payload     length bytes
```

Literal kinds:

- `1` — UTF-8 string.
- `2` — IEEE-754 float64, little-endian, length 8.

## Metadata Records

Metadata records preserve information needed by decompilation/debugging, such as
lambda arities and `LETREC` binding names.

```text
key_len     u16
value_count u16
key         key_len UTF-8 bytes
values      repeated value_count times:
  len       u16
  payload   len UTF-8 bytes
```

## Rust/WASM VM

The `models/rust-red2/` crate is the first non-Python executor for `.red2`
bytecode. It supports literals, bundled top-level definitions, simple
application, strict integer arithmetic/comparison primitives, structures needed
for PAIR/list values, lambda/beta cases, and simulator UART/CLOCK IO actions.

For day-to-day source-file runs, use the canonical `mise run` task surface. The
Rust and Wasm tasks compile a temporary `.red2` bundle and then execute it with
the native or Wasmtime RED2 VM:

```sh
mise run rust examples/uart-caesar-plus4.thor
mise run wasm examples/uart-caesar-plus4.thor
printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000
printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000
mise run rust examples/breakout.thor --clock /tmp/asgard-clock --quantum 12000
mise run wasm examples/breakout.thor --clock /tmp/asgard-clock --quantum 12000
```

Successful model tasks reserve stdout for simulated UART/device output and are
quiet on stderr by default. Add `--verbose` to `mise run rust` or
`mise run wasm` when diagnostics such as `io result: NIL` are needed.

Lower-level commands are useful when inspecting the `.red2` format or debugging
an executor against a precompiled bytecode bundle:

```sh
uv run compile --expr "(+ 2 3)" --output /tmp/add.red2
cargo run -p red2-wasm -- /tmp/add.red2 --quantum 20
cargo run -p red2-wasm -- /tmp/breakout.red2 --quantum 12000 --clock /tmp/asgard-clock
```

WASI/Wasmtime direct execution also operates on an existing `.red2` bundle:

```sh
rustup target add wasm32-wasi
cargo build -p red2-wasm --target wasm32-wasi
wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/add.red2 --quantum 20
wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/breakout.red2 --quantum 12000 --clock /tmp/asgard-clock
```

Wasmtime requires `--dir /tmp` or another preopened directory to grant the WASI
module access to `.red2` files.

Next VM milestones:

1. Expand Rust VM coverage for `Y`, `LETREC`, and non-PAIR structure behavior.
2. Add remaining simulator device IO such as LED diagnostics where useful.
3. Define a flash-oriented image layout for FPGA boards.

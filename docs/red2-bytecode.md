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
uv run thor-spec compile-red2 --expr "(+ 2 3)" --output /tmp/add.red2
```

Run a `.red2` image with the Python RED2 VM:

```sh
uv run thor-spec run-red2 --bytecode /tmp/add.red2 --quantum 20
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

The `red2-wasm/` crate is the first non-Python executor for `.red2` bytecode. It
currently supports a definition-free subset: literals, simple application,
strict integer arithmetic/comparison primitives, and simple lambda/beta cases.
It writes VM result diagnostics to stderr and reserves stdout for future
UART/device IO.

Native run:

```sh
uv run thor-spec compile-red2 --expr "(+ 2 3)" --output /tmp/add.red2
cargo run -p red2-wasm -- /tmp/add.red2 --quantum 20
```

WASI/Wasmtime run:

```sh
rustup target add wasm32-wasi
cargo build -p red2-wasm --target wasm32-wasi
wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/add.red2 --quantum 20
```

Wasmtime requires `--dir /tmp` or another preopened directory to grant the WASI
module access to `.red2` files.

Run the UART Caesar cipher with the native Rust VM:

```sh
uv run thor-spec compile-red2 --file examples/uart-caesar-plus4.thor --output /tmp/caesar.red2
printf 'abcXYZ!\033' | cargo run -p red2-wasm --quiet -- /tmp/caesar.red2 --io
```

Run the same bytecode under Wasmtime:

```sh
cargo build -p red2-wasm --target wasm32-wasi
printf 'abcXYZ!\033' | wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/caesar.red2 --io
```

Hangman currently targets the Python THOR/RED2 IO runtimes while Rust work is
paused:

```sh
printf 'A\nS\nG\nR\nD\n' | uv run thor-spec --io --model red2 --file examples/hangman.thor --quantum 2000
```

In IO mode, stdout is the simulated UART byte stream (`efgBCD!` for the Caesar
example above, or rendered game text for Hangman). Final IO diagnostics such as
`io result: NIL` are written to stderr.

Next VM milestones:

1. Bundle top-level definition images into the `.red2` container.
2. Expand Rust VM coverage for structures, `IF`, `Y`, and `LETREC`.
3. Add simulator UART/LED IO to the Rust/WASM VM while keeping stdout reserved
   for UART bytes.
4. Define a flash-oriented image layout for FPGA boards.

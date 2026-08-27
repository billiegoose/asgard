# Rust RED2 Caesar VM Design

## Goal

Expand the Rust/WASM RED2 bytecode interpreter until it can run the simulated UART Caesar cipher from a top-level `examples/` directory, with stdout reserved for UART bytes and diagnostics/final IO state on stderr.

## User Requirements

- Move THOR examples out of `vscode-thor/examples/` into a top-level `examples/` directory.
- Use a clean `.red2` v2 container for bundled definitions; strict versioning/backward compatibility is not important while the project is semantically pre-1.0.
- Implement iteratively: subset, test, then expand.
- Get to running the Caesar cipher in the Rust VM.
- Preserve the stdout policy: stdout is for simulated IO/UART bytes, not final expression printing.
- Target Wasmtime for the WASM path.

## Architecture

The Python compiler remains the source of truth for parsing and lowering THOR source to RED2 bytecode. The `.red2` binary codec will be bumped to v2 and changed from a single `ProgramImage` container into an image bundle containing one entry program and zero or more named top-level definition programs. Each program keeps its own instruction stream and metadata, but all string/float literals live in a deterministic file-level literal table.

The Rust crate will mirror that v2 bundle shape. Its VM will evaluate the entry program, resolve `SYM` references through the bundled definition map, and reduce the subset needed by the Caesar example: top-level recursion, lambdas, integer primitives, boolean control primitives (`IF`, `AND`, `OR`), and simulated IO actions.

The Rust CLI will gain `--io`. In non-IO mode, the final result diagnostic remains on stderr. In IO mode, stdout contains only bytes emitted by `UART-TX`; stderr contains final diagnostics such as `io result: NIL`.

## Components

### Top-level examples

Create `examples/` and move/copy existing THOR examples there:

- `examples/appendix-a-sample.thor`
- `examples/fibonacci.thor`
- `examples/uart-alphanumerics.thor`
- `examples/uart-caesar-plus4.thor`

Update README, CLI comments, and tests to use these top-level paths. The VS Code extension can still ship syntax assets, but it should not be treated as the canonical example location.

### Python `.red2` v2 bundle codec

Update `src/thor_spec/red2/binary.py` with public functions:

- `encode_program_image(image: ProgramImage) -> bytes`
- `decode_program_image(data: bytes) -> ProgramImage`
- `encode_bundle(entry: ProgramImage, definitions: DefinitionImage | None = None) -> bytes`
- `decode_bundle(data: bytes) -> Red2Bundle`

`encode_program_image` and `decode_program_image` become compatibility wrappers around single-entry v2 bundles to keep current callers simple.

The v2 file layout is:

```text
magic       4 bytes   ASCII "RED2"
version     u16       2
flags       u16       reserved, 0
entry_index u32       program-table index of entry image
prog_count  u32       number of program records
lit_count   u32       number of literal table records
meta_count  u32       number of metadata records
meta_size   u32       encoded metadata byte length
reserved    8 bytes   zeroed
programs    repeated program records
literals    repeated literal records
metadata    repeated global metadata records
checksum    u32       CRC32 of all preceding bytes
```

Each program record contains a name literal index (`u32`, `0xffffffff` for anonymous entry), entry pc, instruction count, metadata count, instruction records, and metadata records. Instruction/literal/metadata record formats stay the same as the existing v1 format where possible.

### Rust bytecode reader

Update `red2-wasm/src/bytecode.rs` to decode version 2 bundle images into:

- `ProgramBundle { entry_index, programs, definitions }`
- `Program { name, entry, instructions, metadata }`

The parser validates magic, version, section lengths, literal indexes, and CRC32 before VM execution.

### Rust VM expansion

Update `red2-wasm/src/vm.rs` to run against a bundle. The reducer will:

- Parse the entry program and bundled definitions into expression terms.
- Resolve `SYM` names through definitions.
- Preserve lazy closure behavior for lambdas/recursive definition calls enough for the Caesar loop.
- Implement integer primitives: `+`, `-`, `*`, `/`, `MOD`, `<`, `>`, `<=`, `>=`, `=`, `1-`.
- Implement `IF`, `AND`, `OR` non-strictly.
- Implement IO action execution for `IO-RETURN`, `IO-BIND`, `IO-THEN`, `UART-RX`, `UART-TX`.

### Wasmtime

Keep the crate buildable as WASI:

```sh
cargo build -p red2-wasm --target wasm32-wasi
wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/caesar.red2 --io
```

Wasmtime requires a preopened directory for bytecode file access.

## Testing Strategy

Follow TDD by adding failing tests before each implementation increment.

Python tests:

- v2 bytecode starts with version 2.
- v2 bytecode round-trips a bundle with top-level definitions.
- `compile-red2 --file examples/uart-caesar-plus4.thor` produces a bundled bytecode file.
- Rust CLI native Caesar smoke: stdin `abcXYZ!\x1b`, stdout `efgBCD!`, stderr contains `io result: NIL`.

Rust tests:

- Decode v2 single-entry image.
- Decode v2 bundle with a named definition.
- Execute definition lookup.
- Execute `IF`/comparisons.
- Execute one UART TX action without printing result to stdout.

Final gates:

- `cargo test -p red2-wasm`
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy src tests`
- Native Caesar smoke
- Wasmtime Caesar smoke

## Error Handling

Python and Rust bytecode decoders report bad magic, unsupported version, bad checksum, truncated sections, invalid UTF-8, invalid literal indexes, and unsupported VM operations as explicit errors.

Rust CLI exits 2 for decode/VM/argument errors and writes diagnostics to stderr.

## Non-Goals

- Full Chapter 4 machine fidelity in Rust.
- FPGA memory map or flash partition format.
- Browser JS bindings beyond WASI/Wasmtime CLI execution.
- Backward compatibility with v1 files beyond the tests that are updated to v2.

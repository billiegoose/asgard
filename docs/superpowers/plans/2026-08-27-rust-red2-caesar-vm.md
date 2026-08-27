# Rust RED2 Caesar VM Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Rust/WASM RED2 interpreter until it can run the UART Caesar cipher from top-level examples.

**Architecture:** Move THOR examples to `examples/`, bump `.red2` to a clean v2 bundle format with top-level definitions, mirror that bundle in Rust, then grow the Rust VM through definition lookup, control primitives, recursion, and IO. Rust CLI stdout remains reserved for UART bytes; result diagnostics go to stderr.

**Tech Stack:** Python 3.14, Rust 1.75, Cargo, WASI `wasm32-wasi`, Wasmtime 17, pytest, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-08-27-rust-red2-caesar-vm-design.md`

## Global Constraints

- Use a clean `.red2` v2 container; backward compatibility with v1 is not required.
- Implement iteratively: write failing tests, observe failure, implement minimal code, verify green, then continue.
- Do not print final VM expression results to stdout; stdout is reserved for simulated UART/device IO bytes.
- Rust CLI diagnostics and final IO result go to stderr.
- Wasmtime execution targets WASI via `wasm32-wasi` and requires preopened bytecode directories.
- Keep Python gates green: `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests`.
- Keep Rust gates green: `cargo test -p red2-wasm`.

**Acceptance:** suite — native and Wasmtime Rust VM run `examples/uart-caesar-plus4.thor` compiled to `.red2`, transforming stdin `abcXYZ!\x1b` to stdout `efgBCD!` and reporting `io result: NIL` on stderr.

---

### Task 1: Move canonical THOR examples top-level

**Type:** implementation
**Depends-on:** none
**Review:** lean

**Files:**
- Create: `examples/appendix-a-sample.thor`
- Create: `examples/fibonacci.thor`
- Create: `examples/uart-alphanumerics.thor`
- Create: `examples/uart-caesar-plus4.thor`
- Modify: `README.md`
- Modify: `vscode-thor/README.md`
- Modify: `tests/test_vscode_thor_extension.py`
- Modify: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: existing examples under `vscode-thor/examples/`
- Produces: canonical top-level `examples/*.thor` paths used by docs and tests

**Parallelization rationale:** Example relocation is independent of bytecode and VM internals; it only changes filesystem paths and documentation.

- [ ] Write failing docs/examples tests that assert `examples/uart-caesar-plus4.thor` exists and README mentions top-level `examples/` instead of canonical `vscode-thor/examples/` usage.
- [ ] Move or copy existing example source files to `examples/`.
- [ ] Update comments/docs/tests to refer to top-level example paths.
- [ ] Run `uv run pytest tests/test_docs_examples.py tests/test_vscode_thor_extension.py -v`.

---

### Task 2: Python `.red2` v2 bundle codec and compile CLI

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `src/thor_spec/red2/binary.py`
- Modify: `src/thor_spec/cli.py`
- Modify: `docs/red2-bytecode.md`
- Modify: `tests/test_red2_binary.py`
- Modify: `tests/test_cli_models.py`

**Interfaces:**
- Consumes: `ProgramImage`, `DefinitionImage`, `compile_expr`, `compile_definitions`, normalized parsed THOR programs
- Produces: `Red2Bundle`, `encode_bundle(entry: ProgramImage, definitions: DefinitionImage | None = None) -> bytes`, `decode_bundle(data: bytes) -> Red2Bundle`; `compile-red2 --file` writes a bundled v2 image containing top-level definitions and the final expression

**Parallelization rationale:** The v2 Python codec defines the binary contract for the Rust reader, but can be implemented and tested independently from Rust once the spec is fixed.

- [ ] Add failing test `test_red2_binary_starts_with_magic_and_version_2` expecting bytes `b"\x02\x00"` at offset 4.
- [ ] Add failing test that encodes a bundle with `inc == (lambda (x) (+ x 1))` and final `(inc 41)`, decodes it with `decode_bundle`, then runs `Red2Machine(decoded.entry, definitions=decoded.definitions)` to get `42`.
- [ ] Add failing CLI test that `compile-red2 --file examples/uart-caesar-plus4.thor` writes a v2 bytecode file with bundled definitions.
- [ ] Implement `Red2Bundle` and v2 program-record/literal/metadata encoding.
- [ ] Update `encode_program_image`/`decode_program_image` as single-entry v2 wrappers.
- [ ] Update CLI `_compile_red2_command` to parse the full program, compile definitions, and encode a bundle for `--file` and multi-form `--expr`.
- [ ] Update bytecode docs with the v2 layout.
- [ ] Run `uv run pytest tests/test_red2_binary.py tests/test_cli_models.py -v`.

---

### Task 3: Rust v2 bundle parser and definition lookup subset

**Type:** implementation
**Depends-on:** 2
**Review:** adversarial

**Files:**
- Modify: `red2-wasm/src/bytecode.rs`
- Modify: `red2-wasm/src/vm.rs`
- Modify: `red2-wasm/src/lib.rs`
- Modify: `red2-wasm/src/main.rs`
- Modify: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: v2 `.red2` files from Task 2
- Produces: Rust `ProgramBundle` decode and VM symbol lookup for bundled definitions, enough for `inc == ...; (inc 41)`

**Parallelization rationale:** Rust reader/definition lookup depends on the v2 binary contract but not on IO behavior.

- [ ] Add failing Rust tests for v2 version parsing and bundled named definition parsing.
- [ ] Add failing pytest integration that compiles `inc == (lambda (x) (+ x 1)); (inc 41)` to `.red2` and expects the Rust CLI stderr to contain `red2 result: 42` with empty stdout.
- [ ] Implement v2 bundle parser in Rust.
- [ ] Update VM entry point to run `ProgramBundle` and resolve `SYM` through the bundle definition map.
- [ ] Run `cargo test -p red2-wasm` and `uv run pytest tests/test_red2_wasm_cli.py -v`.

---

### Task 4: Rust control primitives and recursion subset

**Type:** implementation
**Depends-on:** 3
**Review:** adversarial

**Files:**
- Modify: `red2-wasm/src/vm.rs`
- Modify: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: Rust bundle VM with definition lookup
- Produces: support for `IF`, `AND`, `OR`, `1-`, comparisons, and recursive top-level calls enough for bounded loop-style programs

**Parallelization rationale:** Control/recursion builds on definition lookup but is independent of device IO once expressions can reduce.

- [ ] Add failing pytest for Rust CLI running `choose == (lambda (x) (if (AND (>= x 65) (<= x 90)) (+ x 4) x)); (choose 65)` and returning `69` on stderr only.
- [ ] Add failing pytest for a recursive countdown definition that terminates at zero.
- [ ] Implement non-strict `IF`, `AND`, and `OR` in Rust reducer.
- [ ] Implement unary `1-` and any missing integer primitives needed by tests.
- [ ] Make top-level recursive symbol resolution work by evaluating definitions by name without consuming them destructively.
- [ ] Run `cargo test -p red2-wasm` and `uv run pytest tests/test_red2_wasm_cli.py -v`.

---

### Task 5: Rust IO action runtime and Caesar native/Wasmtime smokes

**Type:** implementation
**Depends-on:** 1, 4
**Review:** adversarial

**Files:**
- Modify: `red2-wasm/src/vm.rs`
- Modify: `red2-wasm/src/main.rs`
- Modify: `docs/red2-bytecode.md`
- Modify: `README.md`
- Modify: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: Rust VM with bundled definitions, control primitives, and recursion
- Produces: `--io` CLI mode implementing `IO-RETURN`, `IO-BIND`, `IO-THEN`, `UART-RX`, `UART-TX`; Caesar cipher works natively and under Wasmtime with stdout as UART bytes

**Parallelization rationale:** IO action handling depends on control/recursion and top-level examples, then provides the final end-to-end behavior.

- [ ] Add failing pytest that compiles `examples/uart-caesar-plus4.thor`, runs native Rust CLI with `--io`, input `abcXYZ!\x1b`, and asserts stdout `efgBCD!` and stderr contains `io result: NIL`.
- [ ] Add optional failing pytest or documented smoke for Wasmtime Caesar if `wasmtime` and `wasm32-wasi` are available.
- [ ] Implement `--io` argument parsing in Rust CLI.
- [ ] Implement Rust IO action evaluator with stdin byte reads and stdout byte writes.
- [ ] Ensure non-IO result diagnostics remain stderr-only.
- [ ] Update README and bytecode docs with Caesar native and Wasmtime commands.
- [ ] Run final verification commands.

## Operator smoke

- do: `uv run thor-spec compile-red2 --file examples/uart-caesar-plus4.thor --output /tmp/caesar.red2`
- see: stderr contains `wrote RED2 bytecode: /tmp/caesar.red2`.

- do: `printf 'abcXYZ!\033' | cargo run -p red2-wasm --quiet -- /tmp/caesar.red2 --io > /tmp/caesar.out 2> /tmp/caesar.err; cat /tmp/caesar.out; cat /tmp/caesar.err`
- see: stdout file contains `efgBCD!`; stderr contains `io result: NIL`.

- do: `cargo build -p red2-wasm --target wasm32-wasi && printf 'abcXYZ!\033' | wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/caesar.red2 --io > /tmp/caesar-wasm.out 2> /tmp/caesar-wasm.err`
- see: stdout file contains `efgBCD!`; stderr contains `io result: NIL`.

- do: `uv run pytest && uv run ruff check . && uv run mypy src tests && cargo test -p red2-wasm`
- see: all gates pass.

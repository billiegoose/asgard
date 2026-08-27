# Rust RED2 WASM VM Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an iterative Rust RED2 `.red2` bytecode interpreter with a native CLI and a path to Wasmtime execution.

**Architecture:** Add a `red2-wasm` Rust crate that first parses the `.red2` v1 container, then executes a small definition-free expression subset, then expands to lambda/beta and primitive operations. The CLI writes VM result diagnostics to stderr and keeps stdout reserved for future UART/device IO.

**Tech Stack:** Rust 1.75, Cargo, Python-generated `.red2` fixtures, pytest host tests, Wasmtime roadmap.

**Spec:** User requested a Rust/WASM `.red2` interpreter targeting Wasmtime, implemented iteratively in subsets, with stdout reserved for IO instead of final expression printing.

## Global Constraints

- Do not print final VM expression results to stdout; stdout is reserved for future UART/device IO.
- Native Rust CLI result diagnostics go to stderr.
- Start with a subset and expand only after tests pass.
- Use `.red2` v1 files produced by Python `thor-spec compile-red2`.
- Keep Python gates green: `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests`.
- Keep Rust gates green: `cargo test` and `cargo run` smokes.

**Acceptance:** suite — committed Python tests and Rust tests cover bytecode parsing, subset execution, CLI stderr/stdout policy, and docs.

---

### Task 1: Rust crate and bytecode parser

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `Cargo.toml`
- Create: `red2-wasm/Cargo.toml`
- Create: `red2-wasm/src/lib.rs`
- Create: `red2-wasm/src/bytecode.rs`
- Create: `red2-wasm/src/main.rs`
- Test: `red2-wasm/src/bytecode.rs`

**Interfaces:**
- Consumes: `.red2` v1 format documented in `docs/red2-bytecode.md`
- Produces: `Program::decode(bytes: &[u8]) -> Result<Program, Red2Error>` and native CLI that validates a bytecode file

**Parallelization rationale:** Parser is the foundation for VM execution and can be tested independently.

- [ ] Write failing Rust unit tests for bad magic, bad checksum, and parsing a generated `(+ 2 3)` bytecode fixture.
- [ ] Implement deterministic little-endian parser and CRC32 validation.
- [ ] Add minimal CLI that reads a `.red2` file and reports parsed instruction count to stderr.
- [ ] Verify `cargo test -p red2-wasm` passes.

---

### Task 2: Literal/primitive subset VM

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Create: `red2-wasm/src/vm.rs`
- Modify: `red2-wasm/src/lib.rs`
- Modify: `red2-wasm/src/main.rs`
- Test: `red2-wasm/src/vm.rs`
- Test: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: `Program` from Task 1
- Produces: `run(program: &Program, quantum: u32) -> Result<Value, Red2Error>` for literals and strict primitive applications such as `(+ 2 3)`, `(<= 3 3)`, `(MOD 29 26)`

- [ ] Write failing Rust VM tests using generated `.red2` fixtures.
- [ ] Implement AST/term decompilation from the linear bytecode subset and strict primitive firing.
- [ ] Update CLI to run the VM and print `red2 result: <expr>` to stderr only.
- [ ] Add Python subprocess test asserting stdout is empty and stderr contains the result.
- [ ] Verify focused Rust and Python tests pass.

---

### Task 3: Lambda/beta subset and Wasmtime docs

**Type:** implementation
**Depends-on:** 2
**Review:** lean

**Files:**
- Modify: `red2-wasm/src/vm.rs`
- Modify: `docs/red2-bytecode.md`
- Modify: `README.md`
- Test: `red2-wasm/src/vm.rs`
- Test: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: `run(...)` from Task 2
- Produces: support for simple lambda application, e.g. `((LAMBDA (X) X) 42)` and `((LAMBDA (X) (+ X 1)) 41)`, plus docs explaining Wasmtime target status.

- [ ] Write failing tests for identity and unary arithmetic lambda applications.
- [ ] Implement simple closure substitution/environment handling for the subset.
- [ ] Document stdout policy and Wasmtime roadmap/target installation note.
- [ ] Run full final gate: `cargo test`, `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests`.

## Operator smoke

- do: `uv run thor-spec compile-red2 --expr "(+ 2 3)" --output /tmp/add.red2 && cargo run -p red2-wasm -- /tmp/add.red2 --quantum 20 > /tmp/red2-rust.out`
- see: `/tmp/red2-rust.out` is empty and stderr contains `red2 result: 5`.

- do: `uv run thor-spec compile-red2 --expr "((LAMBDA (X) (+ X 1)) 41)" --output /tmp/lambda.red2 && cargo run -p red2-wasm -- /tmp/lambda.red2 --quantum 20`
- see: stderr contains `red2 result: 42`.

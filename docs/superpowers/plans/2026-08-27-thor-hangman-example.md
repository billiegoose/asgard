# THOR Hangman Example Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a declarative Hangman THOR example that runs through Python THOR, Python RED2, native Rust RED2, and Wasmtime RED2 IO paths.

**Architecture:** Implement `examples/hangman.thor` as local reusable top-level utility definitions plus a compact recursive game loop. Add tests that exercise win/loss behavior through the IO runtimes and Rust VM bytecode path. Only expand runtime utilities if the complete Hangman fixture requires them.

**Tech Stack:** THOR source examples, Python 3.14 pytest, Rust 1.75 Cargo, WASI `wasm32-wasi`, Wasmtime 17.

**Spec:** `docs/superpowers/specs/2026-08-27-thor-hangman-example-design.md`

## Global Constraints

- Keep examples under top-level `examples/`.
- Preserve stdout as UART/device IO bytes only.
- Write failing tests before implementation and verify they fail for the expected reason.
- Completion notification uses `afplay /System/Library/Sounds/Glass.aiff` after fresh verification.
- Keep final gates green: `cargo test -p red2-wasm`, `uv run pytest`, `uv run ruff check .`, `uv run mypy src tests`.

**Acceptance:** suite — `examples/hangman.thor` wins with input `ASGRD`, loses with input `xyzuvw`, runs through native Rust bytecode, and runs through Wasmtime bytecode with UART output on stdout.

---

### Task 1: Add Hangman fixture and Python IO tests

**Type:** implementation
**Depends-on:** none
**Review:** lean

**Files:**
- Create: `examples/hangman.thor`
- Modify: `tests/test_io_runtime.py`
- Modify: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: existing Python IO runtime actions `IO-RETURN`, `IO-BIND`, `IO-THEN`, `UART-RX`, `UART-TX`
- Produces: `examples/hangman.thor` with deterministic UART behavior; Python IO tests for THOR and RED2 models

**Parallelization rationale:** The THOR fixture and Python IO acceptance can be developed independently of Rust-specific integration tests.

- [ ] Add failing `tests/test_io_runtime.py` test that reads `examples/hangman.thor`, feeds `ASGRD`, and asserts stdout contains `WIN\n` for both `model="thor"` and `model="red2"`.
- [ ] Add failing `tests/test_io_runtime.py` test that feeds `xyzuvw` and asserts stdout contains `LOSE\n` for both models.
- [ ] Add failing docs/examples test that asserts README mentions `examples/hangman.thor` and the file has utility section comments.
- [ ] Create `examples/hangman.thor` with constants, helpers, render functions, update helpers, `loop`, and top-level action.
- [ ] Run `uv run pytest tests/test_io_runtime.py tests/test_docs_examples.py -v`.

---

### Task 2: Add Rust RED2 Hangman integration tests

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `tests/test_red2_wasm_cli.py`
- Modify: `red2-wasm/src/vm.rs`

**Interfaces:**
- Consumes: `examples/hangman.thor`, Python `encode_bundle`, Rust CLI `--io`
- Produces: native Rust bytecode tests for Hangman win/loss paths

**Parallelization rationale:** Rust acceptance depends on the Hangman fixture, but should not require docs changes or Wasmtime docs.

Only modify `red2-wasm/src/vm.rs` if Hangman exposes a real missing runtime behavior.

- [ ] Add failing pytest that compiles `examples/hangman.thor`, runs native Rust CLI with `--io`, input `ASGRD`, and asserts stdout contains `WIN\n` and stderr contains `io result: NIL`.
- [ ] Add failing pytest that compiles `examples/hangman.thor`, runs native Rust CLI with `--io`, input `xyzuvw`, and asserts stdout contains `LOSE\n` and stderr contains `io result: NIL`.
- [ ] If a test fails because Rust lacks a primitive/control form that the Python models handle, add the smallest Rust VM support and rerun the focused failing test.
- [ ] Run `cargo test -p red2-wasm` and `uv run pytest tests/test_red2_wasm_cli.py -v`.

---

### Task 3: Document Hangman native/Wasmtime usage and verify

**Type:** implementation
**Depends-on:** 2
**Review:** lean

**Files:**
- Modify: `README.md`
- Modify: `docs/red2-bytecode.md`
- Modify: `docs/thor-primitives.md`

**Interfaces:**
- Consumes: verified Hangman fixture and Rust CLI behavior
- Produces: documented native and Wasmtime Hangman commands

**Parallelization rationale:** Documentation depends on final command shape, so it follows the working fixture and Rust integration.

- [ ] Update README with Hangman compile/run commands and stdout/stderr notes.
- [ ] Update bytecode docs with a Hangman command alongside Caesar.
- [ ] Update primitive docs example list to include Hangman.
- [ ] Run final verification: `cargo test -p red2-wasm && uv run pytest && uv run ruff check . && uv run mypy src tests`.
- [ ] Run native smoke: compile Hangman and pipe `ASGRD`, expecting stdout to contain `WIN`.
- [ ] Run Wasmtime smoke: compile Hangman and pipe `ASGRD`, expecting stdout to contain `WIN`.
- [ ] Play completion sound: `afplay /System/Library/Sounds/Glass.aiff`.

## Operator smoke

- do: `uv run thor-spec compile-red2 --file examples/hangman.thor --output /tmp/hangman.red2`
- see: stderr contains `wrote RED2 bytecode: /tmp/hangman.red2`.

- do: `printf 'ASGRD' | cargo run -p red2-wasm --quiet -- /tmp/hangman.red2 --io > /tmp/hangman.out 2> /tmp/hangman.err; tail -n 3 /tmp/hangman.out; cat /tmp/hangman.err`
- see: stdout contains `WIN`; stderr contains `io result: NIL`.

- do: `printf 'xyzuvw' | cargo run -p red2-wasm --quiet -- /tmp/hangman.red2 --io > /tmp/hangman-lose.out 2> /tmp/hangman-lose.err; tail -n 3 /tmp/hangman-lose.out; cat /tmp/hangman-lose.err`
- see: stdout contains `LOSE`; stderr contains `io result: NIL`.

- do: `cargo build -p red2-wasm --target wasm32-wasi && printf 'ASGRD' | wasmtime --dir /tmp target/wasm32-wasi/debug/red2-wasm.wasm /tmp/hangman.red2 --io > /tmp/hangman-wasm.out 2> /tmp/hangman-wasm.err`
- see: stdout contains `WIN`; stderr contains `io result: NIL`.

# Rust VM Loop Architecture Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Rust RED2/WASM evaluation loop-driven and reject stuck primitive applications with errors.

**Architecture:** Convert runtime control flow to explicit loops and continuation stacks in `models/rust-red2/src/vm.rs`, keeping bytecode parsing unchanged. Add strict primitive validation so unknown symbols or wrong argument shapes become `Red2Error`s rather than preserved applications. Preserve Breakout and recording behavior while adding deep-loop and stuck-primitive regressions.

**Tech Stack:** Rust 2021 std-only crate, WASI `wasm32-wasi`, Wasmtime, Python 3.14 pytest, mise, asciinema.

**Spec:** `docs/superpowers/specs/2026-08-29-rust-vm-loop-architecture-design.md`

**Acceptance:** suite — Rust unit tests plus pytest `mise`/recording tests verify loop safety, long WASM Breakout, generator behavior, and strict primitive errors.

## Global Constraints

- Bytecode format and compiler output remain unchanged.
- Rust native and WASI execution must not depend on host call-stack depth for ordinary THOR/RED2 looping, IO sequencing, or tail-position lambda/control transitions.
- Strict primitive operations must error when their arguments cannot reduce to supported values.
- The stdout/stderr policy remains: stdout is device output; errors go to stderr through the CLI wrapper.
- Do not introduce external Rust dependencies.

---

### Task 1: Add stack-safety and strict-primitive regression tests

**Type:** implementation
**Depends-on:** none
**Review:** adversarial
**Commutes:** `tests/test_mise_tasks.py`, `tests/test_red2_wasm_cli.py`

**Files:**
- Modify: `tests/test_mise_tasks.py`
- Modify: `tests/test_red2_wasm_cli.py`
- Modify: `tests/test_example_recordings.py`

**Interfaces:**
- Consumes: existing `run_rust_vm(...)` test helper and `mise run wasm` task.
- Produces: tests for long 70-tick WASM Breakout, strict primitive errors, and long WASM cast quality.

**Parallelization rationale:** Tests describe target behavior independently from implementation internals.

- [ ] Add/restore a 70-tick WASM Breakout pytest regression.
- [ ] Add strict primitive error pytest cases for `(+ 1 frog)`, `(MINUS frog)`, `(UART-TX frog)`, and `(IF frog 1 2)`.
- [ ] Require `examples/media/breakout-wasm.cast` to have at least 1000 events, 5-6s duration, at least 10 ball draws, and no trap/stack text.
- [ ] Run focused tests and verify they fail before implementation.

### Task 2: Convert Rust reducer and IO runner to explicit loops

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `models/rust-red2/src/vm.rs`

**Interfaces:**
- Consumes: existing `Expr`, `Reducer`, `IoRunner`, `ClockSource`, and `run_io_bundle_with_clock` APIs.
- Produces: loop-driven `Reducer::reduce`, explicit `ReduceStep`, loop-driven `IoRunner::run_action`, explicit `IoFrame`, strict primitive error behavior.

**Parallelization rationale:** Runtime architecture is a single cohesive change and should be reviewed as one unit.

- [ ] Replace recursive tail-position reducer self-calls with loop state transitions.
- [ ] Replace recursive IO sequencing with an explicit continuation stack.
- [ ] Trim captured environments to referenced outer variable depth when applying lambdas.
- [ ] Keep structural recursion only for bounded tree walks.
- [ ] Make primitive/control failures return `Red2Error` with clear stuck argument messages.
- [ ] Run Rust and focused pytest gates.

### Task 3: Regenerate/upload full WASM recording and final verification

**Type:** implementation
**Depends-on:** 2

**Files:**
- Modify: `tools/videos/generate.py`
- Modify: `.mise.toml`
- Modify: `examples/media/breakout-wasm.cast`
- Modify: `examples/README.md`

**Interfaces:**
- Consumes: stack-safe long WASM Breakout execution from Task 2.
- Produces: `mise run generate-video breakout-wasm --no-upload`, uploaded full WASM cast URL, and updated README badge.

**Parallelization rationale:** Recording generation depends on the runtime being fixed.

- [ ] Ensure `breakout-wasm` generator uses the same 70-tick `BREAKOUT_STEPS` as Python Breakout.
- [ ] Regenerate with `mise run generate-video breakout-wasm --no-upload`.
- [ ] Upload with `asciinema upload examples/media/breakout-wasm.cast`.
- [ ] Update `examples/README.md` to the new hosted URL.
- [ ] Run final verification: `cargo test -p red2-wasm`, focused pytest, Ruff, mypy.
- [ ] Commit and push.

## Operator smoke

- do: `mise run generate-video breakout-wasm --no-upload`
- see: `examples/media/breakout-wasm.cast` is a long 5-6 second real recording with many timed events and no stack trace.
- do: `asciinema play examples/media/breakout-wasm.cast`
- see: Breakout animates through the full deterministic playthrough like the Python recording.

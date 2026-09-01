# RED2 APP-VAR Slice Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Chapter 4 APP-VAR/single-variable-argument behavior to the faithful Python RED2 slice.

**Architecture:** Evolve `mured.py` in place. Keep explicit graph/environment memory and one-transition dispatch; APP-VAR is a real opcode, not an evaluator shortcut.

**Tech Stack:** Python 3.11+, pytest, Ruff, mypy, Thor AST/parser

**Spec:** `docs/superpowers/specs/2026-09-01-red2-app-var-slice-design.md`

**Acceptance:** suite — transition, compiler/decompiler, fidelity, anti-shortcut, and full project gates cover this slice.

## Global Constraints

- Evolve `models/python/red2_engine/mured.py` in place and retain current public names.
- Execution operates directly on graph/environment memory and registers; `step()` and `run()` never invoke decompilation, private terms, or the Chapter 3 evaluator.
- APP-VAR is the only new opcode in this slice.
- Primitive firing, symbols/definition lookup, floats/chars, structures, recursion, CLI integration, Rust implementation, and FPGA work remain out of scope.
- Existing μRED/head/INT behavior must remain unchanged except where APP-VAR intentionally replaces single-variable argument graph layout.

---

### Task 1: Compile and decompile APP-VAR spine entries

**Type:** implementation
**Depends-on:** none

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_fidelity.py`

**Interfaces:**
- Consumes: existing `compile_lambda(expr) -> tuple[Word, ...]`, `Word(..., head: bool)`, and `_decompile()` application-spine traversal
- Produces: `MuredOpcode.APP_VAR` layout and decompiler support for APP-VAR inside spines

- [ ] Add failing tests showing a single bound variable argument compiles to inline `Word(MuredOpcode.APP_VAR, index, False)` while non-variable arguments still compile through `APP` pointers. Use an expression such as `(LAMBDA (f x) (f x))`; expected body spine contains `APP_VAR 0` followed by the operator `VAR 1`.
- [ ] Add a failing decompiler test loading a result spine containing `APP_VAR` before an operator and expecting the original application source order.
- [ ] Implement `MuredOpcode.APP_VAR` and compiler helper logic that recognizes only syntactic `Var` and in-scope `Symbol` arguments. Keep operators and non-variable arguments unchanged.
- [ ] Extend `_decompile()` application-spine traversal so `APP_VAR` contributes an inline `Var(data)` argument and continues to the next spine word.
- [ ] Run `uv run pytest tests/test_mured_compile.py tests/test_mured_fidelity.py -q`, `uv run ruff check models/python/red2_engine/mured.py tests/test_mured_compile.py tests/test_mured_fidelity.py`, `uv run mypy models/python/red2_engine/mured.py tests/test_mured_compile.py tests/test_mured_fidelity.py`, and `git diff --check`.
- [ ] Commit as `feat: compile app-var spine entries`.

### Task 2: Execute APP-VAR transitions and contraction

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/mured-thesis-notes.md`
- Modify: `docs/thor-red2-prototype.md`

**Interfaces:**
- Consumes: `MuredOpcode.APP_VAR` from Task 1
- Produces: direct `_app_var(word: Word) -> None`, APP-VAR-aware LAMBDA contraction, and JOIN VAR-to-APP-VAR conversion

- [ ] Add failing transition tests for forward APP-VAR resolving to `UBV`, forward APP-VAR resolving to `CLOSURE`, reverse APP-VAR, LAMBDA contraction with result-head APP-VAR, and JOIN converting a reduced VAR argument into APP-VAR while reclaiming the `VAR; JOIN` tail.
- [ ] Implement direct dispatch for `APP_VAR`. On forward execution, `LOOKUP(word.data)`, increment `pc`, and either push corrected `APP_VAR` for UBV or push control path plus `APP` for CLOSURE. On reverse execution, decrement `pc` only. Reject negative/non-int data and malformed values.
- [ ] Update `_lambda()` so a result-head `APP_VAR` contracts by allocating `Word(UBV, phi - app_var.data, False)`, decrementing `q`, reclaiming one result word, and entering the body without popping control.
- [ ] Update `_join()` so a reduced `VAR` at `pc + 1` rewrites the parent APP as `APP_VAR`, decrements `fsp` by two, and continues up the parent spine; non-VAR results keep the existing APP-pointer behavior.
- [ ] Add small semantic/cycle coverage for closed programs that exercise compiled APP-VAR without changing final meaning. Include `(LAMBDA (f x) (f x))`, `((LAMBDA (x) (LAMBDA (y) x)) 42)`, and a zero-quantum case.
- [ ] Update docs to say APP-VAR is now implemented but full RED2 still remains incomplete.
- [ ] Run `uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py tests/test_mured_compile.py tests/test_mured_fidelity.py -q`, `uv run pytest -q`, `uv run ruff check .`, `uv run mypy models/python tests`, `cargo test -p red2-wasm`, and `git diff --check`.
- [ ] Commit as `feat: execute app-var transitions`.

### Task 3: Integrated verification gate

**Type:** gate
**Depends-on:** 2

**Files:**
- Test: `tests/test_mured_state.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_compile.py`
- Test: `tests/test_mured_fidelity.py`

**Interfaces:**
- Consumes: cumulative APP-VAR implementation
- Produces: no code; fresh integrated validation evidence

- [ ] Run `uv run pytest -q`, `uv run ruff check .`, `uv run mypy models/python tests`, `cargo test -p red2-wasm`, `git diff --check`, and `git status --short`; require zero failures and clean status.

## Operator smoke

- do: `uv run pytest tests/test_mured_compile.py tests/test_mured_transitions.py tests/test_mured_fidelity.py -q`
- see: All selected APP-VAR and existing μRED/INT tests pass.

- do: `uv run python -c 'from red2_engine.mured import MuredMachine; from thor_lang.parser import parse_expr; from thor_lang.pretty import to_source; m=MuredMachine.from_expr(parse_expr("(LAMBDA (f x) (f x))"), quantum=10); m.run(); print(to_source(m.result_expr()))'`
- see: `(LAMBDA (f x) (f x))`

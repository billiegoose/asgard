# RED2 FLOAT and CHAR Slice Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add faithful passive `FLOAT` and `CHAR` instructions to the evolving Python RED2 slice.

**Architecture:** Extend the existing `mured.py` passive-data machinery while keeping one-transition dispatch and explicit graph-memory execution. `FLOAT` and `CHAR` mirror `INT` transition shape but validate their own payloads.

**Tech Stack:** Python 3.11+, pytest, Ruff, mypy, Thor AST/parser

**Spec:** `docs/superpowers/specs/2026-09-01-red2-float-char-slice-design.md`

**Acceptance:** suite — focused transition, compile/decompile, fidelity, anti-shortcut, documentation, and full project gates cover this slice.

## Global Constraints

- Evolve `models/python/red2_engine/mured.py` in place and retain current public names.
- Execution operates directly on graph/environment memory and registers; `step()` and `run()` never invoke decompilation, private terms, or the Chapter 3 evaluator.
- This slice adds only `FLOAT` and `CHAR` passive data instructions.
- Symbolic constants and definition lookup, primitive firing, structures, recursion, CLI integration, Rust implementation, and FPGA work remain out of scope.
- Existing μRED/head/INT/APP-VAR behavior must remain unchanged.

---

### Task 1: Execute and reconstruct FLOAT/CHAR passive data

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `docs/mured-thesis-notes.md`

**Interfaces:**
- Consumes: existing `INT` passive transition shape and `compile_lambda(expr) -> tuple[Word, ...]`
- Produces: `MuredOpcode.FLOAT`, `MuredOpcode.CHAR`, compile/load/decompile/transition support for `Float` and `Char`

- [ ] Add failing compile tests for exact words and head flags:

```python
assert compile_lambda(parse_expr("1.5")) == (Word(MuredOpcode.FLOAT, 1.5, True),)
assert compile_lambda(parse_expr("#\\a")) == (Word(MuredOpcode.CHAR, "a", True),)
assert compile_lambda(parse_expr("(LAMBDA (x) 1.5)"))[-1] == Word(MuredOpcode.FLOAT, 1.5, True)
assert compile_lambda(parse_expr("(LAMBDA (x) #\\space)"))[-1] == Word(MuredOpcode.CHAR, " ", True)
```

Run `uv run pytest tests/test_mured_compile.py -q` and verify failure because the opcodes are absent.

- [ ] Add failing transition tests for both `FLOAT` and `CHAR`: forward head copies the exact word and enters reverse traversal; forward non-head copies and advances; reverse decrements `pc` only. Add malformed payload tests: `FLOAT` rejects `1`, `True`, and non-numbers; `CHAR` rejects `""`, `"ab"`, and non-strings.

- [ ] Implement `MuredOpcode.FLOAT` and `MuredOpcode.CHAR`. Import `Float` and `Char`. Extend the passive-data helper or add opcode-specific transition methods so payload validation is exact and deterministic. Permit both opcodes in `MuredMachine.load()`.

- [ ] Extend compilation and decompilation: `Float(value)` emits/reconstructs `Word(MuredOpcode.FLOAT, value, head)` and `Char(value)` emits/reconstructs `Word(MuredOpcode.CHAR, value, head)`. Reject malformed result words with `MuredMachineError` or the existing deterministic machine error family.

- [ ] Add fidelity tests comparing halted machine results to Chapter 3 for:

```text
1.5
#\a
#\space
(LAMBDA (x) 1.5)
(LAMBDA (x) #\newline)
((LAMBDA (x) x) 1.5)
((LAMBDA (x) x) #\a)
```

Include quantum `10` and at least one zero-quantum application case.

- [ ] Update docs to say the faithful slice now includes APP-VAR/head plus passive `INT`, `FLOAT`, and `CHAR`; symbolic constants remain deferred.

- [ ] Run:

```bash
uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py tests/test_mured_compile.py tests/test_mured_fidelity.py -q
uv run pytest -q
uv run ruff check .
uv run mypy models/python tests
cargo test -p red2-wasm
git diff --check
```

Confirm only declared files changed and commit as `feat: execute passive float and char data`.

### Task 2: Integrated verification gate

**Type:** gate
**Depends-on:** 1

**Files:**
- Test: `tests/test_mured_state.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_compile.py`
- Test: `tests/test_mured_fidelity.py`

**Interfaces:**
- Consumes: Task 1 FLOAT/CHAR implementation
- Produces: no code; fresh integrated validation evidence

- [ ] Run `uv run pytest -q`, `uv run ruff check .`, `uv run mypy models/python tests`, `cargo test -p red2-wasm`, `git diff --check`, and `git status --short`; require zero failures and clean status.

## Operator smoke

- do: `uv run python -c 'from red2_engine.mured import MuredMachine; from thor_lang.parser import parse_expr; from thor_lang.pretty import to_source; m=MuredMachine.from_expr(parse_expr("((LAMBDA (x) x) 1.5)"), quantum=10); m.run(); print(to_source(m.result_expr()))'`
- see: `1.5`

- do: Repeat with `parse_expr("((LAMBDA (x) x) #\\space)")`.
- see: `#\space`

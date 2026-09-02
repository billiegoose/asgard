# RED2 Passive Symbol Slice Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Chapter 4 no-definition `SYM` branch to the evolving faithful Python RED2 slice.

**Architecture:** Represent free symbolic constants as `SYM` graph words and execute only the `definition = bottom` branch. Definitions remain out of scope, so symbol execution is passive but documented as an incomplete subset of the full SYM instruction.

**Tech Stack:** Python 3.11+, pytest, Ruff, mypy, Thor AST/parser

**Spec:** `docs/superpowers/specs/2026-09-02-red2-symbol-passive-slice-design.md`

**Acceptance:** suite — transition, compiler/decompiler, fidelity, docs, anti-shortcut, and full project gates cover this slice.

## Global Constraints

- Evolve `models/python/red2_engine/mured.py` in place and retain current public names.
- Execution operates directly on graph/environment memory and registers; `step()` and `run()` never invoke decompilation, private terms, or the Chapter 3 evaluator.
- This slice adds only no-definition `SYM` behavior.
- Symbol hash tables, definition lookup/reduction, primitive firing, structures, recursion, CLI integration, Rust implementation, and FPGA work remain out of scope.
- Existing μRED/head/INT/FLOAT/CHAR/APP-VAR behavior must remain unchanged.

---

### Task 1: Execute and reconstruct no-definition SYM

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
- Consumes: existing passive-data transition pattern and `compile_lambda(expr) -> tuple[Word, ...]`
- Produces: `MuredOpcode.SYM`, compile/load/decompile/transition support for no-definition symbols

- [ ] Add failing compile tests:

```python
assert compile_lambda(parse_expr("FOO")) == (Word(MuredOpcode.SYM, "FOO", True),)
assert compile_lambda(parse_expr("(LAMBDA (x) FOO)"))[-1] == Word(MuredOpcode.SYM, "FOO", True)
assert compile_lambda(parse_expr("(LAMBDA (x) x)"))[-1] == Word(MuredOpcode.VAR, 0, True)
assert any(word.opcode is MuredOpcode.APP_VAR for word in compile_lambda(parse_expr("(LAMBDA (f x) (f x))")))
```

Run `uv run pytest tests/test_mured_compile.py -q` and verify failure because free symbols are still rejected or `SYM` is absent.

- [ ] Add failing transition tests for `SYM`: forward head copies the exact word and enters reverse traversal; forward non-head copies and advances; reverse decrements `pc` only. Add malformed payload tests rejecting non-string data and empty symbol names.

- [ ] Implement `MuredOpcode.SYM`. Change `compile_lambda()` so `Symbol` in lexical scope still emits `VAR`, while free `Symbol` emits `Word(MuredOpcode.SYM, name, head)`. Permit `SYM` in `MuredMachine.load()`.

- [ ] Implement direct `_sym(word: Word) -> None` for the no-definition branch. Validate `type(word.data) is str and word.data != ""`. Reuse or mirror passive-data copy/walk behavior, but do not add a definition field and do not decrement `q`.

- [ ] Extend `_decompile()` so valid `SYM` result words become `Symbol(name)`.

- [ ] Add fidelity tests comparing halted machine results to Chapter 3 for:

```text
FOO
(LAMBDA (x) FOO)
((LAMBDA (x) x) FOO)
((LAMBDA (x) FOO) 42)
```

Include quantum `10` and one zero-quantum application case. Ensure bound symbols still do not become `SYM`.

- [ ] Update docs to say the faithful slice includes no-definition symbols only, and that symbol definition lookup/reduction remains deferred.

- [ ] Run:

```bash
uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py tests/test_mured_compile.py tests/test_mured_fidelity.py -q
uv run pytest -q
uv run ruff check .
uv run mypy models/python tests
cargo test -p red2-wasm
git diff --check
```

Confirm only declared files changed and commit as `feat: execute passive symbols without definitions`.

### Task 2: Integrated verification gate

**Type:** gate
**Depends-on:** 1

**Files:**
- Test: `tests/test_mured_state.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_compile.py`
- Test: `tests/test_mured_fidelity.py`

**Interfaces:**
- Consumes: Task 1 SYM implementation
- Produces: no code; fresh integrated validation evidence

- [ ] Run `uv run pytest -q`, `uv run ruff check .`, `uv run mypy models/python tests`, `cargo test -p red2-wasm`, `git diff --check`, and `git status --short`; require zero failures and clean status.

## Operator smoke

- do: `uv run python -c 'from red2_engine.mured import MuredMachine; from thor_lang.parser import parse_expr; from thor_lang.pretty import to_source; m=MuredMachine.from_expr(parse_expr("((LAMBDA (x) x) FOO)"), quantum=10); m.run(); print(to_source(m.result_expr()))'`
- see: `FOO`

- do: Repeat with `parse_expr("(LAMBDA (x) FOO)")`.
- see: `(LAMBDA (x) FOO)`

# Full Appendix A Benchmarks Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Appendix A core-subset fixtures with fuller SINE and GAME benchmark coverage that runs with THOR/RED2 parity.

**Architecture:** Keep THOR as reference and RED2 as parity target. Add only language/runtime behavior needed by the Appendix A source, then transcribe fuller fixtures and update docs to remove SINE/GAME omissions. Leave hardware/vendor/cycle-accurate non-goals intact.

**Tech Stack:** Python 3.14, pytest, ruff, mypy, uv.

**Spec:** `thesis-transcription/src/appendices/appendix-a.tex`; `thesis-transcription/src/chapters/chapter3.tex`; `thesis-transcription/src/chapters/chapter4.tex`.

## Global Constraints

- Keep runtime dependencies empty.
- Preserve `thor-spec` CLI behavior.
- Verify every benchmark fixture with both `--model thor` and `--model red2`.
- Do not require PipelineC/vendor FPGA tools.
- Prefer Appendix A source definitions for higher-order functions; add Python primitives only for primitive operators or finite-fixture safety helpers.

**Acceptance:** suite — full pytest plus CLI fixture parity smokes verify this plan.

---

### Task 1: Full SINE Fixture and Numeric Semantics

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `src/thor_spec/primitives.py`
- Modify: `src/thor_spec/red2/primitives.py`
- Create: `tests/fixtures/appendix_a/sine_full.thor`
- Create: `tests/test_appendix_a_sine_full.py`
- Modify: `docs/thor-red2-prototype.md`

**Interfaces:**
- Consumes: existing scalar primitives and recursive definitions.
- Produces: full-ish Appendix A SINE fixture using Taylor/Horner/period/reflection definitions; parity helper tests.

- [ ] **Step 1: Write failing SINE full test**

Create `tests/test_appendix_a_sine_full.py`:

```python
from pathlib import Path

from thor_spec.golden import run_source


def test_sine_full_fixture_matches_between_thor_and_red2() -> None:
    source = Path("tests/fixtures/appendix_a/sine_full.thor").read_text()
    thor = run_source(source, model="thor", quantum=20000)
    red2 = run_source(source, model="red2", quantum=20000)
    assert thor == red2
    assert thor in {"0", "0.0"}
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_appendix_a_sine_full.py -v`
Expected: FAIL because fixture does not exist and/or numeric gaps remain.

- [ ] **Step 3: Implement numeric gaps and fixture**

Transcribe Appendix A SINE to ASCII `.thor`, preserving names. If exact `sine pi` floating equality is unstable, add fixture comments and choose a deterministic benchmark expression such as `(sine 0)` or `(sine pi)` rounded through existing arithmetic only if both models match. Ensure `floor`, `ceiling`, `expt`, float division/coercion, `abs`, `1+`, `1-`, and recursive Horner evaluation work for THOR and RED2.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_appendix_a_sine_full.py -v`
Expected: PASS.

---

### Task 2: Full GAME Move Generator Fixture

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `src/thor_spec/primitives.py`
- Modify: `src/thor_spec/red2/primitives.py`
- Modify: `src/thor_spec/normalization.py`
- Create: `tests/fixtures/appendix_a/game_full.thor`
- Create: `tests/test_appendix_a_game_full.py`
- Modify: `docs/thor-red2-prototype.md`

**Interfaces:**
- Consumes: existing list/structure/recursive definition behavior.
- Produces: Appendix A GAME fixture with `moves`, `reverse`, `reptree`, `maptree`, `prune`, `static`, and `evaluate 1` parity.

- [ ] **Step 1: Write failing GAME full test**

Create `tests/test_appendix_a_game_full.py`:

```python
from pathlib import Path

from thor_spec.golden import run_source


def test_game_full_fixture_matches_between_thor_and_red2() -> None:
    source = Path("tests/fixtures/appendix_a/game_full.thor").read_text()
    thor = run_source(source, model="thor", quantum=30000)
    red2 = run_source(source, model="red2", quantum=30000)
    assert thor == red2
    assert thor.lstrip("-").replace(".", "", 1).isdigit()
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_appendix_a_game_full.py -v`
Expected: FAIL before full fixture/support.

- [ ] **Step 3: Implement GAME support**

Transcribe Appendix A GAME as closely as possible. Define `reverse` in THOR source if Appendix A assumes it. Ensure lowercase `or`, `nil`, `cons`, `car`, `cdr`, `equal?`, `max`, `min`, `even?`, `++`, `map`, `reduce`, `reptree`, and generated tree helpers all work in both models. Keep depth at `evaluate 1` unless depth 2 is tractable under 30k quantum.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_appendix_a_game_full.py -v`
Expected: PASS.

---

### Task 3: Character/Symbol Runtime Coverage and Omission Cleanup

**Type:** implementation
**Depends-on:** none

**Files:**
- Modify: `src/thor_spec/parser.py`
- Modify: `src/thor_spec/pretty.py`
- Modify: `src/thor_spec/primitives.py`
- Modify: `src/thor_spec/red2/primitives.py`
- Create: `tests/test_character_symbol_runtime.py`
- Modify: `docs/thor-red2-prototype.md`

**Interfaces:**
- Consumes: existing `Char` AST.
- Produces: parser/pretty/runtime parity tests for character constants and symbol predicates/equality.

- [ ] **Step 1: Write failing char/symbol tests**

Create tests asserting `#\\a` parses/prints, `(CHAR? #\\a)` is `TRUE`, `(SYMBOL? FOO)` is `TRUE`, `(EQUAL? #\\a #\\a)` is `TRUE`, and THOR/RED2 parity holds.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_character_symbol_runtime.py -v`
Expected: FAIL if any char/symbol omission remains.

- [ ] **Step 3: Implement minimal runtime coverage**

Fill parser/pretty/primitive gaps for character and symbol constants. Update docs to remove the character-operator omission if tests cover it; otherwise describe remaining non-benchmark character APIs precisely.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_character_symbol_runtime.py -v`
Expected: PASS.

---

### Task 4: Integrated Benchmark Gate

**Type:** gate
**Depends-on:** 1, 2, 3

**Files:**
- Test: `tests/`
- Test: `docs/thor-red2-prototype.md`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: verified full Appendix A benchmark coverage status.

- [ ] **Step 1: Full tests**

Run: `uv run pytest`
Expected: PASS.

- [ ] **Step 2: Static checks**

Run: `uv run ruff check . && uv run mypy src tests`
Expected: PASS.

- [ ] **Step 3: CLI fixture smokes**

Run THOR and RED2 CLI for `sine_full.thor` and `game_full.thor` with the quantum from tests.
Expected: THOR and RED2 outputs match for each fixture.

---

## Operator smoke

- do: `uv run pytest tests/test_appendix_a_sine_full.py tests/test_appendix_a_game_full.py -v`
- see: both tests pass.

- do: run `thor-spec` on `sine_full.thor` with both models.
- see: outputs match.

- do: run `thor-spec` on `game_full.thor` with both models.
- see: outputs match.

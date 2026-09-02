# Remaining Faithful Python RED2 Slices Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the faithful Python RED2 VM in `models/python/red2_engine/mured.py` after the passive `SYM` slice lands.

**Architecture:** Continue evolving `mured.py` in place through narrow Chapter 4 slices. Each slice adds one coherent machine mechanism, keeps direct graph/environment/register execution, and ends with focused transition tests, fidelity checks, adversarial review, and full project validation.

**Tech Stack:** Python 3.11+, pytest, Ruff, mypy, Thor AST/parser/semantics as reference only at test boundaries

**Spec:** Existing Chapter 4 transcription plus per-slice specs to be created by each planning task.

**Acceptance:** suite — every slice has focused transition/layout/fidelity tests plus the full project gates.

## Global Constraints

- Evolve `models/python/red2_engine/mured.py` in place until the faithful surface is large enough to rename.
- Execution operates directly on graph/environment memory and registers; `step()` and `run()` never invoke decompilation, private terms, or the Chapter 3 evaluator.
- Existing μRED/head/APP-VAR/passive-data behavior must remain green after every slice.
- Every implementation slice must update docs to state exactly which part of RED2 remains incomplete.
- Use low-cost subagent models where practical, but use adversarial review for hard-to-read machine semantics.

---

### Task 1: Land current passive SYM slice

**Type:** manual
**Depends-on:** none

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `docs/mured-thesis-notes.md`

**Interfaces:**
- Consumes: active workflow `cc0106f2-3c06-4305-87fd-47c8c21b36c5`
- Produces: no-definition `MuredOpcode.SYM`

- [ ] Wait for the active workflow result.
- [ ] If review passes, integrate the final head and run local gates.
- [ ] If review fails, fix only reviewed blockers with TDD and rerun review.

### Task 2: Symbol definitions and closed definition execution

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-symbol-definitions-slice-design.md`

**Interfaces:**
- Consumes: no-definition `SYM`
- Produces: representation for symbol definition metadata; head `SYM` definition execution; reverse `SYM` conversion to `APP`

- [ ] Write a slice spec for Chapter 4 `SYM` with definitions: abstract definition metadata, q handling, forward head execution, reverse conversion to `APP`, and control-stack path push.
- [ ] Add failing tests for head `SYM` with definition and q>0 reducing through definition code; q=0 and non-head remain passive.
- [ ] Implement the minimal abstract definition representation needed by `Word` or side tables.
- [ ] Implement forward and reverse definition branches exactly as Chapter 4 describes.
- [ ] Add fidelity tests comparing defined-symbol expansion against Chapter 3 at normal and zero quantum.
- [ ] Run focused/full gates and commit.

### Task 3: Primitive-register scaffold and passive primitive opcodes — ✅ DONE (commit a423f18)

**Type:** implementation
**Depends-on:** 2
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_state.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-primitive-registers-slice-design.md`

**Interfaces:**
- Consumes: head flags and passive data
- Produces: `argcnt`, `prim`, `fire` registers; `PRIM_0`, `PRIM_1`, `PRIM_2` opcodes in passive/no-fire cases

**Status:** Implemented manually on 2026-09-02. Opcodes `PRIM_0/1/2`, `argcnt/prim/fire` registers, `_prim()` passive handler, load/validate/step wiring, and `test_prim_forward_pushes_word_and_sets_registers` landed in commit `a423f18`. 108 tests pass. Remaining sub-items (`argcnt` maintenance through APP/LAMBDA/JOIN paths and PRIM compilation) are folded into Task 4 since strict ADD requires those same paths.

- [x] Write a slice spec for primitive firing registers and passive primitive copying.
- [x] Add state validation and snapshot coverage for `argcnt`, `prim`, and `fire`.
- [x] Test passive PRIM forward/reverse behavior and unchanged earlier slices.
- [x] Run focused/full gates and commit.
- [ ] Update APP/LAMBDA/JOIN/passive-copy paths to maintain `argcnt` per Chapter 4 (deferred to Task 4).
- [ ] Add PRIM opcode compilation for primitive symbols without firing yet where q/arity prevents firing (deferred to Task 4).

### Task 4: Strict primitive firing, integer ADD first

**Type:** implementation
**Depends-on:** 3
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-strict-add-slice-design.md`

**Interfaces:**
- Consumes: primitive registers and `PRIM_2`
- Produces: strict primitive fire path for integer ADD

- [ ] Write a slice spec for firing mechanism and ADD's Chapter 4 overwrite/reclaim/q behavior.
- [ ] Add failing transition tests where `(+ 2 3)` reduces by firing ADD only after both arguments are reduced.
- [ ] Implement fire countdown save/restore around nested argument reduction.
- [ ] Implement integer ADD with q/type checks and memory reclamation.
- [ ] Add q=0 and wrong-type tests proving the primitive remains unreduced/passive.
- [ ] Run focused/full gates and commit.

### Task 5: Strict primitive family expansion

**Type:** implementation
**Depends-on:** 4
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-strict-primitives-slice-design.md`

**Interfaces:**
- Consumes: ADD/fire machinery
- Produces: selected unary/binary strict primitive set matching current Chapter 3 primitive surface for numbers/chars/symbol predicates

- [ ] Write a spec enumerating exactly which strict primitives this slice supports.
- [ ] Add parity tests against Chapter 3 for each selected primitive at completion and q=0.
- [ ] Add type/coercion tests, including int/float arithmetic where supported by Chapter 3.
- [ ] Implement the minimal primitive table and firing handlers.
- [ ] Run focused/full gates and commit.

### Task 6: Non-strict primitive Y

**Type:** implementation
**Depends-on:** 5
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-y-primitive-slice-design.md`

**Interfaces:**
- Consumes: `PRIM_0`, `argcnt`, q, APP/APP_VAR behavior
- Produces: Chapter 4 Y transformation for `(Y f)`

- [ ] Write a spec for the Y transformation and passive q=0/no-argument cases.
- [ ] Add failing cycle tests for Y with APP and non-APP `f` cases.
- [ ] Implement the graph rewrite and temporary head-copy behavior.
- [ ] Add semantic checks for a tiny recursive expression bounded by quantum.
- [ ] Run focused/full gates and commit.

### Task 7: Non-strict conditional IF

**Type:** implementation
**Depends-on:** 5
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-if-primitive-slice-design.md`

**Interfaces:**
- Consumes: primitive registers and strict first-argument reduction machinery
- Produces: IF behavior that reduces condition but preserves lazy branches

- [ ] Write a spec for IF's strict/non-strict split and q behavior.
- [ ] Add tests proving only the condition is forced before branch selection.
- [ ] Implement the minimal graph control needed for branch selection.
- [ ] Add q=0/non-boolean reconstruction tests.
- [ ] Run focused/full gates and commit.

### Task 8: Lazy STRUCT instruction and structure compilation

**Type:** implementation
**Depends-on:** 5
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-structures-slice-design.md`

**Interfaces:**
- Consumes: passive symbols/data, APP/APP_VAR, LAMBDA-like contraction
- Produces: `STRUCT` opcode, structure literal compilation, selector behavior through existing lambda machinery

- [ ] Write a spec for Chapter 4 STRUCT compilation and q-save/q-zero behavior.
- [ ] Add compile tests for `{PAIR 1 2}` into `STRUCT`, APP component graphs, and trailing `VAR 0`.
- [ ] Add transition tests for STRUCT with no arguments and with selector argument.
- [ ] Implement STRUCT as LAMBDA-like with q preservation around lazy components.
- [ ] Add fidelity tests for `{PAIR 1 2}` and selector-like applications.
- [ ] Run focused/full gates and commit.

### Task 9: LETREC compile scaffold and RBLOCK/RUP construction

**Type:** implementation
**Depends-on:** 8
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-letrec-rblock-rup-slice-design.md`

**Interfaces:**
- Consumes: SYM decompilation, environment allocation, q behavior
- Produces: `RBLOCK`, `RUP`, partial `REC` environment constructs, LETREC compilation layout

- [ ] Write a spec for LETREC compilation and forward RBLOCK/RUP construction paths.
- [ ] Add compile tests for a one-binding and two-binding LETREC layout.
- [ ] Add transition tests for q>0 REC construction and q=0 UBV/control preparation.
- [ ] Implement only RBLOCK/RUP construction paths and reject unsupported RECP execution explicitly.
- [ ] Run focused/full gates and commit.

### Task 10: RECP access and LETREC reconstruction

**Type:** implementation
**Depends-on:** 9
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-recp-reconstruct-slice-design.md`

**Interfaces:**
- Consumes: `REC`, `RBLOCK`, `RUP` constructs
- Produces: `RECP` execution and Chapter 4 `RECONSTRUCT`

- [ ] Write a spec for RECP forward/reverse branches and RECONSTRUCT.
- [ ] Add transition tests for head/non-head RECP, q>0 binding access, q=0 reconstruction, and reverse behavior.
- [ ] Implement RECP and RECONSTRUCT with explicit environment replacement of RECs by UBVs.
- [ ] Add semantic bounded-quantum LETREC parity tests.
- [ ] Run focused/full gates and commit.

### Task 11: CLI/program integration for faithful machine

**Type:** implementation
**Depends-on:** 10
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/__init__.py`
- Modify: `models/python/thor_compile/cli.py`
- Modify: `models/python/thor_compile/red2.py`
- Modify: `tests/test_red2_machine_core.py`
- Create: `tests/test_mured_cli.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-faithful-cli-slice-design.md`

**Interfaces:**
- Consumes: complete faithful Python RED2 subset
- Produces: opt-in CLI path for faithful machine, without replacing evaluator-backed compatibility mode by default

- [ ] Write a spec for an opt-in CLI flag or separate command path.
- [ ] Add CLI tests proving current compatibility CLI remains unchanged.
- [ ] Add faithful CLI tests for lambda, passive data, symbol, primitive, structure, and LETREC examples.
- [ ] Implement the opt-in route and docs.
- [ ] Run focused/full gates and commit.

### Task 12: Final integrated RED2 conformance review

**Type:** implementation
**Depends-on:** 11
**Review:** adversarial

**Files:**
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Create: `docs/superpowers/specs/2026-09-02-red2-final-conformance-design.md`

**Interfaces:**
- Consumes: all faithful Python RED2 slices
- Produces: final conformance checklist, corpus, and remaining-gap declaration

- [ ] Write a final conformance spec enumerating supported vs unsupported Chapter 4 behavior.
- [ ] Add a corpus crossing definitions, primitives, structures, recursion, q=0 reconstruction, and lazy evaluation.
- [ ] Add static anti-shortcut checks for all faithful-machine files.
- [ ] Update docs with final status and remaining non-Python/Rust/FPGA gaps.
- [ ] Run full Python/Rust gates and commit.

### Task 13: Release/integration gate

**Type:** gate
**Depends-on:** 12

**Files:**
- Test: `tests/`

**Interfaces:**
- Consumes: all prior tasks
- Produces: no code; final verification evidence

- [ ] Run `uv run pytest -q`.
- [ ] Run `uv run ruff check .`.
- [ ] Run `uv run mypy models/python tests`.
- [ ] Run `cargo test -p red2-wasm`.
- [ ] Run `git diff --check` and require clean status.

## Operator smoke

- do: Run the final faithful CLI smoke command once Task 11 exists.
- see: Lambda, passive data, symbol definition, primitive, structure selector, and LETREC examples print Chapter 3-equivalent results.

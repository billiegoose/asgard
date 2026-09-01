# RED2 Head-Flag and Integer Slice Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the faithful Python μRED core in place with RED2 spine-head metadata and direct passive integer execution.

**Architecture:** Add head metadata without changing addresses or register layout, then add `INT` as the first RED2 data instruction. Existing class names remain compatible; the compiler, machine transitions, and result boundary evolve together without evaluator-backed execution.

**Tech Stack:** Python 3.11+, pytest, Ruff, mypy, Thor AST/parser

**Spec:** `docs/superpowers/specs/2026-09-01-red2-head-int-slice-design.md`

**Acceptance:** suite — exact transition, cycle-trace, compiler-layout, semantic-parity, and anti-shortcut tests exercise the complete slice.

## Global Constraints

- Evolve `models/python/red2_engine/mured.py` in place and retain `MuredMachine`, `MuredMachineState`, `MuredOpcode`, and `Word` names.
- `Word.head` is Boolean and defaults to `False` after `data`, preserving existing positional construction.
- Execution operates directly on graph/environment memory and registers; `step()` and `run()` never invoke decompilation, private terms, or the Chapter 3 evaluator.
- APP-VAR compaction, primitives, symbols, floats, characters, structures, recursion, CLI integration, Rust implementation, and FPGA work remain out of scope.
- Existing pure-lambda transition order and semantic behavior remain unchanged apart from head metadata.
- Use ASCII Python/LaTeX source except where the existing module already uses μ or λ in messages.

---

### Task 1: Represent and compile spine-head flags

**Type:** implementation
**Depends-on:** none

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `tests/test_mured_transitions.py`

**Interfaces:**
- Consumes: existing `Word(opcode, data)` and `compile_lambda(expr) -> tuple[Word, ...]`
- Produces: `Word(opcode: MuredOpcode | None, data: int | str | None = None, head: bool = False)` and compiler-emitted head metadata

- [ ] **Step 1: Add failing compiler-layout assertions**

Assert these exact conventions in `tests/test_mured_compile.py`:

```python
assert compile_lambda(parse_expr("(LAMBDA (x) x)")) == (
    Word(MuredOpcode.LAMBDA, "x", False),
    Word(MuredOpcode.VAR, 0, True),
)
assert compile_lambda(parse_expr("((LAMBDA (x) x) (LAMBDA (y) y))")) == (
    Word(MuredOpcode.APP, 3, False),
    Word(MuredOpcode.LAMBDA, "x", False),
    Word(MuredOpcode.VAR, 0, True),
    Word(MuredOpcode.LAMBDA, "y", False),
    Word(MuredOpcode.VAR, 0, True),
)
```

Also assert grouped/nested lambda words are non-head and their body root is head. Run `uv run pytest tests/test_mured_compile.py -q`; verify failure because `Word` lacks `head` or actual flags differ.

- [ ] **Step 2: Add the metadata and compiler contract**

Add `head: bool = False` to `Word`. Change the nested compiler to `compile_graph(node: Expr, scope: tuple[str, ...], *, head: bool)`. Emit:

```python
Word(MuredOpcode.VAR, index, head)
Word(MuredOpcode.LAMBDA, parameter, False)
Word(MuredOpcode.APP, argument_address, False)
```

Compile every operator and separately addressed argument with `head=True`; compile a lambda body with the incoming `head`; start the root with `head=True`.

- [ ] **Step 3: Preserve metadata through machine graph writes**

Ensure copied source words retain their exact head flag. Generated result `VAR` roots from `UBV` use `head=True`; generated `APP`, `JOIN`, environment, closure, and pointer words use `head=False`. Update existing exact word and golden-trace expectations to include the compiler-assigned flags; do not change register/cycle expectations.

- [ ] **Step 4: Verify and commit**

Run:

```bash
uv run pytest tests/test_mured_compile.py tests/test_mured_transitions.py tests/test_mured_fidelity.py -q
uv run ruff check models/python/red2_engine/mured.py tests/test_mured_compile.py tests/test_mured_transitions.py tests/test_mured_fidelity.py
uv run mypy models/python/red2_engine/mured.py tests/test_mured_compile.py tests/test_mured_transitions.py tests/test_mured_fidelity.py
git diff --check
```

Commit as `feat: add red2 spine head flags`.

### Task 2: Execute and reconstruct passive integers

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_compile.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `docs/mured-thesis-notes.md`

**Interfaces:**
- Consumes: `Word(..., head: bool)` and compiler head positions from Task 1
- Produces: `MuredOpcode.INT`, direct `_int(word: Word) -> None`, integer compilation/loading/decompilation

- [ ] **Step 1: Write failing transition tests**

In `tests/test_mured_transitions.py`, construct minimal valid states and assert:

```python
# Forward head INT copies itself, then begins reverse traversal.
assert copied == Word(MuredOpcode.INT, 42, True)
assert (state.direction, state.pc, state.q, state.phi) == (
    Direction.B, state.fsp - 1, original_q, original_phi
)

# Forward non-head INT copies itself and advances through the source spine.
assert copied == Word(MuredOpcode.INT, 7, False)
assert (state.direction, state.pc) == (Direction.F, original_pc + 1)

# Reverse INT changes only pc.
assert state.pc == original_pc - 1
```

Add malformed-data coverage expecting `IllegalTransition` for non-`int` payloads. Run the focused tests and verify failure because `INT` is absent.

- [ ] **Step 2: Implement the literal Chapter 4 transition**

Import `Integer`, add `INT` to `MuredOpcode`, dispatch it from `step()`, and implement:

```python
def _int(self, word: Word) -> None:
    if not isinstance(word.data, int):
        raise IllegalTransition("INT requires an integer value")
    if self.state.direction is Direction.B:
        self.state.pc -= 1
        return
    self._push_graph(word)
    if word.head:
        self.state.pc = self.state.fsp - 1
        self.state.direction = Direction.B
    else:
        self.state.pc += 1
```

Do not alter `q`, `phi`, `env`, `c`, or control memory.

- [ ] **Step 3: Compile, load, and decompile integers**

Extend `compile_lambda()` so `Integer(value)` emits `Word(MuredOpcode.INT, value, head)`. Permit `INT` in `MuredMachine.load()`. In `_decompile()`, return `Integer(word.data), address + 1` after validating `type(word.data) is int` (reject Boolean payloads as malformed integer data).

- [ ] **Step 4: Add end-to-end and boundary coverage**

Add exact compiler/result assertions for:

```text
42
(LAMBDA (x) 42)
((LAMBDA (x) x) 42)
```

Compare the halted μRED/RED2-slice result with Chapter 3 for quantum `10` and `0`. Add a cycle trace for top-level `42` proving the sequence `INT(F) -> STOP(B)` and exact copied word/head flag. Keep the anti-shortcut source scan green.

- [ ] **Step 5: Correct documentation**

Update `docs/thor-red2-prototype.md` to call `red2_engine.mured` a faithful μRED core plus the first RED2 head/INT slice, not full RED2. Extend `docs/mured-thesis-notes.md` with the explicit boundary: source-compiled arguments still use APP pointers; non-head `INT` is implemented for the later single-instruction-argument optimization but that optimization is not claimed.

- [ ] **Step 6: Verify and commit**

Run:

```bash
uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py tests/test_mured_compile.py tests/test_mured_fidelity.py -q
uv run pytest -q
uv run ruff check .
uv run mypy models/python tests
cargo test -p red2-wasm
git diff --check
```

Confirm only the declared files changed and commit as `feat: execute passive integers in mured core`.

### Task 3: Integrated verification gate

**Type:** gate
**Depends-on:** 2

**Files:**
- Test: `tests/test_mured_state.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_compile.py`
- Test: `tests/test_mured_fidelity.py`

**Interfaces:**
- Consumes: cumulative Task 1 and Task 2 implementation
- Produces: no code; fresh integrated validation evidence

- [ ] Run `uv run pytest -q`, `uv run ruff check .`, `uv run mypy models/python tests`, and `cargo test -p red2-wasm`; require zero failures.
- [ ] Run `git diff --check` and require a clean worktree.

## Operator smoke

- do: `uv run python -c 'from red2_engine.mured import MuredMachine; from thor_lang.parser import parse_expr; from thor_lang.pretty import to_source; m=MuredMachine.from_expr(parse_expr("42"), quantum=10); m.run(); print(to_source(m.result_expr()))'`
- see: `42`

- do: Repeat the command with `parse_expr("((LAMBDA (x) x) 42)")`.
- see: `42`

- do: Run `uv run pytest tests/test_mured_fidelity.py -k 'manual_chapter4 or int' -q`.
- see: All selected transition traces pass.

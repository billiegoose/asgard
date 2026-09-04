# 2026-09-02 — RED2 Non-Strict Y Primitive (Task 6)

**Status:** implementation
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 6 — *Non-strict primitive Y*
**Depends on:** Task 5 (`5fcef2b`, selected strict primitive family)

## Goal

Implement the Chapter 4 RED2 `Y` machine transformation directly in `models/python/red2_engine/mured.py`, preserving the non-strict character of the operator and its graph-sharing behavior.

`Y` is a `PRIM_0`, not a strict primitive. It must transform `(Y f)` into `(f (Y f))` without reducing `f` first, consume exactly one unit of quantum when the transformation occurs, and retain a pointer to the original `(Y f)` problem graph rather than copying the recursive expression recursively.

The Chapter 3 evaluator remains an oracle at test boundaries only.

## Source grounding

Chapter 3 Rule 25 gives the semantic contraction:

`(Y e) -> (e (Y e))`, consuming one contraction when `q > 0`.

Chapter 4 specifies the RED2 graph rewrite for a headed `PRIM_0 Y`:

- a non-head `PRIM_0` is passive;
- if `q == 0` or `argcnt < 1`, `Y` is passive and is copied to the result graph;
- otherwise decrement `q` once;
- decrement `pc` so it points at the problem-graph `f` of `(Y f)`;
- overwrite the copied result-graph `f` at `fsp` with `APP` whose data points back to that problem-graph `f`, thereby representing the recursive `(Y f)` argument;
- if problem-graph `f` is `APP`, follow its code pointer directly; its prior APP execution has already pushed the needed path pointer;
- otherwise push the current `env` path, copy `f` temporarily at `fsp + 1`, mark that copy as a spine head, and execute it from that temporary location.

The rewrite intentionally uses problem/result graph sharing. It must not decompile or construct a recursive AST.

## In scope

- Headed `PRIM_0 Y` execution in forward direction.
- Passive `Y` when `q == 0`.
- Passive `Y` when there is no argument (`argcnt < 1`).
- Existing passive behavior for non-head `PRIM_0 Y`.
- Successful rewrite when problem-graph `f` is an `APP`.
- Successful rewrite when problem-graph `f` is not an `APP`, including the temporary headed copy at `fsp + 1` and control-stack path push.
- Bounded semantic parity against Chapter 3 for small `Y` expressions that do not require later `IF`/structure/LETREC slices.

## Out of scope

- `IF`, `AND`, and `OR` non-strict primitive execution.
- Structure and LETREC machinery.
- Any optimization beyond the Chapter 4 temporary-copy rewrite.
- Turning `PRIM_0` into the strict `prim`/`fire` register mechanism.

## Machine behavior

### Dispatch

`_prim()` continues to handle `PRIM_1`/`PRIM_2` strict priming exactly as before. For `PRIM_0`:

- headed `Y` invokes a dedicated `_y()` transition immediately;
- other headed `PRIM_0` names remain passive until their later slices;
- non-head `PRIM_0` remains passive.

### Passive Y

When headed `Y` sees `q == 0` or `argcnt < 1`:

1. copy the `Y` word to the result graph using the normal primitive/passive copy path;
2. begin reverse traversal from `fsp - 1`;
3. do not change `q`, `env`, or control stack.

### Successful Y rewrite

Given the current instruction location `pc` on `Y` and at least one argument:

1. decrement `q` exactly once;
2. set `pc = pc - 1`, which selects problem-graph `f`;
3. replace the result word currently at `fsp` (the copied `f`) with `Word(APP, pc, False)`; this APP is the recursive `(Y f)` argument and therefore is not itself a spine head;
4. inspect problem-graph `f` at `pc`.

If `f.opcode is APP`:

- validate its pointer;
- set `pc = f.data` and continue forward execution;
- do not push another control path, because Chapter 4 relies on the path already pushed when that APP was traversed earlier.

If `f` is not APP:

- push the current `env` path onto the control stack;
- copy `f` to graph memory at `fsp + 1` with `head=True`, preserving its opcode/data/definition;
- leave `fsp` unchanged: Chapter 4 uses `fsp + 1` as temporary executable scratch, not yet as part of the logical result graph;
- leave `argcnt` unchanged for the scratch write;
- set `pc` to the temporary copy and continue forward execution. If executing that temporary head subsequently copies a result, the normal transition will advance `fsp` and update `argcnt` at that time.

The result-memory overwrite of the old copied `f` does not increment `argcnt`; it replaces one already-counted result word.

## Invariants

- Successful `Y` costs exactly one quantum unit before recursive work continues.
- `Y` never sets `prim` or `fire`.
- The recursive edge points into the original problem graph; it does not recursively copy `(Y f)`.
- No AST evaluator/decompiler calls occur in `step()`/`run()`.
- No later non-strict primitive receives semantics in this slice.

## Tests-first acceptance

### Transition tests

Add tests proving:

- q=0 headed `Y` remains passive;
- headed `Y` with `argcnt == 0` remains passive;
- non-head `Y` remains passive;
- non-APP `f` rewrite decrements q, overwrites old result `f` with `APP` pointing to problem `f`, pushes `env`, emits a temporary headed copy at `fsp+1`, and transfers `pc` there;
- APP `f` rewrite decrements q, overwrites old result `f`, follows the APP code pointer, and does not add an extra control-stack entry;
- temporary copy preserves definition metadata where present.

### Fidelity tests

Compare μRED against Chapter 3 at bounded quantum for expressions such as:

- `(Y (LAMBDA (self) 7))`, which should reach `7` when enough quantum is available;
- `(Y (LAMBDA (self) self))` at small bounded quantum, proving recursive identity is retained without Python recursion;
- q=0 `(Y (LAMBDA (self) 7))`, which remains unchanged.

Use only expressions whose reductions depend on already-implemented lambda/application behavior and `Y` itself.

## Documentation

Update `docs/thor-red2-prototype.md` to state that the faithful μRED core now includes the Chapter 4 non-strict `Y` graph transformation. State that `IF`, `AND`, `OR`, structures, and LETREC remain incomplete.

## Validation

Run focused Task-6 tests, then:

- `uv run pytest -q`
- `uv run ruff check .`
- mypy on touched Python/test files
- repo-wide mypy; only the previously known unrelated `tools/videos/generate.py:99` error is acceptable if unchanged
- `git diff --check`
- inspect final diff/status

Commit only Task-6 files and leave `archives/` and unrelated working-tree state untouched.

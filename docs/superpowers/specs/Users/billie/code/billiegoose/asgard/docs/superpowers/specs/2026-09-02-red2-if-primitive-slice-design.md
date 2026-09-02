# 2026-09-02 — RED2 Non-strict Conditional IF (Task 7)

**Status:** design
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 7 — *Non-strict conditional IF*
**Depends on:** Task 5 (strict primitive family)
**Review:** adversarial

## Scope

Land the non-strict `IF` primitive. `(IF cond then else)` reduces `cond` to a value
(TRUE/FALSE symbols), then selects the appropriate branch without forcing the
other branch first — lazy evaluation. q=0 leaves the IF application passive.

## Design choices

- `IF` is compiled as `PRIM_0 "IF"` (arity-3 non-strict primitive).
- The fire path checks `argcnt == 0` (all three arguments present), `fire == 0`
  (condition reduced to a value), `q > 0`, head set, forward direction.
- On TRUE: replace the IF redex head with the then-branch graph (second argument).
- On FALSE: replace with the else-branch graph (third argument).
- Non-boolean condition: stays passive (no branch selected).
- q=0: passive copy only.

## Acceptance

- `(IF TRUE 42 43)` → `42`
- `(IF FALSE 42 43)` → `43`
- `(IF TRUE 42 43)` at q=0 → passive (original application preserved)
- `(IF 42 42 43)` → passive (non-boolean condition)
- `(IF (LAMBDA (x) x) 42 43)` → passive (condition not a value)
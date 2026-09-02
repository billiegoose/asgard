# 2026-09-02 — RED2 Strict Primitive Family Expansion (Task 5)

**Status:** design
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 5 — *Strict primitive family expansion*
**Depends on:** Task 4 (strict ADD firing complete at `b89c0ae`)

## Scope

Extend the primitive table (`_fire_primitive`) to cover the remaining strict binary arithmetic primitives that the current Chapter 3 surface supports: SUBTRACT (`-`), MULTIPLY (`*`), DIVIDE (`/`). Each must use the same two-argument `INT` value contract: both arguments must be reduced to `INT`, `argcnt == 0`, `fire == 0`, `q > 0`, head set, forward direction. After the fire, the head is overwritten with the arithmetic result (`INT`), `fsp` reclaimed by 2, `q` decremented by 1, and the control-stack path restored.

Other strict primitives (comparison predicates, character predicates, float arithmetic, integer/float coercions) remain out of scope for this slice and are deferred to later tasks.

## Design choices

- Keep the primitive table as a small module-level mapping (`PRIM_TABLE`) so new primitives are registered by arity and callable.
- The fire mechanism stays in `_prim()` and delegates to `_fire_primitive()`; no change to register or control-stack wiring.
- Type-check and value-check conditions are identical to ADD: both args must be `INT` with integer `data`.

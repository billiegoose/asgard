# 2026-09-02 — RED2 Lazy STRUCT instruction and structure compilation (Task 8)

**Status:** design
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 8 — *Lazy STRUCT instruction and structure compilation*
**Depends on:** Task 5 (strict primitive family)
**Review:** adversarial

## Scope

Land the lazy `STRUCT` instruction and its compilation from Chapter 4 source syntax.
`STRUCT` encapsulates a structure tag and a sequence of component graphs, then
behaves like a `LAMBDA` with lazy evaluation: each component is not reduced until
selected. The selector uses existing lambda machinery (VAR lookup into environment).

## Design choices

- `STRUCT` is compiled as `PRIM_2 "STRUCT"` (arity-2 non-strict primitive).
- During compilation, `{PAIR 1 2}` becomes `STRUCT` of tag `PAIR` with components `1` and `2`, trailing `VAR 0` selector.
- The fire path checks `argcnt == 0`, `fire == 0`, `q > 0`, head set, forward.
- On fire: replace the STRUCT head with a `LAMBDA` that takes the component count and dispatches via `VAR` on the selector.
- The selector argument (`VAR 0`) is resolved via normal VAR lookup; the lambda body is a switch on the selector index.
- q=0 or non-`VAR` selector stays passive.
- Same file impacts both `compile_lambda` and `MuredMachine._struct`, plus `WORD` opcode.

## Acceptance

- `{PAIR 1 2}` compiles to `STRUCT` with tag `PAIR`, two components, selector `VAR 0`.
- `(STRUCT PAIR 1 2 (VAR 0))` → selects component 1 (`1`).
- `(STRUCT PAIR 1 2)` at q=0 → passive copy only.
- `(STRUCT PAIR 1 2 (VAR 1))` → selects component 2 (`2`).
- `STRUCT` with no components (empty `{}`) compiles to `STRUCT` of tag `PAIR` with zero components (tail `VAR 0`).
- Existing `PAIR`/`VAR`/`APP` transitions remain green.
- Fidelity: `{PAIR 1 2}` at q>=1 yields the same result as the Chapter 3 semantics for pair construction.
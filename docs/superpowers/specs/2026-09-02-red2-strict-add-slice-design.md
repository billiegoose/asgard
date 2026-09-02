# 2026-09-02 — RED2 Strict Primitive Firing, Integer ADD Slice Design

> **Status:** final (Task 4 complete — strict ADD fire landed, spec verified)
> **Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
> **Slice task:** Task 4 — *Strict primitive firing, integer ADD first*
> **Depends on:** Task 3 (primitive registers landed at commit `a423f18`)

## Purpose

Land the first **strict primitive firing** path. After this slice,
`(+ 2 3)` reduces to `5` because `+` fires only when both arguments are
values and the registered arity is satisfied, *exactly* as Chapter 4
prescribes. All previously landed slices (μRED, head flags, APP-VAR,
passive data, SYM, passive `PRIM_n`) remain green.

## Scope

This slice is intentionally narrow:

- it implements the strict `fire` countdown for `PRIM_2`;
- it extends `argcnt` maintenance through APP, APP_VAR, LAMBDA, JOIN, and
  passive data paths so `fire` is correct at every step;
- it fires the first strict primitive: integer `+`;
- it keeps the other strict primitives (subtraction, multiplication, …)
  explicit placeholders that refuse to fire but remain in the table.

The remaining strict primitive family is the next slice (Task 5).

## What Chapter 4 says

`fire` is the countdown that tells the machine how many more passive
*arguments* the registered primitive still owes before it is allowed to
fire. `argcnt` is the live counter; every APP/APP_VAR that consumes a
primitive arg (and every passive/head result that contributes one) bumps
or decrements it in lock-step with `argcnt`. The strict primitive fires
when:

1. its `argcnt` is `0` — i.e. exactly `arity` arguments have arrived;
2. the head flag is set — it is the current redex;
3. the machine direction is **forward**;
4. `q > 0` — quantum permits the fire;
5. every argument is a value (INT, FLOAT, CHAR, SYM, or `VAR` whose
   target is `UBV`-only).

The fire rewinds the result head in place: it overwrites the
`PRIM_2 + integer` head with `INT 5`, claims the saved argument slots
back into the free-space pointer, and finally pops control back to the
reductor path the way a LAMBDA contraction would.

## Acceptance

- `(+ 2 3)` reduces to `5` at `q >= 1`.
- `(+ (LAMBDA (x) x) 1)` with `q >= 1` rewrites the head
  `(+ … 1)` only once `((LAMBDA (x) x))` collapses to a value. The
  intermediate steps keep the partial application as a `PRIM_2` over
  the not-yet-value argument.
- `(+ 2 3)` with `q = 0` is *passive* — both the head and its
  arguments are pushed untouched, `fire` stays at `0`, and the result
  is the original application.
- `(+ 1 #\a)` with `q >= 1` is *also* passive: the second argument
  fails the value predicate, the primitive must not fire.
- Existing passive `SYM`, APP-VAR, lambda and structure traces keep
  passing.
- **Status:** complete (see tests/test_mured_transitions.py, tests/test_mured_fidelity.py, and docs/thor-red2-prototype.md).

## Design choices

- Keep `fire` purely a function of `argcnt` and the *registered arity*.
  We do not introduce a separate "wanted arity" register — the arity
  is `PRIM_0`/`PRIM_1`/`PRIM_2` itself.
- A strict primitive handler in `_prim()` reads the saved control-stack
  path; we already push it during the **passive** copy in
  Task 3. Firing pops that path, restores `env`, and overwrites the
  redex slot exactly the way `_lambda` does for `APP` results.
- The integer addition helper lives in a small module-private table
  `PRIM_TABLE[2]` mapping arity-2 primitives to a callable that
  consumes the value-list and either returns a value or refuses.
  Refusal is *not* an error: it is the q=0 / wrong-type path that
  leaves the partial application passive.

## Files

- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`

## Test plan (failing first, then green)

1. `test_argcnt_decrements_when_app_var_resolves_to_value_ubv` — value
   arguments decrement, not just push.
2. `test_argcnt_increments_when_app_var_resolves_to_app` — partial
   applications *add* to `argcnt` so `fire` can track pending args.
3. `test_prim_fire_when_argcnt_zero_overwrites_redex_with_sum` —
   `(+ 2 3)` rewrites the head `PRIM_2` to `INT 5`.
4. `test_prim_does_not_fire_when_argcnt_positive` — partial argument
   still pending.
5. `test_prim_does_not_fire_when_quantum_zero` — passive even with
   `argcnt == 0`.
6. `test_prim_does_not_fire_when_second_argument_not_value` — passive
   on type mismatch.
7. `test_prim_fire_restores_env_and_advances_to_reductor_path` — control
   stack pop matches `_lambda` rewind.
8. `test_mured_result_matches_chapter3_for_add` — fidelity check.

## Out of scope

- Other strict primitives (subtraction, multiplication, character
  predicates, integer/float coercions) — Task 5.
- Compilation of `+` from a SYM in a richer expression — Task 5 also
  covers the symbol→primitive compilation path.
- LETREC, structure selector, IF, Y — Tasks 6–10.

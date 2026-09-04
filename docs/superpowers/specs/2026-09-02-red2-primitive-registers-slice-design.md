# RED2 Primitive-Register Scaffold and Passive Primitive Opcodes — Task 3

**Status:** design
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 3 — primitive-register scaffold and passive primitive opcodes
**Depends on:** Task 2

## Scope

Add the Chapter 4 primitive-register scaffold without firing a primitive. The faithful μRED state gains `argcnt`, `prim`, and `fire`; source compilation gains `PRIM_0`, `PRIM_1`, and `PRIM_2`; and primitive words can traverse and reconstruct passively. Task 4 owns strict firing, argument-reduction save/restore, and ADD.

## Registers

- `argcnt: int` starts at `0` for a new reduction spine.
- `prim: str | None` starts at `None` and names the strict primitive whose arguments are being reduced.
- `fire: int` starts at `0` and is loaded with a strict primitive's arity when its firing mechanism is primed.
- Negative `argcnt`/`fire` are invalid in this slice. (`RBLOCK` later deliberately uses `argcnt = -1`; Task 9 must widen validation when that mechanism lands.)
- A non-`None` `prim` must be a non-empty symbol name.

## `argcnt` transfers

Chapter 4 says `argcnt` counts arguments in the current spine, is reset when reverse APP begins reducing an argument, increments as instructions are copied to the result graph, and decrements when LAMBDA removes an argument. The RBLOCK discussion explicitly confirms that a copied SYM increments it.

For this slice:

- forward APP copies increment `argcnt`;
- APP-VAR result entries increment `argcnt`;
- forward passive data/SYM/PRIM result copies increment `argcnt`;
- a preserved/unapplied LAMBDA is copied, then resets `argcnt` to `0` before traversal enters its body, because the abstraction body is a new spine and must not inherit an apparent argument from the LAMBDA word itself;
- UBV-generated result VAR entries increment `argcnt`;
- beta contraction by LAMBDA decrements `argcnt` when it removes APP/APP-VAR from the result graph;
- reverse APP resets `argcnt` to `0` before traversing the argument;
- when a copied headed defined SYM is rewritten into its definition-staging APP, decrement `argcnt` once to cancel the SYM copy itself. This slice only supports the existing closed/bare defined-symbol path; rejoining an applied defined symbol to an outer APP remains outside this slice;
- generated JOIN bookkeeping does not itself increment `argcnt`, and JOIN does not otherwise rewrite the counter.

The dissertation says copied instructions increment `argcnt` but does not spell out the balancing transfer when a preserved LAMBDA enters its abstraction body. Without a boundary reset, `(LAMBDA (x) NOT)` falsely presents one argument to `NOT`. This prototype therefore treats entry into a preserved LAMBDA body as a new spine and resets `argcnt` to zero after copying the LAMBDA. Re-check this reconciliation when STRUCT, which is explicitly LAMBDA-like, lands.

## Primitive compilation

Lexical scope wins over primitive recognition. A bound symbol such as `+` compiles as `VAR`, not a primitive.

Current Chapter 3 strict unary primitives compile as `PRIM_1`: `1-`, `1+`, `ABS`, `CAR`, `CDR`, `CEILING`, `EVEN?`, `FLOOR`, `MINUS`, `NULL?`, `NOT`, `TAG`, `INTEGER?`, `FLOAT?`, `CHAR?`, `SYMBOL?`, `STRUCTURE?`.

Current Chapter 3 strict binary primitives compile as `PRIM_2`: `+`, `-`, `*`, `/`, `<`, `>`, `<=`, `>=`, `=`, `CONS`, `EQUAL?`, `EXPT`, `MAX`, `MIN`, `MOD`.

Non-strict built-ins `IF`, `Y`, `AND`, and `OR` compile as `PRIM_0`. Task 3 does not execute them; their dedicated semantics remain later work. `TRUE`, `FALSE`, and `NIL` are constants and remain `SYM`.

## Primitive transitions

- Reverse `PRIM_0/1/2` only walks backward (`pc -= 1`).
- Forward primitive execution copies the word to the result graph and maintains `argcnt` like other passive copies.
- A non-head primitive is passive and continues forward.
- A headed `PRIM_1`/`PRIM_2` checks the pre-copy `argcnt` and `q`. If enough arguments are present and `q > 0`, it loads `prim` and `fire` with the primitive name and arity, respectively, then begins reverse traversal. No primitive fires in Task 3.
- If arity is insufficient or `q == 0`, a headed strict primitive remains unprimed and begins reverse traversal after copying.
- `PRIM_0` is passive in Task 3 even at the head; Task 6/7 implement non-strict invocation.

## Result reconstruction

A passive `PRIM_0`, `PRIM_1`, or `PRIM_2` decompiles to its source `Symbol`, allowing zero-quantum programs containing primitives to round-trip without invoking Chapter 3 semantics.

## Acceptance

- state snapshots/validation cover all three registers;
- compiler tests cover primitive arities, lexical shadowing, and symbolic constants;
- transition tests cover APP/LAMBDA/JOIN/result-copy `argcnt` behavior and PRIM forward/reverse/priming cases;
- a zero-quantum `(+ 2 3)` run reconstructs `(+ 2 3)` unchanged;
- existing μRED tests remain green;
- focused tests, full pytest, Ruff, and mypy pass.

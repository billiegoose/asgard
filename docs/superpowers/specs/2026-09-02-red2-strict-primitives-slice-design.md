# 2026-09-02 — RED2 Strict Primitive Family Expansion (Task 5)

**Status:** implementation
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 5 — *Strict primitive family expansion*
**Depends on:** Task 4 (`dc2e75d`, integer ADD firing)

## Goal

Extend the Chapter 4 strict-primitive firing machinery from integer-only `+` to the selected strict primitive family that can be represented faithfully with the atomic μRED result words already implemented. Preserve direct graph/register execution, Chapter 4 q/type checks, strict-argument reduction, result overwrite, and graph reclamation.

The Chapter 3 evaluator remains the semantic oracle at test boundaries only; `mured.py` must not invoke it during execution.

## Source grounding

Chapter 3 states that unary operators, binary operators, and type predicates over constants are strict: the correct number of arguments are reduced before the primitive may contract. Type predicates produce `FALSE` only when enough information is available; an irreducible application or unbound variable remains undecided.

Chapter 4 gives the machine mechanism shared by strict primitives: `PRIM_1`/`PRIM_2` prime `prim` and `fire` only at a headed spine with sufficient arguments and available q; APP/JOIN save and restore that context while reducing arguments; the primitive itself rechecks q and argument types at fire time. On success the primitive result overwrites the primitive-arguments subgraph, becomes a head node, `fsp` reclaims the discarded operator/arguments, and q decreases by one. On q exhaustion or type failure the compact primitive application remains unchanged and traversal continues. Chapter 4 explicitly notes that real RED2 addition also handles floating-point and mixed integer/float operands even though its pseudocode shows integer ADD only.

The current Chapter 3 implementation defines the exact executable behavior for result typing and mixed numeric operations, including integer-preserving results where appropriate.

## In scope

### Unary numeric primitives

- `1-` — integer only, matching the current Chapter 3 implementation.
- `1+` — integer or float.
- `MINUS` — integer or float.
- `ABS` — integer or float.
- `FLOOR` — integer or float input, integer result.
- `CEILING` — integer or float input, integer result.
- `EVEN?` — integer only, symbolic boolean result.

### Strict logical/list-constant primitives

- `NOT` — contracts only `TRUE` to `FALSE` and `FALSE` to `TRUE`.
- `NULL?` — `NIL` gives `TRUE`; known non-application/non-variable atomic values give `FALSE`; applications/variables remain undecided.

### Type predicates that need no structure representation

- `INTEGER?`
- `FLOAT?`
- `CHAR?`
- `SYMBOL?`

These return `TRUE` on a matching known atomic result, `FALSE` on a known nonmatching atomic/lambda result, and remain unreduced for irreducible applications or variables, matching Chapter 3 partial-evaluation semantics.

### Binary numeric primitives

- `+`
- `-`
- `*`
- `/`
- `<`
- `>`
- `<=`
- `>=`
- `EXPT`
- `MAX`
- `MIN`
- `MOD`

For `+`, `-`, and `*`, two integers produce `INT`; any float operand produces `FLOAT`. `/` follows current Chapter 3 behavior: integer/integer division produces `INT` only when the quotient is integral, otherwise `FLOAT`; mixed numeric division produces `FLOAT`. `EXPT`, `MAX`, and `MIN` use Chapter 3 numeric-result normalization. `MOD` requires two integers. Numeric comparisons return symbolic `TRUE` or `FALSE`.

### Constant equality

- `=` — supports the Chapter 3 constant domain currently representable atomically by μRED: integers, floats, characters, and symbols. Unsupported compound values remain unreduced.

## Explicitly out of scope

The following are already classified as strict by the compiler but are deferred because faithful execution requires graph machinery not present until the structure slice or more complex primitive-specific machinery:

- `CAR`, `CDR`, `CONS`, `TAG`, `STRUCTURE?` — require `STRUCT` representation/construction/access introduced by Task 8.
- `EQUAL?` — Chapter 3 defines this through recursive `EQUAL*` decomposition, alpha-equivalence, conjunction construction, and potentially multiple contractions; it is not a one-step atomic strict primitive.

`IF`, `Y`, `AND`, and `OR` remain non-strict and belong to later tasks.

## Firing and layout rules

All supported primitives reuse the Task-4 priming/countdown mechanism. A handler is invoked only after its strict arguments have been reduced and compacted into the parent result spine. Handlers must not decompile the graph or call Chapter 3 semantics.

At fire time:

1. Recheck `q > 0`.
2. Inspect the compact argument words beginning at `pc` using the same Chapter 4 orientation established by ADD: for a binary primitive, the second source operand is at `pc` and the first source operand at `pc + 1`; for a unary primitive, its sole operand is at `pc`.
3. Validate the exact operand types required by that primitive.
4. If the primitive cannot contract, do not modify the primitive-arguments subgraph and do not decrement q.
5. On success, overwrite the lowest-address argument word at `pc` with the atomic result word and mark it `head=True`.
6. Set `fsp = pc`, thereby reclaiming the operator and consumed strict arguments as in the Chapter 4 ADD example.
7. Decrement q exactly once for the primitive contraction.
8. Continue reverse traversal with `pc -= 1`.
9. Clear `prim`/`fire` regardless of success, as Task 4 already does after countdown reaches zero.

## Result representation

Use only existing atomic result opcodes:

- integer result -> `Word(INT, value, True)`
- floating result -> `Word(FLOAT, value, True)`
- character result, where applicable -> `Word(CHAR, value, True)`
- boolean/symbol result -> `Word(SYM, name, True)`

The result word must be self-contained and must not retain stale definition metadata from an operand.

## Primitive dispatch design

Replace the one-off `_add()` dispatch with a small explicit table or grouped handlers. The table should describe only primitives actually implemented by this slice. Compiler classification may remain broader so deferred primitives continue to compile as `PRIM_1`/`PRIM_2`; when such a primitive reaches fire time without a Task-5 handler, it must remain unreduced rather than being given invented semantics.

Prefer shared helpers for:

- reading/validating atomic numeric words;
- constructing normalized numeric results;
- constructing symbolic booleans;
- common successful overwrite/reclaim/q behavior.

Do not import or call private Chapter 3 primitive helpers from the machine implementation; parity belongs in tests.

## Tests-first acceptance

Add failing transition/fidelity tests before implementation.

### Transition tests

Cover at minimum:

- unary successful fire overwrites at `pc`, sets head, reclaims to `fsp == pc`, decrements q once;
- binary float/mixed numeric fire uses the existing operand orientation and produces the correct opcode/value;
- symbolic boolean result (`<`, `EVEN?`, or `NOT`) is a headed `SYM` and reclaims the primitive spine;
- wrong-type fire leaves the compact primitive application unchanged and preserves q;
- fire-time q exhaustion leaves the compact primitive application unchanged;
- an unimplemented/deferred strict primitive remains unreduced at fire time.

### Chapter 3 parity tests

For every primitive included above, provide at least one successful semantic parity case and q=0 parity coverage. Parameterization is preferred.

Include representative coercion/result-typing cases:

- integer, float, and mixed `+`/`-`/`*`;
- integral and non-integral `/` results;
- `FLOOR`/`CEILING` over float values;
- numeric comparisons over mixed numeric types;
- integer-only `MOD` type rejection;
- constant `=` over matching and nonmatching atomic constants;
- all four non-structure type predicates;
- `NULL?`/`NOT` symbolic results.

Also retain the Task-4 nested strict-argument/q-recheck tests to prove the generalized dispatch does not break primitive context save/restore.

## Documentation

Update `docs/thor-red2-prototype.md` to state that μRED now supports the selected atomic strict primitive family, including float/mixed numeric coercion and atomic predicates. State explicitly that structure-dependent strict primitives and `EQUAL?`, plus all non-strict primitives, remain incomplete.

## Validation

Run focused Task-5 transition/fidelity tests first, then:

- `uv run pytest -q`
- `uv run ruff check .`
- mypy on touched Python/test files
- `uv run mypy models/python tests` (the known unrelated `tools/videos/generate.py` error is outside this command; if a repo-wide command is additionally run, only that previously known error is acceptable if unchanged)
- `git diff --check`
- inspect `git diff` and `git status`

Commit only Task-5 files. Leave `.toolcall-smoke.txt`, `archives/`, and any unrelated working-tree changes untouched.

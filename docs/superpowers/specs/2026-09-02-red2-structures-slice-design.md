# 2026-09-02 — RED2 Lazy STRUCT Instruction (Task 8)

**Status:** complete
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 8 — *Lazy STRUCT instruction and structure compilation*
**Depends on:** Task 5 strict primitive machinery; compatible with Tasks 6–7

## Goal

Implement THOR structure literals directly in the faithful μRED machine. A structure is lazy data: reducing the structure must not spend quantum reducing its fields, but q=0 traversal must still perform environment lookup and beta-substitution inside those fields. Applying a structure to a selector uses the structure's existing lambda-like encoding. Chapter 3 presents structure access as one semantic contraction; the Chapter 4 physical encoding then exposes the selector lambda's ordinary beta contractions separately, so result fidelity is required for selector tests without requiring identical remaining-q bookkeeping between those abstraction levels.

Execution remains graph/register based. The Chapter 3 reducer may be used only as a fidelity oracle at test boundaries.

## Semantic grounding

Chapter 3 Rule 14 reduces every structure field with contractions disabled, then restores the caller's quantum. Chapter 3 Rule 15 applies a structure to a selector and charges one contraction before reducing the selected field.

Chapter 4 gives the compilation rule

`C[{t e1 ... en}, s] = (STRUCT t):(APP C[en,s]):...:(APP C[e1,s]):(VAR 0)`.

`STRUCT` acts like `LAMBDA`, except that an unapplied structure saves q on the control stack, sets q to zero while traversing its fields, and restores q during reverse execution. The trailing `VAR 0` retrieves an applied selector closure; without an argument, the STRUCT installs an UBV so the trailing variable reconstructs the structure wrapper.

## Compiler layout

For `{PAIR 1 2}` the faithful compiler emits, in order:

1. `STRUCT PAIR`;
2. APP pointing to field `2`;
3. APP pointing to field `1`;
4. headed `VAR 0`;
5. headed field `2` graph;
6. headed field `1` graph.

Field APPs are always explicit APP instructions as specified by Chapter 4; unlike ordinary application arguments, a bare variable field is not compiled as APP_VAR in the structure spine. The runtime encoding reserves De Bruijn index 0 for STRUCT's synthetic selector binding, so source variables in field subgraphs are compiled through a synthetic scope slot: an outer source `VAR 0` becomes field `VAR 1`, while binders introduced inside a field remain nearest as usual. This is the concrete indexing needed for the Chapter 4 `STRUCT ... (VAR 0)` encoding to preserve the Chapter 3 requirement that free variables in fields still beta-substitute.

STRUCT is not a source-level binder; the synthetic slot exists only in the encoded graph and is removed again when decompiling a result structure.

## Unapplied STRUCT transition

When `STRUCT` executes forward with `argcnt == 0`:

1. push a typed saved-quantum entry on the control stack;
2. set `q = 0`;
3. copy the STRUCT instruction into the result graph;
4. reset `argcnt` for the new structure spine;
5. increment `phi` and allocate `UBV phi` in the environment, exactly as an unapplied LAMBDA supplies the trailing `VAR 0`;
6. continue forward at the first field APP.

Field APP/JOIN traversal then runs with q=0. No primitive, symbol definition, beta redex, Y, or IF contraction inside a field may fire, but VAR/closure/UBV traversal still performs the substitution required by Rule 14.

When reverse traversal reaches that copied STRUCT, it restores q from the typed control-stack marker, removes that marker, resets the structure's temporary binder depth, and continues reverse traversal below the structure wrapper. The reconstructed result remains a STRUCT graph, not an ordinary lambda.

## Applied STRUCT transition

When `STRUCT` executes forward with `argcnt > 0`, its nearest result-spine argument is the selector. It behaves like the contracting branch of LAMBDA:

- if q is zero, it cannot contract and follows the unapplied/passive reconstruction behavior;
- if q is positive, consume one contraction;
- for an APP selector, pop its saved environment path and allocate a closure containing that path and selector graph address;
- for an APP_VAR selector, allocate the corresponding UBV binding without popping an APP path, following the existing LAMBDA APP_VAR convention;
- reclaim the consumed selector slot, decrement `argcnt`, and continue into the STRUCT component spine.

The trailing `VAR 0` then dereferences the selector. A selector lambda receives the fields as its arguments through the structure's APP component spine, so existing LAMBDA machinery performs field selection without a structure-specific accessor evaluator.

## Result decompilation

A halted result rooted at STRUCT is decompiled back to `StructLit(tag, fields)`, recognizing the STRUCT + reversed APP-field spine + trailing VAR 0 encoding. Result decompilation is observational tooling only and is never called by `step()` or `run()`.

## Invariants

- Structure fields consume zero quantum while the structure itself is merely reconstructed.
- Free variables in structure fields still participate in beta-substitution at q=0.
- Applying a structure to a selector consumes one STRUCT contraction; the encoded selector lambda may then consume its own ordinary beta contractions, so Chapter 4 physical remaining-q need not equal Chapter 3 Rule 15's collapsed accessor accounting.
- Field order is preserved across reversed APP compilation.
- STRUCT uses a typed saved-quantum marker so environment-path pops cannot confuse q with an address.
- Earlier APP/LAMBDA/primitive/Y/IF behavior remains unchanged.

## Tests-first acceptance

### Compile tests

- `{PAIR 1 2}` emits `STRUCT`, reversed field APPs, trailing headed `VAR 0`, then field graphs.
- A structure field containing a bound source variable is compiled in the surrounding scope.
- Result decompilation round-trips a structure literal.

### Transition tests

- Unapplied STRUCT pushes q, sets q=0, copies itself, allocates an UBV, and continues into fields.
- Reverse STRUCT restores the saved q and binder depth.
- Applied STRUCT with APP selector creates the selector closure and charges one q.
- q=0 applied STRUCT does not contract.

### Fidelity tests

Compare μRED with Chapter 3 for:

- `{PAIR (+ 1 2) (* 3 4)}` at positive q: arithmetic remains lazy and q is unchanged;
- `((LAMBDA (x) {PAIR (+ x 1) x}) 5)`: x is substituted inside lazy fields without field arithmetic firing after the beta contraction;
- `({PAIR 1 2} (LAMBDA (CAR CDR) CAR))`: selector returns `1`;
- `({PAIR (+ 1 2) (+ 3 4)} (LAMBDA (CAR CDR) CDR))`: only the selected field becomes available for ordinary reduction after extraction;
- q=0 structure reconstruction remains passive and preserves q.

## Documentation and validation

Update `docs/thor-red2-prototype.md` to include faithful lazy STRUCT support. `AND`/`OR`, LETREC/REC machinery, and CLI integration remain incomplete. Run focused tests, full pytest, Ruff, touched-file mypy, repo-wide mypy (allowing only the unchanged known `tools/videos/generate.py:99` issue), and diff checks. Commit only Task-8 files; leave `archives/` untouched.

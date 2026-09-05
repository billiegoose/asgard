# 2026-09-02 — RED2 LETREC / RBLOCK / RUP Construction (Task 9)

**Status:** complete
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 9 — *LETREC compile scaffold and RBLOCK/RUP construction*
**Depends on:** Task 8 structures; existing environment allocation, control stack, q, phi, and SYM copying

## Goal

Add the Chapter 4 machine scaffold for mutually recursive `LETREC` without implementing recursive-variable reduction or LETREC reconstruction yet. This slice compiles LETREC into `RBLOCK`/`RUP` graph code, constructs the recursive environment when quantum is available, and prepares the unbound-variable/control context when q is exhausted. `RECP` is represented but execution is deliberately rejected until Task 10.

Execution remains graph/register based. No machine transition may call decompilation or the Chapter 3 evaluator.

## Semantic grounding

Chapter 4 gives the compilation rule

`C[(LETREC ((x1 e1) ... (xn en)) e), s] = (RBLOCK (SYM x1):C[e1,s']): ... : (RBLOCK (SYM xn):C[en,s']):(RUP n):C[e,s']`,

where `s' = x1:...:xn:s`.

Each `RBLOCK.data` points to the leading `SYM xi` word. That symbol is present only for later decompilation. When q is positive, the REC created for the binding stores `RBLOCK.data + 1`, deliberately skipping the leading SYM when the binding expression is eventually reduced. When q is zero, reverse RBLOCK traversal will later begin at the SYM and use `argcnt = -1` so copying that synthetic SYM returns `argcnt` to zero.

Chapter 3 Rule 26 describes the recursive context as REC objects containing a binding-expression reference, a pointer to the whole recursive context, and a BLOCK reference. Chapter 4 realizes each REC as three environment words. Forward `RBLOCK` reserves/fills the first word and `RUP` fills the remaining two words.

## Compiler layout

Binding RBLOCKs remain in source order. Binding graphs are emitted after the LETREC body, as pointer targets, and each begins with `SYM <binding-name>` followed by the compiled binding expression.

For `(LETREC ((x 1)) x)` the compiler emits:

1. `RBLOCK <binding-x-SYM-address>`;
2. `RUP 1`;
3. headed `VAR 0` for the body;
4. `SYM x`;
5. headed `INT 1`.

For multiple bindings, executable De Bruijn indices follow the physical redex-store order. The environment grows downward, so source-order RBLOCK execution leaves the last binding nearest to `env`. As with grouped LAMBDA compilation, the compiler therefore uses the physical binder scope `reversed(binding_names) + outer_scope`. For `(LETREC ((x y) (y x)) x)`, `y` is runtime index 0 and `x` is runtime index 1; the body is therefore `VAR 1`, binding `x` contains `VAR 0`, and binding `y` contains `VAR 1`.

This is a machine-encoding adjustment only. The source-level Chapter 3 translation still describes `s' = x1:...:xn:s`.

## q > 0 construction

Forward RBLOCK with quantum available:

1. reserves three consecutive words by moving `env` downward by three;
2. writes `REC` at the new `env` with data `RBLOCK.data + 1`;
3. leaves two data-only placeholder words for RUP;
4. advances `pc` to the next RBLOCK/RUP instruction;
5. consumes no quantum.

Forward RUP with data `n` then walks the `n` REC triples starting at the current `env`. For each REC it writes:

- word `REC+1`: pointer to the completed recursive context (`env`);
- word `REC+2`: pointer to the start of the BLOCK construct (`pc - n`).

RUP then advances `pc`. Creating the recursive context is not itself a contraction and does not decrement q.

## q = 0 preparation

Forward RBLOCK with exhausted quantum does not create a REC. Instead it:

1. copies the RBLOCK into the result graph so the LETREC can be reconstructed;
2. increments `phi`;
3. allocates `UBV phi` in the environment;
4. advances `pc`.

Forward RUP with data `n` pushes the current environment path `n` times on the control stack, once for each copied RBLOCK, copies the RUP instruction into the result graph, and advances `pc`. As with other copied instructions in RED2, that copy increments `argcnt`; Task 9 does not add an extra normalization that is absent from the Chapter 4 procedure. These saved paths are consumed by later reverse RBLOCK traversal/reconstruction machinery.

Task 9 widens the state invariant to permit `argcnt == -1`, because Chapter 4 RBLOCK reverse traversal uses that temporary value to cancel the synthetic binding-name SYM. Values below -1 remain invalid. The complete reverse-RBLOCK/RECP reconstruction path is completed in Task 10.

## REC representation boundary

`REC` is environment data, not executable problem-graph code. Its three words are:

1. `Word(REC, binding_expression_address)`;
2. `Word(None, recursive_context_address)` after RUP;
3. `Word(None, block_address)` after RUP.

The original μRED LOOKUP procedure predates REC and describes non-UBV values as two-word closures. Task 9 does not extend variable dereference into REC values; Task 10 owns REC-aware lookup, RECP generation/access, and reconstruction. Attempting to execute a RECP in this slice raises an explicit `IllegalTransition` rather than silently treating it as ordinary graph data.

## Invariants

- LETREC compilation is graph-only and never calls the evaluator.
- RBLOCK pointers address the leading binding-name SYM; REC binding pointers skip it by one word.
- Recursive-context construction consumes zero quantum.
- q=0 LETREC setup allocates UBVs and preserves the reconstructible RBLOCK/RUP graph.
- `REC` occupies exactly three contiguous environment words.
- Source-order binding names are preserved in RBLOCK/SYM layout even though executable indices use physical environment order.
- `argcnt == -1` is a valid transient RBLOCK value; `argcnt < -1` is invalid.
- RECP execution remains intentionally unsupported until Task 10.
- Earlier APP/LAMBDA/primitive/Y/IF/STRUCT behavior remains unchanged.

## Tests-first acceptance

### Compile tests

- One-binding LETREC emits RBLOCK, RUP, body, then a SYM-prefixed binding graph with correct pointers.
- Two-binding LETREC preserves source-order RBLOCK/SYM layout and uses physical recursive-binding De Bruijn indices consistently in body and binding graphs.

### Transition/state tests

- q>0 RBLOCK reserves a partial three-word REC and RUP fills its recursive-context/BLOCK pointers without charging q.
- q=0 RBLOCK copies itself and allocates an UBV; RUP pushes one environment path per RBLOCK and copies itself.
- The state validator accepts transient `argcnt = -1` but rejects values below -1; `fire` remains non-negative.
- Executing RECP raises an explicit unsupported-transition error.

## Deferred to Task 10

Task 10 implements REC-aware recursive-variable access, RECP forward/reverse behavior, reverse RBLOCK traversal required by reconstruction, RECONSTRUCT, LETREC result decompilation, and Chapter 3 fidelity tests for recursive reduction prefixes.

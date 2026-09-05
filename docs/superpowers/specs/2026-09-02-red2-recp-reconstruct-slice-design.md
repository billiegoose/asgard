# 2026-09-02 — RED2 RECP Access and LETREC Reconstruction (Task 10)

**Status:** complete
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 10 — *RECP access and LETREC reconstruction*
**Depends on:** Task 9 `LETREC` compilation plus `RBLOCK`, `RUP`, and three-word `REC` construction

## Goal

Complete Chapter 4 local mutual recursion in the faithful Python RED2 machine. A variable dereference that lands on a `REC` becomes a `RECP` access; headed `RECP` follows the saved binding expression when quantum remains, while exhausted quantum reconstructs a `LETREC` around that recursive variable. Reverse `RECP` and `RBLOCK` behavior must preserve the ordinary graph/control-stack traversal rules.

Execution remains graph/register/environment based. `step()` and `run()` must not invoke result decompilation or the Chapter 3 evaluator.

## REC-aware lookup

Task 9 introduced the physical recursive-context value as three consecutive environment words:

1. `Word(REC, binding_expression_address)`;
2. data-only word containing the recursive-context path;
3. data-only word containing the first `RBLOCK` address.

`LOOKUP` must therefore advance by three words when skipping a `REC`, by two for a closure, and by one for a `UBV`. Parent pointers remain transparent.

A headed `VAR i` whose lookup lands on `REC r` does not execute the environment word directly. It executes an equivalent headed `RECP r`, preserving the RED2 rule that RECP points at the REC construct. The same representation is used for an optimized single-variable argument: an `APP_VAR` landing on a REC emits a non-head `RECP r` in the result graph, analogous to the existing closure/UBV optimized paths.

## RECP forward execution

For `RECP r` in forward direction:

- `r` must address a three-word REC value.
- If `head == False`, copy the RECP into the result graph and continue forward. It consumes no quantum.
- If `head == True` and `q > 0`, consume one quantum, restore the recursive-context path from `REC+1`, and continue at the binding-expression pointer stored in the REC word. A parent-node pointer is allocated so that reductions performed inside the binding expression see the saved recursive context while preserving the caller's surrounding environment path.
- If `head == True` and `q == 0`, call RECONSTRUCT instead of entering the binding expression.

## RECP reverse execution

For a reverse RECP with quantum available, Chapter 4 converts the copied RECP into an `APP` pointing at the binding expression, pushes the LETREC recursive-context path for later argument traversal, and consumes one quantum. This is the non-head analogue of headed RECP indirection.

If reverse RECP reaches exhausted quantum, it must preserve any active primitive firing context exactly as APP/RBLOCK argument traversal does, place a JOIN, and reconstruct the LETREC-wrapped variable as the argument result.

## RECONSTRUCT

RECONSTRUCT receives the address of a REC through the current RECP. It:

1. reads the first-RBLOCK pointer from `REC+2`;
2. scans/copies the consecutive source `RBLOCK`s to the result graph, preserving each binding-code pointer;
3. counts the bindings and verifies the following source word is matching `RUP n`;
4. creates a replacement environment path in which the recursive-context REC values are represented by `UBV`s, attached to the caller's environment through a `PNP`;
5. pushes one replacement-environment path per copied RBLOCK for their later reverse traversal;
6. copies `RUP n`;
7. emits a headed `VAR` selecting the same recursive binding in the reconstructed LETREC;
8. begins reverse traversal of the reconstructed graph.

The emitted variable index follows the physical RED2 environment order. With source-order RBLOCKs, the last binding is nearest the environment and therefore index 0.

## Reverse RBLOCK

Reverse `RBLOCK` restores the path saved by q=0 RUP/RECONSTRUCT, saves active primitive firing state when necessary, places a `JOIN` whose parent is the copied RBLOCK, jumps to the RBLOCK's SYM-prefixed binding graph, and sets `argcnt = -1`. The synthetic leading binding-name `SYM` then copies itself and returns `argcnt` to zero before the binding expression is traversed.

The JOIN result updates the RBLOCK's binding pointer just as an APP argument JOIN updates an APP pointer; this keeps reconstructed binding expressions in the result graph without involving decompilation.

## Result decompilation

A completed result graph beginning with one or more consecutive `RBLOCK`s followed by matching `RUP n` decompiles to `LetRec`:

- each binding name comes from the leading `SYM` at its RBLOCK target;
- each binding expression begins immediately after that SYM;
- the body begins after RUP;
- recursive scope uses the physical reversed binding-name order while returned `LetRec.bindings` preserve source RBLOCK order.

This decompiler support is only a result boundary. Machine transitions never call it.

## Invariants

- `REC` remains environment-only data and occupies exactly three words.
- Skipping a REC in lookup advances by three words.
- A RECP's data always points to the REC word, not directly to binding code.
- Entering a recursive binding costs exactly one quantum; constructing/reconstructing its context does not.
- q=0 reconstruction produces a genuine RBLOCK/RUP result graph and UBV replacement environment.
- RECONSTRUCT preserves the selected recursive binding's identity.
- Reverse RBLOCK starts binding traversal at its synthetic `SYM` with `argcnt = -1`.
- No faithful-machine transition invokes Chapter 3 evaluation or result decompilation.

## Tests-first acceptance

### Transition tests

- LOOKUP skips a three-word REC when selecting a later value.
- headed VAR landing on REC executes a headed RECP access.
- non-head RECP copies itself without charging quantum.
- headed RECP with q>0 enters the saved binding expression/context and charges one quantum.
- reverse RECP with q>0 converts to APP and saves the recursive-context path.
- headed RECP with q=0 reconstructs RBLOCK/RUP/VAR plus UBV replacement context.
- reverse RBLOCK begins SYM-prefixed binding traversal with `argcnt = -1`.

### Fidelity tests

- bounded-quantum simple LETREC results match Chapter 3.
- the dissertation's alternating infinite-pair example at quantum 1 produces `[1 | (LETREC ((x [1 | y]) (y [2 | x])) y)]`.
- q=0 preserves an unreduced LETREC modulo normal pretty-printing.

## Deferred

Task 11 exposes the faithful machine through the CLI. Task 12 performs final integrated conformance review and unsupported-behavior declaration.

# RED2 Strict ADD Slice Design

## Goal

Implement the Chapter 4 strict-primitive firing mechanism in `models/python/red2_engine/mured.py`, with integer `+` as the first firing primitive. Execution remains direct graph-memory/register execution; no evaluator-backed shortcut is permitted.

## Thesis contract

Chapter 4 requires a strict primitive to be at a spine head, have enough arguments, have those arguments reduced, have acceptable argument types, and have quantum available. `PRIM_2` primes `prim` and `fire=2` only when the first two conditions and initial quantum check hold.

During reverse traversal, each argument reduction is isolated from the parent firing mechanism. Before reverse APP descends into an argument, an active `prim`/`fire` context is saved on the control stack and the live primitive registers are cleared. JOIN restores that context after the argument returns, decrements `fire`, and fires `prim` when the countdown reaches zero. Inert `(None, 0)` contexts are not materialized because there is no primitive state to preserve.

The control stack keeps primitive state as two typed entries, corresponding to the two saved register words, so environment path integers cannot be confused with primitive-register values.

## Single-instruction argument compaction

The RED2 head flag generalizes the single-instruction-argument idea beyond the earlier VAR-specific APP-VAR optimization. When JOIN returns a one-word headed result while a strict primitive firing context is saved, the result can occupy the parent APP slot directly and the temporary JOIN/result tail is reclaimed. The inserted word is marked non-head because it is now an argument in the primitive's parent spine. A one-word VAR continues to use the existing APP-VAR representation. General head-flag compaction outside strict primitive argument reduction remains outside this slice because the existing LAMBDA path does not yet consume arbitrary non-head atomic argument variants.

This reconciliation is required by the dissertation's ADD address contract: when a binary primitive fires, `pc` points at its second reduced operand and `pc+1` at its first. After both one-word integer arguments have rejoined, the parent spine is therefore contiguous as second operand, first operand, headed PRIM_2.

If a reduced argument is not one word, JOIN retains the existing APP-pointer reconstruction path. Such an APP at an ADD operand position naturally fails the primitive's type check and leaves the application unreduced.

Because failed/q=0 strict applications may now halt in a mixed spine containing APP/APP_VAR entries plus non-head atomic argument words, result decompilation must reconstruct those inline atomic arguments as ordinary source application arguments.

## Integer ADD

When `fire` reaches zero for `prim == "+"`, ADD executes with `pc` at the second operand:

1. Check `q > 0` and that both `pc` and `pc+1` are `INT` words.
2. On success, write the integer sum at `pc` with `head=True`.
3. Set `fsp = pc`, reclaiming the first operand, primitive operator, and any higher temporary graph words.
4. Decrement `q` once.
5. Whether the operation succeeds or fails, continue reverse traversal with `pc -= 1`.

A type failure or exhausted quantum does not modify the primitive-argument spine. The firing registers are disarmed after the firing attempt so traversal cannot fire the same primitive twice.

Other strict primitive names may still prime in this slice, because primitive classification already exists. When their countdown reaches zero they are disarmed without contraction; Task 5 owns their actual firing implementations.

## Acceptance

Tests must prove:

- reverse APP saves and clears an active primitive context before argument reduction;
- JOIN restores that context and decrements the countdown once per returned argument;
- one-word integer results compact into parent APP slots and reclaim JOIN/result tail space;
- `(+ 2 3)` fires only after both arguments return and yields headed `INT 5` with one quantum consumed by ADD;
- nested `(+ (+ 1 2) 3)` preserves the outer firing context while the inner ADD uses the live primitive registers;
- if strict argument reduction consumes the last quantum, the outer ADD re-checks `q` at fire time and remains unreduced;
- `q=0` leaves `(+ 2 3)` unreduced;
- a wrong-type application such as `(+ 2 TRUE)` remains unreduced;
- failed applications decompile correctly from compact/mixed result spines;
- earlier μRED, APP-VAR, passive data, symbol, and primitive-register tests remain green.

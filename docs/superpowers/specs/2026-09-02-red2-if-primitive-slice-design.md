# 2026-09-02 — RED2 Non-Strict IF Primitive (Task 7)

**Status:** implementation
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 7 — *Non-strict conditional IF*
**Depends on:** Task 5 strict primitive machinery; compatible with Task 6 `Y`

## Goal

Implement THOR/RED2 `IF` directly in the faithful μRED machine. `IF` is ternary and mixed-strictness: the condition is reduced normally, while the true and false branches remain lazy until a boolean condition selects one of them.

For a non-boolean condition, neither branch may consume quantum. The machine must nevertheless traverse the branch graphs at q=0 so normal RED2 substitution/reconstruction behavior is preserved, then restore the quantum available after reducing the condition.

The Chapter 3 evaluator is an oracle only at test boundaries; execution may not call it or decompile terms.

## Semantic grounding

Chapter 3 Rules 22–24 specify:

- `(IF TRUE e_t e_f)` consumes one contraction and continues with `e_t` when q > 0;
- `(IF FALSE e_t e_f)` consumes one contraction and continues with `e_f` when q > 0;
- the condition is always reduced before either branch;
- when the reduced condition is neither `TRUE` nor `FALSE`, both branches are reconstructed at q=0 and the quantum remaining after condition reduction is retained;
- if the quantum is exhausted after condition reduction, even a boolean condition cannot select a branch and the IF is reconstructed.

Chapter 4 classifies `IF` as a non-strict primitive that is strict only in its first operand. `PRIM_0` operators at a spine head invoke their individual control behavior; non-head `PRIM_0` remains passive.

## Result-spine layout

`compile_lambda()` reverses application arguments before the headed operator. Immediately after the IF head is copied, the result spine for `(IF condition true false)` is therefore, from lower to higher graph addresses:

1. false-branch APP/APP_VAR slot;
2. true-branch APP/APP_VAR slot;
3. condition APP/APP_VAR slot;
4. headed `PRIM_0 IF`.

The nearest reverse APP is the condition. Existing primitive save/restore and JOIN compaction can therefore force only the condition by setting `prim = "IF"` and `fire = 1` before reverse traversal begins.

## Dispatch and condition forcing

For a headed `PRIM_0 IF` with at least three arguments and q > 0:

1. set `prim = "IF"` and `fire = 1`;
2. copy the IF instruction normally;
3. enter reverse traversal at the condition slot.

Existing APP/JOIN behavior evaluates the condition, compacts it back into its argument slot, restores the IF primitive context, decrements `fire` to zero, and invokes `_fire_primitive()` at the compacted condition.

If q is initially zero, or fewer than three arguments are present, IF remains passive. This follows Chapter 4's strict firing rule that the quantum is checked before the firing mechanism is primed. Other `PRIM_0` operators retain their existing behavior.

## Boolean branch selection

At IF fire time, let `pc` be the compacted condition slot, `true_slot = pc - 1`, and `false_slot = pc - 2`.

If q > 0 and the condition is `TRUE` or `FALSE`:

1. consume exactly one unit of q for the IF contraction;
2. identify the selected branch slot;
3. remove the saved APP path pointers belonging to both lazy branches from the control stack;
4. for an APP branch, reclaim the entire IF result spine by setting `fsp = false_slot - 1`, install the selected branch's saved environment path directly in `env`, reset `argcnt`, set `pc` to the selected APP's code pointer, and continue forward; this evaluates the chosen branch as the replacement result without creating a JOIN that could remain visible at the new root;
5. for an already-inline/non-APP branch representation, move it to `false_slot` and make that the compact result.

No instruction from the discarded branch is executed. Directly entering the selected APP code is equivalent to ordinary reverse APP entry except that no parent APP/JOIN is required: the IF itself is disappearing, so the branch result is now the replacement graph rather than an argument result that must later be rejoined to a parent.

## q exhausted after condition

If the condition is boolean but q is zero when IF fires, the IF cannot contract. Leave the compacted IF result spine unchanged, discard the saved APP path pointers for both lazy branches, and jump reverse traversal below the two branch slots. The branches are not traversed at all: unlike Rule 24's non-boolean case, an exhausted boolean IF must preserve them exactly as lazy operands and must not perform q=0 substitution inside them.

## Non-boolean reconstruction

If the reduced condition is not `TRUE` or `FALSE`:

- preserve the q remaining after condition reduction;
- set q to zero while reconstructing branch APPs;
- APP_VAR branch slots need no extra forcing: their initial forward traversal has already performed the applicable environment lookup/substitution;
- use the existing `prim`/`fire` APP/JOIN save-restore mechanism to count only branch slots whose current result opcode is APP;
- keep the saved quantum in a typed control-stack marker inserted immediately below the branch APP path pointers, so ordinary APP path pops still see integer environment paths;
- after the last branch APP returns through JOIN, restore q from that marker and continue reverse traversal below the IF subgraph.

If neither branch is APP, no q=0 reduction is required and q can remain unchanged while reverse traversal passes through APP_VAR slots.

This internal reconstruction continuation is machine-only state; it is not a source primitive and must never appear in decompiled output.

## Invariants

- Only the condition is forced before boolean selection.
- A successful boolean IF selection costs exactly one contraction in addition to any condition work.
- The unselected branch consumes no quantum and is never traversed.
- Non-boolean branches consume no quantum but still receive q=0 graph traversal/substitution where they are APPs.
- Quantum after a non-boolean condition is restored exactly.
- `IF` does not alter `Y`, `AND`, or `OR` behavior.
- Execution remains graph/register based and does not call Chapter 3 evaluation or result decompilation.

## Tests-first acceptance

### Transition tests

Add tests proving:

- headed IF primes exactly one strict argument when arity/q permit;
- q=0 and missing-argument IF remain passive;
- TRUE selection consumes one q, reclaims the IF spine, discards the false path, and retains only the true branch path;
- FALSE selection mirrors TRUE and retains only the false branch path;
- boolean IF with q exhausted at fire time reconstructs instead of selecting;
- non-boolean IF enters q=0 branch reconstruction and later restores q.

### Fidelity tests

Compare μRED to Chapter 3 for:

- `(IF TRUE (+ 1 2) (+ 100 200))` with a quantum that proves the false branch is not forced;
- `(IF FALSE (+ 100 200) (+ 4 5))` likewise;
- `(IF (= 1 1) (+ 1 2) (+ 3 4))`, proving the condition is reduced first;
- q=0 reconstruction;
- a condition that consumes the last quantum and becomes boolean, leaving `(IF TRUE ...)` unreduced;
- a non-boolean condition with reducible branches, proving branch arithmetic does not fire;
- a lambda/environment case where q=0 branch reconstruction still substitutes variables.

## Documentation and validation

Update `docs/thor-red2-prototype.md` to include non-strict IF and leave `AND`/`OR` as pending. Run focused tests, full pytest, Ruff, touched-file mypy, repo-wide mypy (allowing only the unchanged known `tools/videos/generate.py:99` issue), and `git diff --check`. Commit only Task-7 files; leave `archives/` untouched.

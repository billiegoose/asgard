## μRED source reconciliations

1. Reverse `APP` creates `JOIN(parent_app)` because Figure 4.9 draws that pointer and `JOIN` later dereferences it, although the APP pseudocode only assigns the opcode.
2. A non-contracting forward `LAMBDA` advances `pc` after copying itself and allocating `UBV`; omission would repeat the same instruction forever.
3. Reverse `STOP` advances `pc` from the sentinel to the first result word before halt so the halted `pc` identifies the result root as the execution-model prose requires.

Boundary: `APP_VAR` is implemented in this slice, but full RED2 still remains incomplete. Non-head `INT` is nevertheless implemented literally now so the later optimization has the needed transition, but the optimization itself remains out of scope.

These are narrow reconciliations of internally incomplete pseudocode, not evaluator shortcuts.

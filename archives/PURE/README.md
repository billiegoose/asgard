# PURE

An early **pure lambda-calculus** instruction layer for the PC-Scheme lambda-processor simulator.

## Files

- `INSTRUCT.S` — 346-line instruction-set implementation dated 9 February 1989. Handles basic head/root traversal, environment lookup, bindings, pointers, variables, start/stop, etc., without the later functional primitive machinery seen in `FP/`.
- `INSTRUCT.FSL`, `INSTRUCT.SO` — historical PC-Scheme compiled forms.
- `SCHEME.INI` — startup script loading the shared `COMMON/` and `WINDOWS/` simulator pieces plus this instruction set.

## Relationship to other branches

The apparent progression is `PURE` → `FP` → `RED`: `FP/INSTRUCT.S` is substantially larger, and `RED/INSTRUCT.S` expands it further for logic/unification experiments.

This makes `PURE/` useful when trying to isolate the minimal graph-reduction mechanism from later primitive and logic machinery.

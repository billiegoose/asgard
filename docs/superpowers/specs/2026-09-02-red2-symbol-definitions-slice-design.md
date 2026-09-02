# RED2 Symbol Definitions Slice Design

## Goal

Extend `models/python/red2_engine/mured.py` in place with the Chapter 4 `SYM` definition path so closed symbol definitions can be represented and executed directly without broadening the faithful surface to the later RED2 machinery.

## Scope

This slice adds:

- minimal symbol-definition metadata on `Word` or a side table;
- head `SYM` execution when a definition is present and quantum remains;
- conversion of a defined `SYM` back into an executable `APP` node during reverse traversal;
- control-stack path saving for the definition jump;
- continued passive behavior for `SYM` when quantum is exhausted or the symbol is not at the head;
- fidelity coverage against the Chapter 3 definition context for the closed-definition case.

Out of scope: primitive firing, structures, recursion, LETREC/RBLOCK/RUP, CLI integration, Rust, evaluator shortcuts, or general definition-table management beyond the closed-definition path used in this slice.

## Transition Semantics

This slice distinguishes two `SYM` cases:

- **No definition present or non-head / `q = 0`:** `SYM` remains passive, copying the word, preserving `head`, and following the existing forward/reverse passive-data behavior.
- **Closed definition present at the head with `q > 0`:** the symbol begins definition execution by entering the definition graph, preserving the closed-definition boundary, and saving the control path needed to return through the original spine.

The implementation should keep `step()` and `run()` graph/register based; no evaluator or decompilation calls may be introduced into the execution path.

## Validation

Tests must cover:

- explicit definition metadata on `Word`;
- head `SYM` with definition and `q > 0` entering the definition path;
- `q = 0` and non-head `SYM` remaining passive;
- reverse `SYM` converting into `APP` for the defined case;
- parity with Chapter 3 on a closed defined symbol at normal and zero quantum;
- docs stating exactly which RED2 surface remains incomplete after this slice.

# FP

The **functional-programming** instruction/primitive layer for the PC-Scheme lambda-processor simulator.

This directory loads the shared machinery in `COMMON/` and the UI in `WINDOWS/` through `SCHEME.INI`.

## Files

- `INSTRUCT.S` — 572-line lambda-processor instruction implementation, dated 12 May 1989. Implements graph traversal, environment lookup, bindings, pointers, symbols, variables, primitive instruction classes, structures, start/stop, and related machine behavior.
- `PRIMITIV.S` — primitive semantics for arithmetic, comparisons, `IF`, `Y`, boolean operations, structures, etc.
- `FUNS.S` — small test/example library using `ldefine`, including factorial, `Y`, lists, and bottom.
- `SCHEME.INI` — PC-Scheme startup script loading `COMMON`, `WINDOWS`, and this directory's instruction/primitive files.

## Relationship to RED2

This appears to be a mature **functional** RED2/lambda-machine branch. Compared with `PURE/`, its instruction set is much larger and adds primitive support. `RED/` then modifies this branch further for logic programming and unification.

For Asgard's basic RED2 reducer, this directory may be a cleaner semantic reference than the logic-augmented `RED/`, while `RED/` is useful for later extensions and for seeing subsequent fixes.

# STRICT

An **early C head-order lambda reducer**, mostly dated July–September 1989, predating the later Version 0.4 and Version 1.0 HORSE trees.

Despite the directory name, the code already contains much of the recognizable head-order reducer machinery.

## Files

- `RED.C` — head-order reducer, dated 17 July 1989. Defines `argcount`, `binding_offset`, problem/result traversal state, environment/free-space pointers, a waiting primitive pointer, `prim_args`, stack/auxiliary pointers, and reduction limits.
- `PRIMS.C` — primitive table and implementations/hooks, including arithmetic, `IF`, `Y`, booleans, structures, equality, and list primitives.
- `LISTS.C` — C implementation of lazy list primitives, dated September 1989.
- `MAIN.C` — early “Lambda Reduction System, Version 0.0” driver.
- `PRINTER.C` — expression reconstruction/printing; explicitly protects against overflowing the C runtime stack during recursive printing.

The compactness and age of this tree make it useful for understanding how the later C HORSE implementation evolved, but it is incomplete as a standalone archive snapshot (for example, included headers/source dependencies referenced by these files are not all present here).

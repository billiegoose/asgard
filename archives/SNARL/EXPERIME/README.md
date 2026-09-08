# SNARL/EXPERIME

An **experimental Version-1.0-era** C snapshot of the Head Order Reduction System, dated around January 1990.

The original `README` records the same earlier HORSE development history as the other branches, then states on **11 Jan 90**:

> HORSE now conforms to the user's manual. Releasing Version 1.0!

## Contents

The main C program has the standard Version 1.0 family structure (`MAIN.C`, `RED.C`, `PRIMS.C`, `ARITH.C`, parser/compiler, printer, debugger/editor, header, makefile) plus:

- `OLDPRIMS.C` — older primitive implementation retained for comparison.
- `HUGHES.LAM`, `SINE.LAM`, `SIEVE.LAM` — substantial example programs.
- `LISTS.LAM` — list/string prelude.

Several core files are identical to the `OPT/` and `SNARL/` siblings, while others differ. Treat this as an experimental sibling rather than the canonical release tree.

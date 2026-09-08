# WORK

A late-1989 **working HORSE 0.4 branch** closely related to `DEC6/`, with active experimentation on unification and logic programming.

Its original `README` is the same development diary as `DEC6/`, documenting parser fixes, `letrec` fixes, equality changes, introduction of unification, environment-lifetime problems, heap copying, and existential-variable scope work.

## Differences from `DEC6/`

Many source files are exactly identical, including `ARITH.C`, `COMPILER.C`, `EDIT.C`, `OLDUNIFY.C`, `LISTS.LAM`, and `TEST.LAM`. Others differ, notably:

- `UNIFY.C` is substantially larger here than in `DEC6/`.
- `RED.C`, `PRIMS.C`, `PRINTER.C`, `DEBUG.C`, `LRS.H`, `MAIN.C`, and `COMPILER.Y` have branch-specific changes.
- `P.LAM` adds a compact `prove`/logic example.
- `LOGIC.LAM` and `T.LAM` differ from the DEC6 versions.

The historical `MAKEFILE` targets Microsoft DOS C (`cl`, huge model `/AH`, `pcyacc`, `lcurses.lib`) and the code also contains Sun/Unix conditionals.

Treat `WORK/` as an experimental branch snapshot rather than a release. For plain THOR Version 1.0, use `THOR/`; for historical unification experiments, compare `WORK/` with `DEC6/` and the Scheme `RED/` branch.

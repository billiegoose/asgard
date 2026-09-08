# DEC6

A late-1989 **HORSE 0.4** C working tree centered on experiments with adding unification and logic-programming behavior to the head-order reducer.

The original `README` is a development diary. It records fixes through October–December and discusses the difficulties introduced by unification: environment lifetime, disappearing lambdas, reset/trail state, graph copying into a heap, existential-variable scope, and changes to `UNIFY`/`UNIFY*`.

## Program structure

- `MAIN.C` — HORSE driver; identifies the system as Version 0.4.
- `RED.C` — head-order graph reducer.
- `PRIMS.C`, `ARITH.C` — primitives.
- `UNIFY.C` — then-current unification implementation.
- `OLDUNIFY.C`, `OLDPRIMS.C` — explicitly retained older versions.
- `COMPILER.Y` — Yacc parser/compiler source.
- `COMPILER.C` — generated C parser/compiler.
- `PRINTER.C`, `EDIT.C`, `DEBUG.C` — UI/printing/debug support.
- `LRS.H` — common node and machine definitions; dated October 1989.
- `LISTS.LAM` — lambda-encoded list primitives.
- `LOGIC.LAM`, `TEST.LAM`, `T.LAM` — unification/logic experiments and tests.
- `MAKEFILE` — DOS/Microsoft-C build description.

## Historical build

The makefile uses Microsoft's DOS-era `cl`, huge memory model `/AH`, `pcyacc`, and `lcurses.lib`. Source conditionals also show an intended Sun/Unix port.

## Relationship to other trees

`DEC6/` and `WORK/` share many exact files but differ in active unification/debug/reducer work. They should be treated as sibling working snapshots, not releases. For a clean Version 1.0 functional THOR implementation, `THOR/` or `SNARL/SNARL/` is a better starting point.

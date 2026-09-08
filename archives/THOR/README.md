# THOR

A complete C source tree for **HORSE Version 1.0**, the Head Order Reduction System used to execute **THOR**.

This is the best C revival candidate in the archive.

Source headers identify the system as developed by **Mike Hilton**, dated 10 January 1990, with 1989–1990 copyright notices. The archived files have later May-1990 timestamps and are extremely close to the January `SNARL/SNARL/` Version 1.0 tree.

## Files

- `MAIN.C` — interactive HORSE driver; Version 1.0.
- `RED.C` — head-order graph reducer instructions for THOR.
- `PRIMS.C` — builtin primitive table/semantics and prelude loading.
- `ARITH.C` — arithmetic primitive implementation.
- `COMPILER.Y` — Yacc grammar/compiler source.
- `COMPILER.C` — generated parser/compiler C source; useful because the historical Yacc need not be reproduced immediately.
- `LRS.H` — node representation, machine constants, instruction/types, memory/control-stack definitions.
- `PRINTER.C` — graph-to-expression reconstruction/printing.
- `EDIT.C`, `DEBUG.C` — HORSE user-interface/debug machinery.
- `PRELUDE.LAM` — startup THOR definitions for lists and strings.
- `MAKEFILE` — period DOS build instructions.

## Historical compiler/build environment

The `MAKEFILE` uses:

- Microsoft `cl`
- huge memory model (`/AH`)
- `pcyacc` for `.Y` → `.C`
- `LINK`
- `lcurses.lib`
- `IBM` preprocessor definition

The code also contains `SUN` conditionals, and the 1990 manual states that HORSE ran on IBM PCs and Sun workstations.

A modern port should start from the existing `COMPILER.C`, compile in a permissive/K&R-compatible C mode, replace obsolete DOS/Sun APIs and headers, and adapt curses. The original source should remain untouched; a port should preferably live outside `archives/`.

## Relationship to Asgard

Use this tree primarily as the reference for **THOR source-language behavior and the C graph reducer**. For the lower-level RED2 architecture/register model, compare with the Scheme simulator in `COMMON/`, `FP/`, and `RED/`.

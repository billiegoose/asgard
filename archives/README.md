# Hilton thesis-era source archive

This directory is a recovered snapshot of Michael L. Hilton's late-1980s/1990 work on lambda-calculus graph reduction, the RED2/lambda-processor architecture, THOR, and HORSE. It is **not** a single source tree. It contains several generations of the same ideas, experiments in logic programming, two different simulator implementations, a C implementation of the THOR/HORSE system, documentation, examples, and compiled artifacts from period development environments.

The dates and comments in the sources place most of this material between 1988 and 1990. There is no version-control history, so the relationships below are inferred from source comments, embedded dates, README logs, exact-file comparisons, and diffs between directories.

## Short answers

### A. Is the original TeX for the dissertation here?

**Apparently not.**

The archive contains substantial TeX material, but none of the files appears to be the dissertation manuscript itself:

- `MANUAL/` is the source for **User's Manual and Programming Guide for THOR/HORSE, Version 1.0**, by Klaus J. Berkling and Michael L. Hilton. It contains chapters describing THOR, HORSE, and a constructive-programming example.
- `SLIDES/DEF.TEX` is unmistakably from Hilton's **dissertation defense**, titled **“An Architecture for Declarative Programming.”** It describes the goal as developing an architecture for efficiently implementing the complete lambda-beta calculus and explicitly discusses RED2.
- The archive contains no other `.TEX` files and no TeX root identifying itself as the dissertation/thesis manuscript.

So the defense slides survive, and the THOR/HORSE manual survives, but the dissertation's original TeX does not appear to be in this archive.

## B. What code is most useful as a reference for Asgard?

There are two especially important historical implementations.

### 1. The RED2 / lambda-processor simulator: `COMMON/` + `PURE/`, `FP/`, or `RED/`

This is the closest source in the archive to the machine Asgard's RED2 implementation is reconstructing.

`COMMON/REDUCER.S` identifies itself as a **“LAMBDA REDUCTION MACHINE”** and says it simulates the lambda processor based on the microprogrammed reducer implemented on an **AMD29C300 Evaluation Board**. It explicitly models registers and machine state including:

- `argcount`
- `argreg`
- `binding-offset`
- `env` / `envdr`
- `pgar` / `pgdr` (problem-graph address/data)
- `rgar` / `rgdr` (result-graph address/data)
- `primreg`
- reduction counts and limits
- an explicit stack and environment area

It also implements the reducer as an explicit reduction loop with global `goto`-style continuations specifically to avoid host-language recursive stack buildup. That is highly relevant to Asgard's faithful RED2 work.

The branch-specific instruction implementations appear to form an evolution:

1. `PURE/INSTRUCT.S` — early/pure lambda-machine instruction set (346 lines).
2. `FP/INSTRUCT.S` + `FP/PRIMITIV.S` — substantially expanded functional-programming machine with primitive support (572-line instruction set).
3. `RED/INSTRUCT.S` + `RED/PRIMITIV.S` + `RED/UNIFY.S` + `RED/LOGIC.S` — later branch explicitly modified for logic programming and explicitly called **red2** in `LOGIC.S` (622-line instruction set).

For ordinary faithful RED2 semantics, start with `COMMON/`, `FP/`, and `RED/`. Treat the logic/unification additions in `RED/` separately from the core reducer semantics.

### 2. The C THOR/HORSE reducer: `THOR/`

`THOR/` is a complete C implementation of the **Head Order Reduction System** used to run THOR programs. Its headers say it was developed by Mike Hilton, dated 10 January 1990, and its driver identifies itself as Version 1.0.

Important files include:

- `RED.C` — graph-reducer execution machinery.
- `PRIMS.C` / `ARITH.C` — primitive semantics.
- `COMPILER.Y` — Yacc grammar/compiler for THOR source.
- `COMPILER.C` — generated parser/compiler C source.
- `LRS.H` — node representation, instruction/type definitions, machine constants.
- `MAIN.C` — HORSE interactive driver.
- `PRINTER.C` — reconstruction/printing of reduced expressions.
- `PRELUDE.LAM` — built-in list/string definitions loaded at startup.

This is likely the best executable specification for the **language-level behavior of THOR**, while the Scheme RED2 simulator is the better source for the **RED2 architectural machine model**.

## C. Are there example THOR programs to try?

**Yes. There are many `.LAM` files.** They appear to be source programs for HORSE/THOR or closely related versions of the language.

Good candidates include:

- `SNARL/SNARL/SIEVE.LAM` — lazy prime sieve and infinite lists (`from`, `primes`, `nats`, `ones`).
- `SNARL/SNARL/SINE.LAM` — constructive sine implementation adapted from Gerald Roylance.
- `SNARL/SNARL/HUGHES.LAM` — examples adapted from John Hughes' “Why Functional Programming Matters,” including list reductions and trees.
- `SNARL/OPT/PAP.LAM` — tiny recursion/factorial examples useful as smoke tests.
- `CRED/TEST.LAM` — recursion, infinite lists, `Y`, `letrec`, structures, list operations.
- `CRED/KJBTESTS.LAM` — 21 compact lambda-reduction test expressions.

The `DEC6/` and `WORK/` `.LAM` files concentrate on experimental logic-programming/unification extensions and should not be the first compatibility targets for plain THOR.

There is also `COMMON/TESTS.S`, which contains 21 lambda expressions paired with expected reduced results for the Scheme machine simulator. These are particularly valuable as reducer conformance cases even though they are Scheme data rather than `.LAM` files.

## D. Is there an interpreter or RED2 machine we could try compiling/running?

### C HORSE/THOR: yes, with porting work

`THOR/` is a complete C program with a `MAKEFILE`. The historical IBM build uses:

- Microsoft's DOS-era `cl` compiler
- huge memory model (`/AH`)
- `pcyacc` to regenerate `COMPILER.C` from `COMPILER.Y`
- `lcurses.lib`

The code also has `#ifdef SUN` paths and the manual says HORSE ran on **IBM PCs and Sun workstations**, so it was intentionally portable across DOS and Unix of its era.

Because `COMPILER.C` is already present, a modern port need not initially reproduce `pcyacc`; the generated C parser can be used as the starting point. Porting will still require dealing with K&R-era C, old headers/APIs, curses differences, assumptions about data sizes/memory models, and possibly generated-parser compatibility.

`SNARL/SNARL/` is an extremely close January-1990 Version 1.0 ancestor. `THOR/` contains later May-1990 timestamps and mostly small naming/packaging changes, including renaming the reducer from SNARL to THOR and changing `LISTS.LAM` into the more general `PRELUDE.LAM`. Therefore **`THOR/` is the best C tree to attempt to revive first**.

### RED2 machine simulator: yes, but it is Scheme rather than C

The architectural RED2/lambda-machine simulator is in Scheme, primarily:

- `COMMON/REDUCER.S`
- `COMMON/MEMORY.S`
- `COMMON/COMPILE.S`
- `FP/INSTRUCT.S` or `RED/INSTRUCT.S`
- `FP/PRIMITIV.S` or `RED/PRIMITIV.S`

It was written for **PC-Scheme** and uses the SCOOPS object system plus a period-specific graphical interface in `WINDOWS/`. `.FSL` and `.SO` files in these directories are historical PC-Scheme compiled artifacts, not modern ELF/shared-object files despite the `.SO` suffix.

Running it unchanged would probably require recovering/emulating a compatible PC-Scheme environment. Porting the source to a modern Scheme may be possible, but the PC-Scheme/SCOOPS-specific macros, mutable structure syntax, GUI calls, and global-`goto` implementation would need adaptation.

There is also an older Common Lisp simulator in `LISP/`, dating from 1988. It uses Lisp Machine/Flavors-style facilities (`defflavor`, `defmethod`, `tv:`), so it is useful as historical reference but probably harder to execute unchanged today.

## Apparent development families

### RED2 / lambda-processor simulator family

Approximate progression inferred from embedded dates and code growth:

`LISP/` (1988 Common Lisp simulator) → `COMMON/` + `PURE/` (early 1989 PC-Scheme rewrite) → `FP/` (functional primitives) → `RED/` (logic/unification experiments)

`WINDOWS/` supplies the PC-Scheme graphical simulator UI shared by these branches.

### C HORSE/THOR family

Approximate progression:

`STRICT/` (July–September 1989 early C reducer) → `DEC6/` / `WORK/` (late 1989 HORSE 0.4 plus unification experiments) → `SNARL/*` (January 1990 Version 1.0) → `THOR/` (later 1990 THOR-branded release tree)

Important qualification: `DEC6/` and `WORK/` contain experimental logic/unification work that does not simply map onto the later pure functional release, so this is a family tree rather than a guaranteed linear succession.

## Directory map

| Directory | What it appears to contain |
| --- | --- |
| `COMMON/` | Shared PC-Scheme compiler, memory model, reducer loop, tests, and compiled artifacts for the lambda-processor/RED2 simulator |
| `CRED/` | THOR/HORSE `.LAM` examples and reducer tests |
| `DEC6/` | December-era experimental HORSE 0.4 C tree with unification/logic work |
| `FP/` | Functional-programming instruction and primitive layer for the PC-Scheme RED2 simulator |
| `LISP/` | Older 1988 Common Lisp lambda-processor simulator and graphical monitor |
| `LOGIC/` | Independent Scheme experiments in Prolog, unification, hyper-resolution, and lock resolution |
| `MANUAL/` | THOR/HORSE Version 1.0 user's manual and programming guide TeX source |
| `PAPER/` | Scheme theorem-proving/structure-sharing experiments |
| `PURE/` | Early pure lambda-calculus instruction layer for the PC-Scheme reducer |
| `RED/` | Most developed PC-Scheme RED2 branch here, including logic/unification experiments |
| `SLIDES/` | Hilton dissertation-defense slides and supporting figures |
| `SNARL/` | Container for three closely related January-1990 HORSE/SNARL C trees |
| `SNARL/EXPERIME/` | Experimental Version-1.0-era C tree and examples |
| `SNARL/OPT/` | Optimized-build Version-1.0-era C tree |
| `SNARL/SNARL/` | January 11, 1990 Version 1.0 release-like SNARL/HORSE tree |
| `STRICT/` | Earlier mid-1989 C head-order reducer |
| `THOR/` | Later 1990 C THOR/HORSE Version 1.0 source tree; best C revival candidate |
| `WINDOWS/` | PC-Scheme/SCOOPS graphical UI for the RED2 simulator |
| `WORK/` | Late-1989 working HORSE/unification branch closely related to `DEC6/` |

## Preservation note

The original files should be treated as archival material. These README files are modern annotations only; no attempt has been made here to normalize line endings, remove DOS EOF characters, modernize syntax, or replace historical generated/compiled files.

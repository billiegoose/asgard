# THOR / RED2 Prototype Traceability

## Scope

This project is a faithful research prototype of Hilton's THOR interpreter. It
also includes distinct compatibility and machine-fidelity paths for investigating
the RED2 machine and making the dissertation rules executable and comparable.
The project prioritizes readable source, deterministic examples, and thesis
traceability over production compiler coverage or hardware completeness.

The Python THOR interpreter is the executable semantic reference.
`red2_engine.machine.Red2Machine` is the existing evaluator-backed compatibility
model: it compiles the same THOR expressions into a linear instruction graph and
is checked against the THOR result, but it does not execute the Chapter 4 register
transfers directly. The Rust evaluator provides the same kind of compatibility
and parity evidence rather than direct Chapter 4 machine fidelity. The boundary
is explicit: semantic parity is not machine fidelity.

`red2_engine.mured` is the faithful μRED core plus the APP-VAR/head,
passive `INT`/`FLOAT`/`CHAR`, closed head-`SYM` definitions, the Chapter 4
primitive registers, a selected Chapter 3 strict primitive family, and the
Chapter 4 non-strict `Y` and mixed-strictness `IF` transformations. It executes
these graph-memory instructions and register transfers directly, including
`argcnt`, `prim`, `fire`, strict-argument save/restore through APP/JOIN, JOIN
ownership of saved primitive contexts, one-word strict argument compaction,
fire-time quantum re-checks, graph reclamation after successful strict firing,
the shared-graph `(Y f)` to `(f (Y f))` rewrite, and `IF` condition forcing with
lazy branch selection/reconstruction. The implemented strict slice covers
numeric unary/binary operations and comparisons, `NULL?`/`NOT`, atomic type
predicates, and constant `=` with Chapter 3 integer/float coercion behavior where
applicable. Structural strict primitives, recursive equality, and the remaining
non-strict primitives `AND` and `OR` are not implemented yet, so it is still not
full RED2 and is not wired to the CLI. The broader definition-context
machinery outside that closed path remains incomplete. See [`mured-thesis-notes.md`](mured-thesis-notes.md) for the three
narrow source reconciliations used by this core. The `models/python/pypeline_red2/` artifact is
a PypelineC-oriented fixed-width RED2 stepper subset for hardware exploration.
The current user-visible primitive surface is documented in
[`thor-primitives.md`](thor-primitives.md).

## Thesis Traceability

- `models/python/thor_lang/ast.py`, `parser.py`, and `pretty.py` cover Chapter 3 THOR
  syntax, source forms, and the Figure 3.1 translation from named binders to
  De Bruijn-style variables.
- `models/python/thor_engine/semantics.py` and `models/python/thor_lang/primitives.py` implement the
  Chapter 3 abstract interpreter behavior for Rules 1-29, including beta
  contraction, passive data, definitions, primitives, structures, `Y`, and
  `LETREC` reconstruction.
- `models/python/thor_compile/red2.py`, `models/python/red2_engine/instructions.py`,
  `machine.py`, and `primitives.py` implement the evaluator-backed RED2
  compatibility path: instruction-shaped data, head flags, stacks, lookup,
  strict primitives, structures, and recursive blocks.
- `models/python/red2_engine/mured.py` implements the faithful pure-λ subset of
  the Chapter 4 graph-memory machine, including its instruction transitions,
  shared graph/environment memory, and separate control stack.
- `tests/fixtures/appendix_a/sine_core.thor`,
  `tests/fixtures/appendix_a/sine_full.thor`,
  `tests/fixtures/appendix_a/game_core.thor`, and
  `tests/fixtures/appendix_a/game_full.thor` cover executable Appendix A SINE
  and GAME benchmark fixtures with THOR/RED2 parity smoke tests.
- `tools/vscode-thor/` contains a local VS Code-compatible TextMate syntax extension
  for `.thor` files, with examples derived from THOR fixtures.
- `models/python/red2_engine/pipelinec_vectors.py` and
  `models/python/pypeline_red2/red2_stepper.py` trace the Chapter 4 instruction
  encoding into a small PypelineC stepper subset with golden vectors. See
  `models/python/pypeline_red2/README.md` for the optional external
  PipelineC validation path.

## Known Omissions

- The faithful μRED strict slice models the Chapter 3 integer/float coercions
  for its selected numeric primitives; broader floating-point primitive coverage
  outside that slice and the Appendix A SINE benchmark remains incomplete.
- Appendix A GAME is covered at the dissertation benchmark gate of
  `evaluate 1` over the nine root move outcomes; deeper search remains outside
  the default quantum gate.
- Character constants, symbol predicates, and equality are covered; a complete
  non-benchmark character library is not implemented.
- The faithful μRED core implements non-strict `Y` and mixed-strictness `IF`;
  `AND` and `OR` still remain passive pending their dedicated primitive slices.
- The faithful μRED core still lacks the broader multi-definition context
  machinery outside the closed head-`SYM` path.
- FPGA synthesis automation is not part of this milestone.
- Successful selected strict primitive firing performs the Chapter 4/5 `fsp`
  reclamation required for its primitive-arguments subgraph; broader
  performance-accurate reclamation is not yet modeled throughout the machine.
- Vendor tool integration is intentionally out of scope for the default tests.

## Example Commands

Run the Chapter 3 THOR reference model:

```sh
uv run thor --expr "(+ 2 3)" --quantum 20
```

Run the evaluator-backed RED2 compatibility model on the same expression:

```sh
uv run red2 --expr "(+ 2 3)" --quantum 20
```

Both commands should print:

```text
5
```

## Lockstep Parity Mode

`mise run parity` compares THOR and RED2 at contraction-prefix
snapshots for source files. For `--quantum N`, it runs both models for every quantum from `0`
through `N`, alpha-normalizes bound-variable rendering differences such as RED2
`(VAR 0)` output, and compares the user-facing expressions at every prefix.

This is stronger than completion-only parity, but it is not a claim that THOR's
recursive reducer and RED2's internal machine phases schedule every intermediate
recursive application identically. Some programs can diverge at intermediate
prefixes and reconverge at later quanta; in that case parity mode continues to
`N` and reports each mismatch range separately, including the THOR/RED2
expressions at that range's first quantum and the reconvergence point for that
range. The command exits 0 when the final quantum matches and exits 1 when the
final quantum still differs.

Example matching-prefix check:

```sh
mise run parity examples/fibonacci.thor --quantum 10
```

Example diagnostic check that reports the first Fibonacci prefix mismatch:

```sh
mise run parity examples/fibonacci.thor --quantum 75
```

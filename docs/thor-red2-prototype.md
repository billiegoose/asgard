# THOR / RED2 Prototype Traceability

## Scope

This project is a faithful research prototype of Hilton's THOR interpreter and
RED2 machine, built to make the dissertation rules executable and comparable. It
prioritizes readable source, deterministic examples, and thesis traceability over
production compiler coverage or hardware completeness.

The Python THOR interpreter is the executable semantic reference. The Python
RED2 machine compiles the same THOR expressions into a linear instruction graph
and is checked against the THOR result. The `models/python/pypeline_red2/`
artifact is a PypelineC-oriented fixed-width RED2 stepper subset for hardware
exploration.
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
  `machine.py`, and `primitives.py` map the same AST to the Chapter 4
  RED2 execution model: instruction memory, head flags, stacks, lookup, strict
  primitives, structures, and recursive blocks.
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

- Full floating-point coercions are not modeled beyond the prototype and
  Appendix A SINE benchmark subset.
- Appendix A GAME is covered at the dissertation benchmark gate of
  `evaluate 1` over the nine root move outcomes; deeper search remains outside
  the default quantum gate.
- Character constants, symbol predicates, and equality are covered; a complete
  non-benchmark character library is not implemented.
- FPGA synthesis automation is not part of this milestone.
- Performance-accurate memory reclamation is not attempted.
- Vendor tool integration is intentionally out of scope for the default tests.

## Example Commands

Run the Chapter 3 THOR reference model:

```sh
uv run thor --expr "(+ 2 3)" --quantum 20
```

Run the Chapter 4 RED2 model on the same expression:

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

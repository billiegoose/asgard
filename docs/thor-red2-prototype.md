# THOR / RED2 Prototype Traceability

## Scope

This project is a faithful research prototype of Hilton's THOR interpreter and
RED2 machine, built to make the dissertation rules executable and comparable. It
prioritizes readable source, deterministic examples, and thesis traceability over
production compiler coverage or hardware completeness.

The Python THOR interpreter is the executable semantic reference. The Python
RED2 machine compiles the same THOR expressions into a linear instruction graph
and is checked against the THOR result. The `pypeline_red2/` artifact is a
PypelineC-oriented fixed-width RED2 stepper subset for hardware exploration.

## Thesis Traceability

- `src/thor_spec/ast.py`, `parser.py`, and `pretty.py` cover Chapter 3 THOR
  syntax, source forms, and the Figure 3.1 translation from named binders to
  De Bruijn-style variables.
- `src/thor_spec/semantics.py` and `src/thor_spec/primitives.py` implement the
  Chapter 3 abstract interpreter behavior for Rules 1-29, including beta
  contraction, passive data, definitions, primitives, structures, `Y`, and
  `LETREC` reconstruction.
- `src/thor_spec/red2/compiler.py`, `red2/instructions.py`,
  `red2/machine.py`, and `red2/primitives.py` map the same AST to the Chapter 4
  RED2 execution model: instruction memory, head flags, stacks, lookup, strict
  primitives, structures, and recursive blocks.
- `src/thor_spec/red2/pipelinec_vectors.py` and `pypeline_red2/red2_stepper.py`
  trace the Chapter 4 instruction encoding into a small PypelineC stepper subset
  with golden vectors. See `pypeline_red2/README.md` for the optional external
  PipelineC validation path.

## Known Omissions

- Full floating-point coercions are not modeled beyond the prototype subset.
- All character operators from a complete language runtime are not implemented.
- FPGA synthesis automation is not part of this milestone.
- Performance-accurate memory reclamation is not attempted.
- Vendor tool integration is intentionally out of scope for the default tests.

## Example Commands

Run the Chapter 3 THOR reference model:

```sh
uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)"
```

Run the Chapter 4 RED2 model on the same expression:

```sh
uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"
```

Both commands should print:

```text
5
```

# THOR / RED2 Package Layout Proposal

## Status

Proposal only. This document describes a desired package and source-tree architecture; it does not authorize or perform the migration.

## Motivation

The current package split reflects the order in which the prototype grew rather than the final architectural boundaries. In particular, `abstract_red2_machine` currently owns both the faithful Abstract RED2 Machine implementation and pieces of the shared RED2 representation, while `thor_compile` is a very small package that translates THOR into that representation. As a result, the Concrete RED2 Machine and host-side support code import shared RED2 vocabulary from a package whose name implies one specific implementation.

The desired architecture separates language definitions, shared RED2 representation/compiler code, and executable machine implementations.

## Target dependency architecture

```text
                thor
                   │
          ┌────────┴────────┐
          ↓                 ↓
 thor_interpreter      red2.compiler
                            │
                            ↓
                       shared RED2
                     representation
                    /       |       \
                   ↓        ↓        ↓
                 abs       con      syn
```

The important dependency rule is that machine implementations depend on shared language/RED2 libraries, rather than on one another for common representation types.

### `thor`

`thor` is the language-definition library. It is the renamed successor to `thor_lang` and owns only backend-independent THOR concerns:

- AST types;
- parsing;
- normalization;
- pretty-printing;
- primitive/language definitions;
- language version information.

It must not know how RED2 stores or executes a compiled program.

### `red2`

`red2` is the shared RED2 representation and compiler library. It absorbs the architectural role currently split between `thor_compile` and shared representation code housed under `abstract_red2_machine`.

Expected responsibilities include:

- RED2 opcodes and instruction/word representation;
- shared graph/program-image types required by more than one RED2 implementation;
- THOR-to-RED2 compilation under `red2.compiler`;
- shared encoding helpers that are properties of the RED2 representation rather than a particular machine.

The existing `.red2` serialized bytecode format should be evaluated separately during this migration. Serialization may remain under `red2` if it still has a useful interchange/debugging role, but it is not part of the execution architecture and should not determine package boundaries.

### Machine implementations

The four executable implementations are peers:

- `thor_interpreter` — direct THOR execution;
- `abstract_red2_machine` (`abs`) — faithful Abstract RED2 Machine;
- `concrete_red2_machine` (`con`) — bounded architectural RED2 Machine;
- `synthesizable_red2_machine` (`syn`) — synthesizable PipelineC/Pypeline implementation.

The three RED2 machines should consume shared RED2 definitions from `red2`. The Concrete and Synthesizable implementations should not need to import shared vocabulary from `abstract_red2_machine` merely because the Abstract implementation currently owns those definitions.

Machine-to-machine imports are permitted only where they represent an explicit validation/oracle boundary, not as the home of shared representation types. For example, Concrete-vs-Abstract lockstep tooling may intentionally reference both machines, while the RED2 opcode set itself belongs in `red2`.

## Target filesystem layout

Use the conventional Python `src/` source root instead of the current `models/` directory. Within that source tree, separate reusable libraries from executable machine implementations:

```text
src/
  lib/
    thor/
      __init__.py
      ast.py
      parser.py
      normalization.py
      pretty.py
      primitives.py
      version.py

    red2/
      __init__.py
      representation.py       # exact module split to be determined
      compiler.py
      binary.py               # only if .red2 serialization is retained

  machines/
    thor_interpreter/
      __init__.py
      cli.py
      core.py
      semantics.py
      io_runtime.py
      ...

    abstract_red2_machine/
      __init__.py
      cli.py
      machine.py
      io_runtime.py
      ...

    concrete_red2_machine/
      __init__.py
      cli.py
      machine.py
      abi.py
      oracle.py
      pipelinec_vectors.py
      ...

    synthesizable_red2_machine/
      __init__.py
      machine.py
      ...
```

`src/` is the standard Python source-layout convention. `lib/` and `machines/` are organizational source roots, not desired import-name prefixes: the intended public imports remain clean names such as `thor`, `red2`, `thor_interpreter`, and `abstract_red2_machine`, rather than `lib.thor` or `machines.abstract_red2_machine`. The eventual migration should configure packaging/import roots accordingly rather than leaking filesystem organization into the API.

If the packaging toolchain makes multiple source roots unnecessarily awkward, the implementation plan may choose an equivalent conventional `src/` layout that preserves the same architectural distinction without changing the dependency model. The important design constraint is the library/machine separation, not a mandatory `lib.` or `machines.` Python namespace.

## Intended dependency direction

```text
src/lib/thor
  ├──> thor_interpreter
  └──> red2.compiler
          │
          v
       red2 shared representation
          ├──> abstract_red2_machine
          ├──> concrete_red2_machine
          └──> synthesizable_red2_machine
```

Host-side parity and translation tooling may additionally depend on multiple machine packages where comparison itself is the purpose. Those dependencies should be visibly isolated from the core machine implementations.

## Specific cleanup implied by this design

A future migration should determine the exact ownership of every currently shared symbol before moving files. Likely candidates to extract from `abstract_red2_machine` include the instruction/opcode representation and other representation-level types used by `thor_compile` or `concrete_red2_machine`.

`thor_compile` should then disappear as a standalone package, with its live THOR-to-RED2 compiler functionality moving to `red2.compiler`. This is different from moving compilation into `thor`: THOR remains backend-independent, while RED2 compilation belongs to the RED2 library.

`thor_lang` should be renamed to `thor` with imports updated directly rather than retaining a permanent compatibility package.

The current `models/` source root should be replaced by `src/`; the four executable implementations should live under the machine-oriented portion of that source tree, and the two reusable language/representation libraries under the library-oriented portion.

The migration should also decide whether `.red2` serialization still earns maintenance cost after removal of the Rust/WASM VM. If retained, its documentation must describe it as an interchange/debugging representation rather than a separate RED2 execution architecture.

## Non-goals

This proposal does not change RED2 semantics, the quantum model, host-call behavior, the Abstract/Concrete/Synthesizable machine contracts, or the PipelineC/Pypeline hardware boundary. It does not complete missing `syn` semantics and does not revive the removed Rust/WASM VM.

It also does not prescribe compatibility aliases for the old Python package names. The recent cleanup intentionally converged on canonical names, so the eventual migration should prefer one coherent cutover with repository-wide import updates and verification.

## Migration principles

A later implementation plan should preserve these invariants:

1. `thor` remains independent of RED2.
2. Shared RED2 representation/compiler code lives in `red2`, not in a machine implementation.
3. `abs`, `con`, and `syn` consume the same shared RED2 vocabulary while remaining distinct implementations.
4. Synthesizable source remains free of dependencies that cannot pass through the hardware frontend.
5. Oracle/lockstep dependencies are explicit validation edges, not accidental ownership of shared types.
6. The canonical command surface remains `thor`, `abs`, `con`, and `syn`.
7. The migration must remain behavior-preserving and finish with the full test suite and canonical command smokes green.

## Open implementation questions

The implementation plan should resolve, rather than assume, the following details:

- which `abstract_red2_machine.machine` types are true shared RED2 representation versus Abstract-machine runtime state;
- whether `Instruction`/`Opcode` and graph `Word` should share one representation module or remain distinct compiler/runtime forms;
- whether `.red2` binary serialization remains supported;
- the cleanest Hatch/uv configuration for treating `src/lib` and `src/machines` as organizational source roots while preserving top-level import names;
- whether host-side `pipelinec_vectors` belongs in `red2`, `concrete_red2_machine`, or a narrowly scoped bridge module after shared types are extracted.

Those questions affect file placement, but not the dependency architecture proposed here.

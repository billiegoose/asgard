# THOR / RED2 Package Layout

## Status

Implemented. This document records the package architecture adopted from the
original layout proposal.

## Architecture

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

The central rule is that THOR language definitions and RED2 representation are
reusable libraries, while execution engines are peer machine implementations.
Shared representation types do not live inside one machine merely because that
machine happened to implement them first.

## Source layout

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
      representation.py
      instructions.py
      compiler.py

  machines/
    thor_interpreter/
    abstract_red2_machine/
    concrete_red2_machine/
    synthesizable_red2_machine/
```

`src/` follows the conventional Python source-layout pattern. `lib/` and
`machines/` are organizational source roots only: public imports remain `thor`,
`red2`, `thor_interpreter`, `abstract_red2_machine`,
`concrete_red2_machine`, and `synthesizable_red2_machine`.

## `thor`

`thor` is the backend-independent language library, replacing the former
`thor_lang` package. It owns:

- THOR AST types;
- parsing;
- normalization;
- pretty-printing;
- primitive/language definitions;
- language version metadata.

It has no RED2 or machine dependencies.

## `red2`

`red2` is the shared RED2 library. It absorbs the useful functionality of the
former `thor_compile` package together with RED2 representation code that had
previously lived under `abstract_red2_machine`.

Its responsibilities are split deliberately:

- `red2.representation` — live graph vocabulary such as `MuredOpcode`,
  `Direction`, and `Word`;
- `red2.instructions` — compiler/transport representation such as `Opcode`,
  `Instruction`, `ProgramImage`, and `DefinitionImage`;
- `red2.compiler` — THOR-to-RED2 graph and image compilation;

## Machine implementations

The four machine packages are peers:

- `thor_interpreter` — direct THOR execution;
- `abstract_red2_machine` (`abs`) — faithful Abstract RED2 Machine;
- `concrete_red2_machine` (`con`) — bounded fixed-width architectural RED2
  Machine;
- `synthesizable_red2_machine` (`syn`) — synthesizable PipelineC/Pypeline RED2
  Machine.

The Abstract machine now consumes shared graph vocabulary and compilation from
`red2` rather than owning those definitions. Its `loader.py` contains the
Abstract-specific work of constructing and relocating an
`AbstractRED2Machine`.

Concrete host/oracle code may intentionally import the Abstract implementation
for parity and lockstep validation. Those are explicit comparison edges, not
ownership of shared RED2 types. The synthesizable source remains independent of
Python-only machine implementations.

## Dependency rules

```text
src/lib/thor
  ├──> thor_interpreter
  └──> red2.compiler
          │
          v
       shared RED2 representation
          ├──> abstract_red2_machine
          ├──> concrete_red2_machine
          └──> synthesizable_red2_machine
```

The repository enforces these architectural intentions:

1. `thor` does not import RED2 or any machine implementation.
2. `red2` does not import any machine implementation.
3. Shared RED2 opcodes/words/images live under `red2`, not under `abs`.
4. Machine-to-machine imports are limited to explicit host/oracle/validation
   boundaries.
5. Public import names do not contain `lib.` or `machines.`.
6. The canonical executable surfaces remain `thor`, `abs`, `con`, and `syn`.

## Migration result

The migration made these direct cutovers with no permanent compatibility
packages:

- `thor_lang` → `thor`;
- `thor_compile` → functionality under `red2`;
- `models/` → `src/lib/` plus `src/machines/`;
- `abstract_red2_machine.instructions` → `red2.instructions`;
- live graph `MuredOpcode`, `Direction`, and `Word` → `red2.representation`;
- THOR-to-live-RED2 compilation → `red2.compiler.compile_lambda`;
- Abstract-specific definition relocation/loading →
  `abstract_red2_machine.loader`.

The unused `.red2` serialization format and its standalone `compile` command were
retired after the Rust/WASM consumer was removed; compiler-image types remain because
they are still used by current RED2 tooling.

This restructuring is intended to be semantics-preserving. It does not change
RED2 quantum behavior, host-call behavior, the machine contracts, or the
remaining incomplete Synthesizable RED2 semantics.

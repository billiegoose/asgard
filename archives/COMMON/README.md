# COMMON

Shared infrastructure for Hilton's **PC-Scheme lambda-processor / RED2 simulator**, mostly dated 1989.

This is one of the most important directories in the archive for Asgard. The branch-specific instruction sets in `PURE/`, `FP/`, and `RED/` are loaded on top of this common machinery.

## Files

- `REDUCER.S` — core “LAMBDA REDUCTION MACHINE.” It says the simulator is based on the microprogrammed reducer on an **AMD29C300 Evaluation Board**. Defines machine registers, reduction loop, stack/environment helpers, the `instruction`, `primitive`, and `ldefine` macros, and the explicit `goto` mechanism.
- `MEMORY.S` — simulated graph memory and data-register representation.
- `COMPILE.S` — compiler from lambda expressions to **Lambda Assembly Code (LAC)**. Classifies instructions such as `VAR`, `SYM`, primitives, numeric heads, bindings, and application pointers.
- `TESTS.S` — 21 lambda-reduction tests with expected results plus a test runner.
- `CLISP.S` — compatibility utilities making PC-Scheme more Common-Lisp-like.
- `*.FSL`, `*.SO` — historical PC-Scheme compiled forms corresponding to the `.S` sources. These are not modern Unix shared objects despite the `.SO` extension.

## Architectural significance

`REDUCER.S` contains the state model that strongly resembles the RED2 machine described in the dissertation material: problem/result graph address and data registers, environment, argument count, primitive register, reduction limits, and explicit control flow.

A particularly relevant comment explains that its reduction loop implements global gotos specifically to avoid deep recursion buildup in the Scheme host stack.

For Asgard, read this directory together with `FP/` and `RED/`.

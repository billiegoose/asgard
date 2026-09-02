# RED2 FLOAT and CHAR Slice Design

## Goal

Extend `models/python/red2_engine/mured.py` in place with the remaining passive basic data instructions whose Chapter 4 behavior matches `INT`: floating-point and character constants.

## Scope

This slice adds:

- `MuredOpcode.FLOAT` and `MuredOpcode.CHAR`;
- direct passive forward/reverse transitions for both opcodes;
- compilation of `thor_lang.ast.Float` and `thor_lang.ast.Char`;
- loading of source FLOAT/CHAR graph words;
- halted-result decompilation to `Float` and `Char`;
- transition, compiler-layout, fidelity, and documentation coverage.

Out of scope: symbolic constants and definition lookup, primitive firing, structures, recursion, CLI integration, Rust implementation, FPGA work, or evaluator-backed execution.

## Transition Semantics

`FLOAT` and `CHAR` use the same passive-data transition shape as `INT`:

- forward execution copies the complete word, including `head`, to `fsp + 1`;
- if `head` is true, set `pc` to `fsp - 1` after the push and switch to reverse direction;
- if `head` is false, increment `pc` and remain forward;
- reverse execution decrements `pc` only;
- passive data never changes `q`, `phi`, `env`, `c`, control memory, or environment memory.

`FLOAT` payloads must be `float` exactly, not `int` or `bool`. `CHAR` payloads must be strings of length one. Named character spellings are parsed/rendered by the existing Thor parser/pretty-printer and are not represented specially in the machine.

## Architecture

Reuse one private passive-data helper for `INT`, `FLOAT`, and `CHAR` if helpful, but keep dispatch literal and opcode-specific validation messages deterministic. The faithful machine remains in `mured.py`; public names are unchanged.

Compilation extends the existing `compile_lambda()` boundary to accept `Float` and `Char` AST nodes. This temporary legacy name remains until the faithful RED2 surface is large enough to rename.

Decompilation reconstructs `Float(value)` and `Char(value)` only after halt or explicit test inspection. `step()` and `run()` must not call decompilation or the Chapter 3 evaluator.

## Validation

Tests must prove:

- exact compile output and head flags for top-level, lambda-body, and application-position FLOAT/CHAR values;
- forward head, forward non-head, and reverse transition behavior for both opcodes;
- malformed data rejection for wrong payload types;
- result parity for small closed FLOAT/CHAR expressions at normal and zero quantum;
- existing pure-lambda, INT, and APP-VAR behavior stays green;
- docs continue to state that full RED2 is incomplete and symbolic constants are still deferred.

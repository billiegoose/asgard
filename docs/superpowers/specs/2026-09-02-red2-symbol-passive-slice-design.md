# RED2 Passive Symbol Slice Design

## Goal

Extend `models/python/red2_engine/mured.py` in place with the no-definition branch of Chapter 4 `SYM`, so free symbolic constants can be represented, copied, and reconstructed without implementing definition lookup yet.

## Scope

This slice adds:

- `MuredOpcode.SYM`;
- compilation of free `thor_lang.ast.Symbol` values as `SYM` instead of rejecting them;
- loading of source `SYM` graph words;
- halted-result decompilation to `Symbol`;
- direct forward/reverse execution for symbols whose associated definition is absent (`definition = bottom` in the thesis);
- tests and docs proving definition lookup remains deferred.

Out of scope: symbol hash-table addresses, definition storage, reducing a symbol to its definition, primitive firing, structures, recursion, CLI integration, Rust implementation, or evaluator-backed execution.

## Transition Semantics

This slice models only symbol words with no associated definition. A `SYM` word stores the printed symbol name in `data`; no definition field is present yet, so every symbol behaves as if its associated definition is absent.

Forward `SYM` follows the Chapter 4 no-definition/passive branch:

- copy the complete word, including `head`, to `fsp + 1`;
- if `head` is true, set `pc` to `fsp - 1` after the push and switch to reverse direction;
- if `head` is false, increment `pc` and remain forward.

Reverse `SYM` with no definition decrements `pc` only.

`SYM` never changes `q`, `phi`, `env`, `c`, control memory, or environment memory in this slice.

## Validation

Tests must prove:

- free symbols compile to `Word(MuredOpcode.SYM, name, head)`;
- bound symbols still compile as `VAR`/`APP_VAR` according to lexical scope;
- head and non-head `SYM` transitions match the Chapter 4 no-definition branch;
- reverse `SYM` decrements `pc` only;
- malformed symbol payloads are rejected deterministically;
- result parity holds for small closed/free-symbol expressions at normal and zero quantum;
- docs state that definition lookup is still not implemented;
- anti-shortcut checks remain green.

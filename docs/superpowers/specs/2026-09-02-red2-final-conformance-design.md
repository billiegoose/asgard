# 2026-09-02 — Final Integrated Python RED2 Conformance Review (Task 12)

**Status:** complete
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Depends on:** Task 11 integration plus the 2026-09-05 faithful-default migration

## Goal

Close the faithful Python RED2 implementation plan with an explicit conformance boundary. This review does not add an evaluator-backed fallback or claim exhaustive historical RED2 coverage. It records what the current Python μRED path faithfully executes, protects that path against evaluator/decompiler shortcuts, and exercises the integrated source surface against the Chapter 3 THOR semantic reference at test boundaries.

## Execution invariant

`MuredMachine.step()` and `MuredMachine.run()` execute only graph/environment memory transitions and machine registers. They do not invoke the Chapter 3 evaluator, the deleted evaluator-backed `Red2Machine`, or result decompilation.

Result decompilation is presentation-only and is available after halt through `result_expr()`.

Faithful program loading in `thor_compile.red2` may compile and relocate source ASTs, install definition metadata, and recognize canonical generated structure accessors. It does not evaluate source expressions on behalf of the machine.

## Supported integrated conformance surface

The final Python conformance corpus covers the following features across one or more direct transition/fidelity/program-level tests:

- passive integer, float, character, and symbol data;
- lambda application, captured variables, APP/APP-VAR, JOIN, and environment lookup;
- visible top-level definitions, cross-definition references, and recursive definition execution;
- primitive registers and strict argument forcing;
- selected numeric unary/binary primitives and comparisons;
- boolean/type predicates, `NULL?`, `NOT`, constant `=` and supported atomic `EQUAL?`;
- lazy source `AND`/`OR` lowering to `IF` chains;
- non-strict `Y`;
- mixed-strictness `IF`, including unselected-branch laziness;
- lazy `STRUCT` construction;
- strict `CONS` construction and native `CAR`/`CDR` projection;
- canonical generated `StructDef` accessors, including atomic, structured, definition-backed, and application-valued lazy fields;
- explicit user definitions overriding generated bare accessor names;
- `LETREC`, `RBLOCK`, `RUP`, `REC`, `RECP`, and q=0 reconstruction;
- restored environment paths with separate physical `env_frontier` allocation and `PNP` bridging;
- program/CLI integration and host IO pure reductions through the same faithful machine;
- Appendix A SINE and GAME repository parity gates.

## Final cross-feature corpus

`tests/test_mured_fidelity.py::test_final_mured_conformance_corpus_matches_chapter3` deliberately crosses the slice boundaries rather than testing each opcode in isolation. The corpus includes:

1. top-level definitions plus strict arithmetic;
2. nested strict primitives;
3. lazy `IF` with an invalid unselected branch;
4. bounded `Y` reduction;
5. recursive `LETREC` structure reconstruction;
6. zero-quantum `LETREC` reconstruction;
7. a generated structure accessor selecting a lazy arithmetic field while leaving another field unevaluated;
8. a generated structure accessor selecting an application-valued structured field.

Each case compares the user-visible faithful RED2 result with the Chapter 3 THOR result. This comparison occurs after execution and is an oracle at the test boundary only.

## Static anti-shortcut contract

`test_faithful_machine_files_do_not_use_evaluator_shortcuts` scans the faithful execution/integration files:

- `models/python/red2_engine/mured.py`;
- `models/python/red2_engine/__init__.py`;
- `models/python/thor_compile/red2.py`.

The scan rejects dependencies on the deleted evaluator machine, Chapter 3 `thor_engine.semantics` / `reduce_expr`, and prior private evaluator-term machinery. It separately scans the bodies of `step()` and `run()` to ensure neither calls `result_expr()` nor `_decompile()`.

This static contract supplements, rather than replaces, transition-level tests that inspect exact machine state and single-step behavior.

## Supported-vs-unsupported boundary

The Python implementation is now the repository's faithful RED2 execution path, but the following remain outside the conformance claim:

- exhaustive coverage of every primitive or library operation described historically around THOR/RED2;
- recursive/general structural `EQUAL?` beyond the supported atomic-constant path;
- dedicated Chapter 4 `AND` and `OR` primitive transitions: the current source surface lowers them to lazy `IF` chains when not shadowed;
- byte-accounted public stack/heap controls equivalent to the deleted compatibility evaluator; the faithful machine uses word capacities;
- proof that every intermediate contraction prefix is identical to the Chapter 3 recursive evaluator. Lockstep parity intentionally permits internal scheduling differences and records reconvergence;
- performance-accurate hardware timing, exhaustive reclamation/cost modeling, or FPGA/vendor synthesis integration;
- equivalence between the Python μRED memory format and the retained `.red2` bytecode/Rust/WASM compatibility representation. Those paths have their own tests and remain separate implementation targets.

These are declared gaps, not reasons to reintroduce evaluator-backed Python execution. Future Python RED2 work should extend the faithful machine/frontend semantics directly.

## Non-Python boundary

The Rust/WASM RED2 implementation and PypelineC hardware exploration remain separate targets. Task 12 requires their existing gates to remain green, but does not assert that they execute the same Chapter 4 transition representation as `MuredMachine`.

The `.red2` bytecode/compiler layer remains transport/compiler infrastructure used by those targets and is not a second Python evaluator.

## Acceptance

Task 12 is complete when:

- the integrated corpus passes against Chapter 3 at test boundaries;
- the static anti-shortcut contract covers all faithful Python execution/integration files;
- `docs/thor-red2-prototype.md` states the final supported and unsupported surface;
- the full Python test suite, Ruff, mypy, Rust/WASM tests, and `git diff --check` pass.

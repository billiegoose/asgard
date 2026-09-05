# 2026-09-02 — RED2 Faithful CLI Integration (Task 11)

**Status:** complete; historical CLI slice, superseded as the current default-route design by `2026-09-05-red2-faithful-default-design.md`
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`
**Slice task:** Task 11 — *CLI/program integration for faithful machine*
**Depends on:** Task 10 faithful Python μRED subset through RECP/RECONSTRUCT

## Goal

Expose the faithful Python μRED machine through the existing `red2` command as an explicit opt-in execution mode while preserving the evaluator-backed compatibility route as the default.

The faithful route must execute normalized THOR expressions directly through `MuredMachine`; neither `step()` nor `run()` may invoke the Chapter 3 evaluator or compatibility `Red2Machine`.

## CLI surface

`red2` gains `--faithful`.

- Without `--faithful`, behavior is unchanged: IO probing/fallback, compatibility RED2 execution, byte resource limits, clock handling, and output stay exactly as before.
- With `--faithful`, pure THOR program forms are parsed/normalized and evaluated by the faithful μRED machine.
- `--faithful` is intentionally opt-in for this slice; it does not replace compatibility mode.
- The faithful route is pure-expression/program execution only. `--clock` and `--verbose` retain their compatibility meanings and are not used to add IO semantics to μRED.
- Explicit `--stack-size-in-bytes` / `--heap-size-in-bytes` are rejected with `--faithful` because μRED currently exposes word-count capacities rather than the compatibility machine's byte-accounted resource model. Silently reinterpreting bytes as words would be misleading.

## Program runner

Add a public faithful program runner at the RED2 integration layer. It parses and normalizes the program once, then walks forms in source order:

1. ordinary `Definition` forms update the current definition mapping;
2. `StructDef` forms are ignored for machine execution in this slice; custom accessor synthesis remains outside the faithful subset;
3. each expression form is executed with the definitions visible at that point;
4. each result is rendered with `thor_lang.pretty.to_source`, one line per expression.

The initial compatibility definitions/IO machinery are not imported into faithful execution. Primitive names and `PAIR` structure literals are handled by the faithful compiler/machine itself.

## Definition layout

`MuredMachine` already implements Chapter 4 defined-`SYM` execution when `Word.definition` contains a graph address. Task 11 adds a loader that turns an expression plus a mapping of top-level definitions into one μRED memory image:

- compile the root expression and every visible definition with `compile_lambda`;
- reserve root result/STOP placement exactly as `MuredMachine.load` does;
- reserve definition graphs in a static region at the high end of machine memory and move the initial environment frontier immediately below that region; the ordinary result graph continues to grow upward from the root STOP and the environment grows downward without overwriting definition code;
- place a STOP sentinel after each static definition graph for malformed-fallthrough detection;
- relocate graph-address operands in copied definition words from definition-local addresses to their absolute memory addresses;
- address-bearing source opcodes requiring relocation are `APP` and `RBLOCK`; `APP_VAR` and `VAR` contain de Bruijn indices and must never be relocated;
- after all definition base addresses are known, annotate every `SYM name` in the root and definition graphs with the matching definition address when `name` is currently defined;
- definition symbols may therefore reference other visible definitions, including themselves.

No evaluator term graph or compatibility `ProgramImage` is used by this layout.

## Public API

`red2_engine` exports the faithful machine plus a small program-level entry point suitable for the CLI. The existing compatibility exports remain unchanged.

`thor_compile.red2` exposes the faithful graph-layout helper because it is compilation/integration logic; the existing `compile_expr` and `compile_definitions` bytecode APIs remain byte-for-byte unchanged.

The parent plan lists `thor_compile/cli.py`, but the installed `red2` runner is `red2_engine.cli:main`; the opt-in runtime flag therefore belongs in `red2_engine/cli.py`. The `compile` command remains a bytecode writer and is intentionally unchanged.

## Supported CLI acceptance corpus

Faithful CLI tests cover:

- lambda: `((LAMBDA (x) x) 42)`;
- passive data: integer/float/char;
- passive symbol: `FOO`;
- top-level defined symbol/application;
- strict primitive: `(+ 2 3)`;
- structure literal / selector behavior already supported by μRED (with normal pretty-printer canonicalization, e.g. `PAIR` renders as list syntax);
- LETREC, including a bounded recursive reconstruction case.

The tests also prove an invocation without `--faithful` still follows the compatibility route and that the compile CLI remains unchanged.

## Errors and limits

Parse, machine, cycle-limit, and layout failures are reported through the existing `red2: ...` stderr/error-code convention.

The faithful CLI uses the existing μRED default memory/control capacities and cycle limit for this slice. Exposing byte-compatible capacity controls is deferred until a byte accounting model exists for μRED.

## Invariants

- compatibility `red2` remains the default;
- compatibility compile bytecode is unchanged;
- faithful execution reaches `MuredMachine.run()` directly;
- top-level definitions become `SYM.definition` graph addresses, not evaluator callbacks;
- relocated definition graphs never rewrite De Bruijn indices;
- no faithful transition invokes Chapter 3 evaluation or result decompilation;
- result decompilation occurs only after machine halt for presentation.

## Deferred

Task 12 performs final integrated conformance review and declares the remaining unsupported Chapter 4 behavior. IO actions, faithful byte-accounted resource limits, and custom `StructDef` accessor synthesis are outside this slice.

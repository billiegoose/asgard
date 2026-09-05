# 2026-09-05 — Faithful Python RED2 Becomes the Default

**Status:** complete
**Supersedes:** the default-route assumptions in `2026-09-02-red2-faithful-cli-slice-design.md`
**Parent plan:** `docs/superpowers/plans/2026-09-02-remaining-faithful-python-red2-slices.md`

## Goal

Make the faithful Python μRED machine the only Python RED2 execution engine. `red2`, `mise run red2`, parity execution with `model="red2"`, and pure reductions performed by the IO host all execute through `MuredMachine`.

The evaluator-backed Python compatibility machine is deleted rather than retained behind a compatibility switch.

## Runtime architecture

- `models/python/red2_engine/mured.py` is the Python RED2 executor.
- `models/python/thor_compile/red2.py::load_faithful_machine` compiles THOR expressions plus visible definitions into μRED graph/environment memory.
- `models/python/thor_engine/golden.py` routes `model="red2"` directly through the faithful loader and machine.
- `models/python/thor_engine/io_runtime.py` keeps the host-level IO dispatcher, but every pure RED2 reduction it requests is performed by the faithful μRED machine.
- `models/python/red2_engine/machine.py` and `primitives.py` are removed.

`step()` and `run()` remain machine execution only: they do not invoke the Chapter 3 evaluator or decompile to THOR terms as an execution shortcut. Chapter 3 reduction is used only as an oracle at test boundaries.

## CLI surface

`red2` is faithful by default and has no compatibility mode or `--faithful` flag.

The old `--stack-size-in-bytes` and `--heap-size-in-bytes` switches are removed. They described byte-accounted limits implemented only by the deleted compatibility evaluator. The faithful μRED loader currently exposes fixed word capacities instead; silently preserving the byte flags would misrepresent their meaning.

`--clock`, `--verbose`, source-file/`--expr`, and quantum handling remain available through the existing CLI/IO host integration.

## Bytecode boundary

Deleting the Python evaluator does **not** delete the `.red2` bytecode/compiler infrastructure.

`red2_engine.instructions`, `red2_engine.binary`, and the bytecode compilation functions in `thor_compile.red2` remain transport/compiler infrastructure used by the Rust/WASM RED2 paths. Python tests for this layer validate codec and bundle round trips rather than executing the encoded image through the deleted evaluator.

## Definition and structure integration

Visible ordinary definitions are compiled as relocated static μRED graphs. Matching `SYM` instructions receive definition addresses, so nested and recursive definition execution stays within graph/register semantics.

`StructDef` support is integrated without falling back to the Chapter 3 evaluator:

1. constructors remain ordinary generated source definitions;
2. the faithful loader recognizes canonical generated accessor lambdas whose matching `make-TAG` constructor has the expected canonical shape;
3. those generated accessor names are compiled as strict unary primitives and recorded as `(tag, field-offset)` selector metadata on the machine;
4. user definitions that replace a generated accessor no longer match the canonical generated form and therefore keep normal source-definition semantics;
5. native selectors project atomic, structured, and lazy application-valued fields. Lazy fields are evaluated through the ordinary APP/JOIN machinery before the selector result is compacted.

`CAR` and `CDR` use the same native structure-projection mechanism for `PAIR`.

## Graph/environment lifetime

The Chapter 4 `env` register is the current environment-path tip, not a reliable physical allocation high-water mark: restoring a path may move `env` upward while cells allocated below it remain live.

The implementation therefore tracks `env_frontier`, a monotonically downward host-side allocation frontier. When allocating below a restored `env`, it inserts a `PNP` bridge back to the restored path before placing the new environment object. Graph growth is checked against `env_frontier`, preventing live environment cells from being reused after a path restoration.

This is bookkeeping for the shared immutable environment region; it is not presented as an additional thesis execution register.

## Primitive/structure additions needed for integrated programs

The migration includes the machine mechanisms required by the existing parity/Appendix corpus:

- strict `CONS` rewrites its result into a lazy `PAIR` structure graph;
- `CAR`/`CDR` natively project `PAIR` fields;
- canonical generated `StructDef` accessors natively project arbitrary structure fields;
- selected structured results preserve their structure spine and sharing;
- application-valued selected fields are evaluated through APP/JOIN before projection completes;
- constant `EQUAL?` shares the existing constant equality path;
- source applications of `AND`/`OR` are lowered by the frontend to lazy `IF` chains when those names are not shadowed by visible definitions.

The `AND`/`OR` lowering provides the expected boolean identities and short-circuit behavior for the supported source surface; it is frontend lowering, not a new faithful Chapter 4 primitive transition, and partial/non-boolean edge semantics are not claimed beyond the tested surface.

## Capacity defaults

Program-level faithful loaders use larger practical defaults (`65,536` graph/environment words and `8,192` control entries) so real THOR fixtures can execute without relying on the tiny transition-test capacities.

Low-level tests may still construct machines with deliberately small memories and stacks.

## Tests migrated or removed

Compatibility-only evaluator tests are removed. Useful coverage is retained by moving it to faithful-machine or bytecode-codec tests.

Permanent regression coverage includes:

- faithful CLI execution without an opt-in flag;
- top-level and cross-definition execution;
- `CONS`, `CAR`, and `CDR` parity;
- `StructDef` selectors over atomic, structured, and lazy fields;
- user override precedence over generated bare accessors;
- environment allocation after path restoration;
- IO/clock reductions through faithful RED2;
- Appendix A SINE and GAME parity gates.

## Remaining scope

This migration establishes one truthful Python RED2 execution path; it does not claim that every RED2/Chapter 4 primitive or every historical compatibility feature has been implemented. Remaining omissions are documented in `docs/thor-red2-prototype.md` and should be closed through faithful machine/frontend work rather than by resurrecting evaluator-backed execution.

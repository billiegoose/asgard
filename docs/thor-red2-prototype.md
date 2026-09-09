# THOR / RED2 Prototype Traceability

## Scope

This project is a faithful research prototype of Hilton's THOR interpreter and RED2 graph-reduction machine. The Python THOR interpreter is the Chapter 3 semantic reference; the Python RED2 path executes the Chapter 4-style μRED graph/environment/register machine directly.

Python RED2 execution is implemented by `models/python/red2_engine/mured.py`. `red2`, `mise run red2`, and parity runs using `model="red2"` all execute through `MuredMachine`.

Semantic parity remains distinct from machine fidelity: Chapter 3 reduction is an oracle at test boundaries, not an execution callback from `MuredMachine.step()` or `run()`.

## Faithful Python RED2 surface

The μRED core currently includes:

- APP/APP-VAR/head traversal and JOIN reconstruction;
- passive integer, float, character, symbol, and structure data;
- static top-level definition graphs and recursive/cross-definition `SYM` execution;
- Chapter 4 primitive registers (`argcnt`, `prim`, `fire`) and strict-argument save/restore through APP/JOIN;
- selected strict numeric operations, comparisons, type predicates, `NULL?`, `NOT`, constant equality, and `EQUAL?` for supported atomic constants;
- non-strict `Y` graph rewriting and mixed-strictness `IF`;
- source `AND`/`OR` lowering to lazy `IF` chains when those names are not shadowed;
- lazy `STRUCT` execution;
- strict `CONS` construction of lazy `PAIR` graphs plus native `CAR`/`CDR` projection;
- canonical generated `StructDef` accessors lowered by the faithful loader to native unary structure selectors, including lazy application-valued fields and preservation of explicit user overrides;
- `LETREC` compilation/execution through `RBLOCK`, `RUP`, `REC`, `RECP`, and q=0 reconstruction;
- a separate physical `env_frontier`/`fs` boundary plus typed subgraph frames, `JOIN` frontier restoration for proven-safe child results, and `PNP` bridges for logical path splicing when `env` is not physically adjacent.

See [`mured-thesis-notes.md`](mured-thesis-notes.md) for implementation reconciliations, [`superpowers/specs/2026-09-05-red2-faithful-default-design.md`](superpowers/specs/2026-09-05-red2-faithful-default-design.md) for the faithful-default migration boundary, and [`superpowers/specs/2026-09-02-red2-final-conformance-design.md`](superpowers/specs/2026-09-02-red2-final-conformance-design.md) for the completed Task 12 supported/unsupported conformance declaration.

## Program and CLI integration

`red2` directly runs the faithful machine; there is no `--faithful` or compatibility-mode switch.

Visible source definitions are compiled into relocated static μRED graphs. `StructDef` constructors remain source definitions, while canonical generated accessor lambdas are recognized by the loader and emitted as native structure-selector primitives. A user definition that replaces a generated accessor keeps ordinary definition semantics.

Effectful Python RED2 programs also stay on one persistent `MuredMachine`. The machine recognizes `UART-RX`, `UART-TX`, `UART-TX-BYTES`, and `CLOCK` as native suspension points and returns a `MuredHostCall`; the scheduler performs the host operation and resumes that same graph, environment, control stack, and register state. It does not reduce IO continuations by constructing fresh AST requests or loading replacement machines. The THOR model keeps its separate simulator action interpreter.

The IO scheduler treats the contraction quantum as a responsiveness/watchdog budget. By default, every successful host dispatch resets the quantum to the configured amount. Genuine external quantum exhaustion is surfaced as an error unless `quantum-exhausted` is explicitly enabled as a recharge event; the lower-level machine suspension is therefore suitable for a future interactive wait/kill policy.

User-facing faithful loaders default to 1,048,576 graph/environment words and 8,192 control entries. There is still no tracing graph/environment garbage collector; reclamation comes from RED2-known lifetime boundaries. Bounded recursive workloads now reuse proven-safe child environment regions incrementally, while q=0 checkpoint/recharge remains a coarse fallback for residual-world compaction when host-dispatch headroom is low.

## Bytecode and Rust/WASM boundary

The `.red2` instruction/compiler/binary layer remains in the repository. `red2_engine.instructions`, `red2_engine.binary`, and bytecode compilation functions in `thor_compile.red2` are still used as compiler/transport infrastructure for the Rust/WASM paths.

Python binary tests check deterministic encoding and codec/bundle round trips; the bytecode layer is compiler/transport infrastructure rather than the Python execution path.

## Thesis traceability

- `models/python/thor_lang/ast.py`, `parser.py`, and `pretty.py` cover Chapter 3 syntax, source forms, and named-binder/De Bruijn representation.
- `models/python/thor_engine/semantics.py` and `models/python/thor_lang/primitives.py` implement the Chapter 3 semantic reference.
- `models/python/red2_engine/mured.py` implements the faithful graph-memory/register transitions used by Python RED2 execution.
- `models/python/thor_compile/red2.py` contains both faithful μRED program layout and the retained `.red2` bytecode compiler used by non-Python targets.
- `tests/fixtures/appendix_a/sine_core.thor` and `game_core.thor` provide executable Appendix A parity gates.
- `models/python/red2_engine/pipelinec_vectors.py` and `models/python/pypeline_red2/red2_stepper.py` explore a fixed-width PypelineC-oriented hardware RED2 subset.
- `tools/vscode-thor/` contains the local VS Code/TextMate syntax support for `.thor` sources.

## Known omissions and boundaries

- The Python machine should not yet be read as a claim of exhaustive RED2/Chapter 4 primitive coverage.
- Recursive/general structural `EQUAL?` is not implemented; the current faithful path handles supported atomic constants.
- `AND`/`OR` are source-level lazy `IF` lowering rather than dedicated faithful primitive transitions; the tested boolean/short-circuit surface is supported, while broader partial/non-boolean semantics are not claimed.
- The faithful resource model is word-count based internally; byte-accounted public stack/heap controls have not been reintroduced.
- Appendix A GAME is gated at the repository's bounded benchmark scenario rather than as an unlimited search-performance claim.
- FPGA synthesis/vendor automation remains outside the default test milestone.

## Example commands

Run the Chapter 3 THOR reference:

```sh
uv run thor --expr "(+ 2 3)" --quantum 20
```

Run the faithful Python RED2 machine:

```sh
uv run red2 --expr "(+ 2 3)" --quantum 20
```

or through the repository task:

```sh
mise run red2 --expr "(+ 2 3)" --quantum 20
```

Each prints:

```text
5
```

## Lockstep parity mode

`mise run parity` compares THOR and faithful Python RED2 at contraction-prefix snapshots. Intermediate scheduling can differ because the Chapter 3 recursive reducer and Chapter 4 machine perform different internal phases; parity mode reports mismatch ranges and later reconvergence rather than treating every internal scheduling difference as semantic failure.

Example:

```sh
mise run parity examples/fibonacci.thor --quantum 75
```

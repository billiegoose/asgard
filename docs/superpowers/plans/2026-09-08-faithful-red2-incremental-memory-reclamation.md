# Plan: Faithful RED2 Incremental Memory Reclamation

## Goal

Make the Python `MuredMachine` reclaim graph and environment storage according to the archived RED2 machine's incremental lifetime rules instead of relying on a monotonically descending environment frontier plus occasional whole-result checkpoint/relinearization.

The desired behavior is not a tracing garbage collector. It is faithful stack/region reclamation driven by RED2 control-flow boundaries:

- save the physical environment free-space frontier when entering nested subgraphs;
- restore it when those subgraphs rejoin their parent after publishing any surviving value;
- preserve logical environment paths with PNP/MARKER links;
- eagerly rewind graph `fsp` where the archived machine rewinds `ws` or overwrites a dead result suffix;
- keep adaptive host checkpoints as a safety net until the incremental model is demonstrated to be sufficient.

## Historical basis

Archived `RED.C::jump_subgraph()` saves `fs` alongside primitive context before entering a child graph. `inst_join()` updates/shares the child result, then restores `fs` from the control stack and assigns `env = fs` before resuming the parent.

Environment allocation (`make_closure`, `push_marker`, lambda binding, recursive contexts) descends from `fs`. MARKER nodes splice a new physical segment back to an older logical context when `env != fs`.

Graph storage is reclaimed separately. `JOIN` overwrites atomic results into their parent and rewinds `ws`; strict primitives overwrite/reclaim their redex; `IF` rewinds its spine and discards the unchosen lazy branch context.

See `docs/red2-incremental-memory-reclamation.md` for the detailed mechanism and current Python mismatch.

## Non-goals

- Do not add a tracing GC.
- Do not solve failures by increasing `memory_words`.
- Do not remove graph/environment collision checking.
- Do not special-case `clock-dots`, Breakout, STRUCT benchmarks, Y, or named recursive definitions.
- Do not change archived files.
- Do not weaken captured-closure correctness to obtain lower memory use.
- Do not remove the host checkpoint fallback until tests demonstrate that doing so is safe and desirable.
- Do not conflate the IO checkpoint fix with complete historical memory fidelity.

## Phase 0 — Build a memory-lifetime conformance harness

Before changing allocation semantics, make memory behavior directly observable.

### Instrumentation

Add opt-in machine diagnostics or test helpers that record per transition:

- cycle;
- opcode/direction;
- `pc`;
- `fsp`;
- logical `env`;
- physical environment frontier;
- control-stack depth;
- graph words in use;
- environment words in use;
- subgraph-entry/save and JOIN-restore events;
- graph rewind events.

Avoid production logging overhead unless diagnostics are enabled.

### Baseline workloads

Capture deterministic traces/peaks for:

1. nested lambda application with captured variables;
2. repeated strict primitive arguments;
3. a top-level recursive countdown;
4. Y recursion;
5. nested IF with APP branches;
6. recursive list construction/traversal;
7. dynamic user STRUCT construction/traversal (depths 4/8/16);
8. bounded IO-THEN recursion;
9. IO-BIND with captured atomic value;
10. IO-BIND with list/lambda/captured closure value;
11. deterministic `clock-dots`.

Record baseline peak `fsp`, lowest `env_frontier`, and collision point. These become regression evidence, not golden addresses unless the transition is historically specified.

## Phase 1 — Represent saved physical frontier explicitly on the control stack

### Problem

Python `_app()` currently saves logical `env` and primitive context, but does not save the physical environment allocation frontier corresponding to historical `jump_subgraph()`.

### Change

Introduce a typed control entry such as:

```python
@dataclass(frozen=True)
class _SavedEnvFrontier:
    value: int
```

or a single typed `_SubgraphFrame` containing:

```python
@dataclass(frozen=True)
class _SubgraphFrame:
    env_frontier: int
    prim: str | None
    fire: int
```

Prefer a representation that mirrors the historical grouping without making ordinary environment-path pops ambiguous.

When reverse APP/EP/other historical subgraph-entry paths call the equivalent of `jump_subgraph()`:

1. save the current physical environment frontier;
2. save primitive context as required;
3. enter the child exactly as today.

Do **not** restore/reclaim it yet in this phase. First prove push/pop nesting and control-stack shape with transition tests.

### Tests

- nested APP creates nested saved-frontier frames in LIFO order;
- primitive context and saved frontier cannot be confused with integer environment paths;
- EP/closure forcing uses the same historical subgraph frame where appropriate;
- malformed stack ordering raises a machine error.

## Phase 2 — Separate logical environment path from reclaimable physical frontier

### Problem

`env_frontier` currently means “lowest address ever allocated in this live segment.” To model historical `fs`, it must become a current physical free-space boundary that can move upward on proven region exit.

### Change

Define explicit invariants:

- `env` is the logical path tip;
- `env_frontier` is the current physical allocation boundary / historical `fs` analogue;
- allocation always descends from `env_frontier`;
- if `env != env_frontier`, allocation first emits a PNP to `env` exactly as historical MARKER logic requires;
- restoring a saved frontier is legal only at a verified subgraph exit after all surviving child values have been published outside that region.

Update `_validate_state()` so it no longer requires `env_frontier <= env` if historical path restoration/markers permit a logical path into an older higher segment in a way that violates that numeric ordering. Replace numeric assumptions with structural validity where necessary.

### Critical test

Reproduce the captured-closure overwrite bug that motivated monotonic `env_frontier`. It must remain fixed under the new reclaimable frontier model.

## Phase 3 — Restore historical frontier at JOIN for cases with no special reservation

Implement the smallest safe historical subset first.

### Safe initial JOIN cases

Start with child reductions whose result cannot reference temporary child environment storage after JOIN, for example:

- atomic INT/FLOAT/CHAR/SYM results;
- VAR -> APP_VAR compaction;
- strict primitive atomic results;
- EP closure sharing where the atomic value is copied into the parent closure slot.

For these cases:

1. publish/overwrite/share the result exactly as current `_join()` does;
2. restore the saved physical frontier;
3. restore the parent logical environment according to the historical rule/adapted path invariant;
4. restore primitive context;
5. continue backward.

Clear reclaimed memory cells in debug/tests if useful for catching stale references, but do not require clearing for runtime semantics.

### Tests

Use tiny memories where current monotonic allocation fails after many repetitions but the historical-region version should remain flat.

Assert that the frontier repeatedly returns to the same parent address after nested argument reductions.

## Phase 4 — Resolve the `_reserve_problem()` / IO-BIND lifetime conflict

This is the blocking architectural issue for global frontier restoration.

### Current conflict

`_reserve_problem()` allocates copied problem graphs downward from the same `env_frontier` used by environment storage. These reservations may remain referenced after the immediate child JOIN. Restoring historical `fs` would therefore reclaim live Python-only problem storage.

### Required investigation

Build small transition-level experiments for:

- `(IO-BIND (CLOCK) (LAMBDA (x) ...))` with atomic x;
- list-valued bind;
- lambda-valued bind;
- captured lambda-valued bind;
- nested binds;
- bind followed by recursion.

Trace every graph/environment pointer that survives `_fire_io_sequence()`.

### Preferred target

Eliminate `_reserve_problem()` by expressing bound values through ordinary RED2 graph/environment sharing semantics.

Investigate in this order:

1. Can IO-BIND continuation application use an EP/CLOSURE-style environment value directly?
2. Can the returned machine value overwrite/share into the continuation's existing argument closure just as historical JOIN shares atomic closure results?
3. For structured/non-atomic values, can the continuation retain an ordinary graph pointer whose graph lifetime is governed by `fsp`, not the environment arena?
4. Can IO combinators be compiled/lowered so ordinary APP/JOIN machinery performs this application without a Python-specific reservation?

Only if all faithful options fail should a separate reservation arena be considered, and such an arena must be documented explicitly as non-historical integration machinery.

### Exit criterion

No live problem graph may depend on memory that will be reclaimed by a historical environment-frontier restore.

## Phase 5 — Generalize frontier restoration to all historical subgraph exits

Once reservations no longer conflict, audit every Python path corresponding to archived `jump_subgraph()` / JOIN behavior:

- reverse APP;
- closure/EP forcing;
- STRUCT selector subgraphs;
- RBLOCK/RECP binding-expression reduction;
- definition/SYM subgraph execution;
- any internal continuation that semantically enters a child graph.

For each path, answer explicitly:

1. What frontier is saved?
2. What allocations may occur below it?
3. What values may survive the child?
4. Where are those surviving values copied/shared before restore?
5. At what exact transition is the frontier restored?

Do not use one generic restore merely because control returns; lifetime must be justified by the archived transition.

## Phase 6 — Complete graph `ws`/`fsp` reclamation audit

Environment fidelity alone will not fix pure workloads whose graph grows unnecessarily.

Create a table mapping archived graph rewinds to Python behavior.

Audit at least:

- `inst_join()` atomic headed result;
- JOIN pointer result;
- APP_VAR conversion;
- strict primitive result overwrite;
- IF TRUE/FALSE branch selection;
- lambda contraction argument removal;
- STRUCT selector contraction and copied field spines;
- RBLOCK/RUP/RECP contraction/reconstruction;
- definition calls;
- Y temporary scratch;
- q=0 reconstruction.

For every historical `ws = ...`, `ws -= ...`, or overwrite that makes a suffix dead, either:

- identify the equivalent Python `fsp` update; or
- add a failing transition test and implement it.

This phase should revisit the existing recursive dynamic STRUCT collision because it is strong evidence of graph-lifetime mismatch as well as environment growth.

## Phase 7 — Differential memory-shape experiments against archived C

If the archived C reducer can be built/run reproducibly, add small deterministic programs and compare qualitative memory behavior:

- peak graph words;
- peak environment words;
- whether the environment frontier returns after a child JOIN;
- whether graph suffixes rewind after atomic results;
- final result and contraction count where comparable.

Exact addresses/cycles need not match if frontend encodings differ. The important conformance properties are lifetime boundaries and bounded-vs-growing behavior.

If direct execution of archived C is impractical, use source-derived transition tests as the authority and document that limitation.

## Phase 8 — Stress regressions proving incremental reclamation

Add tests that are impossible to pass merely by having a large default arena.

### Pure recursion

Run recursive computations with memory deliberately close to their maximum live set and increase recursion count substantially. Peak memory should remain bounded where the algorithm's live data is bounded.

Distinguish algorithms that legitimately retain an expanding result graph from temporary-space leaks.

### Dynamic STRUCT

Depth 4/8/16 and larger must complete at normal memory without graph/environment collision. Track peak space to ensure it scales with genuine live structure size, not total reduction history.

### IO

Run 5,000+ host actions in 256/512/1024-word machines where feasible. Verify:

- exact effect count/order;
- no effect replay;
- one machine identity;
- incremental frontier restoration occurs;
- host q=0 checkpoints are rare or unnecessary once the working set is stable.

### Captures/sharing

Stress nested closures capturing outer values across many child reductions. Correctness must survive aggressive frontier reuse.

## Phase 9 — Reevaluate host checkpoint policy

After incremental reclamation is complete, instrument deterministic Breakout and `clock-dots` to count adaptive `checkpoint_quantum()` calls.

Desired result: ordinary execution requires zero or very few whole-result checkpoints.

Then choose one of:

1. retain adaptive checkpoints as an emergency compaction/scheduling safety net;
2. increase the threshold only for defensive margin;
3. disable automatic host checkpoints by default if incremental reclamation proves sufficient and tests cover long-running workloads.

Do not remove the mechanism merely for aesthetic purity; decide from measured behavior.

## Phase 10 — Documentation cleanup

Update:

- `docs/mured-thesis-notes.md`;
- `docs/thor-red2-prototype.md`;
- `docs/superpowers/specs/2026-09-05-red2-faithful-default-design.md`;
- the single-machine IO ultraplan's final architecture notes.

Replace statements that environment allocation is monotonic with the final saved/restored frontier semantics.

Document the distinction between:

- logical environment path (`env`);
- physical free-space frontier (`env_frontier` / historical `fs`);
- graph working-space pointer (`fsp` / historical `ws`);
- coarse q=0 checkpoint/relinearization.

## Validation gates

Before each implementation commit:

```text
uv run pytest -q
uv run ruff check .
uv run mypy models/python tests
cargo test -p red2-wasm --quiet
git diff --check
mise run benchmark-breakout --iterations 1
```

Also run deterministic:

- real/fake-clock `clock-dots`;
- recursive STRUCT conformance workload;
- tiny-memory recursive IO stress;
- captured-environment stress.

## Commit strategy

Prefer independently reviewable commits:

1. memory-lifetime instrumentation and tests;
2. typed saved-frontier/subgraph frame with no behavior change;
3. safe atomic JOIN frontier restoration;
4. IO-BIND reservation redesign/removal;
5. general historical environment frontier restoration;
6. graph `fsp` reclamation audit/fixes;
7. stress tests and checkpoint-policy reevaluation;
8. documentation cleanup.

Do not push until explicitly requested.

## Definition of done

This work is complete when:

- Python RED2's physical environment frontier can move downward on allocation and upward on historically justified region exit;
- nested APP/closure/other subgraph reductions save and restore that frontier in LIFO order;
- captured closures remain correct under reclaimed/reused environment addresses;
- `_reserve_problem()` no longer prevents faithful frontier restoration, preferably because it has been removed;
- every significant archived `ws` reclamation has a tested Python equivalent;
- recursive pure workloads do not consume memory proportional to reduction history when their live set is bounded;
- dynamic STRUCT recursion no longer collides at shallow depth;
- long-running IO remains bounded and exactly-once;
- Breakout performance remains near the pre-checkpoint baseline;
- coarse host checkpoints are demonstrably a fallback rather than the primary memory-management mechanism;
- all project gates pass.

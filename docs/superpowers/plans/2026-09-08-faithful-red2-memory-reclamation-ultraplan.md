# Faithful RED2 Incremental Memory Reclamation Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make normal Python RED2 execution reclaim obsolete graph and environment regions incrementally, matching Hilton's archived RED2 lifetime discipline closely enough that bounded recursive IO processes do not grow with elapsed history.

**Architecture:** Preserve one `MuredMachine` per program and keep the μRED machine as the evaluator. Add observability first, then introduce typed subgraph frontier frames, centralize allocator semantics, enable historically justified frontier restores and graph rewinds, remove Python-only IO-BIND upper-arena reservations, and finally document/measure the resulting memory model.

**Tech Stack:** Python 3.14, pytest, ruff, mypy, Rust/WASM test crate `red2-wasm`, mise benchmark tasks.

**Spec:** `docs/red2-incremental-memory-reclamation.md` and the source historical/architectural evidence in `archives/`, `docs/mured-thesis-notes.md`, and `docs/thor-red2-prototype.md`.

**Acceptance:** suite — full project gates plus phase-specific memory-lifetime tests are the verification surface.

## Global Constraints

- One program execution remains one `MuredMachine`; do not reintroduce per-expression or per-action machine construction.
- The μRED machine remains the evaluator; do not sequence IO, recursion, lambda application, IF, arithmetic, or definitions at the AST level.
- Do not add a tracing garbage collector; reclamation must come from machine-known RED2 lifetime boundaries.
- Do not increase default `memory_words` values to hide leaks.
- `GraphEnvironmentCollision` must continue detecting genuine graph/environment overlap.
- Captured closures, REC/RECP values, EP values, PNP/MARKER paths, and saved environment paths must remain correct under frontier reuse.
- Committed host effects must remain exactly-once across quantum exhaustion, host resume, reconstruction, and reclamation.
- Keep the current q=0 host checkpoint path available during migration as a safety net.
- Do not modify `archives/`.
- Do not modify `poor-girls-codex-ax-dump-*.txt`.
- Keep instrumentation disabled by default in normal and benchmark runs.
- Before final completion run: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy models/python tests`, `cargo test -p red2-wasm --quiet`, `git diff --check`, and `mise run benchmark-breakout --iterations 1`.

---

### Task 1: Add RED2 memory lifetime diagnostics

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Create: `tests/test_mured_memory_lifetimes.py`
- Modify: `docs/red2-incremental-memory-reclamation.md`

**Interfaces:**
- Consumes: existing `red2_engine.mured.MuredMachine` construction, execution, state, `fsp`, `env`, `env_frontier`, q=0 checkpoint behavior, and host-call resume APIs.
- Produces: opt-in memory event recording on `MuredMachine`, a snapshot/counter API usable from tests, and documented event names: `SUBGRAPH_ENTER`, `JOIN_RETURN`, `GRAPH_REWIND`, `ENV_ALLOC`, `ENV_RECLAIM`, `IO_BIND`, and `CHECKPOINT`.

**Parallelization rationale:** This creates read-only observability and tests that later reclamation tasks can consume without changing allocator semantics.

- [ ] **Step 1: Locate the current machine state and allocation sites**

  Inspect `models/python/red2_engine/mured.py` for direct writes to `state.fsp`, `state.env`, and `state.env_frontier`, plus q=0 checkpoint/reconstruction code and IO-BIND host sequencing code.

- [ ] **Step 2: Add disabled-by-default diagnostics types**

  Add small internal/public-enough test helpers in `mured.py` equivalent to:

  ```python
  @dataclass(frozen=True)
  class MuredMemoryEvent:
      cycle: int
      opcode: str | None
      name: str
      data: Mapping[str, object]

  @dataclass(frozen=True)
  class MuredMemorySnapshot:
      graph_words: int
      environment_words: int
      peak_graph_words: int
      peak_environment_words: int
      minimum_gap: int
      frontier_restores: int
      graph_rewinds: int
      host_checkpoints: int
  ```

  Names may be adjusted to fit existing style, but tests must have a stable way to enable diagnostics, read ordered events, and read counters.

- [ ] **Step 3: Record allocation/checkpoint/rewind events without changing behavior**

  Instrument existing transitions so opt-in tests can observe environment allocation, graph rewinds, q=0 host checkpoints, IO-BIND reservation/sequencing, subgraph entry, and JOIN return. Do not print by default.

- [ ] **Step 4: Add deterministic baseline tests**

  In `tests/test_mured_memory_lifetimes.py`, add tests for nested lambda application, captured closure application, strict arithmetic recursion/countdown, Y recursion, IF with lazy APP branches, IO-THEN recursion, IO-BIND recursion, and fake-clock `examples/clock-dots.thor`. Assert current results/effects and that diagnostics expose non-empty cycle/event/counter data.

- [ ] **Step 5: Document the baseline interpretation**

  Update `docs/red2-incremental-memory-reclamation.md` with the terminology `env` (logical path), `env_frontier`/`fs` (physical boundary), `fsp`/`ws` (graph boundary), `PNP`/`MARKER` (logical splice), and note that the Task 1 tests intentionally capture the pre-reclamation baseline.

- [ ] **Step 6: Run focused verification**

  Run: `uv run pytest tests/test_mured_memory_lifetimes.py tests/test_red2_no_internal_leaks.py -q`

  Expected: all focused tests pass, and no normal test output includes memory diagnostics unless explicitly enabled.

### Task 2: Introduce typed subgraph frontier frames without reclaiming

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_memory_lifetimes.py`

**Interfaces:**
- Consumes: Task 1 memory diagnostics and existing control-stack / primitive-context implementation.
- Produces: a typed `_SubgraphFrame`-style representation that carries saved `env_frontier`, primitive name/context, and fire/argument state for historical child-subgraph entry.

- [ ] **Step 1: Add a typed frame**

  In `mured.py`, add an internal typed frame similar to:

  ```python
  @dataclass(frozen=True)
  class _SubgraphFrame:
      env_frontier: int
      prim: str | None
      fire: int
  ```

  If existing names differ, keep the fields semantically equivalent and prevent integer environment-path stack entries from being confused with saved physical-frontier state.

- [ ] **Step 2: Add an `_enter_subgraph` helper**

  Route historical child-subgraph entry through one helper that saves the current physical frontier and primitive context, resets the child primitive/argument context, records `SUBGRAPH_ENTER`, and then enters the child graph. This task must deliberately preserve existing memory reuse behavior: do not restore `env_frontier` yet.

- [ ] **Step 3: Convert reverse APP entry first**

  Update the reverse APP path so it uses the typed frame/helper instead of ad-hoc primitive/frontier/control-stack storage.

- [ ] **Step 4: Convert EP/closure forcing only where historically justified**

  Audit `_ep()` and closure forcing paths. Convert only transitions that correspond to archived child-subgraph execution. Leave ambiguous RBLOCK/RECP paths unchanged and documented for a later task if the archived control shape is not yet proven.

- [ ] **Step 5: Add frame-order and behavior tests**

  Add tests proving one nested APP saves one frame, nested APPs save frontiers in LIFO order, primitive context survives nested child reduction, integer environment-path entries remain unambiguous, and malformed frame ordering raises `IllegalTransition`.

- [ ] **Step 6: Run focused verification**

  Run: `uv run pytest tests/test_mured_transitions.py tests/test_mured_memory_lifetimes.py -q`

  Expected: observable result/cycle/space behavior is unchanged except diagnostic metadata records typed subgraph entry/return.

### Task 3: Centralize the environment allocator and validation model

**Type:** implementation
**Depends-on:** 2
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_closure_capture_parity.py`
- Modify: `tests/test_mured_state.py`
- Modify: `tests/test_mured_memory_lifetimes.py`

**Interfaces:**
- Consumes: typed subgraph frame data from Task 2 and diagnostic counters/events from Task 1.
- Produces: centralized environment allocation helpers for one-word bindings, closure allocation, REC block allocation, and PNP/MARKER insertion; debug-only reclaimed-region poisoning support; validation that separates logical `env` from physical `env_frontier`.

- [ ] **Step 1: Audit `_validate_state()`**

  Identify every assumption equivalent to `fsp < env_frontier <= env`. Preserve collision detection but separate physical frontier validity from logical environment path validity.

- [ ] **Step 2: Add allocator helpers**

  Replace direct hand-coded `env_frontier` decrements/writes with helpers for binding cells, closures, REC blocks, and PNP/MARKER insertion. Every helper must record `ENV_ALLOC` diagnostics when enabled.

- [ ] **Step 3: Add debug-only poison support**

  Add an opt-in test/debug option so a future frontier restore can replace reclaimed cells with `None` or a sentinel. Do not make production correctness depend on clearing memory.

- [ ] **Step 4: Preserve the captured-closure regression**

  Ensure the test that originally justified `env_frontier` remains present or add a focused regression where a closure captures an older path and allocation below a restored path cannot overwrite the captured object.

- [ ] **Step 5: Run focused verification**

  Run: `uv run pytest tests/test_closure_capture_parity.py tests/test_mured_state.py tests/test_mured_memory_lifetimes.py -q`

  Expected: validation remains strict enough to catch real overlap and stale poisoned reads while permitting independent logical `env` and physical frontier histories.

### Task 4: Reclaim atomic JOIN child environment regions

**Type:** implementation
**Depends-on:** 3
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_memory_lifetimes.py`

**Interfaces:**
- Consumes: `_SubgraphFrame`-style saved frontier state, allocator helpers, poison option, and diagnostics from Tasks 1-3.
- Produces: `_restore_environment_region(saved_frontier: int, parent_env: int) -> None` or equivalent; first real `ENV_RECLAIM` behavior for safe atomic JOIN result classes.

- [ ] **Step 1: Implement a frontier-restore helper**

  Add a helper that validates no surviving pointer illegally points into the reclaimed interval, records `ENV_RECLAIM`, optionally poisons the reclaimed region in tests, sets `env_frontier` to the saved frontier, and restores the parent logical environment path according to the archived transition.

- [ ] **Step 2: Enable only proven-safe atomic JOIN classes**

  Update `_join()` so frontier restoration occurs only after child result publication for INT, FLOAT, CHAR, plain SYM, VAR-to-APP_VAR compaction, atomic strict primitive results, and atomic EP/closure sharing where the surviving value has been copied into parent-owned storage.

- [ ] **Step 3: Preserve JOIN ordering**

  The implementation order must be: inspect child result, publish/copy/share the result into parent-owned storage, perform graph-tail compaction, restore environment frontier, restore parent logical environment path, restore primitive context, and resume parent traversal.

- [ ] **Step 4: Add address-reuse tests**

  Add repeated pure recursion tests with a tiny memory arena. Assert that the frontier descends during a child iteration then returns to the same saved region on repeated iterations, rather than monotonically descending. Also assert captured closures remain correct under poisoned reclaimed cells.

- [ ] **Step 5: Run focused verification**

  Run: `uv run pytest tests/test_mured_transitions.py tests/test_mured_memory_lifetimes.py tests/test_closure_capture_parity.py -q`

  Expected: at least one repeated pure recursive workload demonstrates physical environment address reuse without corrupting captured closures.

### Task 5: Restore faithful lambda binding lifetimes

**Type:** implementation
**Depends-on:** 4
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_closure_capture_parity.py`
- Modify: `docs/red2-incremental-memory-reclamation.md`

**Interfaces:**
- Consumes: Task 4 safe atomic frontier restoration and Task 3 allocation helpers.
- Produces: lambda binding behavior mapped to archived `inst_lambda()` cases: PTR/closure argument, VAR/UBV argument, atomic direct value, and q-exhausted/no-argument UBV.

- [ ] **Step 1: Add the historical mapping table**

  In `docs/red2-incremental-memory-reclamation.md` or a targeted code comment, map Python APP/APP_VAR/EP lambda cases to Hilton's PTR/VAR/value/no-argument cases and state which side owns each surviving allocation.

- [ ] **Step 2: Audit closure capture paths**

  Confirm every closure's captured logical path points outside any child region that will be reclaimed, or that the closure object is copied/published into parent-owned storage before restore.

- [ ] **Step 3: Update lambda binding allocation to use the centralized helpers**

  Ensure atomic argument bindings repeatedly allocate in the current child region and become reclaimable at the enclosing subgraph boundary. Ensure closure-valued results that outlive a child are not left in the reclaimed interval.

- [ ] **Step 4: Add nested capture stress tests**

  Add tests for: an outer binding `x`, a child producing a lambda that captures `x`, the child returning, and the returned lambda being invoked later under aggressive address reuse/poisoning.

- [ ] **Step 5: Run focused verification**

  Run: `uv run pytest tests/test_closure_capture_parity.py tests/test_mured_transitions.py tests/test_mured_memory_lifetimes.py -q`

  Expected: ordinary lambda recursion with bounded live depth no longer requires monotonic environment growth.

### Task 6: Eliminate IO-BIND upper-arena problem reservations

**Type:** implementation
**Depends-on:** 5
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `models/python/red2_engine/io_runtime.py`
- Modify: `tests/test_red2_io_runtime.py`
- Modify: `tests/test_mured_memory_lifetimes.py`
- Modify: `docs/red2-incremental-memory-reclamation.md`

**Interfaces:**
- Consumes: faithful lambda publication/lifetime behavior from Task 5 and existing host dispatch/resume APIs.
- Produces: IO-BIND continuation application that consumes committed atomic host values through ordinary graph/environment sharing rather than persistent copied executable graphs in the upper environment arena; `_reserve_problem()` removed from IO-BIND execution.

- [ ] **Step 1: Trace current atomic IO-BIND**

  Use diagnostics for `(IO-BIND (CLOCK) (LAMBDA (x) (IO-RETURN x)))` and record live graph/environment/control pointers before CLOCK fires, after `resume_host_call`, before IO-BIND fires, after continuation lambda binding, and after JOIN. Confirm no upper-arena reservation occurs.

- [ ] **Step 2: Compare IO-THEN**

  Use IO-THEN as the model for destructive effect-prefix elimination. Identify which transition lets IO-THEN discard the completed value and directly enter the continuation.

- [ ] **Step 3: Implement atomic IO-BIND without `_reserve_problem()`**

  For atomic host values, make the continuation consume the existing result descriptor or a graph-side value whose lifetime is not environment-frontier lifetime. Preserve exactly-once effects and one machine identity.

- [ ] **Step 4: Make structured IO-BIND results explicitly out of scope**

  Current host IO returns only atomic values (`CLOCK` -> `INT`, `UART-RX` -> `INT`/`NIL`, `UART-TX` -> `NIL`, `UART-TX-BYTES` -> `NIL`). Reject application/structured/lambda-valued `IO-BIND` results with an `IllegalTransition` that names the future need for graph-owned publication if structured IO results are added later.

- [ ] **Step 5: Remove `_reserve_problem()` from IO-BIND execution**

  Delete the upper-arena reservation fallback from IO-BIND execution. If `_value_problem()` remains useful for checkpoint/relinearization or external APIs, keep that concern separate and ensure IO-BIND execution never reserves persistent upper-arena problem graphs.

- [ ] **Step 6: Add IO-BIND stress and scope tests**

  Add tests for atomic CLOCK bind, nested binds, bind where later output depends on the clock result, 5,000 bind iterations without checkpoint fallback, exactly-once effects, same machine identity throughout, and explicit rejection of structured/application-valued bind results.

- [ ] **Step 7: Run focused verification**

  Run: `uv run pytest tests/test_red2_io_runtime.py tests/test_mured_memory_lifetimes.py -q`

  Expected: no live IO continuation graph depends on memory that historical environment-frontier restoration would reclaim.

### Task 7: Generalize historical frontier restoration to all justified child-subgraph completions

**Type:** implementation
**Depends-on:** 6
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_mured_memory_lifetimes.py`
- Modify: `docs/red2-incremental-memory-reclamation.md`

**Interfaces:**
- Consumes: IO-BIND lifetime cleanup from Task 6 and atomic/lambda restoration from Tasks 4-5.
- Produces: documented audit table and implementation for every historically justified child-subgraph frontier restoration path.

- [ ] **Step 1: Build the candidate transition audit table**

  For APP argument reduction, EP/closure forcing, LETREC/RBLOCK binding reduction, REC/RECP expansion/reconstruction, definition expansion, STRUCT selector/application subgraphs, primitive strict arguments, and Python-only internal continuations, document: entry transition, saved frontier, child allocations, surviving result representation, publication point, and restore point.

- [ ] **Step 2: Restore only historically justified paths**

  Enable saved-frontier restoration on paths with a clear archived lifetime argument. Do not restore merely because a Python helper looks nested.

- [ ] **Step 3: Add transition tests**

  Cover APP subgraph save/restore, nested APP LIFO restoration, pointer-result JOIN, closure atomic sharing, lambda atomic/closure arguments, APP_VAR, IF chosen/unselected branch lifetime, Y scratch lifetime, RUP/ReCP/RBLOCK restoration where justified, and STRUCT selector lifetime.

- [ ] **Step 4: Run focused verification**

  Run: `uv run pytest tests/test_mured_transitions.py tests/test_mured_memory_lifetimes.py tests/test_red2_recursive_definitions.py -q`

  Expected: the environment frontier commonly oscillates around a bounded live-set region during recursive execution rather than tracking total execution history.

### Task 8: Complete graph-side `ws` / `fsp` rewind parity

**Type:** implementation
**Depends-on:** 7
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_mured_transitions.py`
- Modify: `tests/test_red2_recursive_structs.py`
- Modify: `docs/red2-incremental-memory-reclamation.md`

**Interfaces:**
- Consumes: environment frontier restoration from Task 7 and memory diagnostics from Task 1.
- Produces: Python equivalents or documented representation-specific exceptions for archived `ws = ...`, `ws -= ...`, and destructive overwrite sites.

- [ ] **Step 1: Create the archived-vs-Python rewind table**

  In `docs/red2-incremental-memory-reclamation.md`, add columns: archived site, archived ws action, Python site, current fsp action, parity, fix/test.

- [ ] **Step 2: Audit and fix JOIN graph rewinds**

  Verify atomic JOIN, APP_VAR compaction, pointer results, and destination HEAD/non-HEAD cases match historical graph-tail compaction behavior or have a documented representation reason.

- [ ] **Step 3: Audit and fix lambda, strict primitive, IF, RUP, Y, STRUCT, and RECONSTRUCT rewinds**

  Pay special attention to `_rup()` q>0 behavior and STRUCT field graph copying. Do not reclaim field graphs that are genuinely live.

- [ ] **Step 4: Add graph-growth tests**

  Add tests showing temporary result spines are rewound for strict primitives, IF discards the unchosen branch, RUP does not leak argument scratch, Y scratch is temporary, and STRUCT temporary tails do not grow with total reduction history.

- [ ] **Step 5: Run focused verification**

  Run: `uv run pytest tests/test_mured_transitions.py tests/test_red2_recursive_structs.py tests/test_mured_memory_lifetimes.py -q`

  Expected: graph-side memory counters show bounded temporary growth for bounded-live-set workloads.

### Task 9: Fix recursive STRUCT and long-running process memory behavior

**Type:** implementation
**Depends-on:** 8
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_red2_recursive_structs.py`
- Modify: `tests/test_red2_io_runtime.py`
- Modify: `tests/test_mured_memory_lifetimes.py`
- Modify: `docs/red2-incremental-memory-reclamation.md`

**Interfaces:**
- Consumes: complete environment and graph reclamation parity from Tasks 7-8.
- Produces: bounded-space behavior for dynamic recursive STRUCT workloads, `clock-dots`, deterministic Pong/Breakout-style loops, and synthetic state-threading IO loops.

- [ ] **Step 1: Re-run the shallow recursive STRUCT collision workload**

  Measure depth 4, then depths 8, 16, 32, and 64 where practical. Distinguish genuine live recursive structure data from temporary graph/environment history.

- [ ] **Step 2: Fix remaining STRUCT-specific leaks**

  Correct selector APP slots, field graph pointers, copied structure spines, and `_copy_struct_result_to()` behavior only where diagnostics prove temporary history is retained incorrectly.

- [ ] **Step 3: Add long-running bounded-state IO stress tests**

  Add deterministic fake-clock `clock-dots`, a synthetic loop equivalent to `CLOCK; UART; loop(next_integer_state)`, and existing deterministic game-loop probes where practical. Assert effects are correct and memory peaks remain within a bounded region after warm-up.

- [ ] **Step 4: Run focused verification and benchmark smoke**

  Run: `uv run pytest tests/test_red2_recursive_structs.py tests/test_red2_io_runtime.py tests/test_mured_memory_lifetimes.py -q`

  Run: `mise run benchmark-breakout --iterations 1`

  Expected: bounded-state loops do not show linear memory growth with completed frames/effects, and Breakout is not dramatically slower than the adaptive-checkpoint reference.

### Task 10: Reevaluate q=0 host checkpoint fallback and archived C differential evidence

**Type:** implementation
**Depends-on:** 9
**Review:** lean

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `tests/test_red2_io_runtime.py`
- Modify: `docs/red2-incremental-memory-reclamation.md`

**Interfaces:**
- Consumes: bounded process behavior and diagnostics from Task 9.
- Produces: measured checkpoint counts for bounded IO workloads and a documented decision for checkpoint role: emergency compactor, disabled-by-default, or scheduler-visible explicit API.

- [ ] **Step 1: Measure checkpoint counts after incremental reclamation**

  For 5,000 fake `clock-dots` writes, deterministic Pong where available, deterministic Breakout, and the synthetic bounded IO loop, record checkpoint counts, peak graph/environment words, minimum gap, and effect counts.

- [ ] **Step 2: Decide and implement the final automatic checkpoint policy**

  Retain checkpointing as an emergency compactor unless measurements strongly support disabling automatic checkpoints by default. Do not decide from aesthetics; document the measured reason.

- [ ] **Step 3: Compare with archived RED2 evidence**

  If the archived C reducer can be built practically without modifying `archives/`, instrument/observe cycle/reduction, `ws`, `fs`, `env`, and stack depth for tiny deterministic programs. If build is impractical, document that direct runtime comparison could not be completed and cite archived transition code/thesis text as authority.

- [ ] **Step 4: Run focused verification**

  Run: `uv run pytest tests/test_red2_io_runtime.py tests/test_mured_memory_lifetimes.py -q`

  Expected: q=0 checkpointing is demonstrably a fallback/emergency compaction mechanism rather than the primary reason long-running IO survives.

### Task 11: Reconcile RED2 memory documentation

**Type:** implementation
**Depends-on:** 10
**Review:** lean

**Files:**
- Modify: `docs/mured-thesis-notes.md`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `docs/red2-incremental-memory-reclamation.md`
- Modify: `docs/superpowers/specs/2026-09-05-red2-faithful-default-design.md`
- Modify: `docs/superpowers/plans/2026-09-05-single-machine-red2-io-ultraplan.md`
- Modify: `docs/superpowers/plans/2026-09-08-faithful-red2-memory-reclamation-ultraplan.md`

**Interfaces:**
- Consumes: final implementation semantics and checkpoint policy from Task 10.
- Produces: documentation that consistently explains `env`, `env_frontier`/`fs`, `fsp`/`ws`, `PNP`/`MARKER`, JOIN lifetime boundaries, and checkpoint fallback semantics.

- [ ] **Step 1: Search for monotonic allocation claims**

  Search the listed docs for statements implying `env_frontier` is a monotonic conservative watermark or that q=0 checkpointing is the normal primary memory reclamation mechanism.

- [ ] **Step 2: Update final terminology**

  Ensure docs consistently define: `env` as logical environment path, `env_frontier`/`fs` as physical environment free-space boundary, `fsp`/`ws` as graph/result working-space boundary, `PNP`/`MARKER` as logical path splice, JOIN as child-result publication plus parent continuation plus lifetime boundary, and `checkpoint_quantum` as coarse residual-world compaction.

- [ ] **Step 3: Preserve migration history accurately**

  Explain that adaptive q=0 checkpointing was a correct coarse safety net but is no longer the ordinary allocator for bounded loops after incremental reclamation.

- [ ] **Step 4: Run documentation verification**

  Run: `uv run pytest tests/test_docs_examples.py -q`

  Run: `git diff --check`

  Expected: docs examples remain valid and no whitespace errors are introduced.

### Task 12: Full validation gate

**Type:** gate
**Depends-on:** 11

**Files:** none (verification only)

**Interfaces:**
- Consumes: all implementation and documentation tasks.
- Produces: final verification evidence for merge readiness.

- [ ] **Step 1: Run the full Python suite**

  Run: `uv run pytest -q`

  Expected: all tests pass.

- [ ] **Step 2: Run lint**

  Run: `uv run ruff check .`

  Expected: no lint violations.

- [ ] **Step 3: Run type checking**

  Run: `uv run mypy models/python tests`

  Expected: no type errors.

- [ ] **Step 4: Run Rust/WASM tests**

  Run: `cargo test -p red2-wasm --quiet`

  Expected: all Rust/WASM tests pass.

- [ ] **Step 5: Run diff hygiene**

  Run: `git diff --check`

  Expected: no whitespace errors.

- [ ] **Step 6: Run performance smoke**

  Run: `mise run benchmark-breakout --iterations 1`

  Expected: no multi-x slowdown relative to the adaptive-checkpoint reference without a measured explanation.

## Operator smoke

- do: run `mise run red2 examples/clock-dots.thor` with a deterministic/fake clock configuration long enough to produce many dots.
- see: dots continue without `graph and environment collide`, and diagnostic counters show bounded post-warm-up memory rather than history-proportional growth.

- do: run `mise run benchmark-breakout --iterations 1`.
- see: the benchmark completes successfully and RED2 performance is not dramatically worse than the prior adaptive-checkpoint reference.

- do: inspect `docs/red2-incremental-memory-reclamation.md`.
- see: the document explains `env`, `env_frontier`/`fs`, `fsp`/`ws`, `PNP`/`MARKER`, JOIN, and q=0 checkpoint fallback without describing normal allocation as monotonic.

## Implementation status note

This plan has been executed in the Python prototype with opt-in memory
diagnostics, typed child-subgraph frames, centralized environment allocation,
proven-safe JOIN frontier restoration, graph-rewind counters, and documentation
reconciliation. Atomic IO-BIND host values now flow through ordinary
continuation binding without upper-arena reservation. Application-valued IO-BIND
results are explicitly out of scope for the current host IO contract and are
rejected until a future graph-owned publication design is needed.

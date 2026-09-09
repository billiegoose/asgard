# Complete Hilton memory reclamation implementation plan

> Pi-native execution: `/skill:ultrapowers docs/superpowers/plans/2026-09-09-hilton-complete-memory-reclamation-ultraplan.md`. This is a planning deliverable, not an execution launch. Contracts and exams replace implementation steps.

**Grammar:** claims-v1
**Claim:** change our env_frontier implementation to us a free_space pointer like Hilton's. (elicited)
**Goal:** Implement the functional THOR/HORSE C memory-reclamation techniques in the faithful Python RED2 runtime: explicit free_space allocation, structural environment-region return, graph suffix reuse, sharing, lazy discard, recursive/structure/equality temporary lifetimes, and forwarding-aware residual compaction. Preserve RED2 semantics and exactly-once IO.
**Tech Stack:** Python 3.14+, uv, pytest, existing RED2 graph engine; a C99-capable host compiler in GNU89 compatibility mode for the archived-C reference adapter.
**Exam command:** uv run pytest -q {paths}
**Spec:** `docs/superpowers/specs/2026-09-09-hilton-complete-memory-reclamation-design.md`
**Acceptance:** suite — focused behavioral exams, independent peer review of unsafe-memory surfaces, archived-C differential fixtures, and the final integrated Python verification gate are required; no silent waiver of C reference coverage.
**Parallelization rationale:** Expected implementation widths are 2 (pointer conversion and isolated C reference), 1 (safe publication/region return), 5 (graph suffixes, lazy control, recursive structures, equality, compaction), 1 (IO integration), 1 (documentation), followed by a gate. Publication needs the initialized allocator and measured C boundary behavior; the five consumers need publication's runtime ownership guarantees; IO needs the combined reclaim/compaction behavior; documentation and final acceptance need measured integrated behavior. Shared text edits require isolated worktrees and reviewed folding, not concurrent writers in one cwd. Correctness review, rather than speed, is the reason to use Ultrapowers.

## Global Constraints

- Execute Chapter 4 instructions directly over machine graph/environment memory and typed control state. Do not replace reduction with an AST evaluator, use a persistent Python closure heap, introduce tracing GC, or increase default memory to hide retention.
- Preserve existing q=0 residual semantics, contraction-prefix behavior, closure capture, lazy demand, static definitions, and exactly-once effects. C and RED2 have different node layouts and quantum accounting; lifetime equivalence does not mean identical addresses or instruction counts.
- Use archived THOR as functional C authority. Catalogue related C variants but do not import logic/unification/backtracking semantics from DEC6/WORK or experimental RPTR into this plan. Archive source and thesis transcription are read-only.
- Check: git diff --exit-code "$ULTRA_BASE" -- archives thesis
- Production arena headroom is derived from an explicit initialized free_space register, never logical env. A collision raises a typed error without partial allocation. Diagnostic poisoning is opt-in.
- Normal region return must not silently skip reclaiming a machine-generated child region. Publication must establish safety first; malformed states fail before reuse. Debug root scans are not the production lifetime algorithm.
- Preserve atomic IO-BIND scope and the single MuredMachine host scheduler. Checkpoint/recharge remain explicit coarse boundaries, not substitutes for local lifetime correctness.
- Bounded-memory claims apply to fixed-live-state cases, not arbitrary recursion or growing outputs. Tests distinguish graph, environment, control stack, and host diagnostic storage.
- Long-running subprocess tests wait for expected output then terminate explicitly; a timeout is a failure guard, never the success condition. Concurrent proofs use isolated temporary paths and build directories.

## Baseline and file responsibilities

Base inspected: `9a7acc8d84beb142cce00e359049ed68f85a20cd`. Focused baseline: `uv run pytest -q tests/test_mured_memory_lifetimes.py tests/test_mured_state.py tests/test_red2_recursive_structs.py` → `42 passed in 2.24s`. This is not a full-suite or C differential result.

- `models/python/red2_engine/mured.py`: physical allocator, publication, typed transitions, graph lifetimes and compaction.
- `models/python/thor_compile/red2.py`: static region initialization and definition boundaries.
- `models/python/red2_engine/io_runtime.py`: headroom decisions and same-machine scheduling.
- `tools/hilton_reference/`: isolated headless C source adapter and normalized lifetime fixtures, not a new production evaluator.
- Existing transition/lifetime/recursive/IO tests remain their respective behavioral exam surfaces; new reference and equality tests have separate behavior-specific files.
- `docs/red2-incremental-memory-reclamation.md`: final single source of current memory-model status and C-site mapping. Earlier dated plans stay historical.

## Tasks

### Task 1: Make free_space the authoritative allocation register
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `models/python/red2_engine/io_runtime.py`
- Modify: `models/python/thor_compile/red2.py`
- Test: `tests/test_mured_state.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_fidelity.py`
- Test: `tests/test_red2_recursive_structs.py`
- Test: `tests/test_red2_io_runtime.py`
- Test: `tests/test_mured_compile.py`

**Claim:** Run the existing machines with a free_space pointer independent of the logical environment, and see allocation and collision checks use that pointer. (derived)
Machine: M1. Machine-owned states expose an initialized integer `free_space`; load, direct-state construction, static-definition loading, subgraph frames, and recharge use it, with no executable `env_frontier` state or runtime env fallback. M2. Allocating a binding or contiguous block when env differs from free_space inserts the required PNP and allocates below free_space; complete reservation failure changes neither machine state nor diagnostics. M3. Graph append and host headroom decisions use free_space even when env names a higher valid saved path; the existing semantic regression suite remains green.

**Authorized-by:** Operator request; design §§3–4.

**Interfaces:**
- Consumes: `none`
- Produces: `MuredMachineState.free_space: int`

**Context:** C `fs` is distinct from graph `ws` and logical `env`; Python `fsp` remains the last occupied graph address. The sole boundary satisfies fsp < free_space <= working_memory_limit. Legacy constructors omitting the boundary may initialize it once from env before execution, but do not keep two writable fields. Existing synthetic tests mutate env after load and need explicit physical-boundary setup. Existing skip-reclaim behavior is preserved in this contract until publication owns its replacement. Runtime diagnostic payloads containing env_frontier migrate with their consumers; historical prose is updated by the documentation contract. The allocator must preflight the marker plus entire binding/block footprint, not emit a marker before discovering a collision.

**Proof:**
- Test: `tests/test_mured_state.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_fidelity.py`
- Test: `tests/test_red2_recursive_structs.py`
- Test: `tests/test_red2_io_runtime.py`
- Test: `tests/test_mured_compile.py`
- Run: uv run pytest -q tests/test_mured_state.py tests/test_mured_transitions.py tests/test_mured_memory_lifetimes.py tests/test_mured_fidelity.py tests/test_red2_recursive_structs.py tests/test_red2_io_runtime.py tests/test_mured_compile.py
- Run: python3 -c "from pathlib import Path; roots=[Path('models/python/red2_engine'),Path('models/python/thor_compile')]; hits=[str(p) for r in roots for p in r.rglob('*.py') if 'env_frontier' in p.read_text()]; assert not hits, hits"
- Legs: (a) For each of load, direct-state construction, definition loader, subgraph frame save/restore, and recharge, assert the integer physical boundary, change only env afterward, and assert the boundary stays fixed; reject independent legacy allocator storage and runtime fallback in the source sweep [M1]; (b) Single-word and three-word block fixtures each cover adjacent env, nonadjacent env with PNP, exact fit, marker-only-fit failure, and total exhaustion; compare full state, arena, stack, and diagnostics before/after each failure and verify lookup through a successful PNP [M2]; (c) Construct a higher saved env path containing a real binding and terminating valid PNP chain, validate it and assert lookup returns that binding before testing headroom; place graph allocation against free_space with that valid env higher and require GraphEnvironmentCollision; spy on host checkpoint-versus-refresh at both sides of the existing headroom threshold using that same validated path, and run all listed regressions [M3].

**Stale-if:**
- path-absent: `models/python/red2_engine/mured.py`
- path-absent: `models/python/red2_engine/io_runtime.py`

### Task 2: Establish an executable C lifetime reference and site inventory
**Type:** implementation
**Review:** peer

**Files:**
- Create: `tools/hilton_reference/runner.py`
- Create: `tools/hilton_reference/adapter.c`
- Create: `tools/hilton_reference/compat.h`
- Create: `tools/hilton_reference/cases.json`
- Create: `tools/hilton_reference/README.md`
- Create: `tools/hilton_reference/reclamation-sites.json`
- Test: `tests/test_hilton_reference.py`

**Claim:** Run the archived functional C reducer's memory cases and inspect evidence for each distinct reclamation technique rather than treating source comments as runtime proof. (derived)
Machine: M1. `run_case` executes the archived THOR reducer/primitive bodies through a headless C adapter and returns normalized semantic results, sharing relations, and ws/fs boundary events for the committed named cases. M2. The reference corpus covers environment return, closure sharing, graph suffix contraction, lazy discard, recursion/reconstruction, equality scratch graphs, and copy/shift forwarding; each case has hand-derived expected evidence independent of Python RED2. M3. Missing compiler, C compilation failure, runtime failure, and unknown case are reported as failures rather than skipped differential success; the site inventory classifies THOR sites and variant-only differences with source locations.

**Authorized-by:** Operator's comprehensive C-reclamation request; design §§1,5,7.

**Interfaces:**
- Consumes: `none`
- Produces: `run_case(case_id: str) -> dict[str, object]`

**Context:** The adapter is verification tooling, never the execution backend. Source originals remain byte-preserved. Build in per-invocation temporary directories; expose fixtures as explicit C node graphs to avoid reviving the interactive editor/parser. Compatibility changes must be listed and preserve semantics; historical undefined behavior is a reported blocker or documented narrow repair, not authority to copy a Python result. Normalized offsets are relative to the fixture's own arenas. The JSON case record contains id, technique, expected_result, expected_aliases, and expected_events; site records contain path, symbol, arena, trigger, disposition, and case_ids. Dispositions are parity, representation-equivalent, or variant-out-of-scope. C copy_graph forwarding MARKER is not the environment path MARKER. Source ranges must resolve against archived files, including all ws/fs rewind/reset sites in RED.C, PRIMS.C, ARITH.C, and MAIN.C and classification of STRICT/DEC6/WORK/SNARL differences.

**Proof:**
- Test: `tests/test_hilton_reference.py`
- Run: uv run pytest -q tests/test_hilton_reference.py
- Legs: (a) For every committed named case, invoke run_case and require evidence that the headless adapter executes the actual archived function bodies, not a substituted implementation; assert the normalized semantic result, sharing relations (including explicitly empty relations), and both ws/fs boundary event sequences against independently derived expectations, with unchanged boundaries recorded where appropriate; an atomic child-return fixture must restore exactly its saved fs; removing any required output field or altering any expected event must fail comparison [M1]; (b) For each corpus technique—environment return, closure sharing, atomic JOIN/lambda/RUP/primitive suffix contraction, IF/AND/OR discard, Y/REC reconstruction, equal/equal_star scratch graphs, and copy_graph/shift_memory forwarding—require at least one concrete fixture with independently calculated result and lifetime/alias assertions, and fail the corpus validator when that technique's fixture is removed [M2]; (c) Inject missing compiler, compile failure, abnormal C exit, and unknown id independently; each must fail explicitly and must not report a skip or successful comparison; validate every inventory location and compare the inventory against a complete source-site audit, including variant dispositions, during peer review [M3].

**Stale-if:**
- path-absent: `archives/THOR/RED.C`
- path-absent: `archives/THOR/MAIN.C`
- path-exists: `tools/hilton_reference/runner.py`

### Task 3: Publish child results before structural region return
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_closure_capture_parity.py`
- Test: `tests/test_red2_no_internal_leaks.py`

**Claim:** Force nested values, reclaim their temporary environments, then reuse those addresses without changing captured values or retained results. (derived)
Machine: M1. `_publish_child_result` represents surviving child values without references into the dying environment interval, preserving value, binding scope, and required sharing. M2. Machine-generated typed JOIN returns restore the saved free_space after publication without scan-and-skip retention; parent contexts and primitive state are restored consistently. M3. An opt-in root audit catches direct or transitive live references into reclaimed storage from live continuation roots, while ignoring dead arena words; malformed region/frame states fail before memory reuse.

**Authorized-by:** Design §§3–4; C RED.C jump_subgraph/inst_join.

**Interfaces:**
- Consumes: `MuredMachineState.free_space: int`
- Consumes: `run_case(case_id: str) -> dict[str, object]`
- Produces: `MuredMachine._publish_child_result(frame: _SubgraphFrame, result_address: int) -> int`

**Context:** This contract needs initialized free_space behavior and measured C child-return boundaries. Base _restore_environment_region checks only frame.env and one result graph; its skip tests are safety regressions, not the desired endpoint. Base CLOSURE stores an environment address and an adjacent untagged graph-code payload; REC has graph, environment, and block fields. Python representation requires scope-correct graph publication, not relocation of raw environment tuples into graph space. Typed frames may normalize a saved logical context with a PNP before child entry so a valid C-equivalent return has env equal to saved free_space. Enumerated audit roots: published result, live parent graph, saved APP paths, saved definition paths, outer subgraph frames, older closure/REC payloads, static definitions, and pending host argument. Follow these transitively with cycle protection; unreachable cells are not roots. Do not add host-side retained expression/closure storage. Ordinary production return relies on structural invariants; the full walker is diagnostic-only. Tests for malformed synthetic graphs may become typed-error tests, but cannot simply disappear.

**Proof:**
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_closure_capture_parity.py`
- Test: `tests/test_red2_no_internal_leaks.py`
- Run: uv run pytest -q tests/test_mured_memory_lifetimes.py tests/test_mured_transitions.py tests/test_closure_capture_parity.py tests/test_red2_no_internal_leaks.py
- Legs: (a) Publish an atomic value, captured lambda, EP chain, shared application, STRUCT with lazy field, and recursive residual separately; poison and then overwrite the entire old child interval, evaluate each retained value against its pre-publication meaning, and assert required aliases and De Bruijn scope are preserved; the typed diagnostic root walker must find zero pointers into the dying interval, and an injected dangling EP must fail that assertion [M1]; (b) Execute nested APP and closure-forcing JOIN cases with and without active primitives; compare saved/restored free_space and C normalized return boundaries, assert matching entry/return frames, parent env and restored countdown, require an exact physical restore even when the child captured a value, and fail if a production return invokes a scan-and-skip helper [M2]; (c) Parameterize direct and transitive references from published results, live parent graph nodes, saved APP paths, saved definition paths, outer subgraph frames, older CLOSURE/REC untagged payloads, static definitions, and pending host arguments, and require the diagnostic audit to reject a dangling publication before poisoning; an otherwise identical unreachable arena reference must not block return; missing/misordered frames and malformed saved boundaries must raise a typed machine error without reclaim [M3].

**Stale-if:**
- path-absent: `models/python/red2_engine/mured.py`
- path-absent: `tests/test_closure_capture_parity.py`

### Task 4: Reclaim dead graph suffixes at local contractions
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_fidelity.py`

**Claim:** Reduce atomic arguments and primitive redexes and see their dead temporary graph tails reused without discarding live shared graphs. (derived)
Machine: M1. JOIN, lambda argument consumption, and successful strict primitive contraction reclaim the structurally dead suffix specified by their node representation. M2. Pointer results, live aliases, partial primitives, type-stuck primitives, and q=0 residuals retain the graph data they still require. M3. Repeated fixed-size atomic child contractions reuse the same bounded graph workspace with no checkpoint or relinearization calls.

**Authorized-by:** Design §5; C inst_join, inst_lambda, ARITH.C and PRIMS.C make_result.

**Interfaces:**
- Consumes: `MuredMachine._publish_child_result(frame: _SubgraphFrame, result_address: int) -> int`
- Produces: `MuredMachine._join(word: Word) -> None`

**Context:** Correct publication must exist at runtime before environment and graph lifetime operations can be composed. C has separate head-destination ws reset and argument-tail ws decrement paths; Python cannot infer atomicity merely from opcode if a shared graph tail still survives. Python positive-q RBLOCK does not append C's LETREC spine, so RUP parity belongs to the recursive contract, not an unconditional decrement here. Snapshot events must identify each rewind's old/new boundary. Preserve existing compiler inlining and closure_slot sharing semantics.

**Proof:**
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_fidelity.py`
- Run: uv run pytest -q tests/test_mured_transitions.py tests/test_mured_memory_lifetimes.py tests/test_mured_fidelity.py
- Legs: (a) For atomic JOIN at head and argument destinations, each lambda binding descriptor form, unary arithmetic, binary arithmetic, comparisons, NOT, and supported character/type primitives, hand-construct the pre-state and assert the exact result slot, fsp rewind, stack delta, and retained words; cross-check equivalent C case events [M1]; (b) For each pointer-result, live-alias, partial, type-stuck, and zero-quantum case, poison only the claimed dead suffix and assert continuation/result correctness and unchanged live pointers; deliberately over-rewinding must make the exam fail [M2]; (c) Repeat the same finite fixed-size child workload at increasing repetition counts with checkpoint/recharge/relinearization replaced by raising sentinels; assert identical post-warmup boundary ranges and successful exact results, not merely positive rewind counts [M3].

**Stale-if:**
- path-absent: `tests/test_mured_transitions.py`

### Task 5: Complete lazy discard and acyclic Y scratch lifetimes
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_lockstep_parity.py`

**Claim:** Select lazy branches and unfold Y while discarding only the branches, saved contexts, and scratch storage that are no longer needed. (derived)
Machine: M1. IF and compiler-lowered AND/OR discard unselected graph/context storage without demanding the unselected branch; stuck and q=0 forms retain reconstructible residuals. M2. Y uses acyclic code reuse and bounded per-unfold scratch rather than persistent recursion objects, while retained recursive arguments stay valid. M3. The lazy-control fixture corpus preserves existing THOR/RED2 contraction-prefix parity and balances saved quantum/control contexts.

**Authorized-by:** Design §5; C prim_if, prim_and, prim_or, prim_y.

**Interfaces:**
- Consumes: `MuredMachine._publish_child_result(frame: _SubgraphFrame, result_address: int) -> int`
- Produces: `MuredMachine._select_if_branch(condition: str) -> None`
- Produces: `MuredMachine._y(word: Word) -> None`

**Context:** Publication's ownership guarantee is needed when selected branch results outlive condition evaluation. Existing AND/OR applications lower to IF; a new direct primitive implementation is unnecessary if equivalent lifetime/demand behavior is established. Existing THOR q accounting is the prefix oracle; C fixtures establish lifetime technique rather than equal step counts. No assertion of constant space for Y programs whose call depth or output grows. Direct and APP-valued branches carry different saved-path obligations. Acyclic means no knot-tying graph introduced by Y, not that captured letrec structures can never be cyclic.

**Proof:**
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_lockstep_parity.py`
- Run: uv run pytest -q tests/test_mured_memory_lifetimes.py tests/test_mured_transitions.py tests/test_lockstep_parity.py
- Legs: (a) For IF true/false and lowered AND/OR short-circuit cases, combine atomic/APP branches with captured paths and an unselected failing or effectful branch; assert it is never entered and its saved contexts are removed, then poison/reuse the dead suffix; separately assert stuck and q=0 residuals retain both required branches [M1]; (b) Exercise pointer and immediate-function Y unfoldings with expected normalized code-reference topology and exact scratch deltas, poison dead scratch before using retained recursive arguments, and compare repeated fixed-live-state unfold boundaries rather than growing-output workloads [M2]; (c) For the committed IF/AND/OR/Y corpus, compare prefixes over zero through a sufficient quantum to cover each branch/stop transition, assert final canonical results, and inspect saved-quantum/control depth before and after nested lazy contexts [M3].

**Stale-if:**
- path-absent: `tests/test_lockstep_parity.py`

### Task 6: Close recursive binding and lazy structure lifetime gaps
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_red2_recursive_definitions.py`
- Test: `tests/test_red2_recursive_structs.py`
- Test: `tests/test_mured_memory_lifetimes.py`

**Claim:** Reduce and reconstruct recursive bindings and select lazy structure fields without retaining completed child environments or invalidating recursive captures. (derived)
Machine: M1. RBLOCK/RUP/RECP, including backward RECP at q=0, use balanced typed child regions and preserve correct recursive environment/path layout. M2. STRUCT construction and selector returns publish escaping fields before environment reclaim and reclaim only dead selector/construction spines. M3. Recursive/structure fixtures preserve q-prefix and final results under poison-and-reuse, with no legacy frameless machine-generated JOIN or unnecessary copied positive-q RBLOCK spine.

**Authorized-by:** Design §§4–5; C inst_letrec, inst_rup, inst_rec, inst_rec_1 and structure lambda encodings.

**Interfaces:**
- Consumes: `MuredMachine._publish_child_result(frame: _SubgraphFrame, result_address: int) -> int`
- Produces: `MuredMachine._recp(word: Word) -> None`
- Produces: `MuredMachine._copy_struct_value_to_result(source_address: int, destination: int) -> None`

**Context:** Publication's runtime guarantee is needed for lazy fields and residual recursive bodies. Base backward q=0 RECP manually pushes JOIN and saved primitive state instead of a _SubgraphFrame. Base REC entries occupy three words; RUP currently assumes contiguous REC entries, so marker traversal and block boundaries require explicit checks. C rewinds copied LETREC nodes in positive-q RUP; Python already avoids those copies and must preserve that representation-equivalent reclamation. Non-selected lazy fields can be live through aliases even when the selector spine is dead. Address-specific historical tests may change only with an equivalent explicit lifetime assertion.

**Proof:**
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_red2_recursive_definitions.py`
- Test: `tests/test_red2_recursive_structs.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Run: uv run pytest -q tests/test_mured_transitions.py tests/test_red2_recursive_definitions.py tests/test_red2_recursive_structs.py tests/test_mured_memory_lifetimes.py
- Legs: (a) Cover positive-q and q=0 forward/backward RECP, mutually recursive blocks, outer captured paths separated by PNP, and active primitive countdown; assert matched typed entry/return frames, saved free_space restoration, REC field interpretation and balanced phi/control state [M1]; (b) Select atomic, application, nested STRUCT, and lambda fields separately from shared structures; force allocation into poisoned reclaimed intervals before consuming retained fields, verify unselected lazy failures are not forced, and assert exact selector dead-spine reuse; independently construct shared lazy structures and assert construction rewinds exactly its dead spine while retained constructor operands and aliased fields remain evaluable after that suffix is poisoned and reused [M2]; (c) Run recursive-definition/structure prefix fixtures and depth-four regression with reclaim poisoning enabled; overwrite reclaimed intervals through subsequent normal allocation before evaluating surviving recursive captures, and assert both canonical results at each q-prefix and final results against the independent expected fixtures; reject generated JOIN without its typed frame, and assert positive-q RUP graph boundary reflects no copied RBLOCK spine rather than a blind C-style subtraction [M3].

**Stale-if:**
- path-absent: `tests/test_red2_recursive_definitions.py`
- path-absent: `tests/test_red2_recursive_structs.py`

### Task 7: Give structural equality explicit temporary graph lifetimes
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `models/python/thor_compile/red2.py`
- Test: `tests/test_mured_equality.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_lockstep_parity.py`
- Test: `tests/test_red2_no_internal_leaks.py`

**Claim:** Compare structured and lambda-valued expressions using graph reduction, reclaim equality's temporary graphs, and retain correct residual expressions when comparison cannot finish. (derived)
Machine: M1. Graph-driven EQUAL? handles the committed atomic, shared-closure, application, lazy-structure, lambda-alpha-equivalence, and free-variable cases with the expected true/false/stuck behavior. M2. Equality graph splitting and lambda wrapping use ordinary typed publication/region returns; completed comparison scratch is reclaimed without losing live operands or sharing. M3. Exhausted-quantum and stuck equality reconstruct public EQUAL? expressions with correct binder scope, not exposed internal comparison continuations.

**Authorized-by:** Comprehensive request; design §5; C prim_equal, prim_equal_star, nodes_equal, wrap_lambdas.

**Interfaces:**
- Consumes: `MuredMachine._publish_child_result(frame: _SubgraphFrame, result_address: int) -> int`
- Produces: `MuredMachine._fire_equality() -> None`

**Context:** Publication behavior is required by equality's generated child graphs. Current Python EQUAL? routes through the binary primitive path and must not be mistaken for C's structural/alpha equality implementation. This contract adds only the equality machinery needed for the archived functional behavior, not logic unification. Use C results for historical supported cases and THOR prefixes for existing shared semantics; a semantic conflict is a blocker to resolve explicitly, not permission to weaken an oracle. No host AST equality, eager normal-form serialization, persistent comparison heap, or second reducer is allowed. Any internal opcode/context must remain confined to the machine; compiler/serialization source instructions stay backward compatible.

**Proof:**
- Test: `tests/test_mured_equality.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_lockstep_parity.py`
- Test: `tests/test_red2_no_internal_leaks.py`
- Run: uv run pytest -q tests/test_mured_equality.py tests/test_mured_transitions.py tests/test_lockstep_parity.py tests/test_red2_no_internal_leaks.py
- Legs: (a) For each atomic, shared-closure, application, lazy-structure, alpha-equivalent lambda, alpha-inequivalent lambda, and free-variable row, assert the concrete true/false/stuck result against independent fixtures and normalized C results where supported; include mismatching tags/arity and a lazy unused divergent field where comparison can decide early [M1]; (b) Capture allocation/return/rewind traces for split applications and wrapped lambdas, assert typed publication at each child return, poison/reuse dead comparison regions, then evaluate aliased operands; repeat a fixed-size completed comparison and assert its post-warmup scratch envelope does not grow [M2]; (c) Interrupt each comparison fixture at q=0 and intervening contraction boundaries, assert canonical public residuals and binder indices, resume to the expected outcome, and scan both result words and decompiled output for leaked internal comparison state; any leaked internal continuation must fail the exam [M3].

**Stale-if:**
- path-absent: `models/python/thor_compile/red2.py`
- path-exists: `tests/test_mured_equality.py`

### Task 8: Preserve sharing during residual copy, relocation, and arena reset
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `models/python/thor_compile/red2.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_compile.py`
- Test: `tests/test_red2_recursive_definitions.py`
- Test: `tests/test_red2_no_internal_leaks.py`

**Claim:** Compact a completed residual graph, retain its shared subgraphs and definitions, and continue reducing in the same machine with dead workspace available again. (derived)
Machine: M1. Residual relinearization copies reachable graph nodes with forwarding/memoization so repeated references retain sharing and unreachable garbage is omitted. M2. Relocation rewrites graph-owned pointer fields while preserving static definition ownership; recharge resets fsp/free_space/control state in the same machine without altering the residual's semantics. M3. Capacity failure and malformed residual pointers fail before installing a partially relocated graph or corrupting definitions.

**Authorized-by:** Design §§5–6; C MAIN.C copy_graph, shift_memory, LAM_RED/LAM_RDEF and RED.C reduce reset.

**Interfaces:**
- Consumes: `MuredMachine._publish_child_result(frame: _SubgraphFrame, result_address: int) -> int`
- Produces: `MuredMachine.recharge_quantum(quantum: int) -> MuredMachineState`

**Context:** Publication is needed to ensure the residual no longer depends on temporary environment storage before compaction. C marks old graph roots with forwarding MARKER; Python may use a temporary map rather than destructively marking immutable/static definitions. The map is bounded to the copy operation and not a persistent execution heap. Handle APP and RBLOCK code pointers, symbol definitions, STRUCT fields and recursive residuals according to their representation; do not relocate integer literals that happen to resemble addresses. Existing compiled definitions occupy a protected high region. C return-address conventions in copy_graph/shift_memory differ; determine bounds from executable fixtures, not their inconsistent prose comments. Preserve static bytes and identity through repeated recharge.

**Proof:**
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_compile.py`
- Test: `tests/test_red2_recursive_definitions.py`
- Test: `tests/test_red2_no_internal_leaks.py`
- Run: uv run pytest -q tests/test_mured_memory_lifetimes.py tests/test_mured_compile.py tests/test_red2_recursive_definitions.py tests/test_red2_no_internal_leaks.py
- Legs: (a) Compact a diamond graph with two references to the same child and unreachable poisoned garbage; assert equal relocated child addresses, one physical copy of the child, exclusion of garbage and canonical result parity; repeat with RBLOCK and STRUCT descriptors and compare C forwarding fixtures [M1]; (b) Snapshot machine identity and static definition words, recharge a q=0 captured/recursive residual repeatedly, and assert unchanged identity/static bytes, relocated dynamic pointers, free_space reset to the exact working-memory limit, fsp reset to the independently counted compact graph/STOP boundary, balanced empty control state, no integer-literal relocation, and final/prefix equivalence; allocate and evaluate a fresh continuation through addresses formerly occupied by unreachable workspace to prove those addresses are reusable rather than merely unreferenced [M2]; (c) Exercise exact fit, one-word-short capacity, invalid APP address, malformed RBLOCK target, and invalid environment escape independently; failure cases must raise typed errors and leave the installed arena, definitions, boundary registers, and control state unchanged [M3].

**Stale-if:**
- path-absent: `models/python/red2_engine/mured.py`
- path-absent: `tests/test_mured_compile.py`

### Task 9: Prove integrated bounded-live-state reclamation and exactly-once IO
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Modify: `models/python/red2_engine/io_runtime.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_red2_io_runtime.py`
- Test: `tests/test_mured_cli.py`

**Claim:** Run fixed-live-state pure and IO workloads for longer without accumulating dead machine storage, and preserve the exact host-effect sequence when explicit checkpointing is needed. (derived)
Machine: M1. The selected bounded-live-state corpus completes with stable post-warmup graph/environment/control envelopes when all coarse checkpoint/recharge/relinearization entry points are forbidden. M2. Host checkpoints and quantum-triggered reconstruction are separately observable; forced low-headroom and quantum-exhaustion cases preserve machine identity and exactly-once ordered effects. M3. Growing retained outputs remain intact, diagnostics are opt-in, and unsupported structured IO-BIND results still fail explicitly rather than escaping into upper-arena storage.

**Authorized-by:** Design §6; integration acceptance for the operator's memory reclamation request.

**Interfaces:**
- Consumes: `MuredMachine._join(word: Word) -> None`
- Consumes: `MuredMachine._select_if_branch(condition: str) -> None`
- Consumes: `MuredMachine._y(word: Word) -> None`
- Consumes: `MuredMachine._recp(word: Word) -> None`
- Consumes: `MuredMachine._copy_struct_value_to_result(source_address: int, destination: int) -> None`
- Consumes: `MuredMachine._fire_equality() -> None`
- Consumes: `MuredMachine.recharge_quantum(quantum: int) -> MuredMachineState`
- Produces: `test_integrated_reclamation_without_coarse_compaction()`

**Context:** This contract needs the combined runtime behavior of local contraction, lazy control, recursive publication, equality scratch reuse and compaction. Base's 5,000-loop test permits recharge_quantum despite asserting zero host checkpoints; that does not prove incremental-only memory behavior. Measure local joins over increasing completed iterations of finite fixed-state workloads and use a separate growing-output control. At least one program combines nested strict arguments, closure capture, lazy selection and atomic IO-BIND. The fixed host-headroom threshold remains unchanged unless a separately justified change is essential; tiny default-policy machines may intentionally checkpoint each dispatch. Do not count diagnostics' own event list as machine arena usage or let default execution allocate such a list indefinitely. C has no Asgard host scheduler, so exact effects are checked against deterministic fake hosts and existing IO semantics rather than invented C IO parity.

**Proof:**
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_red2_io_runtime.py`
- Test: `tests/test_mured_cli.py`
- Run: uv run pytest -q tests/test_mured_memory_lifetimes.py tests/test_red2_io_runtime.py tests/test_mured_cli.py
- Legs: (a) `test_integrated_reclamation_without_coarse_compaction` runs increasing finite repetition counts for a fixed-size strict pure case, a recursive lazy/selector case, equality scratch reuse, and an atomic IO-BIND loop; patch checkpoint_quantum, recharge_quantum and residual-relinearization entry points to raise, allow only cheap refresh, assert exact results/effects and identical post-warmup boundary envelopes per repeated state rather than an arbitrary arena-size threshold [M1]; (b) Force a host-headroom checkpoint and a quantum-exhaustion recharge in separate deterministic CLOCK/UART RX/TX scenarios; assert distinct event/counter evidence, one machine identity, exact ordered input consumption/output bytes/call counts, and no replay across repeated boundaries [M2]; (c) Retain an increasing output structure and verify its full contents before and after reclaim, run the same fixture with diagnostics omitted, explicitly false, and explicitly true; the first two must accumulate no events, invoke no diagnostic event sink, and emit no diagnostic stdout/stderr, while the enabled run must expose expected reclamation events without changing results; assert structured IO-BIND rejection and no upper-arena problem reservation, and cover supported direct EP aliases through reclaim and resume [M3].

**Stale-if:**
- path-absent: `tests/test_red2_io_runtime.py`
- path-absent: `tests/test_mured_cli.py`

### Task 10: Publish the complete source-to-runtime reclamation account
**Type:** implementation
**Review:** peer

**Files:**
- Modify: `docs/red2-incremental-memory-reclamation.md`
- Modify: `docs/mured-thesis-notes.md`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `README.md`

**Claim:** Inspect one current account of the memory model and trace each functional C reclamation technique to an implemented behavior and reproducible evidence. (derived)
Machine: M1. Current documentation consistently distinguishes free_space, env, fsp, region return, graph forwarding and coarse compaction, and replaces obsolete current-state claims about monotonic env_frontier or scan-and-skip return. M2. The documented site coverage and measured limitations agree with the executable C inventory and integrated runtime exams, without claiming C address/quantum identity or constant memory for growing live data.

**Authorized-by:** Design §§1–7; operator request for comprehensive coverage.

**Interfaces:**
- Consumes: `test_integrated_reclamation_without_coarse_compaction()`
- Consumes: `run_case(case_id: str) -> dict[str, object]`
- Produces: `none`

**Context:** Documentation needs measured integrated behavior, not a future-tense completion claim. Base docs/red2-incremental-memory-reclamation.md has an old monotonic-allocation account followed by a guarded-reclamation status addendum; consolidate it instead of appending another contradictory status section. Earlier dated plans/specs remain historical. Enumerate C source sites, Python entry points, semantic differences, proof commands, outcomes and excluded variant-only logic machinery. Explain focus replacement/teardown as machine/object lifecycle rather than invented runtime instructions. A historical reference harness compilation problem or unresolved semantic discrepancy must be reported as a limitation and blocks a blanket completion claim.

**Proof:**
- Run: uv run pytest -q tests/test_hilton_reference.py tests/test_mured_memory_lifetimes.py tests/test_red2_io_runtime.py
- Run: git diff --check
- Legs: (a) Peer-read all four changed documents against current state fields and transition implementations, checking each named memory concept and explicitly locating/removing contradictory present-tense monotonic/scan-and-skip claims; reject treating copy forwarding as environment PNP or checkpointing as local reclamation [M1]; (b) Re-run the reference and integrated exams and compare their actual output and inventory with every coverage/measurement assertion in the documents; fail the review for any undocumented excluded source site, unsupported C address/quantum identity or constant-space claim for growing data, or fabricated timing/space result [M2].

**Stale-if:**
- path-absent: `docs/red2-incremental-memory-reclamation.md`
- path-absent: `docs/mured-thesis-notes.md`

### Task 11: Gate the integrated result and archive preservation
**Type:** gate
**Review:** peer

**Files:**
- Test: `tests/test_hilton_reference.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_equality.py`
- Test: `tests/test_red2_io_runtime.py`

**Claim:** Run the integrated verification and see a working free_space runtime with the reclamation evidence passing together, without changes to Hilton's archived source. (derived)
Machine: M1. The adopted integration tree passes the full Python tests, Ruff and mypy, including C differential, lifetime, equality, and IO exams without skipped required reference cases. M2. Archives and thesis transcription are unchanged from execution BASE; unresolved publication, parity, memory-envelope, or exactly-once failures prevent acceptance.

**Authorized-by:** Design §7; plan-level Acceptance.

**Interfaces:**
- Consumes: `test_integrated_reclamation_without_coarse_compaction()`
- Consumes: `run_case(case_id: str) -> dict[str, object]`
- Produces: `none`

**Context:** This is a write-nothing integration gate, not an implementation task or release authorization. Gate evidence refers to the adopted tree with all contracts present. Global archive preservation also runs per task. The Python reference adapter requires a functioning C compiler in the acceptance environment; missing tooling is a blocker to provision, not a pytest skip. Existing unrelated failures must be isolated and disclosed; do not claim green based on just the focused baseline. No push, merge, benchmark publication, or test weakening is authorized here.

**Proof:**
- Test: `tests/test_hilton_reference.py`
- Test: `tests/test_mured_memory_lifetimes.py`
- Test: `tests/test_mured_equality.py`
- Test: `tests/test_red2_io_runtime.py`
- Run: uv run pytest -n 4 --dist loadfile
- Run: uv run ruff check .
- Run: uv run mypy models/python tests
- Run: git diff --exit-code "$ULTRA_BASE" -- archives thesis
- Run: git diff --check
- Legs: (a) Require successful full-suite, Ruff and mypy exits on the integration tree and inspect the C adapter/lifetime/equality/IO results for missing or skipped required cases; the required reference tests themselves fail rather than skip when tooling is absent [M1]; (b) Require an empty archive/thesis diff against the execution base and reconcile peer findings against the final tree; require the IO exams' exact expected ordered effect lists and exact per-effect call counts so duplication, omission, replay, or reorder each fail; any unresolved publication, parity, bounded-envelope or exactly-once/effect-order failure blocks acceptance rather than being downgraded to an undocumented limitation [M2].

**Stale-if:**
- path-absent: `pyproject.toml`
- path-absent: `archives/THOR/RED.C`

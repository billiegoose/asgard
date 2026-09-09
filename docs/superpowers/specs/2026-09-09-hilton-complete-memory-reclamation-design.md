# Hilton memory reclamation and explicit free_space

Status: proposed design accompanying the requested ultraplan; runtime implementation is not authorized by this document alone.

## 1. Request and scope

The operator requested a comprehensive implementation plan for the memory-reclaiming techniques in Hilton's C code and replacement of `env_frontier` with a `free_space` pointer like Hilton's. The subsequent instruction was to put together an ultraplan. This delivery is planning only; the pointer conversion is the first implementation contract, not an unreviewed runtime edit.

Primary authority: `archives/THOR/RED.C`, `PRIMS.C`, `ARITH.C`, and `MAIN.C`. This is the C HORSE/THOR release, not a byte-for-byte implementation of the dissertation's RED2 microarchitecture. Chapter 4 and the Scheme FP/RED simulator remain the architectural cross-check. Map lifetimes rather than copying incompatible node layouts or contraction counts. Keep archive originals unchanged. Compare SNARL variants and inventory STRICT/DEC6/WORK differences, but do not silently add logic programming, unification, backtracking heaps, or experimental RPTR semantics to the functional runtime.

The target is `models/python/red2_engine/mured.py` and its compiler/host adapters, not the Rust AST evaluator or the hardware prototypes. No general tracing collector, reference-counted heap, persistent Python closure heap, second evaluator, or larger default arena is proposed.

## 2. Baseline evidence

Planning base: `9a7acc8d84beb142cce00e359049ed68f85a20cd` (2026-09-09 inspection).

`uv run pytest -q tests/test_mured_memory_lifetimes.py tests/test_mured_state.py tests/test_red2_recursive_structs.py` returned `42 passed in 2.24s`. This is focused baseline evidence, not full-suite verification.

The base already has memory diagnostics, typed `_SubgraphFrame`, guarded child reclamation, primitive graph rewinds, and same-machine checkpointing. Earlier plan documents are historical records, not an accurate list of still-missing work. `docs/red2-incremental-memory-reclamation.md` contains contradictory pre-change and post-change descriptions that need consolidation.

Specific gaps:

- `env_frontier` is optional and several callers fall back to logical `env`; an initialized independent physical register is preferable.
- `_restore_environment_region` tests `frame.env` and one published graph; it does not establish the absence of references from all live parent graph nodes, saved contexts, older closures, REC payloads, definitions, or suspended host arguments.
- It silently retains regions when the guard finds a dependency; this is not the unconditional saved-`fs` return in C.
- `_recp` with q=0 bypasses typed `_enter_subgraph` and builds a legacy JOIN.
- `_rup`'s representation differs from C: Python does not copy positive-quantum RBLOCK descriptors in the first place, so blindly applying C's `ws -= n` would be incorrect.
- Python AND/OR source applications are lowered into IF, while C uses primitive-specific spine sliding and saved-context discard.
- Python equality currently dispatches through `_apply_binary_primitive`; the C equality machinery handles graph splitting and lambda wrapping with its own temporary graphs and JOIN boundaries.
- The 5,000-iteration IO test checks `host_checkpoints == 0` but permits `recharge_quantum`; that does not by itself establish absence of coarse reconstruction.

## 3. Architectural choice

Choose explicit physical allocation plus structural region lifetimes, with result publication that establishes the preconditions of a constant-time region return. Rejected alternatives: a cosmetic rename with permanent scan-and-skip reclamation (does not meet historical lifetime intent), or removing the guard immediately (can reclaim captured values).

The first contract establishes `MuredMachineState.free_space` as the sole initialized integer physical boundary. Omitted legacy construction may initialize it once from `env` before machine execution, but runtime allocation never falls back to `env`. Remove `env_frontier` from executable state and migrate its in-repository consumers together. Do not maintain two independently writable allocator fields. `fsp` retains its existing graph-boundary name and last-occupied-address convention. Python pointers are integer arena addresses, not native C pointers.

For a machine-owned state: `0 <= fsp < free_space <= working_memory_limit <= len(memory)`. Validate logical environment roots structurally and within their permitted arena, not by using them to determine headroom. PNP path bridging is separate from physical allocation. Block allocations reserve their complete footprint, including any marker, before writing; collisions leave registers, memory, stacks, and diagnostic counters unchanged.

## 4. Reclamation and publication

Each historical child entry has one typed region frame containing the saved physical boundary and primitive state. Historical returns publish/share the child result, discard dead graph suffixes where justified, restore `free_space`, and resume the parent context. For C-equivalent entries the parent continuation satisfies `env == saved free_space`; RED2-specific contexts must be reconciled by explicit path bridging at entry, not by silently freeing a live saved path.

Publication must eliminate dependence on the dying environment region without changing lambda capture, De Bruijn scope, q=0 residuals, lazy demand, sharing, or effect ordering. Graph-owned residual representation and existing longer-lived sharing cells are the permitted destinations. A copied graph containing a raw EP into the dying interval is not publication. Do not copy mutable environment closures into graph addresses and assume environment-address decoding will accept them. RET/REC reconstruction needs explicit representation handling.

Debug verification enumerates roots and follows typed pointer fields transitively: parent graph and result descriptors, saved APP/definition/subgraph contexts, current continuation, older closure/REC payloads, static definition references, and pending host argument descriptors. Word(None, ...) payloads are interpreted by their owning closure/REC layout, never as arbitrary integers. Unreachable arena words are not roots. Cycle guards in the diagnostic walker are allowed; a production tracing collector at each JOIN is not.

Once publication is proven for machine-generated states, normal JOIN restores the region without a scan-and-skip fallback. Malformed synthetic states fail with a typed machine error before poisoning/reuse. Debug poisoning and reallocation tests must demonstrate that a preserved value is actually usable after old addresses have been overwritten, not just readable immediately after return.

## 5. Complete technique inventory

| Technique | C authority | Python obligation |
| --- | --- | --- |
| Descending physical free-space allocation | RED.C `make_closure`, `push_marker`, `inst_letrec` | Explicit `free_space`, atomic reservations, PNP path independence |
| Nested environment reset | RED.C `jump_subgraph`, `inst_join` | Typed frame coverage, publish before unconditional normal restore |
| Closure update/sharing | RED.C `inst_closure`, `inst_join` | Parent-owned atomic updates and correct non-atomic publication |
| Atomic JOIN tail elimination | RED.C `inst_join` | Head destination reset versus argument-tail removal; preserve pointer results |
| Lambda argument consumption | RED.C `inst_lambda` | Consume descriptor and saved context, rewind only dead suffix |
| Recursive spine removal | RED.C `inst_rup`, `inst_rec_1` | Equivalent space behavior despite Python RBLOCK representation; q=0 reconstruction returns properly |
| Primitive redex overwrite | ARITH.C; PRIMS.C `make_result`, `prim_not`, character conversions | Reuse result slot; failed/partial/inhibited calls do not reclaim live operands |
| Lazy branch/context discard | PRIMS.C `prim_if`, `prim_and`, `prim_or` | IF and lowered AND/OR preserve demand, contexts, residuals, and dead-spine reclamation |
| Acyclic recursion/code reuse | PRIMS.C `prim_y` | No recursion heap/knot; scratch code does not leave a run-long tail |
| Structural/equality scratch lifetimes | PRIMS.C `prim_equal`, `prim_equal_star`, `nodes_equal`, `wrap_lambdas` | Graph-driven equality and lazy structure lifetimes; no eager AST comparison |
| Reachable graph evacuation with forwarding | MAIN.C `copy_graph` | Preserve repeated references and omit unreachable garbage during residual compaction |
| Relocation and arena reset | MAIN.C `shift_memory`, LAM_RED/LAM_RDEF; RED.C `reduce` | Rewrite graph pointers, preserve static definitions, reset same-machine working region safely |
| Control/auxiliary stack discard | RED.C/PRIMS.C pop operations | No retained dead saved paths/frames; typed control/quantum state balanced |
| Focus replacement/session teardown | MAIN.C focus handling, EXIT | Document existing Python machine/object lifecycle equivalence; no artificial VM opcodes |

C uses MARKER both for environment paths and temporary copy forwarding. These have different lifetimes; Python need not destructively overwrite source code to reproduce forwarding. Pointer addresses and instruction counts need not match between representations. An archive-site inventory must distinguish implemented parity, representation-equivalent behavior, and excluded non-functional variants. A source grep alone is not proof of runtime parity.

## 6. Checkpoints and host IO

Compaction is retained as an explicit residual-world boundary, analogous to C's copy/shift before another reduction. q=0 reconstruction is not a tracing collector and is not allowed to change the observed contraction prefix or replay an effect. Preserve machine identity, compiled definitions, and exactly-once host dispatch across recharge.

Keep existing atomic IO-BIND scope; structured host return values are not added incidentally. Direct EP aliases accepted by the existing API still require ownership validation. Preserve current default checkpoint policy unless measurements justify a separately reviewed policy change. Report host checkpoint calls and quantum-triggered reconstruction/recharge separately. A no-compaction test must forbid both, including indirect relinearization calls.

Do not promise constant memory for all recursion or growing outputs. Prove exact local reuse and use bounded-live-state workloads for plateau measurements; report graph, environment, control stack, and diagnostic-buffer storage separately. Growing retained structures must remain correct, not be reclaimed to make a chart flat. Diagnostics remain opt-in and must not introduce an unbounded default trace buffer.

## 7. Verification and source fidelity

A headless C reference adapter outside archives executes the actual archived reducer/primitive bodies on explicit node fixtures. It emits normalized results, sharing topology, and ws/fs region events. Portability shims and any necessary undefined-behavior repairs are explicit and reviewed, never silently folded into the historical authority. Fixtures compare semantic lifetime boundaries, not raw C/Python address layouts. Missing C compiler or a reference mismatch fails the required differential job; it is not a successful skipped parity claim.

Proof combines small transition matrices, poison-and-reuse capture tests, q=0 and contraction-prefix parity, a cross-representation C fixture corpus, finite bounded-state stress tests, CLI/IO tests, and a full integration run. Every normal reclamation mechanism receives a positive reuse case and a negative live-reference case. Timeouts only guard harness failures; finite programs terminate normally, and infinite IO subprocess tests terminate explicitly after the expected output appears.

The requested plan has independent proof review per task and mechanical claims-v1 validation. Selecting execution later authorizes runtime work. No C port, memory optimization, commit, push, or merge is performed merely by writing this specification.

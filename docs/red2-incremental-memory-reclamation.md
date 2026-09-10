# RED2 incremental memory reclamation

## Purpose

This document is the current source-to-runtime account of memory reclamation in Asgard's faithful Python RED2 path. It connects the functional THOR/RED2 C sources in `archives/THOR/` to the implemented `MuredMachine` transitions and to executable differential/lifetime tests.

The important distinction is between **incremental lifetime reclamation** performed by ordinary RED2 transitions and **coarse residual reconstruction** performed at an explicit scheduler boundary. They are different mechanisms and are tested separately.

The current Python machine models one shared working-memory arena with two live boundaries:

- `fsp`: the last occupied problem/result graph word, corresponding to archived `ws`;
- `free_space`: the descending environment/free-space boundary, corresponding to archived `fs`;
- `env`: the logical environment-path tip used by variable lookup; it is not the allocator;
- `c`: the live control-stack top.

There is no current `env_frontier` execution field. Older plans and earlier revisions of this note used that name while the physical-frontier repair was still in progress. The implemented state field is now `free_space`, and it can move downward on allocation and upward when a proven-dead child region is returned.

## 1. The archived lifetime model

The functional archived reducer does not treat the environment as a monotonic heap. Graph and environment storage occupy opposite ends of one arena:

```text
low addresses                                  high addresses
+-----------------------------------------------------------+
| problem/result graph ->      free      <- environment     |
+-----------------------------------------------------------+
                 ^ ws/fsp                    ^ fs/free_space
```

Archived `fs` and `env` have different jobs. `fs` is the physical allocation boundary; `env` is a logical path. `push_marker()` bridges a new physical segment back to an older logical environment when `env != fs`. The corresponding Python representation is `PNP`.

`jump_subgraph()` establishes a region lifetime. It saves the current free-space boundary and primitive state before entering a child. `inst_join()` publishes the child result into a longer-lived owner, restores the saved `fs`, restores primitive/control state, and resumes the parent. Environment cells allocated only for that child are then reusable without a tracing pass.

Graph reclamation is separate. Instruction-specific contractions overwrite dead spines or rewind `ws` as soon as the reducer knows a graph suffix is dead. This is structural/region reclamation, not tracing garbage collection.

## 2. Current Python state and ownership rules

`MuredMachineState` stores `fsp`, `env`, `free_space`, and `c` explicitly. A typed `_SubgraphFrame` saves the parent logical `env`, saved `free_space`, primitive name, and primitive countdown.

The current child-return order is deliberately ownership-first:

1. reduce the child;
2. publish any child result that would otherwise reference the dying environment region;
3. prove that the candidate region has no surviving graph/environment reference;
4. restore the saved `free_space` and parent path;
5. reclaim the corresponding graph suffix when the contraction permits it;
6. resume the parent.

A region is never reclaimed merely because a numerical address is below a saved boundary. Publication and ownership validation happen first. Tests can poison returned environment cells so stale references fail immediately.

Direct `EP` aliases follow the same rule. An `EP` into a dying region is either materialized/published into a longer-lived graph/environment owner before return or the return cannot reclaim that region. A raw residual `EP` that escapes into reclaimed working memory is rejected; residual relinearization does not invent a new ownership exception.

## 3. C reclamation techniques and Python implementations

The executable Hilton reference corpus requires these functional techniques: environment return, closure sharing, atomic JOIN, lambda suffix contraction, RUP suffix contraction, primitive suffix contraction, IF/AND/OR discard, Y reconstruction, REC reconstruction, equality scratch construction, equality lambda wrapping, copy/shift forwarding, reduce reset, equality head-promotion compatibility, and UBV-index equality compatibility.

The main source-to-runtime mapping is:

| Archived functional source | C lifetime behavior | Python entry point / behavior | Executable evidence |
| --- | --- | --- | --- |
| `RED.C:jump_subgraph`, `RED.C:inst_join` | save/restore `fs`; return child control state | `_enter_subgraph()`, `_join()`, `_restore_environment_region()` with typed `_SubgraphFrame` | `atomic-child-return`, `closure-sharing`, `join-pointer-live`; memory lifetime tests |
| `RED.C:inst_join`, `RED.C:inst_closure` | update a longer-lived closure with atomic child value | `_join()` publishes/shareable atomic closure/EP values before region return | `closure-sharing`; publication lifetime tests |
| `RED.C:inst_join` | overwrite atomic parent result and rewind `ws`; retain pointer result graph | `_join()` rewinds `fsp` for dead local tails while preserving referenced result graphs | `atomic-child-return`, `join-pointer-live`; integrated bounded-state test |
| `RED.C:inst_lambda` | beta contraction consumes application suffix; allocate current-region binding | `_lambda()` plus environment allocators and local graph rewind | `lambda-consume`, `reduce-identity`; lifetime tests |
| `RED.C:inst_rup`, `inst_rec`, `inst_rec_1` | recursive residual/update reconstruction and suffix contraction | `_recp()`, RUP/REC reconstruction/publication paths | `rup-contract`, `rec-q0`; recursive lifetime tests |
| `ARITH.C`, primitive helpers | successful primitive overwrites result slot and resets `ws` | `_fire_primitive()` contracts to the result location and returns dead scratch | `primitive-add`; strict primitive/lifetime tests |
| `PRIMS.C:prim_if` | discard condition/primitive/unselected branch spine and contexts | `_select_if_branch()` / `_skip_if_branches()` | `if-true`, `if-false`; lazy selection tests |
| `PRIMS.C:prim_and`, `prim_or`, `make_result` | decisive short-circuit drops remaining graph/control state | source lowering to lazy `IF` plus faithful IF lifetime behavior | `and-discard`, `or-discard`; parity/lifetime tests |
| `PRIMS.C:prim_y` | acyclic `Y f` reconstruction reuses code rather than knot-tying a heap object | `_y()` reuses the function graph and bounded scratch | `y-reconstruct`; integrated local-lifetime test |
| `PRIMS.C:prim_equal`, `prim_equal_star`, `wrap_lambdas`, `nodes_equal` | bounded comparison scratch, recursive structural comparison, lambda wrapping, sharing shortcuts | `_fire_equality()` and equality task/frame machinery reuse local graph/control scratch | `equal-scratch`, `equal-star-wrap`, promotion/UBV cases; `tests/test_mured_equality.py` |
| `MAIN.C:copy_graph` | destructive source MARKER forwarding preserves repeated PTR aliases while omitting garbage | `_relinearize_graph()` uses an explicit local forwarding map without mutating source memory | `copy-shift`; residual sharing tests |
| `MAIN.C:shift_memory` | relocate copied graph addresses | faithful loader relocation and residual graph rebuilding rewrite graph-owned addresses | `copy-shift`; relocation tests |
| `RED.C:reduce` | initialize/recover invocation boundaries and reusable control state | machine initialization/restart and ordinary object lifecycle | `reduce-identity`; CLI/runtime tests |
| `MAIN.C:rep_loop`, `handle_command` | replace interactive focus, copy/shift retained graph, free process-owned buffers | scheduler/machine lifecycle and Python object teardown, not invented μRED instructions | inventory classification only |

`copy_graph()`'s source-code MARKER is a forwarding marker used by the coarse copier. It is not the environment-path MARKER represented by Python `PNP`, and copy forwarding must not be treated as evidence for environment region return.

## 4. Equality scratch is part of the graph lifetime model

The current faithful Python path implements recursive/general structural `EQUAL?` behavior for the supported functional THOR surface, including alpha-equivalent lambdas, lazy structures, pointer/closure sharing cases, q=0 residuals, and Hilton's UBV/free-variable distinctions.

The equality implementation has its own typed control frames and local graph scratch. The lifetime requirement is not that equality allocate nothing; it is that repeated fixed-live-state comparisons reuse a bounded envelope and return dead scratch when the comparison contracts.

The C reference adapter contains narrowly logged compatibility repairs for two archived equality hazards:

- each operand's head-promotion dereference is guarded by that operand actually being a PTR;
- UBV equality compares the stored absolute indices directly.

A third adapter repair turns an unsupported `nodes_equal` tag fallthrough into an explicit failure rather than fabricating equality. Tests require repair provenance and also demonstrate that the original hazards fail under sanitizers. These repairs are evidence boundaries, not silent edits to `archives/`.

## 5. IO-BIND and host effects

The Python RED2 scheduler runs effectful programs on one persistent `MuredMachine`. `CLOCK`, `UART-RX`, `UART-TX`, and `UART-TX-BYTES` suspend the machine with a `MuredHostCall`; the scheduler performs the host operation and resumes that same machine.

`IO-BIND` currently accepts only atomic machine values: `INT`, `FLOAT`, `CHAR`, plain `SYM`/`NIL`, or a supported direct `EP` descriptor. The bound value is published through ordinary graph/environment ownership. No persistent executable problem graph is reserved in the upper environment arena.

Structured/application-valued `IO-BIND` results remain intentionally unsupported. They fail explicitly, and the rejection path does not consume upper-arena `free_space`. Supporting structured host return values would require a separate graph-owned publication design.

Exactly-once host behavior is tested independently of memory compaction. Scheduler statistics distinguish:

- `host_dispatches`;
- cheap host-boundary `host_refreshes`;
- coarse `host_checkpoints`;
- quantum-exhaustion `quantum_recharges`.

Forced low-headroom checkpoints and forced quantum-exhaustion recharges preserve one machine identity and the exact ordered host-effect sequence. No host effect is replayed by q=0 reconstruction.

## 6. Coarse residual reconstruction is a different mechanism

`checkpoint_quantum()` and `recharge_quantum()` are not local reclamation primitives.

A host checkpoint first drives the committed graph through ordinary q=0 reconstruction, then relinearizes the halted residual and restarts the **same** machine from a compact problem graph. `recharge_quantum()` also restarts a halted residual when explicit quantum reconstruction is requested.

Residual relinearization:

- copies only graph-owned reachable data;
- preserves repeated APP/STRUCT graph aliases with a local forwarding map;
- validates graph addresses against the working arena;
- rejects malformed RBLOCK bindings and raw environment-owned residual EP escapes;
- resets graph/environment/control boundaries for the restarted residual.

This is analogous in purpose to the archived interactive `copy_graph()` / `shift_memory()` lifecycle boundary, but Asgard does **not** claim numeric C address identity, identical quantum scheduling, or instruction-for-instruction identity with that interactive host loop.

## 7. What the bounded-memory result does and does not claim

The integrated lifetime test forbids all coarse reclamation entry points—`checkpoint_quantum()`, `recharge_quantum()`, `_relinearize_graph()`, and `_relinearize_result_graph()`—while exercising repeated fixed-live-state operations.

It demonstrates stable post-warmup graph/environment/control envelopes for:

- strict APP/JOIN contraction;
- Y scratch plus lazy IF selection;
- repeated recursive structural equality scratch;
- atomic IO-BIND local rewriting;
- one finite source program combining nested strict arguments, closure capture, lazy selection, and atomic IO-BIND.

That is evidence for incremental reuse at known lifetime boundaries. It is **not** a claim that every recursive source program runs in constant space.

A separate growing-retained-output control intentionally grows the live result graph. Explicit reclaim/restart preserves the full result before and after compaction. Growing live data is allowed to require growing memory.

The known named-definition recursive IO loop can still retain lexical frames across source-level generations until a coarse reconstruction boundary. That observation is not papered over as a Python allocator bug: archived `inst_symbol()` enters named definitions with the current environment, so Task 9 did not invent tail-call/environment rebasing outside its authorized semantics.

## 8. Diagnostics

Memory diagnostics are opt-in. When disabled (the default), `MuredMachine` does not allocate an event-list buffer; `memory_events()` simply reports an empty tuple. Normal CLI execution remains quiet on stderr.

When enabled, `MuredMemoryEvent` records lifetime events such as `SUBGRAPH_ENTER`, `JOIN_RETURN`, `GRAPH_REWIND`, `ENV_ALLOC`, `ENV_RECLAIM`, `IO_BIND`, and `CHECKPOINT`. `MuredMemorySnapshot` reports graph and environment occupancy/peaks, minimum arena gap, region restores, graph rewinds, and host checkpoints.

The IO scheduler can optionally copy enabled events to a caller-provided sink at completion. Supplying a sink while diagnostics are omitted or explicitly false does not invoke it.

Diagnostic buffers are test/inspection state, not μRED arena usage, and the default execution path does not accumulate them.

## 9. Executable C authority and inventory

`tools/hilton_reference/runner.py` builds an isolated GNU89-compatible reference executable from the archived functional THOR bodies in:

- `archives/THOR/RED.C`;
- `archives/THOR/PRIMS.C`;
- `archives/THOR/ARITH.C`;
- selected `MAIN.C` `copy_graph()` / `shift_memory()` bodies.

The adapter instruments function entry but preserves archived bodies except for the explicitly logged equality compatibility repairs described above. Every case records archived source hashes and the functions actually entered.

The inventory in `tools/hilton_reference/reclamation-sites.json` is stricter than a hand-picked rewind list: `validate_inventory()` scans every executable `ws`/`fs` mutation in THOR, STRICT, DEC6, WORK, and SNARL variants and requires every source location to appear exactly once in the inventory.

At the current Task 10 review the inventory contains 269 classified records:

- 165 `parity`;
- 16 `representation-equivalent`;
- 88 `variant-out-of-scope`.

The functional `archives/THOR/` bodies are the execution authority for this integration. Historical variants are catalogued so their memory mutations cannot disappear from the audit, but variant-only machinery is not imported merely because it also manipulates `ws` or `fs`.

Notable excluded machinery includes:

- STRICT's earlier `SUSPEND`/`CL_*` representation, whose child frames do not have the same `fs`-return semantics;
- DEC6/WORK logic branches with `EX_VAR`, `RESET`, trail, and heap state;
- experimental SNARL `RPTR` behavior;
- optimized SNARL equality scratch shapes that differ from the functional THOR implementation.

Those entries remain `variant-out-of-scope`, not undocumented omissions.

## 10. Proof commands and current outcome

The Task 10 documentation claims are grounded by these executable checks:

```sh
uv run pytest -q tests/test_hilton_reference.py \
  tests/test_mured_memory_lifetimes.py \
  tests/test_red2_io_runtime.py

git diff --check
```

Task 9 immediately preceding this publication also established:

- 132/132 tests passing across `test_mured_memory_lifetimes.py`, `test_red2_io_runtime.py`, and `test_mured_cli.py`;
- 845/845 tests passing in the full repository suite;
- 68/68 Hilton reference tests passing;
- Ruff clean on the modified runtime/test files;
- mypy clean for `mured.py` and `io_runtime.py`.

The Task 10 required reference/integration command above passed 180/180 tests after this documentation consolidation, and `git diff --check` was clean.

## 11. Scope of the completion claim

Within the functional THOR memory-lifetime surface audited by the reference corpus, the Python implementation now has a coherent source-to-runtime account for:

- graph suffix contraction and forwarding;
- environment allocation and proven-safe region return;
- logical path splicing through PNP/MARKER equivalents;
- closure/EP publication before reclaim;
- recursive and q=0 residual publication;
- structural equality scratch lifetime;
- control-frame reuse;
- coarse residual relinearization;
- single-machine exactly-once host scheduling;
- opt-in diagnostics that do not change default arena behavior.

This does not claim exhaustive semantics for every historical RED/STRICT/DEC6/WORK/SNARL variant, numeric C address identity, identical quantum scheduling, a tracing collector, or constant memory for programs whose live result/environment state itself grows.

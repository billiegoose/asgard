# RED2 incremental graph and environment reclamation

## Purpose

This note documents how the archived THOR/RED2 C implementation reclaims graph and environment storage incrementally during reduction, how that differs from the current faithful Python `MuredMachine`, and what constraints a faithful repair must preserve.

The central point is that the archived reducer does **not** treat the environment as a monotonic heap. Its two shared-memory arenas behave much more like nested regions/stacks:

- result/working graph storage grows upward through `ws`;
- environment/free storage grows downward through `fs`;
- `env` is the logical environment-path tip, not the allocator itself;
- entering a subgraph saves the current `fs` on the control stack;
- returning through `JOIN` restores that saved `fs`, reclaiming all temporary environment storage allocated while reducing the subgraph;
- graph storage is reclaimed separately by overwriting parent graph nodes and rewinding `ws` when temporary result tails become dead.

This is materially different from the current Python implementation, where `env_frontier` normally moves only downward inside a live reduction segment and therefore retains environment cells whose historical RED2 lifetime would have ended when their subgraph returned.

## 1. The archived machine has three distinct environment notions

The C implementation uses `fs` and `env` for different purposes.

`fs` is the physical free-space pointer. Environment objects are allocated by decrementing it. For example, `make_closure(code, context)` writes two words at `--fs`: a closure environment pointer and a closure code pointer.

`env` is the logical environment context used by variable lookup. Lookup follows ordinary contiguous entries and jumps through `MARKER` nodes. Restoring a captured context can therefore assign `env` to an older address without changing which physical cells are free.

This distinction is why `push_marker()` exists. If `env != fs`, RED2 first allocates a `MARKER` at `--fs` pointing back to the logical parent context, then decrements `fs` again for the new environment entry. The marker lets a newly allocated physical segment extend an older logical environment path without requiring the new cells to be adjacent to the parent path.

The important difference from the current Python bookkeeping is that historical `fs` is **not monotonic for the whole run**. It is saved and restored according to reduction nesting.

## 2. Subgraph entry establishes an environment allocation region

The clearest lifetime boundary is `jump_subgraph()` in archived `RED.C`.

Before reducing an argument subgraph, RED2 pushes three pieces of dynamic state onto the control stack:

1. `prim_args`;
2. `primitive`;
3. the current physical free-space pointer `fs`.

It then clears the argument/primitive state and enters the child problem graph.

Conceptually:

```text
parent reduction
    fs = F_parent
    env = E_parent

enter child subgraph
    save F_parent
    child may allocate MARKERs, UBVs, closures, RECs, ... below F_parent
    fs descends to F_child

return through JOIN
    fs = saved F_parent
    env = fs
```

Everything allocated below `F_parent` solely for reducing that child becomes reclaimable in one pointer assignment when the child rejoins its parent.

This is region/stack reclamation rather than tracing garbage collection. RED2 does not inspect those cells to decide whether they are dead. Their lifetime is implied by the machine's control structure.

## 3. `JOIN` is the inverse lifetime boundary

Archived `inst_join()` performs both graph update/sharing and environment-region reclamation.

After incorporating the child result into its parent, it executes:

```c
pc = destination;
fs = (stack--)->ptr;
env = fs;
primitive = (stack--)->ptr;
prim_args = (stack--)->intval;
move_backward();
```

The `fs` restore is not incidental bookkeeping. It is the operation that discards environment allocations made while reducing the child subgraph.

Setting `env = fs` then makes the parent reduction continue from the parent region's current environment tip. The old source even contains the comment `/* possible problems? */`, which is a useful warning: correctness depends on the machine ensuring that values which must survive the child have been represented elsewhere before this reclaim occurs.

## 4. How values survive a child-region reclaim

The archived machine has specific sharing/update rules so useful results do not remain dependent on temporary child storage.

### 4.1 Atomic closure results are shared into the parent environment

When a closure is forced and produces an atomic headed result, `JOIN` may overwrite the closure's environment slot with that atomic value:

```c
if ((destination->type == CLOSURE) && (result->type != PTR))
    *(destination->op.addr) = *result;
```

That is the historical call-by-need sharing path. The reduced value is copied into an environment cell whose lifetime belongs to the parent/captured context, so the temporary child region can be dropped.

The Python implementation already mirrors a narrow form of this with EP/closure-slot sharing for atomic values.

### 4.2 Non-atomic graph results survive by graph pointer

For non-head/non-atomic results, `JOIN` points the parent destination at the result graph:

```c
destination->op.addr = result;
destination->type = PTR;
```

This retains graph data, not child environment allocation. Consequently graph lifetime and environment lifetime are separate problems: restoring `fs` can be correct even while some result graph remains live.

### 4.3 Atomic graph tails are reclaimed immediately

For an atomic result, `JOIN` writes the result directly into the parent spine. It then rewinds `ws` when the temporary result words are no longer needed:

```c
if (result->type != PTR) {
    if (destination->class == HEAD) ws = destination;
    else ws -= 2;
}
```

Thus a strict argument such as an integer does not leave an ever-growing `JOIN; result` trail. The parent node becomes the result and the temporary graph tail is reclaimed immediately.

The Python machine already implements several instances of this graph compaction: `APP_VAR` conversion, atomic strict-primitive JOIN compaction, primitive-result overwrite/reclaim, and IF spine discard.

## 5. Lambda binding allocates into the current region

The archived lambda transition allocates argument bindings, UBVs, and closures using `push_marker()` / `make_closure()` beneath the current `fs`.

Those allocations are therefore scoped by whichever subgraph-entry frame most recently saved `fs`.

This is the key reason historical RED2 can perform large amounts of recursive computation without monotonically consuming the environment arena: bindings created while evaluating an argument or other nested subgraph disappear when that nested reduction returns, unless the value has been deliberately shared into a longer-lived parent location.

The current Python machine instead uses `env_frontier` as a conservative physical high-water mark. Restoring `state.env` does not make cells below it reusable; later allocation inserts a PNP bridge and continues below the lowest ever frontier. That protects captured closures, but also turns temporary subgraph bindings into run-long allocations.

## 6. MARKER is path splicing, not garbage collection

Historical `push_marker()` is easy to misread as a mechanism for preserving every old environment allocation. It is not.

Its purpose is local: if the logical context `env` is not at the physical free-space edge `fs`, create a jump from the newly allocated physical segment back to that logical context.

The marker only needs to live for the lifetime of the region in which it was allocated. When the enclosing saved `fs` is restored, the marker and the local segment below it are reclaimed together.

This suggests that Python's `PNP` representation is conceptually compatible with historical RED2, but the Python allocator currently gives PNP-linked segments a much longer physical lifetime than the C reducer did.

## 7. IF performs explicit graph and control-context discard

The archived `IF` primitive demonstrates another kind of incremental lifetime management.

Only the condition is strict. The true and false branches are retained lazily with saved environment paths. Once the condition reduces to TRUE/FALSE, `prim_if()`:

1. rewinds `ws` back into the IF spine (`ws = primitive - 2`);
2. inspects the branch descriptors;
3. restores only the selected branch's saved environment context;
4. pops and discards the unselected branch context;
5. rewinds `ws` past both branch slots;
6. directly enters the selected branch in `PROBLEM` mode.

The discarded branch is never traversed and its result-spine storage disappears immediately. This is not GC: the primitive knows structurally which branch is dead.

Python's IF implementation already performs analogous graph-spine reclamation and saved-path selection. The remaining fidelity question is whether environment physical storage associated with discarded/rejoined subgraphs is reclaimed with historical `fs` semantics rather than retained by `env_frontier`.

## 8. Y does not introduce a persistent recursive heap object

Historical `Y` is explicitly acyclic. `(Y f)` rewrites to `(f (Y f))` by pointing the copied argument back at existing problem graph code. When `f` is not already represented by a pointer, RED2 temporarily pushes the current `env`, creates a headed scratch copy, and executes it.

There is no knot-tying heap allocation and no special recursion GC. Space behavior therefore depends on the ordinary APP/JOIN, graph overwrite, and environment-region lifetime rules working correctly.

This is important diagnostically: persistent growth in a long-running Y program is not evidence that Y itself needs special reclamation.

## 9. Primitive contraction also reclaims graph regions eagerly

Strict primitive firing overwrites the primitive redex with its result and moves `ws`/`fsp` back to that result location. The current Python implementation already follows this pattern for strict arithmetic/comparison primitives.

The broader historical pattern is consistent:

- temporary graph data is appended at the working-space edge;
- when a contraction establishes that a suffix is dead, the machine moves `ws` backward immediately;
- temporary environment data is appended at the free-space edge;
- when a nested reduction scope ends, the machine restores a previously saved `fs` immediately.

Both arenas therefore have stack/region-like reclamation, but their lifetime boundaries are not identical.

## 10. Why the current Python `env_frontier` diverges

Current Python state has:

- `state.env`: logical environment path tip;
- `state.env_frontier`: lowest physical environment allocation address seen in the current live segment.

`_allocate_environment()` deliberately refuses to move the physical frontier upward after `env` restoration. If `env != env_frontier`, it creates a `PNP` below the frontier and keeps descending.

That design fixed a real corruption bug: simply allocating at `env - 1` after restoring an older path can overwrite cells still referenced by captured closures.

But the conservative fix discarded an important historical invariant: **the machine knows when a whole nested environment region ceases to be live, because `jump_subgraph()` saved its allocation frontier.**

The correct goal is therefore not to remove `env_frontier` and blindly allocate from `env`. It is to recover explicit physical-frontier lifetimes.

## 11. Current IO-BIND scope: atomic bound values only

Current host-dispatched IO actions produce atomic values:

- `CLOCK` returns an `INT`;
- `UART-RX` returns an `INT` byte or `NIL`;
- `UART-TX` returns `NIL`;
- `UART-TX-BYTES` accepts a list argument but returns `NIL`.

The Python RED2 machine therefore supports `IO-BIND` only when the bound value is
an atomic machine value (`INT`, `FLOAT`, `CHAR`, plain `SYM`/`NIL`, or a direct
`EP` descriptor). Those values are passed to the continuation through ordinary
lambda binding and no upper-arena problem reservation is made.

Structured/application-valued `IO-BIND` results such as lists, STRUCT values, and
lambda-valued results are intentionally out of scope for the current host IO
contract. If future IO APIs need to return structured graph values, they need a
separate graph-owned publication design. The old `_reserve_problem()` fallback
was removed because it stored persistent executable problem graphs in the upper
environment arena and blocked faithful historical `fs` restoration.

## 12. Graph lifetime needs a separate audit

Fixing environment `fs` restoration is necessary but not sufficient for full memory fidelity.

The archived machine also rewinds `ws` in instruction-specific places. Python already implements many of these, but previous experiments showed recursive pure programs and dynamic STRUCT workloads can exhibit large graph growth too.

Therefore the fidelity effort must audit every historical `ws` rewind/update against Python `fsp` behavior, especially:

- JOIN atomic vs pointer results;
- closure/EP sharing;
- LAMBDA contraction;
- strict primitive firing;
- IF branch selection;
- STRUCT selector/application paths;
- RBLOCK/RUP/RECP reconstruction;
- definition/SYM reversal;
- any Python-only internal continuation representation.

A correct final implementation should not rely on host checkpoints to make terminating pure programs fit in reasonable memory.

## 13. Target invariant

The target Python memory model should be:

```text
shared working memory

low addresses                                  high addresses
+-----------------------------------------------------------+
| problem/result graph ->      free      <- environment     |
+-----------------------------------------------------------+
             ^ fsp                         ^ fs/frontier

logical env may jump through PNP markers independently.

On child entry:
    save physical environment frontier

During child:
    allocate environment below frontier
    append temporary result graph above fsp

On child JOIN:
    publish/share child result into parent graph/environment
    rewind temporary graph suffix when structurally dead
    restore saved physical environment frontier
    resume parent
```

The physical environment frontier may move both downward (allocation) and upward (region reclamation), while logical `env` follows environment paths.

## 14. Relationship to host-dispatch checkpoints

Commit `d791224` added adaptive q=0 reconstruction/relinearization when host-dispatch execution is close to graph/environment collision. That is a valid coarse reclamation/scheduling mechanism and should remain as a safety net while incremental fidelity work proceeds.

It should **not** be treated as proof that ordinary RED2 lifetime management is correct. The intended endpoint is that normal APP/JOIN/primitive/branch lifetimes reclaim most temporary storage incrementally, making whole-result checkpointing rare rather than fundamental to ordinary long-running IO.

## 15. Python implementation status after incremental reclamation

The Python `MuredMachine` now exposes opt-in memory diagnostics for tests and
manual probes. `MuredMemoryEvent` records ordered events named
`SUBGRAPH_ENTER`, `JOIN_RETURN`, `GRAPH_REWIND`, `ENV_ALLOC`, `ENV_RECLAIM`,
`IO_BIND`, and `CHECKPOINT`; `MuredMemorySnapshot` reports current and peak graph
words, current and peak environment words, minimum graph/environment gap,
frontier restores, graph rewinds, and host checkpoints. Diagnostics are disabled
by default and normal/benchmark runs do not print them.

The current terminology is:

- `env`: logical environment path used by lookup;
- `env_frontier` / archived `fs`: physical environment/free-space boundary;
- `fsp` / archived `ws`: graph/result working-space boundary;
- `PNP` / archived `MARKER`: logical path splice, not a garbage collector;
- `JOIN`: child-result publication, parent-continuation restoration, and the
  lifetime boundary where proven-safe child environment regions can be reclaimed;
- `checkpoint_quantum`: coarse residual-world reconstruction for low-headroom
  host-dispatch situations, not the ordinary allocator for bounded loops.

Typed child-subgraph frames carry the parent logical path, saved physical
frontier, and primitive countdown context. Reverse APP, EP/closure forcing,
RBLOCK binding reduction, and native structure-selector child reductions enter
through this representation. On JOIN, the child result is published first; then
safe frontiers are restored and optionally poisoned in diagnostic tests. If a
surviving graph or environment pointer would still name the candidate reclaimed
interval, the restore is skipped instead of silently corrupting a captured value.

Lambda binding cases map to the archived `inst_lambda()` cases as follows:

| Python case | Archived case | Surviving owner |
| --- | --- | --- |
| `APP` argument descriptor | PTR/closure argument | closure cell in current environment region points at graph code plus saved context |
| `APP_VAR` argument descriptor | VAR argument | UBV cell in current environment region |
| `INT`/`FLOAT`/`CHAR`/plain `SYM` | direct atomic value | one-word binding in current environment region |
| q-exhausted/no argument | no-argument UBV reconstruction | UBV/result graph until quantum is restored |
| `EP` descriptor | shared closure/environment value | EP cell in current region points at the published longer-lived cell |

Graph-side parity is handled separately from environment-frontier reclamation:

| archived site | archived `ws` action | Python site | current `fsp` action | parity / test |
| --- | --- | --- | --- | --- |
| atomic `JOIN` | rewind temporary `JOIN; result` tail | `_join()` | decrements `fsp` for atomic/APP_VAR/primitive results | `test_mured_transitions.py`, memory diagnostics `GRAPH_REWIND` |
| strict primitive contraction | overwrite redex with result | `_fire_primitive()` | sets `fsp` to result location | arithmetic/countdown diagnostics |
| IF selection | discard IF spine and unselected branch | `_select_if_branch()` / `_skip_if_branches()` | rewinds to selected result/branch entry | lazy IF lifetime tests |
| structure selector result | project field through APP/JOIN if needed | `_fire_primitive()` selector path | compacts selector result and preserves live field graphs | recursive struct tests |
| q=0 reconstruction | bounded result relinearization | `checkpoint_quantum()` / `recharge_quantum()` | rebuilds compact graph in the same machine | IO runtime tests |

IO-BIND now consumes atomic host values through ordinary graph/environment
sharing and records `reserved_upper_arena = False` for that path. Structured
application-valued bind results are rejected explicitly: current host IO does not
return structured values, and future structured IO results require a graph-owned
publication design rather than an upper-arena reservation fallback.

The 2026-09-08 measurement smoke completed `mise run benchmark-breakout
--iterations 1` with RED2 at 1.198 seconds for one iteration versus THOR at 2.421
seconds in the same run. The measured result supports keeping automatic
host-dispatch checkpointing as an emergency headroom compactor while preserving
roomy-machine refresh as the default cheap path.

Direct archived C runtime differential measurement was not completed in this
worktree; the implementation relies on the archived transition code and thesis
notes cited above for `ws`, `fs`, `env`, MARKER/PNP, and JOIN lifetime authority.

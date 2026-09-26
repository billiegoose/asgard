# A3 slice 1 — generic APP publisher mapped onto SynthesizableRED2Machine

This document refines `a3-slice1-generic-app-pseudocode.md` into an implementation-ready machine mapping. It keeps the A2 reviewer decision intact: preserve all existing bounded JOIN APP machinery and enter the generic walker only at the three allocation-free APP gaps.

## 1. Important implementation correction: latch the active task

The architectural graph request mux is built before scratch-RAM outputs are available in the current source ordering. Therefore `MICRO_PUB_EXEC` must **not** assume it can read `pub_task_ram[top]` and use that freshly read task to choose the graph RAM address in the same combinational pass.

Use a persistent current-task register:

```text
pub_current_task : red2_pub_task_t
pub_current_valid: uint1
```

`MICRO_PUB_STACK` owns loading/replacing/pushing task RAM and, when stack mutation is complete, loads the new top task into `pub_current_task`. `MICRO_PUB_EXEC` then has a registered task available early enough for the existing graph request mux to select `task.a` / `task.b` directly.

This avoids reordering the existing RAM-call graph and avoids creating a long scratch-RAM -> graph-RAM combinational dependency.

The two microstates therefore have crisp roles:

- `MICRO_PUB_EXEC` (126): semantic validation using the already-latched current task; stage the complete next stack image and any memo operation.
- `MICRO_PUB_STACK` (127): serialize scratch task writes/reads and install the next `pub_current_task`; no RED2 semantic fault discovery.

## 2. Constants and structs

Add after microstate 125:

```text
MICRO_PUB_EXEC  = 126
MICRO_PUB_STACK = 127

PUB_TASK_NONE              = 0
PUB_TASK_GRAPH             = 1
PUB_TASK_ROOT_DONE         = 2
PUB_TASK_APP_SCAN          = 3
PUB_TASK_APP_REWRITE       = 4
PUB_TASK_APP_OPERATOR_DONE = 5

PUB_ROOT_EMPTY    = 0
PUB_ROOT_VISITING = 1
PUB_ROOT_DONE     = 2
PUB_ROOT_RESERVED = 3

PUB_RESUME_NONE = 0
PUB_RESUME_JOIN = 1

PUB_STACK_IDLE          = 0
PUB_STACK_WRITE_PENDING = 1
PUB_STACK_LOAD_TOP      = 2
```

Keep the future-compatible task and root rows from the A2 review:

```python
@struct
class red2_pub_root_t(NamedTuple):
    generation: uint32_t
    state: uint2_t
    result: uint17_t
    aux: uint17_t

@struct
class red2_pub_task_t(NamedTuple):
    kind: uint6_t
    a: uint17_t
    b: uint17_t
    c: uint17_t
    d: uint17_t
    e: uint17_t
    f: uint17_t
    flags: uint8_t
```

## 3. Scratch RAM and registers

```text
PUB_TASK_WORDS = GRAPH_WORDS * 4
PUB_TASK_ADDR_BITS = 10

pub_task_ram = make_ram(red2_pub_task_t, PUB_TASK_WORDS, ports=("rw",), read_latency=0)
pub_root_ram = make_ram(red2_pub_root_t, GRAPH_WORDS, ports=("rw",), read_latency=0)
```

Persistent registers:

```text
pub_generation   : uint32
pub_sp           : uint16       # stack count
pub_value        : uint17
pub_launch_root  : uint17
pub_resume_kind  : uint2

pub_current_task : red2_pub_task_t
pub_current_valid: uint1

pub_pending_count: uint2        # replacement image size 0..3
pub_pending0     : red2_pub_task_t
pub_pending1     : red2_pub_task_t
pub_pending2     : red2_pub_task_t

pub_stack_phase  : uint2
pub_stack_index  : uint2        # next pending task to write
pub_stack_base   : uint16       # old top index (pub_sp-1)
pub_stack_new_sp : uint16       # validated resulting count
```

`pub_generation` survives RESET/LOAD_STATE/START exactly like `promote_generation`; active publisher registers reset to idle.

Generation zero is reserved. On launch:

```text
if pub_generation == 0xffffffff:
    HW_FAULT_EXECUTION_NOT_IMPLEMENTED   # temporary slice-1 wrap boundary
else:
    pub_generation += 1
```

No stale row is ever accepted across wrap.

## 4. Request-mux mapping

Add predecoded wires:

```text
micro_is_pub_exec
micro_is_pub_stack

pub_current_is_graph
pub_current_is_root_done
pub_current_is_app_scan
pub_current_is_app_rewrite
pub_current_is_app_operator_done
```

### Architectural graph RAM

Only `MICRO_PUB_EXEC` reads graph RAM. Because `pub_current_task` is registered, request selection is direct:

```text
if micro_is_pub_exec:
    if pub_current_is_graph:
        memory_req.addr = pub_current_task.a[GRAPH_ADDR_BITS-1:0]
    elif pub_current_is_app_scan:
        memory_req.addr = pub_current_task.b[GRAPH_ADDR_BITS-1:0]
```

Do not enable architectural graph writes from either publisher microstate.

### Root memo RAM

`MICRO_PUB_EXEC` indexes memo only for `PUB_GRAPH` and `PUB_ROOT_DONE`:

```text
GRAPH     -> pub_root_req.addr = task.a
ROOT_DONE -> pub_root_req.addr = task.a
```

Memo writes are scratch-only and may occur in EXEC after all validation for that step succeeds.

### Task RAM

`MICRO_PUB_STACK` is the only task-RAM mutation state. It either:

1. writes one staged pending task at `pub_stack_base + pub_stack_index`, or
2. reads `pub_stack_new_sp - 1` and latches it into `pub_current_task`, then returns to EXEC.

This guarantees one task-RAM port is sufficient.

## 5. Stack replacement convention

Every EXEC step describes the **entire replacement for the old top task**, bottom-to-top, in `pub_pending0..2`.

Given old count `pub_sp`:

```text
base = pub_sp - 1
new_sp = base + pub_pending_count
```

EXEC validates before entering STACK:

```text
pub_sp != 0
new_sp <= PUB_TASK_WORDS
```

If `new_sp > PUB_TASK_WORDS`, fault `FAULT_CONTROL_OVERFLOW` before any scratch write.

Then STACK serializes:

```text
for i in [0, pending_count):
    task_ram[base+i] = pending[i]

pub_sp = new_sp

if new_sp == 0:
    finish publisher
else:
    pub_current_task = task_ram[new_sp-1]
    pub_current_valid = 1
    goto PUB_EXEC
```

A zero-entry replacement is a pop. One entry replaces top. Two/three entries replace top and push one/two children.

Because task RAM is private scratch, partially completed STACK writes do not violate architectural failure atomicity. Semantic faults are forbidden in STACK.

## 6. Launch mapping onto the existing JOIN machine

Create one repeated launch sequence (inlined at the three sites; do not introduce a Python helper unless PipelineC accepts it cleanly):

```text
next_generation = pub_generation + 1
if next_generation == 0:
    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
    microstate = MICRO_FAULT
else:
    pub_generation = next_generation
    pub_launch_root = join_result_address
    pub_resume_kind = PUB_RESUME_JOIN
    pub_value = 0

    # Initial stack already exists conceptually as one GRAPH task. Stage it
    # through the same STACK machinery so task-RAM initialization has one owner.
    pub_sp = 1
    pub_current_task = GRAPH(join_result_address)
    pub_current_valid = 1
    pub_pending_count = 0
    pub_stack_phase = PUB_STACK_IDLE

    join_preserve_fsp = 1
    join_published_root = join_result_address
    microstate = MICRO_PUB_EXEC
```

For the initial root there is no need to write task RAM slot 0 before the first EXEC, because `pub_current_task` is authoritative while executing. The first replacement writes the live continuation image into task RAM. If simpler for invariants, launch may instead stage GRAPH through STACK; either shape is acceptable, but choose exactly one and test it.

### Launch site A: third distinct target

In `MICRO_JOIN_APP_SCAN`, replace only the existing third-target unsupported branch. Restart from `join_result_address`; ignore the bounded first/second-target scratch registers.

### Launch site B: one-target nested APP

In `MICRO_JOIN_APP_TARGET_READ`:

```text
elif join_app_target_opcode == MOP_APP:
    launch generic whole-root walk
elif not join_app_target_is_ep:
    preserve existing HW_NOT_IMPLEMENTED
```

EP stays on the specialized path.

### Launch site C: two-target nested APP

In `MICRO_JOIN_MULTI_TARGET_READ`:

```text
elif join_multi_root_opcode == MOP_APP:
    launch generic whole-root walk
elif join_multi_root_is_ep:
    existing EP preflight
else:
    preserve existing unsupported behavior
```

CLOSURE/REC stay unsupported here for slice 1.

## 7. State-transition table

The table uses `T` for `pub_current_task`, `W` for `memory_out.p0.rd_data`, and `M` for the root-memo row selected by `T.a`.

| State | Current task / condition | Validation and effects | Replacement staged | Next |
|---|---|---|---|---|
| PUB_EXEC | `!pub_current_valid` or `pub_sp==0` unexpectedly | `FAULT_ILLEGAL_TRANSITION` | — | FAULT |
| PUB_EXEC | GRAPH, root address out of range | `FAULT_INVALID_ADDRESS` | — | FAULT |
| PUB_EXEC | GRAPH, source word invalid | `FAULT_INVALID_ADDRESS` | — | FAULT |
| PUB_EXEC | GRAPH, memo generation matches + VISITING | recursive root cycle -> `FAULT_ILLEGAL_TRANSITION` | — | FAULT |
| PUB_EXEC | GRAPH, memo generation matches + DONE | `pub_value=M.result` | `[]` | PUB_STACK |
| PUB_EXEC | GRAPH, unseen, opcode APP | validate APP word itself is signed/nonnegative/in-range payload; write memo VISITING for root | `[ROOT_DONE(root), APP_SCAN(root,root)]` | PUB_STACK |
| PUB_EXEC | GRAPH, unseen, stable terminal | write memo VISITING; `pub_value=root` | `[ROOT_DONE(root)]` | PUB_STACK |
| PUB_EXEC | GRAPH, unseen, EP/CLOSURE/REC/LAMBDA/RBLOCK/STRUCT/etc | slice-1 semantic boundary -> HW_NOT_IMPLEMENTED | — | FAULT |
| PUB_EXEC | ROOT_DONE | memo row must belong to current generation and be VISITING; write DONE(result=`pub_value`) | `[]` | PUB_STACK |
| PUB_EXEC | APP_SCAN, cursor address out of range | `FAULT_INVALID_ADDRESS` | — | FAULT |
| PUB_EXEC | APP_SCAN, source word invalid | `FAULT_INVALID_ADDRESS` | — | FAULT |
| PUB_EXEC | APP_SCAN, APP descriptor, bad kind/negative/out-of-range target | preserve current APP typed fault ordering (`FAULT_INVALID_ADDRESS`) | — | FAULT |
| PUB_EXEC | APP_SCAN, APP descriptor at live `fsp` boundary | `FAULT_INVALID_ADDRESS` | — | FAULT |
| PUB_EXEC | APP_SCAN, valid APP descriptor -> target | no architecture writes | `[APP_SCAN(root,cursor+1), APP_REWRITE(cursor,target), GRAPH(target)]` | PUB_STACK |
| PUB_EXEC | APP_SCAN, APP_VAR before terminator | if cursor==fsp -> INVALID_ADDRESS; else transparent | `[APP_SCAN(root,cursor+1)]` | PUB_STACK |
| PUB_EXEC | APP_SCAN, non-head inline before terminator | if cursor==fsp -> INVALID_ADDRESS; else transparent | `[APP_SCAN(root,cursor+1)]` | PUB_STACK |
| PUB_EXEC | APP_SCAN, accepted head terminal operator | stable family only for slice 1 | `[APP_OPERATOR_DONE(root,cursor), GRAPH(cursor)]` | PUB_STACK |
| PUB_EXEC | APP_SCAN, other opcode/shape | preserve explicit unsupported boundary | — | FAULT |
| PUB_EXEC | APP_REWRITE, `pub_value == original_target` | no write needed | `[]` | PUB_STACK |
| PUB_EXEC | APP_REWRITE, value changed | relocation requires later patch journal -> HW_NOT_IMPLEMENTED | — | FAULT |
| PUB_EXEC | APP_OPERATOR_DONE, `pub_value == operator` | `pub_value=root` | `[]` | PUB_STACK |
| PUB_EXEC | APP_OPERATOR_DONE, value changed | later relocation semantics -> HW_NOT_IMPLEMENTED | — | FAULT |
| PUB_STACK | pending write phase | write exactly one `pending[i]` task row; increment index | — | PUB_STACK |
| PUB_STACK | writes complete, `new_sp>0` | set `pub_sp=new_sp`; read/latch new top into `pub_current_task`; clear staging | — | PUB_EXEC |
| PUB_STACK | writes complete, `new_sp==0`, resume JOIN, `pub_value!=pub_launch_root` | relocation escaped allocation-free contract -> HW_NOT_IMPLEMENTED | — | FAULT |
| PUB_STACK | writes complete, `new_sp==0`, resume JOIN, value matches | set JOIN success fields below | — | JOIN_PUBLISH |

JOIN success fields:

```text
join_publish_word   = APP(join_result_address)   # same encoded constant currently used
join_needs_ep_cache = 0
join_preserve_fsp   = 1
join_published_root = join_result_address
pub_resume_kind     = PUB_RESUME_NONE
pub_current_valid   = 0
microstate          = MICRO_JOIN_PUBLISH
```

No `pc/fsp/env/control_top/q/phi/free_space/argcnt/prim_id/fire/s_a/s_d` change occurs until the existing JOIN tail takes over.

## 8. Stable-terminal definition for slice 1

Do not inherit the current bounded path's overly broad `head inline` predicate blindly. The generic walker should use exactly the Concrete non-allocating roots that are safe in place for this slice:

```text
head INT
head FLOAT
head CHAR
head SYM with definition_valid == 0
VAR
UBV
```

`PRIM_0/1/2` should remain outside the generic slice unless Concrete `PUB_GRAPH` inspection proves they are returned unchanged in this context. The frozen witnesses do not require them, and expanding the stable set without oracle confirmation creates unnecessary semantic surface.

Likewise, validate data kinds exactly as Concrete does rather than assuming opcode alone implies a valid terminal.

## 9. Memo invariants

For every root in current generation:

```text
EMPTY/unseen -> may transition only to VISITING
VISITING     -> may transition only to DONE or remain stale after fault
DONE         -> immutable for the remainder of the walk
```

A failed walk may leave private memo/task scratch partially populated. That is safe because the next launch advances generation; no architectural state depends on scratch after fault/reset.

`ROOT_DONE` should defensively require the memo row to still be `(generation=current, state=VISITING)`. Any other state is `FAULT_ILLEGAL_TRANSITION`.

## 10. Cycle and sharing behavior

Example shared DAG:

```text
root APP -> target A
         -> target A again
```

First A:

```text
GRAPH(A): EMPTY -> VISITING -> terminal -> ROOT_DONE -> DONE(A)
```

Second A:

```text
GRAPH(A): DONE -> pub_value=A, no recursive traversal
```

Example recursive APP root:

```text
A: APP(A) ... operator
```

Outer `GRAPH(A)` marks A VISITING. Descending through its descriptor invokes `GRAPH(A)` again, sees VISITING, and faults `FAULT_ILLEGAL_TRANSITION` before architectural mutation.

## 11. Reset/start behavior

On `CMD_RESET`, `CMD_LOAD_STATE`, and `CMD_START`, clear active machine registers:

```text
pub_sp = 0
pub_value = 0
pub_launch_root = 0
pub_resume_kind = PUB_RESUME_NONE
pub_current_task = zero task
pub_current_valid = 0
pub_pending_count = 0
pub_pending0/1/2 = zero task
pub_stack_phase = PUB_STACK_IDLE
pub_stack_index = 0
pub_stack_base = 0
pub_stack_new_sp = 0
```

Do **not** reset `pub_generation` or clear `pub_root_ram`/`pub_task_ram`.

## 12. Dispatch/static-test changes

Add `micro_is_pub_exec` and `micro_is_pub_stack` to the predecode block and exactly two new flat handled arms:

```text
if not clock_dispatch_handled and micro_is_pub_exec: ...
if not clock_dispatch_handled and micro_is_pub_stack: ...
```

The exact source count of `clock_dispatch_handled = 1` therefore becomes 128 if no other dispatch arm is refactored. Update `test_task14_microstate_dispatch_stays_flat_for_pipelinec` from 126 to 128.

Keep `red2_status_t.microstate` as `uint7_t`.

## 13. Required implementation order

1. Add constants/types/RAM/register/reset plumbing with no launch sites; static tests + frontend.
2. Implement stack envelope and a synthetic/internal launch if needed to prove task sequencing.
3. Implement GRAPH stable terminals + memo + ROOT_DONE.
4. Implement APP_SCAN / APP_REWRITE / APP_OPERATOR_DONE.
5. Redirect the three existing APP gaps.
6. Turn the frozen third-target and nested-APP witnesses green while EP->REC remains red.
7. Add sharing, cycle, APP_VAR, inline-prefix, late-fault atomicity regressions.
8. Run native parity, fast pytest, `git diff --check`, then pinned PipelineC frontend.

Do not run full HDL until this semantic slice is green and reviewed.

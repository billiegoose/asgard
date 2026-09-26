# A2/A3 slice 1 — reverse-JOIN integration review

## Decision

The safest minimal landing is **not** to replace the existing bounded JOIN APP publisher yet.

Add a separate, allocation-free generic publication walker with:

- one fixed task-stack RAM;
- one generation-tagged root-memo RAM;
- exactly the A3-slice task semantics needed for `PUB_GRAPH` / `PUB_APP` traversal;
- no patch journal;
- no materialization RAM;
- no architectural graph writes;
- no control-RAM writes;
- no mutation of `pc/fsp/env/control_top/q/phi/free_space/argcnt/prim_id/fire/s_a/s_d` while it runs.

Launch it only from the current reverse-JOIN APP gaps where the bounded implementation has already concluded that the generic walker is required:

1. third unique APP target (`MICRO_JOIN_APP_SCAN`, current lines 9475–9478);
2. a nested APP root in the one-target preflight (`MICRO_JOIN_APP_TARGET_READ`, current lines 9555–9557, specifically when the target opcode is `MOP_APP`);
3. a nested APP root in the two-target preflight (`MICRO_JOIN_MULTI_TARGET_READ`, current lines 9630–9633, specifically when the root opcode is `MOP_APP`).

On generic-walker success, require `pub_value == join_result_address`, then resume through the already-existing no-fail JOIN commit tail:

```text
join_publish_word   = APP(join_result_address)
join_needs_ep_cache = 0
join_preserve_fsp   = 1
join_published_root = join_result_address
microstate          = MICRO_JOIN_PUBLISH
```

This makes the frozen three-target and nested-APP witnesses green while deliberately leaving EP relocation, closure allocation, REC publication, selector promotion, and all other allocating semantics on their current code paths.

The existing selector promoter (`promote_*`, `MICRO_STRUCT_SELECTOR_PROMOTE_GENERIC*`) should remain untouched in this slice.

---

## Why this seam is the minimal safe one

The current reverse JOIN already has the transaction boundary A2 needs:

- frame discovery/validation happens in `MICRO_JOIN_FRAME_READ`;
- the result graph is inspected after that;
- architectural control clearing does not begin until after `MICRO_JOIN_PUBLISH` succeeds;
- `MICRO_JOIN_PUBLISH` then restores `env/free_space`, sets `s_a`, and enters `MICRO_JOIN_CONTROL_CLEAR`.

The frozen A1 witnesses require no relocation or allocation at all:

- three-target witness: result APP prefix targets 20, 21, 22; all three are stable roots;
- nested witness: target 20 is itself `APP(24)` and 24 is a stable head INT; target 21 is stable.

Concrete therefore performs only recursive validation/publication whose returned roots remain equal to their source addresses. There is nothing for Synth to rewrite before the normal parent APP publication.

That means slice 1 can prove the two architectural pieces A2 actually needs — explicit bounded traversal and memoized sharing/cycle detection — without introducing any new graph mutation mechanism.

---

## Exact source insertion map

All line numbers below refer to the reviewed `machine.py` SHA `f0383e9e1c0b6eb0c8a633a467582061e79db05dd51fd42b3197353b94d15b4c`.

### 1. Constants / task ABI

Insert after the existing microstate constants and before `PROMOTE_TASK_*` (currently around lines 162–292).

There are only two unused 7-bit microstate IDs left: **126 and 127**. Do not widen `microstate` in this slice; `red2_status_t.microstate` is also `uint7_t`, so widening would change the observable top-level ABI.

Use:

```text
MICRO_PUB_EXEC  = 126
MICRO_PUB_STACK = 127
```

Task kinds should freeze the A2 namespace now even though this slice executes only the first five:

```text
PUB_TASK_NONE              = 0
PUB_TASK_GRAPH             = 1
PUB_TASK_ROOT_DONE         = 2
PUB_TASK_APP_SCAN          = 3
PUB_TASK_APP_REWRITE       = 4
PUB_TASK_APP_OPERATOR_DONE = 5
```

Do not reuse `PROMOTE_TASK_*`: that machine has different semantics and must remain independent for this slice.

### 2. New structs

Insert near `red2_promote_forward_t` (currently lines 303–314).

Use the A2 root-memo row unchanged:

```python
@struct
class red2_pub_root_t(NamedTuple):
    generation: uint32_t
    state: uint2_t
    result: uint17_t
    aux: uint17_t
```

States:

```text
PUB_ROOT_EMPTY    = 0
PUB_ROOT_VISITING = 1
PUB_ROOT_DONE     = 2
PUB_ROOT_RESERVED = 3
```

For the task stack, freeze the future-compatible A2 entry layout rather than creating a throwaway narrow struct:

```python
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

Only these fields are meaningful in slice 1:

```text
GRAPH:
    a = root

ROOT_DONE:
    a = root

APP_SCAN:
    a = application root
    b = cursor

APP_REWRITE:
    a = descriptor address
    b = original target

APP_OPERATOR_DONE:
    a = application root
    b = operator address
```

`c..f` and `flags` stay zero for this slice.

The reason to retain `APP_REWRITE` even though the slice is allocation-free is important: it asserts the first-slice contract explicitly. When the child returns, `pub_value` must equal `original_target`; otherwise this slice must stop with `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` before architectural mutation. The later patch-journal slice can extend this exact task without changing traversal structure.

### 3. New scratch RAMs

Insert beside the existing RAM declarations (currently lines 449–463):

```text
PUB_TASK_WORDS = GRAPH_WORDS * 4   # 1024 at the current GRAPH_WORDS=256
PUB_TASK_ADDR_BITS = 10
```

Then:

```text
pub_task_ram:  make_ram(red2_pub_task_t, PUB_TASK_WORDS, ports=("rw",), read_latency=0)
pub_root_ram:  make_ram(red2_pub_root_t, GRAPH_WORDS, ports=("rw",), read_latency=0)
```

No additional architectural graph RAM port is required. The publisher shares the existing single `graph_ram.p0` request mux because publication is a serialized micro-machine.

Do **not** add an active-visit RAM in slice 1. `pub_root_ram`'s `VISITING` state is sufficient for root-recursion cycle detection. The separate active-visit RAM described in A2 is for later REC rewrite tuple visitation and should arrive with that semantic family.

### 4. Publisher registers

Insert after the selector-promoter scratch registers (around current lines 533–546).

Minimum persistent state:

```text
pub_generation : uint32_t
pub_sp         : uint16_t   # count, valid range 0..PUB_TASK_WORDS (1024)
pub_value      : uint17_t
pub_launch_root: uint17_t
pub_resume_kind: uint2_t
pub_phase      : uint3_t

pub_pending_count : uint2_t
pub_pending0      : red2_pub_task_t
pub_pending1      : red2_pub_task_t
pub_pending2      : red2_pub_task_t
```

A `uint16_t` stack count is sufficient for the current 1024-entry scratch RAM and avoids introducing an unsupported custom-width type. Only truncate a validated stack address to `PUB_TASK_ADDR_BITS` at the RAM request.

For this slice only one resume kind is required:

```text
PUB_RESUME_JOIN = 1
```

Do not add destination/environment/materialization registers yet; they are unused by an allocation-free walker and increase synthesis/state-reset surface for no semantic gain.

### 5. RAM request blocks

Add `pub_task_req` and `pub_root_req` initialization beside the existing `promote_*_req` initialization (currently around lines 733–751), and invoke both RAMs after request selection alongside the other scratch RAMs.

Add two predecoded microstate wires near the current `micro_is_*` block:

```text
micro_is_pub_exec
micro_is_pub_stack
```

Also decode task-kind equality once per source coordinate:

```text
pub_task_is_graph
pub_task_is_root_done
pub_task_is_app_scan
pub_task_is_app_rewrite
pub_task_is_app_operator_done
```

Do not write compound `task.kind == X or task.kind == Y` expressions inside request muxes; the current file explicitly avoids that PipelineC frontend hazard.

Graph RAM requests needed by slice 1 are only:

```text
PUB_GRAPH            -> read task.a
PUB_APP_SCAN         -> read task.b
PUB_APP_OPERATOR_DONE-> no extra graph read if operator was already validated by APP_SCAN;
                        otherwise read task.b if implementation chooses revalidation
```

The root memo request is indexed by a validated source root. Generation mismatch means unseen.

The task RAM needs only one `rw` port because `MICRO_PUB_STACK` serializes stack mutations. Do not add multiple task write ports just to emulate Concrete's conceptual multi-push in one cycle.

---

## Two-microstate envelope

Because IDs 126 and 127 are the only free `uint7_t` states, use the task kind plus a small `pub_phase` register rather than allocating one hardware microstate per publication operation.

### `MICRO_PUB_EXEC` (126)

Responsibilities:

1. read the current top task (`pub_sp - 1`);
2. read graph/root-memo data needed for that task;
3. perform all semantic validation for this task step;
4. prepare zero to three replacement/push entries in `pub_pending0..2`;
5. prepare any root-memo write for the same step;
6. set `pub_pending_count` / `pub_phase`;
7. transition to `MICRO_PUB_STACK` when stack RAM must change;
8. otherwise remain in `MICRO_PUB_EXEC` or finish.

### `MICRO_PUB_STACK` (127)

This is a pure scratch mutation state. It performs at most one task-RAM write per clock and advances `pub_phase` until the staged stack operation is complete, then returns to `MICRO_PUB_EXEC`.

No semantic validation belongs here. This guarantees that a task-stack write can never become the point where a RED2 semantic fault is discovered.

A convenient convention is that `pub_pending0..N-1` describe the complete replacement for the old top task, bottom-to-top. `MICRO_PUB_STACK` first decrements/replaces the old top logically, then emits the staged entries in order. Any equivalent one-port serialization is fine as long as stack-capacity is checked in `MICRO_PUB_EXEC` before the first scratch write.

---

## Slice-1 task semantics

### `PUB_GRAPH(root)`

Validation/fault order:

1. root architectural address range;
2. source word `valid` bit;
3. root memo generation/state;
4. opcode-specific dispatch.

Memo behavior:

```text
generation mismatch / EMPTY:
    write VISITING(root)
    replace GRAPH with ROOT_DONE(root)
    push the dispatched child task when required

DONE:
    pub_value = memo.result
    pop GRAPH

VISITING:
    FAULT_ILLEGAL_TRANSITION
```

Supported terminal roots for this landing are exactly the non-allocating subset needed by A3 slice 1:

```text
head INT
head FLOAT
head CHAR
head shareable SYM (definition_valid == 0)
VAR
UBV
```

For those:

```text
pub_value = root
```

`MOP_APP` dispatches to `APP_SCAN(root, root)`.

Do not silently treat EP, CLOSURE, REC, LAMBDA, RBLOCK, STRUCT, or other composite roots as stable in this slice. They are later publication families. If the generic fallback encounters one, set `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` and enter `MICRO_FAULT` while leaving architectural state untouched.

This is intentionally narrower than existing specialized JOIN paths, which continue to handle the cases they already support.

### `PUB_ROOT_DONE(root)`

Write:

```text
memo[root] = DONE(pub_value, generation=pub_generation)
```

then pop.

The memo write is scratch only. No architectural write occurs.

### `PUB_APP_SCAN(root, cursor)`

Before issuing a RAM request, validate `cursor` is an architectural graph address. This prevents a malformed unterminated APP from wrapping the physical RAM address.

Decode once:

```text
valid
opcode
kind
head
inline family
```

Cases:

#### APP descriptor

Validate in this order:

```text
word valid
kind == DATA_SIGNED
target not negative
target upper bits fit GRAPH_ADDR_BITS
cursor != fsp boundary if preserving current JOIN APP invariant
```

Then stage:

```text
APP_SCAN(root, cursor+1)
APP_REWRITE(descriptor=cursor, original_target=target)
PUB_GRAPH(target)
```

The stack-capacity check for all three resulting live entries must happen before the first task-RAM write. If capacity is insufficient: `FAULT_CONTROL_OVERFLOW`.

#### APP_VAR

Transparent prefix entry:

```text
APP_SCAN(root, cursor+1)
```

#### non-head inline

Transparent prefix entry, matching existing `MICRO_JOIN_APP_SCAN`:

```text
APP_SCAN(root, cursor+1)
```

#### head terminal operator

For this first slice, accept only the same stable terminal family listed above (the frozen witnesses use head INT).

Stage:

```text
APP_OPERATOR_DONE(root, operator=cursor)
PUB_GRAPH(cursor)
```

Everything else remains `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` for this landing.

### `PUB_APP_REWRITE(descriptor, original_target)`

This slice has no patch journal.

Therefore:

```text
if pub_value != original_target:
    HW_FAULT_EXECUTION_NOT_IMPLEMENTED
else:
    pop
```

This is the key allocation-free contract. It ensures a future relocation can never be accidentally accepted without recording the required descriptor patch.

### `PUB_APP_OPERATOR_DONE(root, operator)`

Require:

```text
pub_value == operator
```

Otherwise `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`.

On success:

```text
pub_value = root
pop
```

When the final root `ROOT_DONE` completes and the stack becomes empty, finish through the caller ABI below.

---

## Root memo generation policy

`promote_generation` deliberately survives architectural reset/load today. Use the same policy for `pub_generation`: it is private scratch identity, not architectural RED2 state.

Do not clear `pub_root_ram` on `CMD_RESET`, `CMD_LOAD_STATE`, or `CMD_START`.

At every publication launch:

```text
next_generation = pub_generation + 1
```

Use that generation for the entire walk.

A generation mismatch is equivalent to EMPTY, so reset/load need only clear active publisher registers (`pub_sp`, pending count/phase, resume kind, etc.), not the RAM.

Generation wrap must have defined behavior. The full A2 design recommends an explicit scratch clear sweep when increment wraps to zero, then restart at generation 1. Because such a sweep requires additional envelope machinery and is unreachable in realistic first-slice testing, it is acceptable for the first landing to reserve generation 0 and route wrap to `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`, provided this is explicitly documented and no stale generation is ever accepted as current. Do **not** silently wrap to zero.

---

## Reverse-JOIN launch points

Do not launch generically from every multiword APP result yet. Doing so would regress already-supported specialized EP/closure behavior.

Use generic publication only as a fallback from existing no-write gaps.

### A. Third unique target

Current location: `MICRO_JOIN_APP_SCAN`, lines 9475–9478.

Replace the current unconditional `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` branch with generic launch of the **whole APP result root**:

```text
pub_launch_root = join_result_address
pub_resume_kind = PUB_RESUME_JOIN
pub_generation += 1
pub_sp = 1
stack[0] = PUB_GRAPH(join_result_address)
pub_value = 0
join_preserve_fsp = 1
join_published_root = join_result_address
microstate = MICRO_PUB_EXEC
```

Restarting at `join_result_address` is much safer than trying to splice the generic walker into the partially populated first/second-target registers. The walk revalidates the whole APP graph transactionally and naturally handles any target cardinality.

### B. One-target nested APP

Current location: `MICRO_JOIN_APP_TARGET_READ`, lines 9555–9557.

Change only the `MOP_APP` case:

```text
if target opcode == MOP_APP:
    launch whole result root through generic publisher
else:
    preserve existing HW_FAULT_EXECUTION_NOT_IMPLEMENTED behavior
```

Do not redirect EP here; the existing EP path immediately below already supports EP publication semantics that slice 1 does not.

### C. Two-target nested APP

Current location: `MICRO_JOIN_MULTI_TARGET_READ`, lines 9630–9633.

Again change only the `MOP_APP` case to launch the whole result root.

Leave CLOSURE/REC and other unsupported roots on the existing fault path. EP continues through `MICRO_JOIN_MULTI_TARGET_CHASE`.

This preserves all existing allocation semantics and ensures the generic slice is exercised exactly where its new capability is needed.

---

## Publisher finish ABI

For `PUB_RESUME_JOIN`, stack-empty success must verify the first-slice invariant:

```text
pub_value == pub_launch_root
```

If not, this slice encountered a relocation it cannot commit: `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`.

If equal, prepare the existing JOIN parent publication:

```text
join_publish_word = red2_word_t(
    lo=join_result_address,
    hi=69337088,  # APP descriptor encoding already used by current JOIN paths
)
join_needs_ep_cache = 0
join_preserve_fsp = 1
join_published_root = join_result_address
microstate = MICRO_JOIN_PUBLISH
```

Do not restore the saved frame in the publisher. Do not clear control entries in the publisher. Do not set `s_a` in the publisher.

`MICRO_JOIN_PUBLISH` / `MICRO_JOIN_CONTROL_CLEAR` already perform the architectural commit in the right order:

1. parent APP write;
2. restore `env/free_space`;
3. set `s_a = join_published_root + 1`;
4. preserve `fsp` because `join_preserve_fsp=1`;
5. clear the control suffix/frame;
6. restore primitive bookkeeping;
7. set `pc = join_parent_address - 1`;
8. reach `MICRO_COMMIT`.

That exact tail is why the frozen witnesses should match Concrete without any new JOIN finalization code.

---

## Fault precedence

Keep the existing RED2-vs-hardware distinction.

Publisher semantic faults:

```text
FAULT_INVALID_ADDRESS
    - source/root/cursor outside architectural graph range
    - invalid source word where an architectural graph word is required
    - APP target malformed as address (wrong signed kind, negative, high bits set)

FAULT_CONTROL_OVERFLOW
    - fixed task stack cannot accommodate the complete staged push before mutation

FAULT_ILLEGAL_TRANSITION
    - root memo state is VISITING (publication recursion cycle)
```

Slice-not-yet-implemented semantics:

```text
HW_FAULT_EXECUTION_NOT_IMPLEMENTED
    - EP/CLOSURE/REC/LAMBDA/RBLOCK/STRUCT reached through generic fallback
    - child publication changes root (`APP_REWRITE` would need a patch)
    - operator publication changes root
    - generation wrap if clear-sweep is intentionally deferred
```

Check address/word validity before classifying a root as unsupported. A malformed APP target should remain a RED2 `FAULT_INVALID_ADDRESS`, not be masked by `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`.

Once either fault is set, enter `MICRO_FAULT`; the top-level status already gives fault status precedence over all other statuses.

No publisher failure may have changed architectural RAM or architectural registers.

---

## Reset / load-state / start handling

The reviewed reset blocks currently clear the selector-promoter task registers but intentionally do not clear `promote_generation`.

Add publisher-active register clearing in all three architectural reinitialization paths:

- `CMD_RESET` block around lines 2062–2289;
- `CMD_LOAD_STATE` block around lines 2305–2531;
- successful `CMD_START` block beginning around line 2532.

Clear:

```text
pub_sp
pub_value
pub_launch_root
pub_resume_kind
pub_phase
pub_pending_count
pub_pending0/1/2
```

Do not clear `pub_generation` or walk the root-memo RAM.

The scratch generation is not architectural checkpoint state.

---

## PipelineC / Pypeline hazards

### 1. Only two 7-bit microstate IDs remain

Current IDs occupy 0–125 and `microstate` / status expose `uint7_t`.

Do not add five named publisher microstates without first widening the ABI. For this slice, IDs 126 and 127 plus task-kind/phase registers are the least invasive solution.

Longer-term A4+ work will likely force either microstate widening or consolidation/removal of older specialized states. That should be a separate ABI-conscious change.

### 2. Use one task-RAM write per clock

Concrete pushes several logical tasks atomically. Do not model that by giving the stack RAM several write ports. Stage entries in registers and serialize them through `MICRO_PUB_STACK`.

Perform stack-capacity preflight for the complete logical push before the first scratch write.

### 3. Keep address state 17-bit

`GRAPH_WORDS` is 256 but sentinel arithmetic still uses a wider address domain. Keep roots/cursors/targets as `uint17_t` and truncate only after range validation when driving the 8-bit RAM address.

Do not copy current legacy JOIN `uint16_t` choices into the new publisher ABI.

### 4. Avoid generic ordered comparisons

Use fixed-width subtraction/sign-bit tests or explicit high-bit range tests already established in this source. Avoid mixed-width `<`, `<=`, chained comparisons, or computed Python ranges in synth logic.

### 5. Decode each source expression once

Especially inside the large request/reducer graph, assign opcode/kind/head/valid and each task-kind equality to named wires once. Repeated comparison trees on `memory_out.p0.rd_data` or `task.kind` are a known frontend naming/merge hazard in this file.

### 6. Keep request routing flat

Follow the current sibling-`if` request mux style. Do not insert the publisher as a deep `elif` subtree under existing JOIN routing.

### 7. Root memo read/write scheduling

The root memo has one `rw` port. Do not rely on ambiguous same-address read-during-write behavior for correctness. Read memo state during `MICRO_PUB_EXEC`; if a write is needed, stage it and perform it in the scratch-mutation phase before the corresponding child can be observed again.

The task RAM and root memo are separate physical scratch RAMs, so they may each perform one operation in the same clock.

### 8. Preserve selector promoter verbatim

Do not generalize `promote_forward_ram`, `promote_mat_ram`, `promote_task_*`, or `MICRO_STRUCT_SELECTOR_PROMOTE_GENERIC*` into the new engine in this slice. That migration is desirable later, but coupling it to first task-stack bring-up substantially enlarges the regression surface.

---

## Witness mapping

### Frozen three-target witness

`scripts/check_syn_sim.py` current lines 3347–3387:

```text
result root 5:
  5 APP -> 20
  6 APP -> 21
  7 APP -> 22
  8 head INT

20 head INT
21 head CHAR
22 head INT
```

Current failure is the third-target branch in `MICRO_JOIN_APP_SCAN`.

With the proposed fallback, the generic walker restarts at root 5, recursively marks each root VISITING/DONE, sees all three target roots return unchanged, verifies the head operator, memoizes root 5 DONE(5), and resumes `MICRO_JOIN_PUBLISH`.

Expected final state is already frozen by Concrete:

```text
pc = 2
fsp = 8
env = 32
free_space = 32
s_a = 6
```

Graph targets remain byte-for-byte unchanged; only the existing parent publication/control cleanup occurs.

### Frozen nested-APP witness

`scripts/check_syn_sim.py` current lines 3389–3429:

```text
result root 5:
  5 APP -> 20
  6 APP -> 21
  7 head INT

20 APP -> 24
21 head INT
24 head INT
```

The generic walker recursively enters root 20, validates its APP prefix/operator, returns 20 unchanged, then completes root 5 unchanged.

Expected frozen final state:

```text
pc = 2
fsp = 7
env = 32
free_space = 32
s_a = 6
```

Again there are no publisher graph writes.

---

## Tests that should accompany implementation

The frozen `third_target` and `nested_target` red witnesses should be converted from “expects hardware gap” to ordinary `_run_encoded_to_same_commit` parity checks.

Add focused pure-walker cases before expanding semantics:

1. 3 distinct stable targets;
2. 5 distinct stable targets;
3. repeated target references;
4. nested APP sharing a target already memoized by its parent/sibling;
5. one-target nested APP (covers the `MICRO_JOIN_APP_TARGET_READ` fallback);
6. direct APP cycle -> `FAULT_ILLEGAL_TRANSITION` with graph/control unchanged;
7. late invalid APP target -> `FAULT_INVALID_ADDRESS` with graph/control unchanged;
8. task-stack overflow -> `FAULT_CONTROL_OVERFLOW` with graph/control unchanged;
9. nested EP/CLOSURE through the generic fallback -> still `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`, with no mutation.

Do not make `distinct_allocating` green in this slice. It intentionally exercises a closure/materialization family that remains later work.

---

## Non-goals for this landing

Do not implement or modify:

- EP chase/relocation in the generic walker;
- APP descriptor patch journaling;
- closure materialization;
- REC/RBLOCK publication;
- STRUCT publication;
- LAMBDA publication;
- selector promotion;
- `promote_*` RAMs or tasks;
- existing specialized one/two-target EP publication;
- existing closure publication fast paths;
- control-frame format;
- top-level status ABI;
- architectural graph/control RAM port counts.

The first slice succeeds if it proves that arbitrary APP target multiplicity, nesting, sharing, and cycles can be handled by fixed scratch state and then handed back to the existing reverse-JOIN commit tail without any allocating semantics or architectural pre-commit writes.

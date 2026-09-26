Design for Project A2: replace the current shape-specific JOIN/selector publication machinery with one bounded publication engine built around three fixed scratch memories: a generation-tagged root memo, a materialization buffer, and an explicit task stack. Do not shadow architectural graph RAM or control RAM.

## 1. Architectural model

Treat publication as an internal transaction:

```text
launch(root, interval_start, interval_stop, destination_policy, context)
    |
    v
PRELIGHT / PLAN
    - walk the graph
    - validate every source address/shape
    - resolve sharing
    - chase EPs
    - determine all relocations/materializations
    - compute final fsp/root
    - generate scratch output only
    - perform zero graph_ram writes
    |
    v
VALIDATE
    - all materialized slots valid
    - final destination range fits
    - task stack did not overflow
    - every planned architectural rewrite is representable
    - no unresolved visiting nodes
    |
    v
COMMIT
    - deterministic replay of already validated writes
    - no fallible semantic checks
    - update fsp/root/result registers
    |
    v
caller continuation
```

The important departure from Concrete is that failure atomicity comes from **no architectural writes before validation**, rather than Concrete's whole-graph copy in `_task_memory`.

The existing selector promoter already demonstrates the right general pattern:

- `promote_mat_ram` is full `GRAPH_WORDS` scratch.
- `promote_forward_ram` is generation tagged.
- scratch survives RESET and is epoch-invalidated rather than physically cleared.
- commit is a separate pass after validation.
- the architectural graph is untouched through the fallible portion.

A2 should generalize this mechanism rather than build a second publication subsystem.

---

# 2. Scratch RAMs

## 2.1 Root/memo RAM

Replace/generalize `red2_promote_forward_t` into:

```python
@struct
class red2_pub_root_t(NamedTuple):
    generation: uint32_t
    state: uint2_t
    result: uint17_t
    aux: uint17_t
```

Suggested states:

```text
PUB_ROOT_EMPTY     = 0
PUB_ROOT_VISITING  = 1
PUB_ROOT_DONE      = 2
PUB_ROOT_RESERVED  = 3
```

Meaning:

- `VISITING`: this root is currently on the publication DFS stack.
- `DONE`: `result` is the publication result for that source root.
- `EMPTY`: either generation mismatch or unused.
- `aux`: available for a later REC/closure-specific memo result or materialization base; A3 can leave zero.

One row per architectural graph address:

```python
pub_root_ram: GRAPH_WORDS × red2_pub_root_t
```

This subsumes:

- Concrete `_task_pub_root_state`
- `_task_pub_root_result`
- `_task_pub_closure_valid/result`
- eventually `_task_pub_rec_valid/result`

Do **not** add separate closure/REC memo RAMs unless an implementation constraint forces it. The task kind that created the memo does not matter after the source root has a unique published result.

Generation matching replaces all scratch clearing.

### Cycle semantics

When `PUB_GRAPH(address)` sees:

- generation mismatch → unseen
- `DONE` → return memoized `result`
- `VISITING` → `FAULT_ILLEGAL_TRANSITION`

That directly captures Concrete `TASK4_PUB_GRAPH` root-cycle detection.

REC rewrite visitation is different: some recurrence is intentionally revisitable/ignored. That should use a separate traversal-visit RAM described below rather than weakening root-cycle semantics.

---

## 2.2 Materialization RAM

Generalize the current:

```python
class red2_promote_mat_t:
    word: red2_word_t
    valid: uint1_t
```

to:

```python
@struct
class red2_pub_mat_t(NamedTuple):
    word: red2_word_t
    generation: uint32_t
```

One row per potential output word:

```python
pub_mat_ram: GRAPH_WORDS × red2_pub_mat_t
```

`generation == pub_generation` means valid.

This is preferable to a separate `valid` bit because it makes each transaction logically clear without an O(GRAPH_WORDS) invalidation.

Materialized APP addresses remain **relative scratch offsets** until commit, just as Concrete `_task_mat_words` does. Commit adds the selected destination base.

This RAM is not architectural shadow memory: it holds only newly constructed/relinearized output.

---

## 2.3 Traversal-visit RAM

Materialization and recursive rewriting require cycle detection keyed by more than source address.

Add:

```python
@struct
class red2_pub_visit_t(NamedTuple):
    generation: uint32_t
    address: uint17_t
    environment: uint17_t
    depth: uint17_t
    head: uint1_t
    mode: uint3_t
```

with:

```python
pub_visit_ram: GRAPH_WORDS × red2_pub_visit_t
```

and a register:

```text
pub_visit_count : uint17_t
```

The RAM is used as a compact explicit active-path stack, not an arbitrary associative cache.

Modes eventually include:

```text
VISIT_MATERIALIZE
VISIT_REC_REWRITE
VISIT_RELINEARIZE
```

A linear scan against `0 .. pub_visit_count-1` exactly mirrors Concrete's bounded visit arrays and avoids synthesis-hostile general associative structures.

On entry:

1. scan active visit records;
2. if the relevant equality tuple matches:
   - materialization → `FAULT_ILLEGAL_TRANSITION`;
   - REC rewrite → skip according to Concrete behavior;
3. append record;
4. push a `LEAVE_VISIT` task;
5. on leave decrement `pub_visit_count`.

This keeps maximum live visit state ≤ `GRAPH_WORDS`.

---

## 2.4 Task stack RAM

This is the main missing substrate.

Do not use dozens of scalar `promote_task_a/b/c/d` registers.

Add a fixed RAM:

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

and:

```python
pub_task_ram, ... = make_ram(
    red2_pub_task_t,
    PUB_TASK_WORDS,
    ports=("rw",),
    read_latency=0,
)
```

Register:

```text
pub_sp : uint18_t
```

encoded as count, so zero means empty and top is `pub_sp - 1`.

### Stack capacity

Concrete uses:

```text
memory_words * 4 + control_words + 64
```

That is safe but probably over-large for hardware.

For A2/A3, choose:

```text
PUB_TASK_WORDS = GRAPH_WORDS * 4
```

unless synthesis/resource measurements show that unacceptable.

Why 4× is defensible initially:

- APP DFS can have `PUB_GRAPH + ROOT_DONE + APP_SCAN + APP_REWRITE` per nested edge.
- materialization similarly creates graph/leave/process continuations.
- it preserves Concrete's existing asymptotic bound without introducing a proof burden prematurely.

Later it can be tightened after an explicit maximum-stack proof.

A stack push beyond `PUB_TASK_WORDS` returns `FAULT_CONTROL_OVERFLOW`, before graph commit.

---

# 3. Engine registers

Replace the current generic promoter scalar state with something like:

```text
pub_active              : uint1
pub_phase               : uint3
pub_generation          : uint32

pub_root                : uint17
pub_value               : uint17

pub_interval_start      : uint17
pub_interval_stop       : uint17

pub_destination         : uint17
pub_final_fsp           : uint17

pub_mat_count           : uint17
pub_visit_count         : uint17
pub_sp                  : uint18

pub_commit_index        : uint17
pub_commit_count        : uint17

pub_resume_kind         : uint4
pub_mode                : uint4

pub_environment         : uint17
pub_phi                 : uint32

pub_work_word           : red2_word_t
pub_work_word2          : red2_word_t
pub_work_address        : uint17
pub_work_address2       : uint17

pub_fault               : uint3
```

Optional later:

```text
pub_rec_context         : uint17
pub_rec_block           : uint17
pub_rec_count           : uint17
pub_rec_selected        : uint17
pub_depth               : uint17
```

but prefer carrying context in task entries unless it is global for a whole suboperation.

### Phases

```text
PUB_PHASE_IDLE       = 0
PUB_PHASE_PREFLIGHT  = 1
PUB_PHASE_VALIDATE   = 2
PUB_PHASE_COMMIT     = 3
PUB_PHASE_FINISH     = 4
```

Avoid encoding semantic task states as top-level `MICRO_*` states. There should ideally be a small public-engine microstate envelope:

```text
MICRO_PUB_STEP
MICRO_PUB_VALIDATE
MICRO_PUB_COMMIT_READ
MICRO_PUB_COMMIT_WRITE
MICRO_PUB_FINISH
```

and task kinds decide semantic behavior within `MICRO_PUB_STEP`.

That is how this actually subsumes today's exploding JOIN state set.

---

# 4. Task kinds

Use one namespace for publication plus materialization.

A useful initial allocation:

```text
PUB_TASK_NONE = 0

PUB_TASK_GRAPH = 1
PUB_TASK_ROOT_DONE = 2

PUB_TASK_APP_SCAN = 3
PUB_TASK_APP_REWRITE = 4
PUB_TASK_APP_OPERATOR_DONE = 5

PUB_TASK_LAMBDA_SCAN = 6
PUB_TASK_LAMBDA_DONE = 7

PUB_TASK_EP_CHASE = 8
PUB_TASK_EP_RESULT = 9

PUB_TASK_MAT_GRAPH = 10
PUB_TASK_MAT_VISIT_SCAN = 11
PUB_TASK_MAT_LEAVE = 12
PUB_TASK_MAT_APP_SCAN = 13
PUB_TASK_MAT_APP_PROCESS = 14
PUB_TASK_MAT_LAMBDA_SCAN = 15
PUB_TASK_MAT_LOOKUP = 16
PUB_TASK_MAT_ENV_CHASE = 17
PUB_TASK_MAT_CLOSURE = 18
PUB_TASK_MAT_REHEAD = 19

PUB_TASK_CLOSURE = 20
PUB_TASK_CLOSURE_DONE = 21

PUB_TASK_RBLOCK_SCAN = 22
PUB_TASK_RBLOCK_BINDING_DONE = 23
PUB_TASK_RBLOCK_BODY_DONE = 24

PUB_TASK_STRUCT_SCAN = 25

PUB_TASK_REC = 26
PUB_TASK_REC_SCAN = 27
PUB_TASK_REC_BINDINGS = 28
PUB_TASK_REC_WRITE_PLAN = 29

PUB_TASK_REC_RW_GRAPH = 30
PUB_TASK_REC_RW_VISIT = 31
PUB_TASK_REC_RW_LEAVE = 32
PUB_TASK_REC_RW_APP_SCAN = 33
PUB_TASK_REC_RW_LAMBDA_SCAN = 34
PUB_TASK_REC_RW_RBLOCK = 35
PUB_TASK_REC_RW_EP_CHASE = 36
PUB_TASK_REC_RW_STRUCT = 37

PUB_TASK_MAT_STRUCT_SCAN = 38
PUB_TASK_MAT_STRUCT_PROCESS = 39
```

A3 only implements 1–9 and perhaps 10–15 incrementally.

The point is to freeze the ABI now so A4–A8 extend it rather than inventing parallel machines.

---

# 5. Generic `PUB_GRAPH`

This should follow Concrete almost literally at the semantic level:

```text
PUB_GRAPH(address):
    validate architectural source address
    inspect pub_root[address]

    DONE:
        pub_value = memo.result
        pop

    VISITING:
        fault ILLEGAL_TRANSITION

    unseen:
        memo[address] = VISITING
        replace/pop current task
        push ROOT_DONE(address)

        dispatch source:
            EP          -> push EP_CHASE(...)
            APP prefix  -> push APP_SCAN(root=address,cursor=address)
            LAMBDA      -> push LAMBDA_SCAN(root=address,cursor=address)
            RBLOCK      -> ...
            STRUCT      -> ...
            otherwise:
                pub_value = address
```

`ROOT_DONE`:

```text
memo[root] = DONE(pub_value)
pop
```

This immediately gives sharing/root memoization for arbitrary APP target multiplicity.

---

# 6. APP publication architecture

Current Synth's major limitation is structural:

- it tracks first target in `join_app_shared_target`;
- second in `join_app_second_target`;
- third target faults.

That disappears entirely.

## `PUB_TASK_APP_SCAN`

Fields:

```text
a = application root
b = cursor
```

For each prefix entry:

### APP

Validate signed nonnegative target.

Then:

```text
replace current task with APP_SCAN(root, cursor+1)
push APP_REWRITE(descriptor=cursor, original_target=target)
push PUB_GRAPH(target)
```

### APP_VAR or non-head inline

```text
cursor++
```

### terminal operator

```text
replace/pop
push APP_OPERATOR_DONE(root, operator=cursor)
push PUB_GRAPH(cursor)
```

No unique-target bookkeeping at all.

Three, thirty, or three thousand distinct targets are the same operation.

## `APP_REWRITE`

After `PUB_GRAPH(target)`:

```text
if pub_value == original_target:
    no architectural mutation needed
else:
    record planned descriptor rewrite
```

The crucial hardware question is where that rewrite goes before commit.

For A3, use the existing full scratch materialization RAM as a **transaction journal indexed by architectural address**, but add metadata distinguishing a journal entry from materialized output.

---

# 7. Transaction journal without graph shadow RAM

Extend the scratch row to:

```python
@struct
class red2_pub_mat_t(NamedTuple):
    word: red2_word_t
    generation: uint32_t
    kind: uint2_t
```

Kinds:

```text
PUB_SCRATCH_EMPTY       = 0
PUB_SCRATCH_MATERIAL    = 1
PUB_SCRATCH_PATCH       = 2
PUB_SCRATCH_RESERVED    = 3
```

But a single RAM index space cannot simultaneously use index `N` for materialized slot N and architectural patch address N.

Therefore use **two logical RAMs**, not a whole architectural shadow:

### Materialized words

```text
pub_mat_ram[GRAPH_WORDS]
```

### Patch journal

```python
@struct
class red2_pub_patch_t(NamedTuple):
    generation: uint32_t
    word: red2_word_t
```

```text
pub_patch_ram[GRAPH_WORDS]
```

indexed directly by architectural address.

A generation hit means:

```text
on commit, graph[address] := patch.word
```

This gives O(1) overwrite/dedup for repeated rewrites of one descriptor.

Add:

```text
pub_patch_count : uint17
```

You still need to know which addresses to commit without scanning all GRAPH_WORDS. There are two options.

### Recommended: patch-address list

Add:

```text
pub_patch_addr_ram[GRAPH_WORDS] : uint17_t
```

When patching address A:

1. read `pub_patch_ram[A]`;
2. if generation mismatch:
   - append A to `pub_patch_addr_ram[pub_patch_count]`;
   - increment `pub_patch_count`;
3. write latest patch at A.

Commit iterates only `0 .. pub_patch_count-1`.

This is much smaller than full graph shadowing:

```text
patch word RAM:     GRAPH_WORDS × ~160 bits
patch address list: GRAPH_WORDS × 17 bits
```

versus duplicating every graph word plus all architectural control state.

More importantly, it makes **all in-place source rewrites transactional**, including:

- APP target relocation
- EP → atomic
- EP → VAR / APP_VAR
- EP → APP after closure/REC allocation
- REC recursive-reference rewriting
- STRUCT descriptor retargeting

One mechanism handles them all.

---

# 8. Materialized allocations

New graph regions—closures, REC projection blocks, selector promotion, later relinearization—go into `pub_mat_ram`.

Registers:

```text
pub_mat_count
pub_destination
```

Every scratch APP descriptor stores a relative target.

At validation:

```text
destination = caller-provided destination
last = destination + pub_mat_count - 1

validate:
    destination in range
    last < relevant free_space/frontier
    every material slot [0,count) has generation hit
    every relative APP offset is < pub_mat_count
    every relocated absolute address fits GRAPH_ADDR_BITS
```

Commit then emits:

```text
graph[destination+i] = relocated(pub_mat[i])
```

No semantic fault can occur in this pass.

---

# 9. Commit protocol

Commit has two deterministic sections.

## Section A: existing-address patches

```text
for i in 0 .. pub_patch_count-1:
    addr = pub_patch_addr_ram[i]
    row = pub_patch_ram[addr]
    graph_ram[addr] = row.word
```

Generation is asserted logically already; don't introduce a new semantic fault here.

## Section B: allocated output

```text
for i in 0 .. pub_mat_count-1:
    word = pub_mat_ram[i]
    if APP:
        word.lo = pub_destination + relative
    graph_ram[pub_destination+i] = word
```

Then update:

```text
fsp = pub_final_fsp
published_root = pub_value
```

and return to the caller-specific continuation.

If overlap becomes necessary for STRUCT selector promotion, scratch materialization already solves it: source was completely read before commit, so commit order does not matter.

This is cleaner than today's backwards/forwards memmove path.

---

# 10. Exact atomicity boundary

The publication engine must not mutate any of these during PRELIGHT:

```text
graph_ram
control_ram
pc
fsp
env
control_top
q
phi
free_space
argcnt
prim_id
fire
s_a / s_d
```

Scratch may mutate freely.

JOIN frame discovery presents one issue: current Synth and Concrete conceptually consume/clear frame/control entries as part of the transaction.

For A2, publication should begin **after JOIN has already validated the frame but before any architectural control clearing**.

Snapshot into registers:

```text
join_frame_index
join_frame_env
join_frame_free_space
join_frame_prim_id
join_frame_fire
publication interval
```

Then run the publisher.

Only after publisher validation succeeds should the caller enter a JOIN final commit sequence that performs:

1. graph publication commit;
2. parent replacement;
3. control-frame clearing;
4. env/free_space restoration;
5. phi/prim/fire changes;
6. `pc`;
7. commit pulse.

No subsequent operation in that sequence may fail.

Thus the publisher's transaction and the enclosing RED2 transition share one final no-fail commit tail.

---

# 11. EP handling

`PUB_TASK_EP_CHASE` fields:

```text
a = descriptor_address
b = target_address
c = hop_count
flags.embedded
```

Each hop:

```text
range check
word valid
if EP:
    validate signed/nonnegative next
    if hops == GRAPH_WORDS-1:
        ILLEGAL_TRANSITION
    target = next
    hops++
    continue
```

At terminal:

### Outside interval

Exactly Concrete:

```text
if target < interval_start or target >= interval_stop:
    pub_value = descriptor_address
    done
```

Use subtraction/sign-bit helpers rather than generic ordered comparisons.

### Shareable atomic

Journal patch:

```text
descriptor_address := clone(target, head=descriptor.head)
pub_value = descriptor_address
```

### UBV

Journal:

```text
descriptor := VAR or APP_VAR depending embedded
index = phi - binder
preserve descriptor head/definition
```

### CLOSURE

```text
push EP_RESULT(descriptor, embedded)
push CLOSURE(target)
```

### REC

same:

```text
push EP_RESULT(...)
push REC(target)
```

### Other

`FAULT_ILLEGAL_TRANSITION`.

`EP_RESULT` journals an APP rewrite only when `embedded`, matching Concrete's `TASK4_PUB_EP_CLOSURE_DONE`.

Root EP through closure/REC leaves the original EP descriptor as root where Concrete does; embedded EP gets converted to APP.

---

# 12. LAMBDA

Simple publication requires no allocation.

`LAMBDA_SCAN(root,cursor)`:

```text
while word[cursor] == LAMBDA:
    cursor++

push LAMBDA_DONE(root, body=cursor)
push PUB_GRAPH(body)
```

`LAMBDA_DONE` requires:

```text
pub_value == body
```

then returns `root`.

This is exactly Concrete and is cheap to land alongside APP in A3.

General closure materialization is separate and uses `MAT_LAMBDA_SCAN`.

---

# 13. Closure materialization

A4 can directly reuse the generic materializer.

`CLOSURE(address)`:

1. memo check through root memo;
2. validate closure and code slot;
3. remember `base = pub_mat_count`;
4. `MAT_CLOSURE` recursively emits the code graph with captured environment;
5. after all materialization is complete:
   - validate final capacity;
   - result = `pub_destination + base`;
   - memoize closure source root → result.

Materialization never writes graph RAM.

The existing `promote_mat_ram` is already the prototype for this.

---

# 14. REC/RBLOCK

REC is the hardest later consumer, but A2 should shape the substrate for it.

The current Concrete sequence is:

```text
PUB_REC
  -> scan RBLOCK count
  -> identify selected binding
  -> for every binding:
       recursively rewrite matching REC references to VAR/APP_VAR
       PUB_GRAPH(binding_root)
       require result == binding_root
  -> allocate:
       RBLOCK × count
       RUP(count)
       VAR(selected)
  -> memoize REC -> new destination
```

On Synth, recursive rewrite operations become patch-journal entries rather than architectural mutations.

That preserves atomicity even when the **last** recursive binding fails.

Important distinction:

- root publication recursion → `pub_root_ram VISITING`, cycles fault;
- REC rewrite traversal → `pub_visit_ram`, repeated visited tuple skips exactly like Concrete.

Do not merge those semantics.

---

# 15. RBLOCK and STRUCT

Both become ordinary task-stack walkers.

## RBLOCK

`RBLOCK_SCAN` iterates headers and recursively invokes `PUB_GRAPH(binding+1)`.

Concrete currently insists each binding and body publish in place (`pub_value == original`). Preserve that invariant unless REC semantics explicitly materializes a replacement.

## STRUCT

`STRUCT_SCAN`:

```text
APP descriptor:
    push APP_REWRITE
    push PUB_GRAPH(target)

EP descriptor:
    push EP_CHASE(embedded=1)

APP_VAR/non-head-inline:
    continue

VAR 0 terminator:
    return struct root
```

The existing separate preflight/rewrite STRUCT passes disappear because patch journaling naturally separates planning and commit.

---

# 16. Caller interface

Freeze a small launch ABI:

```text
pub_launch_root
pub_interval_start
pub_interval_stop
pub_destination
pub_environment
pub_phi
pub_resume_kind
pub_mode
```

Modes might be:

```text
PUB_MODE_JOIN
PUB_MODE_SELECTOR_PROMOTE
PUB_MODE_RELINEARIZE
PUB_MODE_CLONE
PUB_MODE_HOST_RESULT   # future, probably trivial
```

Resume kinds:

```text
PUB_RESUME_JOIN
PUB_RESUME_SELECTOR
PUB_RESUME_LAMBDA
PUB_RESUME_EQUALITY
PUB_RESUME_RECHARGE
```

Do not make task behavior branch heavily on resume kind. Resume kind should primarily select what happens **after successful publication**.

---

# 17. A3 first slice

The best first substrate proof is narrower than full A3.

Implement exactly:

```text
PUB_GRAPH
PUB_ROOT_DONE
PUB_APP_SCAN
PUB_APP_REWRITE
PUB_APP_OPERATOR_DONE
```

with stable terminal roots only:

```text
head INT/FLOAT/CHAR/shareable SYM
VAR
UBV where current Concrete PUB_GRAPH itself leaves root unchanged
```

Then add nested APP recursion.

Do **not** start with closure or REC.

### First acceptance witness

Construct a result graph such as:

```text
root APP -> target A
     APP -> target B
     APP -> target C
     APP_VAR ...
     non-head inline ...
     head operator
```

where:

- A is stable atomic/root,
- B is another APP graph,
- C is a third distinct APP graph,
- B contains an APP back to A to prove shared-root memo reuse without cycle,
- multiple descriptors point to the same target.

The current implementation faults at target #3; generic stack traversal must not.

Then escalate:

1. one target;
2. two targets;
3. three distinct targets;
4. five distinct targets;
5. duplicate targets among distinct ones;
6. nested APP target;
7. nested APP whose child shares an already-published target;
8. actual cycle → `FAULT_ILLEGAL_TRANSITION`;
9. bad late target → no graph mutation;
10. task stack overflow → no graph mutation.

### First allocation-free implementation

The very first landing can deliberately support only APP targets whose `PUB_GRAPH` result remains the same source address.

That proves:

- task stack;
- generation root memo;
- >2 targets;
- nesting;
- cycle detection;
- failure atomicity.

Then the next A3 slice adds EP relocation through the patch journal.

That is safer than mixing task-stack bring-up and allocation on day one.

---

# 18. A3 second slice: EP plus patch journal

Add:

```text
PUB_EP_CHASE
PUB_EP_RESULT
pub_patch_ram
pub_patch_addr_ram
```

Test:

- EP → atomic in interval;
- EP → UBV;
- embedded EP rewrite;
- outside-interval EP untouched;
- multiple APP descriptors sharing same EP;
- late invalid EP after earlier planned patches;
- EP cycle at exactly the hop bound;
- nested APP containing EP target.

This proves transactional architectural rewrites.

---

# 19. A3 third slice: materialized nested APP

Only then generalize `promote_mat_ram` into `pub_mat_ram` and prove allocation.

Minimal case:

```text
APP -> target requiring materialization
```

followed by:

```text
3+ APP targets where 2 allocate
nested APP whose relocated child allocates
shared allocating root referenced twice
capacity failure on last allocation
```

At this point A4 closure materialization is largely a new task family rather than new transaction machinery.

---

# 20. PipelineC/Pypeline hazards

Several coding constraints should be explicit in A2.

## Avoid generic ordered comparisons

The source already had to introduce `red2_u64_ge`.

For addresses use explicit fixed-width subtraction tests:

```text
delta = b - a
wrapped = delta[MSB]
nonzero = delta != 0
```

Do not write generic expressions such as:

```python
start <= x < stop
destination + count <= free_space
```

for mixed `uint16/17/64`.

Normalize to `uint17_t` once, then use subtraction/sign-bit checks.

---

## One comparison per source coordinate

The current comments around lines 764–766 are important.

Do not write:

```python
if task.kind == X or task.kind == Y or task.kind == Z:
```

when these comparisons expand inside large request muxes.

Prefer:

```python
task_is_x = task.kind == X
task_is_y = task.kind == Y
task_is_z = task.kind == Z

is_group = task_is_x or task_is_y
is_group = is_group or task_is_z
```

Likewise, avoid repeating:

```python
memory_out.p0.rd_data.hi[25:21] == ...
```

at the same source expression in multiple branches. Decode once to named wires.

---

## Avoid giant `elif` request selectors

The current source explicitly notes deep `elif` trees cause PipelineC to repeatedly merge large reducer graphs.

Use sibling `if`s guarded by mutually exclusive predecoded booleans, as current RAM routing does.

The publisher should have:

```text
pub_task_is_graph
pub_task_is_app_scan
...
```

computed once, then a flat request-routing section.

---

## Keep RAM port count modest

A task stack only needs one `rw` port if each microclock operates on one top entry.

Root memo ideally one `rw` port.

Patch RAM:

- one `rw` port is sufficient;
- address-list RAM one `rw`.

Materialization may retain the current `("r","w","w")` shape because APP processing can create a descriptor and an inline child on the same clock. But if that complicates the frontend, splitting the two writes over two microstates is acceptable and probably easier to synthesize.

Correctness is more important than one-cycle scratch emission.

---

## Avoid struct arrays encoded as Python containers

Everything should be:

```text
make_ram(struct, constant_size, ...)
Reg[fixed_type]
```

No Python list, dict, tuple stack manipulation in the synth path.

---

## Avoid task-range comparisons

Concrete has:

```python
TASK4_MAT_GRAPH <= kind <= TASK4_MAT_VISIT_SCAN
```

Do not copy that to PipelineC.

Use named equality wires or explicit mode bits.

---

## Be conservative with `uint17_t` addresses

Architectural graph addresses are physically `GRAPH_ADDR_BITS`, but boundary values such as `GRAPH_WORDS` require 17-bit sentinel arithmetic.

Recommended convention:

```text
source/destination/cursor/root registers = uint17_t
only truncate to GRAPH_ADDR_BITS when driving a validated RAM request
```

Never store potentially `GRAPH_WORDS` in `uint16_t`.

This would also clean up several current JOIN registers that are still `uint16_t`.

---

## Generation wrap

A 32-bit epoch is practically ample, but correctness should have a defined behavior.

Simplest policy:

```text
pub_generation += 1
if result == 0:
    enter explicit scratch-clear sweep
    set generation = 1
```

This sweep is extraordinarily rare and outside normal publication latency, but prevents stale generation aliasing in the formal contract.

Alternatively make generation wider if PipelineC cost is negligible.

---

# 21. Test staging

Use separate semantic and hardware-shape gates.

### Stage 0: structural/static

Test that the synth source contains:

- fixed task RAM;
- fixed root memo RAM;
- fixed patch journal;
- fixed materialization RAM;
- generation tagging;
- no Python dynamic structures in publisher;
- no third-target branch.

Frontend parse only after this shape is stable.

### Stage 1: pure walker, no writes

Native Synth vs Concrete:

- stable atomic APP target;
- 3+ targets;
- nested APP;
- APP_VAR prefix;
- non-head inline prefix;
- repeated/shared target;
- deep finite nesting;
- actual graph cycle;
- invalid target at final descriptor.

Assert graph RAM byte-for-byte unchanged on all failures.

### Stage 2: patch journal

EP/APP rewrites:

- one patch;
- same descriptor patched twice through nested traversal;
- multiple descriptors;
- shared root;
- outside interval;
- invalid late target;
- EP hop overflow.

Again compare full graph images, not just result root.

### Stage 3: materialization

- one allocating root;
- two shared references to allocating root → one allocation;
- 3+ mixed targets;
- exact-frontier success;
- one-word overflow;
- malformed last materialized word.

### Stage 4: JOIN integration

Compare committed state:

```text
pc
fsp
env
free_space
control_top
q
phi
prim/fire
s_a/s_d
graph
control RAM
```

Use the existing target-#3 witness as the headline regression.

### Stage 5: PipelineC

After A3 substrate is functionally green:

1. static shape tests;
2. direct `PY_TO_LOGIC.PARSE_FILE` or equivalent;
3. native focused parity;
4. `mise run test-fast`;
5. one frontend-only milestone gate.

Do not run full HDL emission for every task-kind addition.

---

# 22. What should disappear eventually

Once the engine is accepted, these become candidates for deletion or thin wrappers:

```text
MICRO_JOIN_APP_SCAN
MICRO_JOIN_APP_TARGET_READ
MICRO_JOIN_MULTI_TARGET_*
MICRO_JOIN_APP_REWRITE_*

MICRO_JOIN_EP_CHASE
special embedded EP paths

MICRO_JOIN_STRUCT_PREFLIGHT_*
MICRO_JOIN_STRUCT_REWRITE_*

MICRO_STRUCT_SELECTOR_PROMOTE_GENERIC*
```

The selector path is particularly valuable as the first caller to migrate because its current `PROMOTE_TASK_*` machinery is already an embryonic version of this design.

Specialized single-word atomic JOIN fast paths can remain. They should bypass the generic engine only when they are trivially no-fail and differential tests prove exact equivalence.

---

## Recommended A2 substrate

The smallest architecture that satisfies the epic constraints is therefore:

```text
1 × generation-tagged root memo RAM       [GRAPH_WORDS]
1 × generation-tagged active-visit RAM    [GRAPH_WORDS]
1 × explicit publication task-stack RAM   [~4*GRAPH_WORDS]
1 × generation-tagged materialization RAM [GRAPH_WORDS]
1 × generation-tagged patch RAM           [GRAPH_WORDS]
1 × patch-address-list RAM                 [GRAPH_WORDS]

+ fixed transaction registers
+ 5-ish publisher envelope microstates
```

That is more scratch than today's promoter, but critically it is **not a second architectural graph image**. It stores only traversal metadata, planned rewrites, and genuinely newly materialized words.

The first implementation target should be the current “third unique APP target needs generic publication stack” failure. If that witness, nested APPs, shared roots, cycles, and late invalid-target atomicity all pass through this substrate without introducing closure/REC logic, A2 has proven the right abstraction before the difficult cases arrive.

Advance the publication engine design

- :chatgpt-content-reference{index="0"}
- :chatgpt-content-reference{index="1"}
- :chatgpt-content-reference{index="2"}

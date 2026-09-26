# A3 slice 1 — allocation-free generic APP publisher pseudocode

This handoff freezes the narrow implementation shape recommended by the A2 integration review. It deliberately does **not** replace the current bounded JOIN APP path. The generic walker is entered only at the three existing APP gaps: third distinct target, one-target nested APP root, and two-target nested APP root.

## Scope

Supported recursively by the new walker:

- APP roots whose publication result remains the same architectural root;
- arbitrary APP prefix length bounded by graph memory;
- arbitrary number of distinct APP targets;
- APP_VAR transparent prefix entries;
- non-head inline transparent prefix entries;
- head inline application operator;
- stable target roots: head INT/FLOAT/CHAR/shareable SYM, VAR, UBV;
- nested APP targets;
- shared/repeated APP target roots;
- root-cycle detection;
- late invalid target failure before architectural graph/control/register writes.

Explicitly out of slice 1:

- EP traversal/publication;
- descriptor patch journaling;
- closure/REC allocation;
- materialization;
- lambda publication;
- selector migration;
- replacement of existing 0/1/2-target fast paths.

## Envelope

Use the two remaining 7-bit microstates:

```text
MICRO_PUB_APP_STEP  = 126
MICRO_PUB_APP_STACK = 127
```

`126` executes the current top task. `127` performs one stack/memo bookkeeping operation when a same-cycle RAM dependency would otherwise require an additional state. If implementation can safely combine the bookkeeping with the step RAM request, 127 may remain a narrow helper rather than a full semantic state.

On successful completion:

```text
join_publish_word = APP(join_result_address)
join_needs_ep_cache = 0
join_preserve_fsp = 1
join_published_root = join_result_address
microstate = MICRO_JOIN_PUBLISH
```

No architectural graph/control/register publication occurs before that return.

## Scratch

```text
PUB_TASK_WORDS = GRAPH_WORDS * 4

pub_generation : uint32
pub_sp         : uint18   # count; top is pub_sp-1
pub_value      : uint17
pub_root       : uint17   # launch root
```

Task RAM row:

```text
kind  : uint3
root  : uint17
cursor: uint17
arg   : uint17
```

Task kinds:

```text
PUB_TASK_NONE          = 0
PUB_TASK_GRAPH         = 1
PUB_TASK_ROOT_DONE     = 2
PUB_TASK_APP_SCAN      = 3
PUB_TASK_APP_REWRITE   = 4
PUB_TASK_OPERATOR_DONE = 5
```

For slice 1, APP_REWRITE is validation-only: it requires `pub_value == original_target`; otherwise the case belongs to the later patch-journal slice.

Root memo row:

```text
generation : uint32
state      : uint2   # EMPTY/VISITING/DONE
result     : uint17
```

States:

```text
PUB_ROOT_EMPTY    = 0
PUB_ROOT_VISITING = 1
PUB_ROOT_DONE     = 2
```

Generation mismatch means EMPTY. Increment generation at launch. Slice 1 may treat generation wrap as a defensive unsupported/internal boundary only if a later task explicitly installs the documented clear sweep before A2 is declared complete; preferred implementation is to reserve wrap handling now.

## Launch points

### Third distinct target in MICRO_JOIN_APP_SCAN

Instead of `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`, launch the walker at:

```text
root = join_result_address
```

The whole result APP graph is revalidated recursively. This avoids trying to import partially collected first/second-target state into the generic engine.

### One-target nested/non-EP root in MICRO_JOIN_APP_TARGET_READ

Instead of the current non-EP implementation fault, launch at:

```text
root = join_result_address
```

Again restart publication from the result APP root.

### Two-target nested/non-EP root in MICRO_JOIN_MULTI_TARGET_READ

Same launch root:

```text
root = join_result_address
```

Discard bounded-preflight scratch state; it is non-architectural.

## Launch transaction

```text
pub_generation += 1
pub_sp = 1
pub_task[0] = GRAPH(join_result_address)
pub_value = 0
microstate = MICRO_PUB_APP_STEP
```

Do not change graph RAM, control RAM, pc/fsp/env/q/phi/free_space/argcnt/prim/fire/s_a/s_d.

## GRAPH(address)

```text
validate address < GRAPH_WORDS
read memo[address]

if memo generation matches and state == DONE:
    pub_value = memo.result
    pop task
    continue

if memo generation matches and state == VISITING:
    fault FAULT_ILLEGAL_TRANSITION

otherwise:
    memo[address] = VISITING(current generation)
    replace GRAPH with ROOT_DONE(address)
    inspect graph[address]

    if invalid word:
        fault FAULT_INVALID_ADDRESS

    if opcode == APP:
        validate APP payload is DATA_SIGNED, nonnegative, in graph range
        push APP_SCAN(root=address, cursor=address)

    elif stable root:
        pub_value = address

    else:
        # EP/LAMBDA/RBLOCK/STRUCT/CLOSURE/REC/etc are later slices.
        # Preserve current explicit unsupported behavior rather than approximating.
        hw fault EXECUTION_NOT_IMPLEMENTED
```

Stable root for this slice is exactly the current APP publisher's unchanged-root set:

```text
(head INT/FLOAT/CHAR/shareable SYM) or VAR or UBV
```

Preserve current validity/kind checks where applicable. A defined SYM is not a shareable inline stable root.

## ROOT_DONE(root)

After child task returns in `pub_value`:

```text
memo[root] = DONE(result=pub_value)
pop ROOT_DONE
```

For all slice-1 supported roots, result should ultimately equal root; memoization still matters for sharing and cycle detection.

## APP_SCAN(root, cursor)

Read graph[cursor]. Validate address before consuming RAM output.

```text
if invalid:
    fault INVALID_ADDRESS

if APP:
    validate DATA_SIGNED
    validate target nonnegative and < GRAPH_WORDS
    validate cursor is not fsp when this is the live result prefix, matching existing fault precedence

    replace APP_SCAN(root,cursor) with APP_SCAN(root,cursor+1)
    push APP_REWRITE(descriptor=cursor, original_target=target)
    push GRAPH(target)

elif APP_VAR:
    if cursor == fsp: fault INVALID_ADDRESS
    cursor++

elif non-head inline accepted by current APP scan:
    if cursor == fsp: fault INVALID_ADDRESS
    cursor++

elif head inline accepted by current APP scan:
    # operator is itself stable and publishes in place
    push OPERATOR_DONE(root=root, operator=cursor)
    push GRAPH(cursor)
    remove/finish APP_SCAN

else:
    preserve current explicit unsupported/fault classification
```

Task pushes must preflight capacity before mutating `pub_sp`. Stack overflow maps to `FAULT_CONTROL_OVERFLOW` and cannot alter architectural state.

## APP_REWRITE(descriptor, original_target)

```text
if pub_value != original_target:
    # relocation/patching is slice 2
    hw fault EXECUTION_NOT_IMPLEMENTED
else:
    pop
```

No graph write occurs.

## OPERATOR_DONE(root, operator)

```text
if pub_value != operator:
    hw fault EXECUTION_NOT_IMPLEMENTED
else:
    pub_value = root
    pop
```

This matches Concrete's `PUB_APP_OPERATOR_DONE`: the operator must publish in place for this allocation-free slice.

## Completion

When `pub_sp == 0` after the root's ROOT_DONE:

```text
if pub_value != join_result_address:
    hw fault EXECUTION_NOT_IMPLEMENTED
else:
    join_publish_word = APP(join_result_address)
    join_needs_ep_cache = 0
    join_preserve_fsp = 1
    join_published_root = join_result_address
    microstate = MICRO_JOIN_PUBLISH
```

Existing JOIN publication/control-clear tail then performs the architectural commit exactly as before.

## Required regression ladder for this landing

The three frozen red witnesses must turn green for the APP subset only:

1. third distinct stable target -> Concrete parity;
2. nested APP target -> Concrete parity;
3. EP->REC remains red at its existing explicit gap.

Add focused slice-1 cases for:

- five distinct stable targets;
- duplicate/shared targets among distinct ones;
- nested APP whose child shares an already completed target;
- APP_VAR in prefix;
- non-head inline prefix word;
- direct APP cycle -> `FAULT_ILLEGAL_TRANSITION`;
- nested target with late invalid descriptor -> exact Concrete typed fault and zero architectural mutation;
- stack-capacity defensive case if reachable with GRAPH_WORDS=256.

Existing 0/1/2-target fast-path tests must remain unchanged and green.

## PipelineC constraints

- fixed `make_ram` task/memo memories only;
- use uint17 addresses/cursors until validated, truncate only at RAM request;
- predecode task-kind equalities once;
- sibling `if` request routing, no giant new elif chain;
- adding states 126 and 127 requires updating the static dispatch-count assertion from 126 to the new exact handled count;
- do not widen `red2_status_t.microstate` beyond uint7;
- do not touch selector `promote_*` RAMs in this slice.

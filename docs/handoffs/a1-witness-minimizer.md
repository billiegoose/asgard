I think the three A3 witnesses can be made quite small without inventing any new semantic machinery.

### 1. Third unique APP publication target

Use the same reverse-JOIN shell as `simple_join_encoded`, but the result graph only needs three APP descriptors followed by a head inline operator:

```python
memory[3] = APP(9)                  # parent
memory[4] = JOIN(3)
memory[5] = APP(20)                 # unique target #1
memory[6] = APP(21)                 # unique target #2
memory[7] = APP(22)                 # unique target #3
memory[8] = INT(3, head=True)       # application operator

memory[20] = INT(41, head=True)
memory[21] = CHAR("A", head=True)
memory[22] = INT(77, head=True)
```

Architectural registers/control:

```text
pc=4
fsp=8
env=28
free_space=28
c=0 / encoded c=1 with CONTROL_SUBGRAPH in slot 0
direction=B
q=0
phi=7
argcnt=0

control[0] = SUBGRAPH(
    env=32,
    free_space=32,
    prim=0,
    fire=0,
)
```

Concrete's generic `PUB_APP_SCAN` recursively visits all three targets and returns one normal JOIN commit. All three target roots are already stable, so no materialization is required; the interesting fact is simply that Concrete has no cardinality limit on unique APP targets.

Synth enters `MICRO_JOIN_APP_SCAN` (`50`). Target 20 initializes `join_app_shared_target`; target 21 becomes `join_app_second_target`; reading descriptor 7 with target 22 then reaches exactly:

```text
machine.py:9475
# A third unique target needs the generic publication stack.
hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
microstate = MICRO_FAULT
```

The externally reported faulting microstate remains `50`, as already asserted by the frozen witness at `check_syn_sim.py:3333`. No publication write has occurred.

The existing `third_target` fixture at lines 3297–3339 is already the exact family witness; it is just slightly noisier than necessary because it is derived from `distinct_app_join_encoded`.

---

### 2. Nested/non-EP APP target

To hit the *specific* `"Allocating/nested publication belongs to the generic walker"` multi-target branch rather than the simpler one-target guard at lines 9555–9557, two distinct prefix targets are required:

```python
memory[3] = APP(9)
memory[4] = JOIN(3)

memory[5] = APP(20)                 # unique target #1
memory[6] = APP(21)                 # unique target #2
memory[7] = INT(3, head=True)       # operator

memory[20] = APP(24)                # nested/non-EP root
memory[21] = INT(42, head=True)     # stable second root
memory[24] = INT(7, head=True)      # nested APP target
```

Use:

```text
pc=4
fsp=7
env=28
free_space=28
direction=B
q=0
phi=7
argcnt=0

control[0] = SUBGRAPH(env=32, free_space=32, prim=0, fire=0)
```

Concrete handles address 20 through generic `TASK4_PUB_GRAPH → TASK4_PUB_APP_SCAN`; since the nested APP ultimately points at a stable head INT, the recursive publication finishes and the JOIN commits normally.

Synth discovers two targets during `MICRO_JOIN_APP_SCAN`, reaches the head operator at 7, and switches to `MICRO_JOIN_MULTI_TARGET_READ` (`54`). Reading root 20 yields APP: it is neither stable nor EP, so it hits the branch immediately before the comment:

```text
# Allocating/nested publication belongs to the generic walker.
# The transaction has not written either target yet.
hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
microstate = MICRO_FAULT
```

Thus the first unsupported microstate is **54 / `MICRO_JOIN_MULTI_TARGET_READ`**, transactionally before either target is rewritten.

This is essentially the already-frozen `nested_target` witness at `check_syn_sim.py:3341–3374`; that fixture uses an EP wrapper around the nested APP, but the generic gap itself only needs the direct APP root above.

There is also a simpler **family-level** unsupported witness at lines 3376–3402: `distinct_allocating`, whose second target is a CLOSURE. It reaches the same bounded multi-target “needs generic publication/allocation” family, although not specifically the nested-APP branch.

---

### 3. EP terminal → REC

The cleanest witness is almost exactly `test_join_publishes_recursive_residual_before_reclaim_exactly`, because a valid REC is intrinsically a three-word environment record plus a valid recursive block.

```python
memory[2]  = STOP
memory[3]  = APP(9)                 # parent
memory[4]  = JOIN(3)
memory[5]  = EP(28, head=True)      # published result root

# Recursive source problem
memory[10] = RBLOCK(20)
memory[11] = RUP(1)
memory[12] = VAR(0, head=True)

memory[20] = SYM("x")
memory[21] = INT(7, head=True)

# REC environment record
memory[28] = REC(21)
memory[29] = NONE(28)               # context
memory[30] = NONE(10)               # recursive block
memory[31] = PNP(64)
```

State:

```text
pc=4
fsp=21
env=28
free_space=28
c=0 / encoded control depth 1
direction=B
q=0
phi=0
argcnt=0

control[0] = SUBGRAPH(
    env=32,
    free_space=32,
    prim=0,
    fire=0,
)
```

Here the EP terminal, address 28, lies inside the child reclaim interval `[28, 32)`, which is important: if you put the REC outside that interval Synth deliberately preserves the EP pointer and never needs to publish the REC.

Concrete follows:

```text
PUB_GRAPH(5)
→ PUB_EP_CHASE(5 → 28)
→ sees REC
→ TASK4_PUB_REC(28)
```

and materializes the recursive residual before restoring the frame. The existing Concrete test establishes the exact post-commit shape:

```text
residual = 22

memory[3]  = APP(22)
memory[22] = RBLOCK(20)
memory[23] = RUP(1)
memory[24] = VAR(0, head=True)

fsp        = 24
free_space = 32
env        = 32
```

Synth enters `MICRO_JOIN_EP_CHASE` (`39`). At address 28 it computes `join_ep_target_is_rec`, reaches:

```text
machine.py:7319
elif join_ep_target_is_rec:
    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
    microstate = MICRO_FAULT
```

So the first unsupported state is **39 / `MICRO_JOIN_EP_CHASE`**. Again, this occurs before recursive materialization or parent publication.

There is no frozen EP→REC red witness in `check_syn_sim.py` yet. The simpler family-level positive witnesses there are `join_ep_int`, `join_ep_chain_int`, UBV, outside-reclaim EP, and EP→CLOSURE. The exact Concrete semantic oracle already exists in `tests/test_concrete_red2_recursive.py:446–508`, making that the best source for the REC construction.

One detail from the attempted probes: importing/building the Synth simulation through the one-shot `uv run` command exceeded the harness timeout, so I would not claim a newly executed confirmation beyond the red fixtures already present. The source paths are nevertheless unambiguous, and gaps (1) and (2) are already exercised by existing red checks. Gap (3) is directly paired with an existing Concrete test and an explicit Synth `MOP_REC → HW_FAULT_EXECUTION_NOT_IMPLEMENTED` branch.

No files changed.

Tighten the three A3 witnesses

- :chatgpt-content-reference{index="0"}
- :chatgpt-content-reference{index="1"}

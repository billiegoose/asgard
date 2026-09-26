# Concrete RED2 thesis-audit follow-up: six-gap test plan

This plan follows `docs/handoffs/concrete-vs-thesis-audit.md`. It began as a six-item follow-up plan; all six items are now resolved or explicitly guarded. The former FLOAT capability divergence was closed by `RED2_FLOAT_V1`, the three missing architectural composition/invariant regressions have landed, the STRUCT reverse-direction transcription anomaly has an executable oracle guard, and bounded-domain rejection is now documented separately from RED2 semantic divergence.

## Priority summary

| # | Audit gap | Category | Action |
|---|---|---|---|
| 1 | FLOAT primitive / mixed INT+FLOAT behavior | resolved capability gap | `RED2_FLOAT_V1` + direct Abstract/Concrete lockstep regressions |
| 2 | gross-LIFO lifetime across nested real subgraphs | resolved test gap | `test_nested_subgraphs_restore_environment_frontiers_in_gross_lifo_order` |
| 3 | LAMBDA publication containing multiple nested APP/environment-sensitive descendants | resolved test gap | `test_join_publication_walks_lambda_with_multiple_nested_app_targets_before_reclaim` |
| 4 | combined STRUCT + recursive REC publication | resolved test gap | `test_join_publication_preserves_struct_field_referencing_recursive_rec_before_reclaim` |
| 5 | thesis STRUCT reverse `pc+1` anomaly | guarded oracle issue | reverse STRUCT regression asserts restored q/binder state and predecessor traversal |
| 6 | fixed-width rejection vs RED2 semantic mismatch | resolved classification/documentation gap | bounded refinements are named separately; FLOAT-result cases are no longer misclassified |

---

## 1. FLOAT/mixed-numeric gap — resolved

Chapter 4 requires floating ADD and implicit INT/FLOAT coercion. Concrete now implements those semantics over the explicit bounded `RED2_FLOAT_V1` profile documented in `concrete-float-divergence-note.md`. The profile uses binary64-shaped finite-normal values and deliberately follows the Pypeline floating-point contract rather than Python host-FPU edge behavior.

Executable guards in `tests/test_concrete_red2_primitives.py` now cover:

- FLOAT/FLOAT and INT/FLOAT ADD;
- mixed arithmetic and comparisons;
- fractional integer division producing FLOAT;
- negative integral `EXPT`;
- FLOAT unary operations defined by Abstract RED2;
- type-sensitive numeric equality;
- signed-64 overflow remaining a bounded-hardware fault.

`test_chapter4_float_add_and_mixed_coercion_gap_is_closed` specifically pins the original Chapter-4 witness. `test_red2_float_v1_common_case_primitives_match_abstract_exactly` broadens that to the supported common-case profile. Subnormals, Inf/NaN, strict IEEE rounding guarantees, and arbitrary fractional-exponent `EXPT` remain outside the hardware profile by design.
---

## 2. Gross-LIFO graph/environment lifetime across nested real subgraphs

### Purpose

The thesis's storage claim is global: graph memory grows upward, environment downward, and gross allocation/reclamation is last-allocated/first-released. Existing tests strongly cover individual allocation and JOIN reclamation, but not one compact end-to-end nested-subgraph invariant.

### Proposed location

`tests/test_concrete_red2_memory.py` or `tests/test_concrete_red2_closures.py` if existing subgraph fixtures are easier to reuse.

### Proposed test

`test_nested_subgraphs_restore_environment_frontiers_in_gross_lifo_order`

Construct two nested APP child entries with environment allocations at both depths:

```text
parent
  -> child A allocates environment region A
       -> child B allocates environment region B
       <- JOIN B
  <- JOIN A
```

Capture at each boundary:

- `fsp`
- logical `env`
- physical `free_space`
- `control_stack` / `c`
- exact interval allocated to A and B.

Assert:

1. B's physical region is below A's frontier and is reclaimed first;
2. B return restores A's logical `env` and physical `free_space` exactly;
3. A return then restores the parent frontier exactly;
4. control frames unwind in the same nesting order;
5. any surviving returned graph remains valid after poisoning/reusing each reclaimed interval;
6. no graph/environment collision occurs in the valid fixture.

This is a direct executable statement of the Chapter 4 gross-LIFO memory invariant.

---

## 3. Generic publication through LAMBDA + multiple nested APP targets

### Purpose

Existing publication tests cover closures, shared APP targets, UBV/EP, STRUCT, and REC separately. Add one test that forces `_task4_publication_clock` to exercise LAMBDA traversal plus several recursively referenced APP roots and an environment-sensitive descendant in one publication.

### Proposed location

`tests/test_concrete_red2_closures.py`

### Proposed test

`test_join_publication_walks_lambda_with_multiple_nested_app_targets_before_reclaim`

Fixture shape, conceptually:

```text
returned LAMBDA
  body APP -> target A
       APP -> target B
       ... head operator

A = nested APP -> stable graph value
B = EP -> child-environment-owned UBV or closure
```

Requirements:

- the returned root itself should remain or relocate according to the existing Concrete publication algorithm;
- at least one APP target remains graph-owned and unchanged;
- at least one descendant requires environment-sensitive preservation (EP->VAR or closure materialization);
- use repeated/shared target references if practical so memoization participates;
- after JOIN, poison/reuse the reclaimed child environment and verify decompiled/result semantics are unchanged;
- assert no surviving graph pointer falls in the reclaimed interval.

This test should exercise the existing **general** bounded publisher, not private helper calls in isolation.

---

## 4. Combined STRUCT + recursive REC publication

### Purpose

STRUCT publication and recursive REC/LETREC publication are each covered, but their interaction is not. This is important because a generic result-preservation engine must compose task families correctly rather than merely pass them individually.

### Proposed location

`tests/test_concrete_red2_recursive.py` or `tests/test_concrete_red2_structs.py`; prefer the file with the easiest existing JOIN-frame fixture.

### Proposed test

`test_join_publication_preserves_struct_field_referencing_recursive_rec_before_reclaim`

Conceptual returned graph:

```text
STRUCT/PAIR
  field 0 -> ordinary stable value
  field 1 -> EP -> REC in child environment
```

The REC should describe a small LETREC whose residual is easy to inspect, for example:

```text
LETREC ((x 7)) x
```

or a one-node self-recursive binding if the existing helper makes that simpler.

Assert after JOIN:

1. the STRUCT graph survives;
2. the recursive field is represented as a graph-owned LETREC residual, not an EP/REC pointer into reclaimed environment;
3. the other field is unchanged;
4. `free_space`/`env` restore to the saved frame;
5. reclaimed environment poisoning does not alter the returned STRUCT;
6. decompilation/source form before and after poisoning is identical;
7. publication scratch/memo sharing does not duplicate a recursive residual if the same REC is referenced twice (optional strengthening).

---

## 5. Guard the STRUCT reverse-direction thesis transcription anomaly

### Purpose

The transcription says reverse STRUCT restores q and performs `pc <- pc+1`, while every surrounding reverse rule and Concrete/Abstract behavior move toward lower addresses. This looks like a thesis/transcription typo, not a desired machine rule.

### Proposed location

`tests/test_concrete_red2_structs.py`

### Proposed test

`test_reverse_struct_restores_saved_quantum_and_moves_to_predecessor`

Set up a minimal reverse STRUCT transition with a saved-quantum control entry and assert exactly:

- q is restored from control;
- saved control entry is popped;
- direction remains backward;
- `pc` changes from N to `N-1`;
- all unrelated architectural state remains unchanged.

Add a comment citing the transcription location and explicitly recording that the test follows the coherent RED2 reverse-traversal invariant plus Abstract/Concrete agreement rather than the apparent `pc+1` typo.

This should be an **oracle guard**, not a claim that Concrete intentionally diverges from RED2.

---

## 6. Separate finite-domain rejection from semantic divergence

### Purpose

Concrete's bounded ABI rejects states/results outside its chosen hardware domain. Those failures should not be conflated with the FLOAT semantic gap.

### Proposed locations

- existing `tests/test_concrete_red2_memory.py`
- `tests/test_concrete_red2_primitives.py`
- optionally a small new `tests/test_concrete_red2_bounded_domain.py` if grouping improves clarity.

### Proposed table-driven contract

`test_bounded_domain_rejections_are_documented_refinements`

Representative bounded-domain categories are:

```text
address outside 16-bit graph domain        -> FAULT_INVALID_ADDRESS
first graph/environment collision          -> FAULT_GRAPH_ENV_COLLISION
control push past fixed capacity           -> FAULT_CONTROL_OVERFLOW
signed-64 ADD overflow                     -> FAULT_UNSUPPORTED_VALUE
unsupported FLOAT-profile edge value       -> FAULT_UNSUPPORTED_VALUE
```

Fractional integer DIV and negative integral EXPT are intentionally absent from this table: `RED2_FLOAT_V1` now supports them and returns FLOAT results.

For each case assert:

- exact typed fault;
- failure atomicity;
- a short case annotation classifying it as `bounded-domain refinement`, not Chapter-4 semantic disagreement.

Ordinary FLOAT/mixed numeric cases from item 1 are no longer a missing capability. Only values or operations outside the explicit `RED2_FLOAT_V1` hardware profile belong in the bounded-domain rejection category.

### Documentation guard

Update the Concrete README/test comment vocabulary to maintain this distinction:

```text
bounded-domain rejection != RED2 semantic divergence
```

The classification is now reflected in the Concrete README and primitive regressions.

---

## Completion record

The follow-up was landed in the following effective sequence:

1. direct FLOAT witnesses first documented the discrepancy, then were converted into positive lockstep tests when `RED2_FLOAT_V1` was implemented;
2. the STRUCT reverse-direction oracle guard landed;
3. nested gross-LIFO subgraph reclamation gained a direct invariant regression;
4. LAMBDA + nested APP publication composition gained a direct JOIN regression;
5. STRUCT + REC publication composition gained a direct JOIN regression;
6. bounded-domain terminology/tests were corrected so fractional DIV and negative integral EXPT are treated as supported FLOAT-result cases rather than finite-domain failures.

## Acceptance status

All six original observations now have explicit executable or documentation guards. The focused primitive/closure/STRUCT follow-up suite passes, and the remaining FLOAT limitations are deliberate `RED2_FLOAT_V1` profile boundaries rather than accidental missing Chapter-4 execution paths.

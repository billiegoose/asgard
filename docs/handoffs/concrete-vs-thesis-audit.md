# Concrete RED2 vs thesis audit

## Executive conclusion

The current `ConcreteRED2Machine` is **architecturally and semantically close to the Chapter 4 µRED design**, not merely inspired by it. Its core state model, dual-ended memory discipline, forward/reverse spine traversal, environment representation, beta reduction, strict primitive sequencing, lazy structures, and local-mutual-recursion machinery all track the dissertation closely.

The main differences fall into three categories:

1. **Implementation choices that preserve the thesis semantics:** fixed-width typed control entries, a separate physical environment-allocation frontier (`free_space`), explicit `EP` graph references, bounded iterative microcode, atomic shadow-state transitions, graph publication before JOIN reclamation, and quantum-recharge relinearization.
2. **Bounded-hardware adaptations:** 16-bit RAM addresses, 17-bit environment/frontier paths, fixed 32-bit counters/quantum, signed-64 integer scalars, explicit overflow/collision/fault states, bounded control/microcode storage, and cycle/hop detection.
3. **FLOAT gap resolved after the audit:** the audit originally found that Concrete faulted Chapter-4 floating arithmetic and mixed integer/float coercion. `RED2_FLOAT_V1` now closes that gap over an explicit finite-normal binary64 hardware profile aligned with Pypeline's existing floating operators; subnormals/Inf/NaN/strict IEEE rounding and arbitrary fractional-exponent EXPT remain outside the bounded hardware profile.

A key result for current architecture work is that **Concrete already contains a general bounded JOIN result-publication/preservation engine**. It is not limited to special-casing atomic APP results. Before restoring/reclaiming the child environment, it recursively walks surviving graph structure, repairs APP targets, preserves lambdas/RBLOCK/STRUCT graphs, resolves escaping `EP`s, materializes escaping closures, and reconstructs escaping recursive `REC` state into graph-owned LETREC residuals. That is directly analogous in purpose to the current Synth A2/A3 preservation work, although Concrete's implementation is richer and operates through fixed scratch arrays and an explicit iterative task stack.

The full Concrete RED2 test suite currently passes: **349 passed**.

---

## 1. Thesis machine state -> Concrete machine state

Chapter 4 replaces the SSM graph/reversal stacks with addressable memory and names the µRED registers explicitly. The thesis says that `pc` points at the current instruction, `fsp` points at the next free graph location, `env` points to the top redex-store entry, `s_d`/`s_a` are scratch registers, and µRED inherits `d`, `phi`, `q`, and control-stack pointer `c` from the SSM (`chapter4.tex` lines 676-685, source PDF p.61).

Concrete maps these almost literally in `ConcreteRED2Machine.__init__` (`machine.py` 221-238):

| Thesis µRED | Concrete | Notes |
|---|---|---|
| `pc` | `self.pc` | direct mapping |
| `fsp` | `self.fsp` | direct mapping |
| `env` | `self.env` | logical current environment path |
| `c` | `self.c` + `self.control_stack` | Concrete stores the top index as zero-based internally (`state.c - 1`) |
| `d` | `self.direction` | forward/reverse direction |
| `q` | `self.q` | semantic contraction budget |
| `phi` | `self.phi` | binder-depth counter |
| `s_a` | `self.s_a` | optional address scratch |
| `s_d` | `self.s_d` | optional data scratch |
| later thesis `argcnt` | `self.argcnt` | thesis introduces it for strict primitives at lines 1259-1266 |
| later thesis `prim` | `self.prim_id` | thesis lines 1272-1277 |
| later thesis `fire` | `self.fire` | thesis lines 1272-1277 |

Concrete additionally exposes `free_space`, `halted`, pending host-call state, and bounded non-architectural task microstate (`machine.py` 230-238, 272-397). `free_space` is best understood as making the thesis's physical environment allocation frontier explicit: `env` remains the logical path tip, while `free_space` is the actual upper-memory frontier after PNP/path restoration. That distinction is required once the shared environment is no longer treated as a simple contiguous current path.

The architectural checkpoint contains memory, control stack, `pc`, `fsp`, `env`, `c`, direction, `q`, `phi`, `free_space`, `argcnt`, primitive/fire state, scratch registers, halt state, and host suspension state (`machine.py` 399-420).

### Fixed-width ABI extensions

Concrete freezes a hardware ABI not specified by Chapter 4: 16-bit physical RAM-cell addresses, 17-bit environment/frontier paths (allowing one-past-end 65536), 32-bit quantum/counter/literal IDs, signed-64 integer payloads, binary64 float payloads, explicit direction/status/fault IDs, and typed fixed-width control entries (`README.md` 5-20). These are bounded-hardware adaptations, not thesis-level semantic changes.

---

## 2. Storage discipline: graph low/up, environment high/down, control separate

This is one of the strongest points of fidelity.

The thesis explicitly says that SSM `g`, `r`, and `rho` are replaced by one memory block split into graph memory at the lower end and the redex-store environment at the upper end; graph memory grows upward and the environment grows downward. It also stresses that neither is a true stack, but their **gross memory usage follows a last-allocated/first-released stack-like policy**, while the control stack is a separate smaller true stack (`chapter4.tex` 664-672, source PDF p.60).

Concrete follows exactly that topology:

- graph growth is through `red2_push_graph(memory, fsp, free_space, ...)` and increments `fsp`;
- environment allocation uses the high-memory frontier and decrements `free_space`;
- graph/environment collision is checked explicitly and faults atomically;
- control storage is a distinct `control_stack` with push/pop helpers and fixed capacity.

Tests cover the physical policy directly:

- `test_graph_push_matches_oracle_and_first_collision_is_atomic`
- `test_environment_allocations_match_oracle_layout`
- `test_environment_collision_has_no_partial_bridge_or_block`
- `test_environment_allocation_uses_physical_frontier_after_logical_path_restore`
- `test_environment_marker_matches_oracle_without_extra_bridge`
- `test_control_storage_fill_drain_and_fault_boundaries_match_oracle`
- `test_64k_one_past_end_frontier_allocates_last_ram_cell`

The important subtlety is that Concrete separates **logical environment path** (`env`) from **physical downward allocation frontier** (`free_space`). This is an implementation clarification of the thesis's shared inverted environment tree, not a change in ownership policy.

### Reclamation / LIFO assumptions

The thesis says environment extensions created during subgraph reduction may be discarded when the subgraph returns — “cutting back the environment” — and attributes this to APP (`chapter4.tex` 737-741). Concrete does this through saved subgraph frames. A reverse APP or equivalent child entry records the normalized environment/frontier, evaluates the child, then JOIN restores the frame after first preserving anything that would otherwise point into the reclaimed interval.

That publication-before-restore step is stricter than the dissertation pseudocode because Concrete must make explicit what is safe when an escaping result contains environment-relative state.

---

## 3. Traversal/reversal mechanics

The thesis's execution model states that every spine is represented by a contiguous instruction sequence; forward execution walks down a spine, reverse execution walks back up it (`chapter4.tex` 743-753, source PDF pp.63-64). Concrete retains this exact organization.

### APP

Thesis APP forward copies the APP and pushes the current `env` path; reverse APP cuts back/restores the environment, emits JOIN, jumps to the argument, and switches to forward traversal (`chapter4.tex` 765-810).

Concrete follows the same semantics, but wraps child evaluation in a typed subgraph frame and performs bounded preflight. `_task4_enter_subgraph` normalizes the environment with a PNP bridge if necessary, saves env/frontier/primitive/fire in `CONTROL_SUBGRAPH`, clears child primitive state, emits JOIN, resets `argcnt`, jumps to the child, and sets forward direction (`machine.py` 2017-2091).

### LAMBDA

Thesis LAMBDA contracts a beta redex only if applied and `q>0`; otherwise it copies itself and allocates a UBV. Beta contraction creates a closure and decrements q exactly once. Reverse LAMBDA decrements `phi` and moves backward (`chapter4.tex` 857-910).

Concrete does the same at `machine.py` 6476-6570. At q=0 / no usable argument it copies LAMBDA, sets `argcnt=0`, increments `phi`, allocates UBV, and advances. Otherwise it converts an APP/APP_VAR/EP argument into an environment binding/closure, decrements q, removes the consumed graph argument, decrements `argcnt`, and advances.

### UBV / VAR

Thesis UBV converts an environment UBV into a graph VAR with De Bruijn index `phi - stored_depth` and switches to reverse execution (`chapter4.tex` 924-938). Concrete `_execute_ubv` does exactly that (`machine.py` 7146-7163).

Thesis VAR invokes LOOKUP through the environment path (`chapter4.tex` 941-955). Concrete's VAR is bounded microcode beginning at `machine.py` 7165-7180`, with lookup code at 4016 onward. It follows PNPs and skips environment-object widths; Concrete extends the thesis's UBV/2-word-CLOSURE lookup by also skipping 3-word `REC` objects.

### CLOSURE

Thesis says a closure activation must not simply assign `env` to the captured path because that could destroy environment branches needed by pending arguments; it instead creates a PNP at the current environment tip (`chapter4.tex` 813-829). Concrete does the same conceptual operation via `_push_environment_marker` / task equivalent.

### JOIN

Thesis JOIN is simple: result root is `pc+1`; jump to parent; install that pointer in the parent APP; continue backward (`chapter4.tex` 832-847).

Concrete retains that semantic outcome, but its JOIN path is necessarily more elaborate because it has explicit bounded reclamation and environment-owned representations. See section 7 below.

### EP

`EP` is not a Chapter 4 graph instruction in the dissertation's basic µRED instruction set. Concrete uses it as an explicit graph-level environment-path indirection/lazy reference. It is therefore an **implementation representation extension**, not evidence of a changed source-language semantics. Concrete's VAR/APP_VAR/STRUCT/JOIN/equality machinery consistently knows how to chase or publish EP values.

---

## 4. Environment and redex-store representation

The thesis explains that µRED stores a single shared inverted redex-store tree. Each child points to its parent; the word after a node is its parent or a PNP to the parent; `env` points to the current path tip. UBV is one word, CLOSURE is two words, and PNP is one word (`chapter4.tex` 695-719, source PDF pp.61-63).

Concrete follows that model closely.

### Closure layout

Thesis closure:

1. `CLOSURE` word whose data points to the captured environment path;
2. following word whose data points to the code sequence (`chapter4.tex` 658-662, 715-717).

Concrete's publication/materialization code validates exactly that two-word representation (`machine.py` 2154-2188): CLOSURE holds captured environment; following `MOP_NONE` word holds code target.

### PNP and shared paths

Concrete inserts PNP bridges whenever the desired logical parent path is not physically adjacent to the current frontier (`machine.py` 2027-2054, 4473-4495). This is directly in the spirit of the thesis's inverted-tree path sharing.

### REC extension

For LETREC, Concrete stores each recursive binding as a 3-word `REC`:

1. `REC` -> binding expression root;
2. `MOP_NONE` -> recursive context;
3. `MOP_NONE` -> BLOCK/RBLOCK sequence.

This matches the Chapter 4 recursion algorithm, where RUP later fills context and block pointers (`chapter4.tex` 1598-1690).

---

## 5. Quantum semantics

Concrete preserves the thesis's core interpretation of q: **q counts semantic contractions, not processor clocks**.

Examples:

- beta LAMBDA decrements q once (`machine.py` 6567);
- scalar contraction decrements q once only when a result is produced (`machine.py` 841-850, 1047-1066);
- RECP indirection decrements once (`machine.py` 4648-4652, 4667-4676);
- selector/CONS transformations decrement once where they semantically contract (`machine.py` 6690-6693, 6783-6790, 6802-6806);
- structural equality may consume many hardware clocks but one semantic quantum; this is explicitly tested by `test_structural_equality_uses_more_clocks_but_same_semantic_quantum`.

The test suite verifies q=0 behavior across lambdas, primitives, structures, equality, recursion, selectors, host primitives, JOIN returns, and full programs.

### q=0 means reconstruct to a stable residual, not immediate stop

Concrete's scheduler status is RUNNING until the q=0 machine has finished reconstructing a stable residual and STOP executes. Only a halted machine with q=0 reports `STATUS_QUANTUM_EXHAUSTED` (`machine.py` 422-432). `test_live_q0_status_is_running_until_residual_halts` checks this directly.

That matches the RED2 idea: once semantic reduction budget is gone, the machine continues ordinary reconstruction until it reaches a representable residual boundary.

### Recharge

Recharge is an ABI/runtime extension beyond Chapter 4's raw instruction descriptions. A halted q=0 residual is relinearized into compact graph memory, garbage is omitted, sharing is preserved, STOP is appended, control/environment state is reset, and the same processor object resumes with a new quantum (`machine.py` 6237 onward).

Tests include:

- `test_repeated_recharge_matches_oracle_and_uninterrupted_result_without_reload`
- `test_recharge_preserves_diamond_sharing_and_omits_garbage_exactly`
- `test_recharge_relocates_rblock_without_relocating_integer_literal_exactly`
- `test_recharge_capacity_failure_is_transactional`
- program-level bounded-loop tests that preserve processor/memory/control identities.

This is best categorized as an **implementation/runtime mechanism preserving RED2 residual semantics**, not a thesis semantic fork.

---

## 6. Primitives, structures, equality

## Strict primitives

The thesis introduces `argcnt`, `prim`, and `fire`: the head primitive arms only when there are enough arguments and q>0; arguments are reduced one by one; APP saves prim/fire across child reduction and JOIN restores them (`chapter4.tex` 1236-1333).

Concrete follows this sequencing. `_primitive_countdown` decrements `fire` and dispatches when zero (`machine.py` 770-796); subgraph frames save primitive/fire state (`machine.py` 2055-2077); JOIN restores it and decrements after the child returns (`machine.py` 3742-3755).

Tests exercise:

- primitive arming and passive q=0 behavior;
- reverse-value countdown;
- primitive save/restore through JOIN;
- firing at countdown zero;
- q=0 return with deferred primitive suppressed;
- failure atomicity.

### Scalar arithmetic divergence

The thesis explicitly says its illustrative ADD pseudocode only shows integer addition, but **RED2 ADD also performs floating-point addition and implicit mixed integer/float coercion** (`chapter4.tex` 1356-1360, source PDF p.78).

The audit initially found this missing in Concrete. That gap has since been closed by `RED2_FLOAT_V1`: Concrete now executes ordinary finite binary64 arithmetic/comparison, mixed INT/FLOAT coercion, fractional integer division yielding FLOAT, and integral-exponent `EXPT` (including negative exponents) through a bit-level model of Pypeline's existing floating-point operators.

The resulting contract is intentionally a bounded hardware FLOAT profile rather than full IEEE-754. Subnormals, infinities, NaNs, exact IEEE rounding guarantees, and arbitrary fractional-exponent `EXPT` remain outside the supported domain. Signed-64 integer overflow remains a separate bounded-hardware restriction.

## Y

Concrete's Y implementation follows the thesis strategy closely: q=0/no argument is passive; otherwise `(Y f)` is transformed into `(f (Y f))`, with APP arguments followed directly and immediate operands temporarily copied as a head node using one scratch graph cell. This matches the thesis discussion at lines 1397-1457.

## STRUCT

The thesis represents a structure as an encoded lambda-like sequence `STRUCT : APP ... : VAR 0`. An unapplied STRUCT saves q, sets q=0 while traversing components, and restores q in reverse (`chapter4.tex` 1469-1517).

Concrete does this semantic shielding (`machine.py` 7023-7067), using typed `CONTROL_SAVED_QUANTUM` entries. Its selector/CONS support is more optimized than the dissertation's description of selectors as ordinary generated lambda expressions: Concrete recognizes selector tags/field offsets and can directly splice/copy selected structure fields (`machine.py` 6572 onward). This is an **implementation optimization intended to preserve the same structure semantics**.

One transcription oddity is worth flagging: the thesis STRUCT pseudocode says reverse traversal restores q then `pc <- pc+1` (`chapter4.tex` 1510-1516), even though reverse traversal elsewhere moves toward lower addresses. Concrete uses `pc -= 1` (`machine.py` 7023-7034). This looks much more like a thesis/transcription typo than a Concrete semantic deviation.

## Structural equality

Concrete contains a substantial bounded structural-equality engine (`machine.py` 4785-5756). It compares constants, lambdas, applications, structures, closures, variables, UBVs, and EP cases iteratively; it uses equality control frames, saved quantum, temporary graph tasks, and fixed scratch arrays. Compound equality can return true/false or a “stuck” residual when equality cannot safely be decided.

The important architectural property is that equality's internal traversal costs hardware clocks but does not spend q for each internal comparison. The semantic equality contraction is charged once (`machine.py` 5054-5119), with saved q restored around its internal work (`machine.py` 5025-5052). Dedicated equality tests cover nested sharing/closures, deep applications, q=0 residual exposure, q restoration/control balancing, and fixed scratch reuse.

Equality is therefore a later implementation elaboration of primitive semantics rather than a change to the q model.

---

## 7. JOIN preservation/publication: Concrete already has a general engine

This is the most important architectural finding for current Synth work.

The thesis's JOIN pseudocode assumes the reduced child graph can simply be referenced by its root (`chapter4.tex` 832-847). At the same time, APP is allowed to “cut back” environment extensions after a child returns (`chapter4.tex` 737-741, 771-801). In a concrete shared-memory implementation, those two facts create an escape problem: a child result may contain closures, environment references, recursive context pointers, or shared graph nodes whose meaning depends on storage about to be reclaimed.

Concrete solves this explicitly.

### Publication happens before environment restoration

JOIN finds the saved `CONTROL_SUBGRAPH` frame, records the child environment interval as `[current_frontier, frame_free_space)`, removes the frame, and **starts publication before restoring `free_space` or `env`** (`machine.py` 3811-3859). Only after publication and parent rewrite does `_task4_join_restore_and_commit` restore the parent environment/frontier (`machine.py` 3742-3755, 3992).

This ordering is exactly what a correct reclaiming implementation needs.

### General graph walker

`_task4_publication_clock` is a bounded iterative graph-preservation walker (`machine.py` 2699 onward). It is memoized and cycle-detecting and handles:

- `EP` environment references;
- contiguous APP spines and pointed subgraphs;
- LAMBDA bodies;
- RBLOCK/LETREC graphs;
- STRUCT descriptors/fields;
- recursive `REC` values;
- escaping closures through the materializer.

APP targets are recursively published and descriptors rewritten if the published root moves (`machine.py` 2766-2824). LAMBDA bodies are traversed (`2826-2850`). RBLOCK bindings and body are traversed (`2852-2917`). STRUCT APP/EP fields are walked and repaired (`2919-2959`).

### Closure materialization

When an escaping EP resolves to a closure whose captured environment would be reclaimed, Concrete materializes the closure's graph into graph-owned memory. The materializer understands APP, APP_VAR, LAMBDA, STRUCT, VAR lookup, EP chase, inline values, captured environments and binder depth (`machine.py` 2125-2695). Materialized APP offsets are relocated when written to graph memory (`machine.py` 3696-3737).

### Recursive context publication

`TASK4_PUB_REC` handles escaping recursive environments. It validates the 3-word REC, determines its recursive block/context, scans RBLOCKs, computes which recursive binding was selected, rewrites self-recursive references, publishes each binding graph, then emits a fresh graph-owned residual:

`RBLOCK* : RUP n : VAR selected`

(`machine.py` 2961-3177).

This is not a trivial special case. It is effectively a bounded LETREC residual reconstruction engine embedded in JOIN publication.

### Memoization / sharing

Root publication states cache published results, so repeated aliases share one published root rather than duplicating the graph. `test_join_shared_recursive_aliases_materialize_one_residual_root_exactly` verifies this for recursive aliases.

### Tests proving publication semantics

Direct tests include:

- `test_typed_join_publishes_atomic_ep_before_frontier_restore`
- `test_typed_join_materializes_escaping_closure_before_reclaim`
- `test_typed_join_publishes_shared_app_target_before_reclaim`
- `test_typed_join_publishes_ep_to_ubv_as_graph_var_before_reclaim`
- `test_repeated_fixed_live_closure_join_reuses_bounded_workspace`
- `test_typed_join_published_closure_has_no_pointer_into_reclaimed_child_region`
- `test_join_publishes_lazy_struct_ep_field_before_reclaim_and_reuse`
- `test_join_publishes_recursive_residual_before_reclaim_exactly`
- `test_join_self_recursive_binding_rewrites_rec_ep_to_letrec_var_exactly`
- `test_join_shared_recursive_aliases_materialize_one_residual_root_exactly`

These tests often poison the reclaimed environment after JOIN and assert the surviving graph is unchanged, directly proving that no published result still depends on reclaimed child storage.

### Bottom line

**Yes: Concrete already has a general graph-preservation/publication/materialization algorithm analogous to the current Synth A2/A3 objective.** It is broader than “replace one escaping pointer.” It recursively preserves the graph structure reachable from the child result and converts environment-owned state into graph-owned residual form before reclaiming the child's environment.

The qualification is that it is not a generic copying GC: graph nodes that are already safe remain in place, while only environment-sensitive references/materialized closures/recursive contexts are repaired or promoted.

---

## 8. Detailed RECP control-flow comparison

The Chapter 4 RECP rules are at `chapter4.tex` 1696-1792, source PDF pp.83-85. Concrete's implementation is at `machine.py` 4623-4783, entered through `_execute_recp` at 7198-7206.

### Entry and REC validation

`_execute_recp` decodes the environment REC address, starts Task 8 RECP microcode, records whether the graph RECP is a head node, and defers execution (`machine.py` 7198-7206).

`_task8_recp_clock` first validates the 3-word REC and extracts:

- binding-expression address;
- recursive-context address;
- RBLOCK block address.

### Forward, non-head RECP

Thesis: a non-head RECP copies itself to the result graph (`chapter4.tex` 1712-1716).

Concrete: if forward and `_task_rec_head` is false, it emits the same RECP pointing to the REC, advances pc, and commits without charging q (`machine.py` 4629-4641).

Covered by `test_non_head_recp_is_passive_without_quantum_charge`.

### Forward, head RECP with q>0

Thesis: follow the REC, restore the recursive binding's environment path using a PNP, execute the binding, decrement q (`chapter4.tex` 1717-1725).

Concrete: pushes an environment marker to `_task_rec_context`, sets pc to `_task_rec_binding`, decrements q, commits (`machine.py` 4648-4652).

This is directly equivalent to the thesis PNP operation.

A VAR landing on REC is tested by `test_head_var_landing_on_rec_enters_binding_and_charges_quantum`.

### Forward, head RECP with q=0

Thesis: call RECONSTRUCT to wrap the recursion variable back in a LETREC residual (`chapter4.tex` 1726-1728).

Concrete: initializes reconstruction scan state and switches to `TASK4_RECP_RECON_SCAN` (`machine.py` 4642-4647), then runs `_task8_reconstruct_clock`.

Reconstruction:

1. scans RBLOCKs from the REC's stored block address and verifies matching RUP count (`4679-4715`);
2. computes selected recursive variable as `(rec_address - context) / 3` (`4704-4712`);
3. inserts a PNP to the environment immediately before the REC group, `context + 3*n` (`4717-4723`), matching thesis line 1774;
4. allocates n UBVs, incrementing `phi` (`4725-4741`);
5. copies the RBLOCK instructions to result graph (`4743-4755`);
6. pushes the replacement environment path n times for later reverse RBLOCK traversal (`4757-4764`);
7. copies RUP and emits selected `VAR` as the new head (`4766-4779`);
8. switches to reverse traversal.

This tracks thesis RECONSTRUCT lines 1751-1792 very closely.

Covered by `test_head_recp_at_zero_quantum_reconstructs_letrec_wrapper_exactly`.

### Reverse RECP with q>0

Thesis: decrement q, read REC binding pointer, rewrite RECP to APP(binding), push the recursive context path (`chapter4.tex` 1730-1740).

Concrete: rewrites current RECP to APP(binding), pushes `_task_rec_context` on control, decrements q, commits (`machine.py` 4667-4676).

Covered by `test_reverse_recp_with_quantum_becomes_app_and_saves_context_path`.

### Reverse RECP with q=0

Thesis: place JOIN, save primitive firing registers, then RECONSTRUCT (`chapter4.tex` 1741-1747).

Concrete achieves this using the generic subgraph mechanism rather than hand-writing a special JOIN frame:

1. remembers the parent RECP address;
2. calls `_task4_enter_subgraph(self._task_env, parent_recp, parent_recp)` (`machine.py` 4654-4661);
3. this emits JOIN and saves env/frontier/prim/fire in a `CONTROL_SUBGRAPH` frame (`machine.py` 2017-2091);
4. reconstruction runs as above (`4662-4666`, `4678-4780`);
5. reverse traversal eventually executes that JOIN;
6. JOIN publishes the reconstructed result if necessary, rewrites parent `RECP` to `APP(published_result)` (`machine.py` 3908-3914), restores parent environment/frontier and primitive state, decrements fire appropriately, and continues (`3742-3755`).

That is operationally faithful to the thesis's “JOIN + save firing registers + RECONSTRUCT,” but implemented through the common child-call/return abstraction.

Tests are unusually strong here:

- `test_reverse_recp_at_zero_quantum_sets_up_join_and_reconstruction_exactly` checks the generated JOIN/residual/control state directly;
- `test_reverse_recp_zero_quantum_follows_oracle_through_join_return` runs eight committed steps in lockstep and confirms environment/frontier/control/prim/fire restoration;
- recursive publication tests then verify LETREC residuals survive child environment reclamation.

### RECP verdict

The current Concrete RECP path is one of the more thesis-faithful portions of the implementation. The most visible difference is factoring the reverse-q0 case through the generic typed subgraph/JOIN machinery rather than duplicating the dissertation's register-transfer sequence.

---

## 9. Bounds and faults versus thesis

Chapter 4 mostly describes an abstract machine implementation without committing to finite ABI widths or transactional fault semantics. Concrete adds them systematically.

Examples:

- finite physical graph/environment memory;
- finite control stack;
- fixed-width encoded addresses/counters;
- invalid-address checks;
- graph/environment collision faults;
- control overflow/underflow;
- illegal-state/transition faults;
- unsupported scalar-value faults;
- cycle/hop limits for graph/environment traversals;
- failure atomicity through a shadow copy of memory/control plus scratch microstate (`machine.py` 272-307, 2097-2123).

The default host `run_to_commit` bound even accounts for quadratic worst-case bounded materialization scans (`machine.py` 606-614).

These are **bounded-hardware adaptations**. They matter architecturally, but they do not alter RED2 behavior on states that fit the supported finite domain, except where finite scalar range / missing float arithmetic changes the language-level result into a fault.

---

## 10. Test coverage and gaps

The complete `tests/test_concrete_red2_*.py` suite currently reports:

> **349 passed in 71.87s**

Coverage is broad and unusually source-semantic rather than merely end-result based. Tests compare committed architectural checkpoints against the faithful Python RED2 implementation for individual transitions, recursive flows, structures, lazy primitives, equality, q exhaustion, and full programs.

Particularly strong direct coverage exists for:

- graph/environment/control allocation and collision boundaries;
- APP/LAMBDA/UBV/VAR transitions;
- closure path restoration and EP chasing;
- JOIN primitive save/restore and publication;
- q=0 reconstruction and repeated recharge;
- RBLOCK/RUP/RECP including reverse-q0 JOIN return;
- recursive residual publication and self-reference rewriting;
- STRUCT saved-q semantics and selector behavior;
- structural equality including deep iterative cases;
- program-level lockstep and host effects.

### Missing / weak direct thesis-conformance tests

Despite the breadth, several thesis-specific points could use explicit regression tests independent of the Python oracle:

1. **Float primitive divergence (resolved).** Explicit tests now demonstrate that Chapter-4 FLOAT ADD, mixed INT/FLOAT coercion, fractional integer division, comparisons, and negative integral EXPT execute in Concrete under `RED2_FLOAT_V1` rather than faulting.
2. **Gross-LIFO lifetime (resolved).** `test_nested_subgraphs_restore_environment_frontiers_in_gross_lifo_order` now checks nested real subgraph allocation/reclamation directly.
3. **LAMBDA + nested APP publication (resolved).** `test_join_publication_walks_lambda_with_multiple_nested_app_targets_before_reclaim` exercises the generic publisher across multiple graph targets and environment-sensitive state.
4. **STRUCT + recursive REC publication (resolved).** `test_join_publication_preserves_struct_field_referencing_recursive_rec_before_reclaim` checks the two publication branches in composition.
5. **STRUCT reverse transcription anomaly (guarded).** The reverse STRUCT regression follows coherent predecessor traversal and restored saved quantum/binder state rather than treating the apparent thesis `pc+1` as an oracle.
6. **Bounded-domain classification (resolved).** README/test vocabulary now separates finite hardware restrictions from semantic disagreement; fractional DIV and negative integral EXPT moved into the supported FLOAT-result domain.

---

## 11. Divergence classification

### Faithful to Chapter 4

- shared memory split: graph low/up, environment high/down;
- stack-like gross LIFO allocation/reclamation;
- separate true control stack;
- `pc`/`fsp` forward/reverse spine traversal;
- logical `env` path and inverted shared redex-store tree;
- UBV/CLOSURE/PNP representation and variable lookup;
- APP child traversal and JOIN return;
- beta LAMBDA semantics and q charging;
- UBV -> VAR reconstruction;
- strict primitive `argcnt` / `prim` / `fire` sequencing;
- Y behavior;
- STRUCT q shielding and restoration;
- RBLOCK/RUP/REC/RECP/RECONSTRUCT local mutual recursion;
- q=0 reconstruction to a stable residual before suspension.

### Implementation choices / refinements

- explicit `free_space` separate from logical `env`;
- typed control records instead of untyped data words;
- `CONTROL_SUBGRAPH` frames;
- explicit graph `EP` representation;
- fixed iterative task microcode and shadow architectural state;
- generic JOIN publication before reclaim;
- closure/recursive-context materialization into graph-owned residuals;
- optimized built-in structure selectors/CONS;
- equality task frames and bounded iterative structural-equality engine;
- post-halt residual relinearization during quantum recharge;
- host-call suspension/resume ABI.

### Bounded-hardware adaptations

- 16-bit RAM / 17-bit environment frontier;
- 32-bit q/counters/literal IDs;
- signed-64 integers / finite literal IDs;
- explicit collision, overflow, underflow, invalid-address and illegal-transition faults;
- bounded hop/cycle detection;
- bounded scratch and control storage;
- transaction/failure atomicity.

### Material semantic/capability divergence

- No ordinary Chapter-4 FLOAT/mixed-numeric gap remains inside `RED2_FLOAT_V1`'s supported finite-normal domain.
- The bounded hardware profile excludes subnormals, Inf/NaN, strict IEEE rounding behavior, and arbitrary fractional-exponent `EXPT`; these are explicit profile limitations rather than accidental missing execution paths.
- Finite signed-64 integer arithmetic introduces overflow/unsupported-result faults where the dissertation does not impose that numeric bound.

Everything else inspected is better described as an implementation refinement or finite-hardware restriction than as a changed RED2 reduction semantics.

---

## Final assessment

For current architecture work, the safest summary is:

**Concrete is already a serious bounded implementation of the dissertation's µRED machine, not a loose approximation.** The low/up graph + high/down environment discipline, explicit reversal, redex-store path sharing, q semantics, lazy reconstruction, and recursive-context machinery are all recognizably the Chapter 4 design.

The biggest architectural enhancement beyond the thesis pseudocode is its **general JOIN publication layer**, which makes the thesis's environment-cutback discipline safe in a finite shared-memory implementation by ensuring that a returned graph owns everything it needs before the child environment is reclaimed. Current Synth preservation work should treat this Concrete algorithm as the semantic reference architecture unless there is a deliberate reason to narrow it.

The former native FLOAT arithmetic/coercion gap is now closed inside `RED2_FLOAT_V1`'s explicitly supported finite-normal domain. The remaining numeric differences are deliberate bounded-profile limits—subnormals, Inf/NaN, strict IEEE rounding guarantees, arbitrary fractional-exponent `EXPT`, and finite signed-64 integer range—not an unimplemented ordinary Chapter-4 FLOAT execution path.

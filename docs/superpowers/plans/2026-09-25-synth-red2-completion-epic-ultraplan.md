# Ultraplan Epic: Complete Synthesizable RED2 Semantics and Same-Machine Host Resume

> Poor Girl's Codex execution: `/skill:ultrapowers docs/superpowers/plans/2026-09-25-synth-red2-completion-epic-ultraplan.md`. This is a planning deliverable, not an execution launch. The epic is intentionally split into two major projects: first eliminate the remaining pure-RED2 semantic gaps with a generic transactional graph publication/relinearization engine; then complete scheduler-visible host suspension/resume so CLOCK and UART effects can run repeatedly on the same live Synthesizable RED2 machine.

**Grammar:** claims-v1

**Epic Claim:** complete the remaining Synthesizable RED2 execution surface by (A) replacing specialized graph-shape fallthroughs with a bounded generic publication/relinearization engine faithful to `ConcreteRED2Machine`, and (B) implementing exact same-machine host-call resume for CLOCK, UART-RX, UART-TX and UART-TX-BYTES, including repeated I/O programs, invalid-resume atomicity, and quantum-boundary interaction. (elicited)

**Goal:** reach a defensible boundary where `RED2_SYNTH_SEMANTICS_COMPLETE` may become `1` because every accepted pure RED2 value/control shape is either implemented or rejected with the same typed RED2 fault as the Concrete oracle, quantum exhaustion/recharge preserves one live machine, and host effects suspend/resume exactly once without a Python reducer taking over continuation execution.

**Tech Stack:** Python 3.14+, Pypeline/PipelineC, uv, pytest, xdist, existing native `sim_call` harness, Concrete/Abstract RED2 oracles, pinned PipelineC revision `171c52b3f1411f632a07ccfc3dbfb177efa901cd`.

**Primary implementation files:**
- `src/machines/synthesizable_red2_machine/machine.py`
- `src/machines/concrete_red2_machine/machine.py` only when an oracle bug or missing explicit contract is proven
- `src/machines/concrete_red2_machine/abi.py` only for genuinely missing finite host/publication ABI data
- `src/machines/concrete_red2_machine/pipelinec_vectors.py`
- `src/machines/concrete_red2_machine/oracle.py`
- `scripts/check_syn_sim.py`
- `scripts/check_syn.py`
- focused tests under `tests/`

**Baseline already proven before this epic:**
- `examples/fibonacci.thor` executes entirely on Synthesizable RED2 and prints `8`.
- Fibonacci Concrete↔Synth lockstep matches all 224 committed transitions.
- full Asgard suite: 1185 passed.
- focused non-stress suite: 1179 passed.
- real PipelineC frontend + HDL emission passed at the pinned revision.
- emitted Synth top was approximately 50.6 MB VHDL.
- full native first-slice parity passed.
- `RED2_SYNTH_SEMANTICS_COMPLETE = 0` remains intentionally withheld.

**Validation cadence:**
- Inner loop: minimized witness + focused native lockstep/parity + static PipelineC shape test.
- Frontend-shape milestone: direct `PY_TO_LOGIC.PARSE_FILE` / supported equivalent only when useful; current parse/elaboration cost is roughly tens of seconds.
- Project milestone: `mise run test-fast`, focused native program lockstep, `git diff --check`.
- Epic milestone/final: full `mise test`, full `scripts/check_syn_sim.py`, exact `scripts/check_syn.py --frontend-only`, direct I/O program exams, and final semantic-gap inventory.
- Do not run the ~15-minute HDL-emission gate after every small edit.

**Parallelization rationale:** Project A is mostly serialized because each later publication case depends on one shared bounded walker contract and failure-atomic transaction model. Within Project A, witness construction and review can fan out by opcode family once the walker ABI is frozen. Project B begins only after Project A provides a generic publication/relinearization substrate, because quantum recharge and resumed host values must publish/relinearize through the same machine without bespoke host-only graph logic. Host-call test construction can proceed in parallel with the final Project-A audit, but host-resume implementation must consume the accepted publication interface.

**Poor Girl's Codex delegation policy:** Execute this epic through Poor Girl's Codex. Any delegated implementation, investigation, peer review, or adversarial review must use the `chatgpt-web` `subagent {name,prompt}` tool. The parent session owns integration, conflict resolution, gates, and final acceptance. Give every delegate a self-contained prompt with exact files, current semantic boundary, oracle, proof obligations, and forbidden shortcuts.

---

## Epic architecture

```text
                        THOR / RED2 compiler
                               |
                               v
                    +-----------------------+
                    | loaded RED2 graph     |
                    +-----------+-----------+
                                |
                                v
              +---------------------------------------+
              |   Synthesizable RED2 persistent core |
              |                                       |
              | FETCH / EXECUTE / COMMIT              |
              | graph + env RAM                       |
              | control RAM                           |
              | q / phi / prim / fire / pc / fsp    |
              |                                       |
              |  Project A                            |
              |  generic transactional publication   |
              |  + materialization/relinearization   |
              +------------------+--------------------+
                                 |
                                 v
                       stable architectural state
                                 |
                  +--------------+--------------+
                  |                             |
                  v                             v
          normal RED2 execution        host primitive fires
                                                |
                                                v
                                     STATUS_HOST_CALL
                                                |
                                                | finite host ABI
                                                v
                                         external service
                                                |
                                                v
                                   RESUME_HOST_CALL(value)
                                                |
                                                v
                              Project B same-machine resume
                                                |
                                                v
                                  same graph / same processor
```

The physical transport used later to carry `HOST_CALL` and `RESUME_HOST_CALL` is not part of this epic. UART here means the RED2 semantic primitives `UART-RX`, `UART-TX`, and `UART-TX-BYTES`; it does **not** imply that the host-control transport itself must be UART.

---

## Semantic authority and non-negotiable boundaries

1. `ConcreteRED2Machine` is the immediate architectural oracle for Synth committed transitions. Abstract RED2 remains the semantic authority above it.
2. Do not special-case source programs, Fibonacci, particular graph addresses, or literal IDs.
3. `q` is a semantic contraction budget, not a hardware clock counter.
4. Publication/relinearization must be bounded hardware work over fixed memories and finite explicit stacks; no Python recursion or dynamic containers in the Synth path.
5. Failure atomicity is mandatory. A fault discovered during publication, materialization, resume validation, or capacity checking must not leave partially published architectural state.
6. Shared graph identity/rewrites, environment paths, EP chasing, closure capture, REC/RBLOCK rewriting and head bits must follow the Concrete oracle exactly.
7. A host effect traps only when the RED2 primitive actually fires with positive q. Traversal toward the primitive is not a host effect.
8. While `STATUS_HOST_CALL` is pending, additional processor clocks must not mutate architectural state or replay the effect.
9. Host service returns a finite encoded machine value. The host does not evaluate RED2 continuations, perform IO-BIND/IO-THEN sequencing, or reduce the graph.
10. Resume consumes the pending call exactly once, writes/publishes the returned atomic value at the oracle-defined location, decrements q exactly once, clears the pending host state, and continues the same loaded machine.
11. `RED2_SYNTH_SEMANTICS_COMPLETE` stays `0` throughout implementation and flips only in the final epic gate if every required proof below is green.
12. Do not edit archived/thesis historical material to make the implementation easier.

---

# Project A — Generic Transactional Graph Publication and Pure-Semantics Closure

## Project A outcome

Replace the current collection of bounded special-case publication paths with a common finite state-machine substrate capable of publishing/relinearizing every graph shape accepted by Concrete RED2. Specialized fast paths may remain when useful, but they must delegate to or be semantically equivalent to the same generic contract. By the end of Project A there must be no reachable pure-RED2 path that reports `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` merely because the returned graph has a previously unsupported shape.

**Interface produced:** `RED2_PUBLISH_COMPLETE_V1`

Conceptual contract:

```text
PUB_GRAPH(root, interval, phi, env, free_space, fsp)
  -> success(new_root, graph writes, new fsp)
  -> typed RED2 fault

Properties:
- bounded
- transactional
- sharing-aware
- cycle/recursion-safe under RED2's finite representation rules
- exact Concrete ordering/fault precedence
- usable by JOIN, STRUCT selector promotion, closure/REC publication,
  q-recharge residual relinearization, equality child construction,
  and later host resume when publication is required
```

### Task A1: Freeze the remaining pure-semantic gap inventory

**Type:** investigation + tests
**Review:** peer

**Claim:** every current `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` site is classified as one of: pure semantic gap, host-resume gap, defensive unreachable invariant, or intentional typed unsupported-value boundary. No site remains ambiguous. (derived)

**Work:**
- enumerate every `hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED` site in `machine.py`;
- associate each with its Concrete transition/task equivalent;
- create a machine-readable or test-visible inventory grouped by semantic family;
- minimize one Concrete↔Synth witness for each reachable pure-semantic family before changing implementation;
- explicitly distinguish `FAULT_UNSUPPORTED_VALUE`, `FAULT_ILLEGAL_TRANSITION`, `FAULT_INVALID_ADDRESS`, and actual missing Synth semantics.

**Required families to classify:**
- generic JOIN publication parent/result combinations;
- APP prefixes with arbitrary target multiplicity;
- EP terminal publication including CLOSURE and REC;
- closure materialization with general body/environment graph shapes;
- REC/RBLOCK composite bindings/bodies;
- STRUCT publication and selector promotion of nested graphs;
- selected IF results beyond the current APP/EP-only live-q shape;
- terminal VAR/APP_VAR binding classes;
- equality child/result publication escape hatches;
- lambda beta result cloning/materialization escape hatches;
- primitive/scalar metadata catch-alls;
- defensive impossible-state guards.

**Proof:** focused tests must demonstrate that every newly added witness matches Concrete up to the exact first unsupported Synth microstate.

**Acceptance:** a reviewer can answer “what semantic behavior is still missing?” from the inventory without reading 11k lines of hardware source.

---

### Task A2: Define the bounded generic publication-machine state

**Type:** design + implementation
**Review:** adversarial

**Claim:** Synth can represent the Concrete generic publication/materialization algorithm with finite explicit task state and bounded RAM/register resources, without whole-memory Python-style shadow copies. (derived)

**Oracle anchors:** Concrete `TASK4_PUB_*`, `TASK4_MAT_*`, REC rewrite states, and `_task10_relinearize_clock`.

**Design requirements:**
- explicit finite work-stack entry type: task kind plus fixed-width fields;
- visited/root memo state sufficient for shared graph roots and recursive records;
- materialization scratch RAM separate from architectural graph RAM where needed;
- root-result cache for repeated/shared publication;
- exact EP hop bound and cycle detection behavior;
- exact head-bit and definition metadata preservation;
- capacity checks before first architectural write when the Concrete transition is transactional;
- a commit protocol that publishes all validated writes atomically at RED2 commit boundaries;
- no dependence on source-language ASTs or Python objects.

**Important design choice:** do not mechanically port Concrete's full shadow-memory implementation if that would imply duplicating the entire graph RAM in hardware. Derive the smallest hardware transaction mechanism that preserves the same externally visible atomicity—for example preflight + deterministic replay/write, bounded write journal, or a combination—then prove it against Concrete.

**Proof legs:**
1. malformed/capacity-failing cases leave architectural memory/control/register state unchanged;
2. shared roots publish once and every descriptor observes the same relocated result;
3. maximum-depth bounded cases terminate with the same typed fault as Concrete rather than hanging.

**Produces:** internal generic walker ABI used by all later A tasks.

---

### Task A3: Implement generic APP/LAMBDA/EP publication

**Type:** implementation
**Review:** peer

**Claim:** arbitrary accepted APP-prefix graphs, lambda bodies, and EP chains publish through the generic walker, including more than two distinct APP targets and nested operator graphs. (derived)

**Must cover:**
- APP prefixes of unbounded-in-source but bounded-in-memory length;
- 1, 2, 3+ distinct APP targets;
- APP_VAR transparent prefix entries;
- nested APP operators/results;
- lambda chains and general lambda body graphs;
- EP chains to shareable atomics, UBV, CLOSURE and REC;
- outside-publication-interval EP behavior;
- sharing and repeated references;
- failure atomicity when a late target is invalid or cannot fit.

**Regression rule:** every current specialized APP/EP path may stay as an optimization only if generic-path differential tests prove equivalent results and fault precedence.

**Acceptance:** remove or make unreachable the current “third target needs generic publication stack,” “nested target needs generic walker,” and equivalent APP/EP `EXECUTION_NOT_IMPLEMENTED` branches.

---

### Task A4: Generalize CLOSURE materialization/publication

**Type:** implementation
**Review:** adversarial

**Claim:** a closure can be published regardless of the accepted RED2 graph shape of its lambda body and captured environment, subject only to the same bounded-memory/fault rules as Concrete. (derived)

**Must cover:**
- captured atomics;
- captured UBV/VAR-derived values;
- nested closures;
- captured APP/LAMBDA/RBLOCK/STRUCT graphs;
- shared captured subgraphs;
- closure body with more than the current narrow head-VAR pattern;
- relocation of APP descriptors after materialization;
- exact environment/depth semantics used by Concrete materialization;
- duplicate closure publication reuses the same materialized result where Concrete does.

**Proof:** generate small closure-shape matrices from the Concrete oracle and compare exact published graph bytes/words, fsp/free-space, pc/env/phi, and faults.

**Acceptance:** current closure-specific `EXECUTION_NOT_IMPLEMENTED` branches become either implemented generic cases or proven unreachable malformed-state guards returning the oracle's typed RED2 fault.

---

### Task A5: Generalize REC/RBLOCK publication and recursive rewriting

**Type:** implementation
**Review:** adversarial

**Claim:** recursive records and RBLOCK values may contain any Concrete-accepted composite binding/body graph and still publish with correct recursive-variable rewriting and sharing. (derived)

**Must cover:**
- composite RBLOCK bindings: APP, LAMBDA, RBLOCK, STRUCT;
- composite RBLOCK body;
- REC publication reached directly or through EP;
- selected recursive binding reconstruction;
- recursive references rewritten with correct depth/context;
- nested recursive records;
- shared recursive binding roots;
- recursion/cycle detection identical to Concrete;
- graph collision and control overflow before partial architectural publication.

**Proof:** build minimal recursive witnesses escalating from one composite binding to mutually recursive/nested composite values; compare complete committed graph image against Concrete.

**Acceptance:** Fibonacci remains green, and the broader REC/RBLOCK publication branches no longer rely on shape-specific `EXECUTION_NOT_IMPLEMENTED` exits.

---

### Task A6: Replace STRUCT/selector promotion special cases with generic publication

**Type:** implementation
**Review:** adversarial

**Claim:** STRUCT publication and selector result promotion accept the same nested value shapes as Concrete, including closures, REC, nested APP/STRUCT/RBLOCK graphs and EP-returned selector operands. (derived)

**Must cover:**
- generic traversal of STRUCT descriptor fields;
- APP and EP fields whose targets require allocation/publication;
- CLOSURE/REC fields;
- selector firing on an operand returned through EP;
- selector result promotion for atomic and arbitrary composite results;
- overlapping source/destination relocation;
- transactional preflight before descriptor mutation;
- tag mismatch/passive semantics;
- q==0 behavior and saved-q restoration exactly as Concrete.

**Acceptance:** remove the current comments/branches saying “generic walker later” for STRUCT and selector promotion.

---

### Task A7: Close IF, lookup, lambda and equality publication escape hatches

**Type:** implementation + semantic audit
**Review:** peer

**Claim:** the non-publication front ends that feed the generic walker no longer reject valid Concrete values merely because they fall outside Fibonacci's narrow shapes. (derived)

**Subtasks:**
- **IF:** support every Concrete-valid selected branch result, not only APP/EP when q>0; reproduce Concrete behavior for non-boolean conditions rather than inventing one.
- **VAR/APP_VAR:** enumerate every valid terminal binding class and route publication/reconstruction through the generic walker when needed.
- **LAMBDA beta:** route arbitrary accepted result graphs through clone/materialize/publication rather than a catch-all hardware fault.
- **Equality:** eliminate `eqc_result_unsupported` for every Concrete-supported structural combination; use generic child/result publication where construction is required.
- **Primitive metadata:** any valid Concrete primitive role/op must execute or produce the same typed RED2 fault; unknown malformed metadata must not masquerade as missing hardware semantics.

**Proof:** one minimized witness per formerly unsupported branch plus cross-product/property-style tables where practical.

---

### Task A8: Make quantum recharge use the generic relinearization substrate

**Type:** implementation
**Review:** adversarial

**Claim:** `CMD_RECHARGE` on a halted q=0 residual resumes the same loaded Synth machine using the same generic materialization/relinearization semantics as Concrete; it is not merely `q = command.value`. (derived)

**Context:** this task belongs in Project A because Concrete recharge materializes/relinearizes the stable residual graph before execution resumes, and Project B's repeated I/O programs must be able to cross quantum boundaries without reload.

**Must cover:**
- non-halted q==0 refill when the oracle permits it;
- halted stable residual relinearization;
- same machine RAM/control objects remain live;
- no recompilation/reload;
- repeated exhaustion/recharge;
- complex residuals containing closures, recursion, structures and shared graphs;
- invalid recharge state/value produces `FAULT_INVALID_RESUME` atomically.

**Acceptance:** a long-running pure recursive program can repeatedly exhaust and recharge Synth and reach the same final graph/result as one sufficiently large-quantum run.

---

### Task A9: Pure-semantics exhaustiveness gate

**Type:** verification / write-nothing unless a defect is found
**Review:** adversarial

**Claim:** no reachable pure RED2 execution path remains gated by `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`. (derived)

**Required checks:**
- rerun the Task-A1 inventory against current source;
- every remaining `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` site must be host-resume-only or a mechanically proven unreachable internal invariant;
- prefer replacing unreachable “not implemented” guards with the correct typed RED2 invariant fault if Concrete defines one;
- run minimized witness corpus across every accepted opcode/value family;
- run q=0/recharge corpus;
- run Fibonacci and richer closure/recursive/structure/equality programs through committed-state lockstep;
- run `mise run test-fast`;
- run full native parity before Project B integration.

**Produces:** `RED2_PURE_COMPLETE_V1`, consumed by Project B.

---

# Project B — Same-Machine Host Suspension/Resume and Useful UART I/O

## Project B outcome

A Synthesizable RED2 program may repeatedly execute semantic host effects, suspend at the exact primitive firing boundary, let an external service provide the result/effect acknowledgement, and resume the **same** machine exactly once. This includes CLOCK, UART-RX, UART-TX and UART-TX-BYTES and must support real multi-effect programs such as loops that receive bytes, transform state recursively, transmit output, cross quantum boundaries, and continue without reloading the program.

**Interface produced:** `RED2_HOSTCALL_COMPLETE_V1`

Transport-independent logical ABI:

```text
RUN/CLOCK...
  -> STATUS_HOST_CALL
     pending_host_op
     pending_host_argument

host service performs exactly one external effect

CMD_RESUME(encoded_atomic_result)
  -> validate pending state + result
  -> publish/replace result at oracle-defined location
  -> q -= 1 exactly once
  -> clear pending_host_op/argument
  -> continue same graph/machine
```

Semantic host operation classes from the Concrete oracle:

```text
DIRECT RESULT HOST CALLS
  CLOCK
  UART-RX
  pending_host_argument == 0
  resume result appended at fsp+1
  argcnt += 1
  q -= 1
  direction := reverse
  pc := fsp - 1 after append

STRICT-ARGUMENT HOST CALLS
  UART-TX
  UART-TX-BYTES
  pending_host_argument encodes current argument/result address
  resume replaces memory[pc] with returned atomic value
  fsp := pc
  q -= 1
  pc -= 1
```

The returned value remains restricted to a valid atomic RED2 word unless the semantic oracle is explicitly changed in a separate design decision.

---

### Task B1: Freeze the host-call/resume ABI and exact fault precedence

**Type:** design + tests
**Review:** adversarial

**Claim:** Synth has an explicit finite contract for pending host calls, resume values, status transitions and invalid-resume faults identical to Concrete. (derived)

**Must specify/test:**
- exact valid host op set: CLOCK, UART-RX, UART-TX, UART-TX-BYTES;
- pending argument encoding: zero for direct calls, optional graph address for strict calls;
- resume accepted only while pending, at the stable fetch/suspend boundary, not halted, with q>0;
- encoded result must be valid atomic INT/FLOAT/CHAR/SYM according to Concrete restrictions;
- reserved bits, closure-slot and definition metadata validation;
- strict pending argument must identify the current pc/address as Concrete requires;
- invalid command/result/state produces `FAULT_INVALID_RESUME` with zero partial graph/control/register mutation;
- clocks while pending are stable and do not create duplicate effects;
- resume cannot be replayed after success.

**Acceptance:** the ABI can be implemented by UART/JTAG/USB/other transport later without changing RED2 semantics.

---

### Task B2: Implement direct host-call resume for CLOCK and UART-RX

**Type:** implementation
**Review:** peer

**Claim:** CLOCK and UART-RX suspend and resume exactly like Concrete, including graph publication, q consumption and direction/argcnt changes. (derived)

**Required behavior:**
1. primitive fires only with positive q and correct primitive/argcnt shape;
2. set pending op, leave argument zero, expose `STATUS_HOST_CALL`;
3. repeated `CMD_CLOCK` while pending changes nothing;
4. `CMD_RESUME(value)` preflights destination `fsp+1` against free-space/memory;
5. write a normalized head atomic result;
6. update fsp, argcnt, q, pc and direction exactly as Concrete;
7. clear pending state only after successful commit;
8. invalid result or collision leaves the suspended state transactionally intact except for the oracle-defined fault state.

**Program exams:**
- `(CLOCK)`
- `(UART-RX)`
- `IO-BIND` using the returned value
- repeated receive loop with recursive state
- receive + arithmetic + transmit chain after later B tasks.

---

### Task B3: Implement strict host-call suspension/resume for UART-TX

**Type:** implementation
**Review:** adversarial

**Claim:** `UART-TX` first reduces its argument completely, traps exactly once at primitive firing, then resumes by replacing the strict argument/result slot exactly as Concrete does. (derived)

**Must prove:**
- no HOST_CALL occurs before strict argument reduction;
- pending argument encodes the exact graph address;
- q==0 suppresses the contraction rather than emitting output;
- the host sees exactly one byte/value effect per RED2 firing;
- clocks while pending do not replay output;
- resume result replaces `memory[pc]`, sets `fsp=pc`, decrements q, decrements pc and clears pending state;
- malformed pending address or stale pc produces atomic invalid-resume fault;
- IO-THEN/IO-BIND continuation is reduced by RED2 after resume, not by the host.

**Program exams:**
- `(UART-TX 65)`
- `(UART-TX (+ 64 1))`
- `(IO-THEN (UART-TX 46) (IO-RETURN 7))`
- recursive loop transmitting a fixed punctuation byte many times.

---

### Task B4: Implement UART-TX-BYTES semantics

**Type:** implementation
**Review:** adversarial

**Claim:** `UART-TX-BYTES` follows the same strict host trap/resume semantics as Concrete for its RED2-level argument and can participate in repeated same-machine I/O sequencing. (derived)

**Important boundary:** this task implements the **semantic host primitive**, not a physical bulk-transfer DMA engine. The external host service may interpret the referenced/encoded argument according to the existing runtime contract; it must not evaluate RED2 graph continuations.

**Must cover:**
- argument reduction and pending-address semantics;
- exact effect count/order;
- empty and representative non-empty byte sequences supported by the existing oracle/runtime;
- invalid argument/value faults;
- q==0 suppression;
- resume exactly once;
- repeated TX-BYTES calls in one live machine.

---

### Task B5: Integrate IO-BIND, IO-THEN and IO-RETURN across real host suspensions

**Type:** implementation + program lockstep
**Review:** adversarial

**Claim:** RED2's own I/O combinators continue to own sequencing around host effects; the external host only services primitive requests/results. (derived)

**Program ladder:**

```thor
(CLOCK)

(IO-BIND (CLOCK)
  (LAMBDA (now) (IO-RETURN now)))

(IO-THEN
  (UART-TX 65)
  (IO-RETURN 7))

(IO-BIND (UART-RX)
  (LAMBDA (ch)
    (IO-THEN
      (UART-TX ch)
      (IO-RETURN ch))))
```

Then add a recursive loop that:
- receives bytes repeatedly;
- maintains changing recursive state;
- conditionally transmits bytes;
- returns a final value;
- never reloads the RED2 machine.

**Proof:** compare ordered effect trace, pending op/argument, q, pc/fsp/env/phi/argcnt, graph writes and final result at every committed transition/suspension/resume boundary.

---

### Task B6: Cross quantum exhaustion/recharge with pending and repeated I/O

**Type:** integration
**Review:** adversarial

**Claim:** long-running I/O programs can cross q boundaries without duplicate/lost effects and without violating the rule that host resume requires positive q. (derived)

**Cases:**
- q exhausts before a host primitive fires: no effect occurs; residual stabilizes, host recharges, same machine continues, effect later fires once;
- host call is already pending: recharge is rejected exactly as Concrete specifies;
- resume consumes the last unit of q: returned result commits once, subsequent execution reaches the normal q=0 stable boundary;
- repeated receive/transmit loop with deliberately tiny recharge quanta;
- q=0 around IO-BIND/IO-THEN reconstruction;
- invalid ordering: resume with no pending call, recharge while pending, second resume after successful resume.

**Acceptance:** effect sequence and count are invariant between one large-quantum run and many small recharge windows.

---

### Task B7: Extend the program-level Concrete↔Synth harness to host service steps

**Type:** test infrastructure
**Review:** peer

**Claim:** the existing committed-state lockstep runner can automatically service deterministic host calls and continue comparison across suspend/resume boundaries. (derived)

**Harness contract:**
- compiled image loaded once into Concrete and Synth;
- deterministic host-service callback keyed by op + argument;
- compare architectural state at:
  - ordinary committed transition,
  - first `STATUS_HOST_CALL`,
  - stable pending clocks,
  - successful resume commit,
  - quantum exhaustion,
  - recharge completion,
  - final completion/fault;
- compare ordered host-effect trace exactly;
- report first divergence with op, argument, returned word, q, pc/fsp, pending fields and relevant graph diff.

**Required deterministic services:**
- CLOCK sequence;
- UART-RX byte/input sequence;
- UART-TX output collector;
- UART-TX-BYTES output collector.

**Acceptance:** the harness can run the mixed receive/compute/transmit loop without manual intervention.

---

### Task B8: UART-oriented end-to-end semantic exams

**Type:** program exams
**Review:** peer

**Claim:** Synthesizable RED2 now supports I/O workloads interesting enough to justify a later physical transport shell. (elicited)

**Required workloads:**
1. **Echo:** repeatedly UART-RX then UART-TX the received value.
2. **Transform:** receive byte, perform RED2 arithmetic/branching, transmit transformed byte.
3. **Stateful loop:** recursive loop with accumulator/state changed by input and output each iteration.
4. **Clock + UART:** CLOCK result influences transmitted output.
5. **Bulk output:** at least one UART-TX-BYTES workload.
6. **Tiny quantum:** one of the above under repeated exhaustion/recharge.
7. **Error cases:** invalid resume word, wrong pending argument/state, graph collision on direct resume, and replay attempt.

**For each:** compare THOR/Abstract/Concrete/Synth where applicable, exact ordered host effects, final RED2 result, and complete committed-state lockstep around every effect.

---

### Task B9: Real PipelineC/frontend regression after host resume

**Type:** hardware gate
**Review:** peer

**Claim:** the complete host-resume state machine remains accepted by the pinned real PipelineC/Pypeline frontend and emits the Synthesizable RED2 top. (derived)

**Required sequence:**
1. static PipelineC-shape tests;
2. focused native host-call parity;
3. `mise run test-fast`;
4. direct PipelineC parse/elaboration sanity if needed;
5. exact `scripts/check_syn.py --frontend-only` once at the milestone;
6. inspect emitted top existence and native parity output.

Do not weaken the hardware gate to a parser-only check. The expensive full emission gate is intentionally milestone-only.

---

# Epic closure — semantics-complete audit

### Task E1: Eliminate or justify every remaining execution-not-implemented site

**Type:** audit / write-nothing unless a defect is found
**Review:** adversarial

**Claim:** no accepted RED2 execution can produce `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`. (derived)

For every remaining textual occurrence:
- prove it is unreachable from a valid encoded machine state, or
- replace it with the oracle's typed RED2 fault, or
- implement the missing semantics.

A comment saying “should be unreachable” is not proof. Require a static invariant plus targeted adversarial test or exhaustive bounded witness where feasible.

---

### Task E2: Full semantic matrix against Concrete

**Type:** verification
**Review:** adversarial

**Claim:** Synth matches Concrete across the complete accepted ABI surface, not only committed example programs. (derived)

**Matrix dimensions:**
- opcode families;
- forward/reverse direction;
- head/non-head where legal;
- q=0/q>0;
- atomic/composite result shapes;
- closure/EP/REC/RBLOCK/STRUCT nesting;
- equality shapes;
- IF branch shapes;
- VAR/APP_VAR binding classes;
- graph/control boundary capacities;
- host pending/no-pending;
- valid/invalid resume;
- recharge states;
- representative definition/head metadata.

Use minimized transition witnesses plus program traces. Prefer generated tables over hand-written one-off expectations when the state space is regular.

---

### Task E3: Final integrated acceptance gate and semantics flag decision

**Type:** final gate
**Review:** adversarial

**Required gates:**

```text
mise test

scripts/check_syn_sim.py

scripts/check_syn.py --frontend-only

examples/fibonacci.thor => 8 on Synth

host-call lockstep corpus => zero divergence

repeated UART-RX/TX/TX-BYTES exams => exact ordered effects

repeated q exhaustion/recharge => same final result/effect trace as uninterrupted run

git diff --check
```

Also require:
- no `.red2` serialization/compile CLI restoration;
- package architecture remains `thor`, `red2`, and peer machine packages;
- no Python reducer fallback after loading Synth;
- no host-side RED2 continuation evaluation;
- no accepted semantic path ending in `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`;
- PipelineC pinned frontend still emits the hardware top;
- archives/thesis material unchanged.

Only after all of the above pass may this task change:

```python
RED2_SYNTH_SEMANTICS_COMPLETE = 0
```

to:

```python
RED2_SYNTH_SEMANTICS_COMPLETE = 1
```

If any promised capability remains withheld, leave the flag at `0` and document the exact residual boundary instead of weakening acceptance.

---

## Epic acceptance

The epic is complete only when all of the following are simultaneously true:

1. A generic bounded transactional publication/relinearization engine covers every Concrete-accepted pure RED2 graph shape.
2. APP/LAMBDA/EP/CLOSURE/REC/RBLOCK/STRUCT publication no longer depends on Fibonacci-specific or narrow shape assumptions.
3. STRUCT selector promotion accepts arbitrary Concrete-supported nested values.
4. IF, equality, lambda beta, VAR and APP_VAR can feed all valid result/value shapes into publication without a hardware-not-implemented escape hatch.
5. q=0 stable residuals can be recharged/relinearized on the same Synth machine.
6. CLOCK and UART-RX suspend only at primitive firing and resume direct atomic results exactly once.
7. UART-TX and UART-TX-BYTES reduce their strict arguments first, emit exactly one host effect, and resume exactly once.
8. IO-BIND/IO-THEN/IO-RETURN sequencing remains RED2 execution, not host-side continuation logic.
9. Pending host state is stable under arbitrary processor clocks and rejects replay/invalid resume atomically.
10. Long-running recursive UART programs can receive, compute, transmit, exhaust/recharge quantum, and continue on one loaded machine.
11. Concrete↔Synth lockstep spans ordinary commits, HOST_CALL, resume, QUANTUM_EXHAUSTED, recharge and completion.
12. No valid RED2 path reaches `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`.
13. Full Python, native and real PipelineC frontend/HDL gates remain green.
14. Only then may `RED2_SYNTH_SEMANTICS_COMPLETE` become `1`.

---

## Explicit non-goals

- Physical Basys 3 UART/JTAG/USB transport framing or board bring-up.
- Choosing the eventual PC↔FPGA transport protocol.
- A RED2 operating system, multitasking kernel, or multiple live machine contexts.
- Moving ordinary arithmetic/comparison primitives to the host.
- Letting the host interpret IO-BIND/IO-THEN or any other RED2 continuation.
- Unbounded/dynamic graph memory.
- Replacing Concrete/Abstract semantics with a cleaner hardware-specific semantics.
- Requiring one RED2 transition per FPGA clock.
- Rewriting PipelineC unless an Asgard coding-shape reduction and minimized compiler witness prove a real frontend defect.
- Lean formalization as a prerequisite for this epic.

---

## Suggested execution order

```text
PROJECT A
A1 inventory/minimized witnesses
  -> A2 generic walker state + transaction design
  -> A3 APP/LAMBDA/EP
  -> A4 CLOSURE
  -> A5 REC/RBLOCK
  -> A6 STRUCT/selectors
  -> A7 IF/lookup/lambda/equality escape hatches
  -> A8 q recharge/relinearization
  -> A9 pure-semantics exhaustive gate

PROJECT B
B1 host ABI/fault contract
  -> B2 CLOCK + UART-RX direct resume
  -> B3 UART-TX strict resume
  -> B4 UART-TX-BYTES
  -> B5 IO combinator integration
  -> B6 q-boundary + repeated I/O integration
  -> B7 automated host-service lockstep harness
  -> B8 UART-oriented end-to-end program exams
  -> B9 real PipelineC/HDL milestone gate

EPIC CLOSURE
E1 zero reachable EXECUTION_NOT_IMPLEMENTED
  -> E2 complete semantic matrix
  -> E3 integrated acceptance + semantics flag decision
```

At every red step:

```text
reproduce against Concrete
-> find first committed/pre-commit divergence
-> minimize
-> add regression
-> implement exact semantics transactionally
-> focused native parity
-> focused PipelineC shape check when source form changed
-> advance one capability
```

Do not use the final UART loop as the debugging unit any more than Fibonacci was used as the debugging unit. Every missing capability discovered on the way must first become a minimized Concrete↔Synth witness and a permanent regression.

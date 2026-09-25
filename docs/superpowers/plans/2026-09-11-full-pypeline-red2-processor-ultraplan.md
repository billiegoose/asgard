# Ultraplan: Full Pypeline RED2 Processor

> Poor Girl's Codex execution: `/skill:ultrapowers docs/superpowers/plans/2026-09-11-full-pypeline-red2-processor-ultraplan.md`. This is a planning deliverable, not an execution launch. The plan intentionally builds a real stateful reducer rather than a combinational opcode demonstration.

**Grammar:** claims-v1
**Claim:** implement the faithful Python RED2 machine as a synthesizable Pypeline processor, first proven by differential simulation and then validated through the real Pypeline/PipelineC hardware flow. (elicited)
**Goal:** Build a persistent, stateful RED2 processor that owns graph/environment/control memory, matches `AbstractRED2Machine` semantics across pure reduction, bounded q=0 residualization, and host-call suspension/resume, and is suitable for later FPGA deployment. Basys 3 transport and physical-board integration are explicitly outside this plan.
**Tech Stack:** Python 3.14+, Pypeline/PipelineC, uv, pytest, ruff, mypy; external HDL/synthesis tooling for the explicit hardware gate.
**Exam command:** uv run pytest -q {paths}
**Spec:** `docs/superpowers/specs/2026-09-11-full-pypeline-red2-processor-design.md`
**Acceptance:** suite — focused transition/memory/program exams, independent peer or adversarial review at declared high-risk boundaries, full Python quality gates, real Pypeline/PipelineC frontend plus HDL/synthesis smoke validation, and archive/thesis preservation are required; missing external hardware tooling blocks the hardware gate rather than silently waiving it.
**Parallelization rationale:** Tasks 1–3 establish the representation, memory substrate, and first true stateful reducer and therefore serialize. Tasks 4–9 extend semantic coverage in dependency order because each consumes the prior machine substrate. Task 10 establishes the external quantum boundary only after pure reduction is complete; Task 11 then adds host suspension. Tasks 12–13 build whole-program differential proof on the completed semantics. Task 14 crosses from simulation into the real Pypeline/PipelineC hardware flow. Task 15 is explicitly deferred from this plan; Basys 3 host transport belongs to later board-integration work after the separate OpenXC7/nextpnr/Project X-Ray Pypeline backend is available. Task 16 is a write-nothing gate over the reducer and synthesis artifact. Correctness and hardware observability, rather than maximal fanout, determine the dependency graph.

**Poor Girl's Codex delegation policy:** Execute this plan through `poor_girls_codex`. **All delegation MUST use Poor Girl's Codex's chatgpt-web `subagent {name,prompt}` tool.** Whenever a task calls for a `peer` or `adversarial` review, or whenever the executing agent delegates implementation, investigation, verification, or any other work to another agent, create that delegate with `subagent`; do not invoke Pi subagents, Paseo subagents, CLI agent runners, or any other agent-spawning mechanism. Give each `subagent` a self-contained prompt naming the task, relevant files, current state, claim/proof obligations, constraints, and requested deliverable. Use separate subagents for genuinely independent work where useful, while respecting the dependency graph above. Subagents report findings/results back to the parent Poor Girl's Codex session; the parent agent remains responsible for integrating changes, resolving conflicts, running the required exams/gates, and determining whether each task is actually complete.

## Goal

Implement the faithful Python `AbstractRED2Machine` execution semantics as a synthesizable Pypeline/PipelineC RED2 processor, using the Python machine as the executable oracle and preserving the architectural boundary required for eventual FPGA operation.

The finished artifact must execute non-trivial compiled RED2 programs by repeatedly advancing persistent machine state, mutating graph/environment memory, maintaining the control stack, respecting the semantic contraction quantum, reconstructing a bounded residual graph at q=0, and suspending/resuming for host-dispatched effects. It must not merely classify opcodes or calculate isolated next-register examples.

## Architectural target

```text
        ASGARD HOST
 +---------------------------+
 | THOR compiler             |
 | graph/image loader        |
 | debugger / monitor        |
 | host-call services        |
 | program lifecycle         |
 +-------------+-------------+
               | RED2 host ABI
               v
 +---------------------------+
 |       RED2 PROCESSOR      |
 |                           |
 | pc / fsp / env / c        |
 | direction / q / phi       |
 | free_space / argcnt       |
 | prim / fire / scratch     |
 | graph + environment RAM   |
 | control-stack RAM         |
 | reduction control         |
 +---------------------------+
```

The Basys 3 deployment model is host-supervised: the PC is the loader/debugger/service host and the FPGA owns RED2 execution. No RED2 operating system, multitasking kernel, PCIe-style subsystem, or embedded ARM integration is required by this plan.

## Semantic authority and non-negotiable boundaries

1. `models/abstract_red2_machine/machine.py` is the executable transition oracle. Pypeline does not invent a second RED2 semantics.
2. Hilton's thesis/archive material remains historical authority when a hardware representation choice exposes an ambiguity. Do not edit `archives/` or `thesis-transcription/`.
3. One loaded program corresponds to one live RED2 machine state. Host calls and quantum boundaries do not instantiate a replacement evaluator.
4. `q` is a semantic contraction budget, not an FPGA clock-cycle counter. A contraction may consume many hardware clocks.
5. q=0 is not an arbitrary mid-transition pause. The processor must perform RED2's ordinary zero-quantum traversal/reconstruction to the stable scheduling boundary before reporting quantum exhaustion.
6. Host effects are traps at primitive firing. The host may service the request and return a machine value; it must not evaluate RED2 continuations or monadic sequencing.
7. Pure RED2 primitives that are practical in hardware remain processor operations. Do not turn arithmetic/comparison/etc. into host calls merely to simplify implementation.
8. Pypeline source must remain synthesizable: fixed-width values and bounded memories/state machines, with no dynamic Python allocation or Python-object semantics in the hardware path.
9. Correctness is established by shared state/transition/program traces against `AbstractRED2Machine`, not by duplicating expected behavior manually in Pypeline-specific tests.

## Hardware representation contract

Before broad opcode work, freeze an explicit fixed-width representation. At minimum it must encode:

- every hardware-supported `MuredOpcode`;
- `Word.head` and the machine-visible payload needed by that opcode;
- graph/environment addresses;
- `Direction.F` / `Direction.B`;
- `pc`, `fsp`, `env`, `free_space`, `c`;
- `q`, `phi`, `argcnt`, `fire`;
- primitive identity/register state;
- scratch/address registers required by transitions;
- bounded control-stack entries, including typed saved contexts needed by the current Python machine;
- processor status and host-call request/result payloads.

Python-only diagnostics such as cycle-event lists, peak-memory statistics, poisoning, exceptions as Python objects, and source-level definition strings are not automatically architectural registers. Where Python stores rich objects or strings, define a finite encoded hardware equivalent or explicitly classify the feature as load-time metadata outside the processor.

The plan must not assume one RED2 transition equals one PipelineC function invocation or one physical clock. Multi-access transitions are implemented as microstates over synchronous memories when required.

## Target host ABI

The logical control interface should converge on this transport-independent shape before UART/JTAG details are chosen:

```text
RESET
LOAD(address, words...)
START(root, graph_limit, env_limit, stack_limit, quantum)
RUN
    -> COMPLETE(result_root)
    -> QUANTUM_EXHAUSTED(result_root/residual_root)
    -> HOST_CALL(op, argument/value descriptor)
    -> FAULT(code)
RESUME_HOST_CALL(value)
RECHARGE_QUANTUM(value)
READ_STATE
READ_MEM(address, count)
```

A debug single-transition command may be exposed for verification. Transport implementation is deliberately later than the logical processor interface.

## Global proof strategy

Use three levels of oracle evidence:

- **Transition vectors:** identical encoded pre-state + relevant memory/control contents produce identical post-state/memory writes or suspension status.
- **Trace lockstep:** execute a compiled program in Python and Pypeline and compare normalized architectural checkpoints through many transitions, including intermediate graph/environment mutation.
- **Program exams:** load real compiled THOR/RED2 fixtures and compare residual/final graphs, contraction behavior, host effects and bounded-memory behavior.

Tests must compare architectural state, not Python-only diagnostic bookkeeping. When a transition takes several hardware clocks, compare at its committed architectural boundary.

### Task 1: Freeze the synthesizable word, state and status ABI

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/concrete_red2_machine/abi.py`
- Modify: `models/concrete_red2_machine/README.md`
- Modify: `models/abstract_red2_machine/pipelinec_vectors.py`
- Test: `tests/test_pipelinec_vectors.py`
- Test: `tests/test_pypeline_red2_static.py`

**Claim:** Encode enough RED2 architectural state to represent a loaded `AbstractRED2Machine` checkpoint without relying on Python objects or strings inside the synthesizable processor. (derived)
Machine: M1. Every required opcode, direction, status and machine register has a fixed-width encoding with explicit range checks. M2. Word/address/control-stack encodings round-trip representative Python machine states without semantic loss. M3. Hardware state excludes diagnostics and host conveniences that are not part of execution semantics.

**Authorized-by:** Current `AbstractRED2MachineState`; current `MuredOpcode`; historical RED2 register/memory model; architectural target above.

**Interfaces:**
- Consumes: `AbstractRED2MachineState`
- Consumes: `Word`
- Produces: `RED2_ABI_V1`

**Context:** The existing stepper is only a fixed-width exploration. Preserve its useful style but do not preserve a narrow ABI merely for compatibility. Primitive names and rich control entries require finite IDs/tags. Decide widths from explicit supported limits, not Python integer behavior. Separate semantic state from test diagnostics.

**Proof:**
- Test: `tests/test_pipelinec_vectors.py`
- Test: `tests/test_pypeline_red2_static.py`
- Run: uv run pytest -q tests/test_pipelinec_vectors.py tests/test_pypeline_red2_static.py
- Legs: (a) Round-trip representative words for every opcode and boundary payload value and require exact encoded widths/range failures [M1]; (b) encode/decode states containing forward/backward traversal, active primitive, saved quantum, definition/subgraph/equality contexts and near-boundary addresses and require exact architectural-state equality with no semantic loss [M2]; (c) static checks reject dynamic containers, unbounded strings and unsupported Python-only state in synthesizable functions [M3].

**Stale-if:**
- path-absent: `models/concrete_red2_machine/abi.py`
- path-absent: `models/abstract_red2_machine/machine.py`

### Task 2: Build persistent graph/environment and control-stack memories

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/concrete_red2_machine/abi.py`
- Test: `tests/test_pypeline_red2_memory.py`
- Test: `tests/test_pipelinec_vectors.py`

**Claim:** Execute memory and stack operations against bounded persistent processor storage with the same graph-up/environment-down collision discipline as `AbstractRED2Machine`. (derived)
Machine: M1. Graph pushes advance `fsp`; environment allocation lowers `free_space`; logical `env` changes do not themselves allocate. M2. PNP/path bridges and environment blocks use the same committed layout semantics as the Python oracle. M3. Control pushes/pops and collision/overflow/invalid-address cases become deterministic processor faults rather than undefined writes.

**Authorized-by:** `AbstractRED2Machine._push_graph`, `_allocate_environment`, `_push_environment_marker`, `_allocate_environment_block`, `_push_control_entry`, `_pop_control_entry`, `_validate_state`.

**Interfaces:**
- Consumes: `RED2_ABI_V1`
- Produces: `RED2_MEMORY_V1`

**Context:** Model synchronous-memory reality explicitly. A semantic helper that performs multiple reads/writes may require several microstates. Atomicity is at the committed RED2 transition boundary: failed reserve/collision must not leave a partially visible block.

**Proof:**
- Test: `tests/test_pypeline_red2_memory.py`
- Run: uv run pytest -q tests/test_pypeline_red2_memory.py tests/test_pipelinec_vectors.py
- Legs: (a) Differentially execute graph pushes and one-/multiword environment allocations including PNP bridges and compare exact memory/state deltas [M1,M2]; (b) fill arenas to each legal boundary and require the same first illegal allocation to fault without partial writes [M3]; (c) fill/drain typed control storage and compare pointer/tag/payload behavior with normalized Python control entries [M3].

**Stale-if:**
- path-absent: `models/abstract_red2_machine/machine.py`

### Task 3: Replace the demonstration stepper with a clocked RED2 transition engine

**Type:** implementation
**Review:** adversarial

**Files:**
- Modify: `models/concrete_red2_machine/abi.py`
- Create: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_transitions.py`
- Modify: `models/abstract_red2_machine/pipelinec_vectors.py`

**Claim:** Repeated processor clocks commit complete RED2 architectural transitions over persistent state rather than computing isolated opcode examples. (derived)
Machine: M1. Fetch/decode/microstate/commit sequencing preserves the Python `step()` dispatch boundary. M2. APP, APP_VAR, atomic INT/FLOAT/CHAR, LAMBDA, VAR and STOP transitions match oracle state and memory deltas in both traversal directions where applicable. M3. A stream of committed transitions can execute without reinitializing machine state between steps.

**Authorized-by:** `AbstractRED2Machine.step()` and corresponding transition methods.

**Interfaces:**
- Consumes: `RED2_MEMORY_V1`
- Produces: `RED2_CORE_V1`

**Context:** Do not require one-cycle instructions. Keep hardware microstate separate from RED2 architectural state so trace comparisons occur only on commit. STOP is an architectural instruction, not a Python harness condition.

**Proof:**
- Test: `tests/test_pypeline_red2_transitions.py`
- Run: uv run pytest -q tests/test_pypeline_red2_transitions.py tests/test_pipelinec_vectors.py
- Legs: (a) Generate pre-state vectors from Python for each first-slice opcode/direction and compare every architectural register plus exact memory/control writes at commit [M1,M2]; (b) execute chained hand-built graphs for at least 50 committed transitions with no hardware-state reinitialization and compare each checkpoint exactly [M3]; (c) deliberately perturb one expected address/direction/head bit in the oracle trace and prove the differential exam detects it [M1].

**Stale-if:**
- path-absent: `models/abstract_red2_machine/machine.py`

### Task 4: Implement application, closure, environment-path and JOIN machinery

**Type:** implementation
**Review:** adversarial

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_transitions.py`
- Test: `tests/test_pypeline_red2_closures.py`

**Claim:** Execute nested applications and closures while preserving environment paths, child-return frames, JOIN publication and reclaimed boundaries. (derived)
Machine: M1. CLOSURE, EP, JOIN and PNP-visible path behavior matches normalized Python transitions. M2. Nested subgraph entry/return restores parent state and publishes escaping results without pointers into reclaimed child storage. M3. Repeated bounded application/closure workloads reuse graph/environment space rather than leaking monotonically.

**Authorized-by:** current `AbstractRED2Machine` closure/EP/JOIN/subgraph-frame implementation and integrated memory-lifetime semantics.

**Interfaces:**
- Consumes: `RED2_CORE_V1`
- Produces: `RED2_CLOSURES_V1`

**Context:** The current Python machine contains post-prototype memory reclamation semantics. Port the current behavior, not an older plan's intermediate allocator. Rich `_SubgraphFrame` state needs an explicit hardware tag/payload representation or equivalent dedicated registers/stack words.

**Proof:**
- Test: `tests/test_pypeline_red2_closures.py`
- Run: uv run pytest -q tests/test_pypeline_red2_closures.py tests/test_pypeline_red2_transitions.py
- Legs: (a) Differential traces for captured lambdas, nested APP, EP chains and JOIN returns [M1,M2]; (b) poison/reuse equivalent oracle cases and require surviving values to remain exact with no pointers into reclaimed child storage after physical address reuse [M2]; (c) repeat fixed-live-state closure workloads at increasing iteration counts and assert bounded post-warmup `fsp` and `free_space` envelopes [M3].

**Stale-if:**
- path-absent: `tests/test_abstract_red2_memory_lifetimes.py`

### Task 5: Implement symbols, definitions and primitive register sequencing

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Modify: `models/concrete_red2_machine/README.md`
- Test: `tests/test_pypeline_red2_primitives.py`
- Test: `tests/test_pypeline_red2_transitions.py`

**Claim:** Expand encoded definitions and collect/fire primitive arguments with the same `argcnt`, `prim`, `fire`, head and control behavior as Python RED2. (derived)
Machine: M1. SYM definition lookup uses a finite load-time definition table/image rather than runtime strings. M2. PRIM_0/1/2 partial and ready states preserve primitive sequencing exactly. M3. q=0 does not accidentally fire a contraction or host effect.

**Authorized-by:** `AbstractRED2Machine._sym`, `_prim`, primitive saved-state machinery.

**Interfaces:**
- Consumes: `RED2_CLOSURES_V1`
- Produces: `RED2_PRIM_SEQ_V1`

**Context:** Keep the THOR compiler on the host. Hardware receives encoded program/definition images. Source symbol names are debug metadata; execution uses IDs/addresses.

**Proof:**
- Test: `tests/test_pypeline_red2_primitives.py`
- Run: uv run pytest -q tests/test_pypeline_red2_primitives.py tests/test_pypeline_red2_transitions.py
- Legs: (a) compare definition expansion traces and nested definition paths [M1]; (b) compare zero-, unary- and binary-primitive collection states including partial/stuck forms [M2]; (c) enter every ready contraction with q=0 and assert no contraction/effect is committed [M3].

**Stale-if:**
- path-absent: `models/abstract_red2_machine/machine.py`

### Task 6: Implement hardware-native scalar primitives and strictness

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_primitives.py`
- Test: `tests/test_pypeline_red2_programs.py`

**Claim:** Contract the supported pure scalar primitive set in hardware with Python-equivalent strictness, result representation and quantum accounting. (derived)
Machine: M1. Integer arithmetic/comparisons/type predicates and practical fixed-width scalar operations produce matching values or deterministic faults/stuck states. M2. Each semantic contraction decrements q exactly where the Python oracle does, independent of physical clock count. M3. Unsupported numeric behavior is explicitly bounded/documented rather than silently inheriting Python arbitrary precision.

**Authorized-by:** current strict primitive implementations and `q` behavior in `AbstractRED2Machine`.

**Interfaces:**
- Consumes: `RED2_PRIM_SEQ_V1`
- Produces: `RED2_SCALARS_V1`

**Context:** Define integer width/overflow and floating-point policy explicitly. If full FLOAT hardware is deferred, preserve its encoding and report unsupported execution as a defined processor fault; do not fake Python float semantics in unsynthesizable code. Division/mod/exponentiation may be multicycle.

**Proof:**
- Test: `tests/test_pypeline_red2_primitives.py`
- Test: `tests/test_pypeline_red2_programs.py`
- Run: uv run pytest -q tests/test_pypeline_red2_primitives.py tests/test_pypeline_red2_programs.py
- Legs: (a) differential boundary/value tables for every implemented primitive [M1]; (b) record physical clocks and committed q before/after multicycle operations and require the exact q delta to equal semantic contractions only, never physical clocks [M2]; (c) exercise overflow/divide-by-zero/unsupported-float policy and require deterministic documented status [M3].

**Stale-if:**
- path-absent: `models/abstract_red2_machine/machine.py`

### Task 7: Implement non-strict IF, Y and lazy control

**Type:** implementation
**Review:** adversarial

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_lazy.py`
- Test: `tests/test_pypeline_red2_programs.py`

**Claim:** Execute non-strict branch selection and recursive unfolding without forcing dead branches or leaking scratch state. (derived)
Machine: M1. IF selects only the demanded branch; compiler-lowered AND/OR inherit equivalent laziness. M2. Y follows the current acyclic code-reuse/scratch-lifetime behavior. M3. q-prefix traces for lazy fixtures agree with Python at committed architectural boundaries.

**Authorized-by:** current `AbstractRED2Machine` IF/Y semantics and lockstep parity corpus.

**Interfaces:**
- Consumes: `RED2_SCALARS_V1`
- Produces: `RED2_LAZY_V1`

**Context:** Include an unselected failing/effectful branch exam. Hardware recursion is graph reduction, not recursive Python/Pypeline function calls.

**Proof:**
- Test: `tests/test_pypeline_red2_lazy.py`
- Run: uv run pytest -q tests/test_pypeline_red2_lazy.py tests/test_pypeline_red2_programs.py
- Legs: (a) true/false IF with atomic/application/captured branches and an unselected fault/effect sentinel, requiring zero evaluation/effects from the unselected branch [M1]; (b) repeated Y unfoldings with bounded fixed-live-state scratch envelope [M2]; (c) compare Python/Pypeline q-prefix residual checkpoints for committed lazy-control fixtures [M3].

**Stale-if:**
- path-absent: `tests/test_lockstep_parity.py`

### Task 8: Implement recursive blocks and lazy structures

**Type:** implementation
**Review:** adversarial

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_recursive.py`
- Test: `tests/test_pypeline_red2_structs.py`
- Test: `tests/test_pypeline_red2_programs.py`

**Claim:** Execute RBLOCK/RUP/RECP recursive environments and STRUCT selection with the same lazy/path/lifetime behavior as Python RED2. (derived)
Machine: M1. Recursive bindings preserve mutually recursive environment layout through forward and reconstruction paths. M2. Structure construction/selection does not force unselected fields and publishes retained fields before reclaim. M3. Real recursive-definition and structure fixtures finish with matching canonical values.

**Authorized-by:** current `AbstractRED2Machine` RBLOCK/RUP/RECP/STRUCT implementation and recursive fixture tests.

**Interfaces:**
- Consumes: `RED2_LAZY_V1`
- Produces: `RED2_RECURSIVE_V1`

**Context:** REC/RECP payloads and selector metadata require finite hardware encoding. Preserve the current Python representation where it intentionally differs from literal C workspace copying but is semantically equivalent.

**Proof:**
- Test: `tests/test_pypeline_red2_recursive.py`
- Test: `tests/test_pypeline_red2_structs.py`
- Run: uv run pytest -q tests/test_pypeline_red2_recursive.py tests/test_pypeline_red2_structs.py tests/test_pypeline_red2_programs.py
- Legs: (a) differential transition traces for positive-q and q=0 recursive paths [M1]; (b) select fields from shared/nested structures with unselected failure sentinels and subsequent address reuse, requiring zero forcing of unselected fields and no dangling reclaimed pointers [M2]; (c) execute representative existing recursive definitions and structures from compiled images to matching final values [M3].

**Stale-if:**
- path-absent: `tests/test_red2_recursive_definitions.py`
- path-absent: `tests/test_red2_recursive_structs.py`

### Task 9: Implement structural equality and remaining pure RED2 value operations

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_equality.py`
- Test: `tests/test_pypeline_red2_programs.py`

**Claim:** Compare supported RED2 values structurally without host evaluation or unbounded hardware recursion, preserving temporary graph/control lifetimes. (derived)
Machine: M1. Atomic and graph equality matches Python results. M2. Nested/shared/recursive-safe cases use bounded explicit processor state rather than host traversal. M3. Temporary equality state is balanced/reclaimed and q behavior matches the oracle.

**Authorized-by:** current `_EqualityFrame` and RED2 equality implementation.

**Interfaces:**
- Consumes: `RED2_RECURSIVE_V1`
- Produces: `RED2_PURE_V1`

**Context:** Translate Python frame objects into finite tags/payloads. Cycles/sharing must follow the semantics already accepted by the Python implementation; do not introduce an independent graph-equality definition.

**Proof:**
- Test: `tests/test_pypeline_red2_equality.py`
- Run: uv run pytest -q tests/test_pypeline_red2_equality.py tests/test_pypeline_red2_programs.py
- Legs: (a) differential atomic/nested/shared equality tables [M1]; (b) adversarial deep values within configured memory/control bounds complete without host recursion [M2]; (c) compare control/free-space/q state before and after equality and repeated fixed-size cases [M3].

**Stale-if:**
- path-absent: `tests/test_abstract_red2_equality.py`

### Task 10: Make q=0 reconstruction and quantum exhaustion architectural

**Type:** implementation
**Review:** adversarial

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_quantum.py`
- Test: `tests/test_pypeline_red2_programs.py`

**Claim:** Exhausting q produces the same stable bounded residual graph as Python RED2 and only then reports `QUANTUM_EXHAUSTED`; recharging continues the same live processor state. (derived)
Machine: M1. q decrements only on semantic contractions. M2. q reaching zero drives ordinary reconstruction until the scheduling-visible residual boundary rather than freezing an arbitrary microstate. M3. `RECHARGE_QUANTUM` resumes from that residual state without recompiling/reloading or replacing processor memory.

**Authorized-by:** current Python q=0 transition/reconstruction behavior, `refresh_quantum`/`recharge_quantum`, and RED2 quantum semantics.

**Interfaces:**
- Consumes: `RED2_PURE_V1`
- Produces: `RED2_QUANTUM_V1`

**Context:** This is a semantic acceptance boundary, not a cycle watchdog. Keep a separate simulation/test cycle limit if needed to detect implementation hangs.

**Proof:**
- Test: `tests/test_pypeline_red2_quantum.py`
- Run: uv run pytest -q tests/test_pypeline_red2_quantum.py tests/test_pypeline_red2_programs.py
- Legs: (a) for q=0..N across representative applications, primitives, lazy control, recursive blocks and structures, compare canonical residual graphs and architectural state exactly at exhaustion/completion, with zero q decrements outside semantic contractions [M1,M2]; (b) recharge each exhausted case repeatedly and require an identical final result to a sufficiently large uninterrupted run with no recompilation/reload and the same memory instance [M3]; (c) use operations with differing physical clock counts and require exact semantic q consumption where contraction counts are equal [M1].

**Stale-if:**
- path-absent: `models/abstract_red2_machine/machine.py`

### Task 11: Add host-call trap and same-machine resume

**Type:** implementation
**Review:** adversarial

**Files:**
- Modify: `models/concrete_red2_machine/machine.py`
- Test: `tests/test_pypeline_red2_host_calls.py`
- Test: `tests/test_pypeline_red2_programs.py`

**Claim:** Trap CLOCK/UART host primitives exactly at firing, expose a finite request, and incorporate an atomic returned value into the same graph exactly once. (derived)
Machine: M1. CLOCK, UART-RX, UART-TX and UART-TX-BYTES reach `HOST_CALL` only when their RED2 primitive fires with positive q. M2. While pending, processor execution is stable and cannot replay the effect. M3. Resume writes the result into the correct redex/result location, decrements q exactly once as required, clears pending status and continues the same machine.

**Authorized-by:** `AbstractRED2Machine._suspend_host_call`, `resume_host_call`, current one-machine IO invariant.

**Interfaces:**
- Consumes: `RED2_QUANTUM_V1`
- Produces: `RED2_HOSTCALL_V1`

**Context:** Do not implement UART transport yet; UART-TX here is the RED2 semantic host primitive, not necessarily the physical host-interface UART. Preserve current restriction to atomic host results unless a separate graph-owned publication design is authorized.

**Proof:**
- Test: `tests/test_pypeline_red2_host_calls.py`
- Run: uv run pytest -q tests/test_pypeline_red2_host_calls.py tests/test_pypeline_red2_programs.py
- Legs: (a) compare Python/Pypeline request primitive, argument descriptor, pc/fsp/env/q and memory exactly at each effect, and require no HOST_CALL before the primitive actually fires [M1]; (b) clock the processor arbitrarily while pending and prove no architectural mutation or duplicate request occurs [M2]; (c) resume deterministic sequences and compare exact ordered effects, call counts, graph writes and final values; invalid/non-atomic resume values fault without partial commit [M3].

**Stale-if:**
- path-absent: `tests/test_red2_io_runtime.py`

### Task 12: Build compiled-program loader and full trace-lockstep harness

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/abstract_red2_machine/pipelinec_vectors.py`
- Create: `models/concrete_red2_machine/oracle.py`
- Test: `tests/test_pypeline_red2_lockstep.py`
- Test: `tests/test_pypeline_red2_programs.py`

**Claim:** Load the same compiled RED2 image into Python and Pypeline machines and automatically identify the first divergent committed architectural transition. (derived)
Machine: M1. Loader relocates/encodes problem and definition images consistently. M2. Trace normalizer compares all architectural registers, live memory writes, control entries, stop reason and host-call data while excluding implementation-only diagnostics/microstates. M3. Corpus includes straight-line, closure, primitive, lazy, recursive, structure, equality, q-exhaustion and IO programs.

**Authorized-by:** common-oracle strategy and current compiler/`AbstractRED2Machine.load` behavior.

**Interfaces:**
- Consumes: `RED2_HOSTCALL_V1`
- Produces: `RED2_LOCKSTEP_V1`

**Context:** This becomes the primary development safety net. Failure output should show transition index, opcode/microstate context, differing registers and minimal memory/control diff.

**Proof:**
- Test: `tests/test_pypeline_red2_lockstep.py`
- Run: uv run pytest -q tests/test_pypeline_red2_lockstep.py tests/test_pypeline_red2_programs.py
- Legs: (a) run the committed corpus through deterministic image loading/relocation and require identical encoded images before execution [M1]; (b) mutation-test representative register, memory, control, stop-reason and host-call fields and require the normalizer to report the exact first divergence with no ignored architectural field [M2]; (c) require committed fixtures covering straight-line, closure, primitive, lazy, recursive, structure, equality, q-exhaustion and IO categories to execute through the differential runner [M3].

**Stale-if:**
- path-absent: `models/abstract_red2_machine/pipelinec_vectors.py`

### Task 13: Prove non-trivial THOR programs run wholly on the Pypeline reducer

**Type:** implementation
**Review:** adversarial

**Files:**
- Test: `tests/test_pypeline_red2_programs.py`
- Modify: `models/concrete_red2_machine/README.md`

**Claim:** Compile and execute representative THOR programs using the Pypeline processor as the evaluator, with the host limited to compilation/loading, scheduling and declared host services. (derived)
Machine: M1. Pure programs exercise hundreds/thousands of committed transitions and finish with Python-equivalent canonical results. M2. Bounded-loop programs cross multiple quantum exhaustion/recharge boundaries without machine replacement. M3. IO programs preserve exact effect order and exactly-once behavior while computation/continuations remain in RED2.

**Authorized-by:** intended host/processor boundary and one-machine invariant.

**Interfaces:**
- Consumes: `RED2_LOCKSTEP_V1`
- Produces: `RED2_PROGRAMS_V1`

**Context:** Include small focused fixtures before attempting Breakout. Candidate corpus should cover arithmetic recursion, lists/structures, closure capture, clock-dots and a deterministic interactive-style sequence. A Python test driver may emulate the host ABI but may not evaluate RED2 expressions.

**Proof:**
- Test: `tests/test_pypeline_red2_programs.py`
- Run: uv run pytest -q tests/test_pypeline_red2_programs.py
- Legs: (a) require at least one pure recursive program, one closure-heavy program and one structure/list program to exceed 500 committed RED2 transitions and match canonical Python output [M1]; (b) force small quantum values causing repeated exhaustion/recharge and assert machine memory/state identity is retained and final output unchanged [M2]; (c) run clock/UART fixture with deterministic host responses and compare exact ordered calls/counts/output with Python RED2 [M3].

**Stale-if:**
- path-absent: `examples/clock-dots.thor`

### Task 14: Establish actual Pypeline/PipelineC translation and synthesis smoke tests

**Type:** implementation
**Review:** peer

**Files:**
- Create: `models/synthesizable_red2_machine/machine.py`
- Modify: `models/concrete_red2_machine/README.md`
- Modify: `.mise.toml`
- Create: `scripts/check_syn.py`
- Create: `scripts/check_syn_sim.py`
- Test: `tests/test_pypeline_red2_static.py`

**Claim:** Validate the processor with the real installed/cloned Pypeline/PipelineC toolchain and produce a reproducible HDL/synthesis smoke result without making vendor tools mandatory for ordinary Python tests. (derived)
Machine: M1. The processor source passes the current Pypeline/PipelineC frontend rather than only CPython syntax/tests. M2. Generated HDL elaborates/synthesizes for a documented generic or Basys-3-compatible target when the external toolchain is available. M3. Default repository tests remain useful when FPGA/vendor tools are absent, while an explicit hardware gate fails clearly if its required toolchain is missing.

**Authorized-by:** project Pypeline exploration goal and existing dependency-light testing policy.

**Interfaces:**
- Consumes: `RED2_PROGRAMS_V1`
- Produces: `RED2_SYNTH_V1`

**Context:** Earlier tool detection timed out; do not hide this behind a skip in the explicit hardware gate. Discover the actual local PipelineC/Pypeline invocation and pin/document the tested revision. `ConcreteRED2Machine` is the executable simulation/oracle model, not directly synthesizable Pypeline source; Task 14 therefore owns a dedicated hardware top in `models/synthesizable_red2_machine/machine.py` using supported fixed-width `@struct`, `Reg` and RAM constructs while preserving the same architectural contract. Keep generated/vendor artifacts out of source control unless explicitly useful.

**Proof:**
- Test: `tests/test_pypeline_red2_static.py`
- Run: uv run pytest -q tests/test_pypeline_red2_static.py
- Run: mise run syn-check
- Legs: (a) frontend translates the actual processor top and reports no unsupported dynamic Python constructs [M1]; (b) HDL elaboration/synthesis smoke reaches a successful tool exit and records target/resource/timing summary when configured [M2]; (c) deliberately hide the external tool and require the explicit hardware command to fail with an exact missing-tool diagnostic rather than a false green, while ordinary pytest remains dependency-light with no vendor-tool requirement [M3].

**Stale-if:**
- path-absent: `.mise.toml`

### Task 15: DEFERRED — Basys 3 host transport shell

**Type:** deferred follow-up
**Review:** none in this plan

**Claim:** Basys 3 host transport, board-level framing, UART/control-channel multiplexing, and physical-board bring-up are deliberately not part of this RED2 processor plan.

**Rationale:** The board-facing path depends on separate Pypeline/PipelineC work adding an open-source Xilinx Artix-7 flow using OpenXC7/nextpnr-xilinx/Project X-Ray. That backend is being developed and reviewed independently. This plan should meet that work in the middle by producing a correct synthesizable RED2 core and stable logical host ABI, not by duplicating or prematurely coupling itself to the board transport layer.

**Interfaces:**
- Consumes later: `RED2_SYNTH_V1`
- Produces later: `RED2_TRANSPORT_V1`
- Produces in this plan: nothing

**Scope rule:** Do not create `basys3_top.py`, `red2_fpga_host.py`, a UART framing protocol, or board-specific transport tests as part of this plan. Those belong to a subsequent explicitly authorized board-integration plan after the required Pypeline synthesis backend is available.

### Task 16: Run the integrated RED2 processor acceptance gate

**Type:** gate
**Review:** peer

**Files:**
- Test: `tests/test_pypeline_red2_lockstep.py`
- Test: `tests/test_pypeline_red2_programs.py`
- Test: `tests/test_pypeline_red2_host_calls.py`

**Claim:** The integrated tree contains a synthesizable, stateful RED2 processor that agrees with the Python oracle on the accepted semantic corpus and preserves the historical sources unchanged. (derived)
Machine: M1. Full Python tests, Ruff and mypy pass with transition/program lockstep green. M2. Explicit Pypeline/PipelineC hardware validation succeeds in the provisioned acceptance environment. M3. Archives/thesis remain byte-for-byte unchanged from execution BASE and no host-side second evaluator is introduced.

**Authorized-by:** plan-level acceptance.

**Interfaces:**
- Consumes: `RED2_SYNTH_V1`
- Produces: `RED2_ACCEPTED_V1`

**Context:** This gate does not authorize push, release, board purchase, archive edits, a RED2 OS, Basys 3 transport, or physical-board bring-up. External hardware-tool absence is a provisioning blocker for M2, not evidence that synthesis passed. Board transport and bring-up are subsequent explicitly authorized work once the separate open-source Artix-7 Pypeline backend is available.

**Proof:**
- Run: uv run pytest -n 4 --dist loadfile
- Run: uv run ruff check .
- Run: uv run mypy models tests
- Run: mise run syn-check
- Run: git diff --exit-code "$ULTRA_BASE" -- archives thesis-transcription
- Run: git diff --check
- Legs: (a) require zero differential divergence across transition and program corpus, including q=0 residuals and exact host-call order/count [M1]; (b) require real frontend/HDL/synthesis smoke success and inspect its recorded target/resource result [M2]; (c) inspect host-side Pypeline test/protocol code for RED2 evaluation logic, require archive/thesis diff empty, and reject acceptance if the host computes continuations/primitive semantics on behalf of the processor [M3].

**Stale-if:**
- path-absent: `models/concrete_red2_machine/abi.py`
- path-absent: `models/abstract_red2_machine/machine.py`

## Acceptance

The plan is complete only when all of the following are demonstrated together:

- the Pypeline artifact is a persistent reducer with graph/environment/control memories, not an opcode demo;
- all accepted RED2 instruction families needed by the committed program corpus execute in the processor;
- q counts semantic contractions and q=0 reaches a stable reconstructed residual before external suspension;
- quantum recharge resumes the same loaded processor state;
- host primitives suspend at firing and resume exactly once in the same graph;
- Python/Pypeline transition lockstep identifies no divergence across the accepted corpus;
- non-trivial compiled THOR programs execute wholly through RED2 rather than host evaluation;
- the actual Pypeline/PipelineC frontend accepts the processor and the explicit hardware gate reaches successful HDL/synthesis validation;
- Basys 3 transport and physical-board integration remain explicitly deferred rather than being treated as hidden acceptance requirements;
- `archives/` and `thesis-transcription/` are unchanged from execution BASE.

## Explicit non-goals

- A RED2 operating system or scheduler running inside RED2.
- Multiple simultaneous RED2 machine contexts.
- Replacing the THOR compiler with FPGA logic.
- A Rust rewrite as a prerequisite.
- Proving the implementation in Lean as part of this plan; Lean should consume/share the same semantic contracts and vectors in parallel work.
- Treating every primitive as a host call.
- One RED2 transition per FPGA clock.
- Basys 3 host transport, UART/control framing, board-specific top-level integration, and physical-board bring-up; these are deferred to a later board-integration plan regardless of local board/toolchain availability.
- Editing Hilton's archived implementation to make comparisons easier.

## Suggested execution shape

Tasks 1–3 establish the hardware substrate and first true reducer slice. Tasks 4–9 complete pure RED2 semantics. Task 10 establishes the scheduler-visible quantum boundary. Task 11 adds the host trap. Tasks 12–13 turn the Python implementation into a strong differential oracle and prove useful programs. Task 14 crosses from simulation into the real Pypeline/PipelineC hardware flow. Task 15 is explicitly deferred to later Basys 3 board-integration work. Task 16 is the write-nothing reducer/synthesis integration gate.

Prefer small commits/integrations at semantic boundaries and keep every intermediate processor executable under differential tests. A later task must never be used to excuse a known divergence in an earlier semantic slice.

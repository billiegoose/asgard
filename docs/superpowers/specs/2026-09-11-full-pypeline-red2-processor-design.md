# Full Pypeline RED2 processor design

Status: retrospective design record backfilled at the accepted Tasks 1–10 checkpoint. It records the architecture already validated by those tasks and the intended design authority for Tasks 11–16. It does not retroactively change accepted task claims, proofs, or review verdicts, and it does not authorize execution by itself.

## 1. Request and scope

The operator requested a faithful implementation of the Python RED2 machine as a synthesizable Pypeline/PipelineC processor suitable for eventual Basys 3 deployment. The target is not a combinational opcode demonstration: it is a persistent stateful reducer that owns RED2 graph/environment memory, control state, semantic contraction quantum, reconstruction, and the host-effect suspension boundary.

The executable semantic oracle is `models/python/red2_engine/mured.py`. Hilton's thesis and archived RED2/HORSE material are historical authority when the executable model exposes a representation ambiguity. `archives/` and `thesis-transcription/` remain read-only evidence. The Pypeline processor is a cycle-level refinement of the same machine semantics, not a second language implementation with independently invented behavior.

This specification separates two layers deliberately:

- `MuredMachine` is the architectural/ISA-level executable model: RED2 instructions, machine-visible registers, arena layout, control contexts, q semantics, JOIN/subgraph behavior, and host-call suspension/resume.
- `Red2Processor` is the cycle-level hardware-oriented realization: fixed-width encodings, bounded storage, explicit microstates, fixed scratch, architectural commit points, and synthesizable control/data paths.

The target flow is therefore:

```text
THOR source
   -> μRED image
   -> MuredMachine architectural oracle
   -> Red2Processor cycle-level model
   -> Pypeline/PipelineC
   -> FPGA implementation
```

## 2. Architectural deployment boundary

The deployment model is host-supervised. A PC-side Asgard host owns compilation, image loading, debugger/monitor duties, host services, and program lifecycle. The FPGA owns RED2 reduction for one loaded machine context at a time.

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

No RED2 operating system, multitasking kernel, embedded compiler, PCIe-style subsystem, or ARM dependency is part of this design. Basys 3 is a target board, not a reason to move RED2 semantics into host software.

## 3. Semantic invariants

The processor preserves the following non-negotiable invariants.

1. One loaded program corresponds to one live RED2 machine state. Quantum exhaustion and host calls suspend that state; they do not instantiate a replacement evaluator.
2. `q` is a semantic contraction budget, never a hardware clock budget. One RED2 transition may require many processor clocks, and one contraction may span multiple architectural transitions.
3. q=0 does not freeze an arbitrary microstate. Ordinary RED2 traversal and reconstruction continue until the stable scheduling-visible residual boundary, and only then may the processor report `QUANTUM_EXHAUSTED`.
4. Host effects trap only when the corresponding RED2 primitive fires. The host services the effect and may return an allowed machine value; it never evaluates RED2 continuations, primitive sequencing, or graph reduction.
5. Pure arithmetic, comparison, lazy, recursive, structure, and equality semantics remain processor operations when covered by the architectural machine. They are not converted to host calls merely to simplify hardware.
6. Architectural failure is atomic. A transition that faults before commit leaves the architecturally visible state, memory, and control storage unchanged except for the reported fault status required by the ABI.
7. Multi-clock implementation detail is invisible at the RED2 architectural boundary. Differential comparison occurs at committed RED2 transitions or explicit suspension boundaries, not arbitrary microstates.
8. Pypeline/PipelineC-facing code uses finite encodings, bounded memories and bounded algorithms. Dynamic Python containers, recursion, object identity tricks, unbounded worklists, and Python exception objects are not part of synthesizable state.

## 4. Fixed-width machine and memory model

The processor ABI must finitely encode every machine-visible value needed by the supported RED2 corpus: opcodes, `Word.head`, opcode payloads, graph/environment addresses, traversal direction, machine registers, primitive identity/state, scratch registers, status/fault codes, host-call request/result descriptors, and typed control entries.

Graph storage grows upward through `fsp`; environment storage grows downward through `free_space`; logical `env` is a path/root and is not itself the physical allocator. The live arena maintains the same collision discipline as `MuredMachine`. PNP bridges express environment-path changes independently of physical allocation.

Control state is finite tagged storage. Entries required by the accepted machine include addresses and saved primitive/fire/quantum/definition-path state, typed subgraph frames, and equality state. Malformed tags, widths, addresses, overflows and underflows produce deterministic typed faults rather than partial writes or Python-level failures.

Scratch registers such as lookup address/data are architectural when the reference transition publishes them. Hardware microstate, temporary decode state and internal clock counters are not architectural unless explicitly promoted by the ABI.

## 5. Transition, subgraph and publication model

The processor advances through explicit fetch/execute/commit microstates while preserving `MuredMachine.step()` as the architectural transition boundary. APP, APP_VAR, atomic values, LAMBDA, VAR, STOP and later semantic families operate over one persistent state and memory image.

Closure/environment execution uses the same graph/environment distinction as the oracle. Reverse APP may enter a child subgraph; CLOSURE follows code under an environment marker; EP preserves caller path semantics; JOIN returns a child result to a typed parent context. Child results must be published into parent-owned/live storage before the child's environment region is reclaimed or reused.

Subgraph entry and JOIN restoration are bounded and failure-atomic. Publication must not leave dangling references into reclaimed child storage. Primitive countdown/state restoration occurs at the same architectural boundary as the oracle, including q=0 cases. A failed scalar or publication path must not expose shadow writes as committed architectural state.

Recursive and structure machinery follows the oracle's concrete representation rather than blindly reproducing historical C layouts. RBLOCK/RUP/RECP, STRUCT traversal, equality and reconstruction may use different bounded microalgorithms so long as committed graph/control state and machine-visible side effects agree.

## 6. Accepted pure-reduction architecture at the Tasks 1–10 checkpoint

At the checkpoint preceding host-call implementation, Tasks 1–10 have been independently implemented and reviewed. Their accepted result establishes the following design facts; this section records those facts rather than reopening their task gates.

- A fixed-width `RED2_ABI_V1` encodes machine words, registers, statuses, faults and typed control entries.
- Persistent graph/environment/control memories enforce bounded allocation, PNP bridging, collision checks and deterministic faults.
- `Red2Processor` is a persistent clocked reducer with explicit microstates and architectural commit boundaries.
- APP/CLOSURE/EP/JOIN/PNP behavior, nested subgraph restoration and publication-before-reclamation match the accepted oracle corpus.
- SYM and PRIM sequencing implement strict/deferred primitive setup without conflating semantic q with processor clocks.
- Scalar, lazy IF/Y, recursive, STRUCT and equality slices execute on the processor for the accepted corpus, with unsupported behavior represented explicitly rather than silently delegated.
- Task 10 makes q=0 reconstruction architectural: live q=0 traversal remains running until a stable bounded residual is reached; only then is `QUANTUM_EXHAUSTED` visible.
- `RECHARGE_QUANTUM` continues the same processor memory/state. Result relinearization is bounded/fixed-scratch and preserves live lambda/structure continuations, including overlapping source/destination cases proven by the accepted regressions.

These statements are the implementation checkpoint from which the remaining design proceeds. They do not imply that host effects, whole-program lockstep, real synthesis, or board transport are already complete.

## 7. Quantum boundary

Semantic contractions decrement q exactly where the architectural oracle does. Hardware clocks, memory stalls and reconstruction traversal do not independently consume q.

When q reaches zero, the reducer performs the ordinary non-firing traversal/reconstruction needed to produce RED2's stable residual graph. `QUANTUM_EXHAUSTED` is therefore a scheduler-visible boundary over a valid bounded residual, not a snapshot of an arbitrary partially executed instruction.

Recharging q mutates the existing live processor state and resumes reduction without recompiling, reloading, replacing RAM, or replacing the machine object. Compaction/relinearization at this boundary must preserve graph sharing and every live continuation represented by the accepted machine state.

## 8. Host-call suspension and resume

The next architectural extension is a transport-independent host trap for the RED2 semantic host primitives `CLOCK`, `UART-RX`, `UART-TX`, and `UART-TX-BYTES`.

A host call becomes visible only when the primitive actually fires with positive q. Suspension records a finite request sufficient for the host to service the effect and for the processor to resume the same redex. While suspended, clocks may not advance RED2 architectural state, issue the effect again, decrement q again, or alter the pending request.

`RESUME_HOST_CALL(value)` validates the resume against the pending operation and current machine state, publishes the permitted atomic result into the correct graph/result location, performs the oracle-required q/state update exactly once, clears pending status, and resumes the same machine. Invalid, stale or unsupported resume values fault without partial publication.

This design intentionally preserves the current restriction to atomic host-return values. Structured graph-owned host results require a separately authorized publication design. The semantic RED2 primitive named UART is distinct from whatever physical UART/JTAG framing may later carry the processor control protocol.

## 9. Logical host ABI

The control interface is transport-independent and converges on the following logical operations/statuses:

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

A debug single-transition operation may exist for verification. The logical ABI is authoritative over the later physical transport. Retries/backpressure at the transport layer must not duplicate committed LOAD/RUN/RESUME operations or semantic host effects.

## 10. Differential proof strategy

Correctness is established against `MuredMachine` at three layers.

**Transition vectors.** The same encoded architectural pre-state plus relevant memory/control contents must produce the same committed post-state, writes, fault, quantum suspension, or host suspension.

**Trace lockstep.** The same compiled RED2 image runs in both machines; normalized checkpoints compare every architectural register, live memory/control mutation, status and host-call field while excluding implementation-only microstates and diagnostics. A divergence report identifies the first mismatching transition and minimal differing state.

**Program exams.** Real compiled THOR/RED2 fixtures exercise long pure reductions, closures, recursion, structures, equality, repeated q exhaustion/recharge and deterministic host effects. The host may compile/load/schedule/service declared effects but may not become a second evaluator.

The final accepted corpus must contain non-trivial programs with hundreds or thousands of committed RED2 transitions and deterministic IO sequences. `clock-dots.thor` is an early host-call acceptance target; interactive games such as Breakout are natural later end-to-end demonstrations after the host boundary and physical/toolchain work are proven.

## 11. Pypeline/PipelineC and synthesis boundary

Python simulation alone does not establish synthesizability. After semantic parity is complete, the actual installed/cloned Pypeline/PipelineC frontend must accept the processor top. Generated HDL must elaborate and, in the provisioned hardware gate, reach a real synthesis smoke result for a documented generic or Basys-3-compatible target.

Ordinary repository tests remain dependency-light. The explicit hardware gate, however, must fail clearly if required external tooling is unavailable; missing tools are a provisioning blocker, not a successful skipped synthesis result. Generated/vendor artifacts remain untracked unless a later decision explicitly makes them source artifacts.

## 12. Basys 3 transport shell

The physical shell is replaceable infrastructure around the logical RED2 host ABI. UART is the simplest candidate, but protocol semantics—not UART itself—are the contract.

Frames for RESET/LOAD/START/RUN/RECHARGE/RESUME/READ_STATE/READ_MEM must be bounded and unambiguous, with deterministic malformed-frame/error responses. Backpressure, retransmission and duplicate frames cannot duplicate machine commits or semantic effects. If semantic `UART-TX` host calls share a physical UART with the control channel, framing/tagging must distinguish the two layers explicitly.

The shell contains no THOR compiler and no RED2 evaluator. Replacing UART with JTAG or another transport must not change reducer semantics.

## 13. Acceptance and non-goals

Integrated acceptance requires all of the following together: persistent processor-owned RED2 state; accepted pure semantic coverage; stable q=0 residualization and same-machine recharge; exactly-once host suspension/resume; transition/program lockstep with the Python oracle; non-trivial compiled THOR execution wholly through RED2; successful real Pypeline/PipelineC frontend plus provisioned HDL/synthesis smoke; a separable Basys 3 host shell; and unchanged `archives/` / `thesis-transcription/` evidence.

Explicit non-goals are a RED2 operating system, multiple simultaneous machine contexts, FPGA-hosted THOR compilation, a Rust rewrite prerequisite, one RED2 transition per physical clock, turning every primitive into a host effect, editing historical sources, or claiming physical board bring-up when only synthesis/protocol simulation is available.

The remaining implementation authority is carried by Tasks 11–16 of `docs/superpowers/plans/2026-09-11-full-pypeline-red2-processor-ultraplan.md`. This backfilled design record exists because the original September 11 plan omitted its separate spec artifact; it preserves the already reviewed checkpoint rather than rewriting its history.

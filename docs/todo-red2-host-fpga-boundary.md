# TODO: RED2 Host / FPGA Boundary Architecture

## Summary

Historical source inspection suggests that Hilton's systems already had a recognizable host/reducer split, but the modern Asgard `MuredMachine -> HOST_CALL -> host -> resume_host_call()` design pushes that boundary lower and makes it substantially more suitable for an FPGA implementation.

The key architectural conclusion is:

> The host should compile/load/manage programs and service external effects. The FPGA should own RED2 architectural state and reduction. Host calls should suspend the live machine and resume it in-place rather than reconstructing execution from a residual graph.

This document records the historical findings and a proposed Asgard hardware/software boundary.

---

## Historical finding 1: the Scheme RED2 simulator already separates preparation from execution

`archives/COMMON/REDUCER.S` contains a convenience-level `reduce` wrapper, but internally its phases are distinct.

`prep-reducer`:

1. Compiles a lambda expression with `compile-exp`.
2. Prepends a `START` control instruction.
3. Loads the resulting LAC into machine memory with `load-lac`.
4. Sets `PGAR` to `problem-addr`.
5. Establishes `RGAR` / `result-addr` immediately after the loaded problem graph.
6. Initializes the stack and environment pointers.
7. Sets `mode` to `PROBLEM`.
8. Resets instrumentation counters.

Then `red` enters the reducer by setting `next-reduction-step` to `next-instruction` and running the explicit reduction loop.

Conceptually, the simulator already has this structure:

```text
host / simulator
    |
    | compile-exp
    | load-lac
    | initialize memory/registers
    v
RED2 machine
    |
    | execute until STOP / reduction limit
    v
result graph
    |
    | decompile-exp
    v
host expression
```

The fact that compiler, loader, execution loop, and decompiler live in one Scheme process should not obscure the underlying machine boundary.

---

## Historical finding 2: START and STOP are architectural instructions

In `archives/FP/INSTRUCT.S`, `START` is explicitly documented as an instruction that initializes reducer state and deposits a `STOP` instruction.

It resets machine-visible state including:

- argument count
- reduction count
- binding offset
- inhibition state
- primitive registers / argument registers

`STOP` is the architectural signal for the end of the reduction sequence. Encountering it in result mode invokes the successful-reduction continuation.

This makes the RED2 simulator look much more like a processor than like an ordinary recursive evaluator:

```text
LOAD memory
SET PGAR
RUN
     ...
STOP encountered
RETURN result root
```

---

## Historical finding 3: the GUI is a processor monitor, not part of the machine

`archives/WINDOWS/INTERFAC.S` describes itself as the graphic interface for the lambda processor simulator. It displays processor state and highlights operations, but the machine semantics are independent of the GUI.

The register pane exposes architectural state including:

- `PGAR`
- `PGDR`
- `RGAR`
- `RGDR`
- `ENVDR`
- `argcount`
- `binding-offset`
- `mode`
- `reductions`
- `red-limit`
- `scratch`
- `temp`
- `primreg`
- `argreg`
- `inhibit`

The reducer's UI interactions are wrapped in optional `show(...)` instrumentation.

This supports a clean interpretation: the GUI was effectively a debugger / front-panel monitor attached to a RED2 processor model.

---

## Historical finding 4: HORSE exposes a very small reducer ABI

The C HORSE/THOR system in `archives/THOR/` exposes a particularly simple reducer entry point:

```c
node *reduce(
    node *start,
    node *workspace,
    node *freespace,
    int reds_allowed,
    int recursive
);
```

The arguments are approximately:

- problem graph root
- start of result/work graph space
- start of free/environment space
- reduction budget
- recursive-invocation flag

The normal HORSE REPL path compiles the expression graph and then calls roughly:

```c
result = reduce(problem, result, high, -1, FALSE);
```

So the historical HORSE/reducer boundary can be summarized as:

```text
problem_graph_root
result_workspace_start
free/environment_space_start
reduction_budget
        |
        v
      REDUCE
        |
        v
result_graph_root
```

That is surprisingly compact.

---

## Historical finding 5: HORSE stepping is residual-graph continuation, not machine suspension

The HORSE manual describes step mode as allowing a bounded number of reductions using commands such as `,1` and complete reduction with `,,`.

However, the C implementation does **not** preserve the live reducer state across those user-visible steps.

`reduce()` initializes state such as:

```text
pc = start
ws = workspace
fs = freespace
argcount = 0
env = freespace
mode = PROBLEM
reductions = 0
stack = initial stack
aux = initial aux
...
```

After a bounded reduction, HORSE keeps the residual graph. On the next step it copies/moves that residual graph back into problem space and calls `reduce()` again.

So historical stepping is approximately:

```text
G0
 |
 | reduce N
 v
G1
 |
 | rebuild machine around G1
 | reduce N
 v
G2
```

rather than:

```text
machine state S0
 |
 | execute N work
 v
S1 ---- suspend
        |
        | resume
        v
       S2
```

This is an important distinction for Asgard.

---

## Historical finding 6: the Scheme RED2 reduction limit behaves similarly

The Scheme machine also has a `red-limit`, but it is fundamentally a reduction-semantic limit rather than a hardware-style execution quantum.

Instructions compare `reductions` to `red-limit`; when the budget is exhausted, further contractions are inhibited while traversal/reconstruction continues until the machine reaches a valid residual result and eventually `STOP`.

This allows the historical system to return a valid residual graph and later restart from that graph without preserving all architectural state.

That design is suitable for an interactive symbolic reducer, but is not the ideal interface for an actual hardware processor.

---

## Asgard improves the boundary by moving it down to live machine state

Hilton's historical systems expose approximately:

```text
REDUCE(graph, reduction_budget) -> graph
```

Asgard's evolving interface is closer to:

```text
RUN(machine_state, execution_budget)
    -> COMPLETE
     | QUANTUM_EXHAUSTED(machine_state)
     | HOST_CALL(machine_state, operation)
     | FAULT(machine_state, reason)
```

This is much more natural for FPGA hardware.

The machine remains alive across suspension. Its graph, environment, stacks, registers, and traversal state do not need to be reconstructed from a residual expression.

---

## Proposed Asgard host / FPGA architecture

The near-term architecture should treat RED2 as a processor or coprocessor controlled by a host runtime.

```text
        ASGARD HOST
 +---------------------------+
 | THOR compiler             |
 | graph loader              |
 | debugger / monitor        |
 | host-call services        |
 | program lifecycle         |
 +-------------+-------------+
               | machine ABI
               v
 +---------------------------+
 |       RED2 PROCESSOR      |
 |                           |
 | PGAR PGDR RGAR RGDR       |
 | ENV / stacks / registers  |
 | graph + environment RAM   |
 | reduction control         |
 +---------------------------+
```

The host owns policy and external integration. The FPGA owns reduction semantics and live machine state.

This is conceptually **HORSE reborn, except with the reducer actually being a processor this time.**

---

## Proposed machine ABI

A first hardware-facing Asgard ABI could be intentionally small:

```text
RESET

LOAD(address, words...)

START(
    root,
    graph_limit,
    env_limit,
    stack_limit
)

RUN(quantum)
    -> COMPLETE(result_root)
    -> QUANTUM_EXHAUSTED
    -> HOST_CALL(op, args)
    -> FAULT(code)

RESUME_HOST_CALL(value)

READ_MEM(address, count)
READ_STATE()
```

`STEP` may exist as a debugger convenience, but does not need to be part of the fundamental execution model if `RUN(quantum)` already provides bounded progress.

The exact meanings of `quantum` and the stop boundary still need to be specified carefully. The important property is that quantum exhaustion should suspend the existing machine rather than convert live execution into a residual graph and restart it later.

---

## What should remain on the host

The following should **not** initially be FPGA responsibilities:

- parsing THOR
- compiling THOR to RED2
- graph decompilation / pretty-printing
- filesystem access
- debugger UI
- program loading policy
- process lifecycle policy
- host clock implementation
- terminal / keyboard policy
- UART protocol policy
- scheduling between RED2 programs

These belong in the Asgard host/runtime initially.

That boundary can later move experimentally if self-hosting parts of the system in RED2 becomes useful or interesting.

---

## What the FPGA should own

The FPGA implementation should own the architectural RED2 state and the rules that mutate it:

- problem/result graph registers (`PGAR`, `PGDR`, `RGAR`, `RGDR` or their modern equivalents)
- environment state
- control / auxiliary stacks
- primitive registers
- argument/binding state
- graph and environment memory
- traversal direction / mode
- instruction decode
- graph mutation
- reduction counts / execution accounting as architecturally defined
- suspension state
- host-call request state

At semantic transition boundaries, the FPGA should agree with the Python reference machine.

Hardware may use many physical clock cycles for one RED2 semantic transition; the ABI and conformance model should not require one RED2 transition per FPGA clock.

---

## HOST_CALL is the key extension beyond the historical systems

The most important difference between Asgard and the historical interfaces is first-class host-effect suspension.

External operations such as:

- CLOCK
- UART-RX
- UART-TX
- UART-TX-BYTES
- future filesystem/network/device services

should suspend exactly when the primitive fires.

The host services the request and resumes the **same** machine via something like:

```text
HOST_CALL(op, args)
        |
        v
      host
        |
        | result value
        v
RESUME_HOST_CALL(value)
```

The host must not evaluate the continuation, traverse the graph on behalf of RED2, or create a second evaluator.

This directly preserves the current single-machine invariant:

> One THOR run -> one RED2 machine.

That invariant is not merely a Python-runtime cleanup. It appears to be an excellent prototype of the eventual FPGA/software boundary.

---

## Architectural evolution

There is a useful historical progression:

```text
1989 Scheme:
  (reduce expression) -> expression

1990 HORSE:
  reduce(graph, workspace, freespace, budget) -> graph

2026 Asgard:
  run_until_suspend(machine) -> stop reason

future FPGA:
  command/MMIO interface -> RED2 processor -> interrupt/host call
```

Each generation moves the external interface closer to the actual machine.

The Asgard design should keep that trajectory rather than reproducing HORSE's residual-graph stepping API literally.

---

## Suggested development direction

Before committing to a physical FPGA transport protocol, define the **logical machine ABI** independently of UART, AXI, MMIO, USB, or any specific board.

The Python `MuredMachine` should implement that logical contract first. The Lean model and FPGA implementation can then implement the same state transitions and stop reasons.

A later transport can map that ABI onto, for example:

```text
Basys 3 phase:
    desktop host <-> USB-UART/JTAG <-> RED2 FPGA

integrated SoC phase:
    ARM/RISC-V host <-> AXI/MMIO <-> RED2 FPGA fabric
```

This prevents an early board-specific wire protocol from accidentally becoming the architectural definition.

---

## Open questions / TODO

- [ ] Define the exact architectural state that must survive `QUANTUM_EXHAUSTED`.
- [ ] Decide whether `quantum` counts RED2 semantic transitions, instruction dispatches, reductions, memory cycles, or another unit.
- [ ] Define the precise suspension point for `HOST_CALL`.
- [ ] Specify what data is carried by a host-call request.
- [ ] Specify how a host-call result is written back into machine state.
- [ ] Define `COMPLETE` precisely: STOP reached, result root location, and required final invariants.
- [ ] Define fault classes that are architectural versus host/runtime errors.
- [ ] Decide which state is always inspectable through `READ_STATE` for debugging.
- [ ] Define a portable graph-image format suitable for Python, Lean tests, FPGA loading, and a future Rust runtime.
- [ ] Generate transition/conformance vectors from the Python reference implementation.
- [ ] Compare the eventual ABI explicitly against the historical Scheme START/STOP behavior and C HORSE `reduce(...)` contract.
- [ ] Keep transport-specific details (UART, AXI, MMIO) outside the semantic ABI specification.

---

## Working conclusion

The historical archive supports the host/reducer architecture rather than arguing against it.

Hilton's systems already separated a user/compiler environment from a graph reducer, and HORSE exposed an impressively small reducer interface. But both historical implementations use residual graphs as their resumable boundary.

Asgard's live-machine suspension model is a more appropriate abstraction for real hardware:

```text
compile/load on host
        |
        v
run RED2 in hardware
        |
        +--> COMPLETE
        |
        +--> QUANTUM_EXHAUSTED -- resume same machine
        |
        +--> HOST_CALL --------- service externally, resume same machine
        |
        +--> FAULT
```

That should be treated as the provisional architectural direction for a RED2 FPGA implementation.

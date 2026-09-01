# Faithful Python μRED Core Design

## Goal

Build a small executable Python specification of the pure λ-calculus μRED machine described in Chapter 4 of Hilton's dissertation. The implementation must execute the thesis's graph-memory instructions and register transfers directly. It must not decode the instruction graph into an AST or private term graph for evaluation.

This is the first step toward a faithful RED2 implementation. Full THOR/RED2 instructions, Rust, FPGA work, and the existing command-line runners are outside this milestone.

## Current Problem

The existing Python `red2_engine.machine.Red2Machine` exposes RED2-like registers and instruction memory, but it decodes instructions into a private term graph and evaluates that graph. The existing Rust executor similarly reconstructs an expression tree before reduction. Consequently, neither implementation executes the Chapter 4 graph machine, and final-result parity does not establish machine fidelity.

The new implementation will be isolated from these evaluators so that old abstractions cannot accidentally substitute for the thesis execution model.

## Scope

Create `models/python/red2_engine/mured.py` as an independent μRED core for the pure λ-calculus. It will implement:

- a fixed-size shared memory containing graph memory at the low end and the environment at the high end;
- a separate fixed-size control stack;
- the `pc`, `fsp`, `env`, `c`, direction, `q`, and `phi` registers;
- scratch address and data registers corresponding to the thesis's `s_a` and `s_d`;
- `APP`, `CLOSURE`, `JOIN`, `LAMBDA`, `STOP`, `UBV`, and `VAR` transitions;
- `PNP` environment words;
- the thesis's `LOOKUP` procedure;
- one-instruction machine stepping;
- pure-lambda problem-graph loading and halted-result decompilation.

The first milestone does not replace `red2_engine.machine.Red2Machine`, alter a CLI, or change the `.red2` format.

## Architecture

### Independent machine core

`mured.py` will define a small μRED word representation, machine state, error hierarchy, and `MuredMachine`. It must not import or construct the private term types in `red2_engine.machine`.

The machine state contains:

- one addressable shared-memory array;
- a graph region growing upward from address zero;
- an environment region growing downward from the top of shared memory;
- a separate control-stack array;
- `pc`, pointing to the instruction currently executed;
- `fsp`, pointing to the current end of graph memory as defined by the thesis;
- `env`, pointing to the tip of the current environment path;
- `c`, identifying the control-stack top;
- direction `F` or `B`;
- contraction quantum `q`;
- binder depth `phi`;
- scratch registers `s_a` and `s_d`;
- halted state and host-visible cycle count.

The representation will keep addresses as integer word indexes. Closures occupy exactly two consecutive environment words: a `CLOSURE` word holding an environment-path pointer followed by a word holding a graph-code pointer.

### Loading

A loader accepts a pure-lambda problem graph, places it at the bottom of shared memory, and places `STOP` immediately after it. It initializes the machine exactly as Chapter 4 specifies:

- `pc` points to the first problem instruction;
- `fsp` points to the `STOP` word;
- graph and environment areas do not overlap;
- the environment and control stack are empty;
- direction is forward;
- `q` is the requested quantum;
- `phi` is zero.

A small pure-lambda compiler may convert Thor AST input into the linear instruction graph before loading. This conversion is not part of execution.

### Stepping

`MuredMachine.step()` performs exactly one machine cycle:

1. Validate the current register addresses and region boundaries.
2. Fetch the word at `pc`.
3. Dispatch on its opcode.
4. Apply the corresponding Chapter 4 register transfers.
5. Increment the host-visible cycle counter.
6. Validate the resulting machine state.

Each instruction has a focused transition handler whose implementation remains visibly comparable with the dissertation pseudocode. `run()` only loops over `step()` until `STOP`, error, or a host cycle limit; it adds no reduction semantics.

No execution path may reconstruct an AST, recursively evaluate a term, invoke the existing Thor evaluator, or replace several machine instructions with one host-level β-reduction.

### Result inspection

When `STOP` halts the machine, `pc` identifies the root of the result graph. A separate decompiler may inspect that graph and reconstruct a Thor expression for assertions and display. Decompilation occurs only after execution and must not mutate machine state.

## Machine Invariants

The implementation will enforce these invariants:

- Problem and result graph words occupy low shared-memory addresses.
- Environment words occupy high shared-memory addresses and grow downward.
- Graph growth must never meet or pass environment growth.
- `pc` references a valid graph or environment word appropriate to the active transition.
- `fsp` follows the exact Chapter 4 convention rather than a host container convention.
- The control stack has explicit capacity and top position.
- A closure is always a valid two-word environment object.
- `PNP` links reference valid environment paths.
- Forward and backward execution are explicit state.
- Quantum changes only at contractions identified by the thesis rules.
- `step()` executes one fetched instruction transition, not one contraction.
- `run()` cannot conceal extra transitions.

## LOOKUP

`LOOKUP` will follow the Chapter 4 procedure literally. Starting at `env`, it traverses the current path until reaching the requested De Bruijn index:

- a `PNP` follows its parent address;
- a `UBV` advances by one environment word when skipped;
- a closure advances by two environment words when skipped;
- finding index zero leaves the value address in `s_a`;
- malformed paths produce a machine error rather than falling back to host-language environment lookup.

## Error Handling

Use narrow deterministic machine errors for:

- invalid memory addresses;
- graph/environment collision;
- control-stack overflow and underflow;
- malformed or truncated closures;
- invalid parent-path pointers;
- illegal opcode/direction combinations;
- malformed problem graphs;
- a host cycle limit reached before halt.

The host cycle limit is a debugging and test guard. It is distinct from Thor's contraction quantum and must not alter machine state as though a reduction quantum had expired.

## Testing Strategy

### Instruction transition tests

Construct minimal machine states and execute one instruction. Assert all affected state, including:

- written or reclaimed memory words;
- `pc`, `fsp`, `env`, `c`, direction, `q`, and `phi`;
- control-stack contents;
- closure and parent-pointer layout.

Cover both legal directions where an instruction defines both, plus illegal direction combinations.

### LOOKUP tests

Cover:

- finding the current-path value;
- skipping `UBV` values;
- skipping two-word closures;
- following one and multiple `PNP` links;
- invalid indexes and malformed environment paths.

### Boundary tests

Cover:

- graph/environment collision;
- invalid graph and environment pointers;
- control-stack overflow and underflow;
- malformed closures;
- cycle-limit exhaustion without using subprocess timeouts.

### Golden cycle traces

For small pure-lambda expressions, record the complete machine sequence:

```text
cycle, opcode, direction, pc, fsp, env, c, q, phi
```

At least one committed trace will be manually derived from Chapter 4's register-transfer rules. It must not be generated from either existing evaluator.

### Semantic checks

After halt, decompile the result graph and compare it with the Chapter 3 Thor evaluator for a deliberately small pure-lambda corpus:

- identity application;
- nested application;
- captured variables;
- reconstruction of free variables;
- zero quantum;
- limited quantum.

Semantic parity is supplementary. It cannot replace transition and trace assertions.

### Anti-shortcut checks

Tests or static checks will ensure:

- `mured.py` does not depend on private term/evaluator types from `red2_engine.machine`;
- execution tests inspect intermediate machine state;
- the machine can be advanced exactly one transition;
- result decompilation is not invoked by `step()` or `run()`.

## Acceptance Boundary

The milestone is complete when the pure λ-calculus subset can:

1. compile or load a linear μRED problem graph;
2. initialize the Chapter 4 memory regions and registers;
3. execute one exact register-transfer transition per cycle;
4. traverse graph and environment memory using the μRED instructions and `LOOKUP`;
5. halt through `STOP`;
6. expose a result graph that can be decompiled after halt;
7. pass instruction-level, boundary, golden-trace, and small semantic tests.

## Deferred Work

The following are explicitly deferred:

- head-flag and single-instruction-argument optimizations;
- passive constants and symbols;
- definition lookup;
- strict primitives and primitive firing registers;
- structures;
- `LETREC`, `RBLOCK`, `RUP`, `RECP`, and `REC`;
- simulator I/O;
- integration with the current Python RED2 CLI;
- replacement or removal of the existing evaluator-backed `Red2Machine`;
- a faithful Rust RED2 port;
- FPGA memory sizing, buses, and synthesis;
- Thor modules or hardware components.

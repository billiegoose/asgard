# THOR Trampoline and RED2 Resource Limits Design

## Goal

Replace host-recursive THOR evaluation and IO execution with explicit iterative stacks, and add deterministic bounded stack/heap accounting for the Python RED2 VM with CLI flags.

## Scope

- THOR reference evaluator: host-stack safety only. Deep THOR recursion must not surface as Python `RecursionError`.
- THOR IO runtime: action sequencing must be iterative, including Y-defined recursive actions such as `examples/clock-dots.thor`.
- RED2 Python machine: explicit stack and heap byte limits with deterministic RED2-level exceptions.
- CLI: `--stack-size-in-bytes INT` and `--heap-size-in-bytes INT` are supported for RED2 execution paths and rejected for THOR/parity when explicitly supplied.
- Tests: regression coverage for host-stack safety, `clock-dots.thor`, and configurable RED2 resource exhaustion.

## Architecture

The THOR evaluator keeps its public `reduce_expr(...) -> ReductionResult` API and quantum semantics but internally uses a trampoline/evaluation-stack driver instead of Python recursion. The driver represents continuation points as explicit frames for application reduction, primitive continuations, lambda/structure contraction, LETREC/REC reconstruction, and no-contract rebuilding.

The IO runtime similarly replaces recursive `run(...)` calls with an explicit action loop. Current action plus continuation frames represent `IF`, top-level lambda-defined actions, `IO-BIND`, `IO-THEN`, and primitive device operations. Pure expression evaluation continues through the THOR or RED2 model selected by the caller.

RED2 receives a deterministic resource-accounting layer. Stack accounting measures explicit VM evaluation/control frames rather than Python frames. Heap accounting measures deterministic VM allocations such as parsed terms, closures, recursive cells, and emitted result graph nodes. Limits raise RED2-specific errors before Python recursion or memory behavior leaks through.

## Error Handling

- THOR evaluator/IO should not raise `RecursionError` for deep THOR recursion under tested scenarios.
- RED2 stack overflow raises `Red2StackOverflowError` with a stable message containing `RED2 stack overflow`.
- RED2 heap exhaustion raises `Red2HeapExhaustedError` with a stable message containing `RED2 heap exhausted`.
- CLI catches these through the existing runtime error path and prints `thor-spec: ...` with exit code 2.
- Explicit THOR/parity resource-limit use exits 2 with `resource limits are currently supported for red2 only`.

## CLI Behavior

- Add defaults for RED2 stack and heap limits.
- `thor-spec --model red2 ...`, `thor-spec red2 ...`, and `thor-spec run-red2 ...` accept and enforce both flags.
- `thor-spec --model thor ...`, `thor-spec thor ...`, and `thor-spec --model parity ...` reject explicit resource-limit flags.
- Existing commands without the new flags continue to work with sensible defaults.

## Testing Strategy

- Unit tests pin THOR trampoline behavior under a deliberately low Python recursion limit.
- IO tests exercise a deep action chain and `examples/clock-dots.thor` using a deterministic clock.
- RED2 machine tests cover stack overflow, heap exhaustion, and success with larger limits.
- CLI tests cover RED2 flag pass-through and THOR/parity rejection.
- Final verification runs focused tests plus the full Python test suite.

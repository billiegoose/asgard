# Rust VM Loop Architecture Design

## Goal

Make the Rust RED2/WASM engine robust against unbounded host recursion by moving evaluator control flow to explicit VM loops/stacks, and make stuck strict primitive applications fail with clear errors.

## Requirements

- Rust native and WASI execution must not depend on host call-stack depth for ordinary THOR/RED2 looping, IO sequencing, or tail-position lambda/control transitions.
- The engine should follow a VM shape: a loop over explicit state and `match` transitions rather than recursive self-calls for control flow.
- Bytecode format and compiler output remain unchanged.
- Breakout’s full deterministic WASM recording playthrough remains supported.
- Deep generated IO sequencing must complete without stack overflow.
- Strict primitive operations must error when their arguments cannot reduce to supported values.
  - Examples: `(+ 1 frog)`, `(MINUS frog)`, `(UART-TX frog)`, and `(IF frog 1 2)` should fail rather than preserve an unknown/stuck expression.
  - This is a runtime error for now, not a typed effect or recoverable THOR value.
- The stdout/stderr policy remains: stdout is device output; errors go to stderr through the CLI wrapper.

## Architecture

The current Rust engine already parses `.red2` bytecode into an expression tree, so this change does not introduce a bytecode program counter. Instead it makes the expression evaluator itself a stack machine:

- `Reducer::reduce` runs a `loop` over `(expr, env)` state.
- Tail-position symbol resolution, variable forcing, closure forcing, `IF`/`AND`/`OR`, and full-arity lambda application transition by replacing loop state, not by recursive self-calls.
- Non-tail primitive argument evaluation can still call `reduce` on subexpressions, but primitives must validate that their reduced arguments are concrete values of the expected kind and return `Red2Error` for unknown/stuck values.
- `IoRunner::run_action` runs a `loop` over `(action, env)` plus an explicit `Vec<IoFrame>` continuation stack for `IO-BIND` and `IO-THEN`.
- IO actions such as `UART-RX`, `UART-TX`, `UART-TX-BYTES`, and `CLOCK` return values into the explicit continuation stack.

This gives the Rust engine the normal VM architecture: the host stack is not the program stack. Structural tree walks such as parsing bytecode, computing needed captured environment depth, or rendering `to_source` may remain recursive because they are bounded by expression structure, not by runtime loop iterations.

## Testing Strategy

Add regression tests that would fail under host recursion:

- A 70-tick `mise run wasm examples/breakout.thor --clock ...` playthrough completes.
- `mise run generate-video breakout-wasm --no-upload` produces a long, real, trap-free cast.
- Rust unit/CLI tests cover strict primitive failures for unknown symbols and invalid IO arguments.
- Existing Rust, Python, docs, and recording tests remain green.

## Non-goals

- Do not implement `Y`, `LETREC`, or non-PAIR structures beyond existing support.
- Do not introduce a user-visible THOR error effect yet.
- Do not rewrite the Python model in this phase.

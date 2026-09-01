# RED2 Head-Flag and Integer Slice Design

## Goal

Evolve `models/python/red2_engine/mured.py` in place from the faithful pure-lambda μRED core into the first faithful RED2 slice by representing spine-head flags and executing passive integer instructions directly.

## Scope

This slice adds:

- a Boolean head flag on every `Word`;
- compiler-assigned head flags for existing lambda graphs;
- opcode `INT` with an integer data field;
- Chapter 4 `INT` forward and reverse transitions;
- compilation and halted-result decompilation of `thor_lang.ast.Integer`;
- cycle-level tests for head and non-head `INT` behavior;
- semantic parity checks for closed expressions containing integers.

It does not add APP-VAR/single-instruction-argument compaction, primitives, symbols, floats, characters, structures, recursion, CLI integration, Rust, or evaluator shortcuts.

## Architecture

The existing module and public `MuredMachine`, `MuredMachineState`, `MuredOpcode`, and `Word` names remain temporarily for compatibility. `Word` gains `head: bool = False` after `data`, preserving existing positional construction. `MuredOpcode` gains `INT`.

The compiler marks instructions according to the linear graph representation:

- `APP` words and copied `LAMBDA` words are not heads;
- the operator root of each spine is a head;
- every separately addressed APP argument graph has its own head;
- a lambda body inherits the surrounding spine's head position;
- an integer root receives the head position passed by the compiler.

Because APP-VAR compaction is deferred, source compilation does not inline single-word arguments into a parent spine. Therefore compiled integer argument roots remain heads of their separately addressed graphs. A manually loaded non-head `INT` is still executed literally and tested, establishing the transition needed by later compaction.

## INT Transition

For `INT` in forward direction:

1. Copy the complete word, including `head`, to `fsp + 1`.
2. If `head` is true, set `pc` to `fsp - 1` after the push and switch to reverse direction.
3. Otherwise increment `pc` and remain forward.

For `INT` in reverse direction, decrement `pc`. No other register changes. Integer execution never changes `q`, `phi`, `env`, or the control stack.

## Compilation and Results

The existing `compile_lambda()` entry point evolves to accept `Integer` in addition to the pure-lambda AST forms. This is intentionally a temporary legacy name while `mured.py` evolves incrementally. `MuredMachine.load()` accepts source `INT` words. `_decompile()` reconstructs `Integer(value)` and rejects malformed non-integer payloads.

Existing pure-lambda behavior and cycle ordering must remain unchanged apart from expected head metadata on words. Execution remains direct graph-memory dispatch; `step()` and `run()` must not invoke either decompilation or the Chapter 3 evaluator.

## Validation

Tests must cover:

- exact compiler flags for identity, nested lambda, application operator, and separately addressed argument roots;
- preservation of flags when words are copied to the result graph;
- forward head `INT`, forward non-head `INT`, and reverse `INT` register transfers;
- top-level `42`, `(LAMBDA (x) 42)`, and `((LAMBDA (x) x) 42)`;
- zero-quantum reconstruction containing an integer;
- malformed `INT` data;
- unchanged μRED transition, golden-trace, and anti-shortcut suites.

## Source Reconciliation Boundary

This slice follows the Chapter 4 head-flag and INT pseudocode directly. It deliberately does not claim the chapter's single-instruction-argument optimization until APP-VAR/generalized inline arguments are implemented.

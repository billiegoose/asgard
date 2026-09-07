# Ultraplan: One μRED Machine Per Program, Host-Dispatched IO

## Problem statement

The current Python RED2 IO implementation is architecturally wrong for the intended machine model.

Today `red2_engine/io_runtime.py` is effectively a second evaluator. It interprets `IO-BIND`, `IO-THEN`, `IO-RETURN`, effect calls, lambdas, and action exposure at the THOR AST level, and repeatedly asks μRED to evaluate small pure fragments by constructing fresh `MuredMachine` instances. The caches added in `37886f4` make that implementation fast enough to run Breakout, but they optimize the wrong boundary.

The intended invariant is stronger:

> **One THOR program execution creates exactly one `MuredMachine`. That same machine owns the graph for the entire execution.**

IO does not create a second evaluation regime. Monad sequencing is represented by graph/data dependence. μRED reduces the program normally. When reduction reaches a primitive that requires the outside world, the machine dispatches that primitive to its host, incorporates the returned value into the existing graph, and continues reducing the same machine.

The quantum is likewise a property of the running machine, not a reason to tear it down. Exhausting the quantum is a suspension/preemption point. The host may recharge the quantum and resume the same machine.

## Architectural invariants

1. **Exactly one machine instance per program run.**
   - `run_io_source(..., model="red2")` may load/instantiate μRED exactly once.
   - No per-expression `load_faithful_machine(...)` calls.
   - No per-action μRED reconstruction/recompilation cycle.

2. **The μRED machine remains the evaluator.**
   - Python host code must not interpret lambda application, `Y`, `IF`, arithmetic, definition calls, or monadic sequencing by repeatedly round-tripping through THOR AST.
   - Those remain graph reductions performed by the machine.

3. **Host IO is a machine suspension/trap, not a second interpreter.**
   - When μRED reaches a host primitive such as `CLOCK`, `UART-RX`, `UART-TX`, or `UART-TX-BYTES`, it exposes a typed host-call request.
   - The runtime invokes the corresponding `Red2IoHost` method.
   - The result is written back into the *same* machine/redex and execution resumes.
   - A fired host primitive must be updated/replaced in the graph so it cannot execute twice merely because the graph is revisited.

4. **Monad sequencing comes from dependency.**
   - `IO-BIND`, `IO-THEN`, and `IO-RETURN` must execute as normal RED2-visible program semantics, not as Python AST control flow.
   - The continuation cannot proceed until the preceding action produces the value on which it depends.
   - The implementation may use μRED primitives or a compiled prelude, but the host runtime must not walk IO action ASTs.

5. **Quantum exhaustion is resumable.**
   - Quantum is a contraction budget / scheduling mechanism.
   - Reaching zero must yield a suspension/preemption state that can be recharged.
   - Recharging must continue the same machine and graph.
   - It must not instantiate a new machine or recompile/reload the program.

6. **Normal completion is distinct from suspension.**
   - Machine outcomes must distinguish at least:
     - completed / normal form,
     - quantum exhausted / preempted,
     - host call pending.

7. **No correctness cache is required to make IO viable.**
   - Static compilation caching may remain as a compiler/load optimization.
   - The per-run `(Expr, quantum) -> Expr` memoization cache added in `37886f4` should disappear from the runtime once the single-machine execution path exists.
   - Performance should come from retaining machine state, not memoizing repeated RPC-like reducer requests.

8. **Breakout, Pong, Hangman, and stack-safety remain acceptance tests.**
   - Existing visible behavior must remain unchanged.
   - Deterministic Breakout RED2 stdout must equal THOR stdout byte-for-byte and end in the real `QUIT\n` marker.

## Phase 0 — Recover the machine/thesis semantics

Before changing state transitions, inspect the thesis notes/source and current implementation for:

- what `q` means formally;
- exactly where contractions decrement `q`;
- what the reconstruction phase does at `q == 0`;
- whether the thesis explicitly describes recharging/restarting a quantum;
- whether reconstruction leaves a graph that can be entered again without reloading;
- whether process switching or fairness is part of the motivation;
- current primitive firing machinery and redex/update semantics.

The implementation must follow the machine semantics rather than infer a new meaning for `q` from the CLI.

## Phase 1 — Add explicit machine suspension API

Introduce an explicit result/status from machine execution rather than overloading `halted` for every stop reason.

Target shape (names may change to match the codebase):

```python
class MuredStopReason(Enum):
    COMPLETE = "complete"
    QUANTUM_EXHAUSTED = "quantum-exhausted"
    HOST_CALL = "host-call"

@dataclass(...)
class MuredHostCall:
    primitive: str
    arguments: tuple[Expr | machine-value, ...]
    # enough machine/redex state to resume without reload

@dataclass(...)
class MuredRunResult:
    reason: MuredStopReason
    host_call: MuredHostCall | None = None
```

Required machine operations:

```python
machine.run_until_suspend(...)
machine.recharge_quantum(amount_or_new_budget)
machine.resume_host_call(result)
```

`MuredMachine.run()` may remain as a compatibility helper for pure programs, implemented in terms of the new lower-level API if appropriate.

## Phase 2 — Make q=0 genuinely resumable

Trace the existing q-exhaustion/reconstruction transition exactly.

The desired lifecycle is:

```text
forward reduction
    -> q reaches 0
    -> faithful reconstruction / safe scheduling boundary
    -> QUANTUM_EXHAUSTED
host scheduler recharges q
    -> same graph, same machine
    -> forward reduction resumes
```

Add a direct regression that:

1. constructs one machine;
2. gives it a deliberately tiny quantum;
3. repeatedly runs to quantum exhaustion;
4. recharges it;
5. eventually reaches the same result as a large-quantum run;
6. proves `MuredMachine.load` / construction happened once.

This is a core machine test independent of IO.

## Phase 3 — Represent host calls inside μRED primitive firing

Teach the compiler/machine which primitive names are host-dispatched.

Initial host primitives:

- `CLOCK` — zero arguments, returns integer milliseconds;
- `UART-RX` — zero arguments, returns byte integer or `NIL`;
- `UART-TX` — one byte-valued argument, returns `NIL` after writing;
- `UART-TX-BYTES` — one byte-list argument, returns `NIL` after writing.

Do not execute these in `compile_lambda`, the AST runtime, or a pure evaluator. They should reach the μRED primitive firing point and suspend there.

The machine must preserve enough redex/update information that `resume_host_call(value)` replaces/updates the effectful redex exactly as ordinary primitive firing would have done.

A host call therefore behaves like a primitive whose implementation lives outside the machine, not like an AST node interpreted outside the machine.

## Phase 4 — Move monadic sequencing into RED2 semantics

Eliminate Python-side handling of:

- `IO-RETURN`
- `IO-BIND`
- `IO-THEN`
- lambda action application
- `Y` action exposure
- operator action exposure
- `_prepare_action_argument`
- `_reduce_pure`
- `(Expr, quantum)` memoization

Determine the smallest faithful representation for the IO combinators:

### Preferred direction

Treat the combinators as ordinary graph-reduction semantics. They may be:

- predefined THOR/RED2 definitions loaded with the program; or
- faithful non-host μRED primitives if their strictness/non-strictness requires machine support.

Whichever representation is chosen, **Python must not sequence them**.

The critical semantic test is:

```text
(IO-BIND (CLOCK) (LAMBDA (now) ...now...))
```

The continuation must be blocked by dependence on the result of `CLOCK`. Once the host returns the clock value into the graph, ordinary reduction makes the continuation runnable.

Likewise:

```text
(IO-THEN (UART-TX 65) (UART-TX 66))
```

must emit `AB` because the graph dependency prevents the second effect from firing before the first completes.

## Phase 5 — Collapse `red2_engine/io_runtime.py` into a host dispatcher

The final runtime loop should be conceptually tiny:

```python
machine = load_program_once(...)
while True:
    stop = machine.run_until_suspend(...)

    if stop.reason is COMPLETE:
        return machine.result_expr()

    if stop.reason is QUANTUM_EXHAUSTED:
        machine.recharge_quantum(quantum)
        continue

    if stop.reason is HOST_CALL:
        result = dispatch_to_host(stop.host_call, host)
        machine.resume_host_call(result)
        continue
```

The runtime may translate host values to machine values, but it must not evaluate THOR expressions.

## Phase 6 — Delete the temporary architecture

Once the single-machine path passes all tests, remove:

- `_step_action` AST interpretation;
- `_NextAction` host control flow if no longer needed;
- `_BindFrame` / `_ThenFrame` host continuation stacks if no longer needed;
- `_prepare_action_argument`;
- `_contains_symbol` reduction-boundary probing if no longer needed;
- `_reduce_pure`;
- per-run pure-result cache;
- action-exposure `quantum=1` logic.

Retain only actual host-dispatch code and useful shared validation/conversion helpers.

## Phase 7 — Architectural regression tests

Add tests that make this bug difficult to reintroduce.

### One-machine invariant

Patch/count `MuredMachine.load` (or the canonical loader) while running:

- a simple `IO-RETURN` program;
- repeated UART output;
- a recursive clock loop;
- deterministic Breakout.

Each program execution must instantiate/load exactly one machine.

### Quantum recharge

With a tiny quantum, a nontrivial pure program must cross multiple quantum boundaries and still use one machine.

### Effect sequencing

Verify exact output order for nested combinations such as:

```text
(IO-THEN (UART-TX 65) (UART-TX 66))
```

and bind chains where later bytes depend on earlier host results.

### Exactly-once effect firing

Force multiple quantum expirations around an effect redex and prove the effect occurs once, not once per resume/reconstruction.

### Existing recursion tests

Keep recursion limit low and ensure long IO chains do not consume the Python call stack.

## Phase 8 — End-to-end gates

Required before commit:

```text
uv run pytest -q
uv run ruff check .
uv run mypy models/python tests
cargo test -p red2-wasm --quiet
git diff --check
mise run benchmark-breakout --iterations 1
```

Also compare deterministic THOR and Python RED2 Breakout stdout byte-for-byte.

## Phase 9 — Documentation

Update GitHub-facing Markdown to say plainly:

- one program == one μRED machine;
- quantum exhaustion is a resumable scheduling boundary;
- host IO is dispatched from primitive firing;
- the IO monad is sequenced by graph/data dependence;
- the previous AST-level IO interpreter and pure-expression memoization were transitional and have been removed.

Correct `docs/breakout-benchmarks.md` so the cache fix is described as the diagnostic stepping stone that exposed the architectural bug, not the desired final runtime architecture.

## Commit strategy

Prefer small reviewable commits if the implementation naturally separates:

1. resumable/rechargeable μRED machine;
2. host primitive trap/resume support;
3. single-machine RED2 IO runtime and deletion of AST evaluator;
4. tests/docs/benchmarks.

Do not push until explicitly requested.

## Non-goals / safety rails

- Do not touch `archives/`.
- Do not modify the existing untracked native-IO plan/gate files.
- Do not weaken faithful μRED primitive semantics merely to make IO convenient.
- Do not solve this by increasing action-exposure quantum.
- Do not retain repeated machine instantiation behind another cache.
- Do not execute host effects during compilation or decompilation.
- Do not make effect ordering depend on Python traversal order.

## Definition of done

This work is done only when all of the following are simultaneously true:

- Breakout works on Python RED2.
- One Breakout run creates one μRED machine.
- The same machine survives every quantum recharge and every host IO call.
- Host effects are dispatched from μRED execution.
- IO ordering follows graph/data dependency.
- The Python runtime no longer interprets the IO AST or repeatedly invokes a pure reducer.
- The `(Expr, quantum)` memoization workaround is gone.
- Full tests/type/lint/Rust-WASM gates pass.
- GitHub Markdown documents the final architecture accurately.

## Investigation note: current implementation behavior

The first architecture regression proves the present RED2 IO runner creates **nine** faithful machines for a tiny program containing two UART writes and one CLOCK bind. That is the bug this plan removes.

The current faithful machine also treats q=0 as a bounded-reduction reconstruction path which eventually reaches backward STOP and sets `state.halted = True`. This existing behavior is useful for Chapter 3/4 contraction-prefix snapshots, but `halted` currently conflates "this bounded quantum has reconstructed a prefix" with "the program is permanently complete." The redesign must preserve bounded-prefix observability while adding a supported same-machine recharge/resume operation.

The current primitive machinery already has the important mechanism needed for host IO: strict primitive arguments are reduced in the machine, primitive context is preserved across graph traversal, and `_fire_primitive()` owns the redex update. Host-dispatched primitives should extend that firing boundary rather than introduce another AST evaluator.

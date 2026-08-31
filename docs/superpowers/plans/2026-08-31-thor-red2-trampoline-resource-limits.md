# THOR/RED2 Trampoline and Resource Limits Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Python THOR evaluation/IO host-stack safe and add deterministic RED2 stack/heap limits exposed through CLI flags.

**Architecture:** Replace recursive evaluator/action dispatch with explicit loop-driven frames while preserving public APIs and quantum output. Add RED2 resource accounting as deterministic VM accounting, then pass limits through RED2 CLI paths and reject explicit THOR/parity use.

**Tech Stack:** Python 3.14, pytest, argparse, existing `thor_spec` AST/evaluator/RED2 modules.

**Spec:** `docs/superpowers/specs/2026-08-31-thor-red2-trampoline-resource-limits-design.md`

## Global Constraints

- THOR resource-limit flags are rejected when explicitly supplied; they are not ignored.
- RED2 overflow/exhaustion errors must be deterministic THOR/RED2-level errors, not Python `RecursionError`.
- `examples/clock-dots.thor` is the IO integration case.
- Existing THOR/RED2 quantum output shapes must remain stable.

**Acceptance:** suite — committed pytest coverage proves trampoline safety, RED2 resource-limit behavior, CLI routing, and clock-dots integration.

---

### Task 1: Add THOR trampoline regression tests

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `tests/test_semantics_recursion.py`

**Interfaces:**
- Consumes: existing `thor_spec.semantics.reduce_expr(expr: Expr, *, quantum: int, definitions: Mapping[str, Expr] | None = None) -> ReductionResult`
- Produces: regression tests documenting host-stack-safe THOR recursion expectations

**Parallelization rationale:** This task defines evaluator expectations independently from IO and RED2 resource accounting.

- [ ] **Step 1: Add failing tests**

Append these tests to `tests/test_semantics_recursion.py`:

```python
import sys

import pytest


def test_deep_y_recursion_does_not_consume_python_stack() -> None:
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        expr = parse_expr(
            "((Y (LAMBDA (loop) (LAMBDA (n) "
            "(if (= n 0) 0 (loop (1- n)))))) 250)"
        )
        result = reduce_expr(expr, quantum=2000)
    finally:
        sys.setrecursionlimit(previous_limit)

    assert to_source(result.expr) == "0"


def test_infinite_y_prefix_exhausts_quantum_not_python_stack() -> None:
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        expr = parse_expr("((Y (LAMBDA (loop) (LAMBDA (n) (loop n)))) 1)")
        result = reduce_expr(expr, quantum=500)
    finally:
        sys.setrecursionlimit(previous_limit)

    rendered = to_source(result.expr)
    assert "Y" in rendered
    assert result.remaining == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_semantics_recursion.py -v`

Expected before implementation: at least one new test fails with `RecursionError` or equivalent host-recursive behavior.

- [ ] **Step 3: Do not implement in this task**

This task is test-only and should not edit `models/python/thor_spec/semantics.py`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_semantics_recursion.py
git commit -m "test: pin thor trampoline recursion behavior"
```

### Task 2: Implement iterative THOR evaluator driver

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `models/python/thor_spec/semantics.py`
- Modify: `models/python/thor_spec/primitives.py`

**Interfaces:**
- Consumes: tests from Task 1
- Produces: `reduce_expr(expr: Expr, *, quantum: int, definitions: Mapping[str, Expr] | None = None) -> ReductionResult` with iterative internals and unchanged public result type

**Parallelization rationale:** The evaluator implementation depends only on Task 1’s test contract and can proceed independently of IO and RED2 work after those tests exist.

- [ ] **Step 1: Run focused failing tests**

Run: `uv run pytest tests/test_semantics_recursion.py tests/test_semantics_core.py tests/test_semantics_primitives.py -v`

Expected before implementation: Task 1 recursion tests fail.

- [ ] **Step 2: Replace host recursion with explicit frames**

In `models/python/thor_spec/semantics.py`, keep the public dataclasses and `translate(...)` API. Refactor `_Reducer.reduce(...)` so it delegates to an iterative loop with an explicit frame stack. The loop must cover these current recursive edges:

```text
Closure -> reduce(term.expr, term.store, phi)
Var -> reduce(store[index], store, phi)
Symbol definition -> contract then reduce(definition, store, phi)
App operator reduction -> primitive/lambda/struct/rebuild continuation
Lambda body reconstruction -> reduce_no_contract body with placeholder store
Struct fields -> reduce_no_contract each field
LetRec body or reconstruction -> explicit continuation
Rec expansion/reconstruction -> explicit continuation
```

A safe implementation shape is:

```python
@dataclass(frozen=True, slots=True)
class _EvalRequest:
    value: object
    store: RedexStore
    phi: int
    no_contract: bool = False

@dataclass(frozen=True, slots=True)
class _Frame:
    kind: str
    data: object
```

`_Reducer.reduce(...)` should push one `_EvalRequest`, loop until a final `Expr` is produced, and apply `_Frame` continuations instead of calling itself. `reduce_no_contract(...)` should use the same driver with a scoped quantum override frame rather than Python recursion.

- [ ] **Step 3: Keep primitive behavior continuation-safe**

Update `models/python/thor_spec/primitives.py` only as needed for the new reducer protocol. Preserve these method names because primitive helpers call them:

```python
remaining: int
reduce(value: object, store: tuple[object, ...], phi: int) -> Expr
reduce_no_contract(value: object, store: tuple[object, ...], phi: int) -> Expr
contract() -> None
```

If primitive helpers still call `state.reducer.reduce(...)`, those calls must enter the trampoline driver and return without growing Python stack proportional to THOR recursion.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_semantics_recursion.py tests/test_semantics_core.py tests/test_semantics_primitives.py tests/test_golden_parity.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add models/python/thor_spec/semantics.py models/python/thor_spec/primitives.py
git commit -m "fix: trampoline thor evaluator"
```

### Task 3: Add iterative IO regression tests with clock-dots

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `tests/test_io_runtime.py`

**Interfaces:**
- Consumes: existing `run_io_source(...)` and `ClockSource` protocol
- Produces: tests proving iterative IO action dispatch, including `examples/clock-dots.thor`

**Parallelization rationale:** IO recursion tests can be authored independently from evaluator internals because they target public IO runtime behavior.

- [ ] **Step 1: Add deterministic advancing clock helper and tests**

Append this helper and tests to `tests/test_io_runtime.py`:

```python
import sys


class AdvancingClock:
    def __init__(self, *, start: int = 0, step: int = 1000) -> None:
        self.value = start - step
        self.step = step

    def now_ms(self) -> int:
        self.value += self.step
        return self.value


def test_deep_io_then_chain_does_not_consume_python_stack() -> None:
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        action = "(IO-RETURN 0)"
        for _ in range(250):
            action = f"(IO-THEN (UART-TX 46) {action})"
        result, stdout, stderr = run_io(action, quantum=1000)
    finally:
        sys.setrecursionlimit(previous_limit)

    assert result == "0"
    assert stdout == "." * 250
    assert stderr == ""


def test_clock_dots_example_emits_dots_without_python_stack_growth() -> None:
    source = Path("examples/clock-dots.thor").read_text()
    stdout = StringIO()
    stderr = StringIO()
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        result = run_io_source(
            source,
            model="thor",
            quantum=500,
            stdin=StringIO(""),
            stdout=stdout,
            stderr=stderr,
            clock=AdvancingClock(step=1000),
        )
    finally:
        sys.setrecursionlimit(previous_limit)

    assert result == "NIL"
    assert stdout.getvalue().startswith(".")
    assert stderr.getvalue() == ""
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_io_runtime.py::test_deep_io_then_chain_does_not_consume_python_stack tests/test_io_runtime.py::test_clock_dots_example_emits_dots_without_python_stack_growth -v`

Expected before implementation: at least one test fails with `RecursionError` or recursive IO behavior.

- [ ] **Step 3: Commit**

```bash
git add tests/test_io_runtime.py
git commit -m "test: pin iterative thor io recursion behavior"
```

### Task 4: Implement iterative IO action runner

**Type:** implementation
**Depends-on:** 2, 3
**Review:** adversarial

**Files:**
- Modify: `models/python/thor_spec/io_runtime.py`

**Interfaces:**
- Consumes: Task 2 trampoline-backed `reduce_expr(...)`; Task 3 IO tests
- Produces: `_IoRuntime.run(action: Expr) -> Expr` implemented with an explicit action/continuation loop

**Parallelization rationale:** Once evaluator and IO tests exist, IO action dispatch can be refactored without depending on RED2 resource accounting.

- [ ] **Step 1: Run focused failing tests**

Run: `uv run pytest tests/test_io_runtime.py -v`

Expected before implementation: Task 3 tests fail.

- [ ] **Step 2: Replace recursive action dispatch**

In `models/python/thor_spec/io_runtime.py`, refactor `_IoRuntime.run(...)` and `_run_app(...)` so action control flow uses an explicit stack. Preserve public `run_io_source(...)` signature for now. Required loop behavior:

```text
current action starts as _resolve_action(action)
IF pushes no host recursion; evaluate condition with _pure, then set current to selected branch
lambda-defined action applies lambda, then sets current to resulting body
IO-RETURN evaluates pure arg and completes current continuation
IO-BIND pushes a bind continuation containing the unary lambda, then current becomes first action
IO-THEN pushes a then continuation containing the second action, then current becomes first action
UART/LEDS/TICKS/CLOCK perform primitive operation and yield Symbol("NIL") or integer result to continuation handling
```

A safe skeleton is:

```python
@dataclass(frozen=True, slots=True)
class _BindCont:
    lambda_expr: Expr

@dataclass(frozen=True, slots=True)
class _ThenCont:
    next_action: Expr

continuations: list[_BindCont | _ThenCont] = []
current = action
while True:
    result_or_next = self._step_action(current, continuations)
    ...
```

When an action yields a value:

```text
no continuation -> return value
BindCont -> current = _apply_unary_lambda(lambda_expr, value)
ThenCont -> current = next_action
```

- [ ] **Step 3: Remove recursion-limit workaround**

Delete the `sys.setrecursionlimit(max(sys.getrecursionlimit(), 20_000))` line from `run_io_source(...)`. The tests should pass without raising the host limit.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_io_runtime.py tests/test_semantics_recursion.py -v`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add models/python/thor_spec/io_runtime.py
git commit -m "fix: run thor io actions iteratively"
```

### Task 5: Add RED2 resource accounting tests

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `tests/test_red2_machine_core.py`

**Interfaces:**
- Consumes: existing `Red2Machine(image: ProgramImage, quantum: int, definitions: DefinitionImage | None = None)` constructor
- Produces: tests requiring `Red2ResourceLimits`, `Red2StackOverflowError`, and `Red2HeapExhaustedError`

**Parallelization rationale:** RED2 accounting is independent from THOR trampoline and IO action dispatch.

- [ ] **Step 1: Add failing tests**

Add imports and tests to `tests/test_red2_machine_core.py`:

```python
import pytest

from thor_spec.red2.machine import (
    Red2HeapExhaustedError,
    Red2Machine,
    Red2ResourceLimits,
    Red2StackOverflowError,
)


def test_red2_stack_limit_raises_deterministic_error() -> None:
    m = Red2Machine(
        compile_expr(parse_expr("((LAMBDA (X) X) 42)")),
        quantum=10,
        resource_limits=Red2ResourceLimits(stack_size_in_bytes=1, heap_size_in_bytes=1_000_000),
    )

    with pytest.raises(Red2StackOverflowError, match="RED2 stack overflow"):
        m.run()


def test_red2_heap_limit_raises_deterministic_error() -> None:
    source = "[1 2 3 4 5 6 7 8 9 10]"
    m = Red2Machine(
        compile_expr(parse_expr(source)),
        quantum=100,
        resource_limits=Red2ResourceLimits(stack_size_in_bytes=1_000_000, heap_size_in_bytes=1),
    )

    with pytest.raises(Red2HeapExhaustedError, match="RED2 heap exhausted"):
        m.run()


def test_red2_configured_resource_limits_allow_success() -> None:
    m = Red2Machine(
        compile_expr(parse_expr("((LAMBDA (X) X) 42)")),
        quantum=10,
        resource_limits=Red2ResourceLimits(stack_size_in_bytes=1_000_000, heap_size_in_bytes=1_000_000),
    )
    m.run()

    assert to_source(m.result_expr()) == "42"
```

If the file already imports `Red2Machine`, merge imports rather than duplicating them.

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_red2_machine_core.py -v`

Expected before implementation: import/signature failures for the new resource types.

- [ ] **Step 3: Commit**

```bash
git add tests/test_red2_machine_core.py
git commit -m "test: pin red2 resource limit errors"
```

### Task 6: Implement RED2 deterministic resource limits

**Type:** implementation
**Depends-on:** 5
**Review:** adversarial

**Files:**
- Modify: `models/python/thor_spec/red2/machine.py`

**Interfaces:**
- Consumes: Task 5 tests
- Produces: `Red2ResourceLimits`, `DEFAULT_STACK_SIZE_IN_BYTES`, `DEFAULT_HEAP_SIZE_IN_BYTES`, `Red2StackOverflowError`, `Red2HeapExhaustedError`, and optional `resource_limits` constructor parameter

**Parallelization rationale:** This VM-local resource layer does not depend on THOR trampoline or CLI wiring.

- [ ] **Step 1: Run focused failing tests**

Run: `uv run pytest tests/test_red2_machine_core.py -v`

Expected before implementation: Task 5 tests fail.

- [ ] **Step 2: Add resource types**

In `models/python/thor_spec/red2/machine.py`, near the top-level dataclasses, add:

```python
DEFAULT_STACK_SIZE_IN_BYTES = 1024 * 1024
DEFAULT_HEAP_SIZE_IN_BYTES = 16 * 1024 * 1024
_STACK_FRAME_BYTES = 64
_HEAP_TERM_BYTES = 64


class Red2ResourceError(RuntimeError):
    """Raised when RED2 deterministic VM resources are exhausted."""


class Red2StackOverflowError(Red2ResourceError):
    """Raised when RED2 explicit evaluation stack exceeds its byte limit."""


class Red2HeapExhaustedError(Red2ResourceError):
    """Raised when RED2 deterministic heap accounting exceeds its byte limit."""


@dataclass(frozen=True, slots=True)
class Red2ResourceLimits:
    stack_size_in_bytes: int = DEFAULT_STACK_SIZE_IN_BYTES
    heap_size_in_bytes: int = DEFAULT_HEAP_SIZE_IN_BYTES
```

Validate non-negative limits in `Red2Machine.__init__`; raise `ValueError` with `stack_size_in_bytes must be non-negative` or `heap_size_in_bytes must be non-negative`.

- [ ] **Step 3: Account stack frames deterministically**

Add private methods:

```python
def _enter_stack_frame(self) -> None:
    self._stack_bytes_used += _STACK_FRAME_BYTES
    if self._stack_bytes_used > self._resource_limits.stack_size_in_bytes:
        raise Red2StackOverflowError(
            f"RED2 stack overflow: used {self._stack_bytes_used} byte(s), "
            f"limit {self._resource_limits.stack_size_in_bytes} byte(s)"
        )


def _leave_stack_frame(self) -> None:
    self._stack_bytes_used -= _STACK_FRAME_BYTES
```

Call `_enter_stack_frame()` at the start of `_reduce(...)` and `_leave_stack_frame()` in a `finally` block. This does not remove RED2 recursion yet, but ensures deterministic RED2 stack failure occurs before Python stack failure.

- [ ] **Step 4: Account heap allocations deterministically**

Add:

```python
def _allocate_heap_terms(self, count: int) -> None:
    self._heap_bytes_used += count * _HEAP_TERM_BYTES
    if self._heap_bytes_used > self._resource_limits.heap_size_in_bytes:
        raise Red2HeapExhaustedError(
            f"RED2 heap exhausted: used {self._heap_bytes_used} byte(s), "
            f"limit {self._resource_limits.heap_size_in_bytes} byte(s)"
        )
```

Call it after parsing source and definitions, and when creating closures, recursive cells, struct terms, app terms, and emitted result graph terms. At minimum, charge `len(self._problem_memory)`, parsed source term count, definition term count, closure tuple sizes, recursive LETREC cells, and `len(self._result)` before syncing memory.

- [ ] **Step 5: Preserve existing behavior with defaults**

Default-constructed `Red2Machine(...)` calls must behave as before for existing tests. The new constructor signature should be:

```python
def __init__(
    self,
    image: ProgramImage,
    quantum: int,
    definitions: DefinitionImage | None = None,
    resource_limits: Red2ResourceLimits | None = None,
) -> None:
```

- [ ] **Step 6: Run focused tests**

Run: `uv run pytest tests/test_red2_machine_core.py tests/test_red2_machine_extended.py tests/test_red2_binary.py -v`

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add models/python/thor_spec/red2/machine.py
git commit -m "feat: add red2 resource accounting"
```

### Task 7: Wire RED2 resource flags through CLI and IO pure RED2 calls

**Type:** implementation
**Depends-on:** 4, 6
**Review:** adversarial

**Files:**
- Modify: `models/python/thor_spec/cli.py`
- Modify: `models/python/thor_spec/golden.py`
- Modify: `models/python/thor_spec/io_runtime.py`
- Modify: `tests/test_cli_models.py`

**Interfaces:**
- Consumes: `Red2ResourceLimits(stack_size_in_bytes: int, heap_size_in_bytes: int)` from Task 6; iterative IO from Task 4
- Produces: CLI support for `--stack-size-in-bytes` and `--heap-size-in-bytes` on RED2 paths, rejection on THOR/parity explicit use

**Parallelization rationale:** CLI wiring waits for both IO and RED2 resource interfaces, but remains independent from evaluator implementation details after those interfaces exist.

- [ ] **Step 1: Add failing CLI tests**

In `tests/test_cli_models.py`, add tests like:

```python
def test_cli_red2_accepts_resource_limits(capsys: CaptureFixture[str]) -> None:
    assert main([
        "--model", "red2",
        "--quantum", "20",
        "--stack-size-in-bytes", "1000000",
        "--heap-size-in-bytes", "1000000",
        "--expr", "(+ 2 3)",
    ]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "5"


def test_cli_thor_rejects_explicit_resource_limits(capsys: CaptureFixture[str]) -> None:
    assert main([
        "--model", "thor",
        "--stack-size-in-bytes", "1000000",
        "--expr", "(+ 2 3)",
    ]) == 2
    captured = capsys.readouterr()
    assert "resource limits are currently supported for red2 only" in captured.err


def test_cli_red2_reports_stack_overflow(capsys: CaptureFixture[str]) -> None:
    assert main([
        "--model", "red2",
        "--stack-size-in-bytes", "1",
        "--heap-size-in-bytes", "1000000",
        "--expr", "((LAMBDA (X) X) 42)",
    ]) == 2
    captured = capsys.readouterr()
    assert "RED2 stack overflow" in captured.err
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_cli_models.py -v`

Expected before implementation: argparse rejects unknown flags or limits are not enforced.

- [ ] **Step 3: Add argparse flags with explicit-use detection**

In `models/python/thor_spec/cli.py`, add defaults imported from RED2 machine and define helper parser arguments using `default=None` so explicit use can be detected:

```python
def _add_resource_limit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stack-size-in-bytes", type=int, default=None)
    parser.add_argument("--heap-size-in-bytes", type=int, default=None)
```

Build limits only for RED2:

```python
def _resource_limits_from_args(args: argparse.Namespace) -> Red2ResourceLimits:
    return Red2ResourceLimits(
        stack_size_in_bytes=args.stack_size_in_bytes
        if args.stack_size_in_bytes is not None
        else DEFAULT_STACK_SIZE_IN_BYTES,
        heap_size_in_bytes=args.heap_size_in_bytes
        if args.heap_size_in_bytes is not None
        else DEFAULT_HEAP_SIZE_IN_BYTES,
    )
```

Reject unsupported explicit use:

```python
def _reject_resource_limits_for_non_red2(args: argparse.Namespace, model: object) -> int | None:
    if model != "red2" and (
        args.stack_size_in_bytes is not None or args.heap_size_in_bytes is not None
    ):
        print("thor-spec: resource limits are currently supported for red2 only", file=sys.stderr)
        return 2
    return None
```

- [ ] **Step 4: Pass limits through RED2 paths**

Update `run_source(...)` in `models/python/thor_spec/golden.py` to accept optional `resource_limits: Red2ResourceLimits | None = None` and pass it only to `Red2Machine` for model `red2`.

Update `run_io_source(...)` and `_IoRuntime` in `models/python/thor_spec/io_runtime.py` to accept optional `resource_limits` and pass it into pure RED2 `Red2Machine(...)` calls.

Update these CLI paths:

```text
thor-spec --model red2 --expr/--file
thor-spec red2 --expr/file
thor-spec run-red2 --bytecode
```

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/test_cli_models.py tests/test_io_runtime.py -v`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add models/python/thor_spec/cli.py models/python/thor_spec/golden.py models/python/thor_spec/io_runtime.py tests/test_cli_models.py
git commit -m "feat: expose red2 resource limits in cli"
```

### Task 8: Final verification and documentation touch-up

**Type:** implementation
**Depends-on:** 2, 4, 7

**Files:**
- Modify: `README.md`
- Test: full project Python suite

**Interfaces:**
- Consumes: implemented CLI flags and error behavior from Task 7
- Produces: verified full-suite status and README mention of RED2 resource flags

- [ ] **Step 1: Update README CLI examples**

Add one short RED2 example near the RED2 CLI examples:

```markdown
RED2 resource limits can be configured on Python RED2 execution paths:

```sh
uv run thor-spec --model red2 --stack-size-in-bytes 1048576 --heap-size-in-bytes 16777216 --expr "(+ 2 3)"
```

The THOR interpreter currently rejects explicit resource-limit flags because its values live in Python-managed memory rather than a modeled VM heap.
```

- [ ] **Step 2: Run full verification**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 3: Check git status**

Run: `git status --short`

Expected: only intended plan/README/test/source changes are present; pre-existing unrelated untracked files may remain but must not be staged.

## Operator smoke

- do: `uv run thor-spec --model red2 --stack-size-in-bytes 1048576 --heap-size-in-bytes 16777216 --expr "(+ 2 3)"`
- see: stdout is exactly `5` and stderr is empty.
- do: `uv run thor-spec --model thor --stack-size-in-bytes 1048576 --expr "(+ 2 3)"`
- see: command exits non-zero and stderr says resource limits are supported for red2 only.
- do: run `examples/clock-dots.thor` with a controlled clock through the Python THOR IO test path.
- see: dots are emitted without a Python stack traceback.

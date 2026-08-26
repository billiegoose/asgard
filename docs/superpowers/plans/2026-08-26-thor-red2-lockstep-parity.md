# THOR/RED2 Lockstep Parity Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a THOR/RED2 lockstep parity diagnostic mode that compares both models at every contraction-prefix quantum and reports the first divergence.

**Architecture:** Use contraction-prefix snapshots as the first shared granularity: for q = 0..N, evaluate the same normalized program with both models at `quantum=q` and compare rendered user-facing outputs. This avoids pretending RED2 raw machine phases and THOR recursive reducer calls are identical micro-steps while still testing every observable contraction budget prefix and reporting programs whose intermediate scheduling differs.

**Tech Stack:** Python 3.14, pytest, existing `thor_spec` parser/normalizer/golden runners, argparse CLI.

**Spec:** User request in chat on 2026-08-26: “figure out what granularity will work for that, then plan and implement that using ultrapowers.”

## Global Constraints

- Use contraction-prefix snapshots, not RED2 raw instruction micro-steps, as the first implemented lockstep granularity.
- Compare user-facing THOR source strings so RED2 internals such as `PNP`, `UBV`, and `CLOSURE` never count as acceptable output.
- Preserve existing `thor-spec --model thor|red2` behavior.
- Keep default verification free of FPGA/vendor/PipelineC tooling.
- Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy src tests` before final completion.

**Acceptance:** suite — committed unit tests plus CLI smoke tests cover matching prefixes, first-divergence reporting, and existing CLI compatibility.

---

### Task 1: Lockstep parity core API

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/lockstep.py`
- Test: `tests/test_lockstep_parity.py`

**Interfaces:**
- Consumes: `thor_spec.golden.run_source(source: str, *, model: ModelName, quantum: int) -> str`
- Produces: `ParitySnapshot(quantum: int, thor: str, red2: str, matches: bool)`, `ParityResult(max_quantum: int, snapshots: tuple[ParitySnapshot, ...])`, `ParityResult.first_mismatch: ParitySnapshot | None`, `compare_prefixes(source: str, *, max_quantum: int) -> ParityResult`

**Parallelization rationale:** This core module defines a stable API that the CLI and fixture tests can consume independently.

- [ ] **Step 1: Write failing API tests**

Create `tests/test_lockstep_parity.py` with tests that import `compare_prefixes` from `thor_spec.lockstep` and assert:

```python
from thor_spec.lockstep import compare_prefixes


def test_compare_prefixes_reports_all_matching_snapshots() -> None:
    result = compare_prefixes("(+ 2 3)", max_quantum=3)

    assert result.max_quantum == 3
    assert [snapshot.quantum for snapshot in result.snapshots] == [0, 1, 2, 3]
    assert result.first_mismatch is None
    assert all(snapshot.matches for snapshot in result.snapshots)
    assert result.snapshots[-1].thor == "5"
    assert result.snapshots[-1].red2 == "5"


def test_compare_prefixes_catches_partial_fibonacci_shape() -> None:
    source = """
    fib == (lambda (n)
      (letrec ((fib-iter
                (lambda (i current next)
                  (if (= i 0)
                      current
                      (fib-iter (1- i) next (+ current next))))))
        (fib-iter n 0 1)))
    fib-six == (fib 6)
    fib-six
    """

    result = compare_prefixes(source, max_quantum=75)

    assert result.first_mismatch is None
    assert result.snapshots[75].thor == "(+ 3 (+ 2 (+ 1 2)))"
    assert result.snapshots[75].red2 == "(+ 3 (+ 2 (+ 1 2)))"
```

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/test_lockstep_parity.py -v`

Expected: FAIL because `thor_spec.lockstep` does not exist.

- [ ] **Step 3: Implement the API**

Create `src/thor_spec/lockstep.py` with frozen dataclasses and `compare_prefixes`:

```python
from __future__ import annotations

from dataclasses import dataclass

from thor_spec.golden import run_source


@dataclass(frozen=True, slots=True)
class ParitySnapshot:
    quantum: int
    thor: str
    red2: str
    matches: bool


@dataclass(frozen=True, slots=True)
class ParityResult:
    max_quantum: int
    snapshots: tuple[ParitySnapshot, ...]

    @property
    def first_mismatch(self) -> ParitySnapshot | None:
        return next((snapshot for snapshot in self.snapshots if not snapshot.matches), None)


def compare_prefixes(source: str, *, max_quantum: int) -> ParityResult:
    if max_quantum < 0:
        msg = f"max_quantum must be non-negative, got {max_quantum}"
        raise ValueError(msg)
    snapshots = tuple(
        _snapshot(source, quantum=quantum) for quantum in range(max_quantum + 1)
    )
    return ParityResult(max_quantum=max_quantum, snapshots=snapshots)


def _snapshot(source: str, *, quantum: int) -> ParitySnapshot:
    thor = run_source(source, model="thor", quantum=quantum)
    red2 = run_source(source, model="red2", quantum=quantum)
    return ParitySnapshot(
        quantum=quantum,
        thor=thor,
        red2=red2,
        matches=thor == red2,
    )
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run pytest tests/test_lockstep_parity.py -v`

Expected: PASS.

- [ ] **Step 5: Run focused static checks**

Run: `uv run ruff check src/thor_spec/lockstep.py tests/test_lockstep_parity.py && uv run mypy src tests`

Expected: PASS.

---

### Task 2: CLI parity mode

**Type:** implementation
**Depends-on:** 1
**Review:** lean

**Files:**
- Modify: `src/thor_spec/cli.py`
- Test: `tests/test_cli_models.py`

**Interfaces:**
- Consumes: `compare_prefixes(source: str, *, max_quantum: int) -> ParityResult` from Task 1
- Produces: CLI model choice `--model parity` that exits 0 on all prefix matches and exits 1 with first-divergence details on mismatch

- [ ] **Step 1: Write failing CLI tests**

Append tests to `tests/test_cli_models.py` that assert:

```python
def test_cli_parity_model_reports_matching_prefixes(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--model", "parity", "--quantum", "3", "--expr", "(+ 2 3)"]) == 0
    captured = capsys.readouterr()
    assert "parity ok: 4 prefix snapshot(s) matched through quantum 3" in captured.err
    assert captured.out == "5\n"


def test_cli_parity_model_rejects_negative_quantum(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--model", "parity", "--quantum", "-1", "--expr", "(+ 2 3)"]) == 2
    captured = capsys.readouterr()
    assert "max_quantum must be non-negative" in captured.err
```

If `pytest` is not imported in that file, add `import pytest`.

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/test_cli_models.py -v`

Expected: FAIL because argparse does not accept `--model parity`.

- [ ] **Step 3: Implement `--model parity`**

Modify `src/thor_spec/cli.py`:

- Extend the `--model` choices to `("thor", "red2", "parity")`.
- Keep `_model_name` for `thor|red2`, or replace it with a local string validator that preserves type safety for `run_source` calls.
- In `main`, when `args.model == "parity"`, call `compare_prefixes(source, max_quantum=args.quantum)`.
- If `first_mismatch is None`, print the final THOR output to stdout when non-empty and write exactly this status line to stderr:

```text
parity ok: {len(result.snapshots)} prefix snapshot(s) matched through quantum {args.quantum}
```

- If there is a mismatch, write these lines to stderr and return exit code 1:

```text
parity mismatch at quantum {snapshot.quantum}
thor: {snapshot.thor}
red2: {snapshot.red2}
```

- Preserve existing exception handling for parse/runtime errors returning exit code 2.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run pytest tests/test_cli_models.py -v`

Expected: PASS.

- [ ] **Step 5: Smoke the Fibonacci parity command**

Run: `uv run thor-spec --model parity --quantum 75 --file vscode-thor/examples/fibonacci.thor`

Expected stdout: `(+ 3 (+ 2 (+ 1 2)))`

Expected stderr contains: `parity ok: 76 prefix snapshot(s) matched through quantum 75`.

---

### Task 3: Fixture lockstep regression coverage

**Type:** implementation
**Depends-on:** 1
**Review:** lean

**Files:**
- Modify: `tests/test_golden_parity.py`
- Test: `tests/test_golden_parity.py`

**Interfaces:**
- Consumes: `compare_prefixes(source: str, *, max_quantum: int) -> ParityResult` from Task 1
- Produces: regression tests that run prefix parity over known-matching source strings and verify Fibonacci first-mismatch diagnostics

- [ ] **Step 1: Write failing fixture-prefix tests**

Modify `tests/test_golden_parity.py` to import `Path` if needed and `compare_prefixes`. Add tests:

```python
def test_simple_cases_match_at_every_prefix_quantum() -> None:
    for source in [
        "(+ 2 3)",
        "((LAMBDA (X) X) 42)",
        "(IF TRUE (+ 1 2) (BAD BAD))",
    ]:
        result = compare_prefixes(source, max_quantum=10)
        assert result.first_mismatch is None, source


def test_fibonacci_example_reports_first_prefix_mismatch() -> None:
    source = Path("vscode-thor/examples/fibonacci.thor").read_text()
    result = compare_prefixes(source, max_quantum=75)

    assert result.first_mismatch is not None
    assert result.first_mismatch.quantum == 3
    assert result.snapshots[75].thor == "(+ 3 (+ 2 (+ 1 2)))"
    assert result.snapshots[75].red2 == "(+ 3 (+ 2 (+ 1 2)))"
```

- [ ] **Step 2: Run tests to verify RED or GREEN-with-existing-API**

Run: `uv run pytest tests/test_golden_parity.py -v`

Expected before Task 1 is integrated: FAIL because `thor_spec.lockstep` does not exist. Expected after Task 1 is integrated: PASS or reveal a genuine prefix mismatch to fix.

- [ ] **Step 3: Fix any real prefix mismatch**

If a mismatch appears, inspect `result.first_mismatch.quantum`, `.thor`, and `.red2`. Fix the semantic/RED2 behavior, not the test fixture, unless the fixture itself is invalid THOR.

- [ ] **Step 4: Run focused regression tests**

Run: `uv run pytest tests/test_golden_parity.py tests/test_lockstep_parity.py -v`

Expected: PASS.

---

### Task 4: Documentation and final gate

**Type:** implementation
**Depends-on:** 2, 3
**Review:** lean

**Files:**
- Modify: `docs/thor-red2-prototype.md`
- Modify: `README.md`
- Test: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: `thor-spec --model parity --quantum N --expr|--file SOURCE` from Task 2
- Produces: documented parity mode and fresh final verification evidence

- [ ] **Step 1: Document contraction-prefix granularity**

Update `docs/thor-red2-prototype.md` to include a short section titled `Lockstep parity mode` explaining:

- The chosen granularity is contraction-prefix snapshots.
- `quantum=N` compares outputs for every q from 0 through N.
- This is intentionally stronger than completion-only parity but does not claim raw RED2 instruction micro-steps or recursive-application scheduling are identical to THOR reducer recursion frames.
- Example matching command: `uv run thor-spec --model parity --quantum 10 --expr "((LAMBDA (X) X) 42)"`.

- [ ] **Step 2: Add README CLI mention**

Update `README.md` near existing THOR/RED2 CLI usage to mention `--model parity` as the way to compare THOR and RED2 at every contraction-prefix quantum.

- [ ] **Step 3: Run docs tests**

Run: `uv run pytest tests/test_docs_examples.py -v`

Expected: PASS.

- [ ] **Step 4: Run full final gate**

Run:

```bash
uv run pytest && uv run ruff check . && uv run mypy src tests
```

Expected: PASS.

- [ ] **Step 5: Run CLI smokes**

Run:

```bash
uv run thor-spec --model parity --quantum 10 --expr "((LAMBDA (X) X) 42)"
uv run thor-spec --model parity --quantum 75 --file vscode-thor/examples/fibonacci.thor || test $? -eq 1
uv run thor-spec --model red2 --quantum 75 --file vscode-thor/examples/fibonacci.thor
```

Expected: the lambda parity command exits 0 with `parity ok`; the Fibonacci parity command exits 1 with `parity mismatch at quantum 3`; the RED2 Fibonacci command contains no `PNP`.

## Operator smoke

- do: `uv run thor-spec --model parity --quantum 75 --file vscode-thor/examples/fibonacci.thor`
- see: stderr says `parity mismatch at quantum 3`, showing the diagnostic frontier where the models schedule recursive application differently.

- do: `uv run thor-spec --model parity --quantum 3 --expr "(+ 2 3)"`
- see: stdout is `5` and stderr says 4 prefix snapshots matched.

- do: `uv run thor-spec --model red2 --quantum 75 --file vscode-thor/examples/fibonacci.thor`
- see: output contains no `PNP`.

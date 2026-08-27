# THOR IO Monad Simulator Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small monadic IO action layer for THOR simulator runs, using stdin/stdout for UART and stderr for diagnostics.

**Architecture:** Keep pure THOR evaluation unchanged. Add a separate IO action interpreter used only by `thor-spec --io`; it interprets monadic action forms (`IO-RETURN`, `IO-BIND`, `IO-THEN`) and device-like actions (`UART-RX`, `UART-TX`, `LEDS`, `TICKS`) while using the existing THOR/RED2 models to reduce pure subexpressions.

**Tech Stack:** Python 3.14, pytest, argparse, existing THOR parser/normalizer/golden harness.

**Spec:** User requested a monad-like IO layer and simulator UART/stdout separation: “For our simulators, lets move our current diagnostic outputs to stderr so we can use stdin and stdout for UART-RX and UART-TX”.

## Global Constraints

- Preserve existing pure `thor-spec --model thor|red2` behavior unless `--io` is explicitly passed.
- In IO mode, stdout is reserved for UART-TX bytes.
- In IO mode, final action result and device diagnostics go to stderr.
- Keep the first IO slice deterministic and host-simulated; no FPGA/vendor tooling.
- Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy src tests` before completion.

**Acceptance:** suite — committed tests cover monadic sequencing, UART stdin/stdout, LED diagnostics, CLI stream behavior, and existing pure CLI compatibility.

---

### Task 1: IO action interpreter

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/io_runtime.py`
- Test: `tests/test_io_runtime.py`

**Interfaces:**
- Consumes: `run_source(source: str, *, model: ModelName, quantum: int) -> str`
- Produces: `run_io_source(source: str, *, model: ModelName, quantum: int, stdin: TextIO, stdout: TextIO, stderr: TextIO) -> str`

**Parallelization rationale:** The IO runtime has a clean API that CLI/docs can consume after it exists.

- [ ] Write failing tests for `UART-TX`, `UART-RX`, `IO-BIND`, `IO-THEN`, and `LEDS`.
- [ ] Implement minimal IO interpreter that parses/normalizes top-level definitions and executes the last expression as an IO action.
- [ ] Use existing pure model evaluation for action arguments and returned pure values.
- [ ] Verify focused tests pass.

---

### Task 2: CLI `--io` wiring

**Type:** implementation
**Depends-on:** 1
**Review:** lean

**Files:**
- Modify: `src/thor_spec/cli.py`
- Test: `tests/test_cli_models.py`

**Interfaces:**
- Consumes: `run_io_source(...) -> str` from Task 1
- Produces: `thor-spec --io --model thor|red2 --expr|--file` behavior with UART bytes on stdout and diagnostics/final result on stderr.

- [ ] Write failing CLI tests for UART-TX stdout and final result stderr.
- [ ] Add `--io` flag and route to `run_io_source` for `thor|red2` models.
- [ ] Reject `--io --model parity` with exit code 2 and a clear stderr error.
- [ ] Verify focused CLI tests pass.

---

### Task 3: Primitive docs update and final gate

**Type:** implementation
**Depends-on:** 1, 2
**Review:** lean

**Files:**
- Modify: `docs/thor-primitives.md`
- Modify: `README.md`
- Test: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: `thor-spec --io` from Task 2
- Produces: documented IO action forms and simulator stream policy.

- [ ] Document IO action forms, UART behavior, LED diagnostics, and stream policy.
- [ ] Link `--io` from README CLI examples.
- [ ] Run docs tests.
- [ ] Run full final gate: `uv run pytest && uv run ruff check . && uv run mypy src tests`.

## Operator smoke

- do: `printf A | uv run thor-spec --io --model thor --expr "(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))"`
- see: stdout is `A`; stderr contains `io result: NIL`.

- do: `uv run thor-spec --io --model thor --expr "(IO-THEN (UART-TX 72) (UART-TX 105))"`
- see: stdout is `Hi`; stderr contains `io result: NIL`.

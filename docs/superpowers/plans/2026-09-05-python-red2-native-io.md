# Python RED2-Owned IO Runtime Implementation Plan

**Grammar:** claims-v1

**Claim:** do: Run Python `red2` programs that use `UART-RX`, `UART-TX`, `UART-TX-BYTES`, and `CLOCK`; see: the Python RED2 implementation itself owns those IO actions with the same observable UART and clock behavior as the Rust RED2 VM, while stdin/stdout and deterministic `--clock` behavior stay unchanged. (elicited)

**Goal:** Give the faithful Python RED2 implementation its own non-recursive IO action runner, analogous to Rust `IoRunner`, instead of routing RED2 IO through the THOR-owned generic action interpreter.

**Tech Stack:** Python 3.14, faithful `MuredMachine`, THOR AST/parser/normalizer as source representation, pytest, Ruff, mypy; Rust `models/rust-red2/src/vm.rs::IoRunner` as the behavioral architecture reference.

**Spec:** user request in chat on 2026-09-05: “add IO to the python red2 implementation so that it supports the same UART and CLOCK primitives”; existing simulator contract in `docs/thor-primitives.md` §Simulator IO Actions; Rust reference in `models/rust-red2/src/vm.rs` `IoRunner`.

## Global Constraints

- The Chapter-4-style `MuredMachine.step()` and `MuredMachine.run()` remain pure graph/environment/register execution: they do not read stdin, write stdout, read the wall clock, or call the Chapter 3 evaluator.
- Python RED2 supports the Rust device subset exactly in this slice: `UART-RX`, `UART-TX`, `UART-TX-BYTES`, and `CLOCK`, plus the existing `IO-RETURN`, `IO-BIND`, and `IO-THEN` sequencing forms needed to use them.
- `UART-RX` returns an integer byte when one is available and `NIL` for no-ready-byte or EOF; `UART-TX` writes `value % 256`; `UART-TX-BYTES` writes each integer element modulo 256; both transmit actions return `NIL`.
- `CLOCK` returns Unix milliseconds supplied by an injected host capability. The existing system clock and latest-value `--clock <path>` behavior remain unchanged at the CLI boundary.
- RED2 IO execution is iterative/trampolined: recursive THOR IO programs must consume RED2/host resources, not Python call-stack depth.
- Pure subexpressions inside RED2 IO actions are reduced only by the faithful `MuredMachine`; `red2_engine` IO code must not import or invoke `thor_engine.semantics`, `ThorDefinitionCache`, or `reduce_expr`.
- The existing THOR-model IO implementation and its `LEDS`/`TICKS` simulator actions remain behaviorally unchanged. Native RED2 `LEDS`/`TICKS` support is outside this slice.
- Existing stdout/stderr policy remains unchanged: UART bytes use stdout; the CLI prints the final IO result only under `--verbose`, to stderr.
- No `.red2` bytecode format change and no Rust/WASM implementation change.
- `archives/` is unrelated and remains untouched.

**Acceptance:** suite — focused RED2 IO ownership tests plus existing cross-model IO examples, Python full-suite/lint/type gates, Rust regression tests, and operator smokes establish the result.

**Parallelization rationale:** three implementation tasks in two waves: Task 1 and Task 3 are wave-0 independent (runtime ownership and documentation can be built from the contracts above); Task 2 follows Task 1 because its integration proof must execute the new RED2 IO runner's runtime behavior, not merely share its type shape. Task 4 is a verification-only gate. Although implementation width is only two, IO sequencing, recursion/termination, and observable device effects are hard-to-review behavior, so Ultrapowers' risk override applies.

### Task 1: RED2-owned iterative IO runner

**Type:** implementation
**Review:** peer

**Files:**
- Create: `models/python/red2_engine/io_runtime.py`
- Test: `tests/test_red2_io_runtime.py`

**Claim:** A Python RED2 IO action runs through RED2-owned code and can receive UART bytes, transmit UART bytes, read a clock, and sequence those effects without using the Python call stack. (derived)
Machine: M1. `run_red2_io_action(...)` executes `UART-RX`, returning `INT(byte)` when the host has a byte and `NIL` when the host reports no byte. M2. It executes `UART-TX` and `UART-TX-BYTES`, passing modulo-256 bytes to the host in source order and returning `NIL`. M3. It executes `CLOCK` by returning the injected host's millisecond integer. M4. `IO-RETURN`, `IO-BIND`, and `IO-THEN` sequence actions iteratively, including a recursive/Y-defined action chain under a low Python recursion limit. M5. `red2_engine.io_runtime` has one faithful pure-reduction seam that loads/runs `MuredMachine` for action exposure and continuation application, and the module contains no Chapter 3 evaluator import/call, AST substitution helper, or recursive call to `run_red2_io_action`.

**Authorized-by:** user request in chat on 2026-09-05; Rust behavioral reference `models/rust-red2/src/vm.rs:575-835`; simulator contract `docs/thor-primitives.md:176-218`.

**Interfaces:**
- Consumes: none
- Produces: `Red2IoHost`
- Produces: `run_red2_io_action(action: Expr, *, definitions: Mapping[str, Expr], quantum: int, host: Red2IoHost) -> Expr`

**Context:** `MuredMachine` is the only Python RED2 evaluator. Keep host effects outside `MuredMachine.step()`/`run()` exactly as Rust keeps them outside `Reducer`: Rust `IoRunner` owns an explicit loop, continuation frames for bind/then, a `reduce_pure` seam, UART reads/writes, and clock reads. The Python runner should mirror that separation. `Red2IoHost` is the platform-neutral effect boundary and has exactly three operations: `uart_rx() -> int | None`, `uart_tx(data: bytes) -> None`, and `clock_ms() -> int`. `UART-TX` calls `uart_tx(bytes((value % 256,)))`; `UART-TX-BYTES` calls it once with the whole constructed byte sequence. The runner works on normalized `thor_lang.ast.Expr` values plus visible definition expressions. To apply an action lambda or an `IO-BIND` continuation, construct the corresponding AST application and ask `load_faithful_machine(...).run()` for the next reduced expression; do not copy the current `_substitute` implementation into RED2. Device symbols stay opaque to pure μRED reduction and are recognized only by the IO runner. `IF`/`Y`/top-level definitions may need repeated pure reductions before the outer form becomes a recognized action, so the runner must tail-loop when pure reduction makes progress. A stuck unrecognized action raises a RED2 IO-specific error naming `not an IO action` or `unknown IO action`, compatible with the existing CLI fallback convention. Do not add `LEDS` or `TICKS` here.

**Proof:**
- Test: `tests/test_red2_io_runtime.py`
- Legs: (a) a fake host returning byte `90` makes `(UART-RX)` return source-equivalent `90`, while a fake host returning `None` makes it return `NIL` [M1]; (b) `(UART-TX 321)` sends exactly `b'A'`, returns `NIL`, and `(UART-TX-BYTES [65 322 -189])` sends exactly `b'ABC'` in one host call [M2]; (c) a fake clock value `1700000000789` makes `(CLOCK)` return exactly that integer and emits no UART bytes [M3]; (d) `(IO-RETURN (+ 40 2))` returns source-equivalent `42`, `(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))` echoes one byte, `(IO-THEN (UART-TX 72) (UART-TX 105))` sends `b'Hi'`, and a Y-defined loop producing at least 250 sequential transmit actions completes with `sys.setrecursionlimit(80)` and no `RecursionError` [M4]; (e) definitions and arithmetic in `emit == (LAMBDA (n) (UART-TX (+ n 64)))` produce `b'ABC'`; source inspection asserts exactly one helper is responsible for pure RED2 reduction, that helper calls `load_faithful_machine(...).run()`, and the module contains none of `thor_engine.semantics`, `ThorDefinitionCache`, `reduce_expr`, `_substitute`, or a call to `run_red2_io_action` from inside its own body [M5].

**Stale-if:**
- path-exists: `models/python/red2_engine/io_runtime.py`
- sha-matches: `models/python/red2_engine/mured.py`@677f6921fd686c6f5a226701563d491fd74d3b046d979e0de5e5a74aa41a67c8

### Task 2: Route Python RED2 simulator IO through the RED2 runner

**Type:** implementation
**Review:** peer

**Files:**
- Modify: `models/python/thor_engine/io_runtime.py`
- Modify: `models/python/red2_engine/__init__.py`
- Test: `tests/test_io_runtime.py`
- Test: `tests/test_mured_cli.py`

**Claim:** Running the existing Python `red2` command with UART or CLOCK behaves the same to the operator, but RED2 device actions no longer execute in THOR's generic IO interpreter. (derived)
Machine: M1. `run_io_source(..., model="red2")` adapts the existing text streams and clock source to `Red2IoHost` and delegates the prepared RED2 action to `run_red2_io_action`; the `_IoRuntime` class remains the THOR-model action interpreter and contains no RED2 pure-reduction branch. M2. Existing RED2 UART examples preserve stdout byte-for-byte and final-result/stderr behavior. M3. Existing RED2 `CLOCK` behavior preserves both injected/fixed clock values and CLI `--clock <path>` latest-valid-value semantics. M4. RED2 recursive IO examples such as `examples/clock-dots.thor` and the bounded Breakout test continue without Python stack growth. M5. Pure `red2 --expr` behavior and THOR-model IO behavior remain unchanged.

**Authorized-by:** user request in chat on 2026-09-05; existing public behavior `models/python/red2_engine/cli.py:67-113`; current host layer `models/python/thor_engine/io_runtime.py:66-347`; Task 1 runtime contract above.

**Interfaces:**
- Consumes: `Red2IoHost`
- Consumes: `run_red2_io_action(action: Expr, *, definitions: Mapping[str, Expr], quantum: int, host: Red2IoHost) -> Expr`
- Produces: none

**Context:** This task genuinely depends on Task 1's runtime behavior: its proof must execute real RED2-owned sequencing/device effects through the public simulator path. Keep `ClockSource`, `SystemClockSource`, `LatestFileClockSource`, stdin readiness probing, and actual text-stream ownership in `thor_engine.io_runtime`; those are host/platform facilities, not graph-reducer semantics. Add a small adapter implementing Task 1's `Red2IoHost`: `uart_rx()` performs the existing nonblocking readiness check and returns `ord(char)`/`None`; `uart_tx(bytes)` writes each byte as its corresponding character to stdout and flushes once; `clock_ms()` calls the existing clock source. In `run_io_source`, parsing/normalization and `_prepare_io_program` may remain shared, but once `model == "red2"` is known, delegate the prepared action/definitions to `run_red2_io_action` and render its returned `Expr` with `to_source`. `_IoRuntime` should then be THOR-only: remove its `load_faithful_machine` import, RED2 definition cache conditionals, and RED2 branch in `_pure`. Preserve the current special removal of generated bare `CAR`/`CDR` definitions for faithful RED2 preparation if the faithful loader still requires it. `red2_engine.__init__` re-exports only the stable RED2 IO symbols needed by callers. `red2_engine.cli` should not need a new flag or stream-policy change; its existing call to `run_io_source(model="red2")` is the public path under test.

**Proof:**
- Test: `tests/test_io_runtime.py`
- Test: `tests/test_mured_cli.py`
- Legs: (a) existing RED2 assertions for `examples/uart-alphanumerics.thor` and `examples/uart-caesar-plus4.thor` remain byte-identical to their THOR-model expected stdout and return `NIL`, while a monkeypatch/counting seam proves `run_red2_io_action` is entered for the RED2 model [M1, M2]; (b) a fixed `ClockSource(1700000000456)` through `run_io_source(..., model="red2")` returns exactly `1700000000456`, and a `red2 --clock <tmp>` CLI test whose file contains malformed lines around two valid timestamps observes the latest valid timestamp in a UART-derived deterministic result [M3]; (c) the existing low-recursion deep IO chain gains a RED2-model row, and the clock-dots bounded-output test gains a RED2-model row that emits at least 20 dots under `sys.setrecursionlimit(80)` with no traceback [M4]; (d) the faithful pure-expression CLI corpus in `tests/test_mured_cli.py` remains unchanged and green, while representative THOR `UART-TX`, `UART-RX`, `IO-BIND`, `LEDS`, and `TICKS` tests retain their existing outputs [M5]; (e) source inspection of `models/python/thor_engine/io_runtime.py` shows `_IoRuntime._pure` has no `model == "red2"`/`load_faithful_machine` branch and the RED2 device path delegates through `run_red2_io_action` [M1].

**Stale-if:**
- sha-matches: `models/python/thor_engine/io_runtime.py`@b356de4d5bebb83a868fef7a0e5c935ba8e1dbbc71770175a5dbcdc1d1852348
- sha-matches: `models/python/red2_engine/__init__.py`@585a3e217ed0958aa03faaec644b2ac90c82e848f99e6c9f14685ca3722d380c

### Task 3: Document the RED2-owned IO boundary

**Type:** implementation

**Files:**
- Modify: `docs/thor-red2-prototype.md`
- Modify: `docs/thor-primitives.md`
- Test: `tests/test_docs_examples.py`

**Claim:** A reader can tell from the documentation that Python RED2 owns its UART/CLOCK action runner around a pure `MuredMachine`, while THOR keeps its separate simulator action path. (derived)
Machine: M1. `docs/thor-red2-prototype.md` states that Python RED2 has an `IoRunner`-style action layer around `MuredMachine`, analogous to Rust, replacing the old generic-host-layer description. M2. `docs/thor-primitives.md` identifies `UART-RX`, `UART-TX`, `UART-TX-BYTES`, and `CLOCK` as the Python RED2 device subset for this slice, while `LEDS` and `TICKS` remain THOR-host actions. M3. The docs retain the existing stdin/stdout/`--verbose`/`--clock` contract and explicitly state that UART/CLOCK host effects occur outside `MuredMachine.step()`/`run()`.

**Authorized-by:** user request in chat on 2026-09-05; current boundary statement `docs/thor-red2-prototype.md:30-38`; simulator API `docs/thor-primitives.md:176-218`.

**Interfaces:**
- Consumes: none
- Produces: none

**Context:** This task needs no sibling runtime behavior: write against the fixed architecture contract in this plan. The wording distinction matters. `MuredMachine` is still a pure faithful reducer. Python RED2 now owns a separate iterative action runner that calls `MuredMachine` for pure reductions and owns UART/CLOCK effects, matching the architectural split in Rust `IoRunner`/`Reducer`. Do not claim `LEDS` or `TICKS` as RED2-owned in this slice. Keep the current operator-facing examples and `--clock` latest-value semantics. `tests/test_docs_examples.py` is the distinct exam artifact; add narrow assertions for the new boundary rather than snapshots of whole paragraphs.

**Proof:**
- Test: `tests/test_docs_examples.py`
- Legs: (a) the prototype documentation contains a statement that Python RED2 owns an iterative IO runner around `MuredMachine` and does not contain the current sentence `The IO runtime remains a host/simulator layer for actions such as UART and CLOCK` [M1]; (b) the primitives documentation names all four `UART-RX`, `UART-TX`, `UART-TX-BYTES`, `CLOCK` as Python RED2-owned device actions and explicitly leaves `LEDS`/`TICKS` outside that subset [M2]; (c) assertions retain text describing stdout as UART output, verbose diagnostics on stderr, CLOCK milliseconds, and `--clock <path>` latest-value behavior, while also containing an explicit statement that host effects are outside `MuredMachine.step()`/`run()` [M3].

**Stale-if:**
- sha-matches: `docs/thor-red2-prototype.md`@e7fea8a739cb77922316c21f4d5092c443207c634fd96b437adfbff5aa1c5afd
- sha-matches: `docs/thor-primitives.md`@ddf1bf901a15f153c9bf2edc25c252d5336f59f8e4fee91b1b7fe6bb1ecfc5b1

### Task 4: RED2 IO integration gate

**Type:** gate
**Review:** peer

**Files:** none

**Claim:** The completed Python RED2 IO slice passes its focused ownership tests, the full Python quality gates, the existing Rust IO regression suite, and direct UART/CLOCK operator smokes. (derived)
Machine: M1. Focused RED2 IO and cross-model simulator tests pass. M2. Full Python pytest, Ruff, and mypy gates pass. M3. `cargo test -p red2-wasm` exits 0 at the integrated implementation head. M4. Direct `red2` UART and controlled-CLOCK smokes produce the exact expected stdout/stderr bytes.

**Authorized-by:** plan-level acceptance contract and the repository's established Python/Rust verification policy.

**Interfaces:**
- Consumes: none
- Produces: none

**Context:** This task writes nothing. Run it only against the integrated implementation head. The required Python commands are `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy models/python tests`; keep the repository's current mypy scope rather than the older `src tests` wording. Rust regression is `cargo test -p red2-wasm`. The UART smoke is `printf A | uv run red2 --verbose --expr '(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))'`: stdout must be exactly `A` and stderr exactly `io result: NIL` plus newline. For controlled CLOCK, create a temporary latest-value file containing `bad`, `1700000000065`, `garbage`; run `uv run red2 --clock <file> --expr '(IO-BIND (CLOCK) (LAMBDA (now) (UART-TX (MOD now 256))))'`; stdout must be exactly `A` and stderr empty. Remove the temporary file afterward and run `git diff --check`.

**Proof:**
- Test: `tests/test_red2_io_runtime.py`
- Test: `tests/test_io_runtime.py`
- Test: `tests/test_mured_cli.py`
- Test: `tests/test_docs_examples.py`
- Legs: (a) `uv run pytest -q tests/test_red2_io_runtime.py tests/test_io_runtime.py tests/test_mured_cli.py tests/test_docs_examples.py` exits 0 [M1]; (b) `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy models/python tests` all exit 0 [M2]; (c) `cargo test -p red2-wasm` exits 0 [M3]; (d) the UART smoke emits stdout exactly `A` and stderr exactly `io result: NIL\n`, the controlled-CLOCK smoke emits stdout exactly `A` and empty stderr, and `git diff --check` exits 0 [M4].

**Stale-if:**
- sha-matches: `models/python/red2_engine/cli.py`@d136e0e61a041dae39c85e4fea4f8ff43fbdb4271bdcb8b5215feb7627eeeff2

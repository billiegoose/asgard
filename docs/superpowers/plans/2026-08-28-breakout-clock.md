# Breakout CLOCK Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Python THOR/RED2 `(CLOCK)` IO support and a terminal-oriented Breakout example driven by controlled time and arrow keys.

**Architecture:** Extend the Python IO runtime with a clock-source abstraction, thread `--clock` through Python model subcommands and `mise run thor/red2`, then add `examples/breakout.thor` as a deterministic ANSI terminal game. Rust/Wasm clock support is explicitly deferred.

**Tech Stack:** Python 3.14, argparse, pytest, THOR source examples, ANSI terminal output, mise tasks.

**Spec:** `docs/superpowers/specs/2026-08-28-breakout-clock-design.md`

**Acceptance:** suite — committed Python runtime/CLI/mise tests plus Breakout fixture tests verify CLOCK semantics, controlled time, arrow input, ANSI rendering, and unchanged command behavior.

## Global Constraints

- `(CLOCK)` is a simulated IO action sequenced through the IO/world runtime, not a pure primitive.
- `(CLOCK)` returns a Unix timestamp in milliseconds as a THOR integer.
- `--clock <path>` is supported only for Python THOR/RED2 model runner commands in this phase.
- Controlled clock input is newline-delimited integer text; malformed lines are ignored.
- stdout remains terminal/device output.
- stderr remains quiet by default; `--verbose` enables final IO-result diagnostics.
- Do not implement Rust or Wasm support for `(CLOCK)` in this phase.
- Do not implement raw terminal mode in this phase.
- Breakout uses a fixed 20 column x 12 row board.

---

## File Structure

- `models/python/thor_spec/io_runtime.py`: add `ClockSource`, system clock, controlled latest-value clock, and `(CLOCK)` action handling.
- `models/python/thor_spec/cli.py`: accept and pass `--clock` on `thor-spec thor` and `thor-spec red2` model subcommands.
- `.mise.toml`: forward `--clock` for `mise run thor` and `mise run red2` only.
- `examples/breakout.thor`: terminal Breakout game example.
- `tests/test_io_runtime.py`: runtime CLOCK and Breakout behavior tests.
- `tests/test_cli_models.py`: Python CLI `--clock` tests.
- `tests/test_mise_tasks.py`: mise `--clock` forwarding tests.
- `tests/test_docs_examples.py`: docs/example assertions for Breakout.
- `README.md` and `docs/thor-primitives.md`: document CLOCK and Breakout usage.

---

### Task 1: Add Python CLOCK IO runtime support

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `models/python/thor_spec/io_runtime.py`
- Modify: `tests/test_io_runtime.py`

**Interfaces:**
- Consumes: existing `run_io_source(source, model, quantum, stdin, stdout, stderr) -> str`.
- Produces: `run_io_source(..., clock: ClockSource | None = None) -> str`; `ClockSource.now_ms() -> int`; `SystemClockSource`; `LatestFileClockSource(path: Path)`; IO action `(CLOCK)` returns `Integer(clock.now_ms())`.

**Parallelization rationale:** Runtime CLOCK behavior can be built and tested independently from CLI task forwarding and the Breakout example.

- [ ] **Step 1: Add failing CLOCK runtime tests**

  Append these imports to `tests/test_io_runtime.py` if missing:

  ```python
  from pathlib import Path
  ```

  Append these tests:

  ```python
  from thor_spec.io_runtime import LatestFileClockSource, run_io_source


  class FixedClock:
      def __init__(self, value: int) -> None:
          self.value = value

      def now_ms(self) -> int:
          return self.value


  def test_clock_io_action_returns_integer_for_thor_model() -> None:
      result = run_io_source(
          "(CLOCK)",
          model="thor",
          quantum=100,
          stdin=StringIO(""),
          stdout=StringIO(),
          stderr=StringIO(),
          clock=FixedClock(1_700_000_000_123),
      )

      assert result == "1700000000123"


  def test_clock_io_action_returns_integer_for_red2_model() -> None:
      result = run_io_source(
          "(CLOCK)",
          model="red2",
          quantum=100,
          stdin=StringIO(""),
          stdout=StringIO(),
          stderr=StringIO(),
          clock=FixedClock(1_700_000_000_456),
      )

      assert result == "1700000000456"


  def test_latest_file_clock_source_returns_latest_valid_value(tmp_path: Path) -> None:
      clock_file = tmp_path / "clock.txt"
      clock_file.write_text("1700000000000\nnot-a-clock\n1700000000123\n")
      clock = LatestFileClockSource(clock_file, initial_ms=123)

      assert clock.now_ms() == 1_700_000_000_123

      clock_file.write_text("1700000000000\nnot-a-clock\n1700000000123\n1700000000456\n")
      assert clock.now_ms() == 1_700_000_000_456
  ```

  If `StringIO` is not already imported in this file, import it from `io`.

- [ ] **Step 2: Run tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_io_runtime.py::test_clock_io_action_returns_integer_for_thor_model tests/test_io_runtime.py::test_clock_io_action_returns_integer_for_red2_model tests/test_io_runtime.py::test_latest_file_clock_source_returns_latest_valid_value -v
  ```

  Expected: import/signature/action failures because clock support does not exist.

- [ ] **Step 3: Implement clock sources and runtime injection**

  In `models/python/thor_spec/io_runtime.py`:

  - import `time`, `Path`, and `Protocol`.
  - add:

  ```python
  class ClockSource(Protocol):
      def now_ms(self) -> int: ...


  class SystemClockSource:
      def now_ms(self) -> int:
          return int(time.time() * 1000)


  class LatestFileClockSource:
      def __init__(self, path: Path, *, initial_ms: int | None = None) -> None:
          self._path = path
          self._latest = int(time.time() * 1000) if initial_ms is None else initial_ms

      def now_ms(self) -> int:
          try:
              text = self._path.read_text()
          except OSError:
              return self._latest
          for line in text.splitlines():
              try:
                  self._latest = int(line.strip())
              except ValueError:
                  continue
          return self._latest
  ```

  Update `run_io_source` signature to accept `clock: ClockSource | None = None` and pass `clock=clock or SystemClockSource()` into `_IoRuntime`.

  Update `_IoRuntime.__init__` to store `self._clock`.

- [ ] **Step 4: Implement `(CLOCK)` action handling**

  In `_IoRuntime._run_app`, add before unknown-action fallback:

  ```python
  if name == "CLOCK" and not args:
      return Integer(self._clock.now_ms())
  ```

- [ ] **Step 5: Run focused runtime validation**

  Run:

  ```sh
  uv run pytest tests/test_io_runtime.py -v
  uv run ruff check models/python/thor_spec/io_runtime.py tests/test_io_runtime.py
  uv run mypy models/python/thor_spec/io_runtime.py tests/test_io_runtime.py
  ```

  Expected: all pass.

- [ ] **Step 6: Commit Task 1**

  Run:

  ```sh
  git add models/python/thor_spec/io_runtime.py tests/test_io_runtime.py
  git commit -m "feat: add CLOCK IO source"
  ```

---

### Task 2: Thread `--clock` through Python CLI and mise tasks

**Type:** implementation
**Depends-on:** 1

**Files:**
- Modify: `models/python/thor_spec/cli.py`
- Modify: `.mise.toml`
- Modify: `tests/test_cli_models.py`
- Modify: `tests/test_mise_tasks.py`

**Interfaces:**
- Consumes: `LatestFileClockSource(path: Path)` and `run_io_source(..., clock=...)` from Task 1.
- Produces: `thor-spec thor <file-or-expr> --clock PATH`; `thor-spec red2 <file-or-expr> --clock PATH`; `mise run thor <file> --clock PATH`; `mise run red2 <file> --clock PATH`.

- [ ] **Step 1: Add failing CLI tests**

  Append to `tests/test_cli_models.py`:

  ```python
  def test_cli_thor_subcommand_uses_clock_file(
      capsys: CaptureFixture[str],
      tmp_path: Path,
  ) -> None:
      clock = tmp_path / "clock.txt"
      clock.write_text("1700000000123\n")

      assert main(["thor", "--clock", str(clock), "--expr", "(CLOCK)"]) == 0

      captured = capsys.readouterr()
      assert captured.out == ""
      assert captured.err == ""


  def test_cli_red2_subcommand_uses_clock_file(
      capsys: CaptureFixture[str],
      tmp_path: Path,
  ) -> None:
      clock = tmp_path / "clock.txt"
      clock.write_text("1700000000456\n")

      assert main(["red2", "--clock", str(clock), "--expr", "(CLOCK)"]) == 0

      captured = capsys.readouterr()
      assert captured.out == ""
      assert captured.err == ""
  ```

  These tests assert quiet command success. The final IO value is intentionally not printed without `--verbose`.

- [ ] **Step 2: Add failing mise forwarding test**

  Append to `tests/test_mise_tasks.py`:

  ```python
  def test_mise_python_tasks_accept_clock_flag(tmp_path: Path) -> None:
      source = tmp_path / "clock.thor"
      source.write_text("(IO-BIND (CLOCK) (LAMBDA (now) (UART-TX 65)))\n")
      clock = tmp_path / "clock.txt"
      clock.write_text("1700000000123\n")

      thor = run_mise_task("thor", str(source), "--clock", str(clock))
      red2 = run_mise_task("red2", str(source), "--clock", str(clock))

      assert thor.returncode == 0
      assert thor.stdout == "A"
      assert thor.stderr == ""
      assert red2.returncode == 0
      assert red2.stdout == "A"
      assert red2.stderr == ""
  ```

- [ ] **Step 3: Run tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_cli_models.py::test_cli_thor_subcommand_uses_clock_file tests/test_cli_models.py::test_cli_red2_subcommand_uses_clock_file tests/test_mise_tasks.py::test_mise_python_tasks_accept_clock_flag -v
  ```

  Expected: parser/task failures because `--clock` is not accepted yet.

- [ ] **Step 4: Implement Python CLI forwarding**

  In `models/python/thor_spec/cli.py`:

  - import `LatestFileClockSource` from `thor_spec.io_runtime`.
  - in `_run_model_command`, add:

  ```python
  parser.add_argument(
      "--clock",
      type=Path,
      help="path to a latest-value clock source with newline-delimited millisecond timestamps",
  )
  ```

  - construct the clock before `_run_io`:

  ```python
  clock = LatestFileClockSource(args.clock) if args.clock is not None else None
  ```

  - pass `clock=clock` into `_run_io`.
  - update `_run_io` signature to accept `clock: ClockSource | None = None` or avoid importing the protocol by leaving the parameter unannotated as `clock: object | None = None` only if mypy remains clean. Prefer importing `ClockSource` and using the precise type.
  - pass `clock=clock` into `run_io_source`.

- [ ] **Step 5: Update mise tasks**

  In `.mise.toml`, add to `[tasks.thor]` and `[tasks.red2]` usage blocks:

  ```toml
  flag "--clock <path>" help="latest-value clock source for CLOCK"
  ```

  Update each run command to append the flag only when set:

  ```sh
  ${usage_clock:+--clock "$usage_clock"}
  ```

  Keep `rust`, `wasm`, `parity`, and `hdl` tasks unchanged.

- [ ] **Step 6: Run focused CLI/mise validation**

  Run:

  ```sh
  mise tasks validate
  uv run pytest tests/test_cli_models.py tests/test_mise_tasks.py -v
  uv run ruff check models/python/thor_spec/cli.py tests/test_cli_models.py tests/test_mise_tasks.py
  uv run mypy models/python/thor_spec/cli.py tests/test_cli_models.py tests/test_mise_tasks.py
  ```

  Expected: all pass.

- [ ] **Step 7: Commit Task 2**

  Run:

  ```sh
  git add models/python/thor_spec/cli.py .mise.toml tests/test_cli_models.py tests/test_mise_tasks.py
  git commit -m "feat: add clock control to Python runners"
  ```

---

### Task 3: Add terminal Breakout example and behavior tests

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Create: `examples/breakout.thor`
- Modify: `tests/test_io_runtime.py`
- Modify: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: `(CLOCK)` IO action from Task 1 and existing UART actions.
- Produces: `examples/breakout.thor`, a 20x12 ANSI terminal Breakout game that works under Python THOR and RED2 IO runners.

**Parallelization rationale:** The example can be developed against the runtime CLOCK interface before CLI/mise forwarding is integrated.

- [ ] **Step 1: Add failing docs/example existence test**

  Append to `tests/test_docs_examples.py`:

  ```python
  def test_breakout_example_documents_terminal_game_sections() -> None:
      breakout = Path("examples/breakout.thor").read_text()

      for section in [
          "; --- constants ---",
          "; --- terminal rendering ---",
          "; --- input decoding ---",
          "; --- game physics ---",
          "; --- game loop ---",
      ]:
          assert section in breakout
      assert "CLOCK" in breakout
      assert "ESC [2J" in breakout
      assert "20x12" in breakout
  ```

- [ ] **Step 2: Add failing Breakout behavior tests**

  Append to `tests/test_io_runtime.py`:

  ```python
  def run_breakout_for_test(stdin_text: str, clock_value: int = 1_700_000_000_000) -> tuple[str, str]:
      stdout = StringIO()
      stderr = StringIO()
      result = run_io_source(
          Path("examples/breakout.thor").read_text(),
          model="thor",
          quantum=8000,
          stdin=StringIO(stdin_text),
          stdout=stdout,
          stderr=stderr,
          clock=FixedClock(clock_value),
      )
      assert result == "NIL"
      return stdout.getvalue(), stderr.getvalue()


  def test_breakout_initial_frame_uses_ansi_and_fixed_board() -> None:
      stdout, stderr = run_breakout_for_test("q")

      assert stdout.startswith("\x1b[2J\x1b[H")
      assert "BREAKOUT 20x12" in stdout
      assert "SCORE: 0" in stdout
      assert "LIVES: 3" in stdout
      assert "####################" in stdout
      assert "QUIT" in stdout
      assert stderr == ""


  def test_breakout_arrow_keys_move_paddle() -> None:
      left_stdout, _ = run_breakout_for_test("\x1b[Dq")
      right_stdout, _ = run_breakout_for_test("\x1b[Cq")

      assert "PADDLE: 7" in left_stdout
      assert "PADDLE: 9" in right_stdout


  def test_breakout_clock_tick_moves_ball() -> None:
      stdout, _ = run_breakout_for_test(" q", clock_value=1_700_000_000_200)

      assert "BALL: 11,7" in stdout


  def test_breakout_can_report_score_after_brick_hit() -> None:
      stdout, _ = run_breakout_for_test("        q", clock_value=1_700_000_001_000)

      assert "SCORE: 1" in stdout
  ```

  These tests define the minimum observable contract. The implementation may render richer board art as long as these strings remain true.

- [ ] **Step 3: Run tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py::test_breakout_example_documents_terminal_game_sections tests/test_io_runtime.py::test_breakout_initial_frame_uses_ansi_and_fixed_board tests/test_io_runtime.py::test_breakout_arrow_keys_move_paddle tests/test_io_runtime.py::test_breakout_clock_tick_moves_ball tests/test_io_runtime.py::test_breakout_can_report_score_after_brick_hit -v
  ```

  Expected: file-not-found failures because `examples/breakout.thor` does not exist.

- [ ] **Step 4: Create `examples/breakout.thor`**

  Create a self-contained THOR program with these exact section comments:

  ```lisp
  ; Breakout 20x12 over ANSI terminal UART.
  ; ESC [2J clears the terminal and ESC [H homes the cursor.
  ; Use left/right arrow keys to move. Press q to quit.

  ; --- constants ---
  ```

  Required constants:

  ```lisp
  ESC == 27
  LBRACKET == 91
  LEFT == 68
  RIGHT == 67
  QLOW == 113
  QUP == 81
  NL == 10
  SPACE == 32
  TICK-MS == 100
  WIDTH == 20
  HEIGHT == 12
  ```

  Implement terminal rendering helpers using `UART-TX`, `IO-THEN`, and small fixed emitters. Each rendered frame must emit these debug/status lines in addition to board art:

  ```text
  BREAKOUT 20x12
  SCORE: <score>
  LIVES: <lives>
  PADDLE: <x>
  BALL: <x>,<y>
  ```

  Implement input decoding for `ESC [ D`, `ESC [ C`, `q`, and ignored bytes.

  Implement a fixed initial state:

  ```text
  score = 0
  lives = 3
  paddle-x = 8
  ball-x = 10
  ball-y = 8
  dx = 1
  dy = -1
  last-tick = 1700000000000
  first brick row contains at least one brick reachable after deterministic ticks
  ```

  Implement one loop iteration per input byte. Each iteration:

  1. reads a byte from `UART-RX`.
  2. decodes arrow/quit/ignored input.
  3. reads `(CLOCK)`.
  4. if `now - last-tick >= TICK-MS`, advances the ball once or more simply once.
  5. renders the new frame.
  6. recurs unless quit/win/lose.

  Keep the implementation intentionally compact and deterministic. If exact physical Breakout collision modeling becomes too large, prefer a small fixed brick layout and simple collision predicates over general data structures.

- [ ] **Step 5: Run focused Breakout validation**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py::test_breakout_example_documents_terminal_game_sections tests/test_io_runtime.py::test_breakout_initial_frame_uses_ansi_and_fixed_board tests/test_io_runtime.py::test_breakout_arrow_keys_move_paddle tests/test_io_runtime.py::test_breakout_clock_tick_moves_ball tests/test_io_runtime.py::test_breakout_can_report_score_after_brick_hit -v
  uv run ruff check tests/test_docs_examples.py tests/test_io_runtime.py
  uv run mypy tests/test_docs_examples.py tests/test_io_runtime.py
  ```

  Expected: all pass.

- [ ] **Step 6: Confirm Python RED2 can run Breakout quit smoke**

  Run:

  ```sh
  printf q | mise run red2 examples/breakout.thor --quantum 12000 >/tmp/asgard-breakout-red2.out 2>/tmp/asgard-breakout-red2.err
  test ! -s /tmp/asgard-breakout-red2.err
  rg -q 'BREAKOUT 20x12' /tmp/asgard-breakout-red2.out
  rg -q 'QUIT' /tmp/asgard-breakout-red2.out
  ```

  Expected: all commands pass.

- [ ] **Step 7: Commit Task 3**

  Run:

  ```sh
  git add examples/breakout.thor tests/test_io_runtime.py tests/test_docs_examples.py
  git commit -m "feat: add terminal Breakout example"
  ```

---

### Task 4: Document CLOCK and Breakout usage

**Type:** implementation
**Depends-on:** 2, 3

**Files:**
- Modify: `README.md`
- Modify: `docs/thor-primitives.md`
- Modify: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: `--clock` Python task support from Task 2 and `examples/breakout.thor` from Task 3.
- Produces: user-facing docs for `(CLOCK)`, controlled clocks, and Breakout commands.

- [ ] **Step 1: Add failing docs assertions**

  Append to `tests/test_docs_examples.py`:

  ```python
  def test_docs_describe_clock_and_breakout() -> None:
      readme = Path("README.md").read_text()
      primitives = Path("docs/thor-primitives.md").read_text()

      assert "mise run thor examples/breakout.thor --clock" in readme
      assert "mise run red2 examples/breakout.thor --clock" in readme
      assert "CLOCK" in primitives
      assert "Unix timestamp" in primitives
      assert "latest-value clock" in primitives
  ```

- [ ] **Step 2: Run docs assertions and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py::test_docs_describe_clock_and_breakout -v
  ```

  Expected: fails because docs do not mention Breakout/CLOCK yet.

- [ ] **Step 3: Update README**

  Add a short Breakout example near the existing `mise run` example section:

  ```markdown
  Run terminal Breakout with a controlled latest-value clock source:

  ```sh
  mise run thor examples/breakout.thor --clock /tmp/asgard-clock
  mise run red2 examples/breakout.thor --clock /tmp/asgard-clock
  ```

  The `--clock` file is newline-delimited millisecond timestamps; the runtime
  uses the latest valid value and ignores malformed lines. Rust/Wasm CLOCK
  support is deferred.
  ```
  ```

- [ ] **Step 4: Update primitive reference**

  In `docs/thor-primitives.md`, add `(CLOCK)` under simulator IO actions:

  ```markdown
  - `(CLOCK)` returns the current Unix timestamp in milliseconds as an integer.
    It is an IO action and must be sequenced with `IO-BIND`/`IO-THEN`. Python
    THOR/RED2 runners support `--clock <path>` as a latest-value clock source for
    deterministic tests.
  ```

- [ ] **Step 5: Run docs validation**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py -v
  uv run ruff check tests/test_docs_examples.py
  ```

  Expected: all pass.

- [ ] **Step 6: Commit Task 4**

  Run:

  ```sh
  git add README.md docs/thor-primitives.md tests/test_docs_examples.py
  git commit -m "docs: document Breakout clock IO"
  ```

---

### Task 5: Final verification gate

**Type:** gate
**Depends-on:** 4

**Files:**
- Test: full project verification only

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: verified Breakout/CLOCK feature with stable existing commands.

- [ ] **Step 1: Run canonical verification**

  Run:

  ```sh
  mise run verify
  ```

  Expected: pytest, Ruff, mypy, and Rust tests all pass.

- [ ] **Step 2: Run Breakout task smokes**

  Run:

  ```sh
  clock=/tmp/asgard-breakout-clock.txt
  printf '1700000000000\n1700000000200\n' > "$clock"

  printf q | mise run thor examples/breakout.thor --clock "$clock" --quantum 12000 >/tmp/asgard-breakout-thor.out 2>/tmp/asgard-breakout-thor.err
  test ! -s /tmp/asgard-breakout-thor.err
  rg -q 'BREAKOUT 20x12' /tmp/asgard-breakout-thor.out
  rg -q 'QUIT' /tmp/asgard-breakout-thor.out

  printf q | mise run red2 examples/breakout.thor --clock "$clock" --quantum 12000 >/tmp/asgard-breakout-red2.out 2>/tmp/asgard-breakout-red2.err
  test ! -s /tmp/asgard-breakout-red2.err
  rg -q 'BREAKOUT 20x12' /tmp/asgard-breakout-red2.out
  rg -q 'QUIT' /tmp/asgard-breakout-red2.out
  ```

  Expected: both smokes pass.

- [ ] **Step 3: Confirm Rust/Wasm remain unchanged**

  Run:

  ```sh
  printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000 >/tmp/asgard-hangman-rust.out 2>/tmp/asgard-hangman-rust.err
  test ! -s /tmp/asgard-hangman-rust.err
  rg -q 'WIN' /tmp/asgard-hangman-rust.out
  ```

  Expected: Rust Hangman still passes; no Rust CLOCK support is implied.

- [ ] **Step 4: Confirm working tree status**

  Run:

  ```sh
  git status --short
  ```

  Expected: no unstaged or uncommitted implementation changes.

## Operator smoke

- do: `printf q | mise run thor examples/breakout.thor --quantum 12000`
- see: terminal output starts with ANSI clear/home, shows `BREAKOUT 20x12`, and ends with `QUIT`.

- do: `printf '\033[Cq' | mise run thor examples/breakout.thor --quantum 12000`
- see: output includes a later frame with `PADDLE: 9`.

- do: `clock=/tmp/asgard-breakout-clock.txt; printf '1700000000200\n' > "$clock"; printf ' q' | mise run red2 examples/breakout.thor --clock "$clock" --quantum 12000`
- see: output includes `BALL: 11,7`.

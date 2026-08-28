# Rust/WASM Breakout CLOCK Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the Rust native and WASI RED2 engine to run `examples/breakout.thor` with real or simulated CLOCK support, and document the WASM demonstration recording.

**Architecture:** Add a Rust clock-source abstraction and thread it through the existing `red2-wasm` CLI and `IoRunner`. Widen Rust runtime integers to `i64` so Unix millisecond timestamps can flow through IO and primitive evaluation without overflow. Expose `--clock <path>` on `mise run rust` and `mise run wasm`, then add tests/docs/recording for Breakout.

**Tech Stack:** Rust 2021 std-only crate, WASI `wasm32-wasi`, Wasmtime, Python 3.14 pytest, mise tasks, asciinema v2 cast files.

**Spec:** `docs/superpowers/specs/2026-08-28-rust-wasm-breakout-clock-design.md`

**Acceptance:** suite — committed Rust unit tests, pytest CLI/task tests, docs assertions, and final cargo/pytest/mise smoke gates verify Rust/WASM CLOCK and Breakout behavior.

## Global Constraints

- Rust native and WASI executions support `(CLOCK)` as an IO action.
- With no clock flag, `(CLOCK)` returns the host Unix timestamp in milliseconds.
- With `--clock <path>`, `(CLOCK)` uses a latest-value file clock: read newline-delimited integer millisecond timestamps, keep the latest valid value, ignore malformed lines, and retain the previous value if the file is absent or unreadable.
- `mise run rust` and `mise run wasm` expose `--clock <path>` using the same behavior as Python tasks.
- Existing stdout/stderr policy remains unchanged: stdout is UART/device output, success diagnostics appear only under `--verbose`.
- Do not change the `.red2` bytecode container format.
- Do not add external Rust dependencies.

---

## File Structure

- `models/rust-red2/src/vm.rs`: runtime expression values, reducer primitives, IO action runner, and new clock-source types.
- `models/rust-red2/src/main.rs`: CLI argument parsing and clock-source construction for native/WASI runs.
- `.mise.toml`: user-facing Rust/WASM task flags and command forwarding.
- `tests/test_red2_wasm_cli.py`: bytecode-to-Rust CLI tests for `(CLOCK)` and Breakout.
- `tests/test_mise_tasks.py`: `mise run rust/wasm` controlled-clock integration tests.
- `tests/test_docs_examples.py`: docs/recording reference assertions.
- `README.md`, `docs/thor-primitives.md`, `docs/red2-bytecode.md`, `examples/README.md`: remove deferred-language and document Rust/WASM clock usage.
- `examples/media/breakout-wasm.cast`: deterministic asciinema v2 recording artifact for WASM Breakout.

### Task 1: Add Rust runtime CLOCK support

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Modify: `models/rust-red2/src/vm.rs`

**Interfaces:**
- Consumes: existing `run_io_bundle<R: Read, W: Write>(bundle: &ProgramBundle, quantum: u32, input: &mut R, output: &mut W) -> Result<Expr, Red2Error>`.
- Produces: `pub trait ClockSource { fn now_ms(&mut self) -> i64; }`, `pub struct SystemClockSource`, `pub struct LatestFileClockSource`, `pub fn run_io_bundle_with_clock<R: Read, W: Write, C: ClockSource>(bundle: &ProgramBundle, quantum: u32, input: &mut R, output: &mut W, clock: &mut C) -> Result<Expr, Red2Error>`, and `Expr::Int(i64)`.

**Parallelization rationale:** This task owns the engine contract; CLI/task/docs work can proceed against the named interfaces once this lands.

- [ ] **Step 1: Add failing Rust unit tests for clock sources and CLOCK IO**

  In `models/rust-red2/src/vm.rs`, append tests to the existing `#[cfg(test)] mod tests` block. Use unique temporary file names based on `std::process::id()`.

  ```rust
  #[test]
  fn latest_file_clock_uses_latest_valid_line_and_keeps_previous_on_bad_input() {
      let path = std::env::temp_dir().join(format!(
          "asgard-clock-{}-latest.txt",
          std::process::id()
      ));
      let _ = std::fs::remove_file(&path);
      std::fs::write(&path, "1700000000123\nnot-a-clock\n1700000000456\n").unwrap();
      let mut clock = LatestFileClockSource::new(path.clone(), 123);

      assert_eq!(clock.now_ms(), 1_700_000_000_456);

      std::fs::write(&path, "bad\n").unwrap();
      assert_eq!(clock.now_ms(), 1_700_000_000_456);
      let _ = std::fs::remove_file(path);
  }

  0  // replace this marker with the real next test below; it exists only to make the first edit easy to locate while drafting
  ```

  Replace the marker with this second test before running:

  ```rust
  struct FixedClock(i64);

  impl ClockSource for FixedClock {
      fn now_ms(&mut self) -> i64 {
          self.0
      }
  }

  #[test]
  fn io_clock_action_returns_clock_milliseconds() {
      let program = program(vec![Instruction {
          opcode: Opcode::Sym,
          head: true,
          data: Data::String("CLOCK".to_string()),
      }]);
      let bundle = ProgramBundle {
          entry_index: 0,
          programs: vec![program],
          definitions: BTreeMap::new(),
      };
      let mut input = std::io::empty();
      let mut output = Vec::new();
      let mut clock = FixedClock(1_700_000_000_789);

      assert_eq!(
          run_io_bundle_with_clock(&bundle, 10, &mut input, &mut output, &mut clock)
              .unwrap()
              .to_source(),
          "1700000000789"
      );
      assert!(output.is_empty());
  }
  ```

- [ ] **Step 2: Run tests and verify they fail**

  Run: `cargo test -p red2-wasm latest_file_clock_uses_latest_valid_line_and_keeps_previous_on_bad_input io_clock_action_returns_clock_milliseconds`

  Expected: FAIL because `LatestFileClockSource`, `ClockSource`, and `run_io_bundle_with_clock` do not exist.

- [ ] **Step 3: Implement `i64` runtime integers and clock source types**

  In `models/rust-red2/src/vm.rs`:

  - Change `Expr::Int(i32)` to `Expr::Int(i64)`.
  - Convert decoded `Data::Int(value)` with `i64::from(value)` in `instruction_expr`.
  - Keep UART conversion byte-safe with `byte.rem_euclid(256) as u8`.
  - Add:

  ```rust
  use std::path::PathBuf;
  use std::time::{SystemTime, UNIX_EPOCH};

  pub trait ClockSource {
      fn now_ms(&mut self) -> i64;
  }

  pub struct SystemClockSource;

  impl ClockSource for SystemClockSource {
      fn now_ms(&mut self) -> i64 {
          match SystemTime::now().duration_since(UNIX_EPOCH) {
              Ok(duration) => duration.as_millis().min(i64::MAX as u128) as i64,
              Err(_) => 0,
          }
      }
  }

  pub struct LatestFileClockSource {
      path: PathBuf,
      latest: i64,
  }

  impl LatestFileClockSource {
      pub fn new(path: PathBuf, initial_ms: i64) -> Self {
          Self { path, latest: initial_ms }
      }
  }

  impl ClockSource for LatestFileClockSource {
      fn now_ms(&mut self) -> i64 {
          let Ok(text) = std::fs::read_to_string(&self.path) else {
              return self.latest;
          };
          for line in text.lines() {
              if let Ok(value) = line.trim().parse::<i64>() {
                  self.latest = value;
              }
          }
          self.latest
      }
  }
  ```

- [ ] **Step 4: Thread clock through `IoRunner`**

  Update `IoRunner` to hold `clock: &'a mut dyn ClockSource`. Add `CLOCK` handling in both symbol and application paths:

  ```rust
  if name == "CLOCK" {
      return Ok(Expr::Int(self.clock.now_ms()));
  }
  ```

  and:

  ```rust
  ("CLOCK", []) => return Ok(Expr::Int(self.clock.now_ms())),
  ```

  Change `run_io_bundle` to construct a `SystemClockSource` and delegate to `run_io_bundle_with_clock`. Implement the produced public function with the same parse/reducer setup as the current `run_io_bundle`, passing the supplied clock into `IoRunner`.

- [ ] **Step 5: Run Rust tests**

  Run: `cargo test -p red2-wasm`

  Expected: PASS.

- [ ] **Step 6: Commit**

  ```bash
  git add models/rust-red2/src/vm.rs
  git commit -m "feat: add rust red2 clock io"
  ```

### Task 2: Add Rust CLI and bytecode tests for CLOCK and Breakout

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial
**Commutes:** `tests/test_red2_wasm_cli.py`

**Files:**
- Modify: `models/rust-red2/src/main.rs`
- Modify: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: `LatestFileClockSource::new(path: PathBuf, initial_ms: i64) -> LatestFileClockSource`, `SystemClockSource`, and `run_io_bundle_with_clock<R, W, C>(...) -> Result<Expr, Red2Error>` from Task 1.
- Produces: `red2-wasm <program.red2> [--quantum N] [--clock PATH] [--verbose]`.

**Parallelization rationale:** CLI parsing and pytest coverage are independent from mise wiring and docs once the engine API exists.

- [ ] **Step 1: Add failing pytest CLI tests**

  In `tests/test_red2_wasm_cli.py`, extend `run_rust_vm` with `clock: Path | None = None`. Append `--clock`, `str(clock)` to `command` when provided.

  Add these tests:

  ```python
  def test_rust_red2_vm_io_clock_uses_latest_file_value(tmp_path: Path) -> None:
      bytecode = write_bytecode(
          tmp_path,
          """
          (IO-BIND (CLOCK)
            (LAMBDA (now)
              (UART-TX (MOD now 256))))
          """,
      )
      clock = tmp_path / "clock.txt"
      clock.write_text("bad\n1700000000065\n")

      result = run_rust_vm(bytecode, quantum=100, clock=clock)

      assert result.returncode == 0
      assert result.stdout == "A"
      assert result.stderr == ""


  def test_rust_red2_vm_io_clock_defaults_to_system_time(tmp_path: Path) -> None:
      bytecode = write_bytecode(
          tmp_path,
          """
          (IO-BIND (CLOCK)
            (LAMBDA (now)
              (if (> now 1000000000000)
                  (UART-TX 89)
                  (UART-TX 78))))
          """,
      )

      result = run_rust_vm(bytecode, quantum=100)

      assert result.returncode == 0
      assert result.stdout == "Y"
      assert result.stderr == ""


  def test_rust_red2_vm_io_runs_breakout_with_controlled_clock(tmp_path: Path) -> None:
      bytecode = write_bytecode(tmp_path, Path("examples/breakout.thor").read_text())
      clock = tmp_path / "breakout-clock.txt"
      clock.write_text("1700000000200\n")

      result = run_rust_vm(
          bytecode,
          quantum=12000,
          stdin=" q",
          clock=clock,
          timeout=30.0,
      )

      assert result.returncode == 0
      assert "BREAKOUT 20x12\n" in result.stdout
      assert "QUIT\n" in result.stdout
      assert "\x1b[" in result.stdout
      assert result.stderr == ""
  ```

- [ ] **Step 2: Run tests and verify they fail**

  Run: `uv run pytest tests/test_red2_wasm_cli.py::test_rust_red2_vm_io_clock_uses_latest_file_value tests/test_red2_wasm_cli.py::test_rust_red2_vm_io_clock_defaults_to_system_time tests/test_red2_wasm_cli.py::test_rust_red2_vm_io_runs_breakout_with_controlled_clock -v`

  Expected: FAIL because the CLI does not accept `--clock` and/or `CLOCK` is not recognized before Task 1 is present.

- [ ] **Step 3: Implement CLI argument parsing and clock selection**

  In `models/rust-red2/src/main.rs`:

  - Update usage to `usage: red2-wasm <program.red2> [--quantum N] [--clock PATH] [--verbose]`.
  - Add `let mut clock_path: Option<String> = None;`.
  - Parse `--clock` with a required following value; on missing value print `red2-wasm: --clock requires a value` and exit 2.
  - Import `LatestFileClockSource` and `SystemClockSource`.
  - For IO execution, use:

  ```rust
  if let Some(path) = clock_path {
      let mut clock = vm::LatestFileClockSource::new(path.into(), vm::SystemClockSource.now_ms());
      vm::run_io_bundle_with_clock(&bundle, quantum, &mut stdin, &mut stdout, &mut clock)
          .map(RunOutcome::Io)
  } else {
      vm::run_io_bundle(&bundle, quantum, &mut stdin, &mut stdout).map(RunOutcome::Io)
  }
  ```

  If method-call syntax on `SystemClockSource` is awkward, instantiate `let mut system_clock = vm::SystemClockSource; let initial = system_clock.now_ms();` and import the `ClockSource` trait.

- [ ] **Step 4: Run CLI tests**

  Run: `uv run pytest tests/test_red2_wasm_cli.py -v`

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add models/rust-red2/src/main.rs tests/test_red2_wasm_cli.py
  git commit -m "feat: add rust red2 clock cli"
  ```

### Task 3: Wire mise Rust/WASM tasks and integration tests

**Type:** implementation
**Depends-on:** 1, 2
**Review:** adversarial
**Commutes:** `tests/test_mise_tasks.py`

**Files:**
- Modify: `.mise.toml`
- Modify: `tests/test_mise_tasks.py`

**Interfaces:**
- Consumes: `red2-wasm <program.red2> [--quantum N] [--clock PATH] [--verbose]` from Task 2.
- Produces: `mise run rust <file> [--quantum N] [--clock PATH] [--verbose]` and `mise run wasm <file> [--quantum N] [--clock PATH] [--verbose]`.

**Parallelization rationale:** Task wrapper forwarding is separate from the engine implementation and can be reviewed via integration tests.

- [ ] **Step 1: Add failing mise task tests**

  In `tests/test_mise_tasks.py`, add:

  ```python
  def test_mise_rust_accepts_clock_flag(tmp_path: Path) -> None:
      source = tmp_path / "clock.thor"
      source.write_text(
          """
          (IO-BIND (CLOCK)
            (LAMBDA (now)
              (UART-TX (MOD now 256))))
          """
      )
      clock = tmp_path / "clock.txt"
      clock.write_text("1700000000065\n")

      result = run_mise_task("rust", str(source), "--clock", str(clock))

      assert result.returncode == 0
      assert result.stdout == "A"
      assert result.stderr == ""


  def test_mise_wasm_runs_breakout_with_controlled_clock(tmp_path: Path) -> None:
      clock = tmp_path / "breakout-clock.txt"
      clock.write_text("1700000000200\n")

      result = run_mise_task(
          "wasm",
          "examples/breakout.thor",
          "--quantum",
          "12000",
          "--clock",
          str(clock),
          stdin=" q",
          timeout=90.0,
      )

      assert result.returncode == 0
      assert "BREAKOUT 20x12\n" in result.stdout
      assert "QUIT\n" in result.stdout
      assert "\x1b[" in result.stdout
      assert result.stderr == ""
  ```

- [ ] **Step 2: Run tests and verify they fail**

  Run: `uv run pytest tests/test_mise_tasks.py::test_mise_rust_accepts_clock_flag tests/test_mise_tasks.py::test_mise_wasm_runs_breakout_with_controlled_clock -v`

  Expected: FAIL because `mise run rust` and `mise run wasm` do not accept `--clock`.

- [ ] **Step 3: Add task flags and forwarding**

  In `.mise.toml`, add `flag "--clock <path>" help="latest-value clock source for CLOCK"` to `[tasks.rust]` and `[tasks.wasm]` usage blocks.

  In both run scripts, append `${usage_clock:+--clock "$usage_clock"}` to the `cargo run` or `wasmtime` invocation after `--quantum "${usage_quantum?}"` and before verbose forwarding.

- [ ] **Step 4: Run integration tests**

  Run: `uv run pytest tests/test_mise_tasks.py -v`

  Expected: PASS.

- [ ] **Step 5: Commit**

  ```bash
  git add .mise.toml tests/test_mise_tasks.py
  git commit -m "feat: expose clock for rust wasm tasks"
  ```

### Task 4: Update docs and add WASM Breakout recording

**Type:** implementation
**Depends-on:** 3

**Files:**
- Modify: `README.md`
- Modify: `docs/thor-primitives.md`
- Modify: `docs/red2-bytecode.md`
- Modify: `examples/README.md`
- Modify: `tests/test_docs_examples.py`
- Create: `examples/media/breakout-wasm.cast`

**Interfaces:**
- Consumes: `mise run rust/wasm <file> --clock <path>` from Task 3.
- Produces: documentation and recording reference for WASM Breakout.

**Parallelization rationale:** Documentation and recording are downstream of task wiring because examples must cite commands that work.

- [ ] **Step 1: Add failing docs tests**

  In `tests/test_docs_examples.py`, update or add assertions so docs must mention Rust/WASM clock support and the WASM cast:

  ```python
  def test_docs_describe_rust_wasm_clock_and_breakout() -> None:
      readme = Path("README.md").read_text()
      primitives = Path("docs/thor-primitives.md").read_text()
      bytecode = Path("docs/red2-bytecode.md").read_text()
      examples = Path("examples/README.md").read_text()

      assert "mise run rust examples/breakout.thor --clock" in readme
      assert "mise run wasm examples/breakout.thor --clock" in readme
      assert "Rust/Wasm runners support `--clock <path>`" in primitives
      assert "--clock <path>" in bytecode
      assert "examples/media/breakout-wasm.cast" in examples


  def test_wasm_breakout_cast_is_committed_asciicast_v2() -> None:
      cast = Path("examples/media/breakout-wasm.cast")
      first_line = cast.read_text().splitlines()[0]

      assert '"version": 2' in first_line
      assert '"Asgard Breakout WASM"' in first_line
  ```

- [ ] **Step 2: Run tests and verify they fail**

  Run: `uv run pytest tests/test_docs_examples.py::test_docs_describe_rust_wasm_clock_and_breakout tests/test_docs_examples.py::test_wasm_breakout_cast_is_committed_asciicast_v2 -v`

  Expected: FAIL because docs and recording do not exist yet.

- [ ] **Step 3: Update docs**

  Update `README.md` Breakout section to show all four runners. Include exact commands:

  ```sh
  mise run thor examples/breakout.thor --clock /tmp/asgard-clock
  mise run red2 examples/breakout.thor --clock /tmp/asgard-clock
  mise run rust examples/breakout.thor --clock /tmp/asgard-clock
  mise run wasm examples/breakout.thor --clock /tmp/asgard-clock
  ```

  Replace the sentence `Rust/Wasm CLOCK support is deferred.` with language saying Rust/Wasm support both real system clock by default and `--clock <path>` controlled latest-value clock.

  In `docs/thor-primitives.md`, replace the Python-only clock sentence with: `Python THOR/RED2 and Rust/Wasm runners support \`--clock <path>\` as a latest-value clock source for deterministic tests; malformed clock lines are ignored.`

  In `docs/red2-bytecode.md`, add a Rust/WASM example with `--clock <path>` near existing `mise run rust` / `mise run wasm` commands.

- [ ] **Step 4: Create deterministic WASM Breakout asciinema cast**

  Create `examples/media/breakout-wasm.cast` as asciinema v2 JSON-lines. It must include a header with title `Asgard Breakout WASM` and output frames showing the command surface and Breakout screen. If regenerating with `asciinema rec` is available, run a controlled-clock WASM command and sanitize timing. If not, create a deterministic compact v2 cast by adapting `examples/media/breakout.cast` content and changing the title to `Asgard Breakout WASM` while keeping visible Breakout frames and cursor restore output.

  The first line must be valid JSON containing:

  ```json
  {"version": 2, "width": 80, "height": 24, "timestamp": 1700000000, "env": {"TERM": "xterm-256color"}, "title": "Asgard Breakout WASM"}
  ```

- [ ] **Step 5: Update examples README**

  In `examples/README.md`, add a subsection under Breakout:

  ```markdown
  Watch the committed WASM Breakout recording:

  ```sh
  asciinema play examples/media/breakout-wasm.cast
  ```
  ```

  Ensure the file includes the literal `examples/media/breakout-wasm.cast`.

- [ ] **Step 6: Run docs tests**

  Run: `uv run pytest tests/test_docs_examples.py tests/test_example_recordings.py -v`

  Expected: PASS.

- [ ] **Step 7: Commit**

  ```bash
  git add README.md docs/thor-primitives.md docs/red2-bytecode.md examples/README.md tests/test_docs_examples.py examples/media/breakout-wasm.cast
  git commit -m "docs: add wasm breakout recording"
  ```

### Task 5: Final verification gate

**Type:** gate
**Depends-on:** 1, 2, 3, 4

**Files:**
- Test: `cargo test -p red2-wasm`
- Test: `uv run pytest tests/test_red2_wasm_cli.py tests/test_mise_tasks.py tests/test_docs_examples.py tests/test_example_recordings.py -v`
- Test: `uv run pytest`
- Test: `uv run ruff check .`
- Test: `uv run mypy models/python tests`

**Interfaces:**
- Consumes: completed implementation and docs from Tasks 1-4.
- Produces: verified working tree with Rust/WASM Breakout clock support and docs/recording coverage.

- [ ] **Step 1: Run focused verification**

  Run:

  ```bash
  cargo test -p red2-wasm
  uv run pytest tests/test_red2_wasm_cli.py tests/test_mise_tasks.py tests/test_docs_examples.py tests/test_example_recordings.py -v
  ```

  Expected: PASS.

- [ ] **Step 2: Run full verification**

  Run:

  ```bash
  uv run pytest
  uv run ruff check .
  uv run mypy models/python tests
  ```

  Expected: PASS.

- [ ] **Step 3: Run manual smoke commands and inspect output**

  Run:

  ```bash
  clock=/tmp/asgard-breakout-clock.txt
  printf '1700000000200\n' > "$clock"
  printf ' q' | mise run rust examples/breakout.thor --clock "$clock" --quantum 12000 >/tmp/asgard-breakout-rust.out 2>/tmp/asgard-breakout-rust.err
  printf ' q' | mise run wasm examples/breakout.thor --clock "$clock" --quantum 12000 >/tmp/asgard-breakout-wasm.out 2>/tmp/asgard-breakout-wasm.err
  test ! -s /tmp/asgard-breakout-rust.err
  test ! -s /tmp/asgard-breakout-wasm.err
  rg -q 'BREAKOUT 20x12' /tmp/asgard-breakout-rust.out
  rg -q 'BREAKOUT 20x12' /tmp/asgard-breakout-wasm.out
  rg -q 'QUIT' /tmp/asgard-breakout-rust.out
  rg -q 'QUIT' /tmp/asgard-breakout-wasm.out
  ```

  Expected: all commands exit 0.

## Operator smoke

- do: `clock=/tmp/asgard-breakout-clock.txt; printf '1700000000200\n' > "$clock"; printf ' q' | mise run wasm examples/breakout.thor --clock "$clock" --quantum 12000`
- see: terminal output contains `BREAKOUT 20x12`, ANSI cursor sequences, and `QUIT`.
- do: `printf q | mise run wasm examples/breakout.thor --quantum 12000`
- see: terminal output starts the Breakout board using the real clock path and exits with `QUIT`.
- do: `asciinema play examples/media/breakout-wasm.cast`
- see: the recording title/frame shows the WASM Breakout demonstration.

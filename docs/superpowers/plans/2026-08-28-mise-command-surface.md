# Mise Command Surface Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `mise run thor/red2/rust/wasm/hdl` the consistent command surface for executable THOR/RED2 examples.

**Architecture:** Add direct model tasks to `.mise.toml` and make the underlying Python and Rust CLIs support quiet-by-default UART execution with `--verbose` diagnostics. Keep existing source directories and avoid dispatch shim scripts.

**Tech Stack:** Python 3.14, argparse, pytest, Rust/Cargo, Wasmtime/WASI, mise TOML tasks with `usage` declarations.

**Spec:** `docs/superpowers/specs/2026-08-28-mise-command-surface-design.md`

**Acceptance:** suite — the committed pytest, Ruff, mypy, Cargo, and model-task smoke tests cover the command surface and quiet/verbose output policy.

## Global Constraints

- Add `mise run` tasks for each execution backend: `thor`, `red2`, `rust`, `wasm`, and `hdl`.
- stdout is simulated device/UART output for runnable backend tasks.
- stderr is quiet by default unless an error occurs.
- `--verbose` enables diagnostic output.
- Do not add repo-local shim scripts for dispatch.
- Do not reorganize `src/`, `red2-wasm/`, `pypeline_red2/`, `vscode-thor/`, or `tests/` in this phase.
- `mise run hdl <file>` prints exactly `todo` plus a trailing newline.

---

## File Structure

- `src/thor_spec/cli.py`: add Python model subcommands for task use and quiet/verbose IO-result handling.
- `red2-wasm/src/main.rs`: make native/WASI bytecode execution quiet by default, with `--verbose` diagnostics, while keeping stdout reserved for UART output.
- `.mise.toml`: add task definitions using `usage = '''...'''`; model tasks call Python, Cargo, and Wasmtime directly.
- `tests/test_cli_models.py`: cover Python subcommand quiet and verbose behavior.
- `tests/test_red2_wasm_cli.py`: cover Rust CLI quiet and verbose behavior.
- `tests/test_mise_tasks.py`: cover `mise run` task integration and `hdl` placeholder behavior.
- `README.md` and `docs/red2-bytecode.md`: document the mise command surface as canonical.

---

### Task 1: Add Python `thor` and `red2` runner subcommands

**Type:** implementation
**Depends-on:** none

**Files:**
- Modify: `src/thor_spec/cli.py`
- Modify: `tests/test_cli_models.py`

**Interfaces:**
- Consumes: existing `run_io_source(source, model, quantum, stdin, stdout, stderr) -> str` behavior and `DEFAULT_QUANTUM`.
- Produces: `thor-spec thor <file> [--quantum N] [--verbose]` and `thor-spec red2 <file> [--quantum N] [--verbose]`, both returning exit code `0` on success, writing UART output to stdout, and writing `io result: NIL` to stderr only when `--verbose` is present.

**Parallelization rationale:** This task changes only the Python CLI contract; Rust CLI behavior can be implemented independently against the same output policy.

- [ ] **Step 1: Add failing tests for quiet Python model subcommands**

  Append these tests to `tests/test_cli_models.py`:

  ```python
  def test_cli_thor_subcommand_runs_io_quiet_by_default(
      capsys: CaptureFixture[str],
  ) -> None:
      assert main(["thor", "--expr", "(UART-TX 65)"]) == 0

      captured = capsys.readouterr()
      assert captured.out == "A"
      assert captured.err == ""


  def test_cli_red2_subcommand_runs_io_quiet_by_default(
      capsys: CaptureFixture[str],
      monkeypatch: MonkeyPatch,
  ) -> None:
      monkeypatch.setattr("sys.stdin", StringIO("B"))

      assert main(
          [
              "red2",
              "--expr",
              "(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))",
          ]
      ) == 0

      captured = capsys.readouterr()
      assert captured.out == "B"
      assert captured.err == ""
  ```

- [ ] **Step 2: Add failing test for verbose Python diagnostics**

  Append this test to `tests/test_cli_models.py`:

  ```python
  def test_cli_model_subcommand_verbose_reports_io_result(
      capsys: CaptureFixture[str],
  ) -> None:
      assert main(["thor", "--verbose", "--expr", "(UART-TX 65)"]) == 0

      captured = capsys.readouterr()
      assert captured.out == "A"
      assert captured.err == "io result: NIL\n"
  ```

- [ ] **Step 3: Run tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_cli_models.py::test_cli_thor_subcommand_runs_io_quiet_by_default tests/test_cli_models.py::test_cli_red2_subcommand_runs_io_quiet_by_default tests/test_cli_models.py::test_cli_model_subcommand_verbose_reports_io_result -v
  ```

  Expected: all three tests fail because `thor` and `red2` are not recognized subcommands yet.

- [ ] **Step 4: Implement Python model subcommands**

  In `src/thor_spec/cli.py`, add an early dispatch in `main()` before the existing parser path:

  ```python
  if argv and argv[0] in {"thor", "red2"}:
      return _run_model_command(argv[0], argv[1:])
  ```

  Add this helper near `_run_red2_command`:

  ```python
  def _run_model_command(model_value: ModelName, argv: list[str]) -> int:
      parser = argparse.ArgumentParser(
          prog=f"thor-spec {model_value}",
          description=f"Run THOR source with the {model_value} model as a UART action.",
      )
      source_group = parser.add_mutually_exclusive_group(required=True)
      source_group.add_argument("--expr", help="THOR expression or program source")
      source_group.add_argument("file", nargs="?", type=Path, help="path to THOR source")
      parser.add_argument(
          "--quantum",
          type=int,
          default=DEFAULT_QUANTUM,
          help=f"maximum contraction quantum (default: {DEFAULT_QUANTUM})",
      )
      parser.add_argument(
          "--verbose",
          action="store_true",
          help="write diagnostics to stderr",
      )
      args = parser.parse_args(argv)
      try:
          source = args.expr if args.expr is not None else args.file.read_text()
          return _run_io(
              source,
              model_value=model_value,
              quantum=args.quantum,
              verbose=args.verbose,
          )
      except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
          print(f"thor-spec: {error}", file=sys.stderr)
          return 2
  ```

  Change `_run_io` to accept `verbose: bool = True` and print the final result only when `verbose` is true:

  ```python
  def _run_io(
      source: str,
      *,
      model_value: object,
      quantum: int,
      verbose: bool = True,
  ) -> int:
      ...
      result = run_io_source(...)
      if verbose:
          print(f"io result: {result}", file=sys.stderr)
      return 0
  ```

  Keep the existing top-level parser path calling `_run_io(..., verbose=True)` so current direct CLI tests keep their existing behavior.

- [ ] **Step 5: Run focused Python CLI tests**

  Run:

  ```sh
  uv run pytest tests/test_cli_models.py -v
  ```

  Expected: all tests pass.

- [ ] **Step 6: Commit Task 1**

  Run:

  ```sh
  git add src/thor_spec/cli.py tests/test_cli_models.py
  git commit -m "feat: add quiet Python model runners"
  ```

---

### Task 2: Make Rust bytecode runner quiet by default with verbose diagnostics

**Type:** implementation
**Depends-on:** none

**Files:**
- Modify: `red2-wasm/src/main.rs`
- Modify: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: `red2_wasm::vm::run_io_bundle(&ProgramBundle, u32, &mut impl Read, &mut impl Write) -> Result<Expr, Red2Error>`.
- Produces: `red2-wasm <program.red2> [--quantum N] [--verbose]`, which runs bytecode with UART stdout by default, emits no success diagnostics by default, and emits `io result: NIL` on stderr only when `--verbose` is present.

**Parallelization rationale:** This task changes the Rust CLI contract independently from Python task wiring; both can be reviewed against the shared stdout/stderr policy.

- [ ] **Step 1: Update Rust subprocess helper test contract**

  In `tests/test_red2_wasm_cli.py`, change `run_rust_vm` to remove its `io_mode` parameter and add a `verbose` parameter:

  ```python
  def run_rust_vm(
      path: Path,
      quantum: int = 20,
      *,
      verbose: bool = False,
      stdin: str = "",
      timeout: float = 20.0,
  ) -> subprocess.CompletedProcess[str]:
      command = [
          "cargo",
          "run",
          "-p",
          "red2-wasm",
          "--quiet",
          "--",
          str(path),
          "--quantum",
          str(quantum),
      ]
      if verbose:
          command.append("--verbose")
      return subprocess.run(
          command,
          input=stdin,
          check=False,
          text=True,
          capture_output=True,
          timeout=timeout,
      )
  ```

- [ ] **Step 2: Update Rust tests for quiet default and verbose output**

  Update existing assertions in `tests/test_red2_wasm_cli.py` so the non-interactive primitive/lambda/definition tests expect quiet success:

  ```python
  assert result.stdout == ""
  assert result.stderr == ""
  ```

  Update Caesar and Hangman tests to remove `io_mode=True` arguments and expect quiet success:

  ```python
  assert "io result: NIL" not in result.stderr
  assert "red2 result:" not in result.stderr
  assert result.stderr == ""
  ```

  Add this new test:

  ```python
  def test_rust_red2_vm_verbose_reports_io_result(tmp_path: Path) -> None:
      result = run_rust_vm(
          write_bytecode(tmp_path, "(UART-TX 65)"),
          quantum=100,
          verbose=True,
      )

      assert result.returncode == 0
      assert result.stdout == "A"
      assert result.stderr == "io result: NIL\n"
  ```

- [ ] **Step 3: Run tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_red2_wasm_cli.py -v
  ```

  Expected: failures show Rust still emits success diagnostics by default and does not yet default to UART execution.

- [ ] **Step 4: Implement Rust CLI defaults**

  In `red2-wasm/src/main.rs`:

  - remove the `io_mode` state variable.
  - add `let mut verbose = false;`.
  - parse `--verbose` by setting `verbose = true`.
  - always call `vm::run_io_bundle` with stdin/stdout handles.
  - on `Ok(result)`, only print `io result: ...` when `verbose` is true.
  - keep error output on stderr and exit code `2`.

  The core result block should become:

  ```rust
  let result = ProgramBundle::decode(&bytes).and_then(|bundle| {
      let mut stdin = io::stdin().lock();
      let mut stdout = io::stdout().lock();
      vm::run_io_bundle(&bundle, quantum, &mut stdin, &mut stdout)
  });
  match result {
      Ok(result) => {
          if verbose {
              eprintln!("io result: {}", result.to_source());
          }
      }
      Err(error) => {
          eprintln!("red2-wasm: {error}");
          std::process::exit(2);
      }
  }
  ```

  Update the usage string to:

  ```rust
  eprintln!("usage: red2-wasm <program.red2> [--quantum N] [--verbose]");
  ```

- [ ] **Step 5: Run Rust and Python Rust-CLI tests**

  Run:

  ```sh
  cargo fmt --all
  cargo test -p red2-wasm
  uv run pytest tests/test_red2_wasm_cli.py -v
  ```

  Expected: all pass.

- [ ] **Step 6: Commit Task 2**

  Run:

  ```sh
  git add red2-wasm/src/main.rs tests/test_red2_wasm_cli.py
  git commit -m "feat: quiet Rust RED2 runner by default"
  ```

---

### Task 3: Add direct `mise run` model tasks

**Type:** implementation
**Depends-on:** 1, 2
**Review:** adversarial

**Files:**
- Modify: `.mise.toml`
- Create: `tests/test_mise_tasks.py`

**Interfaces:**
- Consumes: `thor-spec thor <file> [--quantum N] [--verbose]`, `thor-spec red2 <file> [--quantum N] [--verbose]`, and `red2-wasm <program.red2> [--quantum N] [--verbose]` from Tasks 1 and 2.
- Produces: `mise run thor <file> [--quantum N] [--verbose]`, `mise run red2 <file> [--quantum N] [--verbose]`, `mise run rust <file> [--quantum N] [--verbose]`, `mise run wasm <file> [--quantum N] [--verbose]`, `mise run hdl <file>`.

**Parallelization rationale:** Task definitions depend on the Python and Rust CLI contracts but are independent from documentation once those contracts exist.

- [ ] **Step 1: Add failing mise integration tests**

  Create `tests/test_mise_tasks.py` with:

  ```python
  from __future__ import annotations

  import subprocess
  from pathlib import Path


  def run_mise_task(
      task: str,
      *args: str,
      stdin: str = "",
      timeout: float = 30.0,
  ) -> subprocess.CompletedProcess[str]:
      return subprocess.run(
          ["mise", "run", task, *args],
          input=stdin,
          check=False,
          text=True,
          capture_output=True,
          timeout=timeout,
      )


  def test_mise_thor_runs_hangman_quietly() -> None:
      result = run_mise_task(
          "thor",
          "examples/hangman.thor",
          "--quantum",
          "5000",
          stdin="A\nS\nG\nR\nD\n",
      )

      assert result.returncode == 0
      assert "WORD: ASGARD\n" in result.stdout
      assert "WIN\n" in result.stdout
      assert result.stderr == ""


  def test_mise_red2_runs_hangman_quietly() -> None:
      result = run_mise_task(
          "red2",
          "examples/hangman.thor",
          "--quantum",
          "5000",
          stdin="A\nS\nG\nR\nD\n",
      )

      assert result.returncode == 0
      assert "WORD: ASGARD\n" in result.stdout
      assert "WIN\n" in result.stdout
      assert result.stderr == ""


  def test_mise_rust_runs_hangman_quietly() -> None:
      result = run_mise_task(
          "rust",
          "examples/hangman.thor",
          "--quantum",
          "5000",
          stdin="A\nS\nG\nR\nD\n",
      )

      assert result.returncode == 0
      assert "WORD: ASGARD\n" in result.stdout
      assert "WIN\n" in result.stdout
      assert result.stderr == ""


  def test_mise_rust_verbose_reports_io_result() -> None:
      result = run_mise_task(
          "rust",
          "examples/hangman.thor",
          "--quantum",
          "5000",
          "--verbose",
          stdin="A\nS\nG\nR\nD\n",
      )

      assert result.returncode == 0
      assert "WORD: ASGARD\n" in result.stdout
      assert "WIN\n" in result.stdout
      assert "io result: NIL\n" in result.stderr


  def test_mise_wasm_runs_hangman_quietly() -> None:
      result = run_mise_task(
          "wasm",
          "examples/hangman.thor",
          "--quantum",
          "5000",
          stdin="A\nS\nG\nR\nD\n",
          timeout=60.0,
      )

      assert result.returncode == 0
      assert "WORD: ASGARD\n" in result.stdout
      assert "WIN\n" in result.stdout
      assert result.stderr == ""


  def test_mise_hdl_prints_placeholder() -> None:
      result = run_mise_task("hdl", "examples/hangman.thor")

      assert result.returncode == 0
      assert result.stdout == "todo\n"
      assert result.stderr == ""
  ```

- [ ] **Step 2: Run tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_mise_tasks.py -v
  ```

  Expected: failures show `mise` has no matching tasks.

- [ ] **Step 3: Add `.mise.toml` tasks**

  Replace `.mise.toml` with this content, preserving the existing tool and venv configuration:

  ```toml
  [tools]
  python = "3.14.7"

  [env]
  _.python.venv = { path = ".venv", create = true }

  [tasks.thor]
  description = "Run a THOR source file with the Python THOR model"
  usage = '''
  arg "<file>" help="THOR source file"
  flag "--quantum <n>" help="maximum contraction quantum" default="2000"
  flag "--verbose" help="write diagnostics to stderr"
  '''
  run = '''
  uv run thor-spec thor "${usage_file?}" --quantum "${usage_quantum?}" ${usage_verbose:+--verbose}
  '''

  [tasks.red2]
  description = "Run a THOR source file with the Python RED2 model"
  usage = '''
  arg "<file>" help="THOR source file"
  flag "--quantum <n>" help="maximum contraction quantum" default="2000"
  flag "--verbose" help="write diagnostics to stderr"
  '''
  run = '''
  uv run thor-spec red2 "${usage_file?}" --quantum "${usage_quantum?}" ${usage_verbose:+--verbose}
  '''

  [tasks.rust]
  description = "Compile a THOR source file and run it with the native Rust RED2 VM"
  usage = '''
  arg "<file>" help="THOR source file"
  flag "--quantum <n>" help="maximum contraction quantum" default="5000"
  flag "--verbose" help="write diagnostics to stderr"
  '''
  run = '''
  tmp="$(mktemp -t asgard-rust.XXXXXX).red2"
  uv run thor-spec compile-red2 --file "${usage_file?}" --output "$tmp" >/dev/null 2>/dev/null
  cargo run -p red2-wasm --quiet -- "$tmp" --quantum "${usage_quantum?}" ${usage_verbose:+--verbose}
  rm -f "$tmp"
  '''

  [tasks.wasm]
  description = "Compile a THOR source file and run it with the Wasmtime RED2 VM"
  usage = '''
  arg "<file>" help="THOR source file"
  flag "--quantum <n>" help="maximum contraction quantum" default="5000"
  flag "--verbose" help="write diagnostics to stderr"
  '''
  run = '''
  tmp="$(mktemp -t asgard-wasm.XXXXXX).red2"
  uv run thor-spec compile-red2 --file "${usage_file?}" --output "$tmp" >/dev/null 2>/dev/null
  cargo build -p red2-wasm --target wasm32-wasi >/dev/null
  wasmtime --dir "$(dirname "$tmp")" target/wasm32-wasi/debug/red2-wasm.wasm "$tmp" --quantum "${usage_quantum?}" ${usage_verbose:+--verbose}
  rm -f "$tmp"
  '''

  [tasks.hdl]
  description = "Placeholder for future HDL execution"
  usage = 'arg "<file>" help="THOR source file"'
  run = 'echo "todo"'

  [tasks.test]
  description = "Run Python tests"
  run = "uv run pytest"

  [tasks.lint]
  description = "Run Ruff"
  run = "uv run ruff check ."

  [tasks.typecheck]
  description = "Run mypy"
  run = "uv run mypy src tests"

  [tasks.rust-test]
  description = "Run Rust tests"
  run = "cargo test -p red2-wasm"

  [tasks.verify]
  description = "Run all project verification gates"
  depends = ["test", "lint", "typecheck", "rust-test"]
  ```

- [ ] **Step 4: Run mise task tests**

  Run:

  ```sh
  uv run pytest tests/test_mise_tasks.py -v
  ```

  Expected: all tests pass.

- [ ] **Step 5: Run direct task smoke commands**

  Run:

  ```sh
  printf 'A\nS\nG\nR\nD\n' | mise run thor examples/hangman.thor --quantum 5000
  printf 'A\nS\nG\nR\nD\n' | mise run red2 examples/hangman.thor --quantum 5000
  printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000
  printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000
  mise run hdl examples/hangman.thor
  ```

  Expected: the first four commands include `WORD: ASGARD` and `WIN` on stdout; the final command prints exactly `todo`.

- [ ] **Step 6: Commit Task 3**

  Run:

  ```sh
  git add .mise.toml tests/test_mise_tasks.py
  git commit -m "feat: add mise model runner tasks"
  ```

---

### Task 4: Update docs to make `mise run` canonical

**Type:** implementation
**Depends-on:** 3

**Files:**
- Modify: `README.md`
- Modify: `docs/red2-bytecode.md`

**Interfaces:**
- Consumes: model task names and quiet/verbose behavior from Task 3.
- Produces: README and bytecode documentation that show `mise run thor`, `mise run red2`, `mise run rust`, `mise run wasm`, `mise run hdl`, and `mise run verify` as the preferred user-facing commands.

- [ ] **Step 1: Update README command examples**

  In `README.md`, replace direct day-to-day `uv`, `cargo`, and `wasmtime` examples with the canonical task surface. The CLI Examples section should include these exact commands:

  ```sh
  uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)"
  uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)"
  mise run thor examples/hangman.thor --quantum 5000
  mise run red2 examples/hangman.thor --quantum 5000
  printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000
  printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000
  mise run hdl examples/hangman.thor
  mise run verify
  ```

  State that successful model tasks are quiet on stderr by default and that `--verbose` enables diagnostics.

- [ ] **Step 2: Update RED2 bytecode docs**

  In `docs/red2-bytecode.md`, update the day-to-day run section to prefer:

  ```sh
  mise run rust examples/uart-caesar-plus4.thor
  mise run wasm examples/uart-caesar-plus4.thor
  printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000
  printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000
  ```

  Keep lower-level compile format details only where they describe the `.red2` format rather than the normal user workflow.

- [ ] **Step 3: Run docs/example tests**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py -v
  ```

  Expected: pass. If documentation tests assert command text, update those assertions to match the new canonical task examples.

- [ ] **Step 4: Commit Task 4**

  Run:

  ```sh
  git add README.md docs/red2-bytecode.md tests/test_docs_examples.py
  git commit -m "docs: document mise command surface"
  ```

---

### Task 5: Final verification gate

**Type:** gate
**Depends-on:** 4

**Files:**
- Test: full project verification only

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: verified command-first cleanup with passing project gates.

- [ ] **Step 1: Run the canonical verification task**

  Run:

  ```sh
  mise run verify
  ```

  Expected: Python tests, Ruff, mypy, and Rust tests all pass.

- [ ] **Step 2: Run representative quiet and verbose task smokes**

  Run:

  ```sh
  printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000 >/tmp/asgard-rust.out 2>/tmp/asgard-rust.err
  test ! -s /tmp/asgard-rust.err
  rg -q 'WORD: ASGARD' /tmp/asgard-rust.out
  rg -q 'WIN' /tmp/asgard-rust.out

  printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000 --verbose >/tmp/asgard-rust-verbose.out 2>/tmp/asgard-rust-verbose.err
  rg -q 'WORD: ASGARD' /tmp/asgard-rust-verbose.out
  rg -q 'WIN' /tmp/asgard-rust-verbose.out
  rg -q 'io result: NIL' /tmp/asgard-rust-verbose.err
  ```

  Expected: quiet smoke has no stderr; verbose smoke has `io result: NIL` on stderr.

- [ ] **Step 3: Confirm working tree status**

  Run:

  ```sh
  git status --short
  ```

  Expected: no unstaged or uncommitted implementation changes.

## Operator smoke

- do: `printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000`
- see: Hangman prints `WORD: ASGARD` and `WIN`, with no success diagnostics mixed into stderr.

- do: `printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000 --verbose`
- see: Hangman still prints `WORD: ASGARD` and `WIN`, and stderr includes `io result: NIL`.

- do: `mise run hdl examples/hangman.thor`
- see: stdout is exactly `todo`.

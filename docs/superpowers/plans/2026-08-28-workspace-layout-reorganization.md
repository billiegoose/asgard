# Workspace Layout Reorganization Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize top-level source workspaces into `models/`, `tools/`, and `thesis/` while keeping imports and `mise run` commands stable.

**Architecture:** Move each workspace with `git mv`, then update only the config, tests, and current operational docs that point at the moved paths. Python import names remain `thor_spec.*` and `pypeline_red2.*`; the Rust crate remains package `red2-wasm` even though its folder moves.

**Tech Stack:** Python 3.14, Hatch/uv, pytest, Ruff, mypy, Rust/Cargo, Wasmtime/WASI, mise tasks.

**Spec:** `docs/superpowers/specs/2026-08-28-workspace-layout-reorganization-design.md`

**Acceptance:** suite — layout path tests, existing Python/Rust/doc tests, `mise run verify`, and representative `mise run` smokes verify the reorganization without changing runtime behavior.

## Global Constraints

- Move model implementations under `models/`.
- Move the VS Code extension under `tools/`.
- Move thesis transcription under `thesis/`.
- Keep Python import names unchanged: `thor_spec.*` and `pypeline_red2.*`.
- Keep public task commands unchanged: `mise run thor`, `mise run red2`, `mise run parity`, `mise run rust`, `mise run wasm`, `mise run hdl`, and `mise run verify`.
- Keep examples, tests, and docs at top level.
- Do not split `thor_spec` into separate Python packages yet.
- Do not rename the Rust crate/package from `red2-wasm` in this phase.
- Do not rewrite historical implementation plans/specs solely to update old path references.

---

## File Structure

- `models/python/thor_spec/`: moved Python THOR/RED2 package, same import name.
- `models/python/pypeline_red2/`: moved Pypeline/PypelineC Python artifact, same import name.
- `models/rust-red2/`: moved Rust crate directory, package remains `red2-wasm`.
- `tools/vscode-thor/`: moved VS Code extension.
- `thesis/transcription/`: moved LaTeX transcription project.
- `pyproject.toml`: Python package paths, Ruff source roots, mypy file roots.
- `Cargo.toml`: Rust workspace member path.
- `.mise.toml`: typecheck command and Rust/Wasm task paths if Cargo invocation needs an explicit manifest path.
- Tests: add path invariants and update path-sensitive existing tests.
- Current docs: update `README.md`, `docs/thor-red2-prototype.md`, `docs/red2-bytecode.md`, `AGENTS.md`, and moved local READMEs with new paths.

---

### Task 1: Move Python model packages to `models/python`

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `tests/test_python_workspace_layout.py`
- Create: `models/python/thor_spec/`
- Create: `models/python/pypeline_red2/`
- Modify: `pyproject.toml`
- Modify: `.mise.toml`
- Modify: `tests/test_pypeline_red2_static.py`
- Modify: `src/thor_spec/`
- Modify: `pypeline_red2/`

**Interfaces:**
- Consumes: existing imports `thor_spec.*` and `pypeline_red2.*`.
- Produces: import-compatible Python packages located at `models/python/thor_spec` and `models/python/pypeline_red2`; `uv run pytest`, `uv run ruff check .`, and `uv run mypy models/python tests` can find the moved packages.

**Parallelization rationale:** Python package relocation is independent from Rust, tool, and thesis path moves; it only shares docs/config cleanup with later integration.

- [ ] **Step 1: Add failing Python layout tests**

  Create `tests/test_python_workspace_layout.py` with:

  ```python
  from __future__ import annotations

  import importlib
  from pathlib import Path


  def test_python_packages_live_under_models_python() -> None:
      assert Path("models/python/thor_spec/__init__.py").is_file()
      assert Path("models/python/pypeline_red2/__init__.py").is_file()
      assert not Path("src/thor_spec").exists()
      assert not Path("pypeline_red2").exists()


  def test_python_import_names_stay_stable() -> None:
      thor_spec = importlib.import_module("thor_spec")
      stepper = importlib.import_module("pypeline_red2.red2_stepper")

      assert thor_spec.__name__ == "thor_spec"
      assert hasattr(stepper, "red2_step_word")
  ```

- [ ] **Step 2: Run the new tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_python_workspace_layout.py -v
  ```

  Expected: `test_python_packages_live_under_models_python` fails because the packages have not moved yet.

- [ ] **Step 3: Move Python package directories**

  Run:

  ```sh
  mkdir -p models/python
  git mv src/thor_spec models/python/thor_spec
  git mv pypeline_red2 models/python/pypeline_red2
  rmdir src
  ```

  If `rmdir src` reports the directory is non-empty, inspect it with `find src -maxdepth 2 -print` and remove only generated cache files that are already ignored.

- [ ] **Step 4: Update Python project configuration**

  In `pyproject.toml`, replace:

  ```toml
  packages = ["src/thor_spec", "pypeline_red2"]
  ```

  with:

  ```toml
  packages = ["models/python/thor_spec", "models/python/pypeline_red2"]
  ```

  Replace the Ruff config:

  ```toml
  src = ["src", "tests"]
  ```

  with:

  ```toml
  src = ["models/python", "tests"]
  ```

  Replace the mypy config:

  ```toml
  files = ["src", "tests"]
  ```

  with:

  ```toml
  files = ["models/python", "tests"]
  ```

  In `.mise.toml`, replace the typecheck task command:

  ```toml
  run = "uv run mypy src tests"
  ```

  with:

  ```toml
  run = "uv run mypy models/python tests"
  ```

- [ ] **Step 5: Update Pypeline path-sensitive tests**

  In `tests/test_pypeline_red2_static.py`, replace both `Path("pypeline_red2/...` references with `Path("models/python/pypeline_red2/...`.

  The first test should read:

  ```python
  source = Path("models/python/pypeline_red2/red2_stepper.py").read_text()
  ```

  The second test should read:

  ```python
  text = Path("models/python/pypeline_red2/README.md").read_text()
  ```

- [ ] **Step 6: Run focused Python validation**

  Run:

  ```sh
  uv run pytest tests/test_python_workspace_layout.py tests/test_pypeline_red2_static.py tests/test_cli_models.py -v
  uv run ruff check models/python tests/test_python_workspace_layout.py tests/test_pypeline_red2_static.py tests/test_cli_models.py
  uv run mypy models/python tests/test_python_workspace_layout.py tests/test_pypeline_red2_static.py tests/test_cli_models.py
  mise run typecheck
  ```

  Expected: all commands pass.

- [ ] **Step 7: Commit Task 1**

  Run:

  ```sh
  git add pyproject.toml .mise.toml tests/test_python_workspace_layout.py tests/test_pypeline_red2_static.py models/python
  git add -u src pypeline_red2
  git commit -m "refactor: move Python models under models"
  ```

---

### Task 2: Move Rust RED2 crate to `models/rust-red2`

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `tests/test_rust_workspace_layout.py`
- Create: `models/rust-red2/`
- Modify: `Cargo.toml`
- Modify: `.mise.toml`
- Modify: `tests/test_red2_wasm_cli.py`
- Modify: `red2-wasm/`

**Interfaces:**
- Consumes: existing Cargo package name `red2-wasm` and task commands `mise run rust`, `mise run wasm`, and `mise run rust-test`.
- Produces: Rust crate directory `models/rust-red2` with package name `red2-wasm`; root Cargo workspace commands still work from the repo root.

**Parallelization rationale:** Rust crate relocation is independent from Python package and tool/thesis moves; it can be validated with Cargo and Rust-specific pytest coverage.

- [ ] **Step 1: Add failing Rust layout tests**

  Create `tests/test_rust_workspace_layout.py` with:

  ```python
  from __future__ import annotations

  from pathlib import Path


  def test_rust_red2_crate_lives_under_models() -> None:
      cargo_toml = Path("models/rust-red2/Cargo.toml")

      assert cargo_toml.is_file()
      assert not Path("red2-wasm/Cargo.toml").exists()
      assert 'name = "red2-wasm"' in cargo_toml.read_text()


  def test_root_cargo_workspace_points_at_moved_crate() -> None:
      assert 'members = ["models/rust-red2"]' in Path("Cargo.toml").read_text()
  ```

- [ ] **Step 2: Run the new tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_rust_workspace_layout.py -v
  ```

  Expected: tests fail because `models/rust-red2/Cargo.toml` does not exist and root `Cargo.toml` still points at `red2-wasm`.

- [ ] **Step 3: Move Rust crate directory**

  Run:

  ```sh
  mkdir -p models
  git mv red2-wasm models/rust-red2
  ```

- [ ] **Step 4: Update root Cargo workspace path**

  In root `Cargo.toml`, replace:

  ```toml
  members = ["red2-wasm"]
  ```

  with:

  ```toml
  members = ["models/rust-red2"]
  ```

- [ ] **Step 5: Update Rust/Wasm task commands only if required**

  First run:

  ```sh
  cargo test -p red2-wasm
  mise run rust examples/uart-caesar-plus4.thor
  ```

  If both pass from the repository root, leave `.mise.toml` Rust task command lines unchanged except for path references in comments or documentation. If Cargo reports that the package cannot be found, update `.mise.toml` by adding `--manifest-path Cargo.toml` to `cargo run`, `cargo build`, and `cargo test` invocations. Do not change the public task names or arguments.

- [ ] **Step 6: Update Rust CLI tests if path assumptions changed**

  Inspect `tests/test_red2_wasm_cli.py`. It should keep invoking:

  ```python
  "cargo",
  "run",
  "-p",
  "red2-wasm",
  ```

  Do not replace the package name with `rust-red2`. Only update this test file if it contains filesystem references to the old `red2-wasm/` directory.

- [ ] **Step 7: Run focused Rust validation**

  Run:

  ```sh
  cargo test -p red2-wasm
  uv run pytest tests/test_rust_workspace_layout.py tests/test_red2_wasm_cli.py tests/test_mise_tasks.py -v
  mise run rust examples/uart-caesar-plus4.thor
  ```

  Expected: all commands pass; Caesar task prints `efgBCD!` when run with input `abcXYZ!` followed by Escape:

  ```sh
  printf 'abcXYZ!\033' | mise run rust examples/uart-caesar-plus4.thor
  ```

- [ ] **Step 8: Commit Task 2**

  Run:

  ```sh
  git add Cargo.toml .mise.toml tests/test_rust_workspace_layout.py tests/test_red2_wasm_cli.py models/rust-red2
  git add -u red2-wasm
  git commit -m "refactor: move Rust RED2 crate under models"
  ```

---

### Task 3: Move VS Code extension and thesis transcription workspaces

**Type:** implementation
**Depends-on:** none

**Files:**
- Create: `tests/test_workspace_artifacts_layout.py`
- Create: `tools/vscode-thor/`
- Create: `thesis/transcription/`
- Modify: `tests/test_vscode_thor_extension.py`
- Modify: `vscode-thor/`
- Modify: `thesis-transcription/`

**Interfaces:**
- Consumes: existing VS Code extension files and thesis transcription project files.
- Produces: extension path `tools/vscode-thor` and thesis path `thesis/transcription` without changing extension metadata or thesis source contents.

**Parallelization rationale:** Tooling/thesis relocation does not depend on Python package or Rust crate paths and can be validated by path-sensitive tests.

- [ ] **Step 1: Add failing artifact layout tests**

  Create `tests/test_workspace_artifacts_layout.py` with:

  ```python
  from __future__ import annotations

  from pathlib import Path


  def test_vscode_extension_lives_under_tools() -> None:
      assert Path("tools/vscode-thor/package.json").is_file()
      assert Path("tools/vscode-thor/syntaxes/thor.tmLanguage.json").is_file()
      assert not Path("vscode-thor/package.json").exists()


  def test_thesis_transcription_lives_under_thesis() -> None:
      assert Path("thesis/transcription/scripts/compile.sh").is_file()
      assert Path("thesis/transcription/src/main.tex").is_file()
      assert not Path("thesis-transcription/scripts/compile.sh").exists()
  ```

- [ ] **Step 2: Run the new tests and confirm they fail**

  Run:

  ```sh
  uv run pytest tests/test_workspace_artifacts_layout.py -v
  ```

  Expected: tests fail because `tools/vscode-thor` and `thesis/transcription` do not exist yet.

- [ ] **Step 3: Move the tool and thesis directories**

  Run:

  ```sh
  mkdir -p tools thesis
  git mv vscode-thor tools/vscode-thor
  git mv thesis-transcription thesis/transcription
  ```

- [ ] **Step 4: Update VS Code extension tests**

  In `tests/test_vscode_thor_extension.py`, replace:

  ```python
  "vscode-thor/package.json"
  "vscode-thor/syntaxes/thor.tmLanguage.json"
  "vscode-thor/README.md"
  "vscode-thor/CHANGELOG.md"
  ```

  with:

  ```python
  "tools/vscode-thor/package.json"
  "tools/vscode-thor/syntaxes/thor.tmLanguage.json"
  "tools/vscode-thor/README.md"
  "tools/vscode-thor/CHANGELOG.md"
  ```

- [ ] **Step 5: Run focused artifact validation**

  Run:

  ```sh
  uv run pytest tests/test_workspace_artifacts_layout.py tests/test_vscode_thor_extension.py -v
  ```

  Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

  Run:

  ```sh
  git add tests/test_workspace_artifacts_layout.py tests/test_vscode_thor_extension.py tools/vscode-thor thesis/transcription
  git add -u vscode-thor thesis-transcription
  git commit -m "refactor: move tooling and thesis workspaces"
  ```

---

### Task 4: Update current docs and operational path references

**Type:** implementation
**Depends-on:** 1, 2, 3

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `docs/red2-bytecode.md`
- Modify: `models/python/pypeline_red2/README.md`
- Modify: `examples/hangman.thor`
- Modify: `tests/test_docs_examples.py`
- Modify: `tests/test_pypeline_red2_static.py`

**Interfaces:**
- Consumes: final paths from Tasks 1, 2, and 3.
- Produces: current docs and operational guidance that reference `models/python`, `models/rust-red2`, `tools/vscode-thor`, and `thesis/transcription`.

- [ ] **Step 1: Update current operational docs**

  Update these path references:

  - In `AGENTS.md`:
    - `thesis-transcription/` -> `thesis/transcription/`
    - `thesis-transcription/scripts/compile.sh` -> `thesis/transcription/scripts/compile.sh`
    - `thesis-transcription/src/main.tex` -> `thesis/transcription/src/main.tex`
    - `thesis-transcription/src/assets/` -> `thesis/transcription/src/assets/`
  - In `README.md` Prototype Scope:
    - `src/thor_spec/...` -> `models/python/thor_spec/...`
    - `pypeline_red2/` -> `models/python/pypeline_red2/`
    - add a bullet for `models/rust-red2/` if one is missing.
    - add a bullet for `tools/vscode-thor/` if one is missing.
  - In `docs/thor-red2-prototype.md`:
    - update current source paths to `models/python/thor_spec/...`.
    - update Pypeline paths to `models/python/pypeline_red2/...`.
    - update VS Code path to `tools/vscode-thor/`.
  - In `docs/red2-bytecode.md`:
    - update `red2-wasm/` crate wording to `models/rust-red2/` while preserving package name `red2-wasm` in commands.
  - In `models/python/pypeline_red2/README.md`:
    - update `pypeline_red2/red2_stepper.py` to `models/python/pypeline_red2/red2_stepper.py`.
  - In `examples/hangman.thor` comments:
    - replace direct lower-level Rust command examples with `mise run rust examples/hangman.thor --quantum 5000`.

- [ ] **Step 2: Update docs tests for new path assertions**

  In `tests/test_docs_examples.py`, update the old VS Code negative assertion so it checks the new canonical tooling location:

  ```python
  assert "tools/vscode-thor" in Path("docs/thor-red2-prototype.md").read_text()
  assert "vscode-thor/examples/uart-caesar-plus4.thor" not in readme
  ```

  Keep `examples/uart-caesar-plus4.thor` as the canonical examples assertion.

  In `tests/test_pypeline_red2_static.py`, update the README path if Task 1 did not already update it:

  ```python
  text = Path("models/python/pypeline_red2/README.md").read_text()
  ```

- [ ] **Step 3: Check for unexpected stale current-path references**

  Run:

  ```sh
  rg -n "src/thor_spec|pypeline_red2/|red2-wasm/|vscode-thor/|thesis-transcription" AGENTS.md README.md docs/thor-red2-prototype.md docs/red2-bytecode.md models/python/pypeline_red2/README.md examples/hangman.thor tests
  ```

  Expected: no matches for stale moved directory references, except package/import text `pypeline_red2.*` without a slash and Rust package command text `red2-wasm` without a slash.

- [ ] **Step 4: Run docs-focused validation**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py tests/test_pypeline_red2_static.py -v
  uv run ruff check tests/test_docs_examples.py tests/test_pypeline_red2_static.py
  ```

  Expected: all commands pass.

- [ ] **Step 5: Commit Task 4**

  Run:

  ```sh
  git add AGENTS.md README.md docs/thor-red2-prototype.md docs/red2-bytecode.md models/python/pypeline_red2/README.md examples/hangman.thor tests/test_docs_examples.py tests/test_pypeline_red2_static.py
  git commit -m "docs: update workspace layout references"
  ```

---

### Task 5: Final verification gate

**Type:** gate
**Depends-on:** 4

**Files:**
- Test: full project verification only

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: verified workspace layout reorganization with stable command surface.

- [ ] **Step 1: Validate mise tasks**

  Run:

  ```sh
  mise tasks validate
  ```

  Expected: all tasks validate.

- [ ] **Step 2: Run canonical full verification**

  Run:

  ```sh
  mise run verify
  ```

  Expected: pytest, Ruff, mypy, and Rust tests all pass.

- [ ] **Step 3: Run representative task smokes**

  Run:

  ```sh
  mise run thor examples/hangman.thor --quantum 5000 >/tmp/asgard-layout-thor.out 2>/tmp/asgard-layout-thor.err
  test ! -s /tmp/asgard-layout-thor.err
  rg -q 'WORD: ASGARD' /tmp/asgard-layout-thor.out
  rg -q 'WIN' /tmp/asgard-layout-thor.out

  mise run red2 examples/hangman.thor --quantum 5000 >/tmp/asgard-layout-red2.out 2>/tmp/asgard-layout-red2.err
  test ! -s /tmp/asgard-layout-red2.err
  rg -q 'WORD: ASGARD' /tmp/asgard-layout-red2.out
  rg -q 'WIN' /tmp/asgard-layout-red2.out

  mise run parity examples/fibonacci.thor --quantum 75 >/tmp/asgard-layout-parity.out 2>/tmp/asgard-layout-parity.err
  test -s /tmp/asgard-layout-parity.out
  rg -q 'parity' /tmp/asgard-layout-parity.err

  printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000 >/tmp/asgard-layout-rust.out 2>/tmp/asgard-layout-rust.err
  test ! -s /tmp/asgard-layout-rust.err
  rg -q 'WORD: ASGARD' /tmp/asgard-layout-rust.out
  rg -q 'WIN' /tmp/asgard-layout-rust.out

  printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000 >/tmp/asgard-layout-wasm.out 2>/tmp/asgard-layout-wasm.err
  test ! -s /tmp/asgard-layout-wasm.err
  rg -q 'WORD: ASGARD' /tmp/asgard-layout-wasm.out
  rg -q 'WIN' /tmp/asgard-layout-wasm.out

  mise run hdl examples/hangman.thor >/tmp/asgard-layout-hdl.out 2>/tmp/asgard-layout-hdl.err
  test "$(cat /tmp/asgard-layout-hdl.out)" = "todo"
  test ! -s /tmp/asgard-layout-hdl.err
  ```

  Expected: all smokes pass.

- [ ] **Step 4: Confirm top-level source layout**

  Run:

  ```sh
  test -d models/python/thor_spec
  test -d models/python/pypeline_red2
  test -d models/rust-red2
  test -d tools/vscode-thor
  test -d thesis/transcription
  test ! -e src
  test ! -e pypeline_red2
  test ! -e red2-wasm
  test ! -e vscode-thor
  test ! -e thesis-transcription
  ```

  Expected: all checks pass.

- [ ] **Step 5: Confirm working tree status**

  Run:

  ```sh
  git status --short
  ```

  Expected: no unstaged or uncommitted implementation changes.

## Operator smoke

- do: `find . -maxdepth 2 -type d | sort | sed -n '1,40p'`
- see: source workspaces appear under `models/`, `tools/`, and `thesis/`, not as `src/`, `red2-wasm/`, `vscode-thor/`, or `thesis-transcription/`.

- do: `printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000`
- see: Hangman still prints `WORD: ASGARD` and `WIN`.

- do: `mise run verify`
- see: the canonical verification task passes from the reorganized tree.

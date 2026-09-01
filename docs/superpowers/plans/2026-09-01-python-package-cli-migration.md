# Python Package and CLI Migration Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `thor_spec` with clean `thor_lang`, `thor_engine`, `red2_engine`, and `thor_compile` packages, and make `uv run thor`, `uv run red2`, and `uv run compile` the primary Python commands.

**Architecture:** Move syntax/language modules into `thor_lang`, THOR execution modules into `thor_engine`, RED2 machine/bytecode modules into `red2_engine`, and THOR-to-RED2 compilation into `thor_compile.red2`. Remove the `thor-spec` entry point entirely rather than keeping compatibility shims.

**Tech Stack:** Python 3.14, Hatchling, argparse, pytest, Ruff, mypy, mise tasks.

**Spec:** `docs/superpowers/specs/2026-09-01-python-package-cli-migration-design.md`

## Global Constraints

- Python remains 3.14.
- The package build keeps using Hatchling and `models/python` as the source root.
- No new runtime dependencies.
- Preserve current behavior and output for THOR, RED2, parity helpers, RED2 binary encoding/decoding, and benchmark tasks except for intentional CLI command names.
- Keep the recent RED2 definition-cache optimization in the RED2 engine layer.
- No `thor_spec` compatibility shims should remain.

**Acceptance:** suite — full project tests, lint, typecheck, Rust tests, and command smoke tests verify the migration.

---

### Task 1: Move Python packages and rewrite imports

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `models/python/thor_lang/__init__.py`
- Create: `models/python/thor_lang/ast.py`
- Create: `models/python/thor_lang/parser.py`
- Create: `models/python/thor_lang/pretty.py`
- Create: `models/python/thor_lang/normalization.py`
- Create: `models/python/thor_lang/primitives.py`
- Create: `models/python/thor_lang/version.py`
- Create: `models/python/thor_lang/py.typed`
- Create: `models/python/thor_engine/__init__.py`
- Create: `models/python/thor_engine/core.py`
- Create: `models/python/thor_engine/golden.py`
- Create: `models/python/thor_engine/io_runtime.py`
- Create: `models/python/thor_engine/lockstep.py`
- Create: `models/python/thor_engine/semantics.py`
- Create: `models/python/red2_engine/__init__.py`
- Create: `models/python/red2_engine/binary.py`
- Create: `models/python/red2_engine/instructions.py`
- Create: `models/python/red2_engine/machine.py`
- Create: `models/python/red2_engine/pipelinec_vectors.py`
- Create: `models/python/red2_engine/primitives.py`
- Create: `models/python/thor_compile/__init__.py`
- Create: `models/python/thor_compile/red2.py`
- Modify: `models/python/pypeline_red2/README.md`
- Modify: `models/python/pypeline_red2/red2_stepper.py`
- Modify: `tests/test_appendix_a_struct_defs.py`
- Modify: `tests/test_appendix_a_sine_full.py`
- Modify: `tests/test_appendix_a_list_primitives.py`
- Modify: `tests/test_appendix_a_scalar_primitives.py`
- Modify: `tests/test_red2_wasm_cli.py`
- Modify: `tests/test_closure_capture_parity.py`
- Modify: `tests/test_docs_examples.py`
- Modify: `tests/test_red2_compiler.py`
- Modify: `tests/test_red2_machine_extended.py`
- Modify: `tests/test_semantics_primitives.py`
- Modify: `tests/test_source_normalization.py`
- Modify: `tests/test_semantics_core.py`
- Modify: `tests/test_pipelinec_vectors.py`
- Modify: `tests/test_red2_no_internal_leaks.py`
- Modify: `tests/test_character_symbol_runtime.py`
- Modify: `tests/test_python_workspace_layout.py`
- Modify: `tests/test_red2_recursive_definitions.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_appendix_a_game_full.py`
- Modify: `tests/test_parser_ast_pretty.py`
- Modify: `tests/test_cli_models.py`
- Modify: `tests/test_golden_parity.py`
- Modify: `tests/test_io_runtime.py`
- Modify: `tests/test_red2_binary.py`
- Test: `tests/test_python_workspace_layout.py`

**Interfaces:**
- Consumes: current modules under `models/python/thor_spec`.
- Produces: importable packages `thor_lang`, `thor_engine`, `red2_engine`, and `thor_compile` with no importable `thor_spec` package.

**Parallelization rationale:** This establishes the package contracts that CLI and docs tasks consume; a good engineer would make this boundary first even without parallel execution.

- [ ] **Step 1: Write the failing workspace layout test**

  Replace `tests/test_python_workspace_layout.py` with:

  ```python
  from __future__ import annotations

  import importlib
  from pathlib import Path


  def test_python_packages_live_under_models_python() -> None:
      assert Path("models/python/thor_lang/__init__.py").is_file()
      assert Path("models/python/thor_engine/__init__.py").is_file()
      assert Path("models/python/red2_engine/__init__.py").is_file()
      assert Path("models/python/thor_compile/__init__.py").is_file()
      assert not Path("models/python/thor_spec").exists()
      assert not Path("src/thor_spec").exists()


  def test_runtime_packages_import_from_models_python() -> None:
      thor_lang = importlib.import_module("thor_lang")
      thor_engine = importlib.import_module("thor_engine")
      red2_engine = importlib.import_module("red2_engine")
      thor_compile = importlib.import_module("thor_compile")

      assert thor_lang.__name__ == "thor_lang"
      assert thor_engine.__name__ == "thor_engine"
      assert red2_engine.__name__ == "red2_engine"
      assert thor_compile.__name__ == "thor_compile"


  def test_old_thor_spec_package_is_removed() -> None:
      try:
          importlib.import_module("thor_spec")
      except ModuleNotFoundError:
          return
      raise AssertionError("thor_spec package should not remain importable")
  ```

- [ ] **Step 2: Run the failing layout test**

  Run:

  ```sh
  uv run pytest tests/test_python_workspace_layout.py -q
  ```

  Expected: FAIL because the new package directories do not exist and `thor_spec` is still importable.

- [ ] **Step 3: Move files into new packages**

  Run these moves from the repo root:

  ```sh
  mkdir -p models/python/thor_lang models/python/thor_engine models/python/red2_engine models/python/thor_compile

  git mv models/python/thor_spec/ast.py models/python/thor_lang/ast.py
  git mv models/python/thor_spec/parser.py models/python/thor_lang/parser.py
  git mv models/python/thor_spec/pretty.py models/python/thor_lang/pretty.py
  git mv models/python/thor_spec/normalization.py models/python/thor_lang/normalization.py
  git mv models/python/thor_spec/primitives.py models/python/thor_lang/primitives.py
  git mv models/python/thor_spec/version.py models/python/thor_lang/version.py
  git mv models/python/thor_spec/py.typed models/python/thor_lang/py.typed

  git mv models/python/thor_spec/core.py models/python/thor_engine/core.py
  git mv models/python/thor_spec/golden.py models/python/thor_engine/golden.py
  git mv models/python/thor_spec/io_runtime.py models/python/thor_engine/io_runtime.py
  git mv models/python/thor_spec/lockstep.py models/python/thor_engine/lockstep.py
  git mv models/python/thor_spec/semantics.py models/python/thor_engine/semantics.py

  git mv models/python/thor_spec/red2/binary.py models/python/red2_engine/binary.py
  git mv models/python/thor_spec/red2/instructions.py models/python/red2_engine/instructions.py
  git mv models/python/thor_spec/red2/machine.py models/python/red2_engine/machine.py
  git mv models/python/thor_spec/red2/pipelinec_vectors.py models/python/red2_engine/pipelinec_vectors.py
  git mv models/python/thor_spec/red2/primitives.py models/python/red2_engine/primitives.py
  git mv models/python/thor_spec/red2/compiler.py models/python/thor_compile/red2.py

  rm -f models/python/thor_spec/__init__.py models/python/thor_spec/__main__.py models/python/thor_spec/red2/__init__.py
  rmdir models/python/thor_spec/red2 models/python/thor_spec
  ```

- [ ] **Step 4: Create new package `__init__` files**

  Write `models/python/thor_lang/__init__.py`:

  ```python
  from __future__ import annotations

  from thor_lang.ast import (
      App,
      Binding,
      Block,
      Char,
      Definition,
      Expr,
      Float,
      Integer,
      Lambda,
      LetRec,
      Program,
      Rec,
      StructDef,
      StructLit,
      Symbol,
      Var,
  )
  from thor_lang.parser import parse_expr, parse_program
  from thor_lang.pretty import to_source
  from thor_lang.version import __version__

  __all__ = [
      "App",
      "Binding",
      "Block",
      "Char",
      "Definition",
      "Expr",
      "Float",
      "Integer",
      "Lambda",
      "LetRec",
      "Program",
      "Rec",
      "StructDef",
      "StructLit",
      "Symbol",
      "Var",
      "__version__",
      "parse_expr",
      "parse_program",
      "to_source",
  ]
  ```

  Write `models/python/thor_engine/__init__.py`:

  ```python
  from __future__ import annotations

  from thor_engine.golden import DEFAULT_QUANTUM, ModelName, run_source
  from thor_engine.semantics import ReductionResult, reduce_expr, translate

  __all__ = [
      "DEFAULT_QUANTUM",
      "ModelName",
      "ReductionResult",
      "reduce_expr",
      "run_source",
      "translate",
  ]
  ```

  Write `models/python/red2_engine/__init__.py`:

  ```python
  from __future__ import annotations

  from red2_engine.instructions import Instruction, Opcode, ProgramImage
  from red2_engine.machine import Red2Machine, Red2ResourceLimits

  __all__ = [
      "Instruction",
      "Opcode",
      "ProgramImage",
      "Red2Machine",
      "Red2ResourceLimits",
  ]
  ```

  Write `models/python/thor_compile/__init__.py`:

  ```python
  from __future__ import annotations

  from thor_compile.red2 import compile_definitions, compile_expr

  __all__ = ["compile_definitions", "compile_expr"]
  ```

- [ ] **Step 5: Rewrite imports in source and tests**

  Apply these mechanical replacements across `models/python`, `tests`, and `tools` Python files:

  ```text
  thor_spec.ast -> thor_lang.ast
  thor_spec.parser -> thor_lang.parser
  thor_spec.pretty -> thor_lang.pretty
  thor_spec.normalization -> thor_lang.normalization
  thor_spec.primitives -> thor_lang.primitives
  thor_spec.version -> thor_lang.version
  thor_spec.core -> thor_engine.core
  thor_spec.golden -> thor_engine.golden
  thor_spec.io_runtime -> thor_engine.io_runtime
  thor_spec.lockstep -> thor_engine.lockstep
  thor_spec.semantics -> thor_engine.semantics
  thor_spec.red2.binary -> red2_engine.binary
  thor_spec.red2.instructions -> red2_engine.instructions
  thor_spec.red2.machine -> red2_engine.machine
  thor_spec.red2.pipelinec_vectors -> red2_engine.pipelinec_vectors
  thor_spec.red2.primitives -> red2_engine.primitives
  thor_spec.red2.compiler -> thor_compile.red2
  ```

  Also update `models/python/pypeline_red2/README.md` so the sentence about the instruction layout says `red2_engine.instructions` instead of `thor_spec.red2.instructions`.

- [ ] **Step 6: Fix any self-imports introduced by moves**

  Open `models/python/thor_lang/__init__.py`, `models/python/thor_engine/*.py`, `models/python/red2_engine/*.py`, and `models/python/thor_compile/red2.py`. Confirm there are no remaining `from thor_spec...` imports. Confirm `red2_engine` does not import `thor_engine`.

  Run:

  ```sh
  rg "thor_spec|thor-spec" models/python tests tools || true
  rg "from thor_engine|import thor_engine" models/python/red2_engine && exit 1 || true
  ```

  Expected: no `thor_spec` imports in Python code. Historical docs may still contain `thor-spec` until Task 3.

- [ ] **Step 7: Run tests for package imports and core behavior**

  Run:

  ```sh
  uv run pytest tests/test_python_workspace_layout.py tests/test_parser_ast_pretty.py tests/test_semantics_core.py tests/test_red2_compiler.py tests/test_red2_machine_core.py -q
  ```

  Expected: PASS.

- [ ] **Step 8: Commit Task 1**

  Run:

  ```sh
  git add models/python tests models/python/pypeline_red2/README.md
  git commit -m "Split Python runtime packages"
  ```

### Task 2: Add direct CLI commands and update task runners

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Create: `models/python/thor_engine/cli.py`
- Create: `models/python/red2_engine/cli.py`
- Create: `models/python/thor_compile/cli.py`
- Modify: `pyproject.toml`
- Modify: `.mise.toml`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_cli_models.py`
- Modify: `tests/test_io_runtime.py`
- Modify: `tests/test_red2_binary.py`
- Modify: `tests/test_red2_wasm_cli.py`

**Interfaces:**
- Consumes: packages from Task 1: `thor_lang`, `thor_engine`, `red2_engine`, `thor_compile`.
- Produces: console scripts `thor`, `red2`, and `compile`; function entry points `thor_engine.cli.main(argv: list[str] | None = None) -> int`, `red2_engine.cli.main(argv: list[str] | None = None) -> int`, and `thor_compile.cli.main(argv: list[str] | None = None) -> int`.

**Parallelization rationale:** CLI wiring depends on package names but is otherwise separable from documentation updates; a good engineer would isolate the public command boundary for focused review.

- [ ] **Step 1: Write failing CLI entry-point tests**

  Update tests that currently import `thor_spec.cli.main` so they instead import specific command mains. In `tests/test_cli.py`, create tests like:

  ```python
  from __future__ import annotations

  from thor_engine.cli import main as thor_main
  from red2_engine.cli import main as red2_main
  from thor_compile.cli import main as compile_main


  def test_thor_cli_runs_expression(capsys) -> None:
      assert thor_main(["--expr", "(+ 2 3)", "--quantum", "20"]) == 0
      captured = capsys.readouterr()
      assert captured.out == "5\n"
      assert captured.err == ""


  def test_red2_cli_runs_expression(capsys) -> None:
      assert red2_main(["--expr", "(+ 2 3)", "--quantum", "20"]) == 0
      captured = capsys.readouterr()
      assert captured.out == "5\n"
      assert captured.err == ""


  def test_compile_cli_writes_red2_bytecode(tmp_path, capsys) -> None:
      output = tmp_path / "add.red2"
      assert compile_main(["--expr", "(+ 2 3)", "--output", str(output)]) == 0
      captured = capsys.readouterr()
      assert captured.out == ""
      assert captured.err == f"wrote RED2 bytecode: {output}\n"
      assert output.read_bytes().startswith(b"RED2")
  ```

  Update `tests/test_cli_models.py` resource-limit and IO command tests to call `thor_main(...)` or `red2_main(...)` directly. Remove tests for umbrella arguments like `main(["red2", ...])`, `main(["compile-red2", ...])`, and `main(["run-red2", ...])`; replace them with equivalent direct-command tests.

- [ ] **Step 2: Run failing CLI tests**

  Run:

  ```sh
  uv run pytest tests/test_cli.py tests/test_cli_models.py -q
  ```

  Expected: FAIL because `thor_engine.cli`, `red2_engine.cli`, and `thor_compile.cli` do not exist yet.

- [ ] **Step 3: Implement `thor_engine.cli`**

  Create `models/python/thor_engine/cli.py` with argparse behavior for THOR source. It must support:

  ```text
  thor [--expr SOURCE | FILE] [--quantum N] [--verbose] [--clock PATH] [--version]
  ```

  Behavior:
  - With a file positional argument, run the final expression as a UART action using `run_io_source(..., model="thor", ...)`.
  - With `--expr`, if the expression is an IO action, run it through `run_io_source`; otherwise use `run_source(..., model="thor", ...)` and print the reduced expression to stdout.
  - Preserve `--verbose` for IO result diagnostics: print `io result: VALUE` to stderr only when verbose is set.
  - Reject `--stack-size-in-bytes` and `--heap-size-in-bytes` because those are RED2-only.
  - Use error prefix `thor:`.

  Reuse helper functions rather than importing a shared old `thor_spec.cli` module. If helper duplication between `thor_engine.cli` and `red2_engine.cli` grows beyond argument parsing, extract a private module in `thor_engine/_cli_common.py` only if it does not import RED2 at module import time.

- [ ] **Step 4: Implement `red2_engine.cli`**

  Create `models/python/red2_engine/cli.py` with argparse behavior for Python RED2 over THOR source. It must support:

  ```text
  red2 [--expr SOURCE | FILE] [--quantum N] [--verbose] [--clock PATH] [--stack-size-in-bytes N] [--heap-size-in-bytes N] [--version]
  ```

  Behavior:
  - Source execution uses `run_io_source(..., model="red2", ...)` for file/IO action cases.
  - Pure `--expr` may use `run_source(..., model="red2", ...)` when not an IO action.
  - Resource-limit flags create `Red2ResourceLimits` and are passed through.
  - Use error prefix `red2:`.

- [ ] **Step 5: Implement `thor_compile.cli`**

  Create `models/python/thor_compile/cli.py` with argparse behavior:

  ```text
  compile [--expr SOURCE | FILE] --output OUTPUT
  ```

  Rules:
  - Accept a positional file path or `--expr`, but not both.
  - Parse and normalize the source with `thor_lang.parser.parse_program` and `thor_lang.normalization.normalize_program`.
  - Collect definitions and final expression just like the old compile command did.
  - Write `red2_engine.binary.encode_bundle(compile_expr(final), compile_definitions(definitions))` to output.
  - If no final expression exists, print `compile: compile requires a final expression` to stderr and return 2.
  - On success print `wrote RED2 bytecode: PATH` to stderr and return 0.

- [ ] **Step 6: Update `pyproject.toml` package and script entries**

  Replace `[project.scripts]` with:

  ```toml
  [project.scripts]
  thor = "thor_engine.cli:main"
  red2 = "red2_engine.cli:main"
  compile = "thor_compile.cli:main"
  ```

  Replace Hatchling packages with:

  ```toml
  packages = [
    "models/python/thor_lang",
    "models/python/thor_engine",
    "models/python/red2_engine",
    "models/python/thor_compile",
    "models/python/pypeline_red2",
  ]
  ```

- [ ] **Step 7: Update `.mise.toml` runners**

  Replace command invocations:

  ```text
  uv run thor-spec thor ... -> uv run thor ...
  uv run thor-spec red2 ... -> uv run red2 ...
  uv run thor-spec compile-red2 --file "$INPUT_FILE" --output "$IMAGE_FILE" -> uv run compile "$INPUT_FILE" --output "$IMAGE_FILE"
  ```

  Keep `mise run parity` only if a parity command exists after this task. If no parity console script is added, replace it with a small Python module invocation only if tests require it; otherwise remove the `parity` task from `.mise.toml` and docs.

- [ ] **Step 8: Update subprocess tests for command names**

  In `tests/test_io_runtime.py`, replace subprocess arguments using `uv run thor-spec --io --model thor --expr ...` with `uv run thor --expr ...`.

  In `tests/test_red2_wasm_cli.py`, replace any Python compile subprocess invocation with `uv run compile ...`.

- [ ] **Step 9: Run CLI and bytecode tests**

  Run:

  ```sh
  uv run pytest tests/test_cli.py tests/test_cli_models.py tests/test_io_runtime.py tests/test_red2_binary.py tests/test_red2_wasm_cli.py -q
  uv run thor --expr "(+ 2 3)" --quantum 20
  uv run red2 --expr "(+ 2 3)" --quantum 20
  uv run compile --expr "(+ 2 3)" --output /tmp/asgard-add.red2
  ```

  Expected: pytest passes; both run commands print `5`; compile writes `/tmp/asgard-add.red2` and prints `wrote RED2 bytecode: /tmp/asgard-add.red2` to stderr.

- [ ] **Step 10: Commit Task 2**

  Run:

  ```sh
  git add pyproject.toml .mise.toml models/python tests
  git commit -m "Add direct THOR and RED2 commands"
  ```

### Task 3: Update active documentation and examples

**Type:** implementation
**Depends-on:** 2

**Files:**
- Modify: `README.md`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `docs/red2-bytecode.md`
- Modify: `docs/thor-primitives.md`
- Modify: `docs/breakout-benchmarks.md`
- Modify: `examples/uart-caesar-plus4.thor`
- Modify: `examples/uart-alphanumerics.thor`
- Modify: `examples/hangman.thor`
- Test: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: direct commands `thor`, `red2`, and `compile` from Task 2.
- Produces: active docs and example comments that no longer direct users to `thor-spec`.

- [ ] **Step 1: Write failing docs test updates**

  Update `tests/test_docs_examples.py` so active docs must contain:

  ```python
  assert "uv run thor --expr" in readme
  assert "uv run red2 --expr" in readme
  assert "uv run compile --expr" in readme
  assert "uv run thor-spec" not in readme
  ```

  Add similar assertions for `docs/red2-bytecode.md`:

  ```python
  red2_bytecode = Path("docs/red2-bytecode.md").read_text()
  assert "uv run compile --expr" in red2_bytecode
  assert "uv run thor-spec" not in red2_bytecode
  ```

- [ ] **Step 2: Run failing docs tests**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py -q
  ```

  Expected: FAIL because active docs still mention `uv run thor-spec`.

- [ ] **Step 3: Update README command examples and package descriptions**

  In `README.md`, replace current command examples:

  ```text
  uv run thor-spec --model thor --quantum 20 --expr "(+ 2 3)" -> uv run thor --quantum 20 --expr "(+ 2 3)"
  uv run thor-spec --model red2 --quantum 20 --expr "(+ 2 3)" -> uv run red2 --quantum 20 --expr "(+ 2 3)"
  uv run thor-spec compile-red2 --expr "(+ 2 3)" --output /tmp/add.red2 -> uv run compile --expr "(+ 2 3)" --output /tmp/add.red2
  uv run thor-spec run-red2 --bytecode /tmp/add.red2 --quantum 20 -> cargo run -p red2-wasm -- /tmp/add.red2 --quantum 20
  ```

  Replace package descriptions with the new directories from the spec:

  ```text
  models/python/thor_lang/
  models/python/thor_engine/
  models/python/red2_engine/
  models/python/thor_compile/
  ```

- [ ] **Step 4: Update active docs and examples**

  Update `docs/thor-red2-prototype.md`, `docs/red2-bytecode.md`, `docs/thor-primitives.md`, `docs/breakout-benchmarks.md`, and active example comments to prefer direct commands. Do not rewrite old `docs/superpowers/plans/**` historical plans unless a test explicitly requires it.

- [ ] **Step 5: Run docs tests**

  Run:

  ```sh
  uv run pytest tests/test_docs_examples.py -q
  ```

  Expected: PASS.

- [ ] **Step 6: Commit Task 3**

  Run:

  ```sh
  git add README.md docs/thor-red2-prototype.md docs/red2-bytecode.md docs/thor-primitives.md docs/breakout-benchmarks.md examples tests/test_docs_examples.py
  git commit -m "Document direct Python commands"
  ```

### Task 4: Final integration gate

**Type:** gate
**Depends-on:** 1, 2, 3

**Files:**
- Test: full repository verification commands

**Interfaces:**
- Consumes: migrated packages, direct CLI commands, updated docs.
- Produces: evidence that the migration is complete and behavior-preserving.

- [ ] **Step 1: Verify no live Python imports reference `thor_spec`**

  Run:

  ```sh
  rg "thor_spec" models/python tests tools || true
  ```

  Expected: no matches except none. If matches appear in `docs/superpowers/**`, ignore because this command does not search docs.

- [ ] **Step 2: Verify no active command docs reference `uv run thor-spec`**

  Run:

  ```sh
  rg "uv run thor-spec|compile-red2|run-red2" README.md docs/thor-red2-prototype.md docs/red2-bytecode.md docs/thor-primitives.md docs/breakout-benchmarks.md examples || true
  ```

  Expected: no matches in active docs/examples.

- [ ] **Step 3: Run direct command smoke tests**

  Run:

  ```sh
  uv run thor --expr "(+ 2 3)" --quantum 20
  uv run red2 --expr "(+ 2 3)" --quantum 20
  uv run compile --expr "(+ 2 3)" --output /tmp/asgard-add.red2
  cargo run -p red2-wasm --quiet -- /tmp/asgard-add.red2 --quantum 20
  ```

  Expected: `thor` prints `5`, `red2` prints `5`, `compile` writes RED2 bytecode, and Rust RED2 accepts the bytecode.

- [ ] **Step 4: Run project verification**

  Run:

  ```sh
  mise run verify
  ```

  Expected: all Python tests, Ruff, mypy, and Rust tests pass.

## Operator smoke

- do: `uv run thor --expr "(+ 2 3)" --quantum 20`
- see: stdout is exactly `5`.

- do: `uv run red2 --expr "(+ 2 3)" --quantum 20`
- see: stdout is exactly `5`.

- do: `uv run compile --expr "(+ 2 3)" --output /tmp/asgard-add.red2`
- see: stderr says `wrote RED2 bytecode: /tmp/asgard-add.red2` and the file exists.

- do: `mise run benchmark-breakout --iterations 1`
- see: the CSV includes rows for `thor`, `red2`, `rust`, and `wasm`.

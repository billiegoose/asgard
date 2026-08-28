# Workspace Layout Reorganization Design

## Purpose

Reorganize the repository so the top-level layout communicates the major
workspaces clearly: executable models, developer tools, thesis material, docs,
examples, and tests. This follows the command-surface cleanup: `mise run ...`
commands remain the stable user-facing entrypoints while the underlying folders
move to more consistent homes.

## Goals

- Move model implementations under `models/`.
- Move the VS Code extension under `tools/`.
- Move thesis transcription under `thesis/`.
- Keep Python import names unchanged:
  - `thor_spec.*`
  - `pypeline_red2.*`
- Keep public task commands unchanged:
  - `mise run thor`
  - `mise run red2`
  - `mise run parity`
  - `mise run rust`
  - `mise run wasm`
  - `mise run hdl`
  - `mise run verify`
- Keep examples, tests, and docs at top level.
- Update project configuration, tests, and current docs to reference the new
  paths.

## Non-goals

- Do not split `thor_spec` into separate Python packages yet.
- Do not rename the Rust crate/package from `red2-wasm` in this phase.
- Do not change runtime behavior or command semantics.
- Do not rewrite historical implementation plans/specs solely to update old
  path references. They are records of prior work. Only update current docs,
  active configuration, tests, and operational guidance.
- Do not move `examples/`, `tests/`, or `docs/`.

## Target layout

```text
models/
  python/
    thor_spec/
    pypeline_red2/
  rust-red2/
    Cargo.toml
    src/
tools/
  vscode-thor/
thesis/
  transcription/
docs/
examples/
tests/
```

Top-level files remain:

```text
.mise.toml
.python-version
AGENTS.md
Cargo.toml
Cargo.lock
README.md
pyproject.toml
uv.lock
```

The resulting top-level directory list should be focused:

```text
docs/
examples/
models/
tests/
thesis/
tools/
```

Generated/cache directories such as `.venv/`, `target/`, `.mypy_cache/`,
`.pytest_cache/`, and `.ruff_cache/` may still exist locally but should not be
part of the conceptual source layout.

## Python package layout

Move:

```text
src/thor_spec/       -> models/python/thor_spec/
pypeline_red2/       -> models/python/pypeline_red2/
```

Keep imports unchanged. Tests and downstream code should still import:

```python
from thor_spec.parser import parse_program
from pypeline_red2.red2_stepper import red2_step_word
```

Update `pyproject.toml` accordingly:

- Hatch packages become:
  - `models/python/thor_spec`
  - `models/python/pypeline_red2`
- Ruff source roots include `models/python` and `tests`.
- mypy checks `models/python` and `tests`.
- Any command examples that explicitly check `src tests` should become
  `models/python tests` or use `mise run typecheck`.

## Rust model layout

Move:

```text
red2-wasm/ -> models/rust-red2/
```

Keep the crate/package name `red2-wasm`, so existing Cargo package commands
continue to work:

```sh
cargo test -p red2-wasm
cargo run -p red2-wasm -- ...
```

Update the workspace root `Cargo.toml` member path from `red2-wasm` to
`models/rust-red2`.

Update `.mise.toml` tasks so:

- native Rust task still invokes `cargo run -p red2-wasm`.
- Wasm task uses `target/wasm32-wasi/debug/red2-wasm.wasm` as before.
- no task command changes are visible to users.

## Tools layout

Move:

```text
vscode-thor/ -> tools/vscode-thor/
```

Update tests that read `package.json`, language configuration, grammar, README,
or CHANGELOG from the extension. Update current docs to reference the new path.

The extension remains independent from interpreter internals.

## Thesis layout

Move:

```text
thesis-transcription/ -> thesis/transcription/
```

Update `AGENTS.md` and current README/docs references. The thesis build command
becomes:

```sh
thesis/transcription/scripts/compile.sh
```

The source baseline note becomes:

```text
thesis/transcription/src/main.tex
```

## Documentation policy

Update current operational docs:

- `README.md`
- `docs/thor-red2-prototype.md`
- `docs/red2-bytecode.md`
- `AGENTS.md`
- model/tool-local READMEs that contain path references

Do not mass-edit old `docs/superpowers/plans/` or
`docs/superpowers/specs/` files unless a new active plan/spec depends on them.
Those documents preserve the paths that existed when they were written.

## Tests and verification

Add or update tests to make the layout stable:

- Python package imports still work from installed/editable project context.
- `models/python/thor_spec` exists and old `src/thor_spec` does not.
- `models/python/pypeline_red2` exists and old top-level `pypeline_red2` does
  not.
- `models/rust-red2/Cargo.toml` exists and old `red2-wasm/Cargo.toml` does not.
- `tools/vscode-thor/package.json` exists and old `vscode-thor/package.json`
  does not.
- `thesis/transcription/scripts/compile.sh` exists and old
  `thesis-transcription/scripts/compile.sh` does not.
- `mise run verify` passes.
- Representative model tasks still work after the move, especially:
  - `mise run thor examples/hangman.thor --quantum 5000`
  - `mise run red2 examples/hangman.thor --quantum 5000`
  - `mise run parity examples/fibonacci.thor --quantum 75`
  - `printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor --quantum 5000`
  - `printf 'A\nS\nG\nR\nD\n' | mise run wasm examples/hangman.thor --quantum 5000`

## Migration strategy

Use a few focused commits:

1. Move Python packages and update Python config/tests.
2. Move Rust crate and update Cargo/mise/tests.
3. Move VS Code extension and thesis transcription, then update docs and path
   tests.
4. Run final verification and task smokes.

This ordering keeps each failure mode narrow: Python packaging, Rust workspace,
then docs/tool path references.

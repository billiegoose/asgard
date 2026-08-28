# Mise Command Surface Design

## Purpose

Provide one consistent repo-local command surface for running the THOR/RED2
implementations without requiring contributors to remember whether a path uses
`uv`, `cargo`, or `wasmtime`. This is a command-first cleanup: it does not move
source directories or rename model implementations.

## Goals

- Add `mise run` tasks for each execution backend:
  - `mise run thor <file>`
  - `mise run red2 <file>`
  - `mise run rust <file>`
  - `mise run wasm <file>`
  - `mise run hdl <file>`
- Make these commands suitable for UART-style examples by default:
  - stdout is simulated device/UART output.
  - stderr is quiet unless an error occurs.
  - `--verbose` enables diagnostic output.
- Keep model-specific plumbing inside the existing Python and Rust CLIs where
  possible.
- Avoid repo-local shim scripts for dispatch.
- Preserve existing implementation directories for now.

## Non-goals

- Do not reorganize `src/`, `red2-wasm/`, `pypeline_red2/`, `vscode-thor/`, or
  `tests/` in this phase.
- Do not add a new task runner dependency.
- Do not expose a public task flag for IO mode. The `mise run` backend commands
  should choose their default runtime behavior directly.
- Do not implement HDL execution yet. `mise run hdl <file>` is a placeholder.

## Command interface

Each task accepts a THOR source file as the first positional argument. Runnable
backends also accept common flags:

```sh
mise run thor <file> [--quantum <n>] [--verbose]
mise run red2 <file> [--quantum <n>] [--verbose]
mise run rust <file> [--quantum <n>] [--verbose]
mise run wasm <file> [--quantum <n>] [--verbose]
mise run hdl <file>
```

Example:

```sh
printf 'A\nS\nG\nR\nD\n' | mise run rust examples/hangman.thor
```

Expected default behavior:

- stdout contains rendered UART text, such as Hangman prompts and `WIN`.
- stderr is empty on success.
- with `--verbose`, stderr may include compile paths, final IO result, or other
  backend diagnostics.

## Python CLI behavior

The Python `thor-spec` CLI remains the implementation entrypoint for `thor` and
`red2` tasks.

Required behavior:

- Add a verbose/quiet distinction for IO execution.
- Quiet default suppresses normal final-result diagnostics such as
  `io result: NIL`.
- `--verbose` restores diagnostics.
- Existing direct CLI behavior should remain compatible where practical, but the
  public `mise run` interface is the new preferred path.

Task mappings:

- `mise run thor <file>` invokes Python THOR semantics on `<file>`.
- `mise run red2 <file>` invokes the Python RED2 VM on `<file>`.

## Rust CLI behavior

The Rust `red2-wasm` CLI remains the native RED2 bytecode executor.

Required behavior:

- Native runs should default to the UART/device-output execution mode used by
  examples.
- Quiet default suppresses normal final-result diagnostics such as
  `io result: NIL`.
- `--verbose` restores diagnostics.
- Final expression/result output must not go to stdout.

Task mapping:

- `mise run rust <file>` compiles `<file>` to a temporary `.red2` bundle, then
  runs the native Rust executor with that bundle.

## Wasm task behavior

The Wasm task exercises the same Rust VM through Wasmtime.

Required behavior:

- Compile `<file>` to a temporary `.red2` bundle.
- Build or reuse the WASI artifact as needed.
- Run through `wasmtime` with an appropriate preopened temporary directory.
- Match the same stdout/stderr policy as `mise run rust`.

Task mapping:

- `mise run wasm <file>` compiles `<file>`, ensures the WASI artifact exists,
  and executes it with Wasmtime.

## HDL placeholder

`mise run hdl <file>` is intentionally a placeholder for now:

```sh
echo "todo"
```

This reserves the command shape without implying that arbitrary THOR files can
currently run through the Pypeline/PypelineC artifact.

## Mise task style

Use `.mise.toml` TOML tasks with `usage = ''' ... '''` declarations for proper
argument parsing and help. Prefer `run = [...]` arrays for multi-step flows such
as compile-then-run backends.

The tasks should not call a repo-local dispatch shim. Each task should directly
invoke the underlying CLI commands needed for that backend.

## Documentation updates

Update the README to present `mise run` as the canonical command surface. Keep
lower-level `uv`, `cargo`, and `wasmtime` examples only where they explain
implementation details rather than normal day-to-day use.

## Testing and verification

Add or update tests to cover:

- Python quiet default suppresses final IO diagnostics.
- Python `--verbose` emits final IO diagnostics.
- Rust quiet default suppresses final IO diagnostics.
- Rust `--verbose` emits final IO diagnostics.
- `mise run thor`, `red2`, `rust`, and `wasm` run a representative UART example.
- `mise run hdl <file>` prints `todo`.

Full verification should include:

```sh
mise run verify
```

The `verify` task should run the established project gates:

- Python tests
- Ruff
- mypy
- Rust tests

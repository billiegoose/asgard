# Python Package and CLI Migration Design

## Goal

Replace the monolithic `thor_spec` Python package with clearer packages for THOR syntax, THOR execution, RED2 execution, and THOR-to-RED2 compilation. Make the direct command surface the primary user interface:

- `uv run thor ...`
- `uv run red2 ...`
- `uv run compile ...`

No `thor_spec` compatibility shims should remain.

## Package Layout

```text
models/python/
  thor_lang/
    __init__.py
    ast.py
    parser.py
    pretty.py
    normalization.py
    primitives.py
    version.py

  thor_engine/
    __init__.py
    cli.py
    core.py
    golden.py
    io_runtime.py
    lockstep.py
    semantics.py

  red2_engine/
    __init__.py
    binary.py
    instructions.py
    machine.py
    pipelinec_vectors.py
    primitives.py

  thor_compile/
    __init__.py
    cli.py
    red2.py
```

## Boundaries

- `thor_lang` owns syntax, AST, pretty-printing, normalization, language-level primitive metadata/helpers, and version metadata.
- `thor_engine` owns executable THOR semantics, IO runtime orchestration, parity helpers, golden runners, and the `thor` command.
- `red2_engine` owns RED2 bytecode structures, binary encoding/decoding, primitive firing over RED2 instructions, PipelineC vectors, the RED2 machine, and RED2 reusable definition caches.
- `thor_compile` owns cross-boundary compilation from THOR AST/program definitions to RED2 images and the `compile` command.
- `red2_engine` must not import `thor_engine`. It may import `thor_lang` only for user-facing expression materialization until a future lower-level RED2 result type exists.
- `thor_compile` may import both `thor_lang` and `red2_engine` because it is the explicit translation boundary.
- `thor_engine` may import `thor_compile` and `red2_engine` only where the RED2 model/runtime is selected.

## CLI Behavior

`uv run thor` runs THOR source as the current UART action interface formerly exposed by `uv run thor-spec thor`:

```sh
uv run thor examples/breakout.thor --quantum 50000 --clock /tmp/asgard-clock
uv run thor --expr "(+ 2 3)" --quantum 20
```

`uv run red2` runs THOR source through the Python RED2 model, formerly `uv run thor-spec red2`:

```sh
uv run red2 examples/breakout.thor --quantum 50000 --clock /tmp/asgard-clock
uv run red2 --expr "(+ 2 3)" --quantum 20
```

`uv run compile` compiles THOR source to RED2 bytecode, formerly `uv run thor-spec compile-red2`:

```sh
uv run compile examples/breakout.thor --output examples/breakout.red2
uv run compile --expr "(+ 2 3)" --output /tmp/add.red2
```

The old `thor-spec` script is removed. The Python `run-red2` bytecode helper does not need a top-level CLI replacement in this migration; native Rust/WASM bytecode execution remains available through existing `mise run rust` and `mise run wasm` tasks.

## Tests and Documentation

All Python imports in tests and source must move away from `thor_spec.*`. Documentation should describe the new package names and command names for current user-facing examples. Historical implementation plans/specs may keep old commands when they describe past work, but active README and command docs should be updated.

## Constraints

- Python remains 3.14.
- The package build keeps using Hatchling and `models/python` as the source root.
- No new runtime dependencies.
- Preserve current behavior and output for THOR, RED2, parity helpers, RED2 binary encoding/decoding, and benchmark tasks except for intentional CLI command names.
- Keep the recent RED2 definition-cache optimization in the RED2 engine layer.

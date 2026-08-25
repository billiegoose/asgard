# Asgard

An executable Python specification for THOR, the machine language described in
Michael Lee Hilton's 1990 dissertation, *Implementation of Declarative
Languages*.

The first milestone is a small, directly-readable VM that models the thesis
faithfully. Once that behavior is stable, it can act as the reference model for
PipelineC/Pypeline HDL or other hardware implementations.

## Local Setup

This project is configured for local tools only:

```sh
mise trust
mise install
uv sync
```

If `mise` is not installed yet, `uv sync` will still create/use `.venv` with a
compatible Python when possible.

## Useful Commands

```sh
uv run thor-spec --help
uv run pytest
uv run ruff check .
uv run mypy src tests
```

## Current Shape

- `src/thor_spec/core.py` contains a small fuel-bounded execution loop.
- `src/thor_spec/cli.py` exposes the project command.
- `tests/` locks down the scaffold behavior.

The actual THOR graph representation, instruction set, and reduction rules will
be added after the thesis PDF is available.

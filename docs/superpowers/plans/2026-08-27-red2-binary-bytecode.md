# RED2 Binary Bytecode Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic serializable `.red2` binary bytecode format for compiled RED2 program images.

**Architecture:** Introduce a v1 container with a fixed header, 32-bit instruction words, file-local literal table, metadata table, and CRC32 checksum. Keep the format Rust/WASM-VM friendly: little-endian fixed-width numeric fields, length-prefixed UTF-8 strings, IEEE-754 float64 literals, and explicit section counts.

**Tech Stack:** Python 3.14, pytest, argparse, existing RED2 compiler/machine.

**Spec:** User approved a concrete `.red2` binary format and added a roadmap step: after Python bytecode serialization, build a Rust RED2 VM executor compilable to WASM before moving toward FPGA flash execution.

## Global Constraints

- Preserve existing RED2 instruction semantics and current CLI behavior.
- `.red2` output must be deterministic for identical source input.
- Encoded bytecode must round-trip into a `ProgramImage` that the Python `Red2Machine` can execute.
- The v1 format must be documented as a stable Python/Rust/WASM interchange target, not an FPGA-final memory image.
- Run `uv run pytest`, `uv run ruff check .`, and `uv run mypy src tests` before completion.

**Acceptance:** suite — committed tests cover binary header, deterministic encoding, decode/execute round-trip, checksum rejection, CLI compile/run, and docs.

---

### Task 1: Binary codec module

**Type:** implementation
**Depends-on:** none
**Review:** adversarial

**Files:**
- Create: `src/thor_spec/red2/binary.py`
- Test: `tests/test_red2_binary.py`

**Interfaces:**
- Consumes: `ProgramImage`, `Instruction`, `Opcode` from `src/thor_spec/red2/instructions.py`
- Produces: `encode_program_image(image: ProgramImage) -> bytes`, `decode_program_image(data: bytes) -> ProgramImage`, `Red2BinaryError`

**Parallelization rationale:** The codec is a standalone contract consumed by CLI and future Rust VM work.

- [ ] Write failing tests for magic/version/header, deterministic encoding, decode/execute round-trip, and checksum rejection.
- [ ] Implement little-endian v1 container with file-local literal table and CRC32.
- [ ] Verify focused tests pass.

---

### Task 2: CLI compile/run support

**Type:** implementation
**Depends-on:** 1
**Review:** lean

**Files:**
- Modify: `src/thor_spec/cli.py`
- Test: `tests/test_cli_models.py`

**Interfaces:**
- Consumes: `encode_program_image`, `decode_program_image` from Task 1
- Produces: `thor-spec compile-red2 --file input.thor --output output.red2` and `thor-spec run-red2 --bytecode output.red2 --quantum N`

- [ ] Write failing CLI tests for compiling `.thor` to `.red2` and running `.red2` through the Python RED2 machine.
- [ ] Add argparse subcommands without breaking existing option-based CLI usage.
- [ ] Verify focused CLI tests pass.

---

### Task 3: Documentation and Rust/WASM roadmap note

**Type:** implementation
**Depends-on:** 1, 2
**Review:** lean

**Files:**
- Create: `docs/red2-bytecode.md`
- Modify: `README.md`
- Test: `tests/test_docs_examples.py`

**Interfaces:**
- Consumes: `.red2` format and CLI commands from Tasks 1-2
- Produces: documented bytecode format and roadmap statement for Rust VM/WASM before FPGA flash execution.

- [ ] Document the binary layout and compatibility constraints.
- [ ] Add README command examples.
- [ ] Add docs tests that link the bytecode document.
- [ ] Run full final gate.

## Operator smoke

- do: `uv run thor-spec compile-red2 --file vscode-thor/examples/fibonacci.thor --output /tmp/fibonacci.red2`
- see: `/tmp/fibonacci.red2` starts with `RED2` and is deterministic across repeated compiles.

- do: `uv run thor-spec run-red2 --bytecode /tmp/fibonacci.red2 --quantum 2000`
- see: output is `8`.

# Rust/WASM Breakout CLOCK Design

## Goal

Make the Rust RED2 engine and WASI build capable of running `examples/breakout.thor` with the same user-facing behavior as the Python THOR/RED2 runners, including both real system time and deterministic simulated clock input. Demonstrate the WASM path by adding a committed asciinema recording reference to `examples/README.md`.

## Requirements

- Rust native and WASI executions support `(CLOCK)` as an IO action.
- With no clock flag, `(CLOCK)` returns the host Unix timestamp in milliseconds.
- With `--clock <path>`, `(CLOCK)` uses a latest-value file clock: read newline-delimited integer millisecond timestamps, keep the latest valid value, ignore malformed lines, and retain the previous value if the file is absent or unreadable.
- `mise run rust` and `mise run wasm` expose `--clock <path>` using the same behavior as Python tasks.
- Existing stdout/stderr policy remains unchanged: stdout is UART/device output, success diagnostics appear only under `--verbose`.
- Existing Hangman and UART examples continue to pass under Rust native and WASI.
- Add tests that exercise Rust CLI clock behavior and Breakout execution with controlled clock input.
- Add or update documentation so Breakout can be run via Rust/WASM with real and simulated clocks.
- Add a WASM Breakout asciinema recording artifact and reference it from `examples/README.md`.

## Architecture

The Rust engine already has a pure reducer and an `IoRunner` that sequences UART-style actions. Extend that IO layer with a small clock-source abstraction. The abstraction should be available to the CLI and task wrappers without changing bytecode format or compiler output: `CLOCK` remains a symbol/action name encoded in `.red2` bundles like existing IO actions.

The native/WASI CLI should parse `--clock <path>` and construct either a system clock or latest-file clock. Because the crate currently avoids external dependencies, implement Unix milliseconds with `std::time::{SystemTime, UNIX_EPOCH}` and latest-file reads with `std::fs::read_to_string`.

`IoRunner` should treat both bare `CLOCK` and `(CLOCK)` consistently with other IO actions. It returns `Expr::Int(now_ms)`. The current `Expr::Int(i32)` representation cannot hold current epoch milliseconds, so integer storage must be widened to `i64` across Rust bytecode decoding, expression values, primitive arithmetic, UART byte conversion, and tests. Bytecode integer payloads are still encoded as 32-bit values today, so decoding can convert `i32` payloads into `i64` runtime values.

## Testing Strategy

Add tests at three levels:

1. Rust unit tests for clock sources and `(CLOCK)` IO evaluation.
2. Python CLI tests in `tests/test_red2_wasm_cli.py` that compile small THOR snippets to bytecode and run `cargo run -p red2-wasm`, verifying controlled clock output and quiet stderr.
3. `mise` tests for `rust` and `wasm` Breakout smoke runs with controlled clock input and quick quit, proving task wiring and WASI execution.

Use temporary clock files under pytest `tmp_path` to avoid shared state. Keep real-clock tests broad: assert the returned value is nonzero/recent enough when surfaced through a byte-safe expression, rather than asserting exact wall-clock output.

## Recording and Docs

Generate a deterministic WASM Breakout asciinema cast using the controlled clock path so the committed recording is stable. Add the recording to `examples/media/` and reference it from `examples/README.md` alongside the existing Breakout recording. Update README/docs language that currently says Rust/WASM CLOCK support is deferred.

## Non-goals

- Do not change the `.red2` bytecode container format.
- Do not add async terminal input, raw TTY mode, or a real-time game loop beyond the existing stdin/clock-driven example behavior.
- Do not rewrite the Python runtime or compiler except for tests/docs that verify Rust/WASM parity.

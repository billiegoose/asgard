# THOR Hangman Example Design

## Goal

Add a declarative `examples/hangman.thor` program that runs under the Python THOR IO runtime, Python RED2 IO runtime, native Rust RED2 VM, and Wasmtime Rust RED2 VM.

## Requirements

- The example uses top-level `examples/`, not the VS Code extension directory.
- The game is written as reusable utility definitions plus a small top-level action, not one large expression.
- stdout remains the simulated UART stream.
- stderr remains reserved for final IO diagnostics and host errors.
- The first game target is Hangman; its utility style should be reusable for Tic-tac-toe, Pong, and Breakout.
- Completion notification uses `afplay /System/Library/Sounds/Glass.aiff` after fresh verification.

## Program Behavior

The first Hangman version uses a fixed word: `ASGARD`.

State is represented by parameters to a recursive `loop` function:

- whether `A` has been guessed
- whether `S` has been guessed
- whether `G` has been guessed
- whether `R` has been guessed
- whether `D` has been guessed
- miss count
- ignored sequencing value

The UART protocol is deterministic and script-friendly:

1. Render the current board/status.
2. If all letters are guessed, print `WIN\n` and stop.
3. If misses reach 6, print `LOSE\n` and stop.
4. Read one byte from UART.
5. ESC byte 27 exits without win/loss text.
6. Letter guesses update the matching letter flag.
7. Non-matching guesses increment misses.
8. Repeat.

The first implementation is a short three-miss game so Rust VM integration tests
stay fast. For canned input `ASGRD`, stdout should contain a final `WIN\n`. For
canned input `xyzuvw`, stdout should contain a final `LOSE\n`.

## Utility Style

`examples/hangman.thor` is organized into sections:

- constants
- boolean/predicate helpers
- UART text rendering helpers
- Hangman-specific rendering
- state update helpers
- game loop
- top-level action

Initial helpers are local to the file because the current THOR tooling does not have imports/includes. They should still be written as clean top-level definitions that can be lifted into a future examples library.

Core helper concepts:

- `emit-2`, `emit-3`, `emit-4`, `emit-5`, `emit-6` for readable text emission.
- `emit-known` to print either a revealed byte or underscore.
- `hit?` to test whether a guess matches any target letter.
- `known-after-*` helpers to update per-letter flags declaratively.
- `win?` to compute terminal success.
- `misses-after` to update misses only on misses.

## Implementation Notes

The existing Rust VM already supports the required subset: bundled top-level definitions, recursion, `IF`, `AND`, `OR`, integer comparisons/arithmetic, and IO actions. If tests reveal missing primitives or an evaluator issue, implement the smallest utility/runtime fix needed by Hangman rather than simplifying the fixture.

## Tests

Add automated tests for:

- Python THOR IO Hangman win smoke.
- Python RED2 IO Hangman win smoke.
- Native Rust RED2 VM Hangman win smoke.
- Native Rust RED2 VM Hangman lose smoke.
- Wasmtime smoke command in docs or a guarded test if practical.

Final verification commands:

- `cargo test -p red2-wasm`
- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy src tests`
- native Rust Hangman smoke
- Wasmtime Hangman smoke

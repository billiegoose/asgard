# Breakout and CLOCK IO Design

## Purpose

Add a deterministic, terminal-oriented Breakout example for the Python THOR and
Python RED2 runtimes. The game uses a new simulated IO action, `(CLOCK)`, so it
can advance from elapsed time rather than one input byte per game tick.

## Goals

- Add a Python runtime IO action:
  - `(CLOCK)` returns a Unix timestamp in milliseconds as a THOR integer.
  - `(CLOCK)` is sequenced through the IO/world runtime and is not a pure
    primitive.
- Add deterministic clock control for tests and demos:
  - `--clock <path>` on Python model runner commands.
  - `mise run thor ... --clock <path>` and `mise run red2 ... --clock <path>`.
- Add `examples/breakout.thor` as a richer terminal game example:
  - fixed 20 column x 12 row board.
  - ANSI clear/home redraw on stdout.
  - left/right arrow key support.
  - score, lives, instructions, bricks, paddle, ball, win, lose, and quit path.
- Keep the command surface consistent with existing `mise run` tasks.
- Keep stdout reserved for terminal/device output and stderr quiet by default.

## Non-goals

- Do not implement Rust or Wasm support for `(CLOCK)` in this phase.
- Do not implement raw terminal mode in this phase.
- Do not make Breakout depend on real-time keyboard polling. It remains a
  byte-stream program that can be tested with piped input and controlled clock
  values.
- Do not add imports/includes for shared THOR libraries yet.

## CLOCK semantics

`(CLOCK)` is a simulated IO action. It is used with the existing IO monad forms:

```lisp
(IO-BIND (CLOCK)
  (LAMBDA (now-ms)
    ...))
```

Behavior:

- It returns an integer timestamp in milliseconds.
- Without `--clock`, it returns the current wall-clock Unix timestamp in
  milliseconds.
- With `--clock <path>`, the runtime treats `<path>` as a latest-value source:
  - Each newline-delimited integer read from the path updates the stored clock.
  - `(CLOCK)` returns immediately with the latest valid value.
  - If no valid value has been read yet, the initial value is the wall-clock
    time when the clock source is created.
  - Malformed lines are ignored.
- Reading `(CLOCK)` must remain ordered by the IO world sequencing. A program
  cannot call it as a pure primitive.

## Clock source implementation

The Python IO runtime should own a clock abstraction rather than hard-coding
wall-clock calls in the reducer. A minimal interface is enough:

```python
class ClockSource(Protocol):
    def now_ms(self) -> int: ...
```

Implementations:

- `SystemClockSource`: returns `int(time.time() * 1000)`.
- `LatestFileClockSource`: accepts a path, keeps the latest valid integer, and
  polls for appended/newly available newline-delimited values whenever `now_ms()`
  is called.

The controlled clock source is intended for named pipes in tests, but should not
require named-pipe-specific APIs. Reading available text from a regular file is
also acceptable if the tests use one.

## CLI and task behavior

Add `--clock <path>` only where it can be honored:

- `thor-spec thor <file> [--quantum N] [--verbose] [--clock PATH]`
- `thor-spec red2 <file> [--quantum N] [--verbose] [--clock PATH]`
- `mise run thor <file> [--quantum N] [--verbose] [--clock PATH]`
- `mise run red2 <file> [--quantum N] [--verbose] [--clock PATH]`

Do not expose `--clock` on `mise run rust` or `mise run wasm` until their
runtimes implement `(CLOCK)`.

Default diagnostics policy remains unchanged:

- stdout is simulated terminal/device output.
- stderr is quiet on success.
- `--verbose` enables final IO-result diagnostics.

## Breakout terminal model

Add `examples/breakout.thor`.

Board:

- 20 columns x 12 rows.
- Top/bottom and left/right walls rendered every frame.
- Bricks occupy a small fixed set of cells near the top.
- Paddle is a fixed-width horizontal segment near the bottom.
- Ball is one cell.

Rendering:

- Each frame starts with ANSI clear/home:
  - ESC `[2J`
  - ESC `[H`
- Render score, lives, and instructions above or below the board.
- Use simple ASCII glyphs:
  - wall: `#`
  - brick: `=`
  - paddle: `_`
  - ball: `o`
  - empty: space

Input:

- Left arrow is byte sequence `ESC [ D`.
- Right arrow is byte sequence `ESC [ C`.
- `q` or `Q` quits.
- Other bytes are ignored.

Ticking:

- The game reads `(CLOCK)` in the loop.
- Ball movement occurs only when enough milliseconds have elapsed since the
  last tick.
- For tests, use a small fixed tick interval, such as 100 ms.
- If input arrives but not enough time has elapsed, the paddle can still update
  and the frame can redraw without moving the ball.

Gameplay:

- Ball bounces off left/right/top walls.
- Ball bounces off the paddle.
- Ball hitting a brick removes that brick and increments score.
- Ball falling below the paddle loses one life and resets ball/paddle position.
- Losing all lives prints `LOSE`.
- Removing all bricks prints `WIN`.
- Quit prints `QUIT` or exits cleanly with a final frame/message.

## Testing

Add Python tests for:

- `(CLOCK)` returns an integer in IO mode.
- A controlled clock source returns the latest valid timestamp.
- malformed clock source input is ignored.
- CLI/model subcommands accept `--clock` for `thor` and `red2`.
- `mise run thor` and `mise run red2` forward `--clock`.
- Breakout first frame contains ANSI clear/home and board text.
- Left/right arrow input changes paddle rendering.
- Advancing clock changes ball position.
- A deterministic brick collision updates score and removes a brick.
- Deterministic quit/win/lose paths produce their expected messages where
  feasible within the default quantum.

## Documentation

Update README examples to mention Breakout under Python model tasks:

```sh
mise run thor examples/breakout.thor --clock /tmp/asgard-clock
mise run red2 examples/breakout.thor --clock /tmp/asgard-clock
```

Document that Rust/Wasm `(CLOCK)` support is deferred.

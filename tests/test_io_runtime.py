import subprocess
import sys
from collections.abc import Callable, Mapping
from io import StringIO
from pathlib import Path
from typing import cast

import pytest

from red2_engine.instructions import DefinitionImage
from thor_engine.golden import ModelName
from thor_engine.io_runtime import LatestFileClockSource, run_io_source
from thor_engine.semantics import ThorDefinitionCache, reduce_expr
from thor_lang.ast import Definition, Expr
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source


class FixedClock:
    def __init__(self, value: int) -> None:
        self.value = value

    def now_ms(self) -> int:
        return self.value


class AdvancingClock:
    def __init__(self, *, start: int = 0, step: int = 1000) -> None:
        self.value = start - step
        self.step = step

    def now_ms(self) -> int:
        self.value += self.step
        return self.value


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def run_io(
    source: str,
    *,
    stdin_text: str = "",
    model: ModelName = "thor",
    quantum: int = 100,
) -> tuple[str, str, str]:
    stdin = StringIO(stdin_text)
    stdout = StringIO()
    stderr = StringIO()
    result = run_io_source(
        source,
        model=model,
        quantum=quantum,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )
    return result, stdout.getvalue(), stderr.getvalue()


def test_clock_io_action_returns_integer_for_thor_model() -> None:
    result = run_io_source(
        "(CLOCK)",
        model="thor",
        quantum=100,
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=StringIO(),
        clock=FixedClock(1_700_000_000_123),
    )

    assert result == "1700000000123"


def test_clock_io_action_returns_integer_for_red2_model() -> None:
    result = run_io_source(
        "(CLOCK)",
        model="red2",
        quantum=100,
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=StringIO(),
        clock=FixedClock(1_700_000_000_456),
    )

    assert result == "1700000000456"


def test_red2_io_compiles_definition_image_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import thor_engine.io_runtime as io_runtime

    original_compile_definitions = cast(
        Callable[[Mapping[str, Expr]], DefinitionImage],
        io_runtime.__dict__["compile_definitions"],
    )
    calls = 0

    def counting_compile_definitions(
        definitions: Mapping[str, Expr],
    ) -> DefinitionImage:
        nonlocal calls
        calls += 1
        return original_compile_definitions(definitions)

    monkeypatch.setattr(io_runtime, "compile_definitions", counting_compile_definitions)

    result, stdout, stderr = run_io(
        """
        emit == (LAMBDA (n) (UART-TX (+ n 64)))
        (IO-THEN (emit 1) (IO-THEN (emit 2) (emit 3)))
        """,
        model="red2",
    )

    assert result == "NIL"
    assert stdout == "ABC"
    assert stderr == ""
    assert calls == 1


def test_thor_io_translates_definitions_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_from_definitions: Callable[[Mapping[str, Expr]], ThorDefinitionCache] = (
        ThorDefinitionCache.from_definitions
    )
    calls = 0

    def counting_from_definitions(
        definitions: Mapping[str, Expr],
    ) -> ThorDefinitionCache:
        nonlocal calls
        calls += 1
        return original_from_definitions(definitions)

    monkeypatch.setattr(
        ThorDefinitionCache,
        "from_definitions",
        counting_from_definitions,
    )

    result, stdout, stderr = run_io(
        """
        emit == (LAMBDA (n) (UART-TX (+ n 64)))
        (IO-THEN (emit 1) (IO-THEN (emit 2) (emit 3)))
        """,
        model="thor",
    )

    assert result == "NIL"
    assert stdout == "ABC"
    assert stderr == ""
    assert calls == 1


def test_red2_y_defined_io_action_preserves_zero_arg_clock_call() -> None:
    result = run_io_source(
        """
        loop ==
          (Y
            (LAMBDA (self)
              (LAMBDA (last)
                (IO-BIND (CLOCK)
                  (LAMBDA (now)
                    (IO-RETURN now))))))

        (loop 0)
        """,
        model="red2",
        quantum=1000,
        stdin=StringIO(""),
        stdout=StringIO(),
        stderr=StringIO(),
        clock=FixedClock(1_700_000_000_789),
    )

    assert result == "1700000000789"


def test_deep_io_then_chain_does_not_consume_python_stack() -> None:
    source = """
    loop ==
      (Y
        (LAMBDA (self)
          (LAMBDA ()
            (IO-BIND (TICKS)
              (LAMBDA (n)
                (if (= n 250)
                    (IO-RETURN 0)
                    (IO-THEN (UART-TX 46) (self))))))))

    (loop)
    """
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        result, stdout, stderr = run_io(source, quantum=1000)
    finally:
        sys.setrecursionlimit(previous_limit)

    assert result == "0"
    assert stdout == "." * 250
    assert stderr == ""


def test_clock_dots_example_emits_dots_without_python_stack_growth() -> None:
    class StopAfterDotsError(Exception):
        pass

    class BoundedStdout(StringIO):
        def __init__(self, limit: int) -> None:
            super().__init__()
            self.limit = limit

        def write(self, text: str) -> int:
            written = super().write(text)
            if self.getvalue().count(".") >= self.limit:
                raise StopAfterDotsError
            return written

    previous_limit = sys.getrecursionlimit()
    stdout = BoundedStdout(20)
    stderr = StringIO()
    try:
        sys.setrecursionlimit(80)
        with pytest.raises(StopAfterDotsError):
            run_io_source(
                Path("examples/clock-dots.thor").read_text(),
                model="thor",
                quantum=500,
                stdin=StringIO(""),
                stdout=stdout,
                stderr=stderr,
                clock=AdvancingClock(step=1000),
            )
    finally:
        sys.setrecursionlimit(previous_limit)

    assert stdout.getvalue().count(".") >= 20
    assert "RecursionError" not in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_latest_file_clock_source_returns_latest_valid_value(tmp_path: Path) -> None:
    clock_file = tmp_path / "clock.txt"
    clock_file.write_text("1700000000000\nnot-a-clock\n1700000000123\n")
    clock = LatestFileClockSource(clock_file, initial_ms=123)

    assert clock.now_ms() == 1_700_000_000_123

    clock_file.write_text(
        "1700000000000\nnot-a-clock\n1700000000123\n1700000000456\n"
    )
    assert clock.now_ms() == 1_700_000_000_456


def test_uart_tx_writes_byte_to_stdout_and_returns_nil() -> None:
    result, stdout, stderr = run_io("(UART-TX 65)")

    assert result == "NIL"
    assert stdout == "A"
    assert stderr == ""


def test_uart_rx_reads_byte_from_stdin() -> None:
    result, stdout, stderr = run_io("(UART-RX)", stdin_text="Z")

    assert result == "90"
    assert stdout == ""
    assert stderr == ""


def test_cli_uart_rx_returns_nil_when_open_stdin_has_no_ready_byte() -> None:
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "thor",
            "--verbose",
            "--expr",
            "(UART-RX)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        process.wait(timeout=3.0)
        stdout, stderr = process.communicate(timeout=1.0)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()

    assert process.returncode == 0
    assert stdout == ""
    assert stderr == "io result: NIL\n"


def test_uart_tx_bytes_writes_list_of_bytes_to_stdout() -> None:
    result, stdout, stderr = run_io("(UART-TX-BYTES [65 66 67])")

    assert result == "NIL"
    assert stdout == "ABC"
    assert stderr == ""


def test_io_bind_lifts_uart_rx_value_into_next_action() -> None:
    result, stdout, stderr = run_io(
        "(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))",
        stdin_text="!",
    )

    assert result == "NIL"
    assert stdout == "!"
    assert stderr == ""


def test_io_then_sequences_two_actions() -> None:
    result, stdout, stderr = run_io("(IO-THEN (UART-TX 72) (UART-TX 105))")

    assert result == "NIL"
    assert stdout == "Hi"
    assert stderr == ""


def test_leds_write_diagnostic_to_stderr() -> None:
    result, stdout, stderr = run_io("(LEDS 255)")

    assert result == "NIL"
    assert stdout == ""
    assert stderr == "leds: 255\n"


def test_io_actions_can_be_named_by_top_level_definition() -> None:
    result, stdout, stderr = run_io(
        """
        bang == (UART-TX 33)
        (IO-THEN bang bang)
        """
    )

    assert result == "NIL"
    assert stdout == "!!"
    assert stderr == ""


def test_alphanumerics_fixture_prints_digits_letters_and_newline() -> None:
    source = Path("examples/uart-alphanumerics.thor").read_text()

    result, stdout, stderr = run_io(source)

    assert result == "NIL"
    assert stdout == "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz\n"
    assert stderr == ""

    red2_result, red2_stdout, red2_stderr = run_io(source, model="red2")
    assert red2_result == result
    assert red2_stdout == stdout
    assert red2_stderr == stderr


def test_caesar_fixture_rotates_letters_until_escape() -> None:
    source = Path("examples/uart-caesar-plus4.thor").read_text()

    result, stdout, stderr = run_io(source, stdin_text="ABYZabyz-09\x1bignored")

    assert result == "NIL"
    assert stdout == "EFCDefcd-09"
    assert stderr == ""

    red2_result, red2_stdout, red2_stderr = run_io(
        source,
        stdin_text="ABYZabyz-09\x1bignored",
        model="red2",
    )
    assert red2_result == result
    assert red2_stdout == stdout
    assert red2_stderr == stderr


def run_breakout_source_for_test(
    source: str,
    stdin_text: str,
    clock: FixedClock | AdvancingClock | None = None,
) -> tuple[str, str]:
    stdout = StringIO()
    stderr = StringIO()
    result = run_io_source(
        source,
        model="thor",
        quantum=12000,
        stdin=StringIO(stdin_text),
        stdout=stdout,
        stderr=stderr,
        clock=clock or FixedClock(1_700_000_000_000),
    )
    assert result == "NIL"
    return stdout.getvalue(), stderr.getvalue()


def run_breakout_for_test(
    stdin_text: str,
    clock: FixedClock | AdvancingClock | None = None,
) -> tuple[str, str]:
    return run_breakout_source_for_test(
        Path("examples/breakout.thor").read_text(), stdin_text, clock
    )


def test_breakout_initial_frame_uses_ansi_and_fixed_board() -> None:
    stdout, stderr = run_breakout_for_test("q")

    assert stdout.startswith("\x1b[?25l\x1b[2J\x1b[H")
    assert "BREAKOUT 20x12" in stdout
    assert "ARROWS MOVE; Q QUITS\nSCORE: 0  LIVES: 3\n" in stdout
    assert "PADDLE:" not in stdout
    assert "####################" in stdout
    assert "\x1b[?25hQUIT" in stdout
    assert stderr == ""


def test_breakout_clock_ticks_keep_ball_visible_at_later_positions() -> None:
    stdout, _ = run_breakout_for_test(
        "  q",
        clock=AdvancingClock(start=1_700_000_000_000, step=500),
    )

    assert stdout.count("o") >= 3
    assert "\x1b[11;12Ho" in stdout
    assert "\x1b[10;13Ho" in stdout


def test_breakout_bricks_do_not_all_disappear_after_first_tick() -> None:
    stdout, _ = run_breakout_for_test(" q", clock=FixedClock(1_700_000_000_200))

    assert "===============" in stdout
    assert "SCORE: 1" not in stdout


def test_breakout_source_renders_ball_with_cursor_addressing() -> None:
    breakout = Path("examples/breakout.thor").read_text()

    assert "emit-ball-at" in breakout
    assert "emit-cursor" in breakout
    assert "emit-ball-row-10" not in breakout
    assert "emit-ball-row-11" not in breakout


def test_breakout_initial_render_uses_ball_and_paddle_state() -> None:
    source = Path("examples/breakout.thor").read_text().replace(
        "(IO-BIND (CLOCK)\n"
        "  (LAMBDA (start-ms)\n"
        "    (IO-THEN emit-hide-cursor\n"
        "      (IO-THEN (render-initial 0 3 8 10 8)\n"
        "        (loop 0 3 8 10 8 1 -1 start-ms "
        "TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE)))))",
        "(IO-THEN (render-initial 0 3 3 4 5) (IO-RETURN NIL))",
    )

    stdout, _ = run_breakout_source_for_test(source, "")

    assert "\x1b[9;5Ho" in stdout
    assert "\x1b[14;1H#  _____           #" in stdout


def test_breakout_paddle_dx_uses_left_center_right_segments() -> None:
    program = normalize_program(
        parse_program(Path("examples/breakout.thor").read_text())
    )
    definitions = {
        form.name: form.expr for form in program.forms if isinstance(form, Definition)
    }

    def reduce_source(expr: str) -> str:
        parsed_expr = parse_program(expr).forms[0]
        assert isinstance(parsed_expr, Expr)
        return to_source(
            reduce_expr(parsed_expr, quantum=200, definitions=definitions).expr
        )

    assert reduce_source("(paddle-dx 8 8)") == "-1"
    assert reduce_source("(paddle-dx 10 8)") == "0"
    assert reduce_source("(paddle-dx 12 8)") == "1"

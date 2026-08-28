from __future__ import annotations

from io import StringIO
from pathlib import Path

from thor_spec.ast import Definition
from thor_spec.golden import ModelName
from thor_spec.io_runtime import LatestFileClockSource, run_io_source
from thor_spec.normalization import normalize_program
from thor_spec.parser import parse_program
from thor_spec.pretty import to_source
from thor_spec.semantics import reduce_expr


class FixedClock:
    def __init__(self, value: int) -> None:
        self.value = value

    def now_ms(self) -> int:
        return self.value


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


def test_hangman_fixture_ignores_newlines_and_wins() -> None:
    source = Path("examples/hangman.thor").read_text()

    result, stdout, stderr = run_io(source, stdin_text="A\nS\nG\nR\nD\n", quantum=2000)

    assert result == "NIL"
    assert "GUESS LETTERS; ESC QUITS\n" in stdout
    assert "WORD: ASGARD\n" in stdout
    assert "GUESSED:\n" in stdout
    assert "HIT\n" not in stdout
    assert "MISS\n" not in stdout
    assert "LOSE\n" not in stdout
    assert "WIN\n" in stdout
    assert stderr == ""

    red2_result, red2_stdout, red2_stderr = run_io(
        source,
        stdin_text="A\nS\nG\nR\nD\n",
        model="red2",
        quantum=2000,
    )
    assert red2_result == result
    assert "WORD: ASGARD\n" in red2_stdout
    assert "GUESSED:\n" in red2_stdout
    assert "HIT\n" not in red2_stdout
    assert "MISS\n" not in red2_stdout
    assert "LOSE\n" not in red2_stdout
    assert "WIN\n" in red2_stdout
    assert red2_stderr == stderr


def test_hangman_fixture_tracks_only_wrong_guesses_without_losing() -> None:
    source = Path("examples/hangman.thor").read_text()

    result, stdout, stderr = run_io(
        source,
        stdin_text="x\ny\nz\nA\nS\nG\nR\nD\n",
        quantum=2000,
    )

    assert result == "NIL"
    assert "GUESSED: XYZ\n" in stdout
    assert "GUESSED: XYZASGRD" not in stdout
    assert "LOSE\n" not in stdout
    assert "WIN\n" in stdout
    assert stderr == ""

    red2_result, red2_stdout, red2_stderr = run_io(
        source,
        stdin_text="x\ny\nz\nA\nS\nG\nR\nD\n",
        model="red2",
        quantum=2000,
    )
    assert red2_result == result
    assert "GUESSED: XYZ\n" in red2_stdout
    assert "GUESSED: XYZASGRD" not in red2_stdout
    assert "LOSE\n" not in red2_stdout
    assert "WIN\n" in red2_stdout
    assert red2_stderr == stderr


def run_breakout_source_for_test(
    source: str,
    stdin_text: str,
    clock_value: int = 1_700_000_000_000,
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
        clock=FixedClock(clock_value),
    )
    assert result == "NIL"
    return stdout.getvalue(), stderr.getvalue()


def run_breakout_for_test(
    stdin_text: str,
    clock_value: int = 1_700_000_000_000,
) -> tuple[str, str]:
    return run_breakout_source_for_test(
        Path("examples/breakout.thor").read_text(), stdin_text, clock_value
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


def test_breakout_arrow_keys_move_paddle() -> None:
    left_stdout, _ = run_breakout_for_test("\x1b[Dq")
    right_stdout, _ = run_breakout_for_test("\x1b[Cq")

    assert "#      _____       #" in left_stdout
    assert "#        _____     #" in right_stdout


def test_breakout_clock_ticks_keep_ball_visible_at_later_positions() -> None:
    stdout, _ = run_breakout_for_test("     q", clock_value=1_700_000_000_500)

    assert stdout.count("o") >= 3
    assert "\x1b[11;12Ho" in stdout
    assert "\x1b[10;13Ho" in stdout


def test_breakout_bricks_do_not_all_disappear_after_first_tick() -> None:
    stdout, _ = run_breakout_for_test(" q", clock_value=1_700_000_000_200)

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
        "(IO-THEN emit-hide-cursor\n"
        "  (IO-THEN (render-initial 0 3 8 10 8)\n"
        "    (loop 0 3 8 10 8 1 -1 START-MS "
        "TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE TRUE)))",
        "(IO-THEN (render-initial 0 3 3 4 5) (IO-RETURN NIL))",
    )

    stdout, _ = run_breakout_source_for_test(source, "")

    assert "\x1b[9;5Ho" in stdout
    assert "\x1b[14;1H#  _____           #" in stdout


def test_breakout_erases_a_brick_only_after_a_hit() -> None:
    stdout, _ = run_breakout_for_test("     q", clock_value=1_700_000_000_500)

    assert "\x1b[7;15H " in stdout
    assert "\x1b[7;16H " in stdout
    assert "\x1b[7;17H " in stdout
    assert "\x1b[7;14H " not in stdout
    assert "\x1b[3;8H1 " in stdout


def test_breakout_paddle_dx_uses_left_center_right_segments() -> None:
    program = normalize_program(
        parse_program(Path("examples/breakout.thor").read_text())
    )
    definitions = {
        form.name: form.expr for form in program.forms if isinstance(form, Definition)
    }

    def reduce_source(expr: str) -> str:
        return to_source(
            reduce_expr(
                parse_program(expr).forms[0], quantum=200, definitions=definitions
            ).expr
        )

    assert reduce_source("(paddle-dx 8 8)") == "-1"
    assert reduce_source("(paddle-dx 10 8)") == "0"
    assert reduce_source("(paddle-dx 12 8)") == "1"

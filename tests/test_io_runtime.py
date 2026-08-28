from __future__ import annotations

from io import StringIO
from pathlib import Path

from thor_spec.golden import ModelName
from thor_spec.io_runtime import run_io_source


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

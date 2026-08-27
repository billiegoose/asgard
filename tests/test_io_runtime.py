from __future__ import annotations

from io import StringIO

from thor_spec.io_runtime import run_io_source


def run_io(source: str, *, stdin_text: str = "") -> tuple[str, str, str]:
    stdin = StringIO(stdin_text)
    stdout = StringIO()
    stderr = StringIO()
    result = run_io_source(
        source,
        model="thor",
        quantum=100,
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

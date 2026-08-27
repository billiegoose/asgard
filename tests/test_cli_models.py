from __future__ import annotations

from io import StringIO

from pytest import CaptureFixture, MonkeyPatch

from thor_spec.cli import main


def test_cli_runs_thor_model_expr(capsys: CaptureFixture[str]) -> None:
    assert main(["--model", "thor", "--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out.strip() == "5"


def test_cli_runs_red2_model_expr(capsys: CaptureFixture[str]) -> None:
    assert main(["--model", "red2", "--quantum", "20", "--expr", "(+ 2 3)"]) == 0
    assert capsys.readouterr().out.strip() == "5"


def test_cli_parity_model_reports_matching_prefixes(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["--model", "parity", "--quantum", "3", "--expr", "(+ 2 3)"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "5\n"
    assert (
        "parity ok: 4 prefix snapshot(s) matched through quantum 3"
        in captured.err
    )


def test_cli_parity_model_reports_each_mismatch_range_and_final_match_exit_zero(
    capsys: CaptureFixture[str],
) -> None:
    source = """
    fib == (lambda (n)
      (letrec ((fib-iter
                (lambda (i current next)
                  (if (= i 0)
                      current
                      (fib-iter (1- i) next (+ current next))))))
        (fib-iter n 0 1)))
    fib-six == (fib 6)
    fib-six
    """

    assert main(["--model", "parity", "--quantum", "75", "--expr", source]) == 0
    captured = capsys.readouterr()
    assert captured.out == "(+ 3 (+ 2 (+ 1 2)))\n"
    assert "parity mismatch at quantum 3\n" in captured.err
    assert "parity reconverged at quantum 5\n" in captured.err
    assert "parity mismatch at quantum 8\n" in captured.err
    assert "parity reconverged at quantum 9\n" in captured.err
    assert "mismatch ranges:" not in captured.err
    assert "parity final quantum 75 matched" in captured.err
    assert captured.err.count("thor:") == 14
    assert captured.err.count("red2:") == 14


def test_cli_parity_model_exits_one_when_final_snapshot_mismatches(
    capsys: CaptureFixture[str],
) -> None:
    source = """
    fib == (lambda (n)
      (letrec ((fib-iter
                (lambda (i current next)
                  (if (= i 0)
                      current
                      (fib-iter (1- i) next (+ current next))))))
        (fib-iter n 0 1)))
    fib-six == (fib 6)
    fib-six
    """

    assert main(["--model", "parity", "--quantum", "3", "--expr", source]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "parity mismatch at quantum 3" in captured.err
    assert "parity did not reconverge by quantum 3" in captured.err
    assert "parity final quantum 3 mismatched" in captured.err


def test_cli_io_mode_uses_stdout_for_uart_and_stderr_for_result(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["--io", "--model", "thor", "--expr", "(UART-TX 65)"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "A"
    assert captured.err == "io result: NIL\n"


def test_cli_io_mode_reads_uart_from_stdin(
    capsys: CaptureFixture[str],
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("B"))

    assert main(
        [
            "--io",
            "--model",
            "red2",
            "--expr",
            "(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))",
        ]
    ) == 0
    captured = capsys.readouterr()
    assert captured.out == "B"
    assert captured.err == "io result: NIL\n"


def test_cli_io_mode_rejects_parity_model(capsys: CaptureFixture[str]) -> None:
    assert main(["--io", "--model", "parity", "--expr", "(UART-TX 65)"]) == 2
    captured = capsys.readouterr()
    assert "--io supports only --model thor or --model red2" in captured.err


def test_cli_parity_model_rejects_negative_quantum(
    capsys: CaptureFixture[str],
) -> None:
    assert main(["--model", "parity", "--quantum", "-1", "--expr", "(+ 2 3)"]) == 2
    captured = capsys.readouterr()
    assert "max_quantum must be non-negative" in captured.err

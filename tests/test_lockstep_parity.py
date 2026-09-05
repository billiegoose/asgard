from thor_engine.lockstep import compare_prefixes, format_mismatch_report


def test_compare_prefixes_reports_all_matching_snapshots() -> None:
    result = compare_prefixes("(+ 2 3)", max_quantum=3)

    assert result.max_quantum == 3
    assert [snapshot.quantum for snapshot in result.snapshots] == [0, 1, 2, 3]
    assert result.first_mismatch is None
    assert all(snapshot.matches for snapshot in result.snapshots)
    assert result.snapshots[-1].thor == "5"
    assert result.snapshots[-1].red2 == "5"


FIBONACCI_SOURCE = """
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


def test_compare_prefixes_matches_early_fibonacci_prefixes() -> None:
    result = compare_prefixes(FIBONACCI_SOURCE, max_quantum=3)

    assert result.first_mismatch is None
    assert all(snapshot.matches for snapshot in result.snapshots)
    assert result.snapshots[3].thor == result.snapshots[3].red2


def test_compare_prefixes_reports_partial_fibonacci_shape_mismatch() -> None:
    result = compare_prefixes(FIBONACCI_SOURCE, max_quantum=75)

    assert result.first_mismatch is result.snapshots[4]
    assert result.mismatch_ranges[0] == (4, 6)
    assert (65, 65) in result.mismatch_ranges
    assert result.first_reconvergence is result.snapshots[7]
    assert result.final_snapshot is result.snapshots[75]
    assert result.final_snapshot.matches
    assert result.snapshots[75].thor == "(+ 3 (+ 2 (+ 1 2)))"
    assert result.snapshots[75].red2 == "(+ 3 (+ 2 (+ 1 2)))"


def test_format_mismatch_report_includes_ranges_and_reconvergence() -> None:
    result = compare_prefixes(FIBONACCI_SOURCE, max_quantum=75)

    report = format_mismatch_report(result)

    assert "parity mismatch at quantum 4" in report
    assert "thor: ((LAMBDA (i current next)" in report
    assert "red2: " in report
    assert "parity reconverged at quantum 7" in report
    assert "parity mismatch at quantum 65" in report

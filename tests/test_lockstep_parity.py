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

    assert result.first_mismatch is result.snapshots[8]
    assert result.mismatch_ranges == ((8, 8), (14, 75))
    assert result.first_reconvergence is result.snapshots[9]
    assert result.final_snapshot is result.snapshots[75]
    assert not result.final_snapshot.matches
    assert result.snapshots[75].thor == "(+ 3 (+ 2 (+ 1 2)))"
    assert result.snapshots[75].red2 == "8"


def test_lazy_control_corpus_preserves_expected_contraction_prefixes() -> None:
    cases = [
        ("(IF TRUE (+ 1 2) (BAD BAD))", (), "3"),
        ("(IF FALSE (BAD BAD) (+ 4 5))", (), "9"),
        # RED2 lowers AND/OR to IF before execution, so q=0 exposes that
        # compile-time representation difference.  From the first contraction
        # onward the Chapter 3 prefix oracle and RED2 agree.
        ("(AND FALSE (BAD BAD))", ((0, 0),), "FALSE"),
        ("(OR TRUE (BAD BAD))", ((0, 0),), "TRUE"),
        ("(Y (LAMBDA (self) 7))", (), "7"),
    ]

    for source, mismatch_ranges, expected in cases:
        result = compare_prefixes(source, max_quantum=20)

        assert result.mismatch_ranges == mismatch_ranges, source
        assert result.final_snapshot is not None
        assert result.final_snapshot.thor == expected
        assert result.final_snapshot.red2 == expected


def test_format_mismatch_report_includes_ranges_and_reconvergence() -> None:
    result = compare_prefixes(FIBONACCI_SOURCE, max_quantum=75)

    report = format_mismatch_report(result)

    assert "parity mismatch at quantum 8" in report
    assert "thor: (IF FALSE current" in report
    assert "red2: " in report
    assert "parity reconverged at quantum 9" in report
    assert "parity mismatch at quantum 14" in report
    assert "parity did not reconverge by quantum 75" in report


def test_structural_equality_preserves_public_contraction_prefixes() -> None:
    sources = [
        "(EQUAL? (F 1) (F 1))",
        "(EQUAL? (F 1) (F 2))",
        "(EQUAL? (F 1 2) (F 1 2))",
        "(EQUAL? (F 1 2) (F 1 3))",
        "(EQUAL? (LAMBDA (x) (F x)) (LAMBDA (y) (F y)))",
    ]

    for source in sources:
        result = compare_prefixes(source, max_quantum=5)
        assert result.mismatch_ranges == (), source
        assert all(snapshot.matches for snapshot in result.snapshots), source

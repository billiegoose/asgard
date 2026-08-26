from thor_spec.lockstep import compare_prefixes


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


def test_compare_prefixes_alpha_normalizes_red2_var_rendering() -> None:
    result = compare_prefixes(FIBONACCI_SOURCE, max_quantum=2)

    assert result.first_mismatch is None
    assert result.snapshots[2].thor != result.snapshots[2].red2
    assert result.snapshots[2].matches


def test_compare_prefixes_reports_partial_fibonacci_shape_mismatch() -> None:
    result = compare_prefixes(FIBONACCI_SOURCE, max_quantum=75)

    assert result.first_mismatch is result.snapshots[3]
    assert result.snapshots[75].thor == "(+ 3 (+ 2 (+ 1 2)))"
    assert result.snapshots[75].red2 == "(+ 3 (+ 2 (+ 1 2)))"

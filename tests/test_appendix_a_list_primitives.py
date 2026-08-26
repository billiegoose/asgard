import pytest

from thor_spec.golden import run_source


def assert_parity(source: str, expected: str, quantum: int = 80) -> None:
    assert run_source(source, model="thor", quantum=quantum) == expected
    assert run_source(source, model="red2", quantum=quantum) == expected


def test_cons_car_cdr_null_match_on_pair_lists() -> None:
    assert_parity("(cons 1 [2 3])", "[1 2 3]")
    assert_parity("(car (cons 1 [2 3]))", "1")
    assert_parity("(cdr (cons 1 [2 3]))", "[2 3]")
    assert_parity("(null? [])", "TRUE")
    assert_parity("(null? [1])", "FALSE")
    assert_parity("(null? FOO)", "FALSE")
    assert_parity("(null? (foo x))", "(NULL? (foo x))")


@pytest.mark.xfail(
    strict=True,
    reason="Deferred to Task 5: RED2 recursive top-level definitions are required.",
)
def test_append_operator_can_be_defined_from_reduce_and_cons() -> None:
    source = """
    reduce == (lambda (f id list)
      (if (null? list) id (f (car list) (reduce f id (cdr list)))))
    ++ == (lambda (a b) (reduce cons b a))
    (++ [1 2] [3 4])
    """
    assert_parity(source, "[1 2 3 4]", quantum=200)

import sys

from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source
from thor_spec.semantics import reduce_expr


def test_y_operator_retains_identity_under_small_quantum() -> None:
    expr = parse_expr("((Y (LAMBDA (FACT N) (IF (= N 0) 1 (* N (FACT (1- N)))))) 3)")
    result = reduce_expr(expr, quantum=2)
    assert "Y" in to_source(result.expr)
    assert "FACT" in to_source(result.expr)


def test_letrec_infinite_pair_prefix_reconstructs_when_quantum_expires() -> None:
    expr = parse_expr("(LETREC ((x [1 | y]) (y [2 | x])) x)")
    result = reduce_expr(expr, quantum=1)
    assert to_source(result.expr) == "[1 | (LETREC ((x [1 | y]) (y [2 | x])) y)]"


def test_deep_y_recursion_does_not_consume_python_stack() -> None:
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        expr = parse_expr(
            "((Y (LAMBDA (loop) (LAMBDA (n) "
            "(if (= n 0) 0 (loop (1- n)))))) 250)"
        )
        result = reduce_expr(expr, quantum=2000)
    finally:
        sys.setrecursionlimit(previous_limit)

    assert to_source(result.expr) == "0"


def test_infinite_y_prefix_exhausts_quantum_not_python_stack() -> None:
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        expr = parse_expr("((Y (LAMBDA (loop) (LAMBDA (n) (loop n)))) 1)")
        result = reduce_expr(expr, quantum=500)
    finally:
        sys.setrecursionlimit(previous_limit)

    rendered = to_source(result.expr)
    assert "Y" in rendered
    assert result.remaining == 0

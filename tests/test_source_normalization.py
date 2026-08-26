from thor_spec.ast import App, Integer, Lambda, Symbol
from thor_spec.normalization import normalize_expr
from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source


def test_lowercase_special_forms_normalize_to_core_names() -> None:
    expr = normalize_expr(
        parse_expr("(lambda (x) (if (or (null? x) false) nil (car x)))")
    )
    assert to_source(expr) == "(LAMBDA (x) (IF (OR (NULL? x) FALSE) NIL (CAR x)))"


def test_let_desugars_to_lambda_application() -> None:
    expr = normalize_expr(parse_expr("(let ((x 2) (y 3)) (+ x y))"))
    assert expr == App(
        (
            Lambda(("x", "y"), App((Symbol("+"), Symbol("x"), Symbol("y")))),
            Integer(2),
            Integer(3),
        )
    )


def test_nested_letrec_is_preserved_but_normalized() -> None:
    expr = normalize_expr(parse_expr("(letrec ((f (lambda (n) n))) (f 1))"))
    assert to_source(expr) == "(LETREC ((f (LAMBDA (n) n))) (f 1))"

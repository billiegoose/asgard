from thor_engine.semantics import reduce_expr, translate
from thor_lang.ast import App, Integer, Lambda, Symbol, Var
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def test_translation_converts_bound_symbols_to_debruijn_vars() -> None:
    expr = translate(parse_expr("(LAMBDA (X Y) X Y)"))
    assert expr == Lambda(("X", "Y"), App((Var(0, "X"), Var(1, "Y"))))


def test_beta_reduction_substitutes_argument_through_closure() -> None:
    result = reduce_expr(parse_expr("((LAMBDA (X) X) 42)"), quantum=10)
    assert result.expr == Integer(42)
    assert result.remaining == 9
    assert result.steps == 1


def test_normal_order_reduces_operator_before_operand() -> None:
    result = reduce_expr(
        parse_expr("(((LAMBDA (X) (LAMBDA (Y) X)) 7) (BAD BAD))"),
        quantum=3,
    )
    assert to_source(result.expr) == "7"


def test_exhausted_quantum_preserves_application_shape() -> None:
    result = reduce_expr(parse_expr("((LAMBDA (X) X) 42)"), quantum=0)
    assert to_source(result.expr) == "((LAMBDA (X) X) 42)"
    assert result.remaining == 0


def test_symbol_definition_costs_one_contraction() -> None:
    result = reduce_expr(
        Symbol("ANSWER"), quantum=2, definitions={"ANSWER": Integer(42)}
    )
    assert result.expr == Integer(42)
    assert result.remaining == 1

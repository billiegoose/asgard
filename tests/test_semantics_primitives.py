from thor_spec.ast import Expr, Integer
from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source
from thor_spec.primitives import install_struct_accessors
from thor_spec.semantics import reduce_expr


def reduced(source: str, quantum: int = 20) -> str:
    return to_source(reduce_expr(parse_expr(source), quantum=quantum).expr)


def test_integer_arithmetic_and_predicates() -> None:
    assert reduced("(+ 2 3)") == "5"
    assert reduced("(1- 5)") == "4"
    assert reduced("(= 5 5)") == "TRUE"
    assert reduced("(INTEGER? 5)") == "TRUE"
    assert reduced("(INTEGER? (LAMBDA (X) X))") == "FALSE"


def test_type_predicate_keeps_irreducible_application() -> None:
    assert reduced("(INTEGER? (FOO X))") == "(INTEGER? (FOO X))"


def test_structure_is_lazy_but_accessor_reduces_component() -> None:
    defs: dict[str, Expr] = {}
    install_struct_accessors("PAIR", ("CAR", "CDR"), defs)
    expr = parse_expr("(CAR {PAIR (+ 2 3) (BAD BAD)})")
    assert reduce_expr(expr, quantum=20, definitions=defs).expr == Integer(5)


def test_if_reduces_only_selected_branch() -> None:
    assert reduced("(IF TRUE (+ 1 2) (BAD BAD))") == "3"
    assert reduced("(IF FALSE (BAD BAD) (+ 4 5))") == "9"
    assert reduced("(IF (FOO X) (+ 1 2) (+ 3 4))") == "(IF (FOO X) (+ 1 2) (+ 3 4))"

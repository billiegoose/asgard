from thor_spec.ast import (
    App,
    Binding,
    Integer,
    LetRec,
    StructDef,
    StructLit,
    Symbol,
)
from thor_spec.parser import parse_expr, parse_program
from thor_spec.pretty import to_source


def test_lambda_application_round_trips() -> None:
    expr = parse_expr("((LAMBDA (X Y) X) 1 2)")
    assert isinstance(expr, App)
    assert to_source(expr) == "((LAMBDA (X Y) X) 1 2)"


def test_list_sugar_parses_to_pair_structure() -> None:
    expr = parse_expr("[1 2]")
    assert expr == StructLit(
        "PAIR", (Integer(1), StructLit("PAIR", (Integer(2), Symbol("NIL"))))
    )
    assert to_source(expr) == "[1 2]"


def test_dotted_pair_sugar_parses_to_pair_structure() -> None:
    expr = parse_expr("[1 | X]")
    assert expr == StructLit("PAIR", (Integer(1), Symbol("X")))
    assert to_source(expr) == "[1 | X]"


def test_letrec_and_top_level_forms_parse() -> None:
    program = parse_program(
        """
        PAIR |= CAR CDR
        fact == (LAMBDA (N) (IF (= N 0) 1 (* N (fact (1- N)))))
        (LETREC ((x [1 | y]) (y [2 | x])) x)
        """
    )
    assert isinstance(program.forms[0], StructDef)
    assert program.forms[0].tag == "PAIR"
    expr = program.forms[2]
    assert isinstance(expr, LetRec)
    assert expr.bindings[0] == Binding(
        "x", StructLit("PAIR", (Integer(1), Symbol("y")))
    )

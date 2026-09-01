from thor_engine.golden import run_source
from thor_lang.ast import Char
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def assert_model_parity(source: str, expected: str, quantum: int = 50) -> None:
    assert run_source(source, model="thor", quantum=quantum) == expected
    assert run_source(source, model="red2", quantum=quantum) == expected


def test_character_constant_parses_and_prints() -> None:
    expr = parse_expr("#\\a")
    assert expr == Char("a")
    assert to_source(expr) == "#\\a"


def test_character_and_symbol_predicates_match_between_models() -> None:
    assert_model_parity("(CHAR? #\\a)", "TRUE")
    assert_model_parity("(SYMBOL? FOO)", "TRUE")


def test_character_equality_matches_between_models() -> None:
    assert_model_parity("(EQUAL? #\\a #\\a)", "TRUE")

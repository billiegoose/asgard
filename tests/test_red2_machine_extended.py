from red2_engine.machine import Red2Machine
from red2_engine.primitives import instructions_to_expr
from thor_compile.red2 import compile_expr
from thor_engine.semantics import reduce_expr
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def run_red2(source: str, quantum: int = 30) -> str:
    machine = Red2Machine(compile_expr(parse_expr(source)), quantum=quantum)
    machine.run()
    return to_source(instructions_to_expr(machine.result_instructions()))


def test_red2_addition_matches_thor_reference() -> None:
    assert run_red2("(+ 2 3)") == "5"
    assert run_red2("(+ 2 3)") == to_source(
        reduce_expr(parse_expr("(+ 2 3)"), quantum=30).expr
    )


def test_red2_if_does_not_reduce_unselected_branch() -> None:
    assert run_red2("(IF TRUE (+ 1 2) (BAD BAD))") == "3"


def test_red2_pair_accessor_matches_thor_reference() -> None:
    assert run_red2("(CAR {PAIR (+ 2 3) (BAD BAD)})") == "5"


def test_red2_letrec_prefix_matches_thor_reference() -> None:
    source = "(LETREC ((x [1 | y]) (y [2 | x])) x)"
    assert run_red2(source, quantum=1) == to_source(
        reduce_expr(parse_expr(source), quantum=1).expr
    )

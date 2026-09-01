import pytest

from red2_engine.mured import MuredMachine, MuredOpcode, Word, compile_lambda
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def test_compile_lambda_uses_linear_body_and_operator_layout() -> None:
    assert compile_lambda(parse_expr("(LAMBDA (x) x)")) == (
        Word(MuredOpcode.LAMBDA, "x"),
        Word(MuredOpcode.VAR, 0),
    )
    assert compile_lambda(parse_expr("((LAMBDA (x) x) (LAMBDA (y) y))")) == (
        Word(MuredOpcode.APP, 3),
        Word(MuredOpcode.LAMBDA, "x"),
        Word(MuredOpcode.VAR, 0),
        Word(MuredOpcode.LAMBDA, "y"),
        Word(MuredOpcode.VAR, 0),
    )


def test_compile_lambda_rejects_non_lambda_calculus_values() -> None:
    with pytest.raises(TypeError, match="pure λ-calculus expression required"):
        compile_lambda(parse_expr("42"))


def test_identity_application_runs_and_decompiles_after_halt() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("((LAMBDA (x) x) (LAMBDA (y) y))"),
        quantum=10,
        memory_words=64,
    )
    machine.run()

    assert machine.state.halted is True
    assert machine.state.q == 9
    assert to_source(machine.result_expr()) == "(LAMBDA (y) y)"


def test_result_expr_requires_halt() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("(LAMBDA (x) x)"),
        quantum=10,
    )
    with pytest.raises(RuntimeError, match="result is available only after halt"):
        machine.result_expr()

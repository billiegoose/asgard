import pytest

from red2_engine.mured import MuredMachine, MuredOpcode, Word, compile_lambda
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def test_compile_lambda_uses_linear_body_and_operator_layout() -> None:
    assert compile_lambda(parse_expr("(LAMBDA (x) x)")) == (
        Word(MuredOpcode.LAMBDA, "x", False),
        Word(MuredOpcode.VAR, 0, True),
    )
    assert compile_lambda(parse_expr("((LAMBDA (x) x) (LAMBDA (y) y))")) == (
        Word(MuredOpcode.APP, 3, False),
        Word(MuredOpcode.LAMBDA, "x", False),
        Word(MuredOpcode.VAR, 0, True),
        Word(MuredOpcode.LAMBDA, "y", False),
        Word(MuredOpcode.VAR, 0, True),
    )


@pytest.mark.parametrize(
    ("source", "variable_index"),
    [
        ("(LAMBDA (x y) x)", 1),
        ("(LAMBDA (x y) y)", 0),
    ],
)
def test_compile_grouped_lambda_uses_nearest_de_bruijn_binder(
    source: str,
    variable_index: int,
) -> None:
    assert compile_lambda(parse_expr(source)) == (
        Word(MuredOpcode.LAMBDA, "x", False),
        Word(MuredOpcode.LAMBDA, "y", False),
        Word(MuredOpcode.VAR, variable_index, True),
    )


def test_compile_lambda_inlines_single_variable_application_argument() -> None:
    assert compile_lambda(parse_expr("(LAMBDA (f x) (f x))")) == (
        Word(MuredOpcode.LAMBDA, "f", False),
        Word(MuredOpcode.LAMBDA, "x", False),
        Word(MuredOpcode.APP_VAR, 0, False),
        Word(MuredOpcode.VAR, 1, True),
    )


def test_compile_flat_application_emits_outermost_argument_first() -> None:
    source = "((LAMBDA (x) x) (LAMBDA (a) a) (LAMBDA (b) b))"

    assert compile_lambda(parse_expr(source)) == (
        Word(MuredOpcode.APP, 4, False),
        Word(MuredOpcode.APP, 6, False),
        Word(MuredOpcode.LAMBDA, "x", False),
        Word(MuredOpcode.VAR, 0, True),
        Word(MuredOpcode.LAMBDA, "b", False),
        Word(MuredOpcode.VAR, 0, True),
        Word(MuredOpcode.LAMBDA, "a", False),
        Word(MuredOpcode.VAR, 0, True),
    )


@pytest.mark.parametrize(
    ("source", "compiled", "expected_source"),
    [
        (
            "42",
            (Word(MuredOpcode.INT, 42, True),),
            "42",
        ),
        (
            "(LAMBDA (x) 42)",
            (
                Word(MuredOpcode.LAMBDA, "x", False),
                Word(MuredOpcode.INT, 42, True),
            ),
            "(LAMBDA (x) 42)",
        ),
        (
            "((LAMBDA (x) x) 42)",
            (
                Word(MuredOpcode.APP, 3, False),
                Word(MuredOpcode.LAMBDA, "x", False),
                Word(MuredOpcode.VAR, 0, True),
                Word(MuredOpcode.INT, 42, True),
            ),
            "42",
        ),
    ],
)
def test_compile_lambda_emits_integer_literals_and_results(
    source: str,
    compiled: tuple[Word, ...],
    expected_source: str,
) -> None:
    assert compile_lambda(parse_expr(source)) == compiled

    machine = MuredMachine.from_expr(
        parse_expr(source),
        quantum=10,
        memory_words=64,
    )
    machine.run()

    assert machine.state.halted is True
    assert to_source(machine.result_expr()) == expected_source


@pytest.mark.parametrize(
    ("source", "compiled"),
    [
        ("1.5", (Word(MuredOpcode.FLOAT, 1.5, True),)),
        ("#\\a", (Word(MuredOpcode.CHAR, "a", True),)),
    ],
)
def test_compile_lambda_emits_float_and_char_literals(
    source: str,
    compiled: tuple[Word, ...],
) -> None:
    assert compile_lambda(parse_expr(source)) == compiled


def test_compile_lambda_emits_headed_float_and_char_results() -> None:
    assert compile_lambda(parse_expr("(LAMBDA (x) 1.5)"))[-1] == Word(
        MuredOpcode.FLOAT,
        1.5,
        True,
    )
    assert compile_lambda(parse_expr("(LAMBDA (x) #\\space)"))[-1] == Word(
        MuredOpcode.CHAR,
        " ",
        True,
    )


def test_decompile_application_spine_restores_source_argument_order() -> None:
    machine = MuredMachine.load(
        (
            Word(MuredOpcode.APP, 4, False),
            Word(MuredOpcode.APP, 6, False),
            Word(MuredOpcode.LAMBDA, "x", False),
            Word(MuredOpcode.VAR, 0, True),
            Word(MuredOpcode.LAMBDA, "b", False),
            Word(MuredOpcode.VAR, 0, True),
            Word(MuredOpcode.LAMBDA, "a", False),
            Word(MuredOpcode.VAR, 0, True),
        ),
        quantum=0,
    )

    machine.run()

    assert to_source(machine.result_expr()) == (
        "((LAMBDA (x) x) (LAMBDA (a) a) (LAMBDA (b) b))"
    )


def test_decompile_application_spine_restores_inline_variable_arguments() -> None:
    machine = MuredMachine.load(
        (
            Word(MuredOpcode.LAMBDA, "f", False),
            Word(MuredOpcode.LAMBDA, "x", False),
            Word(MuredOpcode.APP_VAR, 0, False),
            Word(MuredOpcode.VAR, 1, True),
        ),
        quantum=0,
    )
    machine.state.halted = True

    assert to_source(machine.result_expr()) == "(LAMBDA (f x) (f x))"


def test_compile_lambda_emits_free_symbols_as_sym_words() -> None:
    assert compile_lambda(parse_expr("FOO")) == (
        Word(MuredOpcode.SYM, "FOO", True),
    )
    assert compile_lambda(parse_expr("(LAMBDA (x) FOO)"))[-1] == Word(
        MuredOpcode.SYM,
        "FOO",
        True,
    )
    assert compile_lambda(parse_expr("(LAMBDA (x) x)"))[-1] == Word(
        MuredOpcode.VAR,
        0,
        True,
    )
    assert any(
        word.opcode is MuredOpcode.APP_VAR
        for word in compile_lambda(parse_expr("(LAMBDA (f x) (f x))"))
    )


def test_mured_machine_loads_integer_words_and_decompiles_them() -> None:
    machine = MuredMachine.load((Word(MuredOpcode.INT, 42, True),), quantum=10)
    machine.run()

    assert machine.state.halted is True
    assert machine.state.memory[2] == Word(MuredOpcode.INT, 42, True)
    assert to_source(machine.result_expr()) == "42"


@pytest.mark.parametrize(
    ("word", "expected_source"),
    [
        (Word(MuredOpcode.FLOAT, 1.5, True), "1.5"),
        (Word(MuredOpcode.CHAR, " ", True), "#\\space"),
    ],
)
def test_mured_machine_loads_float_and_char_words_and_decompiles_them(
    word: Word,
    expected_source: str,
) -> None:
    machine = MuredMachine.load((word,), quantum=10)
    machine.run()

    assert machine.state.halted is True
    assert machine.state.memory[2] == word
    assert to_source(machine.result_expr()) == expected_source


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

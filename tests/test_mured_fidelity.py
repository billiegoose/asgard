from collections.abc import Sequence
from pathlib import Path

import pytest

from red2_engine.mured import (
    Direction,
    MuredMachine,
    MuredOpcode,
    Word,
    compile_lambda,
)
from thor_engine.semantics import reduce_expr
from thor_lang.ast import App, Expr, Lambda
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def group_consecutive_lambdas(expr: Expr) -> Expr:
    if isinstance(expr, App):
        return App(tuple(group_consecutive_lambdas(item) for item in expr.items))
    if not isinstance(expr, Lambda):
        return expr

    params = list(expr.params)
    body = group_consecutive_lambdas(expr.body)
    while isinstance(body, Lambda):
        params.extend(body.params)
        body = body.body
    return Lambda(tuple(params), body)


def snapshot(machine: MuredMachine) -> tuple[object, ...]:
    state = machine.state
    word = state.memory[state.pc]
    assert word is not None
    return (
        state.cycles,
        word.opcode,
        state.direction,
        state.pc,
        state.fsp,
        state.env,
        state.c,
        state.q,
        state.phi,
    )


def dense_words(
    memory: list[Word | None], start: int, stop: int
) -> tuple[tuple[int, Word], ...]:
    items: list[tuple[int, Word]] = []
    for address in range(start, stop):
        word = memory[address]
        if word is not None:
            items.append((address, word))
    return tuple(items)


def load_defined_symbol_machine(
    symbol_source: str,
    definition_source: str,
    *,
    quantum: int,
    memory_words: int = 64,
    definition_address: int = 8,
) -> MuredMachine:
    def relocate_definition(words: tuple[Word, ...]) -> tuple[Word, ...]:
        relocated: list[Word] = []
        for word in words:
            data = word.data
            if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR}:
                assert isinstance(data, int)
                data = data + definition_address
            relocated.append(Word(word.opcode, data, word.head, word.definition))
        return tuple(relocated)

    machine = MuredMachine.load(
        compile_lambda(parse_expr(symbol_source)),
        quantum=quantum,
        memory_words=memory_words,
    )
    definition = relocate_definition(
        compile_lambda(parse_expr(definition_source))
    )
    for offset, word in enumerate(definition):
        machine.state.memory[definition_address + offset] = word
    machine.state.memory[definition_address + len(definition)] = Word(
        MuredOpcode.STOP
    )
    root = machine.state.memory[0]
    assert root is not None
    machine.state.memory[0] = Word(
        root.opcode,
        root.data,
        True,
        definition_address,
    )
    return machine


def test_defined_symbol_copy_does_not_supply_primitive_argument() -> None:
    machine = load_defined_symbol_machine("FOO", "NOT", quantum=3)

    machine.run()

    assert to_source(machine.result_expr()) == "NOT"
    assert machine.state.prim is None
    assert machine.state.fire == 0


def control_contents(
    control_stack: Sequence[object], c: int
) -> tuple[int, ...]:
    if c < 0:
        return ()
    items: list[int] = []
    for value in control_stack[: c + 1]:
        if type(value) is int:
            items.append(value)
    return tuple(items)


def detailed_snapshot(machine: MuredMachine) -> tuple[object, ...]:
    state = machine.state
    word = state.memory[state.pc]
    assert word is not None
    return (
        state.cycles,
        word.opcode,
        state.direction,
        state.pc,
        state.fsp,
        state.env,
        state.c,
        state.q,
        state.phi,
        dense_words(state.memory, 0, state.env),
        dense_words(state.memory, state.env, len(state.memory)),
        control_contents(state.control_stack, state.c),
    )


def test_closed_identity_matches_manual_chapter4_cycle_trace() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("(LAMBDA (x) x)"),
        quantum=10,
        memory_words=32,
        control_words=8,
    )
    trace: list[tuple[object, ...]] = []
    while not machine.state.halted:
        trace.append(snapshot(machine))
        machine.step()

    assert trace == [
        (0, MuredOpcode.LAMBDA, Direction.F, 0, 2, 32, -1, 10, 0),
        (1, MuredOpcode.VAR, Direction.F, 1, 3, 31, -1, 10, 1),
        (2, MuredOpcode.UBV, Direction.F, 31, 3, 31, -1, 10, 1),
        (3, MuredOpcode.LAMBDA, Direction.B, 3, 4, 31, -1, 10, 1),
        (4, MuredOpcode.STOP, Direction.B, 2, 4, 31, -1, 10, 0),
    ]
    assert machine.state.pc == 3
    assert to_source(machine.result_expr()) == "(LAMBDA (x) x)"


def test_top_level_integer_executes_int_then_stop_and_copies_head_flag() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("42"),
        quantum=10,
        memory_words=16,
        control_words=4,
    )
    trace: list[tuple[object, ...]] = []
    while not machine.state.halted:
        trace.append(snapshot(machine))
        machine.step()

    assert trace == [
        (0, MuredOpcode.INT, Direction.F, 0, 1, 16, -1, 10, 0),
        (1, MuredOpcode.STOP, Direction.B, 1, 2, 16, -1, 10, 0),
    ]
    assert machine.state.memory[2] == Word(MuredOpcode.INT, 42, True)
    assert machine.state.pc == 2
    assert to_source(machine.result_expr()) == "42"


def test_manual_chapter4_app_fwd_rev_join_parent_insertion_trace() -> None:
    lambda_f = Word(MuredOpcode.LAMBDA, "f")
    lambda_x = Word(MuredOpcode.LAMBDA, "x")
    app_var0 = Word(MuredOpcode.APP_VAR, 0, False)
    var1 = Word(MuredOpcode.VAR, 1, True)
    stop = Word(MuredOpcode.STOP)
    ubv1 = Word(MuredOpcode.UBV, 1)
    ubv2 = Word(MuredOpcode.UBV, 2)

    graph_0 = (
        (0, lambda_f),
        (1, lambda_x),
        (2, app_var0),
        (3, var1),
        (4, stop),
    )
    graph_1 = (*graph_0, (5, lambda_f))
    graph_2 = (*graph_1, (6, lambda_x))
    graph_3 = (*graph_2, (7, app_var0))
    graph_4 = (*graph_3, (8, var1))
    env_1 = ((15, ubv1),)
    env_2 = ((14, ubv2), (15, ubv1))

    machine = MuredMachine.from_expr(
        parse_expr("(LAMBDA (f x) (f x))"),
        quantum=10,
        memory_words=16,
        control_words=4,
    )
    trace: list[tuple[object, ...]] = []
    while not machine.state.halted:
        trace.append(detailed_snapshot(machine))
        machine.step()

    assert trace == [
        (
            0,
            MuredOpcode.LAMBDA,
            Direction.F,
            0,
            4,
            16,
            -1,
            10,
            0,
            graph_0,
            (),
            (),
        ),
        (
            1,
            MuredOpcode.LAMBDA,
            Direction.F,
            1,
            5,
            15,
            -1,
            10,
            1,
            graph_1,
            env_1,
            (),
        ),
        (
            2,
            MuredOpcode.APP_VAR,
            Direction.F,
            2,
            6,
            14,
            -1,
            10,
            2,
            graph_2,
            env_2,
            (),
        ),
        (
            3,
            MuredOpcode.VAR,
            Direction.F,
            3,
            7,
            14,
            -1,
            10,
            2,
            graph_3,
            env_2,
            (),
        ),
        (
            4,
            MuredOpcode.UBV,
            Direction.F,
            15,
            7,
            14,
            -1,
            10,
            2,
            graph_3,
            env_2,
            (),
        ),
        (
            5,
            MuredOpcode.APP_VAR,
            Direction.B,
            7,
            8,
            14,
            -1,
            10,
            2,
            graph_4,
            env_2,
            (),
        ),
        (
            6,
            MuredOpcode.LAMBDA,
            Direction.B,
            6,
            8,
            14,
            -1,
            10,
            2,
            graph_4,
            env_2,
            (),
        ),
        (
            7,
            MuredOpcode.LAMBDA,
            Direction.B,
            5,
            8,
            14,
            -1,
            10,
            1,
            graph_4,
            env_2,
            (),
        ),
        (
            8,
            MuredOpcode.STOP,
            Direction.B,
            4,
            8,
            14,
            -1,
            10,
            0,
            graph_4,
            env_2,
            (),
        ),
    ]
    assert machine.state.pc == 5
    assert to_source(machine.result_expr()) == "(LAMBDA (f x) (f x))"


def test_manual_chapter4_beta_closure_quantum_trace() -> None:
    app3 = Word(MuredOpcode.APP, 3)
    lambda_x = Word(MuredOpcode.LAMBDA, "x")
    lambda_y = Word(MuredOpcode.LAMBDA, "y")
    var0 = Word(MuredOpcode.VAR, 0, True)
    stop = Word(MuredOpcode.STOP)
    closure16 = Word(MuredOpcode.CLOSURE, 16)
    pnp16 = Word(MuredOpcode.PNP, 16)
    ubv1 = Word(MuredOpcode.UBV, 1)
    none3 = Word(None, 3)

    graph_0 = (
        (0, app3),
        (1, lambda_x),
        (2, var0),
        (3, lambda_y),
        (4, var0),
        (5, stop),
    )
    graph_1 = (*graph_0, (6, app3))
    graph_5 = (*graph_0, (6, lambda_y))
    graph_7 = (*graph_5, (7, var0))
    env_2 = ((14, closure16), (15, none3))
    env_4 = ((13, pnp16), (14, closure16), (15, none3))
    env_5 = ((12, ubv1), (13, pnp16), (14, closure16), (15, none3))
    control_1 = (16,)

    machine = MuredMachine.from_expr(
        parse_expr("((LAMBDA (x) x) (LAMBDA (y) y))"),
        quantum=10,
        memory_words=16,
        control_words=4,
    )
    trace: list[tuple[object, ...]] = []
    while not machine.state.halted:
        trace.append(detailed_snapshot(machine))
        machine.step()

    assert trace == [
        (0, MuredOpcode.APP, Direction.F, 0, 5, 16, -1, 10, 0, graph_0, (), ()),
        (
            1,
            MuredOpcode.LAMBDA,
            Direction.F,
            1,
            6,
            16,
            0,
            10,
            0,
            graph_1,
            (),
            control_1,
        ),
        (
            2,
            MuredOpcode.VAR,
            Direction.F,
            2,
            5,
            14,
            -1,
            9,
            0,
            graph_1,
            env_2,
            (),
        ),
        (
            3,
            MuredOpcode.CLOSURE,
            Direction.F,
            14,
            5,
            14,
            -1,
            9,
            0,
            graph_1,
            env_2,
            (),
        ),
        (
            4,
            MuredOpcode.LAMBDA,
            Direction.F,
            3,
            5,
            13,
            -1,
            9,
            0,
            graph_1,
            env_4,
            (),
        ),
        (
            5,
            MuredOpcode.VAR,
            Direction.F,
            4,
            6,
            12,
            -1,
            9,
            1,
            graph_5,
            env_5,
            (),
        ),
        (
            6,
            MuredOpcode.UBV,
            Direction.F,
            12,
            6,
            12,
            -1,
            9,
            1,
            graph_5,
            env_5,
            (),
        ),
        (
            7,
            MuredOpcode.LAMBDA,
            Direction.B,
            6,
            7,
            12,
            -1,
            9,
            1,
            graph_7,
            env_5,
            (),
        ),
        (
            8,
            MuredOpcode.STOP,
            Direction.B,
            5,
            7,
            12,
            -1,
            9,
            0,
            graph_7,
            env_5,
            (),
        ),
    ]
    assert machine.state.pc == 6
    assert to_source(machine.result_expr()) == "(LAMBDA (y) y)"


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("42", 10),
        ("42", 0),
        ("(LAMBDA (x) 42)", 10),
        ("(LAMBDA (x) 42)", 0),
        ("((LAMBDA (x) x) 42)", 10),
        ("((LAMBDA (x) x) 42)", 0),
    ],
)
def test_mured_result_matches_chapter3_for_integer_corpus(
    source: str,
    quantum: int,
) -> None:
    expr = parse_expr(source)
    machine = MuredMachine.from_expr(
        expr,
        quantum=quantum,
        memory_words=64,
    )
    machine.run()
    thor = group_consecutive_lambdas(
        reduce_expr(expr, quantum=quantum).expr
    )

    assert to_source(machine.result_expr()) == to_source(thor)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("FOO", 10),
        ("(LAMBDA (x) FOO)", 10),
        ("((LAMBDA (x) x) FOO)", 10),
        ("((LAMBDA (x) FOO) 42)", 10),
        ("((LAMBDA (x) FOO) 42)", 0),
    ],
)
def test_mured_result_matches_chapter3_for_symbol_corpus(
    source: str,
    quantum: int,
) -> None:
    expr = parse_expr(source)
    machine = MuredMachine.from_expr(
        expr,
        quantum=quantum,
        memory_words=64,
    )
    machine.run()
    thor = group_consecutive_lambdas(
        reduce_expr(expr, quantum=quantum).expr
    )

    assert to_source(machine.result_expr()) == to_source(thor)


@pytest.mark.parametrize(
    ("quantum", "expected_source"),
    [
        (10, "42"),
        (0, "FOO"),
    ],
)
def test_mured_result_matches_chapter3_for_defined_symbol_corpus(
    quantum: int,
    expected_source: str,
) -> None:
    expr = parse_expr("FOO")
    definition = parse_expr("((LAMBDA (x) x) 42)")
    machine = load_defined_symbol_machine(
        "FOO",
        "((LAMBDA (x) x) 42)",
        quantum=quantum,
    )
    thor = group_consecutive_lambdas(
        reduce_expr(
            expr,
            quantum=quantum,
            definitions={"FOO": definition},
        ).expr
    )

    machine.run()

    assert to_source(machine.result_expr()) == expected_source
    assert to_source(machine.result_expr()) == to_source(thor)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("1.5", 10),
        ("#\\a", 10),
        ("#\\space", 10),
        ("(LAMBDA (x) 1.5)", 10),
        ("(LAMBDA (x) #\\newline)", 10),
        ("((LAMBDA (x) x) 1.5)", 10),
        ("((LAMBDA (x) x) 1.5)", 0),
        ("((LAMBDA (x) x) #\\a)", 10),
    ],
)
def test_mured_result_matches_chapter3_for_float_and_char_corpus(
    source: str,
    quantum: int,
) -> None:
    expr = parse_expr(source)
    machine = MuredMachine.from_expr(
        expr,
        quantum=quantum,
        memory_words=64,
    )
    machine.run()
    thor = group_consecutive_lambdas(
        reduce_expr(expr, quantum=quantum).expr
    )

    assert to_source(machine.result_expr()) == to_source(thor)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(LAMBDA (x) x)", 10),
        ("((LAMBDA (x) x) (LAMBDA (y) y))", 10),
        ("(LAMBDA (x) (LAMBDA (y) x))", 10),
        ("(LAMBDA (x y) x)", 10),
        ("(LAMBDA (x y) y)", 10),
        (
            "((LAMBDA (x y) x) (LAMBDA (a) a) (LAMBDA (b) b))",
            10,
        ),
        (
            "((LAMBDA (x y) y) (LAMBDA (a) a) (LAMBDA (b) b))",
            10,
        ),
        (
            "((LAMBDA (x) x) (LAMBDA (a) a) (LAMBDA (b) b))",
            10,
        ),
        ("((LAMBDA (x) (LAMBDA (y) x)) (LAMBDA (z) z))", 20),
        ("((LAMBDA (x) (LAMBDA (y) x)) (LAMBDA (z) z))", 1),
        ("(LAMBDA (f x) (f x))", 10),
        ("((LAMBDA (x) (LAMBDA (y) x)) 42)", 10),
        ("((LAMBDA (x) (LAMBDA (y) x)) 42)", 0),
        ("((LAMBDA (x) x) (LAMBDA (y) y))", 0),
    ],
)
def test_mured_result_matches_chapter3_for_small_pure_lambda_corpus(
    source: str,
    quantum: int,
) -> None:
    expr = parse_expr(source)
    machine = MuredMachine.from_expr(
        expr,
        quantum=quantum,
        memory_words=128,
    )
    machine.run()
    thor = group_consecutive_lambdas(
        reduce_expr(expr, quantum=quantum).expr
    )

    assert to_source(machine.result_expr()) == to_source(thor)


@pytest.mark.parametrize(
    ("source", "quantum", "expected", "remaining_quantum"),
    [
        ("(+ 2 3)", 3, "5", 2),
        ("(+ 0 0)", 1, "0", 0),
        ("(+ (+ 1 2) 3)", 5, "6", 3),
    ],
)
def test_mured_integer_add_matches_chapter3(
    source: str,
    quantum: int,
    expected: str,
    remaining_quantum: int,
) -> None:
    expr = parse_expr(source)
    machine = MuredMachine.from_expr(
        expr,
        quantum=quantum,
        memory_words=128,
        control_words=32,
    )

    machine.run()

    assert to_source(machine.result_expr()) == expected
    assert to_source(machine.result_expr()) == to_source(
        reduce_expr(expr, quantum=quantum).expr
    )
    assert machine.state.q == remaining_quantum
    assert machine.state.prim is None
    assert machine.state.fire == 0
    if source == "(+ 2 3)":
        assert machine.state.fsp == machine.state.pc
        assert machine.state.memory[machine.state.fsp] == Word(
            MuredOpcode.INT, 5, True
        )


def test_mured_add_rechecks_quantum_after_strict_argument_reduction() -> None:
    source = "(+ (+ 1 2) 3)"
    machine = MuredMachine.from_expr(
        parse_expr(source),
        quantum=1,
        memory_words=128,
        control_words=32,
    )

    machine.run()

    assert to_source(machine.result_expr()) == "(+ 3 3)"
    assert machine.state.q == 0
    assert machine.state.prim is None
    assert machine.state.fire == 0


def test_mured_add_with_zero_quantum_remains_unreduced() -> None:
    source = "(+ 2 3)"
    machine = MuredMachine.from_expr(
        parse_expr(source),
        quantum=0,
        memory_words=64,
        control_words=16,
    )

    machine.run()

    assert to_source(machine.result_expr()) == source
    assert machine.state.q == 0
    assert machine.state.prim is None
    assert machine.state.fire == 0


def test_mured_add_with_wrong_type_remains_unreduced() -> None:
    source = "(+ 2 TRUE)"
    machine = MuredMachine.from_expr(
        parse_expr(source),
        quantum=5,
        memory_words=64,
        control_words=16,
    )

    machine.run()

    assert to_source(machine.result_expr()) == source
    assert machine.state.q == 5
    assert machine.state.prim is None
    assert machine.state.fire == 0


def test_mured_execution_does_not_depend_on_evaluator_term_graphs() -> None:
    source = Path("models/python/red2_engine/mured.py").read_text()

    assert "from red2_engine.machine" not in source
    assert "_ProgramParser" not in source
    assert "_Term" not in source
    assert "reduce_expr" not in source
    step_body = source[source.index("    def step(") : source.index("    def run(")]
    assert "result_expr" not in step_body
    assert "_decompile" not in step_body

from pathlib import Path

import pytest

from red2_engine.mured import Direction, MuredMachine, MuredOpcode
from thor_engine.semantics import reduce_expr
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


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


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(LAMBDA (x) x)", 10),
        ("((LAMBDA (x) x) (LAMBDA (y) y))", 10),
        ("(LAMBDA (x) (LAMBDA (y) x))", 10),
        ("((LAMBDA (x) (LAMBDA (y) x)) (LAMBDA (z) z))", 20),
        ("((LAMBDA (x) (LAMBDA (y) x)) (LAMBDA (z) z))", 1),
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
    thor = reduce_expr(expr, quantum=quantum).expr

    assert to_source(machine.result_expr()) == to_source(thor)


def test_mured_execution_does_not_depend_on_evaluator_term_graphs() -> None:
    source = Path("models/python/red2_engine/mured.py").read_text()

    assert "from red2_engine.machine" not in source
    assert "_ProgramParser" not in source
    assert "_Term" not in source
    assert "reduce_expr" not in source
    step_body = source[source.index("    def step(") : source.index("    def run(")]
    assert "result_expr" not in step_body
    assert "_decompile" not in step_body

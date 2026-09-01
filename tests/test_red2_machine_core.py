import sys

import pytest

from red2_engine.instructions import Opcode
from red2_engine.machine import (
    Direction,
    Red2HeapExhaustedError,
    Red2Machine,
    Red2ResourceLimits,
    Red2StackOverflowError,
)
from thor_compile.red2 import compile_expr
from thor_lang.ast import Integer, StructLit, Symbol
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def machine(source: str, quantum: int = 10) -> Red2Machine:
    return Red2Machine(compile_expr(parse_expr(source)), quantum=quantum)


def test_machine_initializes_problem_graph_with_stop_and_forward_direction() -> None:
    m = machine("42")
    assert m.state.pc == 0
    assert m.state.direction is Direction.F
    assert m.state.memory[-1].opcode is Opcode.STOP


def test_int_head_switches_to_reverse_and_stop_halts() -> None:
    m = machine("42")
    m.run()
    assert m.state.halted is True
    assert m.result_instructions()[0].opcode is Opcode.INT
    assert m.result_instructions()[0].data == 42


def test_beta_reduction_on_lambda_application_consumes_quantum() -> None:
    m = machine("((LAMBDA (X) X) 42)", quantum=10)
    m.run()
    assert m.state.q == 9
    assert [(i.opcode, i.data) for i in m.result_instructions()] == [(Opcode.INT, 42)]


def test_exhausted_quantum_keeps_application_spine() -> None:
    m = machine("((LAMBDA (X) X) 42)", quantum=0)
    m.run()
    assert [i.opcode for i in m.result_instructions()] == [
        Opcode.APP,
        Opcode.LAMBDA,
        Opcode.INT,
    ]


def test_red2_stack_limit_raises_deterministic_error() -> None:
    m = Red2Machine(
        compile_expr(parse_expr("((LAMBDA (X) X) 42)")),
        quantum=10,
        resource_limits=Red2ResourceLimits(
            stack_size_in_bytes=1,
            heap_size_in_bytes=1_000_000,
        ),
    )

    with pytest.raises(Red2StackOverflowError, match="RED2 stack overflow"):
        m.run()


def test_deep_default_red2_recursion_raises_machine_stack_overflow() -> None:
    source = "((Y (LAMBDA (loop) (LAMBDA (n) (loop n)))) 1)"
    m = Red2Machine(compile_expr(parse_expr(source)), quantum=100_000)
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        with pytest.raises(Red2StackOverflowError, match="RED2 stack overflow"):
            m.run()
    finally:
        sys.setrecursionlimit(previous_limit)


def test_red2_heap_limit_raises_before_copying_or_parsing_image() -> None:
    source = "[1 2 3 4 5 6 7 8 9 10]"
    image = compile_expr(parse_expr(source))

    with pytest.raises(Red2HeapExhaustedError, match="RED2 heap exhausted"):
        Red2Machine(
            image,
            quantum=100,
            resource_limits=Red2ResourceLimits(
                stack_size_in_bytes=1_000_000,
                heap_size_in_bytes=1,
            ),
        )


def test_red2_result_emission_respects_heap_limit_incrementally() -> None:
    m = Red2Machine(
        compile_expr(parse_expr("42")),
        quantum=10,
        resource_limits=Red2ResourceLimits(
            stack_size_in_bytes=1_000_000,
            heap_size_in_bytes=192,
        ),
    )

    with pytest.raises(Red2HeapExhaustedError, match="RED2 heap exhausted"):
        m.run()


def test_red2_result_expression_respects_heap_limit_incrementally() -> None:
    m = Red2Machine(
        compile_expr(parse_expr("42")),
        quantum=10,
        resource_limits=Red2ResourceLimits(
            stack_size_in_bytes=1_000_000,
            heap_size_in_bytes=256,
        ),
    )
    m.run()

    with pytest.raises(Red2HeapExhaustedError, match="RED2 heap exhausted"):
        m.result_expr()


def test_deep_finite_result_materialization_does_not_use_python_stack() -> None:
    depth = 250
    source = "NIL"
    for _ in range(depth):
        source = f"(CONS 1 {source})"
    image = compile_expr(parse_expr(source))

    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        m = Red2Machine(image, quantum=depth + 10)
        m.run()
        value = m.result_expr()
    finally:
        sys.setrecursionlimit(previous_limit)

    for _ in range(depth):
        assert isinstance(value, StructLit)
        assert value.tag == "PAIR"
        assert value.fields[0] == Integer(1)
        value = value.fields[1]
    assert value == Symbol("NIL")


def test_red2_configured_resource_limits_allow_success() -> None:
    m = Red2Machine(
        compile_expr(parse_expr("((LAMBDA (X) X) 42)")),
        quantum=10,
        resource_limits=Red2ResourceLimits(
            stack_size_in_bytes=1_000_000,
            heap_size_in_bytes=1_000_000,
        ),
    )
    m.run()

    assert to_source(m.result_expr()) == "42"

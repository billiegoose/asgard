from thor_spec.parser import parse_expr
from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.instructions import Opcode
from thor_spec.red2.machine import Direction, Red2Machine


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

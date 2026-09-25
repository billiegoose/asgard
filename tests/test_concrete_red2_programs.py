from pathlib import Path

import pytest

from abstract_red2_machine.machine import (
    AbstractRED2Machine,
    MuredOpcode,
    MuredStopReason,
    Word,
)
from concrete_red2_machine import abi
from concrete_red2_machine.machine import RED2_PROGRAMS_V1
from concrete_red2_machine.oracle import load_compiled_program, run_lockstep
from abstract_red2_machine.loader import load_faithful_machine
from thor.ast import Definition, Expr, StructDef
from thor.normalization import normalize_expr, normalize_program
from thor.parser import parse_expr, parse_program
from thor.pretty import to_source
from thor.primitives import install_struct_definition


def test_red2_programs_v1_is_explicit() -> None:
    assert RED2_PROGRAMS_V1 == 1


def _assert_program_commits_match(source: str, quantum: int) -> None:
    expr = normalize_expr(parse_expr(source))
    machine = load_faithful_machine(
        expr,
        quantum=quantum,
        memory_words=128,
        control_words=32,
    )
    result = run_lockstep(machine, max_transitions=256)
    assert result.matches, (
        source,
        quantum,
        None if result.divergence is None else result.divergence.format(),
    )
    assert machine.state.halted


@pytest.mark.parametrize(
    "source",
    [
        "(IF TRUE 7 (BAD BAD))",
        "(IF FALSE (BAD BAD) 9)",
        "(AND FALSE (BAD BAD))",
        "(OR TRUE (BAD BAD))",
        "(Y (LAMBDA (self) 7))",
    ],
)
@pytest.mark.parametrize("quantum", range(0, 7))
def test_lazy_program_q_prefix_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(CAR {PAIR (+ 2 3) (BAD BAD)})", 8),
        ("(CDR {PAIR (BAD BAD) (+ 3 4)})", 8),
        ("(CAR (CONS 1 [2 3]))", 12),
        ("(CDR (CONS 1 [2 3]))", 12),
        ("(CAR {PAIR {PAIR 1 2} (BAD BAD)})", 8),
        ("(CAR {PAIR (FOO {PAIR 1 2}) (BAD BAD)})", 8),
    ],
)
def test_struct_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(LETREC ((x 7)) x)", 1),
        ("(LETREC ((x 7)) x)", 0),
        ("(LETREC ((x y) (y 9)) x)", 2),
        ("(LETREC ((f (LAMBDA (n) n))) (f 1))", 2),
        ("(LETREC ((x [1 | y]) (y [2 | x])) x)", 1),
    ],
)
def test_recursive_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(EQUAL? 1 1)", 1),
        ("(EQUAL? 1 2)", 1),
        ("(EQUAL? #\\a #\\a)", 1),
        ("(EQUAL? SAME SAME)", 1),
        ("(EQUAL? LEFT RIGHT)", 1),
        ("(EQUAL? 1 1)", 0),
    ],
)
def test_equality_atomic_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(EQUAL? (LAMBDA (x) x) (LAMBDA (y) y))", 20),
        ("(EQUAL? (LAMBDA (x) x) (LAMBDA (y) 1))", 20),
        ("(EQUAL? (LAMBDA (x y) x) (LAMBDA (a b) a))", 20),
        ("(EQUAL? (LAMBDA (x y) x) (LAMBDA (a b) b))", 20),
        ("(EQUAL? (F 1 2) (F 1 2))", 20),
        ("(EQUAL? (F 1 2) (F 1 3))", 20),
        ("(EQUAL? (F 1) (F 1 2))", 20),
        ("(EQUAL? {PAIR 1 2} {PAIR 1 2})", 20),
        ("(EQUAL? {PAIR 1 2} {PAIR 1 3})", 20),
        ("(EQUAL? {PAIR 1 (BAD BAD)} {PAIR 2 (BAD BAD)})", 20),
    ],
)
def test_equality_compound_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


def _canonical_python_result(
    source: str,
    *,
    quantum: int = 100_000,
    memory_words: int = 32_768,
    control_words: int = 8_192,
) -> str:
    machine = load_faithful_machine(
        normalize_expr(parse_expr(source)),
        quantum=quantum,
        memory_words=memory_words,
        control_words=control_words,
    )
    machine.run(cycle_limit=2_000_000)
    assert machine.state.halted
    return to_source(machine.result_expr())


def _concrete_result_source(loaded) -> str:
    state = loaded.codec.decode_state(loaded.concrete.checkpoint())
    result_view = AbstractRED2Machine(
        state,
        working_memory_limit=loaded.image.working_memory_limit,
    )
    return to_source(result_view.result_expr())


def _forbid_python_red2_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("concrete execution called the Python RED2 evaluator")

    monkeypatch.setattr(AbstractRED2Machine, "step", forbidden)
    monkeypatch.setattr(AbstractRED2Machine, "run", forbidden)
    monkeypatch.setattr(AbstractRED2Machine, "run_until_suspend", forbidden)


def _nested_closure_source(depth: int) -> str:
    body = "0"
    for index in range(depth, 0, -1):
        body = f"((LAMBDA (x{index}) (+ x{index} {body})) 1)"
    return body


def _structure_heavy_source(count: int) -> str:
    terms = [f"(CAR {{PAIR {value} (BAD BAD)}})" for value in range(1, count + 1)]
    expression = terms[-1]
    for term in reversed(terms[:-1]):
        expression = f"(+ {term} {expression})"
    return expression


@pytest.mark.stress
@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        (
            "recursive",
            "((Y (LAMBDA (self) (LAMBDA (n) "
            "(IF (= n 0) 0 (+ 1 (self (1- n))))))) 25)",
            "25",
        ),
        ("closure-heavy", _nested_closure_source(60), "60"),
        ("structure-heavy", _structure_heavy_source(20), "210"),
    ],
)
def test_nontrivial_pure_program_runs_wholly_on_concrete_machine(
    name: str,
    source: str,
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    python_result = _canonical_python_result(source)
    assert python_result == expected

    loaded = load_compiled_program(
        normalize_expr(parse_expr(source)),
        quantum=100_000,
        memory_words=32_768,
        control_words=8_192,
    )
    _forbid_python_red2_evaluation(monkeypatch)

    status = loaded.concrete.run_until_suspend(max_clocks=100_000_000)

    assert status == abi.STATUS_COMPLETE, (name, loaded.concrete.fault)
    assert loaded.concrete.commits > 500, (name, loaded.concrete.commits)
    assert _concrete_result_source(loaded) == python_result


@pytest.mark.stress
def test_bounded_loop_recharges_same_concrete_machine_and_storage_to_same_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = (
        "((Y (LAMBDA (self) (LAMBDA (n) "
        "(IF (= n 0) 0 (+ 1 (self (1- n))))))) 25)"
    )
    python_result = _canonical_python_result(source)
    loaded = load_compiled_program(
        normalize_expr(parse_expr(source)),
        quantum=8,
        memory_words=16_384,
        control_words=4_096,
    )
    concrete = loaded.concrete
    identities = (id(concrete), id(concrete.memory), id(concrete.control_stack))
    _forbid_python_red2_evaluation(monkeypatch)

    exhaustions = 0
    for _ in range(64):
        status = concrete.run_until_suspend(max_clocks=100_000_000)
        assert (
            id(concrete), id(concrete.memory), id(concrete.control_stack)
        ) == identities
        if status == abi.STATUS_COMPLETE:
            break
        assert status == abi.STATUS_QUANTUM_EXHAUSTED, (status, concrete.fault)
        exhaustions += 1
        assert concrete.recharge_quantum(8) == abi.STATUS_RUNNING
        assert (
            id(concrete), id(concrete.memory), id(concrete.control_stack)
        ) == identities
    else:
        raise AssertionError("bounded loop did not complete after repeated recharge")

    assert exhaustions >= 2
    assert concrete.commits > 500
    assert _concrete_result_source(loaded) == python_result


def _prepare_program(source: str) -> tuple[Expr, dict[str, Expr]]:
    program = normalize_program(parse_program(source))
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    definitions.pop("CAR", None)
    definitions.pop("CDR", None)
    action: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
        else:
            action = form
    assert action is not None
    return action, definitions


def _python_clock_dots_trace(
    source: str, dot_limit: int
) -> tuple[list[tuple[str, int]], int]:
    action, definitions = _prepare_program(source)
    machine = load_faithful_machine(
        action,
        quantum=500,
        definitions=definitions,
        memory_words=65_536,
        control_words=8_192,
    )
    clock = 0
    dots = 0
    trace: list[tuple[str, int]] = []
    for _ in range(100):
        stop = machine.run_until_suspend(cycle_limit=machine.state.cycles + 2_000_000)
        if stop.reason is MuredStopReason.QUANTUM_EXHAUSTED:
            machine.recharge_quantum(500)
            continue
        assert stop.reason is MuredStopReason.HOST_CALL
        call = stop.host_call
        assert call is not None
        if call.name == "CLOCK":
            clock += 1_000
            trace.append(("CLOCK", clock))
            if dots >= dot_limit:
                return trace, machine.state.cycles
            result = Word(MuredOpcode.INT, clock)
        elif call.name == "UART-TX":
            argument = machine.state.memory[call.argument_address]
            assert argument is not None
            assert argument.opcode is MuredOpcode.INT
            assert type(argument.data) is int
            trace.append(("UART-TX", argument.data))
            dots += int(argument.data == 46)
            result = Word(MuredOpcode.SYM, "NIL")
        else:
            raise AssertionError(f"unexpected clock-dots host call: {call.name}")
        machine.resume_host_call(result)
    raise AssertionError("Python RED2 clock-dots did not emit enough dots")


def _concrete_clock_dots_trace(
    source: str,
    dot_limit: int,
) -> tuple[list[tuple[str, int]], int]:
    action, definitions = _prepare_program(source)
    loaded = load_compiled_program(
        action,
        quantum=500,
        definitions=definitions,
        memory_words=65_536,
        control_words=8_192,
    )
    concrete = loaded.concrete
    clock = 0
    dots = 0
    trace: list[tuple[str, int]] = []
    for _ in range(100):
        status = concrete.run_until_suspend(max_clocks=100_000_000)
        if status == abi.STATUS_QUANTUM_EXHAUSTED:
            assert concrete.recharge_quantum(500) == abi.STATUS_RUNNING
            continue
        assert status == abi.STATUS_HOST_CALL, (status, concrete.fault)
        if concrete.pending_host_op == abi.HOST_CLOCK:
            clock += 1_000
            trace.append(("CLOCK", clock))
            if dots >= dot_limit:
                return trace, concrete.commits
            result = Word(MuredOpcode.INT, clock)
        elif concrete.pending_host_op == abi.HOST_UART_TX:
            argument = loaded.codec.decode_word(
                concrete.memory[concrete.pending_host_argument - 1]
            )
            assert argument is not None
            assert argument.opcode is MuredOpcode.INT
            assert type(argument.data) is int
            trace.append(("UART-TX", argument.data))
            dots += int(argument.data == 46)
            result = Word(MuredOpcode.SYM, "NIL")
        else:
            raise AssertionError(
                f"unexpected clock-dots host op: {concrete.pending_host_op}"
            )
        resumed = concrete.resume_host_call(loaded.codec.encode_word(result))
        assert resumed in (abi.STATUS_RUNNING, abi.STATUS_QUANTUM_EXHAUSTED)
    raise AssertionError("Concrete RED2 clock-dots did not emit enough dots")


def test_clock_dots_effect_order_and_exactly_once_behavior_match_python_red2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Path("examples/clock-dots.thor").read_text()
    python_trace, python_cycles = _python_clock_dots_trace(source, dot_limit=4)

    expected = [
        ("CLOCK", 1_000),
        ("CLOCK", 2_000),
        ("UART-TX", 46),
        ("CLOCK", 3_000),
        ("UART-TX", 46),
        ("CLOCK", 4_000),
        ("UART-TX", 46),
        ("CLOCK", 5_000),
        ("UART-TX", 46),
        ("CLOCK", 6_000),
    ]
    assert python_trace == expected

    _forbid_python_red2_evaluation(monkeypatch)
    concrete_trace, concrete_commits = _concrete_clock_dots_trace(source, dot_limit=4)

    assert concrete_trace == python_trace
    assert concrete_commits == python_cycles
    assert sum(name == "UART-TX" for name, _ in concrete_trace) == 4

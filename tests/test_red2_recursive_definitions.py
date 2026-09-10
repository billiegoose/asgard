from thor_compile.red2 import load_faithful_machine
from thor_engine.golden import _initial_definitions, run_source
from thor_engine.semantics import reduce_expr
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition


def _prepare_recursive_source(
    source: str,
    *,
    model: str,
) -> tuple[Expr, dict[str, Expr]]:
    program = normalize_program(parse_program(source))
    definitions = _initial_definitions(model=model)  # type: ignore[arg-type]
    expr: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
        else:
            if expr is not None:
                raise AssertionError("test source must contain exactly one expression")
            expr = form
    assert expr is not None
    return expr, definitions


def test_recursive_top_level_factorial_definition_matches_thor() -> None:
    source = """
    fact == (lambda (n) (if (= n 0) 1 (* n (fact (1- n)))))
    (fact 5)
    """
    assert run_source(source, model="thor", quantum=500) == "120"
    assert run_source(source, model="red2", quantum=500) == "120"


def test_recursive_top_level_fibonacci_definition_matches_thor() -> None:
    source = """
    fib == (lambda (n)
      (if (< n 2)
          n
          (+ (fib (1- n)) (fib (1- (1- n))))))
    (fib 7)
    """
    assert run_source(source, model="thor", quantum=2000) == "13"
    assert run_source(source, model="red2", quantum=2000) == "13"


def test_mutual_recursive_prefixes_survive_reclaim_poisoning() -> None:
    source = """
    even == (lambda (n) (if (= n 0) TRUE (odd (1- n))))
    odd == (lambda (n) (if (= n 0) FALSE (even (1- n))))
    (even 4)
    """
    thor_expr, thor_definitions = _prepare_recursive_source(source, model="thor")
    red2_expr, red2_definitions = _prepare_recursive_source(source, model="red2")
    thor_matching_prefixes = {0, 1, 2, 4, 5, 6}

    for quantum in (0, 1, 2, 3, 4, 5, 6, 12, 64, 500):
        ordinary = load_faithful_machine(
            red2_expr,
            quantum=quantum,
            definitions=red2_definitions,
            memory_words=2_048,
            control_words=512,
        )
        poisoned = load_faithful_machine(
            red2_expr,
            quantum=quantum,
            definitions=red2_definitions,
            memory_words=2_048,
            control_words=512,
            memory_diagnostics=True,
            poison_reclaimed_environment=True,
        )

        ordinary.run(cycle_limit=200_000)
        poisoned.run(cycle_limit=200_000)

        ordinary_result = to_source(ordinary.result_expr())
        assert to_source(poisoned.result_expr()) == ordinary_result
        assert poisoned.state.q == ordinary.state.q
        assert poisoned.state.c == ordinary.state.c == -1
        assert poisoned._saved_quantum_depth == ordinary._saved_quantum_depth == 0

        if quantum in thor_matching_prefixes:
            expected = reduce_expr(
                thor_expr,
                quantum=quantum,
                definitions=thor_definitions,
            )
            assert ordinary_result == to_source(expected.expr)
            assert ordinary.state.q == expected.remaining

    expected_final = reduce_expr(
        thor_expr,
        quantum=500,
        definitions=thor_definitions,
    )
    assert to_source(expected_final.expr) == "TRUE"
    assert to_source(poisoned.result_expr()) == "TRUE"

    events = list(poisoned.memory_events())
    reused_then_captured = False
    for reclaim_index, reclaim in enumerate(events):
        if reclaim.name != "ENV_RECLAIM":
            continue
        low = reclaim.data["from"]
        high = reclaim.data["to"]
        assert isinstance(low, int)
        assert isinstance(high, int)
        for alloc_index in range(reclaim_index + 1, len(events)):
            allocation = events[alloc_index]
            if allocation.name != "ENV_ALLOC" or "address" not in allocation.data:
                continue
            address = allocation.data["address"]
            words = allocation.data.get("words", 1)
            assert isinstance(address, int)
            assert isinstance(words, int)
            if not (address < high and address + words > low):
                continue
            if any(
                later.name == "SUBGRAPH_ENTER" and later.opcode == "ep"
                for later in events[alloc_index + 1 :]
            ):
                reused_then_captured = True
                break
        if reused_then_captured:
            break
    assert reused_then_captured


def test_y_combinator_fibonacci_still_matches() -> None:
    source = """
    ((Y (lambda (fib n)
       (if (< n 2)
           n
           (+ (fib (1- n)) (fib (1- (1- n))))))) 6)
    """
    assert run_source(source, model="thor", quantum=2000) == "8"
    assert run_source(source, model="red2", quantum=2000) == "8"


def test_recursive_q0_residual_survives_repeated_recharge_and_finishes() -> None:
    source = """
    fact == (lambda (n) (if (= n 0) 1 (* n (fact (1- n)))))
    (fact 4)
    """
    expr, definitions = _prepare_recursive_source(source, model="red2")
    machine = load_faithful_machine(
        expr,
        quantum=0,
        definitions=definitions,
        memory_words=2_048,
        control_words=512,
    )
    identity = id(machine)

    machine.run(cycle_limit=200_000)
    prefix = to_source(machine.result_expr())
    for _ in range(3):
        machine.recharge_quantum(0)
        assert id(machine) == identity
        assert machine.state.c == -1
        assert machine.state.free_space == machine.working_memory_limit
        machine.run(cycle_limit=200_000)
        assert to_source(machine.result_expr()) == prefix

    machine.recharge_quantum(500)
    machine.run(cycle_limit=200_000)
    assert id(machine) == identity
    assert machine.state.c == -1
    assert to_source(machine.result_expr()) == "24"

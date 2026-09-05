from __future__ import annotations

import pytest

from red2_engine.mured import (
    Direction,
    GraphEnvironmentCollision,
    MuredMachine,
    MuredMachineState,
    MuredOpcode,
    Word,
)
from thor_compile.red2 import load_faithful_machine
from thor_engine.golden import _initial_definitions
from thor_engine.semantics import reduce_expr
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition


def _recursive_struct_source(depth: int) -> str:
    return f"""
node |= value next
build-node == (lambda (n)
  (if (= n 0) NIL (make-node n (build-node (1- n)))))
sum-node == (lambda (node n acc)
  (if (= n 0) acc
      (sum-node (node-next node) (1- n) (+ acc (node-value node)))))
(sum-node (build-node {depth}) {depth} 0)
"""


def _prepare(source: str, *, model: str) -> tuple[Expr, dict[str, Expr]]:
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


@pytest.mark.parametrize(
    ("depth", "expected"),
    [(4, "10"), (8, "36"), (16, "136")],
)
def test_recursive_user_struct_completes_in_default_faithful_memory(
    depth: int,
    expected: str,
) -> None:
    expr, definitions = _prepare(_recursive_struct_source(depth), model="red2")
    machine = load_faithful_machine(
        expr,
        quantum=5_000_000,
        definitions=definitions,
        memory_words=65_536,
    )

    machine.run(cycle_limit=2_000_000)

    assert to_source(machine.result_expr()) == expected


def test_recursive_user_struct_depth_four_matches_thor() -> None:
    expr, definitions = _prepare(_recursive_struct_source(4), model="thor")

    result = reduce_expr(expr, quantum=5_000_000, definitions=definitions)

    assert to_source(result.expr) == "10"


def test_faithful_loader_default_memory_remains_65536_words() -> None:
    assert load_faithful_machine.__kwdefaults__ is not None
    assert load_faithful_machine.__kwdefaults__["memory_words"] == 65_536


def test_graph_environment_collision_guard_still_rejects_overlap() -> None:
    state = MuredMachineState(
        memory=[None] * 4,
        control_stack=[None] * 2,
        pc=0,
        fsp=2,
        env=3,
        env_frontier=3,
        c=-1,
        direction=Direction.F,
        q=1,
        phi=0,
        argcnt=0,
    )
    state.memory[0] = Word(MuredOpcode.INT, 1, True)
    machine = MuredMachine(state)

    with pytest.raises(
        GraphEnvironmentCollision, match="graph and environment collide"
    ):
        machine._push_graph(Word(MuredOpcode.INT, 2, False))

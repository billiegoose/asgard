from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from thor_spec.ast import Definition, Expr, Program, StructDef, Symbol
from thor_spec.normalization import normalize_program
from thor_spec.parser import parse_program
from thor_spec.pretty import to_source
from thor_spec.primitives import install_struct_definition
from thor_spec.red2.compiler import compile_definitions, compile_expr
from thor_spec.red2.machine import Red2Machine
from thor_spec.red2.primitives import register_struct_accessors
from thor_spec.semantics import reduce_expr

ModelName = Literal["thor", "red2"]
DEFAULT_QUANTUM = 100


def run_source(
    source: str,
    *,
    model: ModelName,
    quantum: int,
) -> str:
    """Run THOR source through one prototype model and return result text.

    ``source`` may contain top-level definitions, structure declarations, and
    expression forms.  Definitions update the context for following forms;
    expression results are rendered one per output line.
    """
    program = normalize_program(parse_program(source))
    results = _run_program(program, model=model, quantum=quantum)
    return "\n".join(results)


def _run_program(program: Program, *, model: ModelName, quantum: int) -> list[str]:
    definitions = _initial_definitions()
    results: list[str] = []
    for form in program.forms:
        if isinstance(form, Definition):
            if not _is_existing_self_alias(form, definitions):
                definitions[form.name] = form.expr
            continue
        if isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
            register_struct_accessors(form.tag, form.accessors)
            continue
        results.append(
            _run_expr(
                form,
                model=model,
                quantum=quantum,
                definitions=definitions,
            )
        )
    return results


def _run_expr(
    expr: Expr,
    *,
    model: ModelName,
    quantum: int,
    definitions: Mapping[str, Expr],
) -> str:
    if model == "thor":
        reduced = reduce_expr(expr, quantum=quantum, definitions=definitions)
        return to_source(reduced.expr)
    if model == "red2":
        machine = Red2Machine(
            compile_expr(expr),
            quantum=quantum,
            definitions=compile_definitions(definitions),
        )
        machine.run()
        return to_source(machine.result_expr())
    msg = f"unknown execution model: {model}"
    raise ValueError(msg)


def _initial_definitions() -> dict[str, Expr]:
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    register_struct_accessors("PAIR", ("CAR", "CDR"))
    return definitions


def _is_existing_self_alias(
    form: Definition,
    definitions: Mapping[str, Expr],
) -> bool:
    return (
        isinstance(form.expr, Symbol)
        and form.expr.name == form.name
        and form.name in definitions
    )

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from red2_engine.machine import Red2Machine, Red2ResourceLimits
from red2_engine.primitives import register_struct_accessors
from thor_compile.red2 import compile_definitions, compile_expr
from thor_engine.semantics import reduce_expr
from thor_lang.ast import Definition, Expr, Program, StructDef, Symbol
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition

ModelName = Literal["thor", "red2"]
DEFAULT_QUANTUM = 100


def run_source(
    source: str,
    *,
    model: ModelName,
    quantum: int,
    resource_limits: Red2ResourceLimits | None = None,
) -> str:
    """Run THOR source through one prototype model and return result text.

    ``source`` may contain top-level definitions, structure declarations, and
    expression forms.  Definitions update the context for following forms;
    expression results are rendered one per output line.
    """
    program = normalize_program(parse_program(source))
    results = _run_program(
        program,
        model=model,
        quantum=quantum,
        resource_limits=resource_limits,
    )
    return "\n".join(results)


def _run_program(
    program: Program,
    *,
    model: ModelName,
    quantum: int,
    resource_limits: Red2ResourceLimits | None,
) -> list[str]:
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
                resource_limits=resource_limits,
            )
        )
    return results


def _run_expr(
    expr: Expr,
    *,
    model: ModelName,
    quantum: int,
    definitions: Mapping[str, Expr],
    resource_limits: Red2ResourceLimits | None,
) -> str:
    if model == "thor":
        reduced = reduce_expr(expr, quantum=quantum, definitions=definitions)
        return to_source(reduced.expr)
    if model == "red2":
        machine = Red2Machine(
            compile_expr(expr),
            quantum=quantum,
            definitions=compile_definitions(definitions),
            resource_limits=resource_limits,
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

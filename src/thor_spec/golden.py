from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from thor_spec.ast import (
    App,
    Binding,
    Definition,
    Expr,
    Lambda,
    LetRec,
    Program,
    StructDef,
    StructLit,
    Symbol,
)
from thor_spec.normalization import normalize_program
from thor_spec.parser import parse_program
from thor_spec.pretty import to_source
from thor_spec.primitives import install_struct_definition
from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.machine import Red2Machine
from thor_spec.red2.primitives import instructions_to_expr, register_struct_accessors
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
    red2_native_definitions = _initial_red2_native_definitions(definitions)
    results: list[str] = []
    for form in program.forms:
        if isinstance(form, Definition):
            if not _is_existing_self_alias(form, definitions):
                definitions[form.name] = form.expr
            continue
        if isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
            for name in register_struct_accessors(form.tag, form.accessors):
                red2_native_definitions[name] = definitions[name]
            continue
        results.append(
            _run_expr(
                form,
                model=model,
                quantum=quantum,
                definitions=definitions,
                red2_native_definitions=red2_native_definitions,
            )
        )
    return results


def _run_expr(
    expr: Expr,
    *,
    model: ModelName,
    quantum: int,
    definitions: Mapping[str, Expr],
    red2_native_definitions: Mapping[str, Expr],
) -> str:
    if model == "thor":
        reduced = reduce_expr(expr, quantum=quantum, definitions=definitions)
        return to_source(reduced.expr)
    if model == "red2":
        expanded = _expand_definitions(
            expr,
            _red2_source_definitions(definitions, red2_native_definitions),
        )
        machine = Red2Machine(compile_expr(expanded), quantum=quantum)
        machine.run()
        return to_source(instructions_to_expr(machine.result_instructions()))
    msg = f"unknown execution model: {model}"
    raise ValueError(msg)


def _initial_definitions() -> dict[str, Expr]:
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    return definitions


def _initial_red2_native_definitions(
    definitions: Mapping[str, Expr],
) -> dict[str, Expr]:
    return {
        name: definitions[name]
        for name in register_struct_accessors("PAIR", ("CAR", "CDR"))
        if name in definitions
    }


def _is_existing_self_alias(
    form: Definition,
    definitions: Mapping[str, Expr],
) -> bool:
    return (
        isinstance(form.expr, Symbol)
        and form.expr.name == form.name
        and form.name in definitions
    )


def _red2_source_definitions(
    definitions: Mapping[str, Expr],
    red2_native_definitions: Mapping[str, Expr],
) -> dict[str, Expr]:
    return {
        name: expr
        for name, expr in definitions.items()
        if red2_native_definitions.get(name) != expr
    }


def _expand_definitions(
    expr: Expr,
    definitions: Mapping[str, Expr],
    scope: tuple[str, ...] = (),
    seen: frozenset[str] = frozenset(),
) -> Expr:
    """Inline available source definitions for the current RED2 prototype.

    The Python RED2 model does not yet carry a separate definition store.  A
    conservative expansion step gives CLI/file definitions the same behavior for
    non-recursive uses while leaving recursive references as symbols.
    """
    if isinstance(expr, Symbol):
        if expr.name in scope or expr.name in seen:
            return expr
        definition = definitions.get(expr.name)
        if definition is None:
            return expr
        return _expand_definitions(
            definition,
            definitions,
            scope,
            seen | frozenset((expr.name,)),
        )
    if isinstance(expr, Lambda):
        return Lambda(
            expr.params,
            _expand_definitions(expr.body, definitions, expr.params + scope, seen),
        )
    if isinstance(expr, App):
        return App(
            tuple(
                _expand_definitions(item, definitions, scope, seen)
                for item in expr.items
            )
        )
    if isinstance(expr, LetRec):
        names = tuple(binding.name for binding in expr.bindings)
        binding_scope = names + scope
        return LetRec(
            tuple(
                Binding(
                    binding.name,
                    _expand_definitions(
                        binding.expr,
                        definitions,
                        binding_scope,
                        seen,
                    ),
                )
                for binding in expr.bindings
            ),
            _expand_definitions(expr.body, definitions, binding_scope, seen),
        )
    if isinstance(expr, StructLit):
        return StructLit(
            expr.tag,
            tuple(
                _expand_definitions(field, definitions, scope, seen)
                for field in expr.fields
            ),
        )
    return expr


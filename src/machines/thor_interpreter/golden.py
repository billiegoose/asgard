from collections.abc import Mapping
from typing import Literal

from abstract_red2_machine.loader import load_faithful_machine
from thor.ast import Definition, Expr, Program, StructDef, Symbol
from thor.normalization import normalize_program
from thor.parser import parse_program
from thor.pretty import to_source
from thor.primitives import install_struct_definition
from thor_interpreter.semantics import reduce_expr

ModelName = Literal["thor", "abs", "red2"]
DEFAULT_QUANTUM = 100


def run_source(
    source: str,
    *,
    model: ModelName,
    quantum: int,
    supervised: bool = False,
    memory_words: int = 1_048_576,
    max_quanta: int | None = None,
) -> str:
    """Run THOR source through one prototype model and return result text.

    ``source`` may contain top-level definitions, structure declarations, and
    expression forms. Definitions update the context for following forms;
    expression results are rendered one per output line.
    """
    program = normalize_program(parse_program(source))
    results = _run_program(
        program,
        model=model,
        quantum=quantum,
        supervised=supervised,
        memory_words=memory_words,
        max_quanta=max_quanta,
    )
    return "\n".join(results)


def _run_program(
    program: Program,
    *,
    model: ModelName,
    quantum: int,
    supervised: bool = False,
    memory_words: int = 1_048_576,
    max_quanta: int | None = None,
) -> list[str]:
    definitions = _initial_definitions(model=model)
    results: list[str] = []
    for form in program.forms:
        if isinstance(form, Definition):
            if not _is_existing_self_alias(form, definitions):
                definitions[form.name] = form.expr
            continue
        if isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
            continue
        results.append(
            _run_expr(
                form,
                model=model,
                quantum=quantum,
                definitions=definitions,
                supervised=supervised,
                memory_words=memory_words,
                max_quanta=max_quanta,
            )
        )
    return results


def _run_expr(
    expr: Expr,
    *,
    model: ModelName,
    quantum: int,
    definitions: Mapping[str, Expr],
    supervised: bool = False,
    memory_words: int = 1_048_576,
    max_quanta: int | None = None,
) -> str:
    if model == "thor":
        reduced = reduce_expr(expr, quantum=quantum, definitions=definitions)
        return to_source(reduced.expr)
    if model in {"abs", "red2"}:
        machine = load_faithful_machine(
            expr,
            quantum=quantum,
            definitions=definitions,
            memory_words=memory_words,
        )
        if supervised:
            from abstract_red2_machine.supervisor import AbstractProcessor
            from red2.supervisor import supervise

            return to_source(
                supervise(
                    AbstractProcessor(machine),
                    quantum=quantum,
                    max_quanta=max_quanta,
                )
            )
        machine.run()
        return to_source(machine.result_expr())
    msg = f"unknown execution model: {model}"
    raise ValueError(msg)


def _initial_definitions(*, model: ModelName) -> dict[str, Expr]:
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    if model in {"abs", "red2"}:
        definitions.pop("CAR", None)
        definitions.pop("CDR", None)
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

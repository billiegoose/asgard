from __future__ import annotations

from pathlib import Path

import pytest

from thor_compile.red2 import load_faithful_machine
from thor_engine.golden import _initial_definitions
from thor_engine.semantics import reduce_expr
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition

ROOT = Path(__file__).resolve().parents[1]

BENCHMARKS = (
    (ROOT / "benchmarks/tak.thor", "15"),
    (ROOT / "benchmarks/list-build-sum.thor", "300"),
    (ROOT / "benchmarks/struct-build-sum.thor", "300"),
    (ROOT / "tests/fixtures/appendix_a/game_full.thor", "8"),
)


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
                raise AssertionError(
                    "benchmark source must contain exactly one expression"
                )
            expr = form
    assert expr is not None
    return expr, definitions


def _run_thor(source: str) -> str:
    expr, definitions = _prepare(source, model="thor")
    result = reduce_expr(expr, quantum=5_000_000, definitions=definitions)
    return to_source(result.expr)


def _run_red2(source: str) -> str:
    expr, definitions = _prepare(source, model="red2")
    machine = load_faithful_machine(
        expr,
        quantum=5_000_000,
        definitions=definitions,
    )
    machine.run(cycle_limit=2_000_000)
    return to_source(machine.result_expr())


@pytest.mark.parametrize(
    ("path", "expected"),
    BENCHMARKS,
    ids=lambda value: Path(value).stem if isinstance(value, Path) else None,
)
def test_pure_benchmark_matches_expected_on_both_python_engines(
    path: Path,
    expected: str,
) -> None:
    source = path.read_text()

    for _ in range(3):
        assert _run_thor(source) == expected
        assert _run_red2(source) == expected


def test_pure_benchmark_sources_do_not_use_runtime_io() -> None:
    forbidden = ("CLOCK", "DISPLAY", "READ", "WRITE", "OPEN", "CLOSE")

    for path, _expected in BENCHMARKS:
        source = path.read_text().upper()
        assert all(token not in source for token in forbidden)

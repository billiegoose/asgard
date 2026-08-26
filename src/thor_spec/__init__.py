"""Executable specification tools for Hilton's THOR graph reducer."""

from thor_spec.ast import (
    App,
    Binding,
    Char,
    Definition,
    Float,
    Integer,
    Lambda,
    LetRec,
    Program,
    StructDef,
    StructLit,
    Symbol,
    Var,
)
from thor_spec.core import FuelExhaustedError, Machine, MachineStatus, StepResult
from thor_spec.parser import parse_expr, parse_program
from thor_spec.pretty import to_source
from thor_spec.semantics import ReductionResult, reduce_expr, translate
from thor_spec.version import __version__

__all__ = [
    "App",
    "Binding",
    "Char",
    "Definition",
    "Float",
    "FuelExhaustedError",
    "Integer",
    "Lambda",
    "LetRec",
    "Machine",
    "MachineStatus",
    "Program",
    "ReductionResult",
    "StepResult",
    "StructDef",
    "StructLit",
    "Symbol",
    "Var",
    "__version__",
    "parse_expr",
    "parse_program",
    "reduce_expr",
    "to_source",
    "translate",
]

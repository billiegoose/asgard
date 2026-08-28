from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from thor_spec.ast import (
    App,
    Char,
    Expr,
    Float,
    Integer,
    Lambda,
    LetRec,
    StructLit,
    Symbol,
    Var,
)
from thor_spec.red2.instructions import (
    DefinitionImage,
    Instruction,
    Opcode,
    ProgramImage,
)

Scope = tuple[str, ...]


_STRICT_PRIMITIVE_ARITY: dict[str, int] = {
    "TRUE": 0,
    "FALSE": 0,
    "NIL": 0,
    "+": 2,
    "-": 2,
    "*": 2,
    "/": 2,
    "<": 2,
    ">": 2,
    "<=": 2,
    ">=": 2,
    "=": 2,
    "EQUAL?": 2,
    "1-": 1,
    "INTEGER?": 1,
    "FLOAT?": 1,
    "CHAR?": 1,
    "SYMBOL?": 1,
    "STRUCTURE?": 1,
    "NOT": 1,
    "TAG": 1,
    "CAR": 1,
    "CDR": 1,
    "MOD": 2,
}
_NON_STRICT_SYMBOLS = frozenset({"AND", "OR", "IF", "Y"})


class _Compiler:
    def __init__(self) -> None:
        self._instructions: list[Instruction] = []
        self._symbol_table: dict[str, int] = {}
        self._metadata: dict[str, tuple[str, ...]] = {}

    def compile(self, expr: Expr) -> ProgramImage:
        self._emit_expr(expr, (), head=True)
        self._emit(Opcode.STOP, 0, head=True)
        return ProgramImage(
            tuple(self._instructions),
            0,
            dict(self._symbol_table),
            dict(self._metadata),
        )

    def _emit_expr(self, expr: Expr, scope: Scope, *, head: bool) -> None:
        if isinstance(expr, Var):
            self._emit(Opcode.VAR, expr.index, head=head)
            return
        if isinstance(expr, Lambda):
            self._emit_lambda(expr, scope, head=head)
            return
        if isinstance(expr, App):
            self._emit_app(expr, scope, head=head)
            return
        if isinstance(expr, LetRec):
            self._emit_letrec(expr, scope, head=head)
            return
        if isinstance(expr, StructLit):
            self._emit_struct(expr, scope, head=head)
            return
        if isinstance(expr, Symbol):
            self._emit_symbol(expr.name, scope, head=head)
            return
        if isinstance(expr, Integer):
            self._emit(Opcode.INT, expr.value, head=head)
            return
        if isinstance(expr, Float):
            self._emit(Opcode.FLOAT, expr.value, head=head)
            return
        if isinstance(expr, Char):
            self._emit(Opcode.CHAR, expr.value, head=head)
            return

    def _emit_lambda(self, expr: Lambda, scope: Scope, *, head: bool) -> None:
        lambda_start = len(self._instructions)
        self._metadata[f"lambda:{lambda_start}:arity"] = (str(len(expr.params)),)
        for param in expr.params:
            self._emit(Opcode.LAMBDA, param, head=False)
        extended_scope = expr.params + scope
        self._emit_expr(expr.body, extended_scope, head=head)

    def _emit_flat_spine(
        self, items: tuple[Expr, ...], scope: Scope, *, final_head: bool
    ) -> None:
        if not items:
            self._emit(Opcode.PNP, 0, head=final_head)
            return
        last_index = len(items) - 1
        for index, item in enumerate(items):
            item_head = final_head if index == last_index else False
            self._emit_expr(item, scope, head=item_head)

    def _emit_app(self, expr: App, scope: Scope, *, head: bool) -> None:
        if not expr.items:
            self._emit(Opcode.PNP, 0, head=head)
            return
        if len(expr.items) == 1:
            self._emit_expr(expr.items[0], scope, head=head)
            return

        app_positions: list[int] = []
        for _arg in expr.items[1:]:
            app_positions.append(self._emit(Opcode.APP, 0, head=False))
        self._emit_expr(expr.items[0], scope, head=head)
        for app_position, arg in zip(app_positions, expr.items[1:], strict=True):
            arg_entry = len(self._instructions)
            self._instructions[app_position] = replace(
                self._instructions[app_position], data=arg_entry
            )
            self._emit_expr(arg, scope, head=True)

    def _emit_struct(self, expr: StructLit, scope: Scope, *, head: bool) -> None:
        self._emit(Opcode.STRUCT, expr.tag, head=False)
        app_positions: list[tuple[int, Expr]] = []
        for field in reversed(expr.fields):
            position = self._emit(Opcode.APP, 0, head=False)
            app_positions.append((position, field))
        self._emit(Opcode.VAR, 0, head=head)
        for app_position, field in app_positions:
            field_entry = len(self._instructions)
            self._instructions[app_position] = replace(
                self._instructions[app_position], data=field_entry
            )
            self._emit_expr(field, scope, head=True)

    def _emit_letrec(self, expr: LetRec, scope: Scope, *, head: bool) -> None:
        block_positions: list[tuple[int, Expr]] = []
        letrec_start = len(self._instructions)
        names = tuple(binding.name for binding in expr.bindings)
        self._metadata[f"letrec:{letrec_start}:names"] = names
        for binding in expr.bindings:
            position = self._emit(Opcode.RBLOCK, 0, head=False)
            block_positions.append((position, binding.expr))
        self._emit(Opcode.RUP, len(expr.bindings), head=False)
        extended_scope = names + scope
        self._emit_expr(expr.body, extended_scope, head=head)
        for block_position, binding_expr in block_positions:
            binding_entry = len(self._instructions)
            self._instructions[block_position] = replace(
                self._instructions[block_position], data=binding_entry
            )
            self._emit_expr(binding_expr, extended_scope, head=True)

    def _emit_symbol(self, name: str, scope: Scope, *, head: bool) -> None:
        if name in scope:
            self._emit(Opcode.VAR, scope.index(name), head=head)
            return
        primitive_arity = _STRICT_PRIMITIVE_ARITY.get(name)
        if primitive_arity == 0:
            self._emit(Opcode.PRIM_0, name, head=head)
            return
        if primitive_arity == 1:
            self._emit(Opcode.PRIM_1, name, head=head)
            return
        if primitive_arity == 2 or name in _NON_STRICT_SYMBOLS:
            self._emit(Opcode.PRIM_2, name, head=head)
            return
        self._emit(Opcode.SYM, name, head=head)

    def _emit(
        self, opcode: Opcode, data: int | str | float | None, *, head: bool
    ) -> int:
        if isinstance(data, str):
            self._symbol_table.setdefault(data, len(self._symbol_table) + 1)
        self._instructions.append(Instruction(opcode, data, head))
        return len(self._instructions) - 1


def compile_expr(expr: Expr) -> ProgramImage:
    """Compile a THOR AST into deterministic linear RED2 graph memory."""
    return _Compiler().compile(expr)


def compile_definitions(definitions: Mapping[str, Expr]) -> DefinitionImage:
    """Compile top-level THOR definitions for native RED2 symbol lookup."""
    return DefinitionImage(
        {name: compile_expr(expr) for name, expr in definitions.items()}
    )

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, replace

from red2.instructions import (
    DefinitionImage,
    Instruction,
    Opcode,
    ProgramImage,
)
from red2.representation import MuredOpcode, Word
from thor.ast import (
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

_STRICT_UNARY_PRIMITIVES = frozenset(
    {
        "1-",
        "1+",
        "ABS",
        "CAR",
        "CDR",
        "CEILING",
        "EVEN?",
        "FLOOR",
        "MINUS",
        "NULL?",
        "NOT",
        "TAG",
        "INTEGER?",
        "FLOAT?",
        "CHAR?",
        "SYMBOL?",
        "STRUCTURE?",
        "IO-RETURN",
        "UART-TX",
        "UART-TX-BYTES",
    }
)
_STRICT_BINARY_PRIMITIVES = frozenset(
    {
        "+",
        "-",
        "*",
        "/",
        "<",
        ">",
        "<=",
        ">=",
        "=",
        "CONS",
        "EQUAL?",
        "EXPT",
        "MAX",
        "MIN",
        "MOD",
    }
)
_NON_STRICT_PRIMITIVES = frozenset(
    {"IF", "Y", "AND", "OR", "IO-BIND", "IO-THEN", "CLOCK", "UART-RX"}
)


def compile_lambda(
    expr: Expr,
    *,
    definition_names: Collection[str] = (),
    unary_primitive_names: Collection[str] = (),
) -> tuple[Word, ...]:
    words: list[Word] = []
    visible_definitions = frozenset(definition_names)
    visible_unary_primitives = _STRICT_UNARY_PRIMITIVES | frozenset(
        unary_primitive_names
    )

    def compile_var_index(
        index: int,
        scope: tuple[str | None, ...],
        name: str | None = None,
    ) -> int:
        if name is not None and name in scope:
            return scope.index(name)
        source_index = 0
        synthetic_slots = 0
        for compiled_index, scope_name in enumerate(scope):
            if scope_name is None:
                synthetic_slots += 1
                continue
            if source_index == index:
                return compiled_index
            source_index += 1
        return index + synthetic_slots

    def compile_inline_argument(
        node: Expr,
        scope: tuple[str | None, ...],
    ) -> int | None:
        if isinstance(node, Var):
            return compile_var_index(node.index, scope, node.name)
        if isinstance(node, Symbol) and node.name in scope:
            return scope.index(node.name)
        return None

    def compile_graph(
        node: Expr,
        scope: tuple[str | None, ...],
        *,
        head: bool,
    ) -> None:
        if isinstance(node, Var):
            words.append(
                Word(
                    MuredOpcode.VAR,
                    compile_var_index(node.index, scope, node.name),
                    head,
                )
            )
            return
        if isinstance(node, Symbol):
            if node.name in scope:
                words.append(Word(MuredOpcode.VAR, scope.index(node.name), head))
            elif node.name in visible_definitions:
                words.append(Word(MuredOpcode.SYM, node.name, head))
            elif node.name in visible_unary_primitives:
                words.append(Word(MuredOpcode.PRIM_1, node.name, head))
            elif node.name in _STRICT_BINARY_PRIMITIVES:
                words.append(Word(MuredOpcode.PRIM_2, node.name, head))
            elif node.name in _NON_STRICT_PRIMITIVES:
                words.append(Word(MuredOpcode.PRIM_0, node.name, head))
            else:
                words.append(Word(MuredOpcode.SYM, node.name, head))
            return
        if isinstance(node, Integer):
            words.append(Word(MuredOpcode.INT, node.value, head))
            return
        if isinstance(node, Float):
            words.append(Word(MuredOpcode.FLOAT, node.value, head))
            return
        if isinstance(node, Char):
            words.append(Word(MuredOpcode.CHAR, node.value, head))
            return
        if isinstance(node, Lambda):
            for parameter in node.params:
                words.append(Word(MuredOpcode.LAMBDA, parameter, False))
            compile_graph(
                node.body,
                tuple(reversed(node.params)) + scope,
                head=head,
            )
            return
        if isinstance(node, LetRec):
            names = tuple(binding.name for binding in node.bindings)
            recursive_scope = tuple(reversed(names)) + scope
            block_start = len(words)
            words.extend(Word(MuredOpcode.RBLOCK) for _ in node.bindings)
            words.append(Word(MuredOpcode.RUP, len(node.bindings), False))
            compile_graph(node.body, recursive_scope, head=head)
            for offset, binding in enumerate(node.bindings):
                binding_address = len(words)
                words[block_start + offset] = Word(
                    MuredOpcode.RBLOCK,
                    binding_address,
                    False,
                )
                words.append(Word(MuredOpcode.SYM, binding.name, False))
                compile_graph(binding.expr, recursive_scope, head=True)
            return
        if isinstance(node, StructLit):
            words.append(Word(MuredOpcode.STRUCT, node.tag, False))
            app_start = len(words)
            fields = tuple(reversed(node.fields))
            words.extend(Word(MuredOpcode.APP) for _ in fields)
            words.append(Word(MuredOpcode.VAR, 0, head))
            field_scope = (None, *scope)
            for offset, field in enumerate(fields):
                field_address = len(words)
                words[app_start + offset] = Word(
                    MuredOpcode.APP,
                    field_address,
                    False,
                )
                compile_graph(field, field_scope, head=True)
            return
        if isinstance(node, App):
            if not node.items:
                words.append(Word(MuredOpcode.PNP, head=head))
                return
            operator = node.items[0]
            if (
                isinstance(operator, Symbol)
                and operator.name not in visible_definitions
                and operator.name in {"AND", "OR"}
            ):
                arguments = node.items[1:]
                identity = Symbol("TRUE" if operator.name == "AND" else "FALSE")
                short_circuit = Symbol("FALSE" if operator.name == "AND" else "TRUE")
                expanded: Expr = identity
                for argument in reversed(arguments):
                    if operator.name == "AND":
                        expanded = App(
                            (Symbol("IF"), argument, expanded, short_circuit)
                        )
                    else:
                        expanded = App(
                            (Symbol("IF"), argument, short_circuit, expanded)
                        )
                compile_graph(expanded, scope, head=head)
                return
            if len(node.items) == 1:
                compile_graph(node.items[0], scope, head=head)
                return
            app_start = len(words)
            arguments = tuple(reversed(node.items[1:]))
            inline_indices = tuple(
                compile_inline_argument(argument, scope) for argument in arguments
            )
            words.extend(
                Word(MuredOpcode.APP_VAR, index, False)
                if index is not None
                else Word(MuredOpcode.APP)
                for index in inline_indices
            )
            compile_graph(node.items[0], scope, head=True)
            for offset, argument in enumerate(arguments):
                if inline_indices[offset] is not None:
                    continue
                argument_address = len(words)
                words[app_start + offset] = Word(
                    MuredOpcode.APP, argument_address, False
                )
                compile_graph(argument, scope, head=True)
            return
        raise TypeError(
            f"pure λ-calculus expression required, got {type(node).__name__}"
        )

    compile_graph(expr, (), head=True)
    return tuple(words)


Scope = tuple[str, ...]


def _canonical_struct_constructor(
    tag: str,
    accessors: tuple[str, ...],
    expr: Expr | None,
) -> bool:
    if not isinstance(expr, Lambda) or expr.params != accessors:
        return False
    body = expr.body
    return (
        isinstance(body, StructLit)
        and body.tag == tag
        and body.fields == tuple(Symbol(accessor) for accessor in accessors)
    )


def _generated_struct_selector(
    expr: Expr,
    definitions: Mapping[str, Expr],
) -> tuple[str, int] | None:
    if not isinstance(expr, Lambda) or len(expr.params) != 1:
        return None
    tag = expr.params[0]
    body = expr.body
    if (
        not isinstance(body, App)
        or len(body.items) != 2
        or body.items[0] != Symbol(tag)
        or not isinstance(body.items[1], Lambda)
    ):
        return None
    selector = body.items[1]
    if not isinstance(selector.body, Symbol):
        return None
    accessors = selector.params
    accessor = selector.body.name
    if accessor not in accessors:
        return None
    if not _canonical_struct_constructor(
        tag,
        accessors,
        definitions.get(f"make-{tag}"),
    ):
        return None
    return tag, len(accessors) - accessors.index(accessor)


# Private EQUAL* / comparison-control symbols are generated only by AbstractRED2Machine.
# Serialized/compiler-visible RED2 remains the historical public EQUAL? primitive.
_PUBLIC_STRUCTURAL_EQUALITY = "EQUAL?"


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
    _PUBLIC_STRUCTURAL_EQUALITY: 2,
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

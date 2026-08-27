from __future__ import annotations

from thor_spec.ast import (
    App,
    Binding,
    Char,
    Definition,
    Expr,
    Float,
    Integer,
    Lambda,
    LetRec,
    Program,
    StructDef,
    StructLit,
    Symbol,
    TopLevel,
)

_SYMBOL_ALIASES = {
    "lambda": "LAMBDA",
    "if": "IF",
    "and": "AND",
    "or": "OR",
    "letrec": "LETREC",
    "nil": "NIL",
    "car": "CAR",
    "cdr": "CDR",
    "cons": "CONS",
    "null?": "NULL?",
    "equal?": "EQUAL?",
    "minus": "MINUS",
    "abs": "ABS",
    "floor": "FLOOR",
    "ceiling": "CEILING",
    "expt": "EXPT",
    "max": "MAX",
    "min": "MIN",
    "mod": "MOD",
    "even?": "EVEN?",
    "true": "TRUE",
    "false": "FALSE",
}


def normalize_expr(expr: Expr) -> Expr:
    """Normalize source-level aliases in an expression."""
    return _normalize_expr(expr, ())


def normalize_program(program: Program) -> Program:
    """Normalize all expressions contained in a parsed source program."""
    return Program(tuple(_normalize_top_level(form) for form in program.forms))


def desugar_let(bindings: tuple[Binding, ...], body: Expr) -> App:
    """Desugar ``LET`` bindings to a lambda application."""
    return App(
        (
            Lambda(tuple(binding.name for binding in bindings), body),
            *(binding.expr for binding in bindings),
        )
    )


def _normalize_top_level(form: TopLevel) -> TopLevel:
    if isinstance(form, Definition):
        return Definition(form.name, normalize_expr(form.expr))
    if isinstance(form, StructDef):
        return form
    return normalize_expr(form)


def _normalize_expr(expr: Expr, scope: tuple[str, ...]) -> Expr:
    if isinstance(expr, Lambda):
        return Lambda(expr.params, _normalize_expr(expr.body, expr.params + scope))
    if isinstance(expr, App):
        return App(tuple(_normalize_expr(item, scope) for item in expr.items))
    if isinstance(expr, LetRec):
        names = tuple(binding.name for binding in expr.bindings)
        binding_scope = names + scope
        return LetRec(
            tuple(
                Binding(
                    binding.name,
                    _normalize_expr(binding.expr, binding_scope),
                )
                for binding in expr.bindings
            ),
            _normalize_expr(expr.body, binding_scope),
        )
    if isinstance(expr, StructLit):
        return StructLit(
            expr.tag,
            tuple(_normalize_expr(field, scope) for field in expr.fields),
        )
    if isinstance(expr, Symbol):
        if expr.name in scope:
            return expr
        return Symbol(_SYMBOL_ALIASES.get(expr.name.lower(), expr.name))
    if isinstance(expr, Integer | Float | Char):
        return expr
    return expr

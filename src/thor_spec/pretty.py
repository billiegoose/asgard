from __future__ import annotations

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


def to_source(expr: Expr) -> str:
    """Render a THOR expression as stable source text."""
    if isinstance(expr, Var):
        return expr.name if expr.name is not None else f"(VAR {expr.index})"
    if isinstance(expr, Lambda):
        params = " ".join(expr.params)
        return f"(LAMBDA ({params}) {to_source(expr.body)})"
    if isinstance(expr, App):
        return f"({' '.join(to_source(item) for item in expr.items)})"
    if isinstance(expr, LetRec):
        bindings = " ".join(
            f"({binding.name} {to_source(binding.expr)})" for binding in expr.bindings
        )
        return f"(LETREC ({bindings}) {to_source(expr.body)})"
    if isinstance(expr, StructLit):
        list_source = _list_source(expr)
        if list_source is not None:
            return list_source
        fields = " ".join(to_source(field) for field in expr.fields)
        return f"{{{expr.tag}{f' {fields}' if fields else ''}}}"
    if isinstance(expr, Symbol):
        return expr.name
    if isinstance(expr, Integer):
        return str(expr.value)
    if isinstance(expr, Float):
        return str(expr.value)
    if isinstance(expr, Char):
        return _char_source(expr.value)


def _list_source(expr: StructLit) -> str | None:
    flattened = _flatten_pair(expr)
    if flattened is None:
        return None
    items, tail = flattened
    item_text = " ".join(to_source(item) for item in items)
    if isinstance(tail, Symbol) and tail.name == "NIL":
        return f"[{item_text}]"
    if item_text:
        return f"[{item_text} | {to_source(tail)}]"
    return f"[| {to_source(tail)}]"


def _flatten_pair(expr: Expr) -> tuple[list[Expr], Expr] | None:
    if not isinstance(expr, StructLit) or expr.tag != "PAIR" or len(expr.fields) != 2:
        return None
    items: list[Expr] = []
    tail: Expr = expr
    while isinstance(tail, StructLit) and tail.tag == "PAIR" and len(tail.fields) == 2:
        head, tail = tail.fields
        items.append(head)
    return items, tail


def _char_source(value: str) -> str:
    names = {" ": "space", "\n": "newline", "\t": "tab"}
    return f"#\\{names.get(value, value)}"

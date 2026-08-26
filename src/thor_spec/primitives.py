from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from dataclasses import dataclass
from operator import add, mul, sub, truediv
from typing import Protocol

from thor_spec.ast import (
    App,
    Char,
    Expr,
    Float,
    Integer,
    Lambda,
    StructLit,
    Symbol,
    Var,
)

TRUE = Symbol("TRUE")
FALSE = Symbol("FALSE")


class ReducerProtocol(Protocol):
    @property
    def remaining(self) -> int: ...

    def reduce(self, value: object, store: tuple[object, ...], phi: int) -> Expr: ...

    def reduce_no_contract(
        self,
        value: object,
        store: tuple[object, ...],
        phi: int,
    ) -> Expr: ...

    def contract(self) -> None: ...


@dataclass(frozen=True, slots=True)
class EvalState:
    reducer: ReducerProtocol
    store: tuple[object, ...]
    phi: int


def install_struct_accessors(
    tag: str,
    accessors: tuple[str, ...],
    definitions: MutableMapping[str, Expr],
) -> None:
    """Install lambda encodings for structure selector definitions.

    The generated accessor for ``CAR`` in ``PAIR |= CAR CDR`` is equivalent to
    ``(LAMBDA (PAIR) (PAIR (LAMBDA (CAR CDR) CAR)))``.
    """
    for accessor in accessors:
        definitions[accessor] = Lambda(
            (tag,),
            App((Symbol(tag), Lambda(accessors, Symbol(accessor)))),
        )


def try_reduce_primitive(app: App, state: EvalState) -> Expr | None:
    if not app.items or not isinstance(app.items[0], Symbol):
        return None
    name = app.items[0].name
    args = app.items[1:]
    if name == "IF":
        return _reduce_if(args, state)
    if name == "Y":
        return _reduce_y(args, state)
    if name == "AND":
        return _reduce_logical(args, state, true_identity=True)
    if name == "OR":
        return _reduce_logical(args, state, true_identity=False)
    if name in _UNARY_PRIMITIVES:
        return _reduce_unary(name, args, state)
    if name in _BINARY_PRIMITIVES:
        return _reduce_binary(name, args, state)
    if name in _TYPE_PREDICATES:
        return _reduce_type_predicate(name, args, state)
    return None


def _reduce_if(args: tuple[Expr, ...], state: EvalState) -> Expr | None:
    if len(args) != 3:
        return None
    condition = state.reducer.reduce(args[0], state.store, state.phi)
    true_branch, false_branch = args[1], args[2]
    if _is_true(condition):
        if state.reducer.remaining == 0:
            return App((Symbol("IF"), condition, true_branch, false_branch))
        state.reducer.contract()
        return state.reducer.reduce(true_branch, state.store, state.phi)
    if _is_false(condition):
        if state.reducer.remaining == 0:
            return App((Symbol("IF"), condition, true_branch, false_branch))
        state.reducer.contract()
        return state.reducer.reduce(false_branch, state.store, state.phi)
    return App(
        (
            Symbol("IF"),
            condition,
            state.reducer.reduce_no_contract(true_branch, state.store, state.phi),
            state.reducer.reduce_no_contract(false_branch, state.store, state.phi),
        )
    )


def _reduce_y(args: tuple[Expr, ...], state: EvalState) -> Expr | None:
    if len(args) != 1 or state.reducer.remaining == 0:
        return None
    arg = args[0]
    state.reducer.contract()
    recursive_app = App((arg, App((Symbol("Y"), arg))))
    return state.reducer.reduce(recursive_app, state.store, state.phi)


def _reduce_logical(
    args: tuple[Expr, ...],
    state: EvalState,
    *,
    true_identity: bool,
) -> Expr | None:
    if not args:
        return TRUE if true_identity else FALSE
    operator = "AND" if true_identity else "OR"
    reduced_args: list[Expr] = []
    for arg in args:
        reduced = state.reducer.reduce(arg, state.store, state.phi)
        if state.reducer.remaining > 0:
            if true_identity and _is_false(reduced):
                state.reducer.contract()
                return FALSE
            if not true_identity and _is_true(reduced):
                state.reducer.contract()
                return TRUE
            if (true_identity and _is_true(reduced)) or (
                not true_identity and _is_false(reduced)
            ):
                state.reducer.contract()
                continue
        reduced_args.append(reduced)
    if not reduced_args:
        return TRUE if true_identity else FALSE
    return App((Symbol(operator), *reduced_args))


def _reduce_unary(name: str, args: tuple[Expr, ...], state: EvalState) -> Expr | None:
    if len(args) != 1:
        return None
    arg = state.reducer.reduce(args[0], state.store, state.phi)
    if state.reducer.remaining == 0:
        return App((Symbol(name), arg))
    result: Expr | None = None
    if name == "1-" and isinstance(arg, Integer):
        result = Integer(arg.value - 1)
    elif name == "NOT" and _is_true(arg):
        result = FALSE
    elif name == "NOT" and _is_false(arg):
        result = TRUE
    elif name == "TAG" and isinstance(arg, StructLit):
        result = Symbol(arg.tag)
    if result is None:
        return App((Symbol(name), arg))
    state.reducer.contract()
    return result


def _reduce_binary(name: str, args: tuple[Expr, ...], state: EvalState) -> Expr | None:
    if len(args) != 2:
        return None
    left = state.reducer.reduce(args[0], state.store, state.phi)
    right = state.reducer.reduce(args[1], state.store, state.phi)
    if state.reducer.remaining == 0:
        return App((Symbol(name), left, right))
    result = _apply_binary(name, left, right)
    if result is None:
        return App((Symbol(name), left, right))
    state.reducer.contract()
    return result


def _reduce_type_predicate(
    name: str,
    args: tuple[Expr, ...],
    state: EvalState,
) -> Expr | None:
    if len(args) != 1:
        return None
    arg = state.reducer.reduce(args[0], state.store, state.phi)
    if state.reducer.remaining == 0:
        return App((Symbol(name), arg))
    if _predicate_matches(name, arg):
        state.reducer.contract()
        return TRUE
    if isinstance(arg, App | Var):
        return App((Symbol(name), arg))
    state.reducer.contract()
    return FALSE


def _apply_binary(name: str, left: Expr, right: Expr) -> Expr | None:
    if name in {"+", "-", "*", "/", "<", ">"}:
        if not isinstance(left, Integer | Float) or not isinstance(
            right, Integer | Float
        ):
            return None
        if name == "<":
            return TRUE if left.value < right.value else FALSE
        if name == ">":
            return TRUE if left.value > right.value else FALSE
        if name == "/":
            value = truediv(left.value, right.value)
            if (
                isinstance(left, Integer)
                and isinstance(right, Integer)
                and value.is_integer()
            ):
                return Integer(int(value))
            return Float(value)
        op = {"+": add, "-": sub, "*": mul}[name]
        value = op(left.value, right.value)
        if isinstance(left, Integer) and isinstance(right, Integer):
            return Integer(int(value))
        return Float(float(value))
    if name == "=":
        return _constant_equal(left, right)
    if name == "EQUAL?":
        return TRUE if _alpha_equal(left, right) else FALSE
    return None


def _predicate_matches(name: str, arg: Expr) -> bool:
    return (
        (name == "INTEGER?" and isinstance(arg, Integer))
        or (name == "FLOAT?" and isinstance(arg, Float))
        or (name == "CHAR?" and isinstance(arg, Char))
        or (name == "SYMBOL?" and isinstance(arg, Symbol))
        or (name == "STRUCTURE?" and isinstance(arg, StructLit))
    )


def _constant_equal(left: Expr, right: Expr) -> Expr | None:
    constant_types = Integer | Float | Char | Symbol
    if not isinstance(left, constant_types) or not isinstance(right, constant_types):
        return None
    return TRUE if left == right else FALSE


def _alpha_equal(left: Expr, right: Expr) -> bool:
    return _canonical(left, ()) == _canonical(right, ())


def _canonical(expr: Expr, names: Sequence[str]) -> object:
    if isinstance(expr, Lambda):
        return (
            "lambda",
            len(expr.params),
            _canonical(expr.body, (*expr.params, *names)),
        )
    if isinstance(expr, App):
        return ("app", tuple(_canonical(item, names) for item in expr.items))
    if isinstance(expr, StructLit):
        return (
            "struct",
            expr.tag,
            tuple(_canonical(field, names) for field in expr.fields),
        )
    if isinstance(expr, Var):
        return ("var", expr.index)
    return expr


def _is_true(expr: Expr) -> bool:
    return isinstance(expr, Symbol) and expr.name == "TRUE"


def _is_false(expr: Expr) -> bool:
    return isinstance(expr, Symbol) and expr.name == "FALSE"


_UNARY_PRIMITIVES = {"1-", "NOT", "TAG"}
_BINARY_PRIMITIVES = {"+", "-", "*", "/", "<", ">", "=", "EQUAL?"}
_TYPE_PREDICATES = {"INTEGER?", "FLOAT?", "CHAR?", "SYMBOL?", "STRUCTURE?"}

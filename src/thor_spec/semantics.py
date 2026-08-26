from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import assert_never

from thor_spec.ast import (
    App,
    Binding,
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


@dataclass(frozen=True, slots=True)
class ReductionResult:
    expr: Expr
    remaining: int
    phi: int
    steps: int


@dataclass(frozen=True, slots=True)
class Closure:
    expr: Expr
    store: RedexStore


@dataclass(frozen=True, slots=True)
class UBV:
    index: int
    name: str | None = None


type RuntimeValue = Expr | Closure | UBV
type RedexStore = tuple[RuntimeValue, ...]


def translate(expr: Expr, scope: tuple[str, ...] = ()) -> Expr:
    """Translate bound source symbols to De Bruijn variables.

    Figure 3.1 represents variables by position in the current redex store.  The
    parser keeps source symbols, so this pass rewrites only symbols bound by the
    lexical lambda/letrec scope and leaves constants and free symbols unchanged.
    """
    if isinstance(expr, Var | Integer | Float | Char):
        return expr
    if isinstance(expr, Symbol):
        try:
            return Var(scope.index(expr.name), expr.name)
        except ValueError:
            return expr
    if isinstance(expr, Lambda):
        return Lambda(expr.params, translate(expr.body, expr.params + scope))
    if isinstance(expr, App):
        return App(tuple(translate(item, scope) for item in expr.items))
    if isinstance(expr, LetRec):
        names = tuple(binding.name for binding in expr.bindings)
        binding_scope = names + scope
        return LetRec(
            tuple(
                Binding(binding.name, translate(binding.expr, binding_scope))
                for binding in expr.bindings
            ),
            translate(expr.body, binding_scope),
        )
    if isinstance(expr, StructLit):
        return StructLit(
            expr.tag,
            tuple(translate(field, scope) for field in expr.fields),
        )
    assert_never(expr)


def reduce_expr(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | None = None,
) -> ReductionResult:
    """Reduce a THOR expression with the Chapter 3 core rules.

    ``quantum`` limits contractions (beta contraction and symbol definition
    expansion).  Store dereferences, closure entry, and UBV reification are the
    bookkeeping rules and may still rebuild the expression when no contraction
    quantum remains.
    """
    reducer = _Reducer(_translate_definitions(definitions or {}), quantum)
    reduced = reducer.reduce(translate(expr), (), 0)
    return ReductionResult(reduced, reducer.remaining, 0, reducer.steps)


class _Reducer:
    def __init__(self, definitions: Mapping[str, Expr], quantum: int) -> None:
        self.definitions = definitions
        self.remaining = max(quantum, 0)
        self.steps = 0

    def reduce(self, value: RuntimeValue, store: RedexStore, phi: int) -> Expr:
        if isinstance(value, Closure):
            return self.reduce(value.expr, value.store, phi)
        if isinstance(value, UBV):
            return Var(phi - value.index, value.name)
        if isinstance(value, Var):
            if 0 <= value.index < len(store):
                return self.reduce(store[value.index], store, phi)
            return value
        if isinstance(value, Lambda):
            placeholders = tuple(
                UBV(phi + len(value.params) - offset, name)
                for offset, name in enumerate(value.params)
            )
            return Lambda(
                value.params,
                self.reduce(value.body, placeholders + store, phi + len(value.params)),
            )
        if isinstance(value, App):
            return self._reduce_app(value, store, phi)
        if isinstance(value, Symbol):
            definition = self.definitions.get(value.name)
            if definition is None or self.remaining == 0:
                return value
            self._contract()
            return self.reduce(definition, store, phi)
        if isinstance(value, LetRec | StructLit):
            return value
        if isinstance(value, Integer | Float | Char):
            return value
        assert_never(value)

    def _reduce_app(self, app: App, store: RedexStore, phi: int) -> Expr:
        if not app.items:
            return app
        operator = self.reduce(app.items[0], store, phi)
        arguments = app.items[1:]
        if (
            isinstance(operator, Lambda)
            and operator.params
            and arguments
            and self.remaining > 0
        ):
            return self._contract_lambda(operator, arguments, store, phi)
        return App((operator, *arguments))

    def _contract_lambda(
        self,
        operator: Lambda,
        arguments: tuple[Expr, ...],
        store: RedexStore,
        phi: int,
    ) -> Expr:
        bind_count = min(len(operator.params), len(arguments), self.remaining)
        self.remaining -= bind_count
        self.steps += bind_count
        closures = tuple(
            Closure(argument, store) for argument in arguments[:bind_count]
        )
        if bind_count == len(operator.params):
            reduced: Expr = self.reduce(operator.body, closures + store, phi)
        else:
            reduced = Lambda(operator.params[bind_count:], operator.body)
            reduced = self.reduce(reduced, closures + store, phi)
        remaining_arguments = arguments[bind_count:]
        if remaining_arguments:
            return self.reduce(App((reduced, *remaining_arguments)), store, phi)
        return reduced

    def _contract(self) -> None:
        self.remaining -= 1
        self.steps += 1


def _translate_definitions(definitions: Mapping[str, Expr]) -> dict[str, Expr]:
    return {name: translate(expr) for name, expr in definitions.items()}

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from thor_spec.ast import (
    App,
    Binding,
    Block,
    Char,
    Expr,
    Float,
    Integer,
    Lambda,
    LetRec,
    Rec,
    StructLit,
    Symbol,
    Var,
)
from thor_spec.primitives import EvalState, try_reduce_primitive


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
type RedexStore = tuple[object, ...]


def translate(expr: Expr, scope: tuple[str, ...] = ()) -> Expr:
    """Translate bound source symbols to De Bruijn variables."""
    if isinstance(expr, Var | Integer | Float | Char | Block | Rec):
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
    msg = f"unsupported THOR expression: {expr!r}"
    raise TypeError(msg)


def reduce_expr(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | None = None,
) -> ReductionResult:
    """Reduce a THOR expression with the Chapter 3 abstract interpreter."""
    reducer = _Reducer(_translate_definitions(definitions or {}), quantum)
    reduced = reducer.reduce(translate(expr), (), 0)
    return ReductionResult(reduced, reducer.remaining, 0, reducer.steps)


class _Reducer:
    def __init__(self, definitions: Mapping[str, Expr], quantum: int) -> None:
        self.definitions = definitions
        self._remaining = max(quantum, 0)
        self.steps = 0

    @property
    def remaining(self) -> int:
        return self._remaining

    def reduce(self, value: object, store: RedexStore, phi: int) -> Expr:
        if isinstance(value, Closure):
            return self.reduce(value.expr, value.store, phi)
        if isinstance(value, UBV):
            return Var(phi - value.index, value.name)
        if isinstance(value, Var):
            if 0 <= value.index < len(store):
                return self.reduce(store[value.index], store, phi)
            return value
        if isinstance(value, Rec):
            return self._reduce_rec(value, store, phi)
        if isinstance(value, Block):
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
            self.contract()
            return self.reduce(definition, store, phi)
        if isinstance(value, LetRec):
            return self._reduce_letrec(value, store, phi)
        if isinstance(value, StructLit):
            return self._reduce_struct(value, store, phi)
        if isinstance(value, Integer | Float | Char):
            return value
        msg = f"unsupported runtime value: {value!r}"
        raise TypeError(msg)

    def reduce_no_contract(self, value: object, store: RedexStore, phi: int) -> Expr:
        saved = self._remaining
        self._remaining = 0
        try:
            return self.reduce(value, store, phi)
        finally:
            self._remaining = saved

    def contract(self) -> None:
        if self._remaining <= 0:
            msg = "cannot contract after quantum expiry"
            raise RuntimeError(msg)
        self._remaining -= 1
        self.steps += 1

    def _reduce_app(self, app: App, store: RedexStore, phi: int) -> Expr:
        if not app.items:
            return app
        operator = self.reduce(app.items[0], store, phi)
        arguments = app.items[1:]
        primitive = try_reduce_primitive(
            App((operator, *arguments)),
            EvalState(self, store, phi),
        )
        if primitive is not None:
            return primitive
        if (
            isinstance(operator, Lambda)
            and operator.params
            and arguments
            and self.remaining > 0
        ):
            return self._contract_lambda(operator, arguments, store, phi)
        if isinstance(operator, StructLit) and arguments:
            return self._contract_structure(operator, arguments, store, phi)
        return self._rebuild_app(operator, arguments, store, phi)

    def _contract_lambda(
        self,
        operator: Lambda,
        arguments: tuple[Expr, ...],
        store: RedexStore,
        phi: int,
    ) -> Expr:
        bind_count = min(len(operator.params), len(arguments), self.remaining)
        for _ in range(bind_count):
            self.contract()
        closures = tuple(
            Closure(argument, store) for argument in arguments[:bind_count]
        )
        remaining_params = operator.params[bind_count:]
        if not remaining_params:
            reduced: Expr = self.reduce(operator.body, closures + store, phi)
        else:
            placeholder_store = _ubv_store(remaining_params, phi)
            body_store = closures + placeholder_store + store
            body_phi = phi + len(remaining_params)
            reduced = Lambda(
                remaining_params,
                self.reduce(operator.body, body_store, body_phi),
            )
        remaining_arguments = arguments[bind_count:]
        if remaining_arguments:
            return self.reduce(App((reduced, *remaining_arguments)), store, phi)
        return reduced

    def _contract_structure(
        self,
        operator: StructLit,
        arguments: tuple[Expr, ...],
        store: RedexStore,
        phi: int,
    ) -> Expr:
        selector = self.reduce(arguments[0], store, phi)
        if not isinstance(selector, Lambda) or self.remaining == 0:
            return self._rebuild_app(operator, (selector, *arguments[1:]), store, phi)
        self.contract()
        bind_count = min(len(selector.params), len(operator.fields))
        closures = tuple(
            Closure(field, store) for field in operator.fields[:bind_count]
        )
        if bind_count == len(selector.params):
            reduced: Expr = self.reduce(selector.body, closures + store, phi)
        else:
            reduced = Lambda(selector.params[bind_count:], selector.body)
            reduced = self.reduce(reduced, closures + store, phi)
        if arguments[1:]:
            return self.reduce(App((reduced, *arguments[1:])), store, phi)
        return reduced

    def _rebuild_app(
        self,
        operator: Expr,
        arguments: tuple[Expr, ...],
        store: RedexStore,
        phi: int,
    ) -> App:
        reduced_arguments = tuple(
            self.reduce_no_contract(argument, store, phi) for argument in arguments
        )
        return App((operator, *reduced_arguments))

    def _reduce_struct(self, struct: StructLit, store: RedexStore, phi: int) -> Expr:
        return StructLit(
            struct.tag,
            tuple(
                self.reduce_no_contract(field, store, phi) for field in struct.fields
            ),
        )

    def _reduce_letrec(self, letrec: LetRec, store: RedexStore, phi: int) -> Expr:
        if not letrec.bindings:
            return self.reduce(letrec.body, store, phi)
        names = tuple(binding.name for binding in letrec.bindings)
        expressions = tuple(binding.expr for binding in letrec.bindings)
        if self.remaining == 0:
            placeholder_store = _ubv_store(names, phi) + store
            binding_phi = phi + len(names)
            return LetRec(
                tuple(
                    Binding(
                        name,
                        self.reduce_no_contract(expr, placeholder_store, binding_phi),
                    )
                    for name, expr in zip(names, expressions, strict=True)
                ),
                self.reduce_no_contract(letrec.body, placeholder_store, binding_phi),
            )
        block = Block(expressions, names)
        recursive_store = _make_recursive_store(block, store)
        return self.reduce(letrec.body, recursive_store, phi)

    def _reduce_rec(self, rec: Rec, _store: RedexStore, phi: int) -> Expr:
        if self.remaining > 0:
            self.contract()
            return self.reduce(rec.block.expressions[rec.index], rec.store, phi)
        names = _block_names(rec.block)
        base_store = rec.store[len(rec.block.expressions) :]
        placeholder_store = _ubv_store(names, phi) + base_store
        binding_phi = phi + len(names)
        bindings = tuple(
            Binding(
                name,
                self.reduce_no_contract(expr, placeholder_store, binding_phi),
            )
            for name, expr in zip(names, rec.block.expressions, strict=True)
        )
        return LetRec(bindings, Var(rec.index, names[rec.index]))


def _make_recursive_store(block: Block, base_store: RedexStore) -> RedexStore:
    recs = [Rec(index, (), block) for index in range(len(block.expressions))]
    recursive_store: RedexStore = (*recs, *base_store)
    for rec in recs:
        object.__setattr__(rec, "store", recursive_store)
    return recursive_store


def _ubv_store(names: tuple[str, ...], phi: int) -> RedexStore:
    return tuple(
        UBV(phi + len(names) - offset, name)
        for offset, name in enumerate(names)
    )


def _block_names(block: Block) -> tuple[str, ...]:
    if block.names:
        return block.names
    return tuple(f"_{index}" for index in range(len(block.expressions)))


def _translate_definitions(definitions: Mapping[str, Expr]) -> dict[str, Expr]:
    return {name: translate(expr) for name, expr in definitions.items()}

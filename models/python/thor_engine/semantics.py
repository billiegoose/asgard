from __future__ import annotations

from collections.abc import Generator, Mapping
from dataclasses import dataclass

from thor_lang.ast import (
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
from thor_lang.primitives import EvalState, ReductionRequest, try_reduce_primitive


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
type _ReductionGenerator = Generator[ReductionRequest, Expr, Expr]


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
        self._no_contract_depth = 0
        self.steps = 0

    @property
    def remaining(self) -> int:
        return self._remaining

    def reduce(self, value: object, store: RedexStore, phi: int) -> Expr:
        return self._drive(self._reduce(value, store, phi))

    def reduce_no_contract(self, value: object, store: RedexStore, phi: int) -> Expr:
        saved = self._remaining
        self._remaining = 0
        self._no_contract_depth += 1
        try:
            return self._drive(self._reduce(value, store, phi))
        finally:
            self._no_contract_depth -= 1
            self._remaining = saved

    def _drive(self, initial: _ReductionGenerator) -> Expr:
        stack: list[tuple[_ReductionGenerator, int | None]] = [(initial, None)]
        result: Expr | None = None
        has_result = False
        while stack:
            generator, saved_quantum = stack[-1]
            try:
                if has_result:
                    assert result is not None
                    request = generator.send(result)
                else:
                    request = next(generator)
            except StopIteration as stopped:
                result = stopped.value
                stack.pop()
                if saved_quantum is not None:
                    self._no_contract_depth -= 1
                    self._remaining = saved_quantum
                has_result = True
                continue

            restore_quantum: int | None = None
            if request.no_contract:
                restore_quantum = self._remaining
                self._remaining = 0
                self._no_contract_depth += 1
            stack.append(
                (
                    self._reduce(request.value, request.store, request.phi),
                    restore_quantum,
                )
            )
            has_result = False

        assert result is not None
        return result

    def contract(self) -> None:
        if self._remaining <= 0:
            msg = "cannot contract after quantum expiry"
            raise RuntimeError(msg)
        self._remaining -= 1
        self.steps += 1

    def _reduce(
        self,
        value: object,
        store: RedexStore,
        phi: int,
    ) -> _ReductionGenerator:
        if isinstance(value, Closure):
            return (yield ReductionRequest(value.expr, value.store, phi))
        if isinstance(value, UBV):
            return Var(phi - value.index, value.name)
        if isinstance(value, Var):
            if 0 <= value.index < len(store):
                return (yield ReductionRequest(store[value.index], store, phi))
            return value
        if isinstance(value, Rec):
            return (yield from self._reduce_rec(value, phi))
        if isinstance(value, Block):
            return value
        if isinstance(value, Lambda):
            placeholders = _ubv_store(value.params, phi)
            body = yield ReductionRequest(
                value.body,
                placeholders + store,
                phi + len(value.params),
                no_contract=True,
            )
            return Lambda(value.params, body)
        if isinstance(value, App):
            return (yield from self._reduce_app(value, store, phi))
        if isinstance(value, Symbol):
            definition = self.definitions.get(value.name)
            if definition is None or self.remaining == 0:
                return value
            self.contract()
            return (yield ReductionRequest(definition, store, phi))
        if isinstance(value, LetRec):
            return (yield from self._reduce_letrec(value, store, phi))
        if isinstance(value, StructLit):
            fields: list[Expr] = []
            for field in value.fields:
                fields.append(
                    (
                        yield ReductionRequest(
                            field,
                            store,
                            phi,
                            no_contract=True,
                        )
                    )
                )
            return StructLit(value.tag, tuple(fields))
        if isinstance(value, Integer | Float | Char):
            return value
        msg = f"unsupported runtime value: {value!r}"
        raise TypeError(msg)

    def _reduce_app(
        self,
        app: App,
        store: RedexStore,
        phi: int,
    ) -> _ReductionGenerator:
        if not app.items:
            return app
        operator = yield ReductionRequest(app.items[0], store, phi)
        arguments = app.items[1:]
        primitive_reducer = try_reduce_primitive(
            App((operator, *arguments)),
            EvalState(self, store, phi),
        )
        if primitive_reducer is not None:
            primitive = yield from primitive_reducer
            if primitive is not None:
                return primitive
        if (
            isinstance(operator, Lambda)
            and operator.params
            and arguments
            and self.remaining > 0
        ):
            return (yield from self._contract_lambda(operator, arguments, store, phi))
        if isinstance(operator, StructLit) and arguments:
            return (
                yield from self._contract_structure(operator, arguments, store, phi)
            )
        return (yield from self._rebuild_app(operator, arguments, store, phi))

    def _contract_lambda(
        self,
        operator: Lambda,
        arguments: tuple[Expr, ...],
        store: RedexStore,
        phi: int,
    ) -> _ReductionGenerator:
        bind_count = min(len(operator.params), len(arguments), self.remaining)
        for _ in range(bind_count):
            self.contract()
        closures = tuple(
            Closure(argument, store) for argument in arguments[:bind_count]
        )
        remaining_params = operator.params[bind_count:]
        if not remaining_params:
            reduced = yield ReductionRequest(operator.body, closures + store, phi)
        else:
            placeholder_store = _ubv_store(remaining_params, phi)
            body_store = closures + placeholder_store + store
            body_phi = phi + len(remaining_params)
            body = yield ReductionRequest(operator.body, body_store, body_phi)
            reduced = Lambda(remaining_params, body)
        remaining_arguments = arguments[bind_count:]
        if remaining_arguments:
            return (
                yield ReductionRequest(
                    App((reduced, *remaining_arguments)),
                    store,
                    phi,
                )
            )
        return reduced

    def _contract_structure(
        self,
        operator: StructLit,
        arguments: tuple[Expr, ...],
        store: RedexStore,
        phi: int,
    ) -> _ReductionGenerator:
        selector = yield ReductionRequest(arguments[0], store, phi)
        if not isinstance(selector, Lambda) or self.remaining == 0:
            return (
                yield from self._rebuild_app(
                    operator,
                    (selector, *arguments[1:]),
                    store,
                    phi,
                )
            )
        self.contract()
        bind_count = min(len(selector.params), len(operator.fields))
        closures = tuple(
            Closure(field, store) for field in operator.fields[:bind_count]
        )
        if bind_count == len(selector.params):
            reduced = yield ReductionRequest(selector.body, closures + store, phi)
        else:
            partial = Lambda(selector.params[bind_count:], selector.body)
            reduced = yield ReductionRequest(partial, closures + store, phi)
        if arguments[1:]:
            return (
                yield ReductionRequest(App((reduced, *arguments[1:])), store, phi)
            )
        return reduced

    def _rebuild_app(
        self,
        operator: Expr,
        arguments: tuple[Expr, ...],
        store: RedexStore,
        phi: int,
    ) -> _ReductionGenerator:
        reduced_arguments: list[Expr] = []
        for argument in arguments:
            reduced_arguments.append(
                (
                    yield ReductionRequest(
                        argument,
                        store,
                        phi,
                        no_contract=True,
                    )
                )
            )
        return App((operator, *reduced_arguments))

    def _reduce_letrec(
        self,
        letrec: LetRec,
        store: RedexStore,
        phi: int,
    ) -> _ReductionGenerator:
        if not letrec.bindings:
            return (yield ReductionRequest(letrec.body, store, phi))
        names = tuple(binding.name for binding in letrec.bindings)
        expressions = tuple(binding.expr for binding in letrec.bindings)
        if self.remaining == 0:
            placeholder_store = _ubv_store(names, phi) + store
            binding_phi = phi + len(names)
            bindings: list[Binding] = []
            for name, expression in zip(names, expressions, strict=True):
                reduced = yield ReductionRequest(
                    expression,
                    placeholder_store,
                    binding_phi,
                    no_contract=True,
                )
                bindings.append(Binding(name, reduced))
            body = yield ReductionRequest(
                letrec.body,
                placeholder_store,
                binding_phi,
                no_contract=True,
            )
            return LetRec(tuple(bindings), body)
        block = Block(expressions, names)
        recursive_store = _make_recursive_store(block, store)
        return (yield ReductionRequest(letrec.body, recursive_store, phi))

    def _reduce_rec(self, rec: Rec, phi: int) -> _ReductionGenerator:
        if self.remaining > 0:
            self.contract()
            return (
                yield ReductionRequest(
                    rec.block.expressions[rec.index],
                    rec.store,
                    phi,
                )
            )
        names = _block_names(rec.block)
        base_store = rec.store[len(rec.block.expressions) :]
        placeholder_store = _ubv_store(names, phi) + base_store
        binding_phi = phi + len(names)
        bindings: list[Binding] = []
        for name, expression in zip(names, rec.block.expressions, strict=True):
            reduced = yield ReductionRequest(
                expression,
                placeholder_store,
                binding_phi,
                no_contract=True,
            )
            bindings.append(Binding(name, reduced))
        return LetRec(tuple(bindings), Var(rec.index, names[rec.index]))


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

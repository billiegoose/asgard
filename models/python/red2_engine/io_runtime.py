from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from thor_lang.ast import App, Expr, Integer, Lambda, LetRec, StructLit, Symbol
from thor_lang.pretty import to_source


class Red2IoRuntimeError(RuntimeError):
    """Raised when faithful RED2 cannot execute an IO action."""


class Red2IoHost(Protocol):
    def uart_rx(self) -> int | None: ...

    def uart_tx(self, data: bytes) -> None: ...

    def clock_ms(self) -> int: ...


@dataclass(frozen=True, slots=True)
class _BindFrame:
    continuation: Expr


@dataclass(frozen=True, slots=True)
class _ThenFrame:
    next_action: Expr


type _Frame = _BindFrame | _ThenFrame

_ZERO_ARG_ACTIONS = frozenset({"UART-RX", "CLOCK"})
_IO_SYMBOLS = frozenset(
    {
        "IO-RETURN",
        "IO-BIND",
        "IO-THEN",
        "UART-RX",
        "UART-TX",
        "UART-TX-BYTES",
        "CLOCK",
    }
)
_REDUCTION_BOUNDARIES = _IO_SYMBOLS | {"Y"}


def run_red2_io_action(
    action: Expr,
    *,
    definitions: Mapping[str, Expr],
    quantum: int,
    host: Red2IoHost,
) -> Expr:
    """Execute RED2-owned UART/CLOCK actions around the pure faithful machine."""
    if not _contains_symbol(action, definitions, _IO_SYMBOLS):
        msg = f"not an IO action: {to_source(action)}"
        raise Red2IoRuntimeError(msg)

    current = action
    frames: list[_Frame] = []

    while True:
        current = _resolve_bare_action(current, definitions)
        step = _step_action(
            current,
            frames=frames,
            definitions=definitions,
            quantum=quantum,
            host=host,
        )
        if isinstance(step, _NextAction):
            current = step.action
            continue

        if not frames:
            return step
        frame = frames.pop()
        if isinstance(frame, _ThenFrame):
            current = frame.next_action
            continue
        current = App((frame.continuation, step))


@dataclass(frozen=True, slots=True)
class _NextAction:
    action: Expr


def _step_action(
    action: Expr,
    *,
    frames: list[_Frame],
    definitions: Mapping[str, Expr],
    quantum: int,
    host: Red2IoHost,
) -> Expr | _NextAction:
    if isinstance(action, Symbol):
        if action.name == "UART-RX":
            byte = host.uart_rx()
            return Symbol("NIL") if byte is None else Integer(byte)
        if action.name == "CLOCK":
            return Integer(host.clock_ms())
        definition = definitions.get(action.name)
        if definition is not None:
            return _NextAction(definition)
        msg = f"not an IO action: {to_source(action)}"
        raise Red2IoRuntimeError(msg)

    if not isinstance(action, App) or not action.items:
        msg = f"not an IO action: {to_source(action)}"
        raise Red2IoRuntimeError(msg)

    operator = action.items[0]
    args = action.items[1:]
    if isinstance(operator, Symbol):
        name = operator.name
        if name == "IO-RETURN" and len(args) == 1:
            return _reduce_pure(args[0], definitions=definitions, quantum=quantum)
        if name == "IO-BIND" and len(args) == 2:
            frames.append(_BindFrame(args[1]))
            return _NextAction(args[0])
        if name == "IO-THEN" and len(args) == 2:
            frames.append(_ThenFrame(args[1]))
            return _NextAction(args[0])
        if name == "UART-RX" and not args:
            byte = host.uart_rx()
            return Symbol("NIL") if byte is None else Integer(byte)
        if name == "CLOCK" and not args:
            return Integer(host.clock_ms())
        if name == "UART-TX" and len(args) == 1:
            value = _reduce_pure(args[0], definitions=definitions, quantum=quantum)
            if not isinstance(value, Integer):
                msg = f"UART-TX expects an integer byte, got {to_source(value)}"
                raise Red2IoRuntimeError(msg)
            host.uart_tx(bytes((value.value % 256,)))
            return Symbol("NIL")
        if name == "UART-TX-BYTES" and len(args) == 1:
            value = _reduce_pure(args[0], definitions=definitions, quantum=quantum)
            host.uart_tx(_byte_list(value))
            return Symbol("NIL")
        if name == "IF" and len(args) == 3:
            condition = _reduce_pure(args[0], definitions=definitions, quantum=quantum)
            if isinstance(condition, Symbol) and condition.name == "TRUE":
                return _NextAction(args[1])
            if isinstance(condition, Symbol) and condition.name == "FALSE":
                return _NextAction(args[2])
            msg = (
                "IO IF condition did not reduce to TRUE or FALSE: "
                f"{to_source(condition)}"
            )
            raise Red2IoRuntimeError(msg)
        if name == "Y" and args:
            reduced = _reduce_pure(action, definitions=definitions, quantum=1)
            if reduced != action:
                return _NextAction(reduced)

    if isinstance(operator, Lambda):
        prepared_args = tuple(
            _prepare_action_argument(
                arg,
                definitions=definitions,
                quantum=quantum,
            )
            for arg in args
        )
        applied = App((operator, *prepared_args))
        reduced = _reduce_pure(applied, definitions=definitions, quantum=1)
        if reduced != applied:
            return _NextAction(reduced)

    reduced_operator = _reduce_pure(operator, definitions=definitions, quantum=1)
    if reduced_operator != operator:
        return _NextAction(App((reduced_operator, *args)))

    msg = f"unknown IO action: {to_source(action)}"
    raise Red2IoRuntimeError(msg)


def _prepare_action_argument(
    expr: Expr,
    *,
    definitions: Mapping[str, Expr],
    quantum: int,
) -> Expr:
    if _contains_symbol(expr, definitions, _REDUCTION_BOUNDARIES):
        return expr
    return _reduce_pure(expr, definitions=definitions, quantum=quantum)


def _resolve_bare_action(action: Expr, definitions: Mapping[str, Expr]) -> Expr:
    if not isinstance(action, Symbol):
        return action
    if action.name in _ZERO_ARG_ACTIONS:
        return App((action,))
    return definitions.get(action.name, action)


def _contains_symbol(
    expr: Expr,
    definitions: Mapping[str, Expr],
    names: frozenset[str],
) -> bool:
    stack = [expr]
    visited_definitions: set[str] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, Symbol):
            if current.name in names:
                return True
            if current.name not in visited_definitions:
                definition = definitions.get(current.name)
                if definition is not None:
                    visited_definitions.add(current.name)
                    stack.append(definition)
            continue
        if isinstance(current, App):
            stack.extend(current.items)
            continue
        if isinstance(current, Lambda):
            stack.append(current.body)
            continue
        if isinstance(current, StructLit):
            stack.extend(current.fields)
            continue
        if isinstance(current, LetRec):
            stack.append(current.body)
            stack.extend(binding.expr for binding in current.bindings)
    return False


def _reduce_pure(
    expr: Expr,
    *,
    definitions: Mapping[str, Expr],
    quantum: int,
) -> Expr:
    from thor_compile.red2 import load_faithful_machine

    machine = load_faithful_machine(
        expr,
        quantum=quantum,
        definitions=definitions,
    )
    machine.run(cycle_limit=2_000_000)
    return machine.result_expr()


def _byte_list(value: Expr) -> bytes:
    result = bytearray()
    cursor = value
    while isinstance(cursor, StructLit) and cursor.tag == "PAIR":
        if len(cursor.fields) != 2:
            break
        head, cursor = cursor.fields
        if not isinstance(head, Integer):
            msg = f"UART-TX-BYTES expects integer bytes, got {to_source(head)}"
            raise Red2IoRuntimeError(msg)
        result.append(head.value % 256)
    if isinstance(cursor, Symbol) and cursor.name == "NIL":
        return bytes(result)
    msg = f"UART-TX-BYTES expects a byte list, got {to_source(cursor)}"
    raise Red2IoRuntimeError(msg)

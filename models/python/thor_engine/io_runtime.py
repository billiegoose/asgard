import select
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO, assert_never

from red2_engine.machine import Red2DefinitionCache, Red2Machine, Red2ResourceLimits
from red2_engine.primitives import register_struct_accessors
from thor_compile.red2 import compile_definitions, compile_expr
from thor_engine.golden import ModelName
from thor_engine.semantics import ThorDefinitionCache, reduce_expr
from thor_lang.ast import (
    App,
    Binding,
    Block,
    Char,
    Definition,
    Expr,
    Float,
    Integer,
    Lambda,
    LetRec,
    Program,
    Rec,
    StructDef,
    StructLit,
    Symbol,
    Var,
)
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition


class IoRuntimeError(RuntimeError):
    """Raised when an expression is not a valid simulator IO action."""


class ClockSource(Protocol):
    def now_ms(self) -> int: ...


class SystemClockSource:
    def now_ms(self) -> int:
        return int(time.time() * 1000)


class LatestFileClockSource:
    def __init__(self, path: Path, *, initial_ms: int | None = None) -> None:
        self._path = path
        self._latest = int(time.time() * 1000) if initial_ms is None else initial_ms

    def now_ms(self) -> int:
        try:
            text = self._path.read_text()
        except OSError:
            return self._latest
        for line in text.splitlines():
            try:
                self._latest = int(line.strip())
            except ValueError:
                continue
        return self._latest


def run_io_source(
    source: str,
    *,
    model: ModelName,
    quantum: int,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    clock: ClockSource | None = None,
    resource_limits: Red2ResourceLimits | None = None,
) -> str:
    """Execute the last top-level expression as a simulated THOR IO action.

    IO mode reserves stdout for simulated UART bytes. The returned string is the
    final IO action value rendered as THOR source so the CLI can print
    diagnostics to stderr without consuming the simulated UART stream.
    """
    program = normalize_program(parse_program(source))
    definitions, action = _prepare_io_program(program)
    runtime = _IoRuntime(
        model=model,
        quantum=quantum,
        definitions=definitions,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        clock=clock or SystemClockSource(),
        resource_limits=resource_limits,
    )
    return to_source(runtime.run(action))


def _prepare_io_program(program: Program) -> tuple[dict[str, Expr], Expr]:
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    register_struct_accessors("PAIR", ("CAR", "CDR"))
    action: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
            continue
        if isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
            register_struct_accessors(form.tag, form.accessors)
            continue
        action = form
    if action is None:
        msg = "IO mode requires a final action expression"
        raise IoRuntimeError(msg)
    return definitions, action


@dataclass(frozen=True, slots=True)
class _BindCont:
    lambda_expr: Expr


@dataclass(frozen=True, slots=True)
class _ThenCont:
    next_action: Expr


@dataclass(frozen=True, slots=True)
class _NextAction:
    action: Expr


type _Continuation = _BindCont | _ThenCont

_ZERO_ARG_IO_ACTIONS = frozenset({"UART-RX", "TICKS", "CLOCK"})


class _IoRuntime:
    def __init__(
        self,
        *,
        model: ModelName,
        quantum: int,
        definitions: Mapping[str, Expr],
        stdin: TextIO,
        stdout: TextIO,
        stderr: TextIO,
        clock: ClockSource,
        resource_limits: Red2ResourceLimits | None,
    ) -> None:
        self._model = model
        self._quantum = quantum
        self._definitions = definitions
        self._thor_definition_cache = (
            ThorDefinitionCache.from_definitions(definitions)
            if model == "thor"
            else None
        )
        self._red2_definition_image = (
            compile_definitions(definitions) if model == "red2" else None
        )
        self._red2_definition_cache = (
            Red2DefinitionCache.from_image(self._red2_definition_image)
            if self._red2_definition_image is not None
            else None
        )
        self._stdin = stdin
        self._stdout = stdout
        self._stderr = stderr
        self._clock = clock
        self._resource_limits = resource_limits
        self._ticks = 0

    def run(self, action: Expr) -> Expr:
        current = action
        continuations: list[_Continuation] = []
        while True:
            step = self._run_current_action(current, continuations)
            if isinstance(step, _NextAction):
                current = step.action
                continue
            next_action = self._continue_after_result(step, continuations)
            if next_action is None:
                return step
            current = next_action

    def _run_current_action(
        self,
        action: Expr,
        continuations: list[_Continuation],
    ) -> Expr | _NextAction:
        action = self._resolve_action(action)
        if not isinstance(action, App):
            msg = f"not an IO action: {to_source(action)}"
            raise IoRuntimeError(msg)
        if not action.items:
            msg = f"not an IO action: {to_source(action)}"
            raise IoRuntimeError(msg)

        operator = action.items[0]
        args = action.items[1:]
        if isinstance(operator, Symbol):
            next_action = self._next_symbol_action(operator.name, args, continuations)
            if next_action is not None:
                return next_action
            return self._primitive_action_result(operator.name, args, action)

        reduced_operator = self._pure(operator)
        if isinstance(reduced_operator, Lambda):
            return _NextAction(_apply_lambda(reduced_operator, args))
        msg = f"not an IO action: {to_source(action)}"
        raise IoRuntimeError(msg)

    def _next_symbol_action(
        self,
        name: str,
        args: tuple[Expr, ...],
        continuations: list[_Continuation],
    ) -> _NextAction | None:
        if name == "IF" and len(args) == 3:
            condition = self._pure(args[0])
            if isinstance(condition, Symbol) and condition.name == "TRUE":
                return _NextAction(args[1])
            if isinstance(condition, Symbol) and condition.name == "FALSE":
                return _NextAction(args[2])
            msg = (
                "IO IF condition did not reduce to TRUE or FALSE: "
                f"{to_source(condition)}"
            )
            raise IoRuntimeError(msg)

        definition = self._definitions.get(name)
        if isinstance(definition, Lambda):
            return _NextAction(_apply_lambda(definition, args))
        if definition is not None:
            reduced_definition = self._pure(definition)
            if isinstance(reduced_definition, Lambda):
                return _NextAction(_apply_lambda(reduced_definition, args))
            if not args:
                return _NextAction(reduced_definition)

        if name == "IO-BIND" and len(args) == 2:
            continuations.append(_BindCont(args[1]))
            return _NextAction(args[0])
        if name == "IO-THEN" and len(args) == 2:
            continuations.append(_ThenCont(args[1]))
            return _NextAction(args[0])
        return None

    def _primitive_action_result(
        self,
        name: str,
        args: tuple[Expr, ...],
        action: App,
    ) -> Expr:
        if name == "IO-RETURN" and len(args) == 1:
            return self._pure(args[0])
        if name == "UART-TX" and len(args) == 1:
            byte = self._integer_arg(name, args[0])
            self._stdout.write(chr(byte % 256))
            self._stdout.flush()
            return Symbol("NIL")
        if name == "UART-TX-BYTES" and len(args) == 1:
            self._stdout.write(
                "".join(chr(byte % 256) for byte in self._byte_list_arg(name, args[0]))
            )
            self._stdout.flush()
            return Symbol("NIL")
        if name == "UART-RX" and not args:
            if not _text_stream_has_ready_input(self._stdin):
                return Symbol("NIL")
            char = self._stdin.read(1)
            if char == "":
                return Symbol("NIL")
            return Integer(ord(char[0]))
        if name == "LEDS" and len(args) == 1:
            value = self._pure(args[0])
            print(f"leds: {to_source(value)}", file=self._stderr)
            return Symbol("NIL")
        if name == "TICKS" and not args:
            tick = self._ticks
            self._ticks += 1
            return Integer(tick)
        if name == "CLOCK" and not args:
            return Integer(self._clock.now_ms())
        msg = f"unknown IO action: {to_source(action)}"
        raise IoRuntimeError(msg)

    def _continue_after_result(
        self,
        result: Expr,
        continuations: list[_Continuation],
    ) -> Expr | None:
        if not continuations:
            return None
        continuation = continuations.pop()
        if isinstance(continuation, _BindCont):
            return _apply_unary_lambda(continuation.lambda_expr, result)
        if isinstance(continuation, _ThenCont):
            return continuation.next_action
        assert_never(continuation)

    def _resolve_action(self, action: Expr) -> Expr:
        if isinstance(action, Symbol):
            definition = self._definitions.get(action.name)
            if definition is not None:
                return definition
            if action.name in _ZERO_ARG_IO_ACTIONS:
                return App((action,))
            return action
        return action

    def _pure(self, expr: Expr) -> Expr:
        if self._model == "thor":
            return reduce_expr(
                expr,
                quantum=self._quantum,
                definitions=self._thor_definition_cache,
            ).expr
        machine = Red2Machine(
            compile_expr(expr),
            quantum=self._quantum,
            definitions=self._red2_definition_image,
            resource_limits=self._resource_limits,
            definition_cache=self._red2_definition_cache,
        )
        machine.run()
        return machine.result_expr()

    def _integer_arg(self, primitive: str, expr: Expr) -> int:
        value = self._pure(expr)
        if isinstance(value, Integer):
            return value.value
        msg = f"{primitive} expects an integer byte, got {to_source(value)}"
        raise IoRuntimeError(msg)

    def _byte_list_arg(self, primitive: str, expr: Expr) -> list[int]:
        value = self._pure(expr)
        bytes_: list[int] = []
        while isinstance(value, StructLit) and value.tag == "PAIR":
            head, tail = value.fields
            if not isinstance(head, Integer):
                msg = f"{primitive} expects integer bytes, got {to_source(head)}"
                raise IoRuntimeError(msg)
            bytes_.append(head.value)
            value = tail
        if isinstance(value, Symbol) and value.name == "NIL":
            return bytes_
        msg = f"{primitive} expects a byte list, got {to_source(value)}"
        raise IoRuntimeError(msg)


def _text_stream_has_ready_input(stream: TextIO) -> bool:
    try:
        fd = stream.fileno()
    except (AttributeError, OSError):
        return True
    readable, _, _ = select.select([fd], [], [], 0)
    return bool(readable)


def _apply_unary_lambda(expr: Expr, value: Expr) -> Expr:
    if not isinstance(expr, Lambda) or len(expr.params) != 1:
        msg = f"IO-BIND expects a unary lambda, got {to_source(expr)}"
        raise IoRuntimeError(msg)
    return _substitute(expr.body, expr.params[0], value, target_index=0)


def _apply_lambda(expr: Lambda, args: tuple[Expr, ...]) -> Expr:
    if len(args) != len(expr.params):
        msg = f"expected {len(expr.params)} argument(s), got {len(args)}"
        raise IoRuntimeError(msg)
    body = expr.body
    for target_index, (name, value) in enumerate(zip(expr.params, args, strict=True)):
        body = _substitute(body, name, value, target_index=target_index)
    return body


def _substitute(
    expr: Expr,
    name: str,
    value: Expr,
    *,
    target_index: int,
    depth: int = 0,
) -> Expr:
    if isinstance(expr, Symbol):
        return value if expr.name == name else expr
    if isinstance(expr, Var):
        matches_name = expr.name == name
        matches_index = expr.name is None and expr.index == depth + target_index
        if matches_name or matches_index:
            return value
        return expr
    if isinstance(expr, Lambda):
        if name in expr.params:
            return expr
        return Lambda(
            expr.params,
            _substitute(
                expr.body,
                name,
                value,
                target_index=target_index,
                depth=depth + len(expr.params),
            ),
        )
    if isinstance(expr, App):
        return App(
            tuple(
                _substitute(
                    item,
                    name,
                    value,
                    target_index=target_index,
                    depth=depth,
                )
                for item in expr.items
            )
        )
    if isinstance(expr, LetRec):
        binding_names = tuple(binding.name for binding in expr.bindings)
        bindings = tuple(
            Binding(
                binding.name,
                _substitute(
                    binding.expr,
                    name,
                    value,
                    target_index=target_index,
                    depth=depth + len(binding_names),
                ),
            )
            if name not in binding_names
            else binding
            for binding in expr.bindings
        )
        body = (
            expr.body
            if name in binding_names
            else _substitute(
                expr.body,
                name,
                value,
                target_index=target_index,
                depth=depth + len(binding_names),
            )
        )
        return LetRec(bindings, body)
    if isinstance(expr, StructLit):
        return StructLit(
            expr.tag,
            tuple(
                _substitute(
                    field,
                    name,
                    value,
                    target_index=target_index,
                    depth=depth,
                )
                for field in expr.fields
            ),
        )
    if isinstance(expr, Integer | Float | Char | Var | Block | Rec):
        return expr
    assert_never(expr)

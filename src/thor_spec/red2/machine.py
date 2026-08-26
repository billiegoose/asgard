from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from itertools import pairwise
from typing import assert_never

from thor_spec.red2.instructions import (
    DefinitionImage,
    Instruction,
    Opcode,
    ProgramImage,
)
from thor_spec.red2.primitives import (
    FALSE,
    TRUE,
    fire_primitive,
    primitive_name,
    struct_accessor,
)


class Direction(Enum):
    F = auto()
    B = auto()


@dataclass(slots=True)
class MachineState:
    memory: list[Instruction]
    pc: int
    fsp: int
    cstack: list[int]
    env: int | None
    q: int
    phi: int
    direction: Direction
    halted: bool
    argcnt: int = 0
    prim: str | None = None
    fire: bool = False


@dataclass(frozen=True, slots=True)
class _VarTerm:
    index: int
    name: str | None = None


@dataclass(frozen=True, slots=True)
class _LambdaTerm:
    params: tuple[str, ...]
    body: _Term


@dataclass(frozen=True, slots=True)
class _AppTerm:
    operator: _Term
    args: tuple[_Term, ...]


@dataclass(frozen=True, slots=True)
class _ClosureTerm:
    term: _Term
    env: _Env


@dataclass(frozen=True, slots=True)
class _StructTerm:
    tag: str
    fields: tuple[_Term, ...]


@dataclass(frozen=True, slots=True)
class _LetRecTerm:
    names: tuple[str, ...]
    expressions: tuple[_Term, ...]
    body: _Term


@dataclass(frozen=True, slots=True)
class _RecTerm:
    index: int
    names: tuple[str, ...]
    expressions: tuple[_Term, ...]
    env: _Env


@dataclass(frozen=True, slots=True)
class _InstrTerm:
    inst: Instruction


type _EnvEntry = _ClosureTerm | _RecTerm
type _Term = (
    _VarTerm
    | _LambdaTerm
    | _AppTerm
    | _ClosureTerm
    | _StructTerm
    | _LetRecTerm
    | _RecTerm
    | _InstrTerm
)
type _Env = tuple[_EnvEntry, ...]


class Red2Machine:
    """Small Python model of the Chapter 4 RED2 machine.

    Public state fields expose the RED2 registers used by the tests.  The
    implementation keeps a private term graph decoded from RED2 instructions so
    that primitive firing, structures, and recursive blocks remain deterministic
    and traceable to the linear instruction image.
    """

    def __init__(
        self,
        image: ProgramImage,
        quantum: int,
        definitions: DefinitionImage | None = None,
    ) -> None:
        self._problem_memory = list(image.instructions)
        self._stop_pc = self._find_stop(image)
        self._source = _ProgramParser(self._problem_memory, image.metadata).parse(
            image.entry,
        )
        self._definitions = _parse_definitions(definitions)
        self._result: tuple[Instruction, ...] = ()
        self._executed = False
        self.state = MachineState(
            memory=list(image.instructions),
            pc=image.entry,
            fsp=len(image.instructions),
            cstack=[],
            env=None,
            q=max(quantum, 0),
            phi=0,
            direction=Direction.F,
            halted=False,
        )

    def step(self) -> MachineState:
        """Advance the RED2 model by one observable phase."""
        if self.state.halted:
            return self.state

        if not self._executed:
            reduced = self._reduce(self._source, ())
            self._result = tuple(_ResultEmitter().emit(reduced))
            self._executed = True
            self.state.direction = Direction.B
            self.state.pc = self._stop_pc
            self._sync_memory()
            return self.state

        self.state.halted = True
        self.state.pc = self._stop_pc
        self.state.direction = Direction.B
        self._sync_memory()
        return self.state

    def run(self, max_steps: int = 10000) -> MachineState:
        """Run until STOP is reached or ``max_steps`` observable phases elapse."""
        steps = 0
        while not self.state.halted and steps < max_steps:
            self.step()
            steps += 1
        return self.state

    def result_instructions(self) -> tuple[Instruction, ...]:
        """Return the materialized result graph without RED2 bookkeeping cells."""
        return tuple(
            inst
            for inst in self._result
            if inst.opcode not in {Opcode.JOIN, Opcode.STOP, Opcode.CLOSURE, Opcode.REC}
        )

    def _reduce(self, term: _Term, env: _Env) -> _Term:
        if isinstance(term, _ClosureTerm):
            if isinstance(term.term, _LambdaTerm):
                return term
            return self._reduce(term.term, term.env)
        if isinstance(term, _RecTerm):
            return self._reduce_rec(term)
        if isinstance(term, _VarTerm):
            if 0 <= term.index < len(env):
                return self._reduce(env[term.index], ())
            corrected = max(self.state.phi - term.index, 0)
            return _VarTerm(corrected, term.name)
        if isinstance(term, _LambdaTerm):
            if env:
                return _ClosureTerm(term, env)
            return term
        if isinstance(term, _StructTerm):
            return _StructTerm(
                term.tag,
                tuple(self._reduce_no_contract(field, env) for field in term.fields),
            )
        if isinstance(term, _LetRecTerm):
            return self._reduce_letrec(term, env)
        if isinstance(term, _InstrTerm):
            return self._reduce_instruction(term, env)
        if isinstance(term, _AppTerm):
            return self._reduce_app(term, env)
        assert_never(term)

    def _reduce_no_contract(self, term: _Term, env: _Env) -> _Term:
        saved = self.state.q
        self.state.q = 0
        try:
            return self._reduce(term, env)
        finally:
            self.state.q = saved

    def _contract(self) -> bool:
        if self.state.q <= 0:
            return False
        self.state.q -= 1
        return True

    def _reduce_instruction(self, term: _InstrTerm, env: _Env) -> _Term:
        inst = term.inst
        if inst.opcode is Opcode.SYM and isinstance(inst.data, str):
            definition = self._definitions.get(inst.data)
            if definition is not None and self._contract():
                return self._reduce(definition, env)
        return term

    def _reduce_app(self, term: _AppTerm, env: _Env) -> _Term:
        operator = self._reduce(term.operator, env)
        primitive = _term_primitive_name(operator)
        if primitive is not None:
            return self._reduce_primitive(primitive, operator, term.args, env)
        lambda_term, lambda_env = _as_lambda(operator, env)
        if lambda_term is not None and term.args:
            bind_count = min(len(lambda_term.params), len(term.args), self.state.q)
            if bind_count == 0:
                return _AppTerm(operator, term.args)
            for _ in range(bind_count):
                self._contract()
            argument_closures = tuple(
                _ClosureTerm(arg, env) for arg in term.args[:bind_count]
            )
            if bind_count == len(lambda_term.params):
                reduced_body = self._reduce(
                    lambda_term.body,
                    (*argument_closures, *lambda_env),
                )
            else:
                remaining_params = lambda_term.params[bind_count:]
                placeholder_env = tuple(
                    _ClosureTerm(_VarTerm(index, name), ())
                    for index, name in enumerate(remaining_params)
                )
                reduced_body = _LambdaTerm(
                    remaining_params,
                    self._reduce(
                        lambda_term.body,
                        (*argument_closures, *placeholder_env, *lambda_env),
                    ),
                )
            remaining_args = term.args[bind_count:]
            if not remaining_args:
                return reduced_body
            return self._reduce(_AppTerm(reduced_body, remaining_args), env)
        if isinstance(operator, _StructTerm) and term.args:
            return self._reduce_struct_application(operator, term.args, env)
        return _AppTerm(
            operator,
            tuple(self._reduce_no_contract(arg, env) for arg in term.args),
        )

    def _reduce_primitive(
        self,
        name: str,
        operator: _Term,
        args: tuple[_Term, ...],
        env: _Env,
    ) -> _Term:
        if name == "IF" and len(args) == 3:
            return self._reduce_if(args, env)
        if name == "Y" and len(args) == 1:
            return self._reduce_y(args[0], env)
        if name == "AND":
            return self._reduce_logical(args, env, true_identity=True)
        if name == "OR":
            return self._reduce_logical(args, env, true_identity=False)
        if name == "CONS" and len(args) == 2:
            return self._reduce_cons(operator, args, env)
        accessor = struct_accessor(name)
        if accessor is not None and len(args) == 1:
            tag, field_index = accessor
            return self._reduce_accessor(name, tag, field_index, operator, args[0], env)
        if name == "NULL?" and len(args) == 1:
            return self._reduce_null(operator, args[0], env)
        if name == "TAG" and len(args) == 1:
            arg = self._reduce(args[0], env)
            if isinstance(arg, _StructTerm) and self._contract():
                return _InstrTerm(Instruction(Opcode.SYM, arg.tag, head=True))
            return _AppTerm(operator, (arg,))

        reduced_args = tuple(self._reduce(arg, env) for arg in args)
        instruction_args = tuple(_term_instruction(arg) for arg in reduced_args)
        if any(inst is None for inst in instruction_args):
            return _AppTerm(operator, reduced_args)
        self.state.argcnt = len(args)
        self.state.prim = name
        self.state.fire = True
        result, remaining = fire_primitive(
            name,
            tuple(inst for inst in instruction_args if inst is not None),
            self.state.q,
        )
        self.state.q = remaining
        self.state.fire = False
        self.state.prim = None
        self.state.argcnt = 0
        if result is None:
            return _AppTerm(operator, reduced_args)
        return _InstrTerm(result)

    def _reduce_if(self, args: tuple[_Term, ...], env: _Env) -> _Term:
        condition = self._reduce(args[0], env)
        condition_inst = _term_instruction(condition)
        if condition_inst is not None and condition_inst == TRUE:
            if not self._contract():
                return _AppTerm(
                    _InstrTerm(Instruction(Opcode.PRIM_2, "IF")),
                    (condition, args[1], args[2]),
                )
            return self._reduce(args[1], env)
        if condition_inst is not None and condition_inst == FALSE:
            if not self._contract():
                return _AppTerm(
                    _InstrTerm(Instruction(Opcode.PRIM_2, "IF")),
                    (condition, args[1], args[2]),
                )
            return self._reduce(args[2], env)
        return _AppTerm(
            _InstrTerm(Instruction(Opcode.PRIM_2, "IF")),
            (
                condition,
                self._reduce_no_contract(args[1], env),
                self._reduce_no_contract(args[2], env),
            ),
        )

    def _reduce_y(self, arg: _Term, env: _Env) -> _Term:
        if not self._contract():
            return _AppTerm(_InstrTerm(Instruction(Opcode.PRIM_2, "Y")), (arg,))
        return self._reduce(
            _AppTerm(
                arg, (_AppTerm(_InstrTerm(Instruction(Opcode.PRIM_2, "Y")), (arg,)),)
            ),
            env,
        )

    def _reduce_logical(
        self,
        args: tuple[_Term, ...],
        env: _Env,
        *,
        true_identity: bool,
    ) -> _Term:
        if not args:
            return _InstrTerm(TRUE if true_identity else FALSE)
        kept: list[_Term] = []
        for arg in args:
            reduced = self._reduce(arg, env)
            inst = _term_instruction(reduced)
            if inst is not None and self.state.q > 0:
                if true_identity and inst == FALSE:
                    self._contract()
                    return _InstrTerm(FALSE)
                if not true_identity and inst == TRUE:
                    self._contract()
                    return _InstrTerm(TRUE)
                if (true_identity and inst == TRUE) or (
                    not true_identity and inst == FALSE
                ):
                    self._contract()
                    continue
            kept.append(reduced)
        if not kept:
            return _InstrTerm(TRUE if true_identity else FALSE)
        return _AppTerm(
            _InstrTerm(Instruction(Opcode.PRIM_2, "AND" if true_identity else "OR")),
            tuple(kept),
        )

    def _reduce_cons(
        self,
        operator: _Term,
        args: tuple[_Term, ...],
        env: _Env,
    ) -> _Term:
        head = self._reduce(args[0], env)
        tail = self._reduce(args[1], env)
        if not self._contract():
            return _AppTerm(operator, (head, tail))
        return _StructTerm("PAIR", (head, tail))

    def _reduce_accessor(
        self,
        name: str,
        tag: str,
        field_index: int,
        operator: _Term,
        arg: _Term,
        env: _Env,
    ) -> _Term:
        value = self._reduce(arg, env)
        if (
            not isinstance(value, _StructTerm)
            or value.tag != tag
            or field_index >= len(value.fields)
        ):
            return _AppTerm(_native_unary_operator(name, operator), (value,))
        if not self._contract():
            return _AppTerm(_native_unary_operator(name, operator), (value,))
        return self._reduce(value.fields[field_index], env)

    def _reduce_null(self, operator: _Term, arg: _Term, env: _Env) -> _Term:
        value = self._reduce(arg, env)
        if _is_nil_term(value):
            if self._contract():
                return _InstrTerm(TRUE)
            return _AppTerm(operator, (value,))
        if _is_irreducible_term(value):
            return _AppTerm(operator, (value,))
        if self._contract():
            return _InstrTerm(FALSE)
        return _AppTerm(operator, (value,))

    def _reduce_struct_application(
        self,
        operator: _StructTerm,
        args: tuple[_Term, ...],
        env: _Env,
    ) -> _Term:
        selector = self._reduce(args[0], env)
        lambda_term, lambda_env = _as_lambda(selector, env)
        if lambda_term is None or not self._contract():
            return _AppTerm(operator, (selector, *args[1:]))
        bind_count = min(len(lambda_term.params), len(operator.fields))
        field_closures = tuple(
            _ClosureTerm(field, env) for field in operator.fields[:bind_count]
        )
        reduced = self._reduce(lambda_term.body, (*field_closures, *lambda_env))
        if args[1:]:
            return self._reduce(_AppTerm(reduced, args[1:]), env)
        return reduced

    def _reduce_letrec(self, letrec: _LetRecTerm, env: _Env) -> _Term:
        if not letrec.names:
            return self._reduce(letrec.body, env)
        recursive_entries = tuple(
            _RecTerm(index, letrec.names, letrec.expressions, ())
            for index in range(len(letrec.expressions))
        )
        recursive_env = (*recursive_entries, *env)
        for rec in recursive_entries:
            object.__setattr__(rec, "env", recursive_env)
        return self._reduce(letrec.body, recursive_env)

    def _reduce_rec(self, rec: _RecTerm) -> _Term:
        if self.state.q > 0:
            self._contract()
            return self._reduce(rec.expressions[rec.index], rec.env)
        placeholder_env: _Env = tuple(
            _ClosureTerm(_VarTerm(index, name), ())
            for index, name in enumerate(rec.names)
        )
        return _LetRecTerm(
            rec.names,
            tuple(
                self._reduce_no_contract(expr, placeholder_env)
                for expr in rec.expressions
            ),
            _VarTerm(rec.index, rec.names[rec.index]),
        )

    def _sync_memory(self) -> None:
        self.state.memory = [*self._problem_memory, *self._result]

    @staticmethod
    def _find_stop(image: ProgramImage) -> int:
        for index, inst in enumerate(image.instructions):
            if inst.opcode is Opcode.STOP:
                return index
        return max(len(image.instructions) - 1, 0)


class _ProgramParser:
    def __init__(
        self,
        memory: list[Instruction],
        metadata: object | None = None,
    ) -> None:
        self._memory = memory
        self._metadata = metadata if isinstance(metadata, dict) else {}

    def parse(self, pc: int) -> _Term:
        term, _next_pc, _head = self._parse_with_span(pc)
        return term

    def _parse_with_span(self, pc: int) -> tuple[_Term, int, bool]:
        inst = self._memory[pc]
        if inst.opcode is Opcode.APP:
            return self._parse_app(pc)
        if inst.opcode is Opcode.LAMBDA:
            return self._parse_lambda(pc)
        if inst.opcode is Opcode.VAR:
            return _VarTerm(_int_data(inst)), pc + 1, inst.head
        if inst.opcode is Opcode.UBV:
            return _VarTerm(_int_data(inst)), pc + 1, inst.head
        if inst.opcode is Opcode.STRUCT:
            return self._parse_struct(pc)
        if inst.opcode is Opcode.RBLOCK:
            return self._parse_letrec(pc)
        return _InstrTerm(inst), pc + 1, inst.head

    def _parse_app(self, pc: int) -> tuple[_Term, int, bool]:
        app_insts: list[Instruction] = []
        operator_pc = pc
        while (
            operator_pc < len(self._memory)
            and self._memory[operator_pc].opcode is Opcode.APP
        ):
            app_insts.append(self._memory[operator_pc])
            operator_pc += 1
        return self._parse_app_from_parts(tuple(app_insts), operator_pc)

    def _parse_app_from_parts(
        self,
        app_insts: tuple[Instruction, ...],
        operator_pc: int,
    ) -> tuple[_Term, int, bool]:
        drop_index = _first_drop_index(tuple(_int_data(inst) for inst in app_insts))
        if drop_index is not None:
            inner, inner_next, inner_head = self._parse_app_from_parts(
                app_insts[drop_index:],
                operator_pc,
            )
            outer_args_with_spans = tuple(
                self._parse_with_span(_int_data(inst))
                for inst in app_insts[:drop_index]
            )
            outer_args = tuple(term for term, _next_pc, _head in outer_args_with_spans)
            next_pc = max(
                (
                    inner_next,
                    *(next_pc for _term, next_pc, _head in outer_args_with_spans),
                ),
                default=inner_next,
            )
            return _AppTerm(inner, outer_args), next_pc, inner_head

        operator, operator_next, operator_head = self._parse_with_span(operator_pc)
        args_with_spans = tuple(
            self._parse_with_span(_int_data(inst)) for inst in app_insts
        )
        args = tuple(term for term, _next_pc, _head in args_with_spans)
        next_pc = max(
            (operator_next, *(next_pc for _term, next_pc, _head in args_with_spans)),
            default=operator_next,
        )
        return _AppTerm(operator, args), next_pc, operator_head

    def _parse_lambda(self, pc: int) -> tuple[_Term, int, bool]:
        params: list[str] = []
        body_pc = pc
        while (
            body_pc < len(self._memory)
            and self._memory[body_pc].opcode is Opcode.LAMBDA
        ):
            data = self._memory[body_pc].data
            params.append(data if isinstance(data, str) else str(data))
            body_pc += 1
        body, next_pc, body_head = self._parse_flat_body(body_pc)
        return _LambdaTerm(tuple(params), body), next_pc, body_head

    def _parse_flat_body(self, pc: int) -> tuple[_Term, int, bool]:
        items: list[_Term] = []
        cursor = pc
        root_head = False
        while (
            cursor < len(self._memory)
            and self._memory[cursor].opcode is not Opcode.STOP
        ):
            term, cursor, root_head = self._parse_with_span(cursor)
            items.append(term)
            if root_head:
                break
        if not items:
            return _InstrTerm(Instruction(Opcode.STOP, 0)), cursor, root_head
        if len(items) == 1:
            return items[0], cursor, root_head
        return _AppTerm(items[0], tuple(items[1:])), cursor, root_head

    def _parse_struct(self, pc: int) -> tuple[_Term, int, bool]:
        inst = self._memory[pc]
        tag = inst.data if isinstance(inst.data, str) else str(inst.data)
        field_terms_with_spans: list[tuple[_Term, int, bool]] = []
        cursor = pc + 1
        while cursor < len(self._memory) and self._memory[cursor].opcode is Opcode.APP:
            field_terms_with_spans.append(
                self._parse_with_span(_int_data(self._memory[cursor]))
            )
            cursor += 1
        root_head = False
        if cursor < len(self._memory):
            root_head = self._memory[cursor].head
            cursor += 1
        next_pc = max(
            (cursor, *(next_pc for _term, next_pc, _head in field_terms_with_spans)),
            default=cursor,
        )
        field_terms = tuple(term for term, _next_pc, _head in field_terms_with_spans)
        return _StructTerm(tag, tuple(reversed(field_terms))), next_pc, root_head

    def _parse_letrec(self, pc: int) -> tuple[_Term, int, bool]:
        blocks: list[Instruction] = []
        cursor = pc
        while (
            cursor < len(self._memory) and self._memory[cursor].opcode is Opcode.RBLOCK
        ):
            blocks.append(self._memory[cursor])
            cursor += 1
        if cursor >= len(self._memory) or self._memory[cursor].opcode is not Opcode.RUP:
            inst = self._memory[pc]
            return _InstrTerm(inst), pc + 1, inst.head
        names = self._metadata.get(f"letrec:{pc}:names")
        if not isinstance(names, tuple) or len(names) != len(blocks):
            names = tuple(_fallback_name(index) for index in range(len(blocks)))
        expressions_with_spans = tuple(
            self._parse_with_span(_int_data(block)) for block in blocks
        )
        body, body_next, body_head = self._parse_with_span(cursor + 1)
        next_pc = max(
            (
                body_next,
                *(next_pc for _term, next_pc, _head in expressions_with_spans),
            ),
            default=body_next,
        )
        expressions = tuple(term for term, _next_pc, _head in expressions_with_spans)
        return _LetRecTerm(names, expressions, body), next_pc, body_head


class _ResultEmitter:
    def emit(self, term: _Term) -> list[Instruction]:
        out: list[Instruction] = []
        self._emit(term, out, head=True, omit_lambda_body=False)
        return out

    def _emit(
        self,
        term: _Term,
        out: list[Instruction],
        *,
        head: bool,
        omit_lambda_body: bool,
    ) -> None:
        if isinstance(term, _ClosureTerm):
            self._emit(term.term, out, head=head, omit_lambda_body=omit_lambda_body)
            return
        if isinstance(term, _RecTerm):
            self._emit(
                _LetRecTerm(term.names, term.expressions, _VarTerm(term.index)),
                out,
                head=head,
                omit_lambda_body=omit_lambda_body,
            )
            return
        if isinstance(term, _VarTerm):
            out.append(
                Instruction(
                    Opcode.VAR,
                    term.name if term.name is not None else term.index,
                    head=head,
                )
            )
            return
        if isinstance(term, _InstrTerm):
            out.append(Instruction(term.inst.opcode, term.inst.data, head=head))
            return
        if isinstance(term, _StructTerm):
            out.append(Instruction(Opcode.STRUCT, term.tag, head=False))
            for index, field in enumerate(term.fields):
                self._emit(
                    field,
                    out,
                    head=head if index == len(term.fields) - 1 else False,
                    omit_lambda_body=False,
                )
            return
        if isinstance(term, _LetRecTerm):
            out.append(Instruction(Opcode.RUP, len(term.names), head=False))
            for name, expr in zip(term.names, term.expressions, strict=True):
                out.append(Instruction(Opcode.RBLOCK, name, head=False))
                self._emit(expr, out, head=False, omit_lambda_body=False)
            self._emit(term.body, out, head=head, omit_lambda_body=False)
            return
        if isinstance(term, _LambdaTerm):
            for param in term.params:
                out.append(Instruction(Opcode.LAMBDA, param, head=False))
            if not omit_lambda_body:
                self._emit(term.body, out, head=head, omit_lambda_body=False)
            return
        if isinstance(term, _AppTerm):
            for _arg in term.args:
                out.append(Instruction(Opcode.APP, len(term.args), head=False))
            self._emit(term.operator, out, head=False, omit_lambda_body=True)
            last_index = len(term.args) - 1
            for index, arg in enumerate(term.args):
                self._emit(
                    arg,
                    out,
                    head=head if index == last_index else False,
                    omit_lambda_body=False,
                )
            return
        assert_never(term)


def _parse_definitions(definitions: DefinitionImage | None) -> dict[str, _Term]:
    if definitions is None:
        return {}
    return {
        name: _ProgramParser(
            list(image.instructions),
            image.metadata,
        ).parse(image.entry)
        for name, image in definitions.programs.items()
    }


def _first_drop_index(values: tuple[int, ...]) -> int | None:
    for index, (left, right) in enumerate(pairwise(values), 1):
        if right < left:
            return index
    return None


def _as_lambda(term: _Term, _fallback_env: _Env) -> tuple[_LambdaTerm | None, _Env]:
    if isinstance(term, _LambdaTerm):
        return term, ()
    if isinstance(term, _ClosureTerm) and isinstance(term.term, _LambdaTerm):
        return term.term, term.env
    return None, ()


def _term_primitive_name(term: _Term) -> str | None:
    if isinstance(term, _InstrTerm):
        return primitive_name(term.inst)
    return None


def _term_instruction(term: _Term) -> Instruction | None:
    if isinstance(term, _InstrTerm):
        return term.inst
    if isinstance(term, _StructTerm):
        return Instruction(Opcode.STRUCT, term.tag, head=True)
    return None


def _native_unary_operator(name: str, operator: _Term) -> _Term:
    if isinstance(operator, _InstrTerm):
        return operator
    return _InstrTerm(Instruction(Opcode.PRIM_1, name))


def _is_nil_term(term: _Term) -> bool:
    inst = _term_instruction(term)
    return inst is not None and inst.opcode is Opcode.PRIM_0 and inst.data == "NIL"


def _is_irreducible_term(term: _Term) -> bool:
    return isinstance(term, _AppTerm | _VarTerm)


def lookup(index: int, state: MachineState) -> int:
    """Resolve a RED2 variable index through the visible control stack.

    The core Task 5 machine stores environment addresses on ``cstack`` in newest
    first logical order.  Tests that construct a state directly can therefore use
    this helper without depending on private reducer objects.
    """
    if index < 0:
        msg = f"negative RED2 variable index: {index}"
        raise IndexError(msg)
    if index < len(state.cstack):
        return state.cstack[-1 - index]
    if state.env is not None and index == 0:
        return state.env
    msg = f"RED2 variable index out of range: {index}"
    raise IndexError(msg)


def _int_data(inst: Instruction) -> int:
    if isinstance(inst.data, int):
        return inst.data
    msg = f"instruction {inst.opcode.name} requires integer data, got {inst.data!r}"
    raise ValueError(msg)


def _fallback_name(index: int) -> str:
    if 0 <= index < 26:
        return chr(ord("x") + index) if index < 3 else f"r{index}"
    return f"r{index}"

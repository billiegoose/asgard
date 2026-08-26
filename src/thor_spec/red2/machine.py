from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import assert_never

from thor_spec.red2.instructions import Instruction, Opcode, ProgramImage
from thor_spec.red2.primitives import FALSE, TRUE, fire_primitive, primitive_name


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

    def __init__(self, image: ProgramImage, quantum: int) -> None:
        self._problem_memory = list(image.instructions)
        self._stop_pc = self._find_stop(image)
        self._source = _ProgramParser(self._problem_memory, image.metadata).parse(
            image.entry,
        )
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
            return term
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

    def _reduce_app(self, term: _AppTerm, env: _Env) -> _Term:
        operator = self._reduce(term.operator, env)
        primitive = _term_primitive_name(operator)
        if primitive is not None:
            return self._reduce_primitive(primitive, operator, term.args, env)
        lambda_term, lambda_env = _as_lambda(operator, env)
        if lambda_term is not None and term.args:
            if not self._contract():
                return _AppTerm(operator, term.args)
            argument_closure = _ClosureTerm(term.args[0], env)
            reduced_body = self._reduce(
                lambda_term.body,
                (argument_closure, *lambda_env),
            )
            remaining_args = term.args[1:]
            if not remaining_args:
                return reduced_body
            return self._reduce(_AppTerm(reduced_body, remaining_args), env)
        if isinstance(operator, _StructTerm) and term.args:
            return self._reduce_struct_application(operator, term.args, env)
        return _AppTerm(operator, term.args)

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
        if name in {"CAR", "CDR"} and len(args) == 1:
            return self._reduce_accessor(name, args[0], env)
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

    def _reduce_accessor(self, name: str, arg: _Term, env: _Env) -> _Term:
        value = self._reduce(arg, env)
        if (
            not isinstance(value, _StructTerm)
            or value.tag != "PAIR"
            or len(value.fields) != 2
        ):
            return _AppTerm(_InstrTerm(Instruction(Opcode.PRIM_1, name)), (value,))
        if not self._contract():
            return _AppTerm(_InstrTerm(Instruction(Opcode.PRIM_1, name)), (value,))
        field_index = 0 if name == "CAR" else 1
        return self._reduce(value.fields[field_index], env)

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
        inst = self._memory[pc]
        if inst.opcode is Opcode.APP:
            return self._parse_app(pc)
        if inst.opcode is Opcode.LAMBDA:
            return self._parse_lambda(pc)
        if inst.opcode is Opcode.VAR:
            return _VarTerm(_int_data(inst))
        if inst.opcode is Opcode.UBV:
            return _VarTerm(_int_data(inst))
        if inst.opcode is Opcode.STRUCT:
            return self._parse_struct(pc)
        if inst.opcode is Opcode.RBLOCK:
            return self._parse_letrec(pc)
        return _InstrTerm(inst)

    def _parse_app(self, pc: int) -> _Term:
        app_insts: list[Instruction] = []
        operator_pc = pc
        while (
            operator_pc < len(self._memory)
            and self._memory[operator_pc].opcode is Opcode.APP
        ):
            app_insts.append(self._memory[operator_pc])
            operator_pc += 1
        operator = self.parse(operator_pc)
        args = tuple(self.parse(_int_data(inst)) for inst in app_insts)
        return _AppTerm(operator, args)

    def _parse_lambda(self, pc: int) -> _Term:
        params: list[str] = []
        body_pc = pc
        while (
            body_pc < len(self._memory)
            and self._memory[body_pc].opcode is Opcode.LAMBDA
        ):
            data = self._memory[body_pc].data
            params.append(data if isinstance(data, str) else str(data))
            body_pc += 1
        body = self.parse(body_pc)
        for param in reversed(params):
            body = _LambdaTerm((param,), body)
        return body

    def _parse_struct(self, pc: int) -> _Term:
        inst = self._memory[pc]
        tag = inst.data if isinstance(inst.data, str) else str(inst.data)
        field_terms: list[_Term] = []
        cursor = pc + 1
        while cursor < len(self._memory) and self._memory[cursor].opcode is Opcode.APP:
            field_terms.append(self.parse(_int_data(self._memory[cursor])))
            cursor += 1
        return _StructTerm(tag, tuple(reversed(field_terms)))

    def _parse_letrec(self, pc: int) -> _Term:
        blocks: list[Instruction] = []
        cursor = pc
        while (
            cursor < len(self._memory) and self._memory[cursor].opcode is Opcode.RBLOCK
        ):
            blocks.append(self._memory[cursor])
            cursor += 1
        if cursor >= len(self._memory) or self._memory[cursor].opcode is not Opcode.RUP:
            return _InstrTerm(self._memory[pc])
        names = self._metadata.get(f"letrec:{pc}:names")
        if not isinstance(names, tuple) or len(names) != len(blocks):
            names = tuple(_fallback_name(index) for index in range(len(blocks)))
        expressions = tuple(self.parse(_int_data(block)) for block in blocks)
        body = self.parse(cursor + 1)
        return _LetRecTerm(names, expressions, body)


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


def _as_lambda(term: _Term, fallback_env: _Env) -> tuple[_LambdaTerm | None, _Env]:
    if isinstance(term, _LambdaTerm):
        return term, fallback_env
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

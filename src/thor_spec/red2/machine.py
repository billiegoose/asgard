from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import assert_never

from thor_spec.red2.instructions import Instruction, Opcode, ProgramImage


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


@dataclass(frozen=True, slots=True)
class _VarTerm:
    index: int


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
class _InstrTerm:
    inst: Instruction


type _Term = _VarTerm | _LambdaTerm | _AppTerm | _ClosureTerm | _InstrTerm
type _Env = tuple[_ClosureTerm, ...]


class Red2Machine:
    """Small Python model of the Chapter 4 core RED2 machine.

    The implementation keeps the public state fields visible as RED2 machine
    registers while using private term objects to make the prototype stepper
    deterministic and readable.  It models the μRED core needed by Task 5:
    applications, lambdas, variables, closures, UBV-style unbound variables, and
    passive constants.  The result graph is materialized after ``fsp`` in
    ``state.memory``.
    """

    def __init__(self, image: ProgramImage, quantum: int) -> None:
        self._problem_memory = list(image.instructions)
        self._stop_pc = self._find_stop(image)
        self._source = _ProgramParser(self._problem_memory).parse(image.entry)
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
        if isinstance(term, _VarTerm):
            if 0 <= term.index < len(env):
                return self._reduce(env[term.index], ())
            corrected = max(self.state.phi - term.index, 0)
            return _VarTerm(corrected)
        if isinstance(term, _LambdaTerm):
            if env:
                return _ClosureTerm(term, env)
            return term
        if isinstance(term, _InstrTerm):
            return term
        if isinstance(term, _AppTerm):
            return self._reduce_app(term, env)
        assert_never(term)

    def _reduce_app(self, term: _AppTerm, env: _Env) -> _Term:
        operator = self._reduce(term.operator, env)
        lambda_term, lambda_env = _as_lambda(operator, env)
        if lambda_term is not None and term.args:
            if self.state.q == 0:
                return _AppTerm(operator, term.args)
            self.state.q -= 1
            argument_closure = _ClosureTerm(term.args[0], env)
            reduced_body = self._reduce(
                lambda_term.body,
                (argument_closure, *lambda_env),
            )
            remaining_args = term.args[1:]
            if not remaining_args:
                return reduced_body
            return self._reduce(_AppTerm(reduced_body, remaining_args), env)
        return _AppTerm(operator, term.args)

    def _sync_memory(self) -> None:
        self.state.memory = [*self._problem_memory, *self._result]

    @staticmethod
    def _find_stop(image: ProgramImage) -> int:
        for index, inst in enumerate(image.instructions):
            if inst.opcode is Opcode.STOP:
                return index
        return max(len(image.instructions) - 1, 0)


class _ProgramParser:
    def __init__(self, memory: list[Instruction]) -> None:
        self._memory = memory

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
        if isinstance(term, _VarTerm):
            out.append(Instruction(Opcode.VAR, term.index, head=head))
            return
        if isinstance(term, _InstrTerm):
            out.append(Instruction(term.inst.opcode, term.inst.data, head=head))
            return
        if isinstance(term, _LambdaTerm):
            for param in term.params:
                out.append(Instruction(Opcode.LAMBDA, param, head=False))
            if not omit_lambda_body:
                self._emit(term.body, out, head=head, omit_lambda_body=False)
            return
        if isinstance(term, _AppTerm):
            for _arg in term.args:
                out.append(Instruction(Opcode.APP, 0, head=False))
            self._emit(
                term.operator,
                out,
                head=False,
                omit_lambda_body=True,
            )
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

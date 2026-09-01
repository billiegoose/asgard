from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from itertools import pairwise
from typing import assert_never

from red2_engine.instructions import (
    DefinitionImage,
    Instruction,
    Opcode,
    ProgramImage,
)
from red2_engine.primitives import (
    FALSE,
    TRUE,
    fire_primitive,
    instruction_to_expr,
    primitive_name,
    struct_accessor,
)
from thor_lang.ast import App, Binding, Expr, Lambda, LetRec, StructLit, Symbol, Var

DEFAULT_STACK_SIZE_IN_BYTES = 1024 * 1024
DEFAULT_HEAP_SIZE_IN_BYTES = 16 * 1024 * 1024
_STACK_FRAME_BYTES = 64
_HEAP_TERM_BYTES = 64


class Red2ResourceError(RuntimeError):
    """Raised when RED2 deterministic VM resources are exhausted."""


class Red2StackOverflowError(Red2ResourceError):
    """Raised when RED2 explicit evaluation stack exceeds its byte limit."""


class Red2HeapExhaustedError(Red2ResourceError):
    """Raised when RED2 deterministic heap accounting exceeds its byte limit."""


@dataclass(frozen=True, slots=True)
class Red2ResourceLimits:
    stack_size_in_bytes: int = DEFAULT_STACK_SIZE_IN_BYTES
    heap_size_in_bytes: int = DEFAULT_HEAP_SIZE_IN_BYTES


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


@dataclass(frozen=True, slots=True)
class Red2DefinitionCache:
    """Parsed RED2 definitions reusable across machines in one runtime.

    The cache belongs to the RED2 engine layer: callers can prebuild it when
    they already have a stable ``DefinitionImage`` and avoid reparsing the same
    immutable definition graph for every pure reduction.
    """

    definitions: Mapping[str, _Term]
    instruction_count: int
    term_count: int

    @classmethod
    def from_image(cls, definitions: DefinitionImage | None) -> Red2DefinitionCache:
        if definitions is None:
            return cls({}, 0, 0)
        parsed = _parse_definitions(
            definitions,
            reserve_instructions=lambda _count: None,
            reserve_term=lambda: None,
        )
        return cls(
            parsed,
            sum(len(image.instructions) for image in definitions.programs.values()),
            sum(_term_count(term) for term in parsed.values()),
        )


@dataclass(frozen=True, slots=True)
class _ReductionRequest:
    term: _Term
    env: _Env
    no_contract: bool = False


type _ReductionGenerator = Generator[_ReductionRequest, _Term, _Term]


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
        resource_limits: Red2ResourceLimits | None = None,
        definition_cache: Red2DefinitionCache | None = None,
    ) -> None:
        self._resource_limits = resource_limits or Red2ResourceLimits()
        if self._resource_limits.stack_size_in_bytes < 0:
            msg = "stack_size_in_bytes must be non-negative"
            raise ValueError(msg)
        if self._resource_limits.heap_size_in_bytes < 0:
            msg = "heap_size_in_bytes must be non-negative"
            raise ValueError(msg)
        self._stack_bytes_used = 0
        self._heap_bytes_used = 0
        self._problem_memory = image.instructions
        self._allocate_heap_terms(len(self._problem_memory))
        self._stop_pc = self._find_stop(image)
        self._source = _ProgramParser(
            self._problem_memory,
            image.metadata,
            self._reserve_heap_term,
        ).parse(image.entry)
        if definition_cache is not None:
            self._allocate_heap_terms(
                definition_cache.instruction_count + definition_cache.term_count
            )
            self._definitions = definition_cache.definitions
        else:
            self._definitions = _parse_definitions(
                definitions,
                reserve_instructions=self._allocate_heap_terms,
                reserve_term=self._reserve_heap_term,
            )
        self._result: tuple[Instruction, ...] = ()
        self._result_term: _Term | None = None
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
            self._result_term = reduced
            self._result = tuple(_ResultEmitter(self._reserve_heap_term).emit(reduced))
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

    def result_expr(self) -> Expr:
        """Return the reduced RED2 term as user-facing THOR AST.

        RED2 instruction memory may contain placeholder/bookkeeping opcodes such
        as PNP while representing partial results. CLI output should reflect the
        reduced THOR term, not leak those internal environment cells.
        """
        if self._result_term is None:
            self.run()
        assert self._result_term is not None
        return _term_to_expr(self._result_term, self._reserve_heap_term)

    def _reduce(self, term: _Term, env: _Env) -> _Term:
        return self._drive(self._reduce_term(term, env))

    def _drive(self, initial: _ReductionGenerator) -> _Term:
        stack: list[tuple[_ReductionGenerator, int | None]] = []
        result: _Term | None = None
        has_result = False
        try:
            self._enter_stack_frame()
            stack.append((initial, None))
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
                    self._leave_stack_frame()
                    if saved_quantum is not None:
                        self.state.q = saved_quantum
                    has_result = True
                    continue

                restore_quantum: int | None = None
                if request.no_contract:
                    restore_quantum = self.state.q
                    self.state.q = 0
                self._enter_stack_frame()
                stack.append(
                    (
                        self._reduce_term(request.term, request.env),
                        restore_quantum,
                    )
                )
                has_result = False
        except BaseException:
            self._stack_bytes_used = 0
            raise

        assert result is not None
        return result

    def _reduce_term(self, term: _Term, env: _Env) -> _ReductionGenerator:
        if isinstance(term, _ClosureTerm):
            if isinstance(term.term, _LambdaTerm):
                return term
            return (yield _ReductionRequest(term.term, term.env))
        if isinstance(term, _RecTerm):
            return (yield from self._reduce_rec(term))
        if isinstance(term, _VarTerm):
            if 0 <= term.index < len(env):
                return (yield _ReductionRequest(env[term.index], ()))
            corrected = max(self.state.phi - term.index, 0)
            return self._new_var(corrected, term.name)
        if isinstance(term, _LambdaTerm):
            if env:
                return self._new_closure(term, env)
            return term
        if isinstance(term, _StructTerm):
            fields: list[_Term] = []
            for field in term.fields:
                fields.append(
                    (
                        yield _ReductionRequest(
                            field,
                            env,
                            no_contract=True,
                        )
                    )
                )
            return self._allocate_term(lambda: _StructTerm(term.tag, tuple(fields)))
        if isinstance(term, _LetRecTerm):
            return (yield from self._reduce_letrec(term, env))
        if isinstance(term, _InstrTerm):
            return (yield from self._reduce_instruction(term, env))
        if isinstance(term, _AppTerm):
            return (yield from self._reduce_app(term, env))
        assert_never(term)

    def _enter_stack_frame(self) -> None:
        self._stack_bytes_used += _STACK_FRAME_BYTES
        if self._stack_bytes_used > self._resource_limits.stack_size_in_bytes:
            raise Red2StackOverflowError(
                f"RED2 stack overflow: used {self._stack_bytes_used} byte(s), "
                f"limit {self._resource_limits.stack_size_in_bytes} byte(s)"
            )

    def _leave_stack_frame(self) -> None:
        self._stack_bytes_used -= _STACK_FRAME_BYTES

    def _allocate_heap_terms(self, count: int) -> None:
        self._heap_bytes_used += count * _HEAP_TERM_BYTES
        if self._heap_bytes_used > self._resource_limits.heap_size_in_bytes:
            raise Red2HeapExhaustedError(
                f"RED2 heap exhausted: used {self._heap_bytes_used} byte(s), "
                f"limit {self._resource_limits.heap_size_in_bytes} byte(s)"
            )

    def _reserve_heap_term(self) -> None:
        self._allocate_heap_terms(1)

    def _allocate_term[TermT](self, factory: Callable[[], TermT]) -> TermT:
        self._reserve_heap_term()
        return factory()

    def _new_app(self, operator: _Term, args: tuple[_Term, ...]) -> _AppTerm:
        return self._allocate_term(lambda: _AppTerm(operator, args))

    def _new_closure(self, term: _Term, env: _Env) -> _ClosureTerm:
        return self._allocate_term(lambda: _ClosureTerm(term, env))

    def _new_instr(self, inst: Instruction) -> _InstrTerm:
        return self._allocate_term(lambda: _InstrTerm(inst))

    def _new_rec(
        self,
        index: int,
        names: tuple[str, ...],
        expressions: tuple[_Term, ...],
        env: _Env,
    ) -> _RecTerm:
        return self._allocate_term(lambda: _RecTerm(index, names, expressions, env))

    def _new_var(self, index: int, name: str | None = None) -> _VarTerm:
        return self._allocate_term(lambda: _VarTerm(index, name))

    def _contract(self) -> bool:
        if self.state.q <= 0:
            return False
        self.state.q -= 1
        return True

    def _reduce_instruction(
        self,
        term: _InstrTerm,
        env: _Env,
    ) -> _ReductionGenerator:
        inst = term.inst
        if inst.opcode is Opcode.SYM and isinstance(inst.data, str):
            definition = self._definitions.get(inst.data)
            if definition is not None and self._contract():
                return (yield _ReductionRequest(definition, env))
        return term

    def _reduce_app(self, term: _AppTerm, env: _Env) -> _ReductionGenerator:
        operator = yield _ReductionRequest(term.operator, env)
        primitive = _term_primitive_name(operator)
        if primitive is not None:
            return (
                yield from self._reduce_primitive(
                    primitive,
                    operator,
                    term.args,
                    env,
                )
            )
        lambda_term, lambda_env = _as_lambda(operator, env)
        if lambda_term is not None and term.args:
            bind_count = min(len(lambda_term.params), len(term.args), self.state.q)
            if bind_count == 0:
                return self._allocate_term(lambda: _AppTerm(operator, term.args))
            for _ in range(bind_count):
                self._contract()
            argument_closures = tuple(
                self._new_closure(arg, env) for arg in term.args[:bind_count]
            )
            if bind_count == len(lambda_term.params):
                reduced_body = yield _ReductionRequest(
                    lambda_term.body,
                    (*argument_closures, *lambda_env),
                )
            else:
                remaining_params = lambda_term.params[bind_count:]
                placeholder_env = tuple(
                    self._new_closure(self._new_var(index, name), ())
                    for index, name in enumerate(remaining_params)
                )
                reduced = yield _ReductionRequest(
                    lambda_term.body,
                    (*argument_closures, *placeholder_env, *lambda_env),
                )
                reduced_body = self._allocate_term(
                    lambda: _LambdaTerm(remaining_params, reduced)
                )
            remaining_args = term.args[bind_count:]
            if not remaining_args:
                return reduced_body
            return (
                yield _ReductionRequest(
                    self._allocate_term(lambda: _AppTerm(reduced_body, remaining_args)),
                    env,
                )
            )
        if isinstance(operator, _StructTerm) and term.args:
            return (
                yield from self._reduce_struct_application(
                    operator,
                    term.args,
                    env,
                )
            )
        reduced_args: list[_Term] = []
        for arg in term.args:
            reduced_args.append(
                (
                    yield _ReductionRequest(
                        arg,
                        env,
                        no_contract=True,
                    )
                )
            )
        return self._new_app(operator, tuple(reduced_args))

    def _reduce_primitive(
        self,
        name: str,
        operator: _Term,
        args: tuple[_Term, ...],
        env: _Env,
    ) -> _ReductionGenerator:
        if name == "IF" and len(args) == 3:
            return (yield from self._reduce_if(args, env))
        if name == "Y" and len(args) == 1:
            return (yield from self._reduce_y(args[0], env))
        if name == "AND":
            return (
                yield from self._reduce_logical(
                    args,
                    env,
                    true_identity=True,
                )
            )
        if name == "OR":
            return (
                yield from self._reduce_logical(
                    args,
                    env,
                    true_identity=False,
                )
            )
        if name == "CONS" and len(args) == 2:
            return (yield from self._reduce_cons(operator, args, env))
        accessor = struct_accessor(name)
        if accessor is not None and len(args) == 1:
            tag, field_index = accessor
            return (
                yield from self._reduce_accessor(
                    name,
                    tag,
                    field_index,
                    operator,
                    args[0],
                    env,
                )
            )
        if name == "NULL?" and len(args) == 1:
            return (yield from self._reduce_null(operator, args[0], env))
        if name == "TAG" and len(args) == 1:
            arg = yield _ReductionRequest(args[0], env)
            if isinstance(arg, _StructTerm) and self._contract():
                return self._new_instr(Instruction(Opcode.SYM, arg.tag, head=True))
            return self._new_app(operator, (arg,))

        reduced_args: list[_Term] = []
        for arg in args:
            reduced_args.append((yield _ReductionRequest(arg, env)))
        reduced_args_tuple = tuple(reduced_args)
        instruction_args = tuple(_term_instruction(arg) for arg in reduced_args_tuple)
        if any(inst is None for inst in instruction_args):
            return self._new_app(operator, reduced_args_tuple)
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
            return self._new_app(operator, reduced_args_tuple)
        return self._new_instr(result)

    def _reduce_if(
        self,
        args: tuple[_Term, ...],
        env: _Env,
    ) -> _ReductionGenerator:
        condition = yield _ReductionRequest(args[0], env)
        condition_inst = _term_instruction(condition)
        if condition_inst is not None and condition_inst == TRUE:
            if not self._contract():
                return self._new_app(
                    self._new_instr(Instruction(Opcode.PRIM_2, "IF")),
                    (condition, args[1], args[2]),
                )
            return (yield _ReductionRequest(args[1], env))
        if condition_inst is not None and condition_inst == FALSE:
            if not self._contract():
                return self._new_app(
                    self._new_instr(Instruction(Opcode.PRIM_2, "IF")),
                    (condition, args[1], args[2]),
                )
            return (yield _ReductionRequest(args[2], env))
        true_branch = yield _ReductionRequest(
            args[1],
            env,
            no_contract=True,
        )
        false_branch = yield _ReductionRequest(
            args[2],
            env,
            no_contract=True,
        )
        return self._new_app(
            self._new_instr(Instruction(Opcode.PRIM_2, "IF")),
            (condition, true_branch, false_branch),
        )

    def _reduce_y(self, arg: _Term, env: _Env) -> _ReductionGenerator:
        y_operator = self._new_instr(Instruction(Opcode.PRIM_2, "Y"))
        if not self._contract():
            return self._new_app(y_operator, (arg,))
        recursive_call = self._new_app(y_operator, (arg,))
        return (
            yield _ReductionRequest(
                self._new_app(arg, (recursive_call,)),
                env,
            )
        )

    def _reduce_logical(
        self,
        args: tuple[_Term, ...],
        env: _Env,
        *,
        true_identity: bool,
    ) -> _ReductionGenerator:
        if not args:
            return self._new_instr(TRUE if true_identity else FALSE)
        kept: list[_Term] = []
        for arg in args:
            reduced = yield _ReductionRequest(arg, env)
            inst = _term_instruction(reduced)
            if inst is not None and self.state.q > 0:
                if true_identity and inst == FALSE:
                    self._contract()
                    return self._new_instr(FALSE)
                if not true_identity and inst == TRUE:
                    self._contract()
                    return self._new_instr(TRUE)
                if (true_identity and inst == TRUE) or (
                    not true_identity and inst == FALSE
                ):
                    self._contract()
                    continue
            kept.append(reduced)
        if not kept:
            return self._new_instr(TRUE if true_identity else FALSE)
        return self._new_app(
            self._new_instr(
                Instruction(Opcode.PRIM_2, "AND" if true_identity else "OR")
            ),
            tuple(kept),
        )

    def _reduce_cons(
        self,
        operator: _Term,
        args: tuple[_Term, ...],
        env: _Env,
    ) -> _ReductionGenerator:
        head = yield _ReductionRequest(args[0], env)
        tail = yield _ReductionRequest(args[1], env)
        if not self._contract():
            return self._new_app(operator, (head, tail))
        return self._allocate_term(lambda: _StructTerm("PAIR", (head, tail)))

    def _reduce_accessor(
        self,
        name: str,
        tag: str,
        field_index: int,
        operator: _Term,
        arg: _Term,
        env: _Env,
    ) -> _ReductionGenerator:
        value = yield _ReductionRequest(arg, env)
        native_operator = (
            operator
            if isinstance(operator, _InstrTerm)
            else self._new_instr(Instruction(Opcode.PRIM_1, name))
        )
        if (
            not isinstance(value, _StructTerm)
            or value.tag != tag
            or field_index >= len(value.fields)
        ):
            return self._new_app(native_operator, (value,))
        if not self._contract():
            return self._new_app(native_operator, (value,))
        return (yield _ReductionRequest(value.fields[field_index], env))

    def _reduce_null(
        self,
        operator: _Term,
        arg: _Term,
        env: _Env,
    ) -> _ReductionGenerator:
        value = yield _ReductionRequest(arg, env)
        if _is_nil_term(value):
            if self._contract():
                return self._new_instr(TRUE)
            return self._new_app(operator, (value,))
        if _is_irreducible_term(value):
            return self._new_app(operator, (value,))
        if self._contract():
            return self._new_instr(FALSE)
        return self._new_app(operator, (value,))

    def _reduce_struct_application(
        self,
        operator: _StructTerm,
        args: tuple[_Term, ...],
        env: _Env,
    ) -> _ReductionGenerator:
        selector = yield _ReductionRequest(args[0], env)
        lambda_term, lambda_env = _as_lambda(selector, env)
        if lambda_term is None or not self._contract():
            return self._new_app(operator, (selector, *args[1:]))
        bind_count = min(len(lambda_term.params), len(operator.fields))
        field_closures = tuple(
            self._new_closure(field, env) for field in operator.fields[:bind_count]
        )
        reduced = yield _ReductionRequest(
            lambda_term.body,
            (*field_closures, *lambda_env),
        )
        if args[1:]:
            return (
                yield _ReductionRequest(
                    self._new_app(reduced, args[1:]),
                    env,
                )
            )
        return reduced

    def _reduce_letrec(
        self,
        letrec: _LetRecTerm,
        env: _Env,
    ) -> _ReductionGenerator:
        if not letrec.names:
            return (yield _ReductionRequest(letrec.body, env))
        recursive_entries = tuple(
            self._new_rec(index, letrec.names, letrec.expressions, ())
            for index in range(len(letrec.expressions))
        )
        recursive_env = (*recursive_entries, *env)
        for rec in recursive_entries:
            object.__setattr__(rec, "env", recursive_env)
        return (yield _ReductionRequest(letrec.body, recursive_env))

    def _reduce_rec(self, rec: _RecTerm) -> _ReductionGenerator:
        if self.state.q > 0:
            self._contract()
            return (
                yield _ReductionRequest(
                    rec.expressions[rec.index],
                    rec.env,
                )
            )
        placeholder_env: _Env = tuple(
            self._new_closure(self._new_var(index, name), ())
            for index, name in enumerate(rec.names)
        )
        expressions: list[_Term] = []
        for expr in rec.expressions:
            expressions.append(
                (
                    yield _ReductionRequest(
                        expr,
                        placeholder_env,
                        no_contract=True,
                    )
                )
            )
        return self._allocate_term(
            lambda: _LetRecTerm(
                rec.names,
                tuple(expressions),
                self._new_var(rec.index, rec.names[rec.index]),
            )
        )

    def _sync_memory(self) -> None:
        self.state.memory = [*self._problem_memory, *self._result]

    @staticmethod
    def _find_stop(image: ProgramImage) -> int:
        for index, inst in enumerate(image.instructions):
            if inst.opcode is Opcode.STOP:
                return index
        return max(len(image.instructions) - 1, 0)


type _ParseResult = tuple[_Term, int, bool]


@dataclass(frozen=True, slots=True)
class _ParseTermRequest:
    pc: int


@dataclass(frozen=True, slots=True)
class _ParseAppPartsRequest:
    app_insts: tuple[Instruction, ...]
    operator_pc: int


type _ParseRequest = _ParseTermRequest | _ParseAppPartsRequest
type _ParseGenerator = Generator[_ParseRequest, _ParseResult, _ParseResult]


class _ProgramParser:
    def __init__(
        self,
        memory: Sequence[Instruction],
        metadata: object | None = None,
        reserve_term: Callable[[], None] | None = None,
    ) -> None:
        self._memory = memory
        self._metadata = metadata if isinstance(metadata, dict) else {}
        self._reserve_term = reserve_term or (lambda: None)

    def parse(self, pc: int) -> _Term:
        term, _next_pc, _head = self._drive(self._parse_with_span(pc))
        return term

    def _drive(self, initial: _ParseGenerator) -> _ParseResult:
        stack = [initial]
        result: _ParseResult | None = None
        has_result = False
        while stack:
            generator = stack[-1]
            try:
                if has_result:
                    assert result is not None
                    request = generator.send(result)
                else:
                    request = next(generator)
            except StopIteration as stopped:
                result = stopped.value
                stack.pop()
                has_result = True
                continue
            if isinstance(request, _ParseTermRequest):
                child = self._parse_with_span(request.pc)
            else:
                child = self._parse_app_from_parts(
                    request.app_insts,
                    request.operator_pc,
                )
            stack.append(child)
            has_result = False
        assert result is not None
        return result

    def _make[TermT](self, factory: Callable[[], TermT]) -> TermT:
        self._reserve_term()
        return factory()

    def _parse_with_span(self, pc: int) -> _ParseGenerator:
        inst = self._memory[pc]
        if inst.opcode is Opcode.APP:
            return (yield from self._parse_app(pc))
        if inst.opcode is Opcode.LAMBDA:
            return (yield from self._parse_lambda(pc))
        if inst.opcode in {Opcode.VAR, Opcode.UBV}:
            term = self._make(lambda: _VarTerm(_int_data(inst)))
            return term, pc + 1, inst.head
        if inst.opcode is Opcode.STRUCT:
            return (yield from self._parse_struct(pc))
        if inst.opcode is Opcode.RBLOCK:
            return (yield from self._parse_letrec(pc))
        return self._make(lambda: _InstrTerm(inst)), pc + 1, inst.head

    def _parse_app(self, pc: int) -> _ParseGenerator:
        app_insts: list[Instruction] = []
        operator_pc = pc
        while (
            operator_pc < len(self._memory)
            and self._memory[operator_pc].opcode is Opcode.APP
        ):
            app_insts.append(self._memory[operator_pc])
            operator_pc += 1
        return (yield _ParseAppPartsRequest(tuple(app_insts), operator_pc))

    def _parse_app_from_parts(
        self,
        app_insts: tuple[Instruction, ...],
        operator_pc: int,
    ) -> _ParseGenerator:
        drop_index = _first_drop_index(tuple(_int_data(inst) for inst in app_insts))
        if drop_index is not None:
            inner, inner_next, inner_head = yield _ParseAppPartsRequest(
                app_insts[drop_index:],
                operator_pc,
            )
            outer_args_with_spans: list[_ParseResult] = []
            for inst in app_insts[:drop_index]:
                outer_args_with_spans.append((yield _ParseTermRequest(_int_data(inst))))
            outer_args = tuple(term for term, _next_pc, _head in outer_args_with_spans)
            next_pc = max(
                (
                    inner_next,
                    *(next_pc for _term, next_pc, _head in outer_args_with_spans),
                ),
                default=inner_next,
            )
            term = self._make(lambda: _AppTerm(inner, outer_args))
            return term, next_pc, inner_head

        operator, operator_next, operator_head = yield _ParseTermRequest(operator_pc)
        args_with_spans: list[_ParseResult] = []
        for inst in app_insts:
            args_with_spans.append((yield _ParseTermRequest(_int_data(inst))))
        args = tuple(term for term, _next_pc, _head in args_with_spans)
        next_pc = max(
            (operator_next, *(next_pc for _term, next_pc, _head in args_with_spans)),
            default=operator_next,
        )
        term = self._make(lambda: _AppTerm(operator, args))
        return term, next_pc, operator_head

    def _parse_lambda(self, pc: int) -> _ParseGenerator:
        params: list[str] = []
        body_pc = pc
        arity = _lambda_arity(self._metadata.get(f"lambda:{pc}:arity"))
        while (
            body_pc < len(self._memory)
            and self._memory[body_pc].opcode is Opcode.LAMBDA
            and (arity is None or len(params) < arity)
        ):
            data = self._memory[body_pc].data
            params.append(data if isinstance(data, str) else str(data))
            body_pc += 1
        body, next_pc, body_head = yield from self._parse_flat_body(body_pc)
        term = self._make(lambda: _LambdaTerm(tuple(params), body))
        return term, next_pc, body_head

    def _parse_flat_body(self, pc: int) -> _ParseGenerator:
        items: list[_Term] = []
        cursor = pc
        root_head = False
        while (
            cursor < len(self._memory)
            and self._memory[cursor].opcode is not Opcode.STOP
        ):
            term, cursor, root_head = yield _ParseTermRequest(cursor)
            items.append(term)
            if root_head:
                break
        if not items:
            term = self._make(lambda: _InstrTerm(Instruction(Opcode.STOP, 0)))
            return term, cursor, root_head
        if len(items) == 1:
            return items[0], cursor, root_head
        term = self._make(lambda: _AppTerm(items[0], tuple(items[1:])))
        return term, cursor, root_head

    def _parse_struct(self, pc: int) -> _ParseGenerator:
        inst = self._memory[pc]
        tag = inst.data if isinstance(inst.data, str) else str(inst.data)
        field_terms_with_spans: list[_ParseResult] = []
        cursor = pc + 1
        while cursor < len(self._memory) and self._memory[cursor].opcode is Opcode.APP:
            field_terms_with_spans.append(
                (yield _ParseTermRequest(_int_data(self._memory[cursor])))
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
        fields = tuple(
            term for term, _next_pc, _head in reversed(field_terms_with_spans)
        )
        term = self._make(lambda: _StructTerm(tag, fields))
        return term, next_pc, root_head

    def _parse_letrec(self, pc: int) -> _ParseGenerator:
        blocks: list[Instruction] = []
        cursor = pc
        while (
            cursor < len(self._memory) and self._memory[cursor].opcode is Opcode.RBLOCK
        ):
            blocks.append(self._memory[cursor])
            cursor += 1
        if cursor >= len(self._memory) or self._memory[cursor].opcode is not Opcode.RUP:
            inst = self._memory[pc]
            return self._make(lambda: _InstrTerm(inst)), pc + 1, inst.head
        names = self._metadata.get(f"letrec:{pc}:names")
        if not isinstance(names, tuple) or len(names) != len(blocks):
            names = tuple(_fallback_name(index) for index in range(len(blocks)))
        expressions_with_spans: list[_ParseResult] = []
        for block in blocks:
            expressions_with_spans.append((yield _ParseTermRequest(_int_data(block))))
        body, body_next, body_head = yield _ParseTermRequest(cursor + 1)
        next_pc = max(
            (
                body_next,
                *(next_pc for _term, next_pc, _head in expressions_with_spans),
            ),
            default=body_next,
        )
        expressions = tuple(term for term, _next_pc, _head in expressions_with_spans)
        term = self._make(lambda: _LetRecTerm(names, expressions, body))
        return term, next_pc, body_head


@dataclass(frozen=True, slots=True)
class _InstructionSpec:
    opcode: Opcode
    data: int | str | float | None
    head: bool


type _EmitWork = tuple[_Term, bool, bool] | _InstructionSpec


class _ResultEmitter:
    def __init__(self, reserve_instruction: Callable[[], None]) -> None:
        self._reserve_instruction = reserve_instruction

    def emit(self, term: _Term) -> list[Instruction]:
        out: list[Instruction] = []
        work: list[_EmitWork] = [(term, True, False)]
        while work:
            item = work.pop()
            if isinstance(item, _InstructionSpec):
                self._reserve_instruction()
                out.append(Instruction(item.opcode, item.data, item.head))
                continue
            current, head, omit_lambda_body = item
            if isinstance(current, _ClosureTerm):
                work.append((current.term, head, omit_lambda_body))
                continue
            if isinstance(current, _RecTerm):
                work.append(
                    _InstructionSpec(
                        Opcode.VAR,
                        current.names[current.index],
                        head,
                    )
                )
                pairs = tuple(zip(current.names, current.expressions, strict=True))
                for name, child_term in reversed(pairs):
                    work.append((child_term, False, False))
                    work.append(_InstructionSpec(Opcode.RBLOCK, name, False))
                work.append(_InstructionSpec(Opcode.RUP, len(current.names), False))
                continue
            if isinstance(current, _VarTerm):
                work.append(
                    _InstructionSpec(
                        Opcode.VAR,
                        current.name if current.name is not None else current.index,
                        head,
                    )
                )
                continue
            if isinstance(current, _InstrTerm):
                work.append(
                    _InstructionSpec(current.inst.opcode, current.inst.data, head)
                )
                continue
            if isinstance(current, _StructTerm):
                last_index = len(current.fields) - 1
                for index in range(last_index, -1, -1):
                    work.append(
                        (
                            current.fields[index],
                            head if index == last_index else False,
                            False,
                        )
                    )
                work.append(_InstructionSpec(Opcode.STRUCT, current.tag, False))
                continue
            if isinstance(current, _LetRecTerm):
                work.append((current.body, head, False))
                pairs = tuple(zip(current.names, current.expressions, strict=True))
                for name, child_term in reversed(pairs):
                    work.append((child_term, False, False))
                    work.append(_InstructionSpec(Opcode.RBLOCK, name, False))
                work.append(_InstructionSpec(Opcode.RUP, len(current.names), False))
                continue
            if isinstance(current, _LambdaTerm):
                if not omit_lambda_body:
                    work.append((current.body, head, False))
                for param in reversed(current.params):
                    work.append(_InstructionSpec(Opcode.LAMBDA, param, False))
                continue
            if isinstance(current, _AppTerm):
                last_index = len(current.args) - 1
                for index in range(last_index, -1, -1):
                    work.append(
                        (
                            current.args[index],
                            head if index == last_index else False,
                            False,
                        )
                    )
                work.append((current.operator, False, True))
                for _arg in current.args:
                    work.append(_InstructionSpec(Opcode.APP, len(current.args), False))
                continue
            assert_never(current)
        return out


def _term_to_expr(
    term: _Term,
    reserve_expr: Callable[[], None] | None = None,
) -> Expr:
    reserve = reserve_expr or (lambda: None)
    work: list[tuple[_Term, _Env, tuple[str, ...], bool]] = [(term, (), (), False)]
    results: list[Expr] = []
    while work:
        current, env, bound_names, visited = work.pop()
        if isinstance(current, _ClosureTerm):
            work.append((current.term, current.env, bound_names, False))
            continue
        if not visited:
            if isinstance(current, _VarTerm):
                if current.index < len(bound_names):
                    reserve()
                    results.append(Var(current.index, current.name))
                    continue
                env_index = current.index - len(bound_names)
                if 0 <= env_index < len(env):
                    work.append((env[env_index], (), (), False))
                    continue
                reserve()
                results.append(Var(current.index, current.name))
                continue
            if isinstance(current, _InstrTerm):
                reserve()
                expr = instruction_to_expr(current.inst)
                results.append(expr or Symbol(current.inst.opcode.name))
                continue
            work.append((current, env, bound_names, True))
            if isinstance(current, _RecTerm):
                child_bound_names = current.names + bound_names
                for child_term in reversed(current.expressions):
                    work.append((child_term, current.env, child_bound_names, False))
            elif isinstance(current, _LambdaTerm):
                work.append((current.body, env, current.params + bound_names, False))
            elif isinstance(current, _AppTerm):
                for arg in reversed(current.args):
                    work.append((arg, env, bound_names, False))
                work.append((current.operator, env, bound_names, False))
            elif isinstance(current, _StructTerm):
                for field in reversed(current.fields):
                    work.append((field, env, bound_names, False))
            elif isinstance(current, _LetRecTerm):
                child_bound_names = current.names + bound_names
                work.append((current.body, env, child_bound_names, False))
                for child_term in reversed(current.expressions):
                    work.append((child_term, env, child_bound_names, False))
            else:
                assert_never(current)
            continue

        reserve()
        if isinstance(current, _VarTerm | _InstrTerm):
            msg = "terminal RED2 term reached materialization continuation"
            raise AssertionError(msg)
        if isinstance(current, _RecTerm):
            count = len(current.expressions)
            rec_expressions = tuple(results[-count:]) if count else ()
            if count:
                del results[-count:]
            reserve()
            rec_body = Var(current.index, current.names[current.index])
            bindings_list: list[Binding] = []
            for name, expression_value in zip(
                current.names,
                rec_expressions,
                strict=True,
            ):
                reserve()
                bindings_list.append(Binding(name, expression_value))
            results.append(LetRec(tuple(bindings_list), rec_body))
        elif isinstance(current, _LambdaTerm):
            results.append(Lambda(current.params, results.pop()))
        elif isinstance(current, _AppTerm):
            count = len(current.args) + 1
            items = tuple(results[-count:])
            del results[-count:]
            results.append(App(items))
        elif isinstance(current, _StructTerm):
            count = len(current.fields)
            fields = tuple(results[-count:]) if count else ()
            if count:
                del results[-count:]
            results.append(StructLit(current.tag, fields))
        elif isinstance(current, _LetRecTerm):
            count = len(current.expressions)
            letrec_values = results[-(count + 1) :]
            del results[-(count + 1) :]
            letrec_expressions = letrec_values[:count]
            letrec_body = letrec_values[count]
            bindings_list = []
            for name, expression_value in zip(
                current.names,
                letrec_expressions,
                strict=True,
            ):
                reserve()
                bindings_list.append(Binding(name, expression_value))
            results.append(LetRec(tuple(bindings_list), letrec_body))
        else:
            assert_never(current)
    assert len(results) == 1
    return results[0]


def _lambda_arity(metadata: object) -> int | None:
    if (
        isinstance(metadata, tuple)
        and len(metadata) == 1
        and isinstance(metadata[0], str)
    ):
        try:
            return int(metadata[0])
        except ValueError:
            return None
    return None


def _parse_definitions(
    definitions: DefinitionImage | None,
    *,
    reserve_instructions: Callable[[int], None],
    reserve_term: Callable[[], None],
) -> dict[str, _Term]:
    if definitions is None:
        return {}
    parsed: dict[str, _Term] = {}
    for name, image in definitions.programs.items():
        reserve_instructions(len(image.instructions))
        parsed[name] = _ProgramParser(
            image.instructions,
            image.metadata,
            reserve_term,
        ).parse(image.entry)
    return parsed


def _term_count(term: _Term) -> int:
    """Count modeled heap cells in a decoded RED2 term graph iteratively."""
    count = 0
    work = [term]
    while work:
        current = work.pop()
        count += 1
        if isinstance(current, _ClosureTerm):
            work.append(current.term)
        elif isinstance(current, _LambdaTerm):
            work.append(current.body)
        elif isinstance(current, _AppTerm):
            work.extend(reversed(current.args))
            work.append(current.operator)
        elif isinstance(current, _StructTerm):
            work.extend(reversed(current.fields))
        elif isinstance(current, _LetRecTerm):
            work.append(current.body)
            work.extend(reversed(current.expressions))
        elif isinstance(current, _RecTerm):
            work.extend(reversed(current.expressions))
        elif not isinstance(current, _VarTerm | _InstrTerm):
            assert_never(current)
    return count


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

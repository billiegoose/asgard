from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto
from math import ceil, floor

from thor_lang.ast import (
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


class MuredOpcode(StrEnum):
    APP = auto()
    APP_VAR = auto()
    CLOSURE = auto()
    JOIN = auto()
    LAMBDA = auto()
    STOP = auto()
    INT = auto()
    FLOAT = auto()
    CHAR = auto()
    SYM = auto()
    PRIM_0 = auto()
    PRIM_1 = auto()
    PRIM_2 = auto()
    STRUCT = auto()
    RBLOCK = auto()
    RUP = auto()
    RECP = auto()
    REC = auto()
    UBV = auto()
    VAR = auto()
    PNP = auto()


class Direction(StrEnum):
    F = auto()
    B = auto()


_STRICT_UNARY_PRIMITIVES = frozenset(
    {
        "1-",
        "1+",
        "ABS",
        "CAR",
        "CDR",
        "CEILING",
        "EVEN?",
        "FLOOR",
        "MINUS",
        "NULL?",
        "NOT",
        "TAG",
        "INTEGER?",
        "FLOAT?",
        "CHAR?",
        "SYMBOL?",
        "STRUCTURE?",
    }
)
_STRICT_BINARY_PRIMITIVES = frozenset(
    {
        "+",
        "-",
        "*",
        "/",
        "<",
        ">",
        "<=",
        ">=",
        "=",
        "CONS",
        "EQUAL?",
        "EXPT",
        "MAX",
        "MIN",
        "MOD",
    }
)
_NON_STRICT_PRIMITIVES = frozenset({"IF", "Y", "AND", "OR"})


@dataclass(frozen=True, slots=True)
class Word:
    opcode: MuredOpcode | None
    data: int | float | str | None = None
    head: bool = False
    definition: int | None = None


class MuredMachineError(RuntimeError):
    pass


class InvalidAddress(MuredMachineError):  # noqa: N818
    pass


class GraphEnvironmentCollision(MuredMachineError):  # noqa: N818
    pass


class ControlStackOverflow(MuredMachineError):  # noqa: N818
    pass


class ControlStackUnderflow(MuredMachineError):  # noqa: N818
    pass


class MalformedClosure(MuredMachineError):  # noqa: N818
    pass


class IllegalTransition(MuredMachineError):  # noqa: N818
    pass


class CycleLimitExceeded(MuredMachineError):  # noqa: N818
    pass


def compile_lambda(expr: Expr) -> tuple[Word, ...]:
    words: list[Word] = []

    def compile_var_index(
        index: int,
        scope: tuple[str | None, ...],
        name: str | None = None,
    ) -> int:
        if name is not None and name in scope:
            return scope.index(name)
        source_index = 0
        synthetic_slots = 0
        for compiled_index, scope_name in enumerate(scope):
            if scope_name is None:
                synthetic_slots += 1
                continue
            if source_index == index:
                return compiled_index
            source_index += 1
        return index + synthetic_slots

    def compile_inline_argument(
        node: Expr,
        scope: tuple[str | None, ...],
    ) -> int | None:
        if isinstance(node, Var):
            return compile_var_index(node.index, scope, node.name)
        if isinstance(node, Symbol) and node.name in scope:
            return scope.index(node.name)
        return None

    def compile_graph(
        node: Expr,
        scope: tuple[str | None, ...],
        *,
        head: bool,
    ) -> None:
        if isinstance(node, Var):
            words.append(
                Word(
                    MuredOpcode.VAR,
                    compile_var_index(node.index, scope, node.name),
                    head,
                )
            )
            return
        if isinstance(node, Symbol):
            if node.name in scope:
                words.append(Word(MuredOpcode.VAR, scope.index(node.name), head))
            elif node.name in _STRICT_UNARY_PRIMITIVES:
                words.append(Word(MuredOpcode.PRIM_1, node.name, head))
            elif node.name in _STRICT_BINARY_PRIMITIVES:
                words.append(Word(MuredOpcode.PRIM_2, node.name, head))
            elif node.name in _NON_STRICT_PRIMITIVES:
                words.append(Word(MuredOpcode.PRIM_0, node.name, head))
            else:
                words.append(Word(MuredOpcode.SYM, node.name, head))
            return
        if isinstance(node, Integer):
            words.append(Word(MuredOpcode.INT, node.value, head))
            return
        if isinstance(node, Float):
            words.append(Word(MuredOpcode.FLOAT, node.value, head))
            return
        if isinstance(node, Char):
            words.append(Word(MuredOpcode.CHAR, node.value, head))
            return
        if isinstance(node, Lambda):
            for parameter in node.params:
                words.append(Word(MuredOpcode.LAMBDA, parameter, False))
            compile_graph(
                node.body,
                tuple(reversed(node.params)) + scope,
                head=head,
            )
            return
        if isinstance(node, LetRec):
            names = tuple(binding.name for binding in node.bindings)
            recursive_scope = tuple(reversed(names)) + scope
            block_start = len(words)
            words.extend(Word(MuredOpcode.RBLOCK) for _ in node.bindings)
            words.append(Word(MuredOpcode.RUP, len(node.bindings), False))
            compile_graph(node.body, recursive_scope, head=head)
            for offset, binding in enumerate(node.bindings):
                binding_address = len(words)
                words[block_start + offset] = Word(
                    MuredOpcode.RBLOCK,
                    binding_address,
                    False,
                )
                words.append(Word(MuredOpcode.SYM, binding.name, False))
                compile_graph(binding.expr, recursive_scope, head=True)
            return
        if isinstance(node, StructLit):
            words.append(Word(MuredOpcode.STRUCT, node.tag, False))
            app_start = len(words)
            fields = tuple(reversed(node.fields))
            words.extend(Word(MuredOpcode.APP) for _ in fields)
            words.append(Word(MuredOpcode.VAR, 0, head))
            field_scope = (None, *scope)
            for offset, field in enumerate(fields):
                field_address = len(words)
                words[app_start + offset] = Word(
                    MuredOpcode.APP,
                    field_address,
                    False,
                )
                compile_graph(field, field_scope, head=True)
            return
        if isinstance(node, App):
            if len(node.items) < 2:
                raise TypeError("malformed pure λ-calculus application")
            app_start = len(words)
            arguments = tuple(reversed(node.items[1:]))
            inline_indices = tuple(
                compile_inline_argument(argument, scope) for argument in arguments
            )
            words.extend(
                Word(MuredOpcode.APP_VAR, index, False)
                if index is not None
                else Word(MuredOpcode.APP)
                for index in inline_indices
            )
            compile_graph(node.items[0], scope, head=True)
            for offset, argument in enumerate(arguments):
                if inline_indices[offset] is not None:
                    continue
                argument_address = len(words)
                words[app_start + offset] = Word(
                    MuredOpcode.APP, argument_address, False
                )
                compile_graph(argument, scope, head=True)
            return
        raise TypeError(
            f"pure λ-calculus expression required, got {type(node).__name__}"
        )

    compile_graph(expr, (), head=True)
    return tuple(words)


@dataclass(frozen=True, slots=True)
class _SavedPrim:
    value: str


@dataclass(frozen=True, slots=True)
class _SavedFire:
    value: int


@dataclass(frozen=True, slots=True)
class _SavedQuantum:
    value: int


_ControlEntry = int | _SavedPrim | _SavedFire | _SavedQuantum | None


@dataclass(slots=True)
class MuredMachineState:
    memory: list[Word | None]
    control_stack: list[_ControlEntry]
    pc: int
    fsp: int
    env: int
    c: int
    direction: Direction
    q: int
    phi: int
    argcnt: int = 0
    prim: str | None = None
    fire: int = 0
    s_a: int | None = None
    s_d: int | None = None
    halted: bool = False
    cycles: int = 0


class MuredMachine:
    def __init__(self, state: MuredMachineState) -> None:
        self.state = state

    @classmethod
    def load(
        cls,
        problem: Sequence[Word],
        *,
        quantum: int,
        memory_words: int = 256,
        control_words: int = 64,
    ) -> MuredMachine:
        if quantum < 0:
            raise ValueError("quantum must be non-negative")
        if memory_words <= 0:
            raise ValueError("memory_words must be positive")
        if control_words <= 0:
            raise ValueError("control_words must be positive")
        if not problem:
            raise ValueError("problem graph must not be empty")
        allowed = {
            MuredOpcode.APP,
            MuredOpcode.APP_VAR,
            MuredOpcode.CHAR,
            MuredOpcode.FLOAT,
            MuredOpcode.INT,
            MuredOpcode.LAMBDA,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
            MuredOpcode.STRUCT,
            MuredOpcode.RBLOCK,
            MuredOpcode.RUP,
            MuredOpcode.RECP,
            MuredOpcode.SYM,
            MuredOpcode.VAR,
        }
        if any(word.opcode not in allowed for word in problem):
            raise ValueError("problem graph contains a non-μRED source instruction")
        stop_address = len(problem)
        if stop_address >= memory_words:
            raise GraphEnvironmentCollision("graph and environment collide")
        memory: list[Word | None] = [None] * memory_words
        memory[:stop_address] = problem
        memory[stop_address] = Word(MuredOpcode.STOP)
        return cls(
            MuredMachineState(
                memory=memory,
                control_stack=[None] * control_words,
                pc=0,
                fsp=stop_address,
                env=memory_words,
                c=-1,
                direction=Direction.F,
                q=quantum,
                phi=0,
            )
        )

    @classmethod
    def from_expr(
        cls,
        expr: Expr,
        *,
        quantum: int,
        memory_words: int = 256,
        control_words: int = 64,
    ) -> MuredMachine:
        return cls.load(
            compile_lambda(expr),
            quantum=quantum,
            memory_words=memory_words,
            control_words=control_words,
        )

    def step(self) -> MuredMachineState:
        state = self.state
        if state.halted:
            return state
        self._validate_state()
        word = self._word(state.pc)
        match word.opcode:
            case MuredOpcode.APP:
                self._app(word)
            case MuredOpcode.APP_VAR:
                self._app_var(word)
            case MuredOpcode.CLOSURE:
                self._closure(word)
            case MuredOpcode.JOIN:
                self._join(word)
            case MuredOpcode.LAMBDA:
                self._lambda(word)
            case MuredOpcode.STOP:
                self._stop()
            case MuredOpcode.INT:
                self._int(word)
            case MuredOpcode.FLOAT:
                self._float(word)
            case MuredOpcode.CHAR:
                self._char(word)
            case MuredOpcode.SYM:
                self._sym(word)
            case MuredOpcode.PRIM_0 | MuredOpcode.PRIM_1 | MuredOpcode.PRIM_2:
                self._prim(word)
            case MuredOpcode.STRUCT:
                self._struct(word)
            case MuredOpcode.RBLOCK:
                self._rblock(word)
            case MuredOpcode.RUP:
                self._rup(word)
            case MuredOpcode.RECP:
                self._recp(word)
            case MuredOpcode.UBV:
                self._ubv(word)
            case MuredOpcode.VAR:
                self._var(word)
            case MuredOpcode.REC | MuredOpcode.PNP | None:
                raise IllegalTransition(f"{word.opcode} is environment data")
        self._validate_state()
        state.cycles += 1
        return state

    def _validate_state(self) -> None:
        state = self.state
        size = len(state.memory)
        if not 0 <= state.fsp < state.env <= size:
            raise GraphEnvironmentCollision("graph and environment collide")
        if not -1 <= state.c < len(state.control_stack):
            raise InvalidAddress(f"invalid μRED control pointer: {state.c}")
        if state.q < 0 or state.phi < 0 or state.argcnt < -1 or state.fire < 0:
            raise IllegalTransition("μRED counters are outside their valid ranges")
        if state.prim is not None and (type(state.prim) is not str or state.prim == ""):
            raise IllegalTransition("prim register requires a symbol name")
        self._word(state.pc)

    def _push_graph(self, word: Word) -> int:
        address = self.state.fsp + 1
        if address >= self.state.env:
            raise GraphEnvironmentCollision("graph and environment collide")
        self.state.memory[address] = word
        self.state.fsp = address
        return address

    def _copy_result(self, word: Word) -> int:
        address = self._push_graph(word)
        self.state.argcnt += 1
        return address

    def _allocate_environment(self, word: Word) -> int:
        address = self.state.env - 1
        if address <= self.state.fsp:
            raise GraphEnvironmentCollision("graph and environment collide")
        self.state.memory[address] = word
        self.state.env = address
        return address

    def _push_control_entry(self, value: _ControlEntry) -> None:
        if value is None:
            raise IllegalTransition("cannot push an empty control-stack entry")
        next_c = self.state.c + 1
        if next_c >= len(self.state.control_stack):
            raise ControlStackOverflow("μRED control stack overflow")
        self.state.control_stack[next_c] = value
        self.state.c = next_c

    def _pop_control_entry(self) -> _ControlEntry:
        if self.state.c < 0:
            raise ControlStackUnderflow("μRED control stack underflow")
        value = self.state.control_stack[self.state.c]
        self.state.control_stack[self.state.c] = None
        self.state.c -= 1
        if value is None:
            raise ControlStackUnderflow("μRED control stack entry is empty")
        return value

    def _push_control(self, address: int) -> None:
        self._push_control_entry(address)

    def _pop_control(self) -> int:
        value = self._pop_control_entry()
        if type(value) is not int:
            raise IllegalTransition("expected an environment path on the control stack")
        return value

    def _save_primitive_context(self) -> None:
        state = self.state
        if state.fire == 0:
            return
        if state.prim is None:
            raise IllegalTransition("active primitive countdown requires prim")
        if state.c + 2 >= len(state.control_stack):
            raise ControlStackOverflow("μRED control stack overflow")
        self._push_control_entry(_SavedPrim(state.prim))
        self._push_control_entry(_SavedFire(state.fire))
        state.prim = None
        state.fire = 0

    def _has_saved_primitive_context(self) -> bool:
        state = self.state
        return state.c >= 0 and isinstance(
            state.control_stack[state.c], _SavedFire
        )

    def _restore_primitive_context(self) -> bool:
        if not self._has_saved_primitive_context():
            return False
        fire_entry = self._pop_control_entry()
        prim_entry = self._pop_control_entry()
        if not isinstance(fire_entry, _SavedFire) or not isinstance(
            prim_entry, _SavedPrim
        ):
            raise IllegalTransition("malformed primitive context on control stack")
        self.state.prim = prim_entry.value
        self.state.fire = fire_entry.value
        return True

    def lookup(self, index: int) -> int:
        if index < 0:
            raise InvalidAddress(f"negative μRED variable index: {index}")
        self.state.s_d = index
        address = self.state.env
        while True:
            word = self._word(address)
            if word.opcode is MuredOpcode.PNP:
                if not isinstance(word.data, int):
                    raise InvalidAddress("PNP requires an address")
                address = word.data
                continue
            if self.state.s_d == 0:
                self.state.s_a = address
                return address
            self.state.s_d -= 1
            if word.opcode is MuredOpcode.UBV:
                address += 1
            elif word.opcode is MuredOpcode.REC:
                address += 3
            else:
                address += 2

    def _app(self, word: Word) -> None:
        state = self.state
        if state.direction is Direction.F:
            self._copy_result(word)
            self._push_control(state.env)
            state.pc += 1
            return
        if word.definition is not None and state.q > 0:
            if not isinstance(word.definition, int):
                raise InvalidAddress("APP definition requires an address")
            self.state.memory[state.pc] = Word(MuredOpcode.STOP)
            state.pc = word.definition
            state.direction = Direction.F
            state.q -= 1
            return
        if not isinstance(word.data, int):
            raise InvalidAddress("APP requires an argument address")
        parent_app = state.pc
        state.env = self._pop_control()
        saves_primitive = state.fire > 0
        self._save_primitive_context()
        self._push_graph(
            Word(
                MuredOpcode.JOIN,
                parent_app,
                False,
                1 if saves_primitive else None,
            )
        )
        state.argcnt = 0
        state.pc = word.data
        state.direction = Direction.F

    def _closure(self, word: Word) -> None:
        if self.state.direction is not Direction.F:
            raise IllegalTransition("CLOSURE requires forward execution")
        if not isinstance(word.data, int):
            raise MalformedClosure("CLOSURE requires an environment address")
        code = self._word(self.state.pc + 1)
        if code.opcode is not None or not isinstance(code.data, int):
            raise MalformedClosure("CLOSURE requires a following code pointer")
        self._allocate_environment(Word(MuredOpcode.PNP, word.data, False))
        self.state.pc = code.data

    def _join(self, word: Word) -> None:
        state = self.state
        if state.direction is not Direction.B:
            raise IllegalTransition("JOIN requires backward execution")
        if not isinstance(word.data, int):
            raise InvalidAddress("JOIN requires a parent APP address")
        state.s_a = state.pc + 1
        parent = self._word(word.data)
        if parent.opcode not in {
            MuredOpcode.APP,
            MuredOpcode.RBLOCK,
            MuredOpcode.RECP,
        }:
            raise IllegalTransition("JOIN parent must be APP, RBLOCK, or RECP")
        tail = self._word(state.s_a)
        saved_primitive = word.definition == 1
        if saved_primitive and not self._has_saved_primitive_context():
            raise IllegalTransition(
                "JOIN primitive context marker has no saved context"
            )
        single_word = state.fsp == state.s_a
        if parent.opcode is MuredOpcode.RBLOCK:
            state.memory[word.data] = Word(
                MuredOpcode.RBLOCK,
                state.s_a,
                parent.head,
                parent.definition,
            )
        elif parent.opcode is MuredOpcode.RECP:
            state.memory[word.data] = Word(MuredOpcode.APP, state.s_a, False)
        elif tail.opcode is MuredOpcode.VAR and single_word:
            if type(tail.data) is not int or tail.data < 0:
                raise InvalidAddress("result VAR requires a De Bruijn index")
            state.memory[word.data] = Word(MuredOpcode.APP_VAR, tail.data, False)
            state.fsp -= 2
        elif saved_primitive and single_word:
            state.memory[word.data] = Word(
                tail.opcode,
                tail.data,
                False,
                tail.definition,
            )
            state.fsp -= 2
        else:
            state.memory[word.data] = Word(MuredOpcode.APP, state.s_a, False)

        if saved_primitive:
            if not self._restore_primitive_context():
                raise IllegalTransition("JOIN failed to restore primitive context")
            if state.fire <= 0 or state.prim is None:
                raise IllegalTransition("restored primitive context is not active")
            state.fire -= 1
            if state.fire == 0:
                state.pc = word.data
                self._fire_primitive()
                return
        state.pc = word.data - 1

    def _lambda(self, word: Word) -> None:
        state = self.state
        if state.direction is Direction.B:
            state.phi -= 1
            if state.phi < 0:
                raise IllegalTransition("LAMBDA reverse underflows phi")
            state.pc -= 1
            return
        result_head = self._word(state.fsp)
        if state.q == 0 or result_head.opcode not in {
            MuredOpcode.APP,
            MuredOpcode.APP_VAR,
        }:
            self._copy_result(word)
            state.argcnt = 0
            state.phi += 1
            self._allocate_environment(Word(MuredOpcode.UBV, state.phi, False))
            state.pc += 1
            return
        if result_head.opcode is MuredOpcode.APP_VAR:
            if type(result_head.data) is not int or result_head.data < 0:
                raise InvalidAddress("result APP_VAR requires a variable index")
            self._allocate_environment(
                Word(MuredOpcode.UBV, state.phi - result_head.data, False)
            )
            state.q -= 1
            state.fsp -= 1
            state.argcnt -= 1
            state.pc += 1
            return
        if not isinstance(result_head.data, int):
            raise InvalidAddress("result APP requires an argument address")
        saved_path = self._pop_control()
        self._allocate_environment(Word(None, result_head.data, False))
        self._allocate_environment(Word(MuredOpcode.CLOSURE, saved_path, False))
        state.q -= 1
        state.fsp -= 1
        state.argcnt -= 1
        state.pc += 1

    def _struct(self, word: Word) -> None:
        if type(word.data) is not str or word.data == "":
            raise IllegalTransition("STRUCT requires a non-empty tag name")
        state = self.state
        if state.direction is Direction.B:
            saved_quantum = self._pop_control_entry()
            if not isinstance(saved_quantum, _SavedQuantum):
                raise IllegalTransition("STRUCT reverse lost saved quantum")
            state.q = saved_quantum.value
            state.phi -= 1
            if state.phi < 0:
                raise IllegalTransition("STRUCT reverse underflows phi")
            state.pc -= 1
            return

        result_head = self._word(state.fsp)
        if state.q == 0 or result_head.opcode not in {
            MuredOpcode.APP,
            MuredOpcode.APP_VAR,
        }:
            self._push_control_entry(_SavedQuantum(state.q))
            state.q = 0
            self._copy_result(word)
            state.argcnt = 0
            state.phi += 1
            self._allocate_environment(Word(MuredOpcode.UBV, state.phi, False))
            state.pc += 1
            return

        if result_head.opcode is MuredOpcode.APP_VAR:
            if type(result_head.data) is not int or result_head.data < 0:
                raise InvalidAddress("result APP_VAR requires a variable index")
            self._allocate_environment(
                Word(MuredOpcode.UBV, state.phi - result_head.data, False)
            )
            state.q -= 1
            state.fsp -= 1
            state.argcnt -= 1
            state.pc += 1
            return

        if not isinstance(result_head.data, int):
            raise InvalidAddress("result APP requires an argument address")
        saved_path = self._pop_control()
        self._allocate_environment(Word(None, result_head.data, False))
        self._allocate_environment(Word(MuredOpcode.CLOSURE, saved_path, False))
        state.q -= 1
        state.fsp -= 1
        state.argcnt -= 1
        state.pc += 1

    def _rblock(self, word: Word) -> None:
        state = self.state
        if type(word.data) is not int or word.data < 0:
            raise InvalidAddress("RBLOCK requires a binding graph address")
        if state.direction is Direction.B:
            state.env = self._pop_control()
            saves_primitive = state.fire > 0
            self._save_primitive_context()
            self._push_graph(
                Word(
                    MuredOpcode.JOIN,
                    state.pc,
                    False,
                    1 if saves_primitive else None,
                )
            )
            state.pc = word.data
            state.argcnt = -1
            state.direction = Direction.F
            return

        if state.q > 0:
            address = state.env - 3
            if address <= state.fsp:
                raise GraphEnvironmentCollision("graph and environment collide")
            state.memory[address] = Word(MuredOpcode.REC, word.data + 1, False)
            state.memory[address + 1] = Word(None)
            state.memory[address + 2] = Word(None)
            state.env = address
        else:
            self._copy_result(word)
            state.phi += 1
            self._allocate_environment(Word(MuredOpcode.UBV, state.phi, False))
        state.pc += 1

    def _rup(self, word: Word) -> None:
        state = self.state
        if type(word.data) is not int or word.data < 0:
            raise IllegalTransition("RUP requires a non-negative binding count")
        if state.direction is Direction.B:
            state.pc -= 1
            return

        count = word.data
        if state.q > 0:
            address = state.env
            block_address = state.pc - count
            for _ in range(count):
                rec = self._word(address)
                if rec.opcode is not MuredOpcode.REC:
                    raise IllegalTransition(
                        "RUP requires contiguous REC environment data"
                    )
                self._word(address + 1)
                self._word(address + 2)
                state.memory[address + 1] = Word(None, state.env, False)
                state.memory[address + 2] = Word(None, block_address, False)
                address += 3
        else:
            for _ in range(count):
                self._push_control(state.env)
            self._copy_result(word)
        state.pc += 1

    def _rec_fields(self, address: int) -> tuple[int, int, int]:
        rec = self._word(address)
        if rec.opcode is not MuredOpcode.REC:
            raise IllegalTransition("RECP requires a REC environment value")
        if type(rec.data) is not int or rec.data < 0:
            raise InvalidAddress("REC requires a binding graph address")
        context = self._word(address + 1)
        block = self._word(address + 2)
        if context.opcode is not None or type(context.data) is not int:
            raise InvalidAddress("REC requires a recursive-context pointer")
        if block.opcode is not None or type(block.data) is not int:
            raise InvalidAddress("REC requires a BLOCK pointer")
        return rec.data, context.data, block.data

    def _recp(self, word: Word) -> None:
        state = self.state
        if type(word.data) is not int or word.data < 0:
            raise InvalidAddress("RECP requires a REC address")
        binding_address, context, _block = self._rec_fields(word.data)

        if state.direction is Direction.F:
            if not word.head:
                self._copy_result(word)
                state.pc += 1
                return
            if state.q > 0:
                self._allocate_environment(Word(MuredOpcode.PNP, context, False))
                state.pc = binding_address
                state.q -= 1
                return
            self._reconstruct(word.data)
            return

        if state.q > 0:
            state.memory[state.pc] = Word(MuredOpcode.APP, binding_address, False)
            self._push_control(context)
            state.q -= 1
            return

        parent_recp = state.pc
        saves_primitive = state.fire > 0
        self._save_primitive_context()
        self._push_graph(
            Word(
                MuredOpcode.JOIN,
                parent_recp,
                False,
                1 if saves_primitive else None,
            )
        )
        self._reconstruct(word.data)

    def _reconstruct(self, rec_address: int) -> None:
        state = self.state
        _binding_address, context, block_address = self._rec_fields(rec_address)

        source_blocks: list[Word] = []
        cursor = block_address
        while True:
            source = self._word(cursor)
            if source.opcode is not MuredOpcode.RBLOCK:
                break
            if type(source.data) is not int or source.data < 0:
                raise InvalidAddress("RBLOCK requires a binding graph address")
            source_blocks.append(source)
            cursor += 1
        count = len(source_blocks)
        if count == 0:
            raise IllegalTransition("RECONSTRUCT requires at least one RBLOCK")
        rup = self._word(cursor)
        if rup.opcode is not MuredOpcode.RUP or rup.data != count:
            raise IllegalTransition("RECONSTRUCT requires matching RUP binding count")

        selected_delta = rec_address - context
        if selected_delta < 0 or selected_delta % 3 != 0:
            raise InvalidAddress("RECP does not point inside its recursive context")
        selected_index = selected_delta // 3
        if selected_index >= count:
            raise InvalidAddress("RECP recursive binding index is outside BLOCK")

        parent_environment = context + 3 * count
        self._allocate_environment(
            Word(MuredOpcode.PNP, parent_environment, False)
        )
        for _ in source_blocks:
            state.phi += 1
            self._allocate_environment(Word(MuredOpcode.UBV, state.phi, False))
        replacement_path = state.env

        for source in source_blocks:
            self._copy_result(source)
        for _ in source_blocks:
            self._push_control(replacement_path)
        self._copy_result(rup)
        self._copy_result(Word(MuredOpcode.VAR, selected_index, True))
        state.pc = state.fsp - 1
        state.direction = Direction.B

    def _stop(self) -> None:
        if self.state.direction is not Direction.B:
            raise IllegalTransition("STOP requires backward execution")
        self.state.pc += 1
        self.state.halted = True

    def _passive(self, word: Word) -> None:
        if self.state.direction is Direction.B:
            self.state.pc -= 1
            return
        self._copy_result(word)
        if word.head:
            self.state.pc = self.state.fsp - 1
            self.state.direction = Direction.B
        else:
            self.state.pc += 1

    def _int(self, word: Word) -> None:
        if type(word.data) is not int:
            raise IllegalTransition("INT requires an integer value")
        self._passive(word)

    def _float(self, word: Word) -> None:
        if type(word.data) is not float:
            raise IllegalTransition("FLOAT requires a floating-point value")
        self._passive(word)

    def _char(self, word: Word) -> None:
        if type(word.data) is not str or len(word.data) != 1:
            raise IllegalTransition("CHAR requires a single-character string")
        self._passive(word)

    def _sym(self, word: Word) -> None:
        if type(word.data) is not str or word.data == "":
            raise IllegalTransition("SYM requires a non-empty symbol name")
        state = self.state
        if state.direction is Direction.B:
            if word.head and word.definition is not None and state.q > 0:
                if not isinstance(word.definition, int) or word.definition < 0:
                    raise InvalidAddress("SYM definition requires an address")
                next_path = state.pc - 1
                if next_path < 0:
                    raise InvalidAddress("SYM definition requires a continuation")
                self._push_control(state.env)
                self.state.memory[state.pc] = Word(
                    MuredOpcode.APP,
                    next_path,
                    word.head,
                    word.definition,
                )
                state.argcnt -= 1
                return
            state.pc -= 1
            return
        if word.head and word.definition is not None and state.q > 0:
            if not isinstance(word.definition, int) or word.definition < 0:
                raise InvalidAddress("SYM definition requires an address")
            self._copy_result(word)
            state.pc = state.fsp
            state.direction = Direction.B
            return
        self._copy_result(word)
        if word.head:
            state.pc = state.fsp - 1
            state.direction = Direction.B
        else:
            state.pc += 1

    def _app_var(self, word: Word) -> None:
        state = self.state
        if state.direction is Direction.B:
            state.pc -= 1
            return
        if type(word.data) is not int or word.data < 0:
            raise InvalidAddress("APP_VAR requires a non-negative variable index")
        redex_address = self.lookup(word.data)
        state.pc += 1
        redex = self._word(redex_address)
        if redex.opcode is MuredOpcode.UBV:
            if type(redex.data) is not int or redex.data < 0:
                raise InvalidAddress("UBV requires a binder depth")
            self._copy_result(
                Word(MuredOpcode.APP_VAR, state.phi - redex.data, False)
            )
            return
        if redex.opcode is MuredOpcode.CLOSURE:
            if type(redex.data) is not int or redex.data < 0:
                raise MalformedClosure("CLOSURE requires an environment address")
            code = self._word(redex_address + 1)
            if code.opcode is not None or type(code.data) is not int or code.data < 0:
                raise MalformedClosure("CLOSURE requires a following code pointer")
            self._push_control(redex.data)
            self._copy_result(Word(MuredOpcode.APP, code.data, False))
            return
        if redex.opcode is MuredOpcode.REC:
            self._rec_fields(redex_address)
            self._copy_result(Word(MuredOpcode.RECP, redex_address, False))
            return
        raise IllegalTransition("APP_VAR encountered malformed redex-store value")

    def _pop_if_branch_paths(
        self,
        false_branch: Word,
        true_branch: Word,
    ) -> tuple[int | None, int | None]:
        true_path = (
            self._pop_control() if true_branch.opcode is MuredOpcode.APP else None
        )
        false_path = (
            self._pop_control() if false_branch.opcode is MuredOpcode.APP else None
        )
        return false_path, true_path

    def _begin_if_reconstruction(
        self,
        false_branch: Word,
        true_branch: Word,
    ) -> None:
        state = self.state
        false_path, true_path = self._pop_if_branch_paths(false_branch, true_branch)
        self._push_control_entry(_SavedQuantum(state.q))
        if false_path is not None:
            self._push_control(false_path)
        if true_path is not None:
            self._push_control(true_path)
        state.q = 0
        state.prim = "__IF_RECONSTRUCT__"
        state.fire = int(false_branch.opcode is MuredOpcode.APP) + int(
            true_branch.opcode is MuredOpcode.APP
        )
        state.pc -= 1

        if state.fire == 0:
            saved_q = self._pop_control_entry()
            if not isinstance(saved_q, _SavedQuantum):
                raise IllegalTransition("IF reconstruction lost saved quantum")
            state.q = saved_q.value
            state.prim = None

    def _select_if_branch(self, condition: str) -> None:
        state = self.state
        false_slot = state.pc - 2
        true_slot = state.pc - 1
        false_branch = self._word(false_slot)
        true_branch = self._word(true_slot)
        false_path, true_path = self._pop_if_branch_paths(false_branch, true_branch)
        if condition == "TRUE":
            selected = true_branch
            selected_path = true_path
        else:
            selected = false_branch
            selected_path = false_path

        state.q -= 1
        if selected.opcode is MuredOpcode.APP:
            if type(selected.data) is not int or selected.data < 0:
                raise InvalidAddress("IF selected APP requires a graph address")
            if selected_path is None:
                raise IllegalTransition("IF selected APP lost its environment path")
            state.fsp = false_slot - 1
            state.argcnt = 0
            state.env = selected_path
            state.pc = selected.data
            state.direction = Direction.F
            return

        state.memory[false_slot] = selected
        state.fsp = false_slot
        state.pc = false_slot

    def _skip_if_branches(self) -> None:
        state = self.state
        false_slot = state.pc - 2
        true_slot = state.pc - 1
        false_branch = self._word(false_slot)
        true_branch = self._word(true_slot)
        self._pop_if_branch_paths(false_branch, true_branch)
        state.pc = false_slot - 1

    def _finish_if_reconstruction(self) -> None:
        saved_q = self._pop_control_entry()
        if not isinstance(saved_q, _SavedQuantum):
            raise IllegalTransition("IF reconstruction lost saved quantum")
        self.state.q = saved_q.value

    def _fire_primitive(self) -> None:
        state = self.state
        primitive = state.prim
        state.prim = None
        state.fire = 0

        if primitive == "__IF_RECONSTRUCT__":
            self._finish_if_reconstruction()
            state.pc -= 1
            return

        if primitive == "IF":
            condition = self._word(state.pc)
            if (
                condition.opcode is MuredOpcode.SYM
                and type(condition.data) is str
                and condition.data in {"TRUE", "FALSE"}
            ):
                if state.q > 0:
                    self._select_if_branch(condition.data)
                else:
                    self._skip_if_branches()
                return
            false_branch = self._word(state.pc - 2)
            true_branch = self._word(state.pc - 1)
            self._begin_if_reconstruction(false_branch, true_branch)
            return

        result: Word | None = None
        if state.q > 0 and primitive is not None:
            if primitive in {
                "1-",
                "1+",
                "MINUS",
                "ABS",
                "FLOOR",
                "CEILING",
                "EVEN?",
                "NULL?",
                "NOT",
                "INTEGER?",
                "FLOAT?",
                "CHAR?",
                "SYMBOL?",
            }:
                result = self._apply_unary_primitive(
                    primitive,
                    self._word(state.pc),
                )
            elif primitive in {
                "+",
                "-",
                "*",
                "/",
                "<",
                ">",
                "<=",
                ">=",
                "=",
                "EXPT",
                "MAX",
                "MIN",
                "MOD",
            }:
                result = self._apply_binary_primitive(
                    primitive,
                    self._word(state.pc + 1),
                    self._word(state.pc),
                )

        if result is not None:
            state.memory[state.pc] = Word(
                result.opcode,
                result.data,
                True,
                result.definition,
            )
            state.fsp = state.pc
            state.q -= 1
        state.pc -= 1

    def _apply_unary_primitive(self, primitive: str, operand: Word) -> Word | None:
        value = self._number_word_value(operand)
        if primitive == "1-":
            if operand.opcode is MuredOpcode.INT and type(operand.data) is int:
                return Word(MuredOpcode.INT, operand.data - 1)
            return None
        if primitive == "1+" and value is not None:
            return self._number_result_word(value + 1)
        if primitive == "MINUS" and value is not None:
            return self._number_result_word(-value)
        if primitive == "ABS" and value is not None:
            return self._number_result_word(abs(value))
        if primitive == "FLOOR" and value is not None:
            return Word(MuredOpcode.INT, floor(value))
        if primitive == "CEILING" and value is not None:
            return Word(MuredOpcode.INT, ceil(value))
        if primitive == "EVEN?":
            if operand.opcode is MuredOpcode.INT and type(operand.data) is int:
                return self._bool_word(operand.data % 2 == 0)
            return None
        if primitive == "NULL?":
            if self._is_indeterminate_strict_value(operand):
                return None
            if self._is_symbol_word(operand) and operand.data == "NIL":
                return self._bool_word(True)
            return self._bool_word(False)
        if primitive == "NOT":
            if operand.opcode is MuredOpcode.SYM and operand.data == "TRUE":
                return self._bool_word(False)
            if operand.opcode is MuredOpcode.SYM and operand.data == "FALSE":
                return self._bool_word(True)
            return None
        if primitive in {"INTEGER?", "FLOAT?", "CHAR?", "SYMBOL?"}:
            if self._is_indeterminate_strict_value(operand):
                return None
            if primitive == "INTEGER?":
                return self._bool_word(operand.opcode is MuredOpcode.INT)
            if primitive == "FLOAT?":
                return self._bool_word(operand.opcode is MuredOpcode.FLOAT)
            if primitive == "CHAR?":
                return self._bool_word(operand.opcode is MuredOpcode.CHAR)
            return self._bool_word(self._is_symbol_word(operand))
        return None

    def _apply_binary_primitive(
        self,
        primitive: str,
        left_word: Word,
        right_word: Word,
    ) -> Word | None:
        if primitive == "=":
            left_constant = self._constant_word_key(left_word)
            right_constant = self._constant_word_key(right_word)
            if left_constant is None or right_constant is None:
                return None
            return self._bool_word(left_constant == right_constant)

        left = self._number_word_value(left_word)
        right = self._number_word_value(right_word)
        if left is None or right is None:
            return None

        both_int = (
            left_word.opcode is MuredOpcode.INT
            and right_word.opcode is MuredOpcode.INT
        )
        if primitive == "+":
            value = left + right
            if both_int:
                return Word(MuredOpcode.INT, int(value))
            return Word(MuredOpcode.FLOAT, float(value))
        if primitive == "-":
            value = left - right
            if both_int:
                return Word(MuredOpcode.INT, int(value))
            return Word(MuredOpcode.FLOAT, float(value))
        if primitive == "*":
            value = left * right
            if both_int:
                return Word(MuredOpcode.INT, int(value))
            return Word(MuredOpcode.FLOAT, float(value))
        if primitive == "/":
            value = left / right
            if both_int and value.is_integer():
                return Word(MuredOpcode.INT, int(value))
            return Word(MuredOpcode.FLOAT, value)
        if primitive == "<":
            return self._bool_word(left < right)
        if primitive == ">":
            return self._bool_word(left > right)
        if primitive == "<=":
            return self._bool_word(left <= right)
        if primitive == ">=":
            return self._bool_word(left >= right)
        if primitive == "MOD":
            if not both_int:
                return None
            return Word(MuredOpcode.INT, int(left) % int(right))
        if primitive == "EXPT":
            value = left**right
            if type(value) is not int and type(value) is not float:
                return None
            return self._number_result_word(value)
        if primitive == "MAX":
            return self._number_result_word(left if left >= right else right)
        if primitive == "MIN":
            return self._number_result_word(left if left <= right else right)
        return None

    @staticmethod
    def _number_word_value(word: Word) -> int | float | None:
        if word.opcode is MuredOpcode.INT and type(word.data) is int:
            return word.data
        if word.opcode is MuredOpcode.FLOAT and type(word.data) is float:
            return word.data
        return None

    @staticmethod
    def _number_result_word(value: int | float) -> Word:
        if type(value) is float:
            if value.is_integer():
                return Word(MuredOpcode.INT, int(value))
            return Word(MuredOpcode.FLOAT, value)
        return Word(MuredOpcode.INT, value)

    @staticmethod
    def _bool_word(value: bool) -> Word:
        return Word(MuredOpcode.SYM, "TRUE" if value else "FALSE")

    @staticmethod
    def _is_symbol_word(word: Word) -> bool:
        return word.opcode in {
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }

    def _is_indeterminate_strict_value(self, word: Word) -> bool:
        if word.opcode in {MuredOpcode.APP_VAR, MuredOpcode.VAR}:
            return True
        if word.opcode is not MuredOpcode.APP:
            return False
        if type(word.data) is not int or word.data < 0:
            raise InvalidAddress("strict argument APP requires a graph address")
        root = self._word(word.data)
        return root.opcode in {
            MuredOpcode.APP,
            MuredOpcode.APP_VAR,
            MuredOpcode.VAR,
        }

    @classmethod
    def _constant_word_key(cls, word: Word) -> tuple[str, int | float | str] | None:
        if word.opcode is MuredOpcode.INT and type(word.data) is int:
            return ("int", word.data)
        if word.opcode is MuredOpcode.FLOAT and type(word.data) is float:
            return ("float", word.data)
        if word.opcode is MuredOpcode.CHAR and type(word.data) is str:
            return ("char", word.data)
        if cls._is_symbol_word(word) and type(word.data) is str:
            return ("symbol", word.data)
        return None

    def _y(self, word: Word) -> None:
        state = self.state
        if state.q == 0 or state.argcnt < 1:
            self._copy_result(word)
            state.pc = state.fsp - 1
            state.direction = Direction.B
            return

        state.q -= 1
        state.pc -= 1
        argument = self._word(state.pc)
        state.memory[state.fsp] = Word(MuredOpcode.APP, state.pc, False)

        if argument.opcode is MuredOpcode.APP:
            if type(argument.data) is not int or argument.data < 0:
                raise InvalidAddress("Y APP argument requires a graph address")
            state.pc = argument.data
            return

        self._push_control(state.env)
        scratch = state.fsp + 1
        if scratch >= state.env:
            raise GraphEnvironmentCollision("graph and environment collide")
        state.memory[scratch] = Word(
            argument.opcode,
            argument.data,
            True,
            argument.definition,
        )
        state.pc = scratch

    def _prim(self, word: Word) -> None:
        if type(word.data) is not str or word.data == "":
            raise IllegalTransition("PRIM requires a non-empty primitive name")
        state = self.state
        if state.direction is Direction.B:
            state.pc -= 1
            return
        if word.opcode is MuredOpcode.PRIM_0:
            if word.head and word.data == "Y":
                self._y(word)
                return
            if (
                word.head
                and word.data == "IF"
                and state.argcnt >= 3
                and state.q > 0
            ):
                state.prim = "IF"
                state.fire = 1
            arity = 0
        elif word.opcode is MuredOpcode.PRIM_1:
            arity = 1
        elif word.opcode is MuredOpcode.PRIM_2:
            arity = 2
        else:
            raise IllegalTransition("_prim requires a primitive opcode")
        if (
            arity > 0
            and word.head
            and state.argcnt >= arity
            and state.q > 0
        ):
            state.prim = word.data
            state.fire = arity
        self._copy_result(word)
        if word.head:
            state.pc = state.fsp - 1
            state.direction = Direction.B
        else:
            state.pc += 1

    def _ubv(self, word: Word) -> None:
        if self.state.direction is not Direction.F:
            raise IllegalTransition("UBV requires forward execution")
        if not isinstance(word.data, int):
            raise InvalidAddress("UBV requires a binder depth")
        self._copy_result(
            Word(MuredOpcode.VAR, self.state.phi - word.data, True)
        )
        self.state.pc = self.state.fsp - 1
        self.state.direction = Direction.B

    def _var(self, word: Word) -> None:
        if self.state.direction is not Direction.F:
            raise IllegalTransition("VAR requires forward execution")
        if not isinstance(word.data, int):
            raise InvalidAddress("VAR requires a De Bruijn index")
        redex_address = self.lookup(word.data)
        redex = self._word(redex_address)
        if redex.opcode is MuredOpcode.REC:
            self._recp(Word(MuredOpcode.RECP, redex_address, word.head))
            return
        self.state.pc = redex_address

    def run(self, *, cycle_limit: int = 100_000) -> MuredMachineState:
        if cycle_limit < 0:
            raise ValueError("cycle_limit must be non-negative")
        while not self.state.halted:
            if self.state.cycles >= cycle_limit:
                raise CycleLimitExceeded(
                    f"μRED cycle limit reached: {cycle_limit}"
                )
            self.step()
        return self.state

    def result_expr(self) -> Expr:
        if not self.state.halted:
            raise MuredMachineError("result is available only after halt")
        expr, _ = self._decompile(self.state.pc, (), frozenset())
        return expr

    @staticmethod
    def _decompile_var_index(index: int, scope: tuple[str | None, ...]) -> int:
        if index < len(scope):
            return sum(name is not None for name in scope[:index])
        return index - sum(name is None for name in scope)

    def _decompile(
        self,
        address: int,
        scope: tuple[str | None, ...],
        path: frozenset[int],
    ) -> tuple[Expr, int]:
        if address in path:
            raise MuredMachineError("cyclic μRED result graph")
        word = self._word(address)

        inline_argument_opcodes = {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }
        if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
            not word.head and word.opcode in inline_argument_opcodes
        ):
            argument_entries: list[tuple[MuredOpcode, int]] = []
            cursor = address
            app_path = path
            while True:
                if cursor in app_path:
                    raise MuredMachineError("cyclic μRED result graph")
                app_word = self._word(cursor)
                if app_word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR}:
                    if not isinstance(app_word.data, int) or app_word.data < 0:
                        raise InvalidAddress("result APP requires an argument address")
                    argument_entries.append((app_word.opcode, app_word.data))
                elif not app_word.head and app_word.opcode in inline_argument_opcodes:
                    argument_entries.append((app_word.opcode, cursor))
                else:
                    break
                app_path = app_path | {cursor}
                cursor += 1
            operator, next_address = self._decompile(cursor, scope, app_path)
            arguments: list[Expr] = []
            for opcode, argument_data in reversed(argument_entries):
                if opcode is MuredOpcode.APP_VAR:
                    name = (
                        scope[argument_data]
                        if argument_data < len(scope)
                        else None
                    )
                    arguments.append(
                        Var(self._decompile_var_index(argument_data, scope), name)
                    )
                    continue
                if opcode is MuredOpcode.APP:
                    argument, next_address = self._decompile(
                        argument_data, scope, app_path
                    )
                    arguments.append(argument)
                    continue
                inline_word = self._word(argument_data)
                if inline_word.opcode is MuredOpcode.INT:
                    if type(inline_word.data) is not int:
                        raise MuredMachineError("result INT requires an integer value")
                    arguments.append(Integer(inline_word.data))
                elif inline_word.opcode is MuredOpcode.FLOAT:
                    if type(inline_word.data) is not float:
                        raise MuredMachineError(
                            "result FLOAT requires a floating-point value"
                        )
                    arguments.append(Float(inline_word.data))
                elif inline_word.opcode is MuredOpcode.CHAR:
                    if type(inline_word.data) is not str or len(inline_word.data) != 1:
                        raise MuredMachineError(
                            "result CHAR requires a single-character string"
                        )
                    arguments.append(Char(inline_word.data))
                elif inline_word.opcode in {
                    MuredOpcode.SYM,
                    MuredOpcode.PRIM_0,
                    MuredOpcode.PRIM_1,
                    MuredOpcode.PRIM_2,
                }:
                    if type(inline_word.data) is not str or inline_word.data == "":
                        raise MuredMachineError("result symbol requires a symbol name")
                    arguments.append(Symbol(inline_word.data))
                else:
                    raise MuredMachineError(
                        f"{inline_word.opcode} is not a valid inline argument"
                    )
            return App((operator, *arguments)), next_address

        if word.opcode is MuredOpcode.RBLOCK:
            blocks: list[Word] = []
            cursor = address
            letrec_path = path
            while True:
                block = self._word(cursor)
                if block.opcode is not MuredOpcode.RBLOCK:
                    break
                if type(block.data) is not int or block.data < 0:
                    raise InvalidAddress("result RBLOCK requires a binding address")
                blocks.append(block)
                letrec_path = letrec_path | {cursor}
                cursor += 1
            rup = self._word(cursor)
            if rup.opcode is not MuredOpcode.RUP or rup.data != len(blocks):
                raise MuredMachineError("result LETREC requires matching RUP")
            letrec_path = letrec_path | {cursor}

            names: list[str] = []
            for block in blocks:
                assert isinstance(block.data, int)
                name_word = self._word(block.data)
                if name_word.opcode is not MuredOpcode.SYM or not isinstance(
                    name_word.data, str
                ):
                    raise MuredMachineError(
                        "result RBLOCK binding requires leading SYM name"
                    )
                names.append(name_word.data)

            recursive_scope: tuple[str | None, ...] = (
                *reversed(names),
                *scope,
            )
            bindings: list[Binding] = []
            next_address = cursor + 1
            for name, block in zip(names, blocks, strict=True):
                assert isinstance(block.data, int)
                binding_expr, binding_next = self._decompile(
                    block.data + 1,
                    recursive_scope,
                    letrec_path,
                )
                next_address = max(next_address, binding_next)
                bindings.append(Binding(name, binding_expr))

            body, body_next = self._decompile(
                cursor + 1,
                recursive_scope,
                letrec_path,
            )
            next_address = max(next_address, body_next)
            return LetRec(tuple(bindings), body), next_address

        if word.opcode is MuredOpcode.STRUCT:
            if type(word.data) is not str or word.data == "":
                raise MuredMachineError("result STRUCT requires a tag name")
            field_entries: list[tuple[MuredOpcode, int]] = []
            cursor = address + 1
            struct_path = path | {address}
            while True:
                if cursor in struct_path:
                    raise MuredMachineError("cyclic μRED result graph")
                field_word = self._word(cursor)
                if field_word.opcode not in {MuredOpcode.APP, MuredOpcode.APP_VAR}:
                    break
                if type(field_word.data) is not int or field_word.data < 0:
                    raise InvalidAddress(
                        "result STRUCT field requires an address or index"
                    )
                field_entries.append((field_word.opcode, field_word.data))
                struct_path = struct_path | {cursor}
                cursor += 1
            selector = self._word(cursor)
            if selector.opcode is not MuredOpcode.VAR or selector.data != 0:
                raise MuredMachineError("result STRUCT requires trailing VAR 0")
            struct_scope: tuple[str | None, ...] = (None, *scope)
            fields: list[Expr] = []
            next_address = cursor + 1
            for opcode, field_data in reversed(field_entries):
                if opcode is MuredOpcode.APP_VAR:
                    name = (
                        struct_scope[field_data]
                        if field_data < len(struct_scope)
                        else None
                    )
                    fields.append(
                        Var(
                            self._decompile_var_index(field_data, struct_scope),
                            name,
                        )
                    )
                    continue
                field, field_next = self._decompile(
                    field_data,
                    struct_scope,
                    struct_path,
                )
                next_address = max(next_address, field_next)
                fields.append(field)
            return StructLit(word.data, tuple(fields)), next_address

        if word.opcode is MuredOpcode.LAMBDA:
            parameters: list[str] = []
            cursor = address
            lambda_path = path
            while True:
                lambda_word = self._word(cursor)
                if lambda_word.opcode is not MuredOpcode.LAMBDA:
                    break
                if not isinstance(lambda_word.data, str):
                    raise MuredMachineError(
                        "result LAMBDA requires a parameter name"
                    )
                parameters.append(lambda_word.data)
                lambda_path = lambda_path | {cursor}
                cursor += 1
            body, next_address = self._decompile(
                cursor,
                (*reversed(parameters), *scope),
                lambda_path,
            )
            return Lambda(tuple(parameters), body), next_address

        if word.opcode is MuredOpcode.INT:
            if type(word.data) is not int:
                raise MuredMachineError("result INT requires an integer value")
            return Integer(word.data), address + 1

        if word.opcode is MuredOpcode.FLOAT:
            if type(word.data) is not float:
                raise MuredMachineError(
                    "result FLOAT requires a floating-point value"
                )
            return Float(word.data), address + 1

        if word.opcode is MuredOpcode.CHAR:
            if type(word.data) is not str or len(word.data) != 1:
                raise MuredMachineError(
                    "result CHAR requires a single-character string"
                )
            return Char(word.data), address + 1

        if word.opcode in {
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }:
            if type(word.data) is not str or word.data == "":
                raise MuredMachineError("result symbol requires a symbol name")
            return Symbol(word.data), address + 1

        if word.opcode is MuredOpcode.VAR:
            if not isinstance(word.data, int) or word.data < 0:
                raise InvalidAddress("result VAR requires a De Bruijn index")
            name = scope[word.data] if word.data < len(scope) else None
            return Var(self._decompile_var_index(word.data, scope), name), address + 1

        raise MuredMachineError(
            f"{word.opcode} is not valid in a μRED result graph"
        )

    def _word(self, address: int) -> Word:
        if not 0 <= address < len(self.state.memory):
            raise InvalidAddress(f"invalid μRED address: {address}")
        word = self.state.memory[address]
        if word is None:
            raise InvalidAddress(f"uninitialized μRED address: {address}")
        return word

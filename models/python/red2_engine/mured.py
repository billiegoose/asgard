from collections.abc import Collection, Mapping, Sequence
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
    EP = auto()
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
        "IO-RETURN",
        "UART-TX",
        "UART-TX-BYTES",
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
_NON_STRICT_PRIMITIVES = frozenset(
    {"IF", "Y", "AND", "OR", "IO-BIND", "IO-THEN", "CLOCK", "UART-RX"}
)


@dataclass(frozen=True, slots=True)
class Word:
    opcode: MuredOpcode | None
    data: int | float | str | None = None
    head: bool = False
    definition: int | None = None
    # RED keeps the CLOSURE class on an environment word after sharing an
    # atomic value over the closure.  The type/opcode becomes the atom, but
    # LOOKUP must still step over the original two-word closure slot.
    closure_slot: bool = False


@dataclass(frozen=True, slots=True)
class MuredHostCall:
    name: str
    argument_address: int | None = None


class MuredStopReason(StrEnum):
    COMPLETE = auto()
    QUANTUM_EXHAUSTED = auto()
    HOST_CALL = auto()


@dataclass(frozen=True, slots=True)
class MuredRunResult:
    reason: MuredStopReason
    host_call: MuredHostCall | None = None


@dataclass(frozen=True, slots=True)
class MuredMemoryEvent:
    cycle: int
    opcode: str | None
    name: str
    data: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class MuredMemorySnapshot:
    graph_words: int
    environment_words: int
    peak_graph_words: int
    peak_environment_words: int
    minimum_gap: int
    frontier_restores: int
    graph_rewinds: int
    host_checkpoints: int


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


def compile_lambda(
    expr: Expr,
    *,
    definition_names: Collection[str] = (),
    unary_primitive_names: Collection[str] = (),
) -> tuple[Word, ...]:
    words: list[Word] = []
    visible_definitions = frozenset(definition_names)
    visible_unary_primitives = _STRICT_UNARY_PRIMITIVES | frozenset(
        unary_primitive_names
    )

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
            elif node.name in visible_definitions:
                words.append(Word(MuredOpcode.SYM, node.name, head))
            elif node.name in visible_unary_primitives:
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
            if not node.items:
                words.append(Word(MuredOpcode.PNP, head=head))
                return
            operator = node.items[0]
            if (
                isinstance(operator, Symbol)
                and operator.name not in visible_definitions
                and operator.name in {"AND", "OR"}
            ):
                arguments = node.items[1:]
                identity = Symbol("TRUE" if operator.name == "AND" else "FALSE")
                short_circuit = Symbol("FALSE" if operator.name == "AND" else "TRUE")
                expanded: Expr = identity
                for argument in reversed(arguments):
                    if operator.name == "AND":
                        expanded = App(
                            (Symbol("IF"), argument, expanded, short_circuit)
                        )
                    else:
                        expanded = App(
                            (Symbol("IF"), argument, short_circuit, expanded)
                        )
                compile_graph(expanded, scope, head=head)
                return
            if len(node.items) == 1:
                compile_graph(node.items[0], scope, head=head)
                return
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


@dataclass(frozen=True, slots=True)
class _SavedDefinitionPath:
    value: int


@dataclass(frozen=True, slots=True)
class _SubgraphFrame:
    env: int
    free_space: int
    prim: str | None
    fire: int


@dataclass(frozen=True, slots=True)
class _EqualityTask:
    left: int
    right: int
    lambdas: int
    descriptor_mode: bool


@dataclass(frozen=True, slots=True)
class _EqualityFrame:
    result_pc: int
    live_fsp: int


_ControlEntry = (
    int
    | _SavedPrim
    | _SavedFire
    | _SavedQuantum
    | _SavedDefinitionPath
    | _SubgraphFrame
    | _EqualityFrame
    | None
)


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
    free_space: int = -1
    argcnt: int = 0
    prim: str | None = None
    fire: int = 0
    s_a: int | None = None
    s_d: int | None = None
    halted: bool = False
    cycles: int = 0

    def __post_init__(self) -> None:
        # Legacy direct construction may omit the physical boundary. Resolve
        # that sentinel once; subsequent logical path changes never allocate.
        if self.free_space == -1:
            self.free_space = self.env
        if type(self.free_space) is not int:
            raise InvalidAddress("free_space requires an integer address")


class MuredMachine:
    def __init__(
        self,
        state: MuredMachineState,
        *,
        struct_selectors: dict[str, tuple[str, int]] | None = None,
        working_memory_limit: int | None = None,
        memory_diagnostics: bool = False,
        poison_reclaimed_environment: bool = False,
    ) -> None:
        self.state = state
        self.struct_selectors = (
            {} if struct_selectors is None else dict(struct_selectors)
        )
        self.working_memory_limit = (
            len(state.memory) if working_memory_limit is None else working_memory_limit
        )
        if not 0 < self.working_memory_limit <= len(state.memory):
            raise ValueError("working memory limit is outside μRED memory")
        self.pending_host_call: MuredHostCall | None = None
        self._saved_quantum_depth = 0
        self._memory_diagnostics_enabled = memory_diagnostics
        self._poison_reclaimed_environment = poison_reclaimed_environment
        self._memory_events: list[MuredMemoryEvent] = []
        self._peak_graph_words = state.fsp + 1
        self._peak_environment_words = self.working_memory_limit - self._frontier()
        self._minimum_gap = self._frontier() - state.fsp
        self._frontier_restores = 0
        self._graph_rewinds = 0
        self._host_checkpoints = 0

    @classmethod
    def load(
        cls,
        problem: Sequence[Word],
        *,
        quantum: int,
        memory_words: int = 256,
        control_words: int = 64,
        memory_diagnostics: bool = False,
        poison_reclaimed_environment: bool = False,
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
                free_space=memory_words,
                c=-1,
                direction=Direction.F,
                q=quantum,
                phi=0,
            ),
            memory_diagnostics=memory_diagnostics,
            poison_reclaimed_environment=poison_reclaimed_environment,
        )

    @classmethod
    def from_expr(
        cls,
        expr: Expr,
        *,
        quantum: int,
        memory_words: int = 256,
        control_words: int = 64,
        memory_diagnostics: bool = False,
        poison_reclaimed_environment: bool = False,
    ) -> MuredMachine:
        return cls.load(
            compile_lambda(expr),
            quantum=quantum,
            memory_words=memory_words,
            control_words=control_words,
            memory_diagnostics=memory_diagnostics,
            poison_reclaimed_environment=poison_reclaimed_environment,
        )

    def enable_memory_diagnostics(self) -> None:
        self._memory_diagnostics_enabled = True
        self._update_memory_snapshot()

    def memory_events(self) -> tuple[MuredMemoryEvent, ...]:
        return tuple(self._memory_events)

    def memory_snapshot(self) -> MuredMemorySnapshot:
        self._update_memory_snapshot()
        frontier = self._frontier()
        return MuredMemorySnapshot(
            graph_words=self.state.fsp + 1,
            environment_words=self.working_memory_limit - frontier,
            peak_graph_words=self._peak_graph_words,
            peak_environment_words=self._peak_environment_words,
            minimum_gap=self._minimum_gap,
            frontier_restores=self._frontier_restores,
            graph_rewinds=self._graph_rewinds,
            host_checkpoints=self._host_checkpoints,
        )

    def _frontier(self) -> int:
        return self.state.free_space

    def _current_opcode_name(self) -> str | None:
        try:
            word = self._word(self.state.pc)
        except MuredMachineError:
            return None
        if word.opcode is None:
            return None
        return str(word.opcode.value)

    def _record_memory_event(
        self,
        name: str,
        data: Mapping[str, object] | None = None,
    ) -> None:
        if not self._memory_diagnostics_enabled:
            return
        self._memory_events.append(
            MuredMemoryEvent(
                cycle=self.state.cycles,
                opcode=self._current_opcode_name(),
                name=name,
                data={} if data is None else dict(data),
            )
        )

    def _update_memory_snapshot(self) -> None:
        frontier = self._frontier()
        graph_words = self.state.fsp + 1
        environment_words = self.working_memory_limit - frontier
        self._peak_graph_words = max(self._peak_graph_words, graph_words)
        self._peak_environment_words = max(
            self._peak_environment_words,
            environment_words,
        )
        self._minimum_gap = min(self._minimum_gap, frontier - self.state.fsp)

    def step(self) -> MuredMachineState:
        state = self.state
        if state.halted or self.pending_host_call is not None:
            return state
        self._validate_state()
        old_fsp = state.fsp
        word = self._word(state.pc)
        match word.opcode:
            case MuredOpcode.APP:
                self._app(word)
            case MuredOpcode.APP_VAR:
                self._app_var(word)
            case MuredOpcode.CLOSURE:
                self._closure(word)
            case MuredOpcode.EP:
                self._ep(word)
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
        if state.fsp < old_fsp:
            self._graph_rewinds += 1
            self._record_memory_event(
                "GRAPH_REWIND",
                {"from": old_fsp, "to": state.fsp},
            )
        self._update_memory_snapshot()
        state.cycles += 1
        return state

    def _validate_state(self) -> None:
        state = self.state
        size = len(state.memory)
        if (
            type(state.free_space) is not int
            or not 0 <= state.fsp < state.free_space <= self.working_memory_limit
        ):
            raise GraphEnvironmentCollision("graph and environment collide")
        if type(state.env) is not int or not 0 <= state.env <= size:
            raise InvalidAddress(f"invalid μRED environment path: {state.env}")
        if not -1 <= state.c < len(state.control_stack):
            raise InvalidAddress(f"invalid μRED control pointer: {state.c}")
        if state.q < 0 or state.phi < 0 or state.argcnt < -1 or state.fire < 0:
            raise IllegalTransition("μRED counters are outside their valid ranges")
        if state.prim is not None and (type(state.prim) is not str or state.prim == ""):
            raise IllegalTransition("prim register requires a symbol name")
        self._word(state.pc)

    def _push_graph(self, word: Word) -> int:
        state = self.state
        address = state.fsp + 1
        frontier = state.free_space
        if address >= frontier:
            raise GraphEnvironmentCollision("graph and environment collide")
        state.memory[address] = word
        state.fsp = address
        return address

    def _copy_result(self, word: Word) -> int:
        address = self._push_graph(word)
        self.state.argcnt += 1
        return address

    def _allocate_environment(self, word: Word) -> int:
        state = self.state
        frontier = state.free_space
        # Reserve the binding and any path bridge before writing either word.
        address = frontier - 1 - (frontier != state.env)
        if address <= state.fsp:
            raise GraphEnvironmentCollision("graph and environment collide")
        if frontier != state.env:
            bridge = frontier - 1
            state.memory[bridge] = Word(MuredOpcode.PNP, state.env, False)
            self._record_memory_event(
                "ENV_ALLOC",
                {"address": bridge, "opcode": "PNP", "words": 1},
            )
        state.memory[address] = word
        state.free_space = address
        state.env = address
        self._record_memory_event(
            "ENV_ALLOC",
            {
                "address": address,
                "opcode": None if word.opcode is None else word.opcode.value,
                "words": 1,
            },
        )
        return address

    def _push_environment_marker(self, parent: int) -> int:
        """Push one faithful RED MARKER/PNP at the physical environment frontier."""
        if type(parent) is not int or parent < 0:
            raise InvalidAddress("PNP requires an environment address")
        state = self.state
        frontier = self._frontier()
        address = frontier - 1
        if address <= state.fsp:
            raise GraphEnvironmentCollision("graph and environment collide")
        state.memory[address] = Word(MuredOpcode.PNP, parent, False)
        state.free_space = address
        state.env = address
        self._record_memory_event(
            "ENV_ALLOC",
            {"address": address, "opcode": "PNP", "words": 1},
        )
        return address

    def _allocate_environment_block(self, words: Sequence[Word]) -> int:
        if not words:
            raise MuredMachineError("environment block must not be empty")
        state = self.state
        frontier = self._frontier()
        # A partial block (or marker alone) must never escape a failed reserve.
        address = frontier - len(words) - (frontier != state.env)
        if address <= state.fsp:
            raise GraphEnvironmentCollision("graph and environment collide")
        if frontier != state.env:
            bridge = frontier - 1
            state.memory[bridge] = Word(MuredOpcode.PNP, state.env, False)
            self._record_memory_event(
                "ENV_ALLOC",
                {"address": bridge, "opcode": "PNP", "words": 1},
            )
        for offset, word in enumerate(words):
            state.memory[address + offset] = word
        state.free_space = address
        state.env = address
        self._record_memory_event(
            "ENV_ALLOC",
            {"address": address, "opcode": "BLOCK", "words": len(words)},
        )
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

    def _push_definition_path(self, address: int) -> None:
        self._push_control_entry(_SavedDefinitionPath(address))

    def _push_saved_quantum(self, quantum: int) -> None:
        self._push_control_entry(_SavedQuantum(quantum))
        self._saved_quantum_depth += 1

    def _pop_saved_quantum(self) -> int:
        saved = self._pop_control_entry()
        if not isinstance(saved, _SavedQuantum):
            raise IllegalTransition("reconstruction lost saved quantum")
        if self._saved_quantum_depth <= 0:
            raise IllegalTransition("saved quantum bookkeeping underflow")
        self._saved_quantum_depth -= 1
        return saved.value

    def _discard_completed_definition_paths(self) -> None:
        while self.state.c >= 0 and isinstance(
            self.state.control_stack[self.state.c], _SavedDefinitionPath
        ):
            self._pop_control_entry()

    def _pop_control(self) -> int:
        value = self._pop_control_entry()
        if isinstance(value, _SavedDefinitionPath):
            return value.value
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
        return state.c >= 0 and isinstance(state.control_stack[state.c], _SavedFire)

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

    def _enter_subgraph(self, parent_env: int, child_pc: int, parent_pc: int) -> None:
        state = self.state
        if type(parent_env) is not int or not 0 <= parent_env <= len(state.memory):
            raise InvalidAddress("subgraph parent environment requires an address")

        # C returns with env == saved fs.  RED2 can arrive with a logical parent
        # path that is not the physical frontier, so make that relationship
        # explicit before the child region begins.  Preflight the marker, JOIN,
        # and control frame together so a failed entry cannot leave a partial
        # normalization behind.
        frontier = self._frontier()
        normalized_env = parent_env
        needs_bridge = parent_env != frontier
        if needs_bridge:
            normalized_env = frontier - 1
        join_address = state.fsp + 1
        if normalized_env <= state.fsp or join_address >= normalized_env:
            raise GraphEnvironmentCollision("graph and environment collide")
        if state.c + 1 >= len(state.control_stack):
            raise ControlStackOverflow("μRED control stack overflow")

        if needs_bridge:
            state.memory[normalized_env] = Word(MuredOpcode.PNP, parent_env, False)
            state.free_space = normalized_env
            state.env = normalized_env
            self._record_memory_event(
                "ENV_ALLOC",
                {"address": normalized_env, "opcode": "PNP", "words": 1},
            )
        else:
            state.env = normalized_env

        frame = _SubgraphFrame(
            env=normalized_env,
            free_space=normalized_env,
            prim=state.prim,
            fire=state.fire,
        )
        self._push_control_entry(frame)
        self._record_memory_event(
            "SUBGRAPH_ENTER",
            {
                "parent_pc": parent_pc,
                "child_pc": child_pc,
                "parent_env": parent_env,
                "env": frame.env,
                "free_space": frame.free_space,
                "prim": "" if frame.prim is None else frame.prim,
                "fire": frame.fire,
            },
        )
        state.prim = None
        state.fire = 0
        self._push_subgraph_join(frame, parent_pc)
        state.argcnt = 0
        state.pc = child_pc
        state.direction = Direction.F

    def _push_subgraph_join(self, frame: _SubgraphFrame, parent_pc: int) -> int:
        """Emit a machine-generated JOIN only while its typed frame is live."""
        state = self.state
        if state.c < 0 or state.control_stack[state.c] is not frame:
            raise IllegalTransition(
                "machine-generated JOIN requires its typed subgraph frame"
            )
        return self._push_graph(
            Word(
                MuredOpcode.JOIN,
                parent_pc,
                False,
                1 if frame.fire > 0 else None,
            )
        )

    def _pop_subgraph_frame(self, saved_primitive: bool) -> _SubgraphFrame | None:
        if self.state.c < 0:
            return None
        entry = self.state.control_stack[self.state.c]
        if isinstance(entry, _SubgraphFrame):
            self._pop_control_entry()
            return entry
        return None

    def _environment_address_in_interval(
        self,
        address: int,
        start: int,
        stop: int,
    ) -> bool:
        return start <= address < stop

    def _word_references_environment_interval(
        self,
        word: Word,
        start: int,
        stop: int,
    ) -> bool:
        if word.opcode in {MuredOpcode.EP, MuredOpcode.RECP} and type(word.data) is int:
            return self._environment_address_in_interval(word.data, start, stop)
        if word.opcode is MuredOpcode.CLOSURE and type(word.data) is int:
            return self._environment_address_in_interval(word.data, start, stop)
        return False

    def _graph_references_environment_interval(
        self,
        address: int,
        start: int,
        stop: int,
    ) -> bool:
        inline_argument_opcodes = {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }
        visited: set[int] = set()
        stack = [address]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            if not 0 <= current <= self.state.fsp:
                continue
            word = self._word(current)
            if self._word_references_environment_interval(word, start, stop):
                return True
            if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                not word.head and word.opcode in inline_argument_opcodes
            ):
                cursor = current
                while cursor <= self.state.fsp:
                    entry = self._word(cursor)
                    if self._word_references_environment_interval(entry, start, stop):
                        return True
                    if entry.opcode is MuredOpcode.APP and type(entry.data) is int:
                        stack.append(entry.data)
                    if entry.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                        not entry.head and entry.opcode in inline_argument_opcodes
                    ):
                        cursor += 1
                        continue
                    stack.append(cursor)
                    break
                continue
            if word.opcode is MuredOpcode.RBLOCK:
                cursor = current
                binding_count = 0
                while cursor <= self.state.fsp:
                    block = self._word(cursor)
                    if block.opcode is not MuredOpcode.RBLOCK:
                        break
                    if self._word_references_environment_interval(block, start, stop):
                        return True
                    if (
                        type(block.data) is not int
                        or block.data < 0
                        or block.data + 1 > self.state.fsp
                    ):
                        return True
                    stack.append(block.data + 1)
                    binding_count += 1
                    cursor += 1
                if cursor > self.state.fsp:
                    return True
                rup = self._word(cursor)
                if rup.opcode is not MuredOpcode.RUP or rup.data != binding_count:
                    return True
                if cursor + 1 > self.state.fsp:
                    return True
                stack.append(cursor + 1)
                continue
            if word.opcode is MuredOpcode.STRUCT:
                cursor = current + 1
                while cursor <= self.state.fsp:
                    descriptor = self._word(cursor)
                    if self._word_references_environment_interval(
                        descriptor, start, stop
                    ):
                        return True
                    if (
                        descriptor.opcode is MuredOpcode.APP
                        and type(descriptor.data) is int
                    ):
                        stack.append(descriptor.data)
                    if descriptor.opcode is MuredOpcode.VAR and descriptor.data == 0:
                        break
                    cursor += 1
                continue
            if word.opcode is MuredOpcode.LAMBDA:
                cursor = current
                while cursor <= self.state.fsp:
                    lambda_word = self._word(cursor)
                    if lambda_word.opcode is not MuredOpcode.LAMBDA:
                        stack.append(cursor)
                        break
                    if self._word_references_environment_interval(
                        lambda_word, start, stop
                    ):
                        return True
                    cursor += 1
        return False

    def _lookup_from_environment(self, environment: int, index: int) -> int:
        """Resolve one lexical slot without changing the live machine registers."""
        if type(environment) is not int or environment < 0:
            raise InvalidAddress("environment lookup requires an address")
        if type(index) is not int or index < 0:
            raise InvalidAddress("environment lookup requires a non-negative index")
        address = environment
        remaining = index
        seen: set[int] = set()
        while True:
            if address in seen:
                raise IllegalTransition("cyclic environment path during publication")
            seen.add(address)
            word = self._word(address)
            if word.opcode is MuredOpcode.PNP:
                if type(word.data) is not int or word.data < 0:
                    raise InvalidAddress("PNP requires an environment address")
                address = word.data
                continue
            if remaining == 0:
                return address
            remaining -= 1
            if word.opcode is MuredOpcode.REC:
                address += 3
            elif word.opcode is MuredOpcode.CLOSURE or word.closure_slot:
                address += 2
            else:
                address += 1

    def _materialize_closure_graph(self, closure_address: int) -> tuple[Word, ...]:
        """Publish closure code as graph-owned words, resolving captured values."""
        closure = self._word(closure_address)
        if closure.opcode is not MuredOpcode.CLOSURE or type(closure.data) is not int:
            raise MalformedClosure("publication requires an unshared CLOSURE")
        code = self._word(closure_address + 1)
        if code.opcode is not None or type(code.data) is not int or code.data < 0:
            raise MalformedClosure("CLOSURE requires a following code pointer")
        captured_environment = closure.data
        output: list[Word | None] = []
        visiting: set[tuple[int, int, int, bool]] = set()
        inline_argument_opcodes = {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }

        def emit_environment_value(
            environment_address: int,
            *,
            head: bool,
            bound_depth: int,
        ) -> None:
            seen: set[int] = set()
            target_address = environment_address
            while True:
                if target_address in seen:
                    raise IllegalTransition(
                        "cyclic EP environment chain during publication"
                    )
                seen.add(target_address)
                target = self._word(target_address)
                if target.opcode is not MuredOpcode.EP:
                    break
                if type(target.data) is not int or target.data < 0:
                    raise InvalidAddress("EP requires an environment address")
                target_address = target.data
            if self._is_shareable_ep_value(target):
                output.append(Word(target.opcode, target.data, head, target.definition))
                return
            if target.opcode is MuredOpcode.CLOSURE:
                nested = self._materialize_closure_graph(target_address)
                base = len(output)
                output.extend(
                    self._relocate_problem_word(word, base) for word in nested
                )
                if output[base] is None:
                    raise MuredMachineError("published closure graph contains a hole")
                first = output[base]
                assert first is not None
                output[base] = Word(
                    first.opcode,
                    first.data,
                    head,
                    first.definition,
                    first.closure_slot,
                )
                return
            if target.opcode is MuredOpcode.UBV:
                raise IllegalTransition(
                    "captured UBV publication requires explicit scope relocation"
                )
            if target.opcode is MuredOpcode.REC:
                raise IllegalTransition(
                    "captured REC publication requires recursive residual handling"
                )
            raise IllegalTransition(
                f"cannot publish captured environment value {target.opcode}"
            )

        def emit_graph(
            address: int,
            environment: int,
            bound_depth: int,
            *,
            head: bool,
        ) -> None:
            key = (address, environment, bound_depth, head)
            if key in visiting:
                raise MuredMachineError("cyclic μRED graph during publication")
            visiting.add(key)
            try:
                word = self._word(address)
                if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                    not word.head and word.opcode in inline_argument_opcodes
                ):
                    entries: list[tuple[MuredOpcode, int, int, int | None]] = []
                    cursor = address
                    while True:
                        entry = self._word(cursor)
                        if entry.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR}:
                            if type(entry.data) is not int or entry.data < 0:
                                raise InvalidAddress(
                                    "published application requires an address/index"
                                )
                            entries.append(
                                (entry.opcode, entry.data, cursor, entry.definition)
                            )
                        elif not entry.head and entry.opcode in inline_argument_opcodes:
                            entries.append(
                                (entry.opcode, cursor, cursor, entry.definition)
                            )
                        else:
                            break
                        cursor += 1

                    slots = len(output)
                    output.extend([None] * len(entries))
                    emit_graph(cursor, environment, bound_depth, head=True)
                    for offset, (
                        opcode,
                        data,
                        source,
                        definition,
                    ) in enumerate(entries):
                        slot = slots + offset
                        if opcode is MuredOpcode.APP_VAR:
                            if data < bound_depth:
                                output[slot] = Word(
                                    MuredOpcode.APP_VAR, data, False, definition
                                )
                                continue
                            target_address = self._lookup_from_environment(
                                environment, data - bound_depth
                            )
                            target = self._word(target_address)
                            if self._is_shareable_ep_value(target):
                                output[slot] = Word(
                                    target.opcode,
                                    target.data,
                                    False,
                                    target.definition,
                                )
                                continue
                            output_target = len(output)
                            output[slot] = Word(
                                MuredOpcode.APP, output_target, False, definition
                            )
                            emit_environment_value(
                                target_address,
                                head=True,
                                bound_depth=bound_depth,
                            )
                            continue
                        if opcode is MuredOpcode.APP:
                            output_target = len(output)
                            output[slot] = Word(
                                MuredOpcode.APP, output_target, False, definition
                            )
                            emit_graph(data, environment, bound_depth, head=True)
                            continue
                        inline = self._word(source)
                        output[slot] = Word(
                            inline.opcode,
                            inline.data,
                            False,
                            inline.definition,
                            inline.closure_slot,
                        )
                    return

                if word.opcode is MuredOpcode.LAMBDA:
                    cursor = address
                    lambdas: list[Word] = []
                    while self._word(cursor).opcode is MuredOpcode.LAMBDA:
                        lambda_word = self._word(cursor)
                        lambdas.append(lambda_word)
                        output.append(
                            Word(
                                MuredOpcode.LAMBDA,
                                lambda_word.data,
                                False,
                                lambda_word.definition,
                            )
                        )
                        cursor += 1
                    emit_graph(
                        cursor,
                        environment,
                        bound_depth + len(lambdas),
                        head=head,
                    )
                    return

                if word.opcode is MuredOpcode.VAR:
                    if type(word.data) is not int or word.data < 0:
                        raise InvalidAddress("published VAR requires a De Bruijn index")
                    if word.data < bound_depth:
                        output.append(
                            Word(MuredOpcode.VAR, word.data, head, word.definition)
                        )
                        return
                    target_address = self._lookup_from_environment(
                        environment, word.data - bound_depth
                    )
                    emit_environment_value(
                        target_address,
                        head=head,
                        bound_depth=bound_depth,
                    )
                    return

                if word.opcode is MuredOpcode.EP:
                    if type(word.data) is not int or word.data < 0:
                        raise InvalidAddress(
                            "published EP requires an environment address"
                        )
                    emit_environment_value(
                        word.data,
                        head=head,
                        bound_depth=bound_depth,
                    )
                    return

                if word.opcode in inline_argument_opcodes:
                    output.append(Word(word.opcode, word.data, head, word.definition))
                    return

                raise IllegalTransition(
                    f"cannot materialize closure result opcode {word.opcode}"
                )
            finally:
                visiting.remove(key)

        emit_graph(code.data, captured_environment, 0, head=True)
        if not output or any(word is None for word in output):
            raise MuredMachineError("published closure graph contains a hole")
        return tuple(word for word in output if word is not None)

    def _publish_child_result(
        self,
        frame: _SubgraphFrame,
        result_address: int,
    ) -> int:
        """Eliminate result references into the child environment before return."""
        state = self.state
        current_frontier = self._frontier()
        if type(frame.free_space) is not int or not (
            0 <= current_frontier <= frame.free_space <= self.working_memory_limit
        ):
            raise IllegalTransition("malformed subgraph publication boundary")
        if not 0 <= result_address <= state.fsp:
            raise InvalidAddress("child result is outside the live graph")

        interval_start = current_frontier
        interval_stop = frame.free_space
        published_roots: dict[int, int] = {}
        published_closures: dict[int, int] = {}
        published_recursive: dict[int, int] = {}
        visiting: set[int] = set()
        inline_argument_opcodes = {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }

        def chase_environment_value(address: int) -> tuple[int, Word]:
            seen: set[int] = set()
            target_address = address
            while True:
                if target_address in seen:
                    raise IllegalTransition(
                        "cyclic EP environment chain during publication"
                    )
                seen.add(target_address)
                target = self._word(target_address)
                if target.opcode is not MuredOpcode.EP:
                    return target_address, target
                if type(target.data) is not int or target.data < 0:
                    raise InvalidAddress("published EP requires an environment address")
                target_address = target.data

        def publish_closure(closure_address: int) -> int:
            existing = published_closures.get(closure_address)
            if existing is not None:
                return existing
            words = self._materialize_closure_graph(closure_address)
            destination = state.fsp + 1
            self._write_problem(destination, words)
            published_closures[closure_address] = destination
            published_roots[destination] = destination
            return destination

        def publish_recursive_residual(rec_address: int) -> int:
            existing = published_recursive.get(rec_address)
            if existing is not None:
                return existing
            _binding_address, context, block_address = self._rec_fields(rec_address)

            source_blocks: list[Word] = []
            cursor = block_address
            while self._word(cursor).opcode is MuredOpcode.RBLOCK:
                block = self._word(cursor)
                if type(block.data) is not int or block.data < 0:
                    raise InvalidAddress(
                        "REC residual RBLOCK requires a binding address"
                    )
                source_blocks.append(block)
                cursor += 1
            count = len(source_blocks)
            if count == 0:
                raise IllegalTransition("REC residual requires at least one RBLOCK")
            rup = self._word(cursor)
            if rup.opcode is not MuredOpcode.RUP or rup.data != count:
                raise IllegalTransition(
                    "REC residual requires matching RUP binding count"
                )

            selected_delta = rec_address - context
            if selected_delta < 0 or selected_delta % 3 != 0:
                raise InvalidAddress("REC residual is outside its recursive context")
            selected_index = selected_delta // 3
            if selected_index >= count:
                raise InvalidAddress("REC residual binding index is outside BLOCK")

            # Hilton RECONSTRUCT copies only the RBLOCK descriptors.  The binding
            # graphs remain graph-owned and are traversed in a replacement lexical
            # context where this REC block is represented by ordinary variables.
            # Publication makes that replacement explicit in any already-forced EPs
            # so the copied residual no longer depends on the dying environment.
            rewriting: set[tuple[int, int]] = set()

            def recursive_index(target_address: int) -> int | None:
                target = self._word(target_address)
                if target.opcode is not MuredOpcode.REC:
                    return None
                _binding, target_context, target_block = self._rec_fields(
                    target_address
                )
                if target_context != context or target_block != block_address:
                    return None
                delta = target_address - context
                if delta < 0 or delta % 3 != 0:
                    raise InvalidAddress("REC is outside its recursive context")
                index = delta // 3
                if index >= count:
                    raise InvalidAddress("REC binding index is outside BLOCK")
                return index

            def rewrite_recursive_references(address: int, bound_depth: int) -> None:
                key = (address, bound_depth)
                if key in rewriting:
                    return
                rewriting.add(key)
                try:
                    word = self._word(address)
                    if word.opcode is MuredOpcode.EP:
                        if type(word.data) is not int or word.data < 0:
                            raise InvalidAddress(
                                "published EP requires an environment address"
                            )
                        target_address, _target = chase_environment_value(word.data)
                        index = recursive_index(target_address)
                        if index is not None:
                            opcode = (
                                MuredOpcode.VAR if word.head else MuredOpcode.APP_VAR
                            )
                            state.memory[address] = Word(
                                opcode,
                                index + bound_depth,
                                word.head,
                                word.definition,
                            )
                        return

                    if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                        not word.head and word.opcode in inline_argument_opcodes
                    ):
                        cursor2 = address
                        while True:
                            entry = self._word(cursor2)
                            if entry.opcode is MuredOpcode.APP:
                                if type(entry.data) is not int or entry.data < 0:
                                    raise InvalidAddress(
                                        "published APP requires a graph address"
                                    )
                                rewrite_recursive_references(entry.data, bound_depth)
                            elif entry.opcode is MuredOpcode.EP and not entry.head:
                                rewrite_recursive_references(cursor2, bound_depth)
                            elif entry.opcode is MuredOpcode.APP_VAR or (
                                not entry.head
                                and entry.opcode in inline_argument_opcodes
                            ):
                                pass
                            else:
                                rewrite_recursive_references(cursor2, bound_depth)
                                break
                            cursor2 += 1
                        return

                    if word.opcode is MuredOpcode.RBLOCK:
                        cursor2 = address
                        nested_blocks: list[Word] = []
                        while self._word(cursor2).opcode is MuredOpcode.RBLOCK:
                            nested = self._word(cursor2)
                            if type(nested.data) is not int or nested.data < 0:
                                raise InvalidAddress(
                                    "published RBLOCK requires a binding address"
                                )
                            nested_blocks.append(nested)
                            cursor2 += 1
                        nested_rup = self._word(cursor2)
                        if (
                            nested_rup.opcode is not MuredOpcode.RUP
                            or nested_rup.data != len(nested_blocks)
                        ):
                            raise MuredMachineError(
                                "published LETREC requires matching RUP"
                            )
                        nested_depth = bound_depth + len(nested_blocks)
                        for nested in nested_blocks:
                            assert type(nested.data) is int
                            rewrite_recursive_references(nested.data + 1, nested_depth)
                        rewrite_recursive_references(cursor2 + 1, nested_depth)
                        return

                    if word.opcode is MuredOpcode.STRUCT:
                        cursor2 = address + 1
                        while True:
                            descriptor = self._word(cursor2)
                            if descriptor.opcode is MuredOpcode.APP:
                                if (
                                    type(descriptor.data) is not int
                                    or descriptor.data < 0
                                ):
                                    raise InvalidAddress(
                                        "published STRUCT APP requires an address"
                                    )
                                rewrite_recursive_references(
                                    descriptor.data, bound_depth + 1
                                )
                            elif descriptor.opcode is MuredOpcode.EP:
                                rewrite_recursive_references(cursor2, bound_depth + 1)
                            elif descriptor.opcode is MuredOpcode.APP_VAR or (
                                not descriptor.head
                                and descriptor.opcode in inline_argument_opcodes
                            ):
                                pass
                            else:
                                if (
                                    descriptor.opcode is not MuredOpcode.VAR
                                    or descriptor.data != 0
                                ):
                                    raise MuredMachineError(
                                        "published STRUCT requires trailing VAR 0"
                                    )
                                break
                            cursor2 += 1
                        return

                    if word.opcode is MuredOpcode.LAMBDA:
                        cursor2 = address
                        depth = bound_depth
                        while self._word(cursor2).opcode is MuredOpcode.LAMBDA:
                            depth += 1
                            cursor2 += 1
                        rewrite_recursive_references(cursor2, depth)
                finally:
                    rewriting.remove(key)

            for block in source_blocks:
                assert type(block.data) is int
                name = self._word(block.data)
                if name.opcode is not MuredOpcode.SYM or type(name.data) is not str:
                    raise MuredMachineError(
                        "REC residual RBLOCK binding requires leading SYM name"
                    )
                rewrite_recursive_references(block.data + 1, 0)
                binding = publish_graph(block.data + 1)
                if binding != block.data + 1:
                    raise IllegalTransition(
                        "published recursive binding root cannot move"
                    )

            destination = state.fsp + 1
            words = [
                Word(MuredOpcode.RBLOCK, block.data, False, block.definition)
                for block in source_blocks
            ]
            words.extend(
                [
                    Word(MuredOpcode.RUP, count, False),
                    Word(MuredOpcode.VAR, selected_index, True),
                ]
            )
            last_address = destination + len(words) - 1
            if last_address >= self._frontier():
                raise GraphEnvironmentCollision("graph and environment collide")
            state.memory[destination : last_address + 1] = words
            state.fsp = last_address
            published_recursive[rec_address] = destination
            published_roots[destination] = destination
            return destination

        def publish_ep(address: int, *, embedded: bool) -> int:
            descriptor = self._word(address)
            if descriptor.opcode is not MuredOpcode.EP:
                raise IllegalTransition("publication EP helper requires EP")
            if type(descriptor.data) is not int or descriptor.data < 0:
                raise InvalidAddress("published EP requires an environment address")
            target_address, target = chase_environment_value(descriptor.data)
            if not self._environment_address_in_interval(
                target_address,
                interval_start,
                interval_stop,
            ):
                return address
            if self._is_shareable_ep_value(target):
                state.memory[address] = Word(
                    target.opcode,
                    target.data,
                    descriptor.head,
                    target.definition,
                )
                return address
            if target.opcode is MuredOpcode.UBV:
                if type(target.data) is not int:
                    raise InvalidAddress("UBV requires a binder depth")
                index = state.phi - target.data
                if index < 0:
                    raise IllegalTransition(
                        "published UBV is outside the current lexical scope"
                    )
                opcode = MuredOpcode.APP_VAR if embedded else MuredOpcode.VAR
                state.memory[address] = Word(
                    opcode,
                    index,
                    descriptor.head,
                    descriptor.definition,
                )
                return address
            if target.opcode is MuredOpcode.CLOSURE:
                return publish_closure(target_address)
            if target.opcode is MuredOpcode.REC:
                return publish_recursive_residual(target_address)
            raise IllegalTransition(
                f"child result publication cannot retain {target.opcode}"
            )

        def publish_embedded_descriptor(address: int) -> None:
            descriptor = self._word(address)
            if descriptor.opcode is MuredOpcode.EP:
                published = publish_ep(address, embedded=True)
                if published != address:
                    state.memory[address] = Word(
                        MuredOpcode.APP,
                        published,
                        descriptor.head,
                        descriptor.definition,
                    )
                return
            if descriptor.opcode is MuredOpcode.APP:
                if type(descriptor.data) is not int or descriptor.data < 0:
                    raise InvalidAddress("published APP requires a graph address")
                published = publish_graph(descriptor.data)
                if published != descriptor.data:
                    state.memory[address] = Word(
                        MuredOpcode.APP,
                        published,
                        descriptor.head,
                        descriptor.definition,
                    )

        def publish_graph(address: int) -> int:
            existing = published_roots.get(address)
            if existing is not None:
                return existing
            if address in visiting:
                raise MuredMachineError("cyclic μRED graph during publication")
            visiting.add(address)
            try:
                word = self._word(address)
                if word.opcode is MuredOpcode.EP:
                    published = publish_ep(address, embedded=False)
                    published_roots[address] = published
                    return published

                if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                    not word.head and word.opcode in inline_argument_opcodes
                ):
                    cursor = address
                    while True:
                        entry = self._word(cursor)
                        if entry.opcode is MuredOpcode.APP:
                            publish_embedded_descriptor(cursor)
                        elif entry.opcode is MuredOpcode.APP_VAR or (
                            not entry.head and entry.opcode in inline_argument_opcodes
                        ):
                            pass
                        else:
                            break
                        cursor += 1
                    operator = publish_graph(cursor)
                    if operator != cursor:
                        raise IllegalTransition(
                            "published application operator cannot move"
                        )
                    published_roots[address] = address
                    return address

                if word.opcode is MuredOpcode.RBLOCK:
                    cursor = address
                    blocks: list[int] = []
                    while self._word(cursor).opcode is MuredOpcode.RBLOCK:
                        block = self._word(cursor)
                        if type(block.data) is not int or block.data < 0:
                            raise InvalidAddress(
                                "published RBLOCK requires a binding address"
                            )
                        blocks.append(cursor)
                        binding = publish_graph(block.data + 1)
                        if binding != block.data + 1:
                            raise IllegalTransition(
                                "published LETREC binding root cannot move"
                            )
                        cursor += 1
                    rup = self._word(cursor)
                    if rup.opcode is not MuredOpcode.RUP or rup.data != len(blocks):
                        raise MuredMachineError(
                            "published LETREC requires matching RUP"
                        )
                    body = publish_graph(cursor + 1)
                    if body != cursor + 1:
                        raise IllegalTransition(
                            "published LETREC body root cannot move"
                        )
                    published_roots[address] = address
                    return address

                if word.opcode is MuredOpcode.STRUCT:
                    cursor = address + 1
                    while True:
                        descriptor = self._word(cursor)
                        if descriptor.opcode in {
                            MuredOpcode.APP,
                            MuredOpcode.EP,
                        }:
                            publish_embedded_descriptor(cursor)
                        elif descriptor.opcode is MuredOpcode.APP_VAR or (
                            not descriptor.head
                            and descriptor.opcode in inline_argument_opcodes
                        ):
                            pass
                        else:
                            break
                        cursor += 1
                    selector = self._word(cursor)
                    if selector.opcode is not MuredOpcode.VAR or selector.data != 0:
                        raise MuredMachineError(
                            "published STRUCT requires trailing VAR 0"
                        )
                    published_roots[address] = address
                    return address

                if word.opcode is MuredOpcode.LAMBDA:
                    cursor = address
                    while self._word(cursor).opcode is MuredOpcode.LAMBDA:
                        cursor += 1
                    body = publish_graph(cursor)
                    if body != cursor:
                        raise IllegalTransition(
                            "published lambda body root cannot move"
                        )
                    published_roots[address] = address
                    return address

                published_roots[address] = address
                return address
            finally:
                visiting.remove(address)

        return publish_graph(result_address)

    def _audit_typed_subgraph_return_roots(
        self,
        frame: _SubgraphFrame,
        result_address: int,
        parent_address: int,
    ) -> None:
        """Diagnose reachable references into a child region before reuse."""
        if not self._memory_diagnostics_enabled:
            return
        self._validate_typed_subgraph_return(frame)
        state = self.state
        start = self._frontier()
        stop = frame.free_space
        graph_seen: set[int] = set()
        environment_seen: set[int] = set()
        inline_argument_opcodes = {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }

        def dangling(kind: str, address: int) -> None:
            raise IllegalTransition(
                f"live {kind} references reclaimed environment address {address}"
            )

        def require_address(kind: str, value: object) -> int:
            if type(value) is not int or value < 0:
                raise InvalidAddress(f"{kind} requires an address")
            return value

        def visit_definition(word: Word) -> None:
            if word.definition is not None:
                visit_graph(require_address("definition", word.definition))

        def visit_environment(address: int) -> None:
            if start <= address < stop:
                dangling("environment root", address)
            if address >= self.working_memory_limit:
                return
            if address < 0:
                raise InvalidAddress("environment root requires an address")
            cursor = address
            while cursor < self.working_memory_limit:
                if start <= cursor < stop:
                    dangling("environment path", cursor)
                if cursor in environment_seen:
                    return
                environment_seen.add(cursor)
                word = self._word(cursor)
                visit_definition(word)
                if word.opcode is MuredOpcode.PNP:
                    visit_environment(require_address("PNP", word.data))
                    return
                if word.opcode is MuredOpcode.EP:
                    visit_environment(require_address("EP", word.data))
                elif word.opcode is MuredOpcode.RECP:
                    visit_environment(require_address("RECP", word.data))
                if word.opcode is MuredOpcode.REC:
                    visit_graph(require_address("REC binding", word.data))
                    context = self._word(cursor + 1)
                    block = self._word(cursor + 2)
                    visit_environment(require_address("REC context", context.data))
                    visit_graph(require_address("REC block", block.data))
                    environment_seen.update({cursor + 1, cursor + 2})
                    cursor += 3
                    continue
                if word.opcode is MuredOpcode.CLOSURE or word.closure_slot:
                    if word.opcode is MuredOpcode.CLOSURE:
                        visit_environment(require_address("CLOSURE", word.data))
                    payload = self._word(cursor + 1)
                    if payload.opcode is not None:
                        raise MalformedClosure(
                            "CLOSURE requires an untagged following code pointer"
                        )
                    visit_graph(require_address("CLOSURE code", payload.data))
                    environment_seen.add(cursor + 1)
                    cursor += 2
                    continue
                cursor += 1

        def visit_graph(address: int) -> None:
            if start <= address < stop:
                dangling("graph root", address)
            if not 0 <= address < len(state.memory):
                raise InvalidAddress("graph root requires an address")
            if address in graph_seen:
                return
            graph_seen.add(address)
            word = self._word(address)
            visit_definition(word)
            if word.opcode is MuredOpcode.EP:
                visit_environment(require_address("EP", word.data))
                return
            if word.opcode is MuredOpcode.RECP:
                visit_environment(require_address("RECP", word.data))
                return
            if word.opcode is MuredOpcode.CLOSURE:
                visit_environment(require_address("CLOSURE", word.data))
                payload = self._word(address + 1)
                if payload.opcode is not None:
                    raise MalformedClosure(
                        "CLOSURE requires an untagged following code pointer"
                    )
                visit_graph(require_address("CLOSURE code", payload.data))
                return
            if word.opcode is MuredOpcode.PNP:
                visit_environment(require_address("PNP", word.data))
                return
            if word.opcode is MuredOpcode.REC:
                visit_graph(require_address("REC binding", word.data))
                context = self._word(address + 1)
                block = self._word(address + 2)
                visit_environment(require_address("REC context", context.data))
                visit_graph(require_address("REC block", block.data))
                return
            if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                not word.head and word.opcode in inline_argument_opcodes
            ):
                cursor = address
                while cursor < len(state.memory):
                    entry = self._word(cursor)
                    visit_definition(entry)
                    if entry.opcode is MuredOpcode.APP:
                        visit_graph(require_address("APP", entry.data))
                    elif entry.opcode is MuredOpcode.EP:
                        visit_environment(require_address("EP", entry.data))
                    if entry.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                        not entry.head
                        and entry.opcode in inline_argument_opcodes | {MuredOpcode.EP}
                    ):
                        cursor += 1
                        continue
                    if entry.opcode is not MuredOpcode.JOIN:
                        visit_graph(cursor)
                    return
                raise InvalidAddress("application graph has no operator")
            if word.opcode is MuredOpcode.RBLOCK:
                cursor = address
                count = 0
                while self._word(cursor).opcode is MuredOpcode.RBLOCK:
                    block = self._word(cursor)
                    visit_definition(block)
                    binding = require_address("RBLOCK", block.data)
                    visit_graph(binding + 1)
                    count += 1
                    cursor += 1
                rup = self._word(cursor)
                if rup.opcode is not MuredOpcode.RUP or rup.data != count:
                    raise MuredMachineError("audit LETREC requires matching RUP")
                visit_graph(cursor + 1)
                return
            if word.opcode is MuredOpcode.STRUCT:
                cursor = address + 1
                while cursor < len(state.memory):
                    descriptor = self._word(cursor)
                    visit_definition(descriptor)
                    if descriptor.opcode is MuredOpcode.APP:
                        visit_graph(require_address("STRUCT APP", descriptor.data))
                    elif descriptor.opcode is MuredOpcode.EP:
                        visit_environment(require_address("STRUCT EP", descriptor.data))
                    if descriptor.opcode in {
                        MuredOpcode.APP,
                        MuredOpcode.APP_VAR,
                        MuredOpcode.EP,
                    } or (
                        not descriptor.head
                        and descriptor.opcode in inline_argument_opcodes
                    ):
                        cursor += 1
                        continue
                    if descriptor.opcode is not MuredOpcode.VAR or descriptor.data != 0:
                        raise MuredMachineError("audit STRUCT requires trailing VAR 0")
                    return
                raise InvalidAddress("STRUCT graph has no selector")
            if word.opcode is MuredOpcode.LAMBDA:
                cursor = address
                while self._word(cursor).opcode is MuredOpcode.LAMBDA:
                    visit_definition(self._word(cursor))
                    cursor += 1
                visit_graph(cursor)

        visit_graph(result_address)
        visit_graph(parent_address)
        for index in range(state.c + 1):
            entry = state.control_stack[index]
            if type(entry) is int:
                visit_environment(entry)
            elif isinstance(entry, _SavedDefinitionPath):
                visit_environment(entry.value)
            elif isinstance(entry, _SubgraphFrame):
                visit_environment(entry.env)
        for address in range(self.working_memory_limit, len(state.memory)):
            static_word = state.memory[address]
            if static_word is not None and static_word.opcode is not None:
                visit_graph(address)
        if self.pending_host_call is not None:
            argument = self.pending_host_call.argument_address
            if argument is not None:
                visit_graph(argument)

    def _validate_typed_subgraph_return(self, frame: _SubgraphFrame) -> None:
        state = self.state
        current_frontier = self._frontier()
        if type(frame.free_space) is not int or not (
            0 <= current_frontier <= frame.free_space <= self.working_memory_limit
        ):
            raise IllegalTransition("malformed subgraph return boundary")
        if type(frame.env) is not int or not 0 <= frame.env <= len(state.memory):
            raise InvalidAddress("saved environment requires an address")
        if self._environment_address_in_interval(
            frame.env,
            current_frontier,
            frame.free_space,
        ):
            raise IllegalTransition(
                "saved environment lies inside reclaimed subgraph region"
            )

    def _restore_typed_subgraph_region(self, frame: _SubgraphFrame) -> bool:
        """Return one machine-generated child region exactly, without root scans."""
        self._validate_typed_subgraph_return(frame)
        state = self.state
        current_frontier = self._frontier()
        saved_frontier = frame.free_space
        if current_frontier == saved_frontier:
            state.env = frame.env
            return False
        if self._poison_reclaimed_environment:
            for address in range(current_frontier, saved_frontier):
                state.memory[address] = None
        state.free_space = saved_frontier
        state.env = frame.env
        self._frontier_restores += 1
        self._record_memory_event(
            "ENV_RECLAIM",
            {
                "from": current_frontier,
                "to": saved_frontier,
                "words": saved_frontier - current_frontier,
            },
        )
        return True

    def _restore_environment_region(
        self,
        frame: _SubgraphFrame | None,
        result_address: int | None,
    ) -> bool:
        if frame is None:
            return False
        state = self.state
        current_frontier = self._frontier()
        saved_frontier = frame.free_space
        if current_frontier > saved_frontier:
            raise IllegalTransition("subgraph frontier moved above saved frontier")
        if current_frontier == saved_frontier:
            state.env = frame.env
            return False
        if self._environment_address_in_interval(
            frame.env,
            current_frontier,
            saved_frontier,
        ):
            state.env = frame.env
            return False
        if result_address is not None and self._graph_references_environment_interval(
            result_address,
            current_frontier,
            saved_frontier,
        ):
            state.env = frame.env
            return False
        if self._poison_reclaimed_environment:
            for address in range(current_frontier, saved_frontier):
                state.memory[address] = None
        state.free_space = saved_frontier
        state.env = frame.env
        self._frontier_restores += 1
        self._record_memory_event(
            "ENV_RECLAIM",
            {"from": current_frontier, "to": saved_frontier, "env": frame.env},
        )
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
            if word.opcode is MuredOpcode.REC:
                address += 3
            elif word.opcode is MuredOpcode.CLOSURE or word.closure_slot:
                address += 2
            else:
                address += 1

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
            if state.c >= 0 and isinstance(
                state.control_stack[state.c], _SavedDefinitionPath
            ):
                self._pop_control_entry()
            self.state.memory[state.pc] = Word(MuredOpcode.STOP)
            state.fsp -= 1
            state.pc = word.definition
            state.direction = Direction.F
            state.q -= 1
            return
        if not isinstance(word.data, int):
            raise InvalidAddress("APP requires an argument address")
        parent_app = state.pc
        parent_env = self._pop_control()
        self._enter_subgraph(parent_env, word.data, parent_app)

    def _closure(self, word: Word) -> None:
        if self.state.direction is not Direction.F:
            raise IllegalTransition("CLOSURE requires forward execution")
        if not isinstance(word.data, int):
            raise MalformedClosure("CLOSURE requires an environment address")
        code = self._word(self.state.pc + 1)
        if code.opcode is not None or not isinstance(code.data, int):
            raise MalformedClosure("CLOSURE requires a following code pointer")
        self._push_environment_marker(word.data)
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
            MuredOpcode.EP,
            MuredOpcode.RBLOCK,
            MuredOpcode.RECP,
        }:
            raise IllegalTransition("JOIN parent must be APP, EP, RBLOCK, or RECP")
        self._discard_completed_definition_paths()
        saved_primitive = word.definition == 1
        frame = self._pop_subgraph_frame(saved_primitive)
        if (
            saved_primitive
            and frame is None
            and not self._has_saved_primitive_context()
        ):
            raise IllegalTransition(
                "JOIN primitive context marker has no saved context"
            )
        if frame is not None:
            self._validate_typed_subgraph_return(frame)
            state.s_a = self._publish_child_result(frame, state.s_a)
            self._audit_typed_subgraph_return_roots(frame, state.s_a, word.data)
        tail = self._word(state.s_a)
        single_word = state.fsp == state.s_a
        shareable_atomic = (
            single_word and tail.head and self._is_shareable_ep_value(tail)
        )
        if parent.opcode is MuredOpcode.EP and shareable_atomic:
            if type(parent.data) is not int or parent.data < 0:
                raise InvalidAddress("EP requires an environment address")
            target = self._word(parent.data)
            if target.opcode is not MuredOpcode.CLOSURE:
                raise IllegalTransition("EP sharing target is not an unshared closure")
            state.memory[parent.data] = Word(
                tail.opcode,
                tail.data,
                False,
                tail.definition,
                closure_slot=True,
            )
            state.memory[word.data] = Word(
                tail.opcode,
                tail.data,
                False,
                tail.definition,
            )
            state.fsp -= 2
        elif parent.opcode is MuredOpcode.RBLOCK:
            state.memory[word.data] = Word(
                MuredOpcode.RBLOCK,
                state.s_a,
                parent.head,
                parent.definition,
            )
            if state.q == 0:
                previous = state.memory[word.data - 1] if word.data > 0 else None
                if previous is None or previous.opcode is not MuredOpcode.RBLOCK:
                    binding_count = 1
                    cursor = word.data + 1
                    while cursor < len(state.memory):
                        candidate = state.memory[cursor]
                        if (
                            candidate is None
                            or candidate.opcode is not MuredOpcode.RBLOCK
                        ):
                            break
                        binding_count += 1
                        cursor += 1
                    state.phi -= binding_count
                    if state.phi < 0:
                        raise IllegalTransition("RBLOCK reverse underflows phi")
        elif parent.opcode is MuredOpcode.RECP:
            state.memory[word.data] = Word(MuredOpcode.APP, state.s_a, False)
        elif tail.head and tail.opcode is MuredOpcode.VAR and single_word:
            if type(tail.data) is not int or tail.data < 0:
                raise InvalidAddress("result VAR requires a De Bruijn index")
            state.memory[word.data] = Word(
                MuredOpcode.VAR if parent.head else MuredOpcode.APP_VAR,
                tail.data,
                parent.head,
            )
            if parent.head:
                state.fsp = word.data
            else:
                state.fsp -= 2
        elif single_word and tail.head and tail.opcode is MuredOpcode.APP:
            # Hilton inst_join copies a HEAD PTR directly into the destination,
            # preserving the destination class, but does not reclaim the result
            # slot because the pointed-to graph may still occupy the live suffix.
            if type(tail.data) is not int or tail.data < 0:
                raise InvalidAddress("result APP requires a graph address")
            state.memory[word.data] = Word(
                MuredOpcode.APP,
                tail.data,
                parent.head,
                tail.definition,
            )
        elif shareable_atomic:
            # Hilton inst_join compacts a HEAD non-PTR result into its parent.
            # A HEAD destination owns everything above it; an APPLY destination
            # drops only the JOIN/result suffix because earlier spine words live.
            state.memory[word.data] = Word(
                tail.opcode,
                tail.data,
                parent.head,
                tail.definition,
            )
            if parent.head:
                state.fsp = word.data
            else:
                state.fsp -= 2
        elif saved_primitive and single_word and tail.opcode is not MuredOpcode.APP:
            # Strict primitives consume any single-word non-PTR value, including
            # primitive and defined-symbol values that are not scalar EP-shareable
            # atoms.  APP is Python's graph-pointer representation and must retain
            # its target graph instead of being compacted away.
            state.memory[word.data] = Word(
                tail.opcode,
                tail.data,
                False,
                tail.definition,
            )
            state.fsp -= 2
        else:
            # Pointer/multiword results remain graph-owned.
            state.memory[word.data] = Word(MuredOpcode.APP, state.s_a, False)

        result_address = word.data if word.data <= state.fsp else None
        restored_frontier = (
            self._restore_typed_subgraph_region(frame) if frame is not None else False
        )
        self._record_memory_event(
            "JOIN_RETURN",
            {
                "parent_pc": word.data,
                "result_address": -1 if result_address is None else result_address,
                "restored_frontier": restored_frontier,
            },
        )

        if saved_primitive:
            if frame is not None:
                state.prim = frame.prim
                state.fire = frame.fire
            elif not self._restore_primitive_context():
                raise IllegalTransition("JOIN failed to restore primitive context")
            if state.fire <= 0 or state.prim is None:
                raise IllegalTransition("restored primitive context is not active")
            state.fire -= 1
            if state.fire == 0:
                state.pc = word.data
                self._fire_primitive()
                return
        state.pc = word.data - 1

    @staticmethod
    def _is_shareable_ep_value(word: Word) -> bool:
        if word.opcode in {MuredOpcode.INT, MuredOpcode.FLOAT, MuredOpcode.CHAR}:
            return True
        return word.opcode is MuredOpcode.SYM and word.definition is None

    @staticmethod
    def _is_linear_application_prefix(word: Word) -> bool:
        return word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
            not word.head
            and word.opcode
            in {
                MuredOpcode.INT,
                MuredOpcode.FLOAT,
                MuredOpcode.CHAR,
                MuredOpcode.SYM,
                MuredOpcode.PRIM_0,
                MuredOpcode.PRIM_1,
                MuredOpcode.PRIM_2,
            }
        )

    @staticmethod
    def _is_supported_io_bind_value(word: Word) -> bool:
        if word.opcode in {MuredOpcode.INT, MuredOpcode.FLOAT, MuredOpcode.CHAR}:
            return True
        if word.opcode is MuredOpcode.SYM:
            return word.definition is None
        return word.opcode is MuredOpcode.EP and type(word.data) is int

    def _ep(self, word: Word) -> None:
        state = self.state
        if type(word.data) is not int or word.data < 0:
            raise InvalidAddress("EP requires an environment address")

        target_address = word.data
        seen: set[int] = set()
        while True:
            if target_address in seen:
                raise IllegalTransition("cyclic EP environment chain")
            seen.add(target_address)
            target = self._word(target_address)
            if target.opcode is not MuredOpcode.EP:
                break
            if type(target.data) is not int or target.data < 0:
                raise InvalidAddress("EP requires an environment address")
            target_address = target.data

        if state.direction is Direction.F:
            # Original RED treats EP as an argument descriptor in problem mode:
            # preserve the current environment path and continue walking the
            # application spine.  Dereferencing happens only in result mode.
            self._copy_result(word)
            self._push_control(state.env)
            state.pc += 1
            return

        parent_ep = state.pc
        caller_path = self._pop_control()
        if caller_path != state.env:
            self._push_environment_marker(caller_path)
        if target.opcode is MuredOpcode.CLOSURE:
            self._enter_subgraph(state.env, target_address, parent_ep)
            return
        if target.opcode is MuredOpcode.UBV:
            if type(target.data) is not int:
                raise InvalidAddress("UBV requires a binder depth")
            state.memory[parent_ep] = Word(
                MuredOpcode.VAR,
                state.phi - target.data,
                False,
            )
            state.pc -= 1
            return
        if target.opcode in {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }:
            state.memory[parent_ep] = Word(
                target.opcode,
                target.data,
                False,
                target.definition,
            )
            if state.fire > 0:
                if state.prim is None:
                    raise IllegalTransition("active primitive countdown requires prim")
                state.fire -= 1
                if state.fire == 0:
                    state.pc = parent_ep
                    self._fire_primitive()
                    return
            state.pc -= 1
            return
        raise IllegalTransition("EP points to unsupported environment value")

    def _lambda(self, word: Word) -> None:
        state = self.state
        if state.direction is Direction.B:
            state.phi -= 1
            if state.phi < 0:
                raise IllegalTransition("LAMBDA reverse underflows phi")
            state.pc -= 1
            return
        result_head = self._word(state.fsp)
        if state.q == 0 or state.argcnt == 0 or result_head.opcode is MuredOpcode.STOP:
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
        if result_head.opcode is MuredOpcode.EP:
            if type(result_head.data) is not int or result_head.data < 0:
                raise InvalidAddress("result EP requires an environment address")
            self._pop_control()
            self._allocate_environment(Word(MuredOpcode.EP, result_head.data, False))
            state.q -= 1
            state.fsp -= 1
            state.argcnt -= 1
            state.pc += 1
            return
        if result_head.opcode is MuredOpcode.APP:
            if not isinstance(result_head.data, int):
                raise InvalidAddress("result APP requires an argument address")
            saved_path = self._pop_control()
            self._allocate_environment(Word(None, result_head.data, False))
            self._allocate_environment(Word(MuredOpcode.CLOSURE, saved_path, False))
        else:
            # Historical PUSH-BINDING accepts immediate argument data directly.
            # Presence is tracked by argcount; the value need not be pointer-shaped.
            self._allocate_environment(
                Word(
                    result_head.opcode,
                    result_head.data,
                    False,
                    result_head.definition,
                )
            )
        state.q -= 1
        state.fsp -= 1
        state.argcnt -= 1
        state.pc += 1

    def _struct(self, word: Word) -> None:
        if type(word.data) is not str or word.data == "":
            raise IllegalTransition("STRUCT requires a non-empty tag name")
        state = self.state
        if state.direction is Direction.B:
            state.q = self._pop_saved_quantum()
            state.phi -= 1
            if state.phi < 0:
                raise IllegalTransition("STRUCT reverse underflows phi")
            state.pc -= 1
            return

        result_head = self._word(state.fsp)
        if state.q == 0 or result_head.opcode not in {
            MuredOpcode.APP,
            MuredOpcode.APP_VAR,
            MuredOpcode.EP,
        }:
            self._push_saved_quantum(state.q)
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

        if result_head.opcode is MuredOpcode.EP:
            if type(result_head.data) is not int or result_head.data < 0:
                raise InvalidAddress("result EP requires an environment address")
            self._pop_control()
            self._allocate_environment(Word(MuredOpcode.EP, result_head.data, False))
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
            parent_pc = state.pc
            parent_env = self._pop_control()
            self._enter_subgraph(parent_env, word.data, parent_pc)
            state.argcnt = -1
            return

        if state.q > 0:
            self._allocate_environment_block(
                (
                    Word(MuredOpcode.REC, word.data + 1, False),
                    Word(None),
                    Word(None),
                )
            )
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
            if block_address < 0:
                raise InvalidAddress("RUP binding block starts before the graph")
            for index in range(count):
                rec = self._word(address)
                if rec.opcode is not MuredOpcode.REC:
                    raise IllegalTransition(
                        "RUP requires contiguous REC environment data"
                    )
                context_slot = self._word(address + 1)
                block_slot = self._word(address + 2)
                if context_slot.opcode is not None or block_slot.opcode is not None:
                    raise IllegalTransition("RUP requires REC metadata slots")

                # RBLOCKs are encountered left-to-right but their three-word REC
                # entries are allocated downward, so the top environment entry
                # corresponds to the last RBLOCK immediately preceding this RUP.
                source = self._word(block_address + count - 1 - index)
                if source.opcode is not MuredOpcode.RBLOCK:
                    raise IllegalTransition(
                        "RUP requires a contiguous RBLOCK graph block"
                    )
                if type(source.data) is not int or source.data < 0:
                    raise InvalidAddress("RBLOCK requires a binding graph address")
                if rec.data != source.data + 1:
                    raise IllegalTransition("RUP REC binding does not match RBLOCK")

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
                self._push_environment_marker(context)
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
        frontier = self._frontier()
        normalized_env = state.env
        needs_bridge = state.env != frontier
        if needs_bridge:
            normalized_env = frontier - 1
        join_address = state.fsp + 1
        if normalized_env <= state.fsp or join_address >= normalized_env:
            raise GraphEnvironmentCollision("graph and environment collide")
        if state.c + 1 >= len(state.control_stack):
            raise ControlStackOverflow("μRED control stack overflow")

        if needs_bridge:
            state.memory[normalized_env] = Word(MuredOpcode.PNP, state.env, False)
            state.free_space = normalized_env
            state.env = normalized_env
            self._record_memory_event(
                "ENV_ALLOC",
                {"address": normalized_env, "opcode": "PNP", "words": 1},
            )

        frame = _SubgraphFrame(
            env=normalized_env,
            free_space=normalized_env,
            prim=state.prim,
            fire=state.fire,
        )
        self._push_control_entry(frame)
        state.prim = None
        state.fire = 0
        self._push_subgraph_join(frame, parent_recp)
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
        self._push_environment_marker(parent_environment)
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
        self._discard_completed_definition_paths()
        self.state.pc += 1
        self.state.halted = True

    def _passive(self, word: Word) -> None:
        if self.state.direction is Direction.B:
            state = self.state
            if state.fire > 0:
                if state.prim is None:
                    raise IllegalTransition("active primitive countdown requires prim")
                state.fire -= 1
                if state.fire == 0:
                    self._fire_primitive()
                    return
            state.pc -= 1
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
                self._push_definition_path(state.env)
                self.state.memory[state.pc] = Word(
                    MuredOpcode.APP,
                    next_path,
                    word.head,
                    word.definition,
                )
                state.argcnt -= 1
                return
            # Historical SYM RESULT falls through MOVE-BACKWARD.  Thus an
            # ordinary symbol completes an active strict-argument countdown
            # exactly like INT/FLOAT/CHAR.  Definition expansion above is the
            # exception: it diverts to the definition before MOVE-BACKWARD and
            # must leave the enclosing primitive context active.
            if state.fire > 0:
                if state.prim is None:
                    raise IllegalTransition("active primitive countdown requires prim")
                state.fire -= 1
                if state.fire == 0:
                    self._fire_primitive()
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
            self._copy_result(Word(MuredOpcode.APP_VAR, state.phi - redex.data, False))
            return
        if redex.opcode is MuredOpcode.CLOSURE:
            if type(redex.data) is not int or redex.data < 0:
                raise MalformedClosure("CLOSURE requires an environment address")
            code = self._word(redex_address + 1)
            if code.opcode is not None or type(code.data) is not int or code.data < 0:
                raise MalformedClosure("CLOSURE requires a following code pointer")
            self._push_control(state.env)
            self._copy_result(Word(MuredOpcode.EP, redex_address, False))
            return
        if redex.opcode is MuredOpcode.EP:
            if type(redex.data) is not int or redex.data < 0:
                raise InvalidAddress("EP requires an environment address")
            self._push_control(state.env)
            self._copy_result(Word(MuredOpcode.EP, redex.data, False))
            return
        if redex.opcode is MuredOpcode.REC:
            self._rec_fields(redex_address)
            self._copy_result(Word(MuredOpcode.RECP, redex_address, False))
            return
        if redex.opcode in {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }:
            self._copy_result(Word(redex.opcode, redex.data, False, redex.definition))
            return
        raise IllegalTransition("APP_VAR encountered malformed redex-store value")

    def _pop_if_branch_paths(
        self,
        false_branch: Word,
        true_branch: Word,
    ) -> tuple[int | None, int | None]:
        # Original RED saves an environment context for both PTR and EP
        # arguments.  APP is the Python μRED spelling of PTR; an EP branch
        # therefore consumes a control-stack path just like an APP branch.
        path_opcodes = {MuredOpcode.APP, MuredOpcode.EP}
        true_path = self._pop_control() if true_branch.opcode in path_opcodes else None
        false_path = (
            self._pop_control() if false_branch.opcode in path_opcodes else None
        )
        return false_path, true_path

    def _begin_if_reconstruction(
        self,
        false_branch: Word,
        true_branch: Word,
    ) -> None:
        state = self.state
        false_path, true_path = self._pop_if_branch_paths(false_branch, true_branch)
        self._push_saved_quantum(state.q)
        if false_path is not None:
            self._push_control(false_path)
        if true_path is not None:
            self._push_control(true_path)
        state.q = 0
        state.prim = "__IF_RECONSTRUCT__"
        path_opcodes = {MuredOpcode.APP, MuredOpcode.EP}
        state.fire = int(false_branch.opcode in path_opcodes) + int(
            true_branch.opcode in path_opcodes
        )
        state.pc -= 1

        if state.fire == 0:
            state.q = self._pop_saved_quantum()
            state.prim = None

    def _select_if_branch(
        self, condition: str, *, consume_quantum: bool = True
    ) -> None:
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

        if consume_quantum:
            state.q -= 1
        if selected.opcode is MuredOpcode.APP:
            if type(selected.data) is not int or selected.data < 0:
                raise InvalidAddress("IF selected APP requires a graph address")
            if selected_path is None:
                raise IllegalTransition("IF selected APP lost its environment path")
            state.fsp = false_slot - 1
            state.env = selected_path
            state.pc = selected.data
            state.direction = Direction.F
            return

        if selected.opcode is MuredOpcode.EP:
            if type(selected.data) is not int or selected.data < 0:
                raise InvalidAddress("IF selected EP requires an environment address")
            if selected_path is None:
                raise IllegalTransition("IF selected EP lost its environment path")

            target_address = selected.data
            seen: set[int] = set()
            while True:
                if target_address in seen:
                    raise IllegalTransition("cyclic IF-selected EP environment chain")
                seen.add(target_address)
                target = self._word(target_address)
                if target.opcode is not MuredOpcode.EP:
                    break
                if type(target.data) is not int or target.data < 0:
                    raise InvalidAddress(
                        "IF selected EP chain requires an environment address"
                    )
                target_address = target.data

            # IF executes the selected argument as a HEAD instruction.  If an
            # EP has already been shared to an atom, that means the atom itself
            # becomes the one-word result.  If it still names a closure, enter
            # that closure directly: the conditional has already disappeared,
            # so no JOIN/return frame belongs around this head execution.
            state.env = selected_path
            if self._is_shareable_ep_value(target):
                state.memory[false_slot] = Word(
                    target.opcode,
                    target.data,
                    True,
                    target.definition,
                )
                state.fsp = false_slot
                state.pc = false_slot
                state.direction = Direction.B
                return
            if target.opcode is MuredOpcode.CLOSURE:
                state.fsp = false_slot - 1
                state.pc = target_address
                state.direction = Direction.F
                return
            raise IllegalTransition(
                "IF selected EP points to unsupported environment value: "
                f"{target.opcode}"
            )

        # The selected value occupies the old false-branch slot after the
        # four-word IF construct is collapsed.  It is now the result head,
        # even though it was stored as an application argument before firing.
        state.memory[false_slot] = Word(
            selected.opcode,
            selected.data,
            True,
            selected.definition,
        )
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
        self.state.q = self._pop_saved_quantum()

    def _cons_field_entry(
        self,
        descriptor: Word,
        root_address: int,
    ) -> tuple[Word, Word | None]:
        if descriptor.opcode is MuredOpcode.APP:
            if type(descriptor.data) is not int or descriptor.data < 0:
                raise InvalidAddress("CONS APP field requires a graph address")
            return Word(MuredOpcode.APP, descriptor.data, False), None
        if descriptor.opcode is MuredOpcode.APP_VAR:
            if type(descriptor.data) is not int or descriptor.data < 0:
                raise InvalidAddress("CONS APP_VAR field requires a variable index")
            return Word(MuredOpcode.APP_VAR, descriptor.data + 1, False), None
        if descriptor.opcode is None:
            raise IllegalTransition("CONS requires executable value descriptors")
        return (
            Word(MuredOpcode.APP, root_address, False),
            Word(
                descriptor.opcode,
                descriptor.data,
                True,
                descriptor.definition,
            ),
        )

    def _fire_cons(self) -> None:
        state = self.state
        base = state.pc
        right_descriptor = self._word(base)
        left_descriptor = self._word(base + 1)
        old_fsp = state.fsp

        # Structured strict arguments may already live above the compact
        # primitive spine. Preserve those graphs and append any atomic field
        # roots after them instead of reusing addresses they may reference.
        next_root = max(old_fsp + 1, base + 4)
        right_field, right_root = self._cons_field_entry(
            right_descriptor,
            next_root,
        )
        if right_root is not None:
            next_root += 1
        left_field, left_root = self._cons_field_entry(
            left_descriptor,
            next_root,
        )
        if left_root is not None:
            next_root += 1

        frontier = state.free_space
        last_address = max(old_fsp, base + 3, next_root - 1)
        if last_address >= frontier:
            raise GraphEnvironmentCollision("graph and environment collide")

        state.memory[base] = Word(MuredOpcode.STRUCT, "PAIR", False)
        state.memory[base + 1] = right_field
        state.memory[base + 2] = left_field
        state.memory[base + 3] = Word(MuredOpcode.VAR, 0, True)
        cursor = max(old_fsp + 1, base + 4)
        if right_root is not None:
            state.memory[cursor] = right_root
            cursor += 1
        if left_root is not None:
            state.memory[cursor] = left_root

        state.fsp = last_address
        state.q -= 1
        state.pc = base - 1

    def _fire_primitive(self) -> None:
        state = self.state
        primitive = state.prim
        state.prim = None
        state.fire = 0

        if primitive == "__EQUALITY_CONTINUE__":
            self._continue_equality()
            return

        if primitive == "__EQUAL_IF__":
            condition = self._word(state.pc)
            if condition.opcode is not MuredOpcode.SYM or condition.data not in {
                "TRUE",
                "FALSE",
                "__EQUAL_STUCK__",
            }:
                raise IllegalTransition(
                    "internal equality IF requires a tri-state condition"
                )
            if condition.data == "__EQUAL_STUCK__":
                false_slot = state.pc - 2
                false_branch = self._word(false_slot)
                true_branch = self._word(false_slot + 1)
                self._pop_if_branch_paths(false_branch, true_branch)
                state.memory[false_slot] = Word(
                    MuredOpcode.SYM,
                    "__EQUAL_STUCK__",
                    True,
                )
                state.fsp = false_slot
                state.pc = false_slot
                return
            self._select_if_branch(condition.data, consume_quantum=False)
            return

        if primitive == "__IF_RECONSTRUCT__":
            self._finish_if_reconstruction()
            state.pc -= 1
            return

        if primitive == "__STRUCT_SELECTOR_RESULT__":
            selected = self._word(state.pc)
            if selected.opcode is MuredOpcode.APP:
                if type(selected.data) is not int or selected.data < 0:
                    raise InvalidAddress(
                        "structure selector result requires a graph address"
                    )
                root = self._word(selected.data)
                if root.opcode is MuredOpcode.STRUCT:
                    self._copy_struct_value_to_result(selected.data, state.pc)
                else:
                    # The structure lookup already succeeded; this is the
                    # selected field's reduced value, and fields may contain
                    # arbitrary graphs.  JOIN leaves a compact APP descriptor
                    # in the selector operand slot, so promote that descriptor
                    # over the consumed selector head before moving backward.
                    self._promote_result_value(state.pc)
                    if root.opcode is MuredOpcode.LAMBDA and state.argcnt > 0:
                        # The promoted field is the operator for arguments that
                        # preceded the selector redex. Execute it with those
                        # surviving arguments as the result stack, just like a
                        # statically compiled lambda application.
                        state.fsp = state.pc - 1
                        state.direction = Direction.F
                        return
            else:
                state.memory[state.pc] = Word(
                    selected.opcode,
                    selected.data,
                    True,
                    selected.definition,
                )
                state.fsp = state.pc
            state.pc -= 1
            return

        if primitive == "IO-RETURN":
            if state.q > 0:
                self._promote_result_value(state.pc)
                state.q -= 1
            state.pc -= 1
            return

        if primitive in {"UART-TX", "UART-TX-BYTES"}:
            if state.q > 0:
                self._suspend_host_call(primitive, argument_address=state.pc)
            else:
                state.pc -= 1
            return

        if primitive in {"IO-BIND", "IO-THEN"}:
            self._fire_io_sequence(primitive)
            return

        if primitive == "CONS":
            if state.q > 0:
                self._fire_cons()
                return
            state.pc -= 1
            return

        if primitive == "EQUAL?":
            self._fire_equality()
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
        selector: tuple[str, int] | None = None
        if primitive == "CAR":
            selector = ("PAIR", 2)
        elif primitive == "CDR":
            selector = ("PAIR", 1)
        elif primitive is not None:
            selector = self.struct_selectors.get(primitive)

        if state.q > 0 and selector is not None:
            tag, field_offset = selector
            value, source_address = self._struct_field_value(
                self._word(state.pc),
                tag=tag,
                field_offset=field_offset,
            )
            if value is not None and source_address is not None:
                if (
                    self._is_linear_application_prefix(value)
                    or value.opcode is MuredOpcode.LAMBDA
                    or (
                        value.opcode is MuredOpcode.SYM
                        and value.definition is not None
                    )
                ):
                    parent_address = state.pc
                    parent = self._word(parent_address)
                    if parent.opcode is not MuredOpcode.APP:
                        raise IllegalTransition(
                            "structure selector requires an APP result parent"
                        )
                    state.q -= 1
                    state.prim = "__STRUCT_SELECTOR_RESULT__"
                    state.fire = 1
                    self._enter_subgraph(state.env, source_address, parent_address)
                    return
                if value.opcode is MuredOpcode.STRUCT:
                    self._copy_struct_value_to_result(source_address, state.pc)
                    state.q -= 1
                    state.pc -= 1
                    return
                result = Word(
                    value.opcode,
                    value.data,
                    False,
                    value.definition,
                )

        if state.q > 0 and primitive is not None and result is None:
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
                "EQUAL?",
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

    def _struct_field_value(
        self,
        operand: Word,
        *,
        tag: str,
        field_offset: int,
    ) -> tuple[Word | None, int | None]:
        if operand.opcode is not MuredOpcode.APP:
            return None, None
        if type(operand.data) is not int or operand.data < 0:
            raise InvalidAddress(f"{tag} selector requires a graph address")
        root_address = operand.data
        root = self._word(root_address)
        if root.opcode is not MuredOpcode.STRUCT or root.data != tag:
            return None, None
        descriptor = self._word(root_address + field_offset)
        if descriptor.opcode is MuredOpcode.APP:
            if type(descriptor.data) is not int or descriptor.data < 0:
                raise InvalidAddress(f"{tag} field requires a graph address")
            value = self._word(descriptor.data)
            return value, descriptor.data
        if descriptor.opcode is MuredOpcode.APP_VAR:
            return None, None
        if not descriptor.head and descriptor.opcode in {
            MuredOpcode.EP,
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }:
            # JOIN can compact a reduced field directly into the STRUCT spine.
            # Read that APPLY-class descriptor as the completed field value, not
            # as the start of an application whose following STRUCT slots belong
            # to the same structure.
            return (
                Word(
                    descriptor.opcode,
                    descriptor.data,
                    True,
                    descriptor.definition,
                    descriptor.closure_slot,
                ),
                root_address + field_offset,
            )
        raise IllegalTransition(
            f"{tag} field requires APP, APP_VAR, or inline atomic descriptor"
        )

    def _copy_struct_value_to_result(
        self,
        source_address: int,
        destination: int,
    ) -> None:
        source = self._word(source_address)
        if source.opcode is not MuredOpcode.STRUCT:
            raise IllegalTransition("structure result copy requires STRUCT root")

        old_fsp = self.state.fsp
        words: list[Word] = [source]
        cursor = source_address + 1
        while True:
            word = self._word(cursor)
            words.append(word)
            if word.opcode is MuredOpcode.VAR:
                if word.data != 0:
                    raise IllegalTransition("STRUCT result requires trailing VAR 0")
                break
            if word.opcode not in {
                MuredOpcode.APP,
                MuredOpcode.APP_VAR,
                MuredOpcode.EP,
                MuredOpcode.INT,
                MuredOpcode.FLOAT,
                MuredOpcode.CHAR,
                MuredOpcode.SYM,
                MuredOpcode.PRIM_0,
                MuredOpcode.PRIM_1,
                MuredOpcode.PRIM_2,
            }:
                raise IllegalTransition(
                    "STRUCT result requires field descriptors; "
                    f"got {word.opcode} at {cursor}"
                )
            cursor += 1

        frontier = self.state.free_space
        last_address = destination + len(words) - 1
        if last_address >= frontier:
            raise GraphEnvironmentCollision("graph and environment collide")

        for offset, word in enumerate(words):
            self.state.memory[destination + offset] = Word(
                word.opcode,
                word.data,
                word.head,
                word.definition,
            )
        self.state.memory[last_address] = Word(MuredOpcode.VAR, 0, True)
        # Copying only the STRUCT spine must not reclaim detached field graphs
        # that the copied APP descriptors still reference above the destination.
        self.state.fsp = max(old_fsp, last_address)

    def _active_equality_frame(self) -> _EqualityFrame:
        for index in range(self.state.c, -1, -1):
            entry = self.state.control_stack[index]
            if isinstance(entry, _EqualityFrame):
                return entry
        raise IllegalTransition("internal equality continuation is missing")

    def _equality_step(
        self,
        task: _EqualityTask,
    ) -> tuple[bool | None, tuple[_EqualityTask, ...]]:
        """Perform one Hilton EQUAL* graph decomposition step."""
        inline_opcodes = {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }

        def application_parts(address: int) -> tuple[int, tuple[int, ...]] | None:
            if not self._is_linear_application_prefix(self._word(address)):
                return None
            descriptors: list[int] = []
            cursor = address
            while True:
                word = self._word(cursor)
                if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                    not word.head and word.opcode in inline_opcodes
                ):
                    descriptors.append(cursor)
                    cursor += 1
                    continue
                return cursor, tuple(reversed(descriptors))

        def struct_parts(address: int) -> tuple[str, tuple[int, ...]] | None:
            root = self._word(address)
            if root.opcode is not MuredOpcode.STRUCT or type(root.data) is not str:
                return None
            fields: list[int] = []
            cursor = address + 1
            while True:
                descriptor = self._word(cursor)
                if descriptor.opcode in {
                    MuredOpcode.APP,
                    MuredOpcode.APP_VAR,
                    MuredOpcode.EP,
                } or (not descriptor.head and descriptor.opcode in inline_opcodes):
                    fields.append(cursor)
                    cursor += 1
                    continue
                if descriptor.opcode is not MuredOpcode.VAR or descriptor.data != 0:
                    raise IllegalTransition("STRUCT equality requires trailing VAR 0")
                return root.data, tuple(reversed(fields))

        left = task.left
        right = task.right
        left_word = self._word(left)
        right_word = self._word(right)
        if task.descriptor_mode:
            if left_word.opcode is MuredOpcode.APP:
                if type(left_word.data) is not int or left_word.data < 0:
                    raise InvalidAddress("EQUAL? APP requires a graph address")
                left = left_word.data
                left_word = self._word(left)
            elif left_word.opcode is MuredOpcode.APP_VAR:
                if type(left_word.data) is not int or left_word.data < 0:
                    raise InvalidAddress("EQUAL? APP_VAR requires a variable index")
                left_word = Word(MuredOpcode.VAR, left_word.data, True)

            if right_word.opcode is MuredOpcode.APP:
                if type(right_word.data) is not int or right_word.data < 0:
                    raise InvalidAddress("EQUAL? APP requires a graph address")
                right = right_word.data
                right_word = self._word(right)
            elif right_word.opcode is MuredOpcode.APP_VAR:
                if type(right_word.data) is not int or right_word.data < 0:
                    raise InvalidAddress("EQUAL? APP_VAR requires a variable index")
                right_word = Word(MuredOpcode.VAR, right_word.data, True)

        if left_word.opcode is MuredOpcode.UBV or right_word.opcode is MuredOpcode.UBV:
            if (
                left_word.opcode is MuredOpcode.UBV
                and right_word.opcode is MuredOpcode.UBV
                and left_word.data == right_word.data
            ):
                return True, ()
            return None, ()

        left_constant = self._constant_word_key(left_word)
        right_constant = self._constant_word_key(right_word)
        if left_constant is not None or right_constant is not None:
            if left_constant is None or right_constant is None:
                return False, ()
            return left_constant == right_constant, ()

        if left_word.opcode is MuredOpcode.VAR or right_word.opcode is MuredOpcode.VAR:
            if (
                left_word.opcode is not MuredOpcode.VAR
                or right_word.opcode is not MuredOpcode.VAR
            ):
                variable = (
                    left_word if left_word.opcode is MuredOpcode.VAR else right_word
                )
                if type(variable.data) is not int or variable.data < 0:
                    raise InvalidAddress("EQUAL? VAR requires a De Bruijn index")
                return (False, ()) if variable.data < task.lambdas else (None, ())
            if type(left_word.data) is not int or left_word.data < 0:
                raise InvalidAddress("EQUAL? VAR requires a De Bruijn index")
            if type(right_word.data) is not int or right_word.data < 0:
                raise InvalidAddress("EQUAL? VAR requires a De Bruijn index")
            if left_word.data == right_word.data:
                return True, ()
            if left_word.data < task.lambdas or right_word.data < task.lambdas:
                return False, ()
            return None, ()

        left_struct = struct_parts(left)
        right_struct = struct_parts(right)
        if left_struct is not None or right_struct is not None:
            if left_struct is None or right_struct is None:
                return False, ()
            left_tag, left_fields = left_struct
            right_tag, right_fields = right_struct
            if left_tag != right_tag or len(left_fields) != len(right_fields):
                return False, ()
            return True, tuple(
                _EqualityTask(left_field, right_field, task.lambdas + 1, True)
                for left_field, right_field in zip(
                    left_fields, right_fields, strict=True
                )
            )

        if (
            left_word.opcode is MuredOpcode.LAMBDA
            or right_word.opcode is MuredOpcode.LAMBDA
        ):
            if (
                left_word.opcode is not MuredOpcode.LAMBDA
                or right_word.opcode is not MuredOpcode.LAMBDA
            ):
                return False, ()
            left_body = left
            right_body = right
            depth = task.lambdas
            while (
                self._word(left_body).opcode is MuredOpcode.LAMBDA
                and self._word(right_body).opcode is MuredOpcode.LAMBDA
            ):
                left_body += 1
                right_body += 1
                depth += 1
            if (
                self._word(left_body).opcode is MuredOpcode.LAMBDA
                or self._word(right_body).opcode is MuredOpcode.LAMBDA
            ):
                return False, ()
            return True, (_EqualityTask(left_body, right_body, depth, False),)

        left_application = application_parts(left)
        right_application = application_parts(right)
        if left_application is not None or right_application is not None:
            if left_application is None or right_application is None:
                return False, ()
            left_operator, left_arguments = left_application
            right_operator, right_arguments = right_application
            if len(left_arguments) != len(right_arguments):
                return False, ()
            return True, (
                _EqualityTask(left_operator, right_operator, task.lambdas, False),
                *(
                    _EqualityTask(left_argument, right_argument, task.lambdas, True)
                    for left_argument, right_argument in zip(
                        left_arguments, right_arguments, strict=True
                    )
                ),
            )

        if (
            left_word.opcode is MuredOpcode.CLOSURE
            or right_word.opcode is MuredOpcode.CLOSURE
        ):
            if (
                left_word.opcode is not MuredOpcode.CLOSURE
                or right_word.opcode is not MuredOpcode.CLOSURE
            ):
                return False, ()
            left_code = self._word(left + 1)
            right_code = self._word(right + 1)
            if left_code.opcode is not None or right_code.opcode is not None:
                raise MalformedClosure("CLOSURE equality requires code pointers")
            return (
                left_word.data == right_word.data and left_code.data == right_code.data,
                (),
            )

        if left_word.opcode is MuredOpcode.EP or right_word.opcode is MuredOpcode.EP:
            if (
                left_word.opcode is right_word.opcode
                and left_word.data == right_word.data
            ):
                return True, ()
            return None, ()

        if left_word.opcode is not right_word.opcode:
            return False, ()
        raise IllegalTransition(f"unsupported EQUAL? node opcode: {left_word.opcode}")

    def _append_equality_task_graph(self, task: _EqualityTask) -> int:
        root = self.state.fsp + 1
        self._push_graph(Word(MuredOpcode.INT, task.left, False))
        self._push_graph(Word(MuredOpcode.INT, task.right, False))
        self._push_graph(Word(MuredOpcode.INT, task.lambdas, False))
        self._push_graph(Word(MuredOpcode.INT, int(task.descriptor_mode), False))
        self._push_graph(Word(MuredOpcode.PRIM_0, "__EQUAL_STAR__", True))
        return root

    def _append_equality_conjunction(self, children: tuple[_EqualityTask, ...]) -> int:
        if not children:
            raise IllegalTransition("internal equality conjunction requires children")
        child_roots = tuple(
            self._append_equality_task_graph(child) for child in children
        )
        true_root = self._push_graph(Word(MuredOpcode.SYM, "TRUE", True))
        false_root = self._push_graph(Word(MuredOpcode.SYM, "FALSE", True))
        branch_root = true_root
        for child_root in reversed(child_roots):
            root = self.state.fsp + 1
            self._push_graph(Word(MuredOpcode.APP, false_root, False))
            self._push_graph(Word(MuredOpcode.APP, branch_root, False))
            self._push_graph(Word(MuredOpcode.APP, child_root, False))
            self._push_graph(Word(MuredOpcode.PRIM_0, "__EQUAL_IF__", True))
            branch_root = root
        return branch_root

    def _launch_equality_child(
        self, frame: _EqualityFrame, task: _EqualityTask
    ) -> None:
        state = self.state
        task_root = self._append_equality_task_graph(task)
        parent = self._push_graph(Word(MuredOpcode.APP, task_root, False))
        state.prim = "__EQUALITY_CONTINUE__"
        state.fire = 1
        self._enter_subgraph(state.env, task_root, parent)

    def _run_equality_child(self) -> None:
        state = self.state
        primitive_pc = state.pc
        task_root = primitive_pc - 4
        if task_root < 0:
            raise IllegalTransition("internal equality task is truncated")
        left_word = self._word(task_root)
        right_word = self._word(task_root + 1)
        lambdas_word = self._word(task_root + 2)
        descriptor_mode_word = self._word(task_root + 3)
        metadata = (left_word, right_word, lambdas_word, descriptor_mode_word)
        if any(word.opcode is not MuredOpcode.INT for word in metadata):
            raise IllegalTransition("internal equality task metadata is malformed")
        if (
            type(left_word.data) is not int
            or type(right_word.data) is not int
            or type(lambdas_word.data) is not int
            or type(descriptor_mode_word.data) is not int
        ):
            raise IllegalTransition("internal equality task metadata is malformed")
        left = left_word.data
        right = right_word.data
        lambdas = lambdas_word.data
        descriptor_mode = descriptor_mode_word.data
        if left < 0 or right < 0 or lambdas < 0 or descriptor_mode not in {0, 1}:
            raise IllegalTransition("internal equality task metadata is invalid")
        if state.argcnt != 4:
            raise IllegalTransition(
                "internal equality task requires four metadata words"
            )

        result, children = self._equality_step(
            _EqualityTask(left, right, lambdas, bool(descriptor_mode))
        )

        join_address = state.fsp - 4
        join = self._word(join_address)
        if join.opcode is not MuredOpcode.JOIN:
            raise IllegalTransition("internal equality task lost its JOIN")
        state.argcnt = 0

        if result and children:
            state.fsp = join_address - 1
            root = self._append_equality_conjunction(children)
            self._push_graph(join)
            state.pc = root
            state.direction = Direction.F
            return

        state.fsp = join_address
        if result is None:
            answer = Word(MuredOpcode.SYM, "__EQUAL_STUCK__", True)
        else:
            value = self._bool_word(result)
            answer = Word(value.opcode, value.data, True, value.definition)
        self._copy_result(answer)
        state.pc = join_address
        state.direction = Direction.B

    def _finish_equality(self, frame: _EqualityFrame, result: bool | None) -> None:
        state = self.state
        if state.c < 0 or state.control_stack[state.c] is not frame:
            raise IllegalTransition("internal equality frame is not current")
        self._pop_control_entry()
        state.q = self._pop_saved_quantum()
        if result is None:
            state.fsp = frame.live_fsp
        else:
            answer = self._bool_word(result)
            state.memory[frame.result_pc] = Word(
                answer.opcode,
                answer.data,
                True,
                answer.definition,
            )
            state.fsp = frame.result_pc
        state.pc = frame.result_pc - 1

    def _continue_equality(self) -> None:
        state = self.state
        frame = self._active_equality_frame()
        child_result = self._word(state.pc)
        if child_result.opcode is not MuredOpcode.SYM or child_result.data not in {
            "TRUE",
            "FALSE",
            "__EQUAL_STUCK__",
        }:
            raise IllegalTransition(
                "internal equality child did not return a tri-state value"
            )
        if child_result.data == "__EQUAL_STUCK__":
            self._finish_equality(frame, None)
            return
        self._finish_equality(frame, child_result.data == "TRUE")

    def _fire_equality(self) -> None:
        state = self.state
        if state.q == 0:
            state.pc -= 1
            return
        left_constant = self._constant_word_key(self._word(state.pc + 1))
        right_constant = self._constant_word_key(self._word(state.pc))
        if left_constant is not None and right_constant is not None:
            answer = self._bool_word(left_constant == right_constant)
            state.memory[state.pc] = Word(answer.opcode, answer.data, True)
            state.fsp = state.pc
            state.q -= 1
            state.pc -= 1
            return

        state.q -= 1
        self._push_saved_quantum(state.q)
        frame = _EqualityFrame(result_pc=state.pc, live_fsp=state.fsp)
        self._push_control_entry(frame)
        self._launch_equality_child(
            frame,
            _EqualityTask(state.pc + 1, state.pc, 0, True),
        )

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
            left_word.opcode is MuredOpcode.INT and right_word.opcode is MuredOpcode.INT
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
        # A compacted application may start with an immediate APPLY-class
        # descriptor rather than an APP pointer.  Self-delimiting graph roots
        # such as LAMBDA and STRUCT are closed values even when reached through APP.
        if self._is_linear_application_prefix(root):
            return True
        return root.opcode is MuredOpcode.VAR

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

        argument_address = state.pc - 1
        argument = self._word(argument_address)

        if argument.opcode is MuredOpcode.APP:
            if type(argument.data) is not int or argument.data < 0:
                raise InvalidAddress("Y APP argument requires a graph address")
            state.q -= 1
            state.memory[state.fsp] = Word(MuredOpcode.APP, argument_address, False)
            state.pc = argument.data
            return

        scratch = state.fsp + 1
        frontier = state.free_space
        if scratch >= frontier:
            raise GraphEnvironmentCollision("graph and environment collide")
        if state.c + 1 >= len(state.control_stack):
            raise ControlStackOverflow("μRED control stack overflow")

        state.q -= 1
        state.memory[state.fsp] = Word(MuredOpcode.APP, argument_address, False)
        self._push_control(state.env)
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
            if word.head and word.data == "__EQUAL_STAR__":
                self._run_equality_child()
                return
            if word.head and word.data == "__EQUAL_IF__" and state.argcnt >= 3:
                state.prim = "__EQUAL_IF__"
                state.fire = 1
            if word.head and word.data == "Y":
                self._y(word)
                return
            if (
                word.head
                and word.data in {"CLOCK", "UART-RX"}
                and state.argcnt == 0
                and state.q > 0
            ):
                self._suspend_host_call(word.data)
                return
            if (
                word.head
                and word.data in {"IO-BIND", "IO-THEN"}
                and state.argcnt >= 2
                and state.q > 0
            ):
                state.prim = word.data
                state.fire = 1
            elif word.head and word.data == "IF" and state.argcnt >= 3 and state.q > 0:
                state.prim = "IF"
                state.fire = 1
            arity = 0
        elif word.opcode is MuredOpcode.PRIM_1:
            arity = 1
        elif word.opcode is MuredOpcode.PRIM_2:
            arity = 2
        else:
            raise IllegalTransition("_prim requires a primitive opcode")
        if arity > 0 and word.head and state.argcnt >= arity and state.q > 0:
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
        self._copy_result(Word(MuredOpcode.VAR, self.state.phi - word.data, True))
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
        if redex.opcode is MuredOpcode.EP:
            if type(redex.data) is not int or redex.data < 0:
                raise InvalidAddress("EP requires an environment address")
            target_address = redex.data
            seen: set[int] = set()
            while True:
                if target_address in seen:
                    raise IllegalTransition("cyclic VAR-head EP environment chain")
                seen.add(target_address)
                target = self._word(target_address)
                if target.opcode is not MuredOpcode.EP:
                    break
                if type(target.data) is not int or target.data < 0:
                    raise InvalidAddress("EP requires an environment address")
                target_address = target.data
            if target.opcode is MuredOpcode.UBV:
                if type(target.data) is not int:
                    raise InvalidAddress("UBV requires a binder depth")
                self._copy_result(
                    Word(MuredOpcode.VAR, self.state.phi - target.data, True)
                )
                self.state.pc = self.state.fsp - 1
                self.state.direction = Direction.B
                return
            if target.opcode is MuredOpcode.CLOSURE:
                self.state.pc = target_address
                return
            if self._is_shareable_ep_value(target):
                self._copy_result(
                    Word(target.opcode, target.data, True, target.definition)
                )
                self.state.pc = self.state.fsp - 1
                self.state.direction = Direction.B
                return
            raise IllegalTransition(
                f"VAR-head EP points to unsupported environment value: {target.opcode}"
            )
        if redex.closure_slot or self._is_shareable_ep_value(redex):
            if redex.closure_slot and not self._is_shareable_ep_value(redex):
                raise IllegalTransition(
                    "shared closure slot contains unsupported environment value"
                )
            # RED's VAR-head action loads an immediate environment value into
            # PGDR, marks that register HEAD, and executes the detached value.
            # Do not execute the environment cell in place: the following word
            # is another binding/marker, not part of the executable graph.
            self._copy_result(Word(redex.opcode, redex.data, True, redex.definition))
            self.state.pc = self.state.fsp - 1
            self.state.direction = Direction.B
            return
        self.state.pc = redex_address

    def _relinearize_graph(self, address: int) -> tuple[Word, ...]:
        """Convert a μRED result graph rooted at address into executable words."""

        inline_argument_opcodes = {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }
        atomic_opcodes = inline_argument_opcodes | {MuredOpcode.VAR}
        memory = self.state.memory
        output: list[Word | None] = []
        visiting: set[tuple[int, bool]] = set()
        forwarded_graphs: dict[int, int] = {}

        def source_word(address: int) -> Word:
            if not 0 <= address < len(memory):
                raise InvalidAddress(f"invalid μRED address: {address}")
            word = memory[address]
            if word is None:
                raise InvalidAddress(f"invalid μRED address: {address}")
            return word

        def emit_atomic(word: Word, *, head: bool) -> None:
            output.append(Word(word.opcode, word.data, head, word.definition))

        def emit_pointer_target(address: int) -> int:
            if not 0 <= address < self.working_memory_limit:
                raise InvalidAddress("result graph pointer escapes the working arena")
            existing = forwarded_graphs.get(address)
            if existing is not None:
                return existing
            if (address, True) in visiting:
                raise MuredMachineError("cyclic μRED result graph")
            target = len(output)
            emit_graph(address, head=True)
            forwarded_graphs[address] = target
            return target

        def emit_graph(address: int, *, head: bool) -> None:
            key = (address, head)
            if key in visiting:
                raise MuredMachineError("cyclic μRED result graph")
            visiting.add(key)
            try:
                word = source_word(address)
                if word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR} or (
                    not word.head and word.opcode in inline_argument_opcodes
                ):
                    entries: list[tuple[MuredOpcode, int, int, int | None]] = []
                    cursor = address
                    while True:
                        entry = source_word(cursor)
                        if entry.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR}:
                            if not isinstance(entry.data, int) or entry.data < 0:
                                raise InvalidAddress(
                                    "result application requires a non-negative "
                                    "address/index"
                                )
                            entries.append(
                                (entry.opcode, entry.data, cursor, entry.definition)
                            )
                        elif not entry.head and entry.opcode in inline_argument_opcodes:
                            entries.append(
                                (entry.opcode, cursor, cursor, entry.definition)
                            )
                        else:
                            break
                        cursor += 1

                    slots = len(output)
                    output.extend([None] * len(entries))
                    emit_graph(cursor, head=True)
                    for offset, (
                        opcode,
                        data,
                        source,
                        definition,
                    ) in enumerate(entries):
                        if opcode is MuredOpcode.APP_VAR:
                            output[slots + offset] = Word(
                                MuredOpcode.APP_VAR, data, False, definition
                            )
                            continue
                        if opcode is MuredOpcode.APP:
                            target = emit_pointer_target(data)
                        else:
                            target = len(output)
                            emit_atomic(source_word(source), head=True)
                        output[slots + offset] = Word(
                            MuredOpcode.APP, target, False, definition
                        )
                    return

                if word.opcode is MuredOpcode.RBLOCK:
                    blocks: list[Word] = []
                    cursor = address
                    while source_word(cursor).opcode is MuredOpcode.RBLOCK:
                        blocks.append(source_word(cursor))
                        cursor += 1
                    rup = source_word(cursor)
                    if rup.opcode is not MuredOpcode.RUP or rup.data != len(blocks):
                        raise MuredMachineError("result LETREC requires matching RUP")

                    slots = len(output)
                    output.extend([None] * len(blocks))
                    output.append(Word(MuredOpcode.RUP, len(blocks), False))
                    emit_graph(cursor + 1, head=head)
                    for offset, block in enumerate(blocks):
                        if not isinstance(block.data, int) or block.data < 0:
                            raise InvalidAddress(
                                "result RBLOCK requires a binding address"
                            )
                        if block.data >= self.working_memory_limit:
                            raise InvalidAddress(
                                "result RBLOCK binding escapes the working arena"
                            )
                        name = source_word(block.data)
                        if name.opcode is not MuredOpcode.SYM or not isinstance(
                            name.data, str
                        ):
                            raise MuredMachineError(
                                "result RBLOCK binding requires leading SYM name"
                            )
                        binding_address = len(output)
                        output[slots + offset] = Word(
                            MuredOpcode.RBLOCK,
                            binding_address,
                            False,
                            block.definition,
                        )
                        output.append(
                            Word(MuredOpcode.SYM, name.data, False, name.definition)
                        )
                        emit_graph(block.data + 1, head=True)
                    return

                if word.opcode is MuredOpcode.STRUCT:
                    output.append(
                        Word(MuredOpcode.STRUCT, word.data, False, word.definition)
                    )
                    cursor = address + 1
                    descriptors: list[tuple[Word, int]] = []
                    while True:
                        descriptor = source_word(cursor)
                        if descriptor.opcode in {
                            MuredOpcode.APP,
                            MuredOpcode.APP_VAR,
                        }:
                            if (
                                not isinstance(descriptor.data, int)
                                or descriptor.data < 0
                            ):
                                raise InvalidAddress(
                                    "result STRUCT field requires an address or index"
                                )
                            descriptors.append((descriptor, cursor))
                        elif (
                            not descriptor.head
                            and descriptor.opcode in inline_argument_opcodes
                        ):
                            descriptors.append((descriptor, cursor))
                        else:
                            break
                        cursor += 1
                    selector = source_word(cursor)
                    if selector.opcode is not MuredOpcode.VAR or selector.data != 0:
                        raise MuredMachineError(
                            "result STRUCT requires a VAR 0 selector"
                        )
                    slots = len(output)
                    output.extend([None] * len(descriptors))
                    output.append(Word(MuredOpcode.VAR, 0, head))
                    for offset, (descriptor, source_address) in enumerate(descriptors):
                        if descriptor.opcode is MuredOpcode.APP_VAR:
                            output[slots + offset] = Word(
                                MuredOpcode.APP_VAR,
                                descriptor.data,
                                False,
                                descriptor.definition,
                            )
                            continue
                        if descriptor.opcode is MuredOpcode.APP:
                            assert isinstance(descriptor.data, int)
                            target = emit_pointer_target(descriptor.data)
                        else:
                            target = len(output)
                            emit_atomic(source_word(source_address), head=True)
                        output[slots + offset] = Word(
                            MuredOpcode.APP,
                            target,
                            False,
                            descriptor.definition,
                        )
                    return

                if word.opcode is MuredOpcode.LAMBDA:
                    cursor = address
                    while source_word(cursor).opcode is MuredOpcode.LAMBDA:
                        lambda_word = source_word(cursor)
                        output.append(
                            Word(
                                MuredOpcode.LAMBDA,
                                lambda_word.data,
                                False,
                                lambda_word.definition,
                            )
                        )
                        cursor += 1
                    emit_graph(cursor, head=head)
                    return

                if word.opcode in atomic_opcodes:
                    emit_atomic(word, head=head)
                    return

                raise MuredMachineError(
                    f"cannot relinearize result opcode {word.opcode}"
                )
            finally:
                visiting.remove(key)

        emit_graph(address, head=True)
        if any(word is None for word in output):
            raise MuredMachineError("relinearized μRED graph contains a hole")
        return tuple(word for word in output if word is not None)

    def _value_problem(self, descriptor_address: int) -> tuple[Word, ...]:
        """Snapshot one compact result descriptor as executable μRED words."""
        descriptor = self._word(descriptor_address)
        if descriptor.opcode is MuredOpcode.APP:
            if type(descriptor.data) is not int or descriptor.data < 0:
                raise InvalidAddress("result APP requires an argument address")
            return self._relinearize_graph(descriptor.data)
        if descriptor.opcode is MuredOpcode.APP_VAR:
            if type(descriptor.data) is not int or descriptor.data < 0:
                raise InvalidAddress("result APP_VAR requires a variable index")
            return (
                Word(
                    MuredOpcode.VAR,
                    descriptor.data,
                    True,
                    descriptor.definition,
                ),
            )
        if descriptor.opcode in {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
            MuredOpcode.VAR,
        }:
            return (
                Word(
                    descriptor.opcode,
                    descriptor.data,
                    True,
                    descriptor.definition,
                ),
            )
        return self._relinearize_graph(descriptor_address)

    @staticmethod
    def _relocate_problem_word(word: Word, base: int) -> Word:
        data = word.data
        if word.opcode in {MuredOpcode.APP, MuredOpcode.RBLOCK}:
            if type(data) is not int or data < 0:
                raise InvalidAddress("relocated μRED graph requires a relative address")
            data = base + data
        return Word(word.opcode, data, word.head, word.definition)

    def _write_problem(self, destination: int, words: Sequence[Word]) -> int:
        if not words:
            raise MuredMachineError("μRED value graph must not be empty")
        state = self.state
        frontier = state.free_space
        last_address = destination + len(words) - 1
        if last_address >= frontier:
            raise GraphEnvironmentCollision("graph and environment collide")
        for offset, word in enumerate(words):
            state.memory[destination + offset] = self._relocate_problem_word(
                word, destination
            )
        state.fsp = last_address
        return destination

    def _promote_result_value(self, descriptor_address: int) -> None:
        words = self._value_problem(descriptor_address)
        self._write_problem(descriptor_address, words)

    def _suspend_host_call(
        self,
        name: str,
        *,
        argument_address: int | None = None,
    ) -> None:
        if self.pending_host_call is not None:
            raise IllegalTransition("μRED machine already has a pending host call")
        self.pending_host_call = MuredHostCall(name, argument_address)

    def resume_host_call(self, result: Word) -> MuredMachineState:
        call = self.pending_host_call
        if call is None:
            raise IllegalTransition("μRED machine has no pending host call")
        if result.opcode not in {
            MuredOpcode.INT,
            MuredOpcode.FLOAT,
            MuredOpcode.CHAR,
            MuredOpcode.SYM,
        }:
            raise IllegalTransition("host call result must be an atomic μRED value")
        if self.state.q <= 0:
            raise IllegalTransition("pending host call requires positive quantum")

        state = self.state
        resumed = Word(result.opcode, result.data, True, result.definition)
        if call.argument_address is None:
            self._copy_result(resumed)
            state.q -= 1
            state.pc = state.fsp - 1
            state.direction = Direction.B
        else:
            if state.pc != call.argument_address:
                raise IllegalTransition("pending host call lost its result address")
            state.memory[state.pc] = resumed
            state.fsp = state.pc
            state.q -= 1
            state.pc -= 1

        self.pending_host_call = None
        return state

    def _fire_io_sequence(self, primitive: str) -> None:
        state = self.state
        if state.q == 0:
            state.pc -= 1
            return

        value_slot = state.pc
        value_path = state.env
        continuation_slot = value_slot - 1
        continuation = self._word(continuation_slot)
        continuation_path = (
            self._pop_control() if continuation.opcode is MuredOpcode.APP else None
        )
        if continuation.opcode is not MuredOpcode.APP:
            raise IllegalTransition(f"{primitive} continuation requires APP")
        if type(continuation.data) is not int or continuation.data < 0:
            raise InvalidAddress(f"{primitive} continuation requires a graph address")
        if continuation_path is None:
            raise IllegalTransition(
                f"{primitive} continuation lost its environment path"
            )

        state.q -= 1
        if primitive == "IO-THEN":
            self._record_memory_event(
                "IO_BIND",
                {"primitive": primitive, "value_slot": value_slot},
            )
            state.fsp = continuation_slot - 1
            state.argcnt = 0
            state.env = continuation_path
            state.pc = continuation.data
            state.direction = Direction.F
            return

        value = self._word(value_slot)
        reserved_upper_arena = False
        if not self._is_supported_io_bind_value(value):
            raise IllegalTransition(
                "IO-BIND supports only atomic bound values; structured graph "
                "values require a future graph-owned publication design"
            )
        state.fsp = continuation_slot - 1
        self._push_graph(
            Word(
                value.opcode,
                value.data,
                False,
                value.definition,
                value.closure_slot,
            )
        )
        if value.opcode is MuredOpcode.EP:
            self._push_control(value_path)
        self._record_memory_event(
            "IO_BIND",
            {
                "primitive": primitive,
                "value_slot": value_slot,
                "reserved_upper_arena": reserved_upper_arena,
            },
        )
        state.argcnt = 1
        state.env = continuation_path
        state.pc = continuation.data
        state.direction = Direction.F

    def _relinearize_result_graph(self) -> tuple[Word, ...]:
        """Convert the halted result graph into a fresh μRED problem graph."""
        if not self.state.halted:
            raise MuredMachineError("result graph is available only after halt")
        return self._relinearize_graph(self.state.pc)

    def refresh_quantum(self, quantum: int) -> MuredMachineState:
        """Reset the budget of a live machine after scheduler-visible progress."""
        if quantum < 0:
            raise ValueError("quantum must be non-negative")
        if self.state.halted:
            raise MuredMachineError("cannot refresh quantum after halt")
        if self.pending_host_call is not None:
            raise MuredMachineError(
                "cannot refresh quantum while a host call is pending"
            )
        self.state.q = quantum
        return self.state

    def checkpoint_quantum(self, quantum: int) -> MuredMachineState:
        """Reconstruct a live bounded result, then restart this same machine."""
        if quantum < 0:
            raise ValueError("quantum must be non-negative")
        state = self.state
        if state.halted:
            raise MuredMachineError("cannot checkpoint an already halted machine")
        if self.pending_host_call is not None:
            raise MuredMachineError("cannot checkpoint while a host call is pending")

        # A committed host result is now part of the graph.  Drive the machine
        # through RED2's ordinary q=0 reconstruction path so temporary graph and
        # environment state is discarded without firing another effect.  The
        # resulting bounded graph is then relinearized by recharge_quantum below.
        self._host_checkpoints += 1
        self._record_memory_event(
            "CHECKPOINT",
            {"quantum": quantum, "fsp": state.fsp, "free_space": self._frontier()},
        )
        state.q = 0
        while not state.halted:
            self.step()
            if self.pending_host_call is not None:
                raise IllegalTransition(
                    "zero-quantum checkpoint attempted to dispatch a host effect"
                )
        return self.recharge_quantum(quantum)

    def recharge_quantum(self, quantum: int) -> MuredMachineState:
        """Refill a live exhaustion or restart from a halted bounded result."""
        if quantum < 0:
            raise ValueError("quantum must be non-negative")
        state = self.state
        if not state.halted:
            if self.pending_host_call is not None:
                raise MuredMachineError(
                    "cannot recharge quantum while a host call is pending"
                )
            if state.q != 0:
                raise MuredMachineError(
                    "live quantum can be recharged only after exhaustion"
                )
            state.q = quantum
            return state

        problem = self._relinearize_result_graph()
        stop_address = len(problem)
        if stop_address >= self.working_memory_limit:
            raise GraphEnvironmentCollision("graph and environment collide")

        for address in range(self.working_memory_limit):
            state.memory[address] = None
        state.memory[:stop_address] = problem
        state.memory[stop_address] = Word(MuredOpcode.STOP)
        for index in range(len(state.control_stack)):
            state.control_stack[index] = None

        state.pc = 0
        state.fsp = stop_address
        state.env = self.working_memory_limit
        state.free_space = self.working_memory_limit
        state.c = -1
        state.direction = Direction.F
        state.q = quantum
        state.phi = 0
        state.argcnt = 0
        state.prim = None
        state.fire = 0
        state.s_a = None
        state.s_d = None
        state.halted = False
        self.pending_host_call = None
        self._saved_quantum_depth = 0
        return state

    def _has_saved_quantum(self) -> bool:
        return self._saved_quantum_depth > 0

    def run_until_suspend(self, *, cycle_limit: int = 100_000) -> MuredRunResult:
        """Run until completion, host suspension, or external quantum exhaustion."""
        if cycle_limit < 0:
            raise ValueError("cycle_limit must be non-negative")
        while True:
            if self.pending_host_call is not None:
                return MuredRunResult(MuredStopReason.HOST_CALL, self.pending_host_call)
            if self.state.halted:
                return MuredRunResult(MuredStopReason.COMPLETE)
            if self.state.q == 0 and not self._has_saved_quantum():
                return MuredRunResult(MuredStopReason.QUANTUM_EXHAUSTED)
            if self.state.cycles >= cycle_limit:
                raise CycleLimitExceeded(f"μRED cycle limit reached: {cycle_limit}")
            self.step()

    def run(self, *, cycle_limit: int = 100_000) -> MuredMachineState:
        if cycle_limit < 0:
            raise ValueError("cycle_limit must be non-negative")
        while not self.state.halted and self.pending_host_call is None:
            if self.state.cycles >= cycle_limit:
                raise CycleLimitExceeded(f"μRED cycle limit reached: {cycle_limit}")
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

    def _decompile_ep_value(
        self,
        word: Word,
        scope: tuple[str | None, ...],
        path: frozenset[int],
    ) -> Expr:
        """Project a result EP through its environment without mutating state."""
        if type(word.data) is not int or word.data < 0:
            raise InvalidAddress("result EP requires an environment address")

        target_address = word.data
        seen: set[int] = set()
        while True:
            if target_address in seen:
                raise MuredMachineError("cyclic result EP environment chain")
            seen.add(target_address)
            target = self._word(target_address)
            if target.opcode is MuredOpcode.EP:
                if type(target.data) is not int or target.data < 0:
                    raise InvalidAddress("result EP requires an environment address")
                target_address = target.data
                continue
            break

        if target.opcode is MuredOpcode.CLOSURE:
            code = self._word(target_address + 1)
            if code.opcode is not None or type(code.data) is not int or code.data < 0:
                raise MalformedClosure("CLOSURE requires a following code pointer")
            expr, _ = self._decompile(code.data, scope, path)
            return expr

        if target.opcode is MuredOpcode.UBV:
            if type(target.data) is not int:
                raise InvalidAddress("UBV requires a binder depth")
            index = self.state.phi - target.data
            if index < 0:
                raise InvalidAddress("result EP resolves to an invalid variable index")
            name = scope[index] if index < len(scope) else None
            return Var(self._decompile_var_index(index, scope), name)

        if target.opcode is MuredOpcode.VAR:
            if type(target.data) is not int or target.data < 0:
                raise InvalidAddress("result VAR requires a De Bruijn index")
            name = scope[target.data] if target.data < len(scope) else None
            return Var(self._decompile_var_index(target.data, scope), name)

        if target.opcode is MuredOpcode.INT:
            if type(target.data) is not int:
                raise MuredMachineError("result INT requires an integer value")
            return Integer(target.data)
        if target.opcode is MuredOpcode.FLOAT:
            if type(target.data) is not float:
                raise MuredMachineError("result FLOAT requires a floating-point value")
            return Float(target.data)
        if target.opcode is MuredOpcode.CHAR:
            if type(target.data) is not str or len(target.data) != 1:
                raise MuredMachineError(
                    "result CHAR requires a single-character string"
                )
            return Char(target.data)
        if target.opcode in {
            MuredOpcode.SYM,
            MuredOpcode.PRIM_0,
            MuredOpcode.PRIM_1,
            MuredOpcode.PRIM_2,
        }:
            if type(target.data) is not str or target.data == "":
                raise MuredMachineError("result symbol requires a symbol name")
            return Symbol(target.data)

        raise MuredMachineError(
            f"result EP points to unsupported environment value: {target.opcode}"
        )

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
            MuredOpcode.EP,
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
                    name = scope[argument_data] if argument_data < len(scope) else None
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
                if inline_word.opcode is MuredOpcode.EP:
                    arguments.append(
                        self._decompile_ep_value(inline_word, scope, app_path)
                    )
                elif inline_word.opcode is MuredOpcode.INT:
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
                if field_word.opcode in {MuredOpcode.APP, MuredOpcode.APP_VAR}:
                    if type(field_word.data) is not int or field_word.data < 0:
                        raise InvalidAddress(
                            "result STRUCT field requires an address or index"
                        )
                    field_entries.append((field_word.opcode, field_word.data))
                elif (
                    not field_word.head and field_word.opcode in inline_argument_opcodes
                ):
                    field_entries.append((field_word.opcode, cursor))
                else:
                    break
                struct_path = struct_path | {cursor}
                cursor += 1
            selector = self._word(cursor)
            if selector.opcode is not MuredOpcode.VAR or selector.data != 0:
                raise MuredMachineError(
                    f"result STRUCT requires trailing VAR 0; got {selector} at {cursor}"
                )
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
                if opcode is MuredOpcode.APP:
                    field, field_next = self._decompile(
                        field_data,
                        struct_scope,
                        struct_path,
                    )
                    next_address = max(next_address, field_next)
                    fields.append(field)
                    continue
                inline_word = self._word(field_data)
                if inline_word.opcode is MuredOpcode.EP:
                    fields.append(
                        self._decompile_ep_value(
                            inline_word,
                            struct_scope,
                            struct_path,
                        )
                    )
                elif inline_word.opcode is MuredOpcode.INT:
                    if type(inline_word.data) is not int:
                        raise MuredMachineError("result INT requires an integer value")
                    fields.append(Integer(inline_word.data))
                elif inline_word.opcode is MuredOpcode.FLOAT:
                    if type(inline_word.data) is not float:
                        raise MuredMachineError(
                            "result FLOAT requires a floating-point value"
                        )
                    fields.append(Float(inline_word.data))
                elif inline_word.opcode is MuredOpcode.CHAR:
                    if type(inline_word.data) is not str or len(inline_word.data) != 1:
                        raise MuredMachineError(
                            "result CHAR requires a single-character string"
                        )
                    fields.append(Char(inline_word.data))
                elif inline_word.opcode in {
                    MuredOpcode.SYM,
                    MuredOpcode.PRIM_0,
                    MuredOpcode.PRIM_1,
                    MuredOpcode.PRIM_2,
                }:
                    if type(inline_word.data) is not str or inline_word.data == "":
                        raise MuredMachineError("result symbol requires a symbol name")
                    fields.append(Symbol(inline_word.data))
                else:
                    raise MuredMachineError(
                        f"{inline_word.opcode} is not a valid inline STRUCT field"
                    )
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
                    raise MuredMachineError("result LAMBDA requires a parameter name")
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
                raise MuredMachineError("result FLOAT requires a floating-point value")
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

        if word.opcode is MuredOpcode.EP:
            return self._decompile_ep_value(word, scope, path), address + 1

        raise MuredMachineError(f"{word.opcode} is not valid in a μRED result graph")

    def _word(self, address: int) -> Word:
        if not 0 <= address < len(self.state.memory):
            raise InvalidAddress(f"invalid μRED address: {address}")
        word = self.state.memory[address]
        if word is None:
            raise InvalidAddress(f"uninitialized μRED address: {address}")
        return word

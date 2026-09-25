from dataclasses import dataclass, fields
from struct import pack as struct_pack
from struct import unpack as struct_unpack

from red2.instructions import Instruction, Opcode, encode_instruction
from red2.representation import Direction, MuredOpcode, Word
from abstract_red2_machine.machine import (
    AbstractRED2Machine,
    AbstractRED2MachineState,
    MuredHostCall,
    _EqualityFrame,
    _SavedDefinitionPath,
    _SavedFire,
    _SavedPrim,
    _SavedQuantum,
    _SubgraphFrame,
)
from concrete_red2_machine import abi

VECTOR_QUANTUM = 3

_OPCODE_TO_ID = {
    None: abi.MOP_NONE,
    MuredOpcode.APP: abi.MOP_APP,
    MuredOpcode.APP_VAR: abi.MOP_APP_VAR,
    MuredOpcode.CLOSURE: abi.MOP_CLOSURE,
    MuredOpcode.EP: abi.MOP_EP,
    MuredOpcode.JOIN: abi.MOP_JOIN,
    MuredOpcode.LAMBDA: abi.MOP_LAMBDA,
    MuredOpcode.STOP: abi.MOP_STOP,
    MuredOpcode.INT: abi.MOP_INT,
    MuredOpcode.FLOAT: abi.MOP_FLOAT,
    MuredOpcode.CHAR: abi.MOP_CHAR,
    MuredOpcode.SYM: abi.MOP_SYM,
    MuredOpcode.PRIM_0: abi.MOP_PRIM_0,
    MuredOpcode.PRIM_1: abi.MOP_PRIM_1,
    MuredOpcode.PRIM_2: abi.MOP_PRIM_2,
    MuredOpcode.STRUCT: abi.MOP_STRUCT,
    MuredOpcode.RBLOCK: abi.MOP_RBLOCK,
    MuredOpcode.RUP: abi.MOP_RUP,
    MuredOpcode.RECP: abi.MOP_RECP,
    MuredOpcode.REC: abi.MOP_REC,
    MuredOpcode.UBV: abi.MOP_UBV,
    MuredOpcode.VAR: abi.MOP_VAR,
    MuredOpcode.PNP: abi.MOP_PNP,
}
_ID_TO_OPCODE = {value: key for key, value in _OPCODE_TO_ID.items()}


@dataclass(frozen=True, slots=True)
class StepperVector:
    name: str
    before: int
    after: int


@dataclass(frozen=True, slots=True)
class EncodedStructSelector:
    selector_id: int
    tag_id: int
    offset: int


@dataclass(frozen=True, slots=True)
class EncodedArchitecturalState:
    """Hardware-visible checkpoint; Python-only diagnostics are deliberately absent."""

    memory: tuple[int, ...]
    control_stack: tuple[int, ...]
    pc: int
    fsp: int
    env: int
    c: int
    direction: int
    q: int
    phi: int
    free_space: int
    argcnt: int
    prim_id: int
    fire: int
    s_a: int
    s_d: int
    halted: int
    pending_host_op: int = abi.HOST_NONE
    pending_host_argument: int = 0


@dataclass(frozen=True, slots=True)
class EncodedProgramImage:
    """Processor-neutral compiled RED2 image plus finite semantic metadata."""

    state: EncodedArchitecturalState
    working_memory_limit: int
    struct_selectors: tuple[EncodedStructSelector, ...]


class RED2ABICodec:
    """Host-side load/debug codec for RED2_ABI_V1 finite literal identifiers."""

    def __init__(self) -> None:
        self._literal_to_id: dict[str, int] = {}
        self._id_to_literal: dict[int, str] = {}

    def literal_id(self, value: str) -> int:
        if not value:
            raise ValueError("RED2 ABI literal must not be empty")
        existing = self._literal_to_id.get(value)
        if existing is not None:
            return existing
        literal_id = len(self._literal_to_id) + 1
        if literal_id > abi.LITERAL_ID_MAX:
            raise ValueError("RED2 ABI literal table exhausted")
        self._literal_to_id[value] = literal_id
        self._id_to_literal[literal_id] = value
        return literal_id

    def literal(self, literal_id: int) -> str:
        try:
            return self._id_to_literal[literal_id]
        except KeyError as error:
            raise ValueError(f"unknown RED2 ABI literal id: {literal_id}") from error

    def encode_word(self, word: Word | None) -> int:
        if word is None:
            return abi.pack_word(0, 0, 0, 0, 0, 0, 0, 0)
        try:
            opcode = _OPCODE_TO_ID[word.opcode]
        except KeyError as error:
            raise ValueError(f"unsupported RED2 opcode: {word.opcode!r}") from error

        data_kind = abi.DATA_NONE
        payload = 0
        if word.data is None:
            pass
        elif type(word.data) is int:
            data_kind = abi.DATA_SIGNED
            payload = abi.signed_to_payload(word.data)
        elif type(word.data) is float:
            data_kind = abi.DATA_FLOAT64
            payload = struct_unpack(">Q", struct_pack(">d", word.data))[0]
        elif type(word.data) is str:
            data_kind = abi.DATA_LITERAL_ID
            payload = self.literal_id(word.data)
        else:
            raise ValueError(f"unsupported RED2 word payload: {word.data!r}")

        definition_valid = int(word.definition is not None)
        definition = (
            0 if word.definition is None else abi.require_address(word.definition)
        )
        return abi.pack_word(
            1,
            opcode,
            data_kind,
            payload,
            int(word.head),
            int(word.closure_slot),
            definition_valid,
            definition,
        )

    def decode_word(self, packed: int) -> Word | None:
        valid = abi.word_field(packed, abi.WORD_VALID_SHIFT, 1)
        if not valid:
            if packed != 0:
                raise ValueError("invalid empty RED2 ABI word")
            return None
        opcode_id = abi.word_field(packed, abi.WORD_OPCODE_SHIFT, abi.WORD_OPCODE_BITS)
        try:
            opcode = _ID_TO_OPCODE[opcode_id]
        except KeyError as error:
            raise ValueError(f"unknown RED2 ABI opcode id: {opcode_id}") from error
        kind = abi.word_field(packed, abi.WORD_DATA_KIND_SHIFT, abi.WORD_DATA_KIND_BITS)
        payload = abi.word_field(packed, abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS)
        if kind == abi.DATA_NONE:
            data: int | float | str | None = None
        elif kind == abi.DATA_SIGNED:
            data = abi.payload_to_signed(payload)
        elif kind == abi.DATA_FLOAT64:
            data = struct_unpack(">d", struct_pack(">Q", payload))[0]
        elif kind == abi.DATA_LITERAL_ID:
            data = self.literal(payload)
        else:
            raise ValueError(f"unknown RED2 ABI data kind: {kind}")
        definition_valid = abi.word_field(packed, abi.WORD_DEFINITION_VALID_SHIFT, 1)
        definition_raw = abi.word_field(
            packed, abi.WORD_DEFINITION_SHIFT, abi.WORD_DEFINITION_BITS
        )
        if not definition_valid and definition_raw:
            raise ValueError("definition bits present without validity flag")
        definition = definition_raw if definition_valid else None
        return Word(
            opcode,
            data,
            bool(abi.word_field(packed, abi.WORD_HEAD_SHIFT, 1)),
            definition,
            bool(abi.word_field(packed, abi.WORD_CLOSURE_SLOT_SHIFT, 1)),
        )

    def encode_control_entry(self, entry: object) -> int:
        if entry is None:
            return abi.pack_control_entry(abi.CONTROL_EMPTY, 0, 0, 0, 0)
        if type(entry) is int:
            return abi.pack_control_entry(
                abi.CONTROL_ADDRESS, abi.require_frontier(entry), 0, 0, 0
            )
        if isinstance(entry, _SavedPrim):
            return abi.pack_control_entry(
                abi.CONTROL_SAVED_PRIM, self.literal_id(entry.value), 0, 0, 0
            )
        if isinstance(entry, _SavedFire):
            return abi.pack_control_entry(
                abi.CONTROL_SAVED_FIRE,
                abi.require_unsigned(entry.value, abi.COUNTER_BITS),
                0,
                0,
                0,
            )
        if isinstance(entry, _SavedQuantum):
            return abi.pack_control_entry(
                abi.CONTROL_SAVED_QUANTUM,
                abi.require_unsigned(entry.value, abi.COUNTER_BITS),
                0,
                0,
                0,
            )
        if isinstance(entry, _SavedDefinitionPath):
            return abi.pack_control_entry(
                abi.CONTROL_SAVED_DEFINITION_PATH,
                abi.require_frontier(entry.value),
                0,
                0,
                0,
            )
        if isinstance(entry, _SubgraphFrame):
            prim_id = 0 if entry.prim is None else self.literal_id(entry.prim)
            return abi.pack_control_entry(
                abi.CONTROL_SUBGRAPH,
                abi.require_frontier(entry.env),
                abi.require_frontier(entry.free_space),
                prim_id,
                abi.require_unsigned(entry.fire, abi.COUNTER_BITS),
            )
        if isinstance(entry, _EqualityFrame):
            return abi.pack_control_entry(
                abi.CONTROL_EQUALITY,
                abi.require_address(entry.result_pc),
                abi.require_address(entry.live_fsp),
                0,
                0,
            )
        raise ValueError(f"unsupported RED2 control entry: {entry!r}")

    def decode_control_entry(self, packed: int) -> object:
        tag = abi.control_tag(packed)
        a = abi.control_field(packed, 0)
        b = abi.control_field(packed, 1)
        c = abi.control_field(packed, 2)
        d = abi.control_field(packed, 3)
        if tag == abi.CONTROL_EMPTY:
            if a or b or c or d:
                raise ValueError("malformed empty RED2 control entry")
            return None
        if tag == abi.CONTROL_ADDRESS:
            return a
        if tag == abi.CONTROL_SAVED_PRIM:
            return _SavedPrim(self.literal(a))
        if tag == abi.CONTROL_SAVED_FIRE:
            return _SavedFire(a)
        if tag == abi.CONTROL_SAVED_QUANTUM:
            return _SavedQuantum(a)
        if tag == abi.CONTROL_SAVED_DEFINITION_PATH:
            return _SavedDefinitionPath(a)
        if tag == abi.CONTROL_SUBGRAPH:
            return _SubgraphFrame(a, b, None if c == 0 else self.literal(c), d)
        if tag == abi.CONTROL_EQUALITY:
            return _EqualityFrame(a, b)
        raise ValueError(f"unknown RED2 control tag: {tag}")

    def encode_state(
        self,
        state: AbstractRED2MachineState,
        pending_host_call: MuredHostCall | None = None,
    ) -> EncodedArchitecturalState:
        pc = abi.require_address(state.pc)
        fsp = abi.require_address(state.fsp)
        env = abi.require_frontier(state.env)
        free_space = abi.require_frontier(state.free_space)
        if not -1 <= state.c < len(state.control_stack):
            raise ValueError("RED2 control pointer outside encoded stack")
        if state.argcnt < -1:
            raise ValueError("RED2 argcnt outside architectural range")
        q = abi.require_unsigned(state.q, abi.COUNTER_BITS)
        phi = abi.require_unsigned(state.phi, abi.COUNTER_BITS)
        fire = abi.require_unsigned(state.fire, abi.COUNTER_BITS)
        argcnt = state.argcnt + 1
        abi.require_unsigned(argcnt, abi.COUNTER_BITS)
        prim_id = 0 if state.prim is None else self.literal_id(state.prim)
        pending_op = abi.HOST_NONE
        pending_argument = 0
        if pending_host_call is not None:
            pending_op = {
                "CLOCK": abi.HOST_CLOCK,
                "UART-RX": abi.HOST_UART_RX,
                "UART-TX": abi.HOST_UART_TX,
                "UART-TX-BYTES": abi.HOST_UART_TX_BYTES,
            }.get(pending_host_call.name, -1)
            if pending_op < 0:
                raise ValueError(
                    f"unsupported RED2 host call: {pending_host_call.name}"
                )
            argument = (
                -1
                if pending_host_call.argument_address is None
                else pending_host_call.argument_address
            )
            pending_argument = abi.encode_optional_address(argument)
        return EncodedArchitecturalState(
            memory=tuple(self.encode_word(word) for word in state.memory),
            control_stack=tuple(
                self.encode_control_entry(entry) for entry in state.control_stack
            ),
            pc=pc,
            fsp=fsp,
            env=env,
            c=state.c + 1,
            direction=(
                abi.DIRECTION_FORWARD
                if state.direction is Direction.F
                else abi.DIRECTION_REVERSE
            ),
            q=q,
            phi=phi,
            free_space=free_space,
            argcnt=argcnt,
            prim_id=prim_id,
            fire=fire,
            s_a=abi.encode_optional_address(-1 if state.s_a is None else state.s_a),
            s_d=abi.encode_optional_address(-1 if state.s_d is None else state.s_d),
            halted=int(state.halted),
            pending_host_op=pending_op,
            pending_host_argument=pending_argument,
        )

    def encode_program(self, machine: AbstractRED2Machine) -> EncodedProgramImage:
        """Encode one already-loaded μRED machine without re-evaluating its source."""
        effective_selectors = dict(machine.struct_selectors)
        # These two selectors are built directly into AbstractRED2Machine and take
        # precedence over the extensible selector table.
        effective_selectors["CAR"] = ("PAIR", 2)
        effective_selectors["CDR"] = ("PAIR", 1)
        selectors = tuple(
            EncodedStructSelector(
                self.literal_id(name),
                self.literal_id(tag),
                abi.require_unsigned(offset, abi.COUNTER_BITS),
            )
            for name, (tag, offset) in sorted(effective_selectors.items())
        )
        return EncodedProgramImage(
            state=self.encode_state(machine.state, machine.pending_host_call),
            working_memory_limit=abi.require_frontier(machine.working_memory_limit),
            struct_selectors=selectors,
        )

    def decode_state(self, encoded: EncodedArchitecturalState) -> AbstractRED2MachineState:
        direction = {
            abi.DIRECTION_FORWARD: Direction.F,
            abi.DIRECTION_REVERSE: Direction.B,
        }.get(encoded.direction)
        if direction is None:
            raise ValueError("unknown RED2 direction encoding")
        if encoded.prim_id < 0 or encoded.prim_id > abi.LITERAL_ID_MAX:
            raise ValueError("primitive id outside RED2 ABI range")
        prim = None if encoded.prim_id == 0 else self.literal(encoded.prim_id)
        return AbstractRED2MachineState(
            memory=[self.decode_word(word) for word in encoded.memory],
            control_stack=[
                _decode_control_entry_typed(self, entry)
                for entry in encoded.control_stack
            ],
            pc=abi.require_address(encoded.pc),
            fsp=abi.require_address(encoded.fsp),
            env=abi.require_frontier(encoded.env),
            c=encoded.c - 1,
            direction=direction,
            q=abi.require_unsigned(encoded.q, abi.COUNTER_BITS),
            phi=abi.require_unsigned(encoded.phi, abi.COUNTER_BITS),
            free_space=abi.require_frontier(encoded.free_space),
            argcnt=encoded.argcnt - 1,
            prim=prim,
            fire=abi.require_unsigned(encoded.fire, abi.COUNTER_BITS),
            s_a=(
                None
                if abi.decode_optional_address(encoded.s_a) == -1
                else abi.decode_optional_address(encoded.s_a)
            ),
            s_d=(
                None
                if abi.decode_optional_address(encoded.s_d) == -1
                else abi.decode_optional_address(encoded.s_d)
            ),
            halted=bool(encoded.halted),
            cycles=0,
        )


def architectural_state_fields() -> tuple[str, ...]:
    return tuple(field.name for field in fields(EncodedArchitecturalState))


def _decode_control_entry_typed(
    codec: RED2ABICodec, packed: int
) -> (
    int
    | _SavedPrim
    | _SavedFire
    | _SavedQuantum
    | _SavedDefinitionPath
    | _SubgraphFrame
    | _EqualityFrame
    | None
):
    value = codec.decode_control_entry(packed)
    if value is None or type(value) is int or isinstance(
        value,
        (
            _SavedPrim,
            _SavedFire,
            _SavedQuantum,
            _SavedDefinitionPath,
            _SubgraphFrame,
            _EqualityFrame,
        ),
    ):
        return value
    raise ValueError("decoded unsupported RED2 control entry")


def emit_stepper_vectors() -> list[StepperVector]:
    """Emit retained legacy word-level golden vectors for frontend smoke tests."""
    instructions = (
        ("int_head", Instruction(Opcode.INT, 42, head=True)),
        ("int_non_head", Instruction(Opcode.INT, 42, head=False)),
        ("app", Instruction(Opcode.APP, 7, head=False)),
        ("lambda", Instruction(Opcode.LAMBDA, 1, head=True)),
        ("stop", Instruction(Opcode.STOP, 0, head=True)),
    )
    return [
        StepperVector(
            name,
            before := encode_instruction(instruction),
            abi.red2_step_word(before, VECTOR_QUANTUM, abi.DIRECTION_FORWARD),
        )
        for name, instruction in instructions
    ]

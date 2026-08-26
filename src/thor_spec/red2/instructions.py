from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum, auto


class Opcode(IntEnum):
    APP = 0
    LAMBDA = auto()
    VAR = auto()
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
    JOIN = auto()
    CLOSURE = auto()
    UBV = auto()
    PNP = auto()
    REC = auto()


InstructionData = int | str | float | None


@dataclass(frozen=True, slots=True)
class Instruction:
    opcode: Opcode
    data: InstructionData = None
    head: bool = False


@dataclass(frozen=True, slots=True)
class ProgramImage:
    instructions: tuple[Instruction, ...]
    entry: int
    symbol_table: Mapping[str, int]


HEAD_SHIFT = 31
OPCODE_SHIFT = 24
DATA_MASK = (1 << OPCODE_SHIFT) - 1
OPCODE_MASK = (1 << 7) - 1
MAX_DATA = DATA_MASK

# Prototype encoding layout:
#   bit 31      : head flag
#   bits 24..30 : unsigned opcode number
#   bits 0..23  : unsigned data field
# String and float payloads are represented by stable process-local IDs in the
# 24-bit data field. Integer payloads are stored directly.
_LITERAL_IDS: dict[str | float, int] = {}
_ID_LITERALS: dict[int, str | float] = {}
_NEXT_LITERAL_ID = 1


def encode_instruction(inst: Instruction) -> int:
    """Encode one instruction into the prototype 32-bit RED2 word layout."""
    opcode_value = int(inst.opcode)
    if opcode_value > OPCODE_MASK:
        msg = f"opcode {inst.opcode!r} does not fit in 7 bits"
        raise ValueError(msg)
    data = _encode_data(inst.data)
    return (int(inst.head) << HEAD_SHIFT) | (opcode_value << OPCODE_SHIFT) | data


def decode_instruction(word: int) -> Instruction:
    """Decode a prototype 32-bit RED2 word into an instruction."""
    if word < 0 or word > 0xFFFF_FFFF:
        msg = f"instruction word out of 32-bit range: {word}"
        raise ValueError(msg)
    head = bool((word >> HEAD_SHIFT) & 1)
    opcode_value = (word >> OPCODE_SHIFT) & OPCODE_MASK
    data_field = word & DATA_MASK
    try:
        opcode = Opcode(opcode_value)
    except ValueError as error:
        msg = f"unknown opcode value: {opcode_value}"
        raise ValueError(msg) from error
    return Instruction(opcode, _decode_data(opcode, data_field), head)


def _encode_data(data: InstructionData) -> int:
    if data is None:
        return 0
    if isinstance(data, int):
        if data < 0 or data > MAX_DATA:
            msg = f"integer instruction data out of 24-bit range: {data}"
            raise ValueError(msg)
        return data
    if isinstance(data, str | float):
        return _literal_id(data)
    msg = f"unencodable instruction data: {data!r}"
    raise ValueError(msg)


def _literal_id(value: str | float) -> int:
    global _NEXT_LITERAL_ID
    existing = _LITERAL_IDS.get(value)
    if existing is not None:
        return existing
    if _NEXT_LITERAL_ID > MAX_DATA:
        msg = "instruction literal table exhausted"
        raise ValueError(msg)
    literal_id = _NEXT_LITERAL_ID
    _NEXT_LITERAL_ID += 1
    _LITERAL_IDS[value] = literal_id
    _ID_LITERALS[literal_id] = value
    return literal_id


def _decode_data(opcode: Opcode, data_field: int) -> InstructionData:
    if opcode in _STRING_DATA_OPCODES or opcode is Opcode.FLOAT:
        literal = _ID_LITERALS.get(data_field)
        if literal is not None:
            return literal
    return data_field


_STRING_DATA_OPCODES = frozenset(
    {
        Opcode.LAMBDA,
        Opcode.CHAR,
        Opcode.SYM,
        Opcode.PRIM_0,
        Opcode.PRIM_1,
        Opcode.PRIM_2,
        Opcode.STRUCT,
    }
)

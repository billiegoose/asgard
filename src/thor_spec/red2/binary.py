from __future__ import annotations

from dataclasses import dataclass
from struct import calcsize, pack, unpack_from
from zlib import crc32

from thor_spec.red2.instructions import (
    Instruction,
    InstructionData,
    Opcode,
    ProgramImage,
)

MAGIC = b"RED2"
VERSION = 1
_HEADER = "<4sHHIIIII8s"
_HEADER_SIZE = calcsize(_HEADER)
_CHECKSUM_SIZE = 4
_KIND_INT = 0
_KIND_STRING = 1
_KIND_FLOAT = 2
_KIND_NONE = 3
_LITERAL_STRING = 1
_LITERAL_FLOAT = 2


class Red2BinaryError(ValueError):
    """Raised when RED2 bytecode cannot be decoded."""


@dataclass(frozen=True, slots=True)
class _LiteralTables:
    values: tuple[str | float, ...]
    ids: dict[str | float, int]


def encode_program_image(image: ProgramImage) -> bytes:
    """Encode a RED2 program image as deterministic `.red2` bytecode."""
    literals = _collect_literals(image)
    instruction_bytes = b"".join(
        _encode_instruction(inst, literals.ids) for inst in image.instructions
    )
    literal_bytes = _encode_literals(literals.values)
    metadata_bytes = _encode_metadata(image.metadata)
    body = pack(
        _HEADER,
        MAGIC,
        VERSION,
        0,
        image.entry,
        len(image.instructions),
        len(literals.values),
        len(image.metadata),
        len(metadata_bytes),
        b"\x00" * 8,
    )
    body += instruction_bytes
    body += literal_bytes
    body += metadata_bytes
    return body + pack("<I", crc32(body) & 0xFFFF_FFFF)


def decode_program_image(data: bytes) -> ProgramImage:
    """Decode deterministic `.red2` bytecode into a RED2 program image."""
    if len(data) < _HEADER_SIZE + _CHECKSUM_SIZE:
        msg = "RED2 bytecode too short"
        raise Red2BinaryError(msg)
    body = data[: -_CHECKSUM_SIZE]
    (
        magic,
        version,
        _flags,
        entry,
        word_count,
        literal_count,
        meta_count,
        _meta_size,
        _reserved,
    ) = unpack_from(_HEADER, body, 0)
    if magic != MAGIC:
        msg = "bad RED2 magic"
        raise Red2BinaryError(msg)
    if version != VERSION:
        msg = f"unsupported RED2 bytecode version: {version}"
        raise Red2BinaryError(msg)
    expected_crc = unpack_from("<I", data, len(data) - _CHECKSUM_SIZE)[0]
    actual_crc = crc32(body) & 0xFFFF_FFFF
    if actual_crc != expected_crc:
        msg = "RED2 bytecode checksum mismatch"
        raise Red2BinaryError(msg)
    offset = _HEADER_SIZE
    instructions: list[Instruction] = []
    raw_words: list[tuple[Opcode, int, bool, int]] = []
    for _ in range(word_count):
        opcode_value, flags, kind, data_field = _read("<BBHI", body, offset)
        offset += calcsize("<BBHI")
        try:
            opcode = Opcode(opcode_value)
        except ValueError as error:
            msg = f"unknown opcode value: {opcode_value}"
            raise Red2BinaryError(msg) from error
        raw_words.append((opcode, kind, bool(flags & 1), data_field))
    literals, offset = _decode_literals(body, offset, literal_count)
    for opcode, kind, head, data_field in raw_words:
        instructions.append(
            Instruction(opcode, _decode_data(kind, data_field, literals), head)
        )
    metadata, offset = _decode_metadata(body, offset, meta_count)
    if offset != len(body):
        msg = "RED2 bytecode has trailing or malformed section data"
        raise Red2BinaryError(msg)
    return ProgramImage(tuple(instructions), entry, {}, metadata)


def _collect_literals(image: ProgramImage) -> _LiteralTables:
    values: list[str | float] = []
    ids: dict[str | float, int] = {}
    for inst in image.instructions:
        if isinstance(inst.data, str | float) and inst.data not in ids:
            ids[inst.data] = len(values)
            values.append(inst.data)
    for key, value in sorted(image.metadata.items()):
        for item in (key, *value):
            if item not in ids:
                ids[item] = len(values)
                values.append(item)
    return _LiteralTables(tuple(values), ids)


def _encode_instruction(
    inst: Instruction,
    literal_ids: dict[str | float, int],
) -> bytes:
    kind: int
    data: int
    if inst.data is None:
        kind = _KIND_NONE
        data = 0
    elif isinstance(inst.data, int):
        kind = _KIND_INT
        data = inst.data & 0xFFFF_FFFF
    elif isinstance(inst.data, str | float):
        kind = _KIND_STRING if isinstance(inst.data, str) else _KIND_FLOAT
        data = literal_ids[inst.data]
    else:
        msg = f"unencodable instruction data: {inst.data!r}"
        raise ValueError(msg)
    return pack("<BBHI", int(inst.opcode), int(inst.head), kind, data)


def _decode_data(
    kind: int,
    data_field: int,
    literals: tuple[str | float, ...],
) -> InstructionData:
    if kind == _KIND_NONE:
        return None
    if kind == _KIND_INT:
        return data_field if data_field < 0x8000_0000 else data_field - 0x1_0000_0000
    if kind in {_KIND_STRING, _KIND_FLOAT}:
        try:
            return literals[data_field]
        except IndexError as error:
            msg = f"literal index out of range: {data_field}"
            raise Red2BinaryError(msg) from error
    msg = f"unknown instruction data kind: {kind}"
    raise Red2BinaryError(msg)


def _encode_literals(literals: tuple[str | float, ...]) -> bytes:
    out = bytearray()
    for literal in literals:
        if isinstance(literal, str):
            data = literal.encode("utf-8")
            out += pack("<BI", _LITERAL_STRING, len(data))
            out += data
        else:
            out += pack("<BI", _LITERAL_FLOAT, 8)
            out += pack("<d", literal)
    return bytes(out)


def _decode_literals(
    body: bytes,
    offset: int,
    count: int,
) -> tuple[tuple[str | float, ...], int]:
    literals: list[str | float] = []
    for _ in range(count):
        kind, length = _read("<BI", body, offset)
        offset += calcsize("<BI")
        payload = body[offset : offset + length]
        if len(payload) != length:
            msg = "truncated literal payload"
            raise Red2BinaryError(msg)
        offset += length
        if kind == _LITERAL_STRING:
            literals.append(payload.decode("utf-8"))
        elif kind == _LITERAL_FLOAT and length == 8:
            literals.append(unpack_from("<d", payload, 0)[0])
        else:
            msg = f"unknown literal kind: {kind}"
            raise Red2BinaryError(msg)
    return tuple(literals), offset


def _encode_metadata(metadata: object) -> bytes:
    if not isinstance(metadata, dict):
        return b""
    out = bytearray()
    for key in sorted(metadata):
        value = metadata[key]
        if not isinstance(key, str) or not isinstance(value, tuple):
            continue
        key_bytes = key.encode("utf-8")
        out += pack("<HH", len(key_bytes), len(value))
        out += key_bytes
        for item in value:
            item_bytes = str(item).encode("utf-8")
            out += pack("<H", len(item_bytes))
            out += item_bytes
    return bytes(out)


def _decode_metadata(
    body: bytes,
    offset: int,
    count: int,
) -> tuple[dict[str, tuple[str, ...]], int]:
    metadata: dict[str, tuple[str, ...]] = {}
    for _ in range(count):
        key_len, value_count = _read("<HH", body, offset)
        offset += calcsize("<HH")
        key = body[offset : offset + key_len].decode("utf-8")
        offset += key_len
        values: list[str] = []
        for _ in range(value_count):
            item_len = _read("<H", body, offset)[0]
            offset += calcsize("<H")
            values.append(body[offset : offset + item_len].decode("utf-8"))
            offset += item_len
        metadata[key] = tuple(values)
    return metadata, offset


def _read(fmt: str, data: bytes, offset: int) -> tuple[int, ...]:
    size = calcsize(fmt)
    if offset + size > len(data):
        msg = "truncated RED2 bytecode"
        raise Red2BinaryError(msg)
    return unpack_from(fmt, data, offset)

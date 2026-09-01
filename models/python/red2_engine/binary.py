from dataclasses import dataclass
from struct import calcsize, pack, unpack_from
from zlib import crc32

from red2_engine.instructions import (
    DefinitionImage,
    Instruction,
    InstructionData,
    Opcode,
    ProgramImage,
)

MAGIC = b"RED2"
VERSION = 2
_HEADER = "<4sHHIIIII8s"
_HEADER_SIZE = calcsize(_HEADER)
_CHECKSUM_SIZE = 4
_INSTRUCTION = "<BBHI"
_INSTRUCTION_SIZE = calcsize(_INSTRUCTION)
_PROGRAM = "<IIII"
_PROGRAM_SIZE = calcsize(_PROGRAM)
_SENTINEL_NAME = 0xFFFF_FFFF
_KIND_INT = 0
_KIND_STRING = 1
_KIND_FLOAT = 2
_KIND_NONE = 3
_LITERAL_STRING = 1
_LITERAL_FLOAT = 2


class Red2BinaryError(ValueError):
    """Raised when RED2 bytecode cannot be decoded."""


@dataclass(frozen=True, slots=True)
class Red2Bundle:
    """A self-contained RED2 bytecode bundle."""

    entry: ProgramImage
    definitions: DefinitionImage


@dataclass(frozen=True, slots=True)
class _ProgramRecord:
    name: str | None
    image: ProgramImage


@dataclass(frozen=True, slots=True)
class _RawProgramRecord:
    name_index: int
    entry: int
    raw_words: tuple[tuple[Opcode, int, bool, int], ...]
    metadata: dict[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class _LiteralTables:
    values: tuple[str | float, ...]
    ids: dict[str | float, int]


def encode_program_image(image: ProgramImage) -> bytes:
    """Encode one RED2 program image as deterministic `.red2` bytecode."""
    return encode_bundle(image)


def decode_program_image(data: bytes) -> ProgramImage:
    """Decode a single-entry deterministic `.red2` bytecode image."""
    return decode_bundle(data).entry


def encode_bundle(
    entry: ProgramImage,
    definitions: DefinitionImage | None = None,
) -> bytes:
    """Encode a self-contained RED2 bundle as deterministic `.red2` bytecode."""
    records = [_ProgramRecord(None, entry)]
    if definitions is not None:
        records.extend(
            _ProgramRecord(name, definitions.programs[name])
            for name in sorted(definitions.programs)
        )
    literals = _collect_literals(tuple(records))
    program_bytes = b"".join(
        _encode_program(record, literals.ids) for record in records
    )
    literal_bytes = _encode_literals(literals.values)
    body = pack(
        _HEADER,
        MAGIC,
        VERSION,
        0,
        0,
        len(records),
        len(literals.values),
        0,
        0,
        b"\x00" * 8,
    )
    body += program_bytes
    body += literal_bytes
    return body + pack("<I", crc32(body) & 0xFFFF_FFFF)


def decode_bundle(data: bytes) -> Red2Bundle:
    """Decode deterministic `.red2` bytecode into a self-contained bundle."""
    if len(data) < _HEADER_SIZE + _CHECKSUM_SIZE:
        msg = "RED2 bytecode too short"
        raise Red2BinaryError(msg)
    body = data[: -_CHECKSUM_SIZE]
    (
        magic,
        version,
        _flags,
        entry_index,
        program_count,
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
    if meta_count != 0:
        msg = "global metadata records are reserved in RED2 v2"
        raise Red2BinaryError(msg)

    offset = _HEADER_SIZE
    raw_programs: list[_RawProgramRecord] = []
    for _ in range(program_count):
        raw_program, offset = _decode_program_header_and_body(body, offset)
        raw_programs.append(raw_program)

    literals, offset = _decode_literals(body, offset, literal_count)
    if offset != len(body):
        msg = "RED2 bytecode has trailing or malformed section data"
        raise Red2BinaryError(msg)
    if entry_index >= len(raw_programs):
        msg = f"entry program index out of range: {entry_index}"
        raise Red2BinaryError(msg)

    programs: list[_ProgramRecord] = []
    for raw_program in raw_programs:
        name = _decode_program_name(raw_program.name_index, literals)
        instructions = tuple(
            Instruction(opcode, _decode_data(kind, data_field, literals), head)
            for opcode, kind, head, data_field in raw_program.raw_words
        )
        programs.append(
            _ProgramRecord(
                name,
                ProgramImage(instructions, raw_program.entry, {}, raw_program.metadata),
            )
        )

    entry = programs[entry_index].image
    definitions = DefinitionImage(
        {
            record.name: record.image
            for index, record in enumerate(programs)
            if index != entry_index and record.name is not None
        }
    )
    return Red2Bundle(entry, definitions)


def _collect_literals(records: tuple[_ProgramRecord, ...]) -> _LiteralTables:
    values: list[str | float] = []
    ids: dict[str | float, int] = {}
    for record in records:
        if record.name is not None and record.name not in ids:
            ids[record.name] = len(values)
            values.append(record.name)
        for inst in record.image.instructions:
            if isinstance(inst.data, str | float) and inst.data not in ids:
                ids[inst.data] = len(values)
                values.append(inst.data)
    return _LiteralTables(tuple(values), ids)


def _encode_program(
    record: _ProgramRecord,
    literal_ids: dict[str | float, int],
) -> bytes:
    name_index = _SENTINEL_NAME if record.name is None else literal_ids[record.name]
    metadata_bytes = _encode_metadata(record.image.metadata)
    out = bytearray(
        pack(
            _PROGRAM,
            name_index,
            record.image.entry,
            len(record.image.instructions),
            len(record.image.metadata),
        )
    )
    out += b"".join(
        _encode_instruction(inst, literal_ids) for inst in record.image.instructions
    )
    out += metadata_bytes
    return bytes(out)


def _decode_program_header_and_body(
    body: bytes,
    offset: int,
) -> tuple[_RawProgramRecord, int]:
    name_index, entry, word_count, meta_count = _read(_PROGRAM, body, offset)
    offset += _PROGRAM_SIZE
    raw_words: list[tuple[Opcode, int, bool, int]] = []
    for _ in range(word_count):
        opcode_value, flags, kind, data_field = _read(_INSTRUCTION, body, offset)
        offset += _INSTRUCTION_SIZE
        try:
            opcode = Opcode(opcode_value)
        except ValueError as error:
            msg = f"unknown opcode value: {opcode_value}"
            raise Red2BinaryError(msg) from error
        raw_words.append((opcode, kind, bool(flags & 1), data_field))
    metadata, offset = _decode_metadata(body, offset, meta_count)
    return _RawProgramRecord(name_index, entry, tuple(raw_words), metadata), offset


def _decode_program_name(index: int, literals: tuple[str | float, ...]) -> str | None:
    if index == _SENTINEL_NAME:
        return None
    try:
        literal = literals[index]
    except IndexError as error:
        msg = f"program name literal index out of range: {index}"
        raise Red2BinaryError(msg) from error
    if not isinstance(literal, str):
        msg = f"program name literal is not a string: {index}"
        raise Red2BinaryError(msg)
    return literal


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
    return pack(_INSTRUCTION, int(inst.opcode), int(inst.head), kind, data)


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
            literal = literals[data_field]
        except IndexError as error:
            msg = f"literal index out of range: {data_field}"
            raise Red2BinaryError(msg) from error
        if kind == _KIND_STRING and not isinstance(literal, str):
            msg = f"literal index does not reference a string: {data_field}"
            raise Red2BinaryError(msg)
        if kind == _KIND_FLOAT and not isinstance(literal, float):
            msg = f"literal index does not reference a float: {data_field}"
            raise Red2BinaryError(msg)
        return literal
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
        payload = body[offset : offset + key_len]
        if len(payload) != key_len:
            msg = "truncated metadata key"
            raise Red2BinaryError(msg)
        key = payload.decode("utf-8")
        offset += key_len
        values: list[str] = []
        for _ in range(value_count):
            item_len = _read("<H", body, offset)[0]
            offset += calcsize("<H")
            payload = body[offset : offset + item_len]
            if len(payload) != item_len:
                msg = "truncated metadata value"
                raise Red2BinaryError(msg)
            values.append(payload.decode("utf-8"))
            offset += item_len
        metadata[key] = tuple(values)
    return metadata, offset


def _read(fmt: str, data: bytes, offset: int) -> tuple[int, ...]:
    size = calcsize(fmt)
    if offset + size > len(data):
        msg = "truncated RED2 bytecode"
        raise Red2BinaryError(msg)
    return unpack_from(fmt, data, offset)

from red2_engine.binary import (
    MAGIC,
    Red2BinaryError,
    decode_bundle,
    decode_program_image,
    encode_bundle,
    encode_program_image,
)
from thor_compile.red2 import compile_definitions, compile_expr
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_expr, parse_program


def test_red2_binary_starts_with_magic_and_version_2() -> None:
    data = encode_program_image(compile_expr(parse_expr("(+ 2 3)")))

    assert data[:4] == MAGIC
    assert data[4:6] == b"\x02\x00"


def test_red2_binary_encoding_is_deterministic() -> None:
    image = compile_expr(parse_expr("((LAMBDA (X) (+ X 1)) 41)"))

    assert encode_program_image(image) == encode_program_image(image)
    left = encode_program_image(compile_expr(parse_expr("(+ 2 3)")))
    right = encode_program_image(compile_expr(parse_expr("(+ 2 3)")))
    assert left == right


def test_red2_binary_program_image_round_trip_preserves_bytecode() -> None:
    image = compile_expr(parse_expr("((LAMBDA (X) (+ X 1)) 41)"))

    decoded = decode_program_image(encode_program_image(image))

    assert decoded.instructions == image.instructions
    assert decoded.entry == image.entry
    assert decoded.metadata == image.metadata


def test_red2_binary_bundle_round_trip_preserves_definitions() -> None:
    program = normalize_program(parse_program("inc == (lambda (x) (+ x 1))\n(inc 41)"))
    definitions = {
        form.name: form.expr for form in program.forms if isinstance(form, Definition)
    }
    entry: Expr | None = None
    for form in program.forms:
        if not isinstance(form, Definition | StructDef):
            entry = form
    assert entry is not None

    entry_image = compile_expr(entry)
    definition_image = compile_definitions(definitions)
    decoded = decode_bundle(encode_bundle(entry_image, definition_image))

    assert decoded.entry.instructions == entry_image.instructions
    assert decoded.entry.entry == entry_image.entry
    assert decoded.entry.metadata == entry_image.metadata
    assert tuple(decoded.definitions.programs) == ("inc",)
    decoded_inc = decoded.definitions.programs["inc"]
    original_inc = definition_image.programs["inc"]
    assert decoded_inc.instructions == original_inc.instructions
    assert decoded_inc.entry == original_inc.entry
    assert decoded_inc.metadata == original_inc.metadata


def test_red2_binary_rejects_bad_magic() -> None:
    data = bytearray(encode_program_image(compile_expr(parse_expr("(+ 2 3)"))))
    data[:4] = b"NOPE"

    try:
        decode_program_image(bytes(data))
    except Red2BinaryError as error:
        assert "bad RED2 magic" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected Red2BinaryError")


def test_red2_binary_rejects_bad_checksum() -> None:
    data = bytearray(encode_program_image(compile_expr(parse_expr("(+ 2 3)"))))
    data[-1] ^= 0xFF

    try:
        decode_program_image(bytes(data))
    except Red2BinaryError as error:
        assert "checksum" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected Red2BinaryError")

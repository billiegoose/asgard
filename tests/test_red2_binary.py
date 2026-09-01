from red2_engine.binary import (
    MAGIC,
    Red2BinaryError,
    decode_bundle,
    decode_program_image,
    encode_bundle,
    encode_program_image,
)
from red2_engine.machine import Red2Machine
from thor_compile.red2 import compile_definitions, compile_expr
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_expr, parse_program
from thor_lang.pretty import to_source


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


def test_red2_binary_round_trip_executes_same_result() -> None:
    source = "((LAMBDA (X) (+ X 1)) 41)"
    image = compile_expr(parse_expr(source))
    decoded = decode_program_image(encode_program_image(image))

    original_machine = Red2Machine(image, quantum=20)
    decoded_machine = Red2Machine(decoded, quantum=20)
    original_machine.run()
    decoded_machine.run()

    assert to_source(original_machine.result_expr()) == "42"
    assert to_source(decoded_machine.result_expr()) == "42"


def test_red2_binary_bundle_round_trip_executes_with_definitions() -> None:
    program = normalize_program(parse_program("inc == (lambda (x) (+ x 1))\n(inc 41)"))
    definitions = {
        form.name: form.expr for form in program.forms if isinstance(form, Definition)
    }
    entry: Expr | None = None
    for form in program.forms:
        if not isinstance(form, Definition | StructDef):
            entry = form
    assert entry is not None
    data = encode_bundle(compile_expr(entry), compile_definitions(definitions))
    decoded = decode_bundle(data)

    machine = Red2Machine(
        decoded.entry,
        quantum=20,
        definitions=decoded.definitions,
    )
    machine.run()

    assert to_source(machine.result_expr()) == "42"
    assert tuple(decoded.definitions.programs) == ("inc",)


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

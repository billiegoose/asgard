from __future__ import annotations

from thor_spec.parser import parse_expr
from thor_spec.pretty import to_source
from thor_spec.red2.binary import (
    MAGIC,
    Red2BinaryError,
    decode_program_image,
    encode_program_image,
)
from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.machine import Red2Machine


def test_red2_binary_starts_with_magic_and_version() -> None:
    data = encode_program_image(compile_expr(parse_expr("(+ 2 3)")))

    assert data[:4] == MAGIC
    assert data[4:6] == b"\x01\x00"


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

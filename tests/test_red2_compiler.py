from thor_spec.parser import parse_expr
from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.instructions import (
    Instruction,
    Opcode,
    decode_instruction,
    encode_instruction,
)


def opcodes(source: str) -> list[Opcode]:
    return [inst.opcode for inst in compile_expr(parse_expr(source)).instructions]


def test_instruction_encoding_round_trips_head_opcode_and_small_data() -> None:
    inst = Instruction(Opcode.INT, 42, head=True)
    assert decode_instruction(encode_instruction(inst)) == inst


def test_lambda_application_compiles_to_linear_spine_with_stop() -> None:
    image = compile_expr(parse_expr("((LAMBDA (X) X) 42)"))
    assert image.entry == 0
    assert image.instructions[-1].opcode is Opcode.STOP
    assert opcodes("((LAMBDA (X) X) 42)")[:4] == [
        Opcode.APP,
        Opcode.LAMBDA,
        Opcode.VAR,
        Opcode.INT,
    ]


def test_head_flag_marks_spine_head() -> None:
    image = compile_expr(parse_expr("(LAMBDA (A B) A B)"))
    assert [(i.opcode, i.head) for i in image.instructions[:4]] == [
        (Opcode.LAMBDA, False),
        (Opcode.LAMBDA, False),
        (Opcode.VAR, False),
        (Opcode.VAR, True),
    ]


def test_structure_and_letrec_compile_to_red2_specific_opcodes() -> None:
    assert Opcode.STRUCT in opcodes("{PAIR 1 2}")
    letrec_ops = opcodes("(LETREC ((x [1 | y]) (y [2 | x])) x)")
    assert letrec_ops.count(Opcode.RBLOCK) == 2
    assert Opcode.RUP in letrec_ops

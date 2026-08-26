"""RED2 graph-machine contracts and compiler helpers."""

from thor_spec.red2.compiler import compile_expr
from thor_spec.red2.instructions import (
    Instruction,
    Opcode,
    ProgramImage,
    decode_instruction,
    encode_instruction,
)

__all__ = [
    "Instruction",
    "Opcode",
    "ProgramImage",
    "compile_expr",
    "decode_instruction",
    "encode_instruction",
]

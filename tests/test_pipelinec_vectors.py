from red2_engine.instructions import Instruction, Opcode, encode_instruction
from red2_engine.pipelinec_vectors import emit_stepper_vectors


def test_stepper_vectors_include_passive_int_and_stop() -> None:
    vectors = {v.name: v for v in emit_stepper_vectors()}
    assert vectors["int_head"].before == encode_instruction(
        Instruction(Opcode.INT, 42, head=True)
    )
    assert vectors["stop"].before == encode_instruction(
        Instruction(Opcode.STOP, 0, head=True)
    )

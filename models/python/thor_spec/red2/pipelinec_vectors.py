from __future__ import annotations

from dataclasses import dataclass

from pypeline_red2.red2_stepper import DIRECTION_FORWARD, red2_step_word
from thor_spec.red2.instructions import Instruction, Opcode, encode_instruction

VECTOR_QUANTUM = 3


@dataclass(frozen=True, slots=True)
class StepperVector:
    name: str
    before: int
    after: int


def emit_stepper_vectors() -> list[StepperVector]:
    """Emit word-level golden vectors for the Pypeline RED2 stepper subset.

    These vectors validate fixed-width instruction decode/encode behavior and
    the stepper's word-local classification convention. They are not a
    replacement for full RED2 graph-machine parity tests.
    """
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
            red2_step_word(before, VECTOR_QUANTUM, DIRECTION_FORWARD),
        )
        for name, instruction in instructions
    ]

from collections.abc import Mapping

from red2_engine.instructions import Instruction, Opcode, ProgramImage
from red2_engine.machine import Red2Machine, Red2ResourceLimits
from red2_engine.mured import MuredMachine, MuredMachineState, MuredOpcode, Word
from thor_lang.ast import Expr


def load_faithful_machine(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | None = None,
    memory_words: int = 256,
    control_words: int = 64,
) -> MuredMachine:
    """Load the faithful μRED integration path without an import cycle."""
    from thor_compile.red2 import load_faithful_machine as load

    return load(
        expr,
        quantum=quantum,
        definitions=definitions,
        memory_words=memory_words,
        control_words=control_words,
    )


__all__ = [
    "Instruction",
    "MuredMachine",
    "MuredMachineState",
    "MuredOpcode",
    "Opcode",
    "ProgramImage",
    "Red2Machine",
    "Red2ResourceLimits",
    "Word",
    "load_faithful_machine",
]

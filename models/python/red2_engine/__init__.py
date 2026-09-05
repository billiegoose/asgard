from collections.abc import Mapping

from red2_engine.instructions import Instruction, Opcode, ProgramImage
from red2_engine.mured import MuredMachine, MuredMachineState, MuredOpcode, Word
from thor_lang.ast import Expr


def load_faithful_machine(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | None = None,
    memory_words: int = 65_536,
    control_words: int = 8_192,
) -> MuredMachine:
    """Load one THOR expression into the faithful Python μRED machine."""
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
    "Word",
    "load_faithful_machine",
]

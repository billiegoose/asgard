from collections.abc import Mapping

from red2_engine.instructions import Instruction, Opcode, ProgramImage
from red2_engine.io_runtime import (
    DEFAULT_RED2_RECHARGE_EVENTS,
    Red2IoHost,
    Red2IoRuntimeError,
    Red2RechargeEvent,
    run_red2_io_action,
)
from red2_engine.mured import MuredMachine, MuredMachineState, MuredOpcode, Word
from thor_lang.ast import Expr


def load_faithful_machine(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | None = None,
    memory_words: int = 1_048_576,
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
    "DEFAULT_RED2_RECHARGE_EVENTS",
    "Instruction",
    "MuredMachine",
    "MuredMachineState",
    "MuredOpcode",
    "Opcode",
    "ProgramImage",
    "Red2IoHost",
    "Red2IoRuntimeError",
    "Red2RechargeEvent",
    "Word",
    "load_faithful_machine",
    "run_red2_io_action",
]

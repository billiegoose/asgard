from dataclasses import dataclass
from enum import StrEnum, auto

class MuredOpcode(StrEnum):
    APP = auto()
    APP_VAR = auto()
    CLOSURE = auto()
    EP = auto()
    JOIN = auto()
    LAMBDA = auto()
    STOP = auto()
    INT = auto()
    FLOAT = auto()
    CHAR = auto()
    SYM = auto()
    PRIM_0 = auto()
    PRIM_1 = auto()
    PRIM_2 = auto()
    STRUCT = auto()
    RBLOCK = auto()
    RUP = auto()
    RECP = auto()
    REC = auto()
    UBV = auto()
    VAR = auto()
    PNP = auto()


class Direction(StrEnum):
    F = auto()
    B = auto()


@dataclass(frozen=True, slots=True)
class Word:
    opcode: MuredOpcode | None
    data: int | float | str | None = None
    head: bool = False
    definition: int | None = None
    # RED keeps the CLOSURE class on an environment word after sharing an
    # atomic value over the closure.  The type/opcode becomes the atom, but
    # LOOKUP must still step over the original two-word closure slot.
    closure_slot: bool = False

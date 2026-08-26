"""Fixed-width RED2 instruction stepper subset for PypelineC exploration.

The functions in this file deliberately use integer bit operations and module
constants so the source remains close to Pypeline/PipelineC-style examples while
also staying executable as plain Python for golden-vector tests.
"""

HEAD_SHIFT = 31
OPCODE_SHIFT = 24
DATA_MASK = (1 << OPCODE_SHIFT) - 1
OPCODE_MASK = (1 << 7) - 1
WORD_MASK = (1 << 32) - 1

STATUS_WORD_SHIFT = 0
STATUS_Q_SHIFT = 32
STATUS_DIRECTION_SHIFT = 56
STATUS_HALTED_SHIFT = 57
STATUS_CLASS_SHIFT = 58
STATUS_Q_MASK = (1 << 24) - 1

DIRECTION_FORWARD = 0
DIRECTION_REVERSE = 1

CLASS_OTHER = 0
CLASS_STOP = 1
CLASS_PASSIVE = 2
CLASS_APP = 3
CLASS_VAR = 4
CLASS_LAMBDA = 5

OP_APP = 0
OP_LAMBDA = 1
OP_VAR = 2
OP_STOP = 3
OP_INT = 4
OP_FLOAT = 5
OP_CHAR = 6
OP_SYM = 7
OP_PRIM_0 = 8

PASSIVE_CONSTANT_OPCODES = (OP_INT, OP_FLOAT, OP_CHAR, OP_SYM, OP_PRIM_0)


# PypelineC entry: red2_step_word(pc_word, q, direction)
def decode_opcode(word: int) -> int:
    """Return the seven-bit RED2 opcode field from a 32-bit instruction word."""
    return (word >> OPCODE_SHIFT) & OPCODE_MASK


def encode_word(head: int | bool, opcode: int, data: int) -> int:
    """Encode a RED2 instruction word using the shared prototype 32-bit layout."""
    return (
        (int(bool(head)) << HEAD_SHIFT)
        | ((opcode & OPCODE_MASK) << OPCODE_SHIFT)
        | (data & DATA_MASK)
    )


def red2_step_word(pc_word: int, q: int, direction: int) -> int:
    """Classify one RED2 word and return packed stepper status.

    Status layout for this prototype artifact:
    - bits 0..31: the unchanged instruction word at the program counter
    - bits 32..55: the unchanged 24-bit quantum input
    - bit 56: next direction, where 0 is forward and 1 is reverse
    - bit 57: halted flag
    - bits 58..63: instruction classification for static/golden checks

    The subset is intentionally word-local: it does not mutate graph memory or
    model stack effects from the full RED2 machine.
    """
    word = pc_word & WORD_MASK
    opcode = decode_opcode(word)
    head = (word >> HEAD_SHIFT) & 1
    next_direction = direction & 1
    halted = 0
    classification = CLASS_OTHER

    if opcode == OP_STOP:
        halted = 1
        classification = CLASS_STOP
    elif opcode in PASSIVE_CONSTANT_OPCODES:
        classification = CLASS_PASSIVE
        if head:
            next_direction = DIRECTION_REVERSE
    elif opcode == OP_APP:
        classification = CLASS_APP
    elif opcode == OP_VAR:
        classification = CLASS_VAR
    elif opcode == OP_LAMBDA:
        classification = CLASS_LAMBDA
        if head and q == 0:
            next_direction = DIRECTION_REVERSE

    return _pack_status(word, q, next_direction, halted, classification)


def _pack_status(
    word: int, q: int, direction: int, halted: int, classification: int
) -> int:
    return (
        ((word & WORD_MASK) << STATUS_WORD_SHIFT)
        | ((q & STATUS_Q_MASK) << STATUS_Q_SHIFT)
        | ((direction & 1) << STATUS_DIRECTION_SHIFT)
        | ((halted & 1) << STATUS_HALTED_SHIFT)
        | ((classification & 0x3F) << STATUS_CLASS_SHIFT)
    )

"""Fixed-width synthesizable RED2 ABI and legacy word-stepper helpers.

The hardware ABI in this module is intentionally independent from
``red2.instructions``' older 32-bit compiler-image encoding.  The
faithful ``AbstractRED2Machine`` has additional opcodes and machine-visible metadata
(``definition`` and ``closure_slot``), and RED2 also uses populated workspace
cells whose opcode is ``None``.  Hardware therefore receives an explicitly
encoded RED2_ABI_V1 image rather than Python objects or source strings.

Only integer constants, range checks and bit operations belong to the hardware
path here.  Python-object adaptation and load-time literal-ID assignment live
in ``concrete_red2_machine.pipelinec_vectors``.
"""

RED2_ABI_V1 = 1
RED2_MEMORY_V1 = 1

# Architectural limits chosen for the first FPGA ABI.  They are deliberately
# explicit rather than inheriting Python's unbounded integers.
ADDRESS_BITS = 16
ADDRESS_MAX = (1 << ADDRESS_BITS) - 1
FRONTIER_BITS = ADDRESS_BITS + 1
FRONTIER_MAX = 1 << ADDRESS_BITS
COUNTER_BITS = 32
COUNTER_MAX = (1 << COUNTER_BITS) - 1
SIGNED_DATA_BITS = 64
SIGNED_DATA_MIN = -(1 << (SIGNED_DATA_BITS - 1))
SIGNED_DATA_MAX = (1 << (SIGNED_DATA_BITS - 1)) - 1
LITERAL_ID_BITS = 32
LITERAL_ID_MAX = (1 << LITERAL_ID_BITS) - 1
OPCODE_BITS = 5
OPCODE_MAX = (1 << OPCODE_BITS) - 1

# Faithful MuredOpcode IDs.  Zero is reserved for a populated RED2 workspace
# word whose opcode is None.  Empty RAM is distinguished by WORD_VALID.
MOP_NONE = 0
MOP_APP = 1
MOP_APP_VAR = 2
MOP_CLOSURE = 3
MOP_EP = 4
MOP_JOIN = 5
MOP_LAMBDA = 6
MOP_STOP = 7
MOP_INT = 8
MOP_FLOAT = 9
MOP_CHAR = 10
MOP_SYM = 11
MOP_PRIM_0 = 12
MOP_PRIM_1 = 13
MOP_PRIM_2 = 14
MOP_STRUCT = 15
MOP_RBLOCK = 16
MOP_RUP = 17
MOP_RECP = 18
MOP_REC = 19
MOP_UBV = 20
MOP_VAR = 21
MOP_PNP = 22
MOP_MAX = MOP_PNP

DIRECTION_FORWARD = 0
DIRECTION_REVERSE = 1

STATUS_RUNNING = 0
STATUS_COMPLETE = 1
STATUS_QUANTUM_EXHAUSTED = 2
STATUS_HOST_CALL = 3
STATUS_FAULT = 4
STATUS_MAX = STATUS_FAULT

FAULT_NONE = 0
FAULT_INVALID_ADDRESS = 1
FAULT_GRAPH_ENV_COLLISION = 2
FAULT_CONTROL_OVERFLOW = 3
FAULT_CONTROL_UNDERFLOW = 4
FAULT_ILLEGAL_TRANSITION = 5
FAULT_UNSUPPORTED_VALUE = 6
FAULT_INVALID_RESUME = 7

HOST_NONE = 0
HOST_CLOCK = 1
HOST_UART_RX = 2
HOST_UART_TX = 3
HOST_UART_TX_BYTES = 4
HOST_MAX = HOST_UART_TX_BYTES

DATA_NONE = 0
DATA_SIGNED = 1
DATA_FLOAT64 = 2
DATA_LITERAL_ID = 3
DATA_MAX = DATA_LITERAL_ID

# Packed word layout.  A Python int represents a fixed 128-bit signal in the
# executable model; the field widths, not Python's runtime integer width, are
# the ABI contract.
WORD_PAYLOAD_SHIFT = 0
WORD_PAYLOAD_BITS = 64
WORD_PAYLOAD_MASK = (1 << WORD_PAYLOAD_BITS) - 1
WORD_DEFINITION_SHIFT = 64
WORD_DEFINITION_BITS = ADDRESS_BITS
WORD_DEFINITION_MASK = (1 << WORD_DEFINITION_BITS) - 1
WORD_DEFINITION_VALID_SHIFT = 80
WORD_DATA_KIND_SHIFT = 81
WORD_DATA_KIND_BITS = 2
WORD_CLOSURE_SLOT_SHIFT = 83
WORD_HEAD_SHIFT = 84
WORD_OPCODE_SHIFT = 85
WORD_OPCODE_BITS = OPCODE_BITS
WORD_VALID_SHIFT = 90
WORD_WIDTH = 128
WORD_MASK = (1 << WORD_WIDTH) - 1

# Fixed-width control-stack entry ABI.  Four 32-bit payload lanes are enough
# for every current typed Python control entry, including subgraph/equality
# frames.  Literal IDs (e.g. saved primitive) occupy one payload lane.
CONTROL_TAG_BITS = 4
CONTROL_PAYLOAD_BITS = 32
CONTROL_PAYLOAD_MASK = (1 << CONTROL_PAYLOAD_BITS) - 1
CONTROL_TAG_SHIFT = CONTROL_PAYLOAD_BITS * 4
CONTROL_WIDTH = CONTROL_TAG_SHIFT + CONTROL_TAG_BITS
CONTROL_EMPTY = 0
CONTROL_ADDRESS = 1
CONTROL_SAVED_PRIM = 2
CONTROL_SAVED_FIRE = 3
CONTROL_SAVED_QUANTUM = 4
CONTROL_SAVED_DEFINITION_PATH = 5
CONTROL_SUBGRAPH = 6
CONTROL_EQUALITY = 7
CONTROL_MAX_TAG = CONTROL_EQUALITY

# Legacy 32-bit compiler-image layout retained for existing golden-vector
# compatibility.  This is not RED2_ABI_V1 machine memory.
HEAD_SHIFT = 31
OPCODE_SHIFT = 24
DATA_MASK = (1 << OPCODE_SHIFT) - 1
OPCODE_MASK = (1 << 7) - 1
LEGACY_WORD_MASK = (1 << 32) - 1
STATUS_WORD_SHIFT = 0
STATUS_Q_SHIFT = 32
STATUS_DIRECTION_SHIFT = 56
STATUS_HALTED_SHIFT = 57
STATUS_CLASS_SHIFT = 58
STATUS_Q_MASK = (1 << 24) - 1
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


def require_unsigned(value: int, bits: int) -> int:
    """Return value after enforcing an unsigned fixed-width hardware range."""
    if type(value) is not int or value < 0 or value >= (1 << bits):
        raise ValueError("unsigned value outside fixed-width ABI range")
    return value


def require_signed_data(value: int) -> int:
    """Return a signed 64-bit RED2 scalar or reject it deterministically."""
    if type(value) is not int or value < SIGNED_DATA_MIN or value > SIGNED_DATA_MAX:
        raise ValueError("signed RED2 value outside 64-bit ABI range")
    return value


def signed_to_payload(value: int) -> int:
    value = require_signed_data(value)
    return value & WORD_PAYLOAD_MASK


def payload_to_signed(payload: int) -> int:
    payload = require_unsigned(payload, WORD_PAYLOAD_BITS)
    sign = 1 << (WORD_PAYLOAD_BITS - 1)
    if payload & sign:
        return payload - (1 << WORD_PAYLOAD_BITS)
    return payload


def pack_word(
    valid: int,
    opcode: int,
    data_kind: int,
    payload: int,
    head: int,
    closure_slot: int,
    definition_valid: int,
    definition: int,
) -> int:
    """Pack one RED2_ABI_V1 memory word from already-normalized integer fields."""
    valid = require_unsigned(valid, 1)
    opcode = require_unsigned(opcode, OPCODE_BITS)
    if valid and opcode > MOP_MAX:
        raise ValueError("unknown RED2 ABI opcode")
    data_kind = require_unsigned(data_kind, WORD_DATA_KIND_BITS)
    if data_kind > DATA_MAX:
        raise ValueError("unknown RED2 ABI payload kind")
    payload = require_unsigned(payload, WORD_PAYLOAD_BITS)
    head = require_unsigned(head, 1)
    closure_slot = require_unsigned(closure_slot, 1)
    definition_valid = require_unsigned(definition_valid, 1)
    definition = require_unsigned(definition, WORD_DEFINITION_BITS)
    if not valid and (
        opcode
        or data_kind
        or payload
        or head
        or closure_slot
        or definition_valid
        or definition
    ):
        raise ValueError("empty RED2 RAM word must have zero payload fields")
    if not definition_valid and definition != 0:
        raise ValueError("definition payload requires definition_valid")
    return (
        (payload << WORD_PAYLOAD_SHIFT)
        | (definition << WORD_DEFINITION_SHIFT)
        | (definition_valid << WORD_DEFINITION_VALID_SHIFT)
        | (data_kind << WORD_DATA_KIND_SHIFT)
        | (closure_slot << WORD_CLOSURE_SLOT_SHIFT)
        | (head << WORD_HEAD_SHIFT)
        | (opcode << WORD_OPCODE_SHIFT)
        | (valid << WORD_VALID_SHIFT)
    )


def word_field(word: int, shift: int, bits: int) -> int:
    word = require_unsigned(word, WORD_WIDTH)
    return (word >> shift) & ((1 << bits) - 1)


def pack_control_entry(tag: int, a: int, b: int, c: int, d: int) -> int:
    """Pack one bounded typed control entry into fixed-width payload lanes."""
    tag = require_unsigned(tag, CONTROL_TAG_BITS)
    if tag > CONTROL_MAX_TAG:
        raise ValueError("unknown RED2 control tag")
    a = require_unsigned(a, CONTROL_PAYLOAD_BITS)
    b = require_unsigned(b, CONTROL_PAYLOAD_BITS)
    c = require_unsigned(c, CONTROL_PAYLOAD_BITS)
    d = require_unsigned(d, CONTROL_PAYLOAD_BITS)
    if tag == CONTROL_EMPTY and (a or b or c or d):
        raise ValueError("empty control entry must have zero payload")
    return (
        a
        | (b << CONTROL_PAYLOAD_BITS)
        | (c << (CONTROL_PAYLOAD_BITS * 2))
        | (d << (CONTROL_PAYLOAD_BITS * 3))
        | (tag << CONTROL_TAG_SHIFT)
    )


def control_field(entry: int, lane: int) -> int:
    require_unsigned(entry, CONTROL_WIDTH)
    lane = require_unsigned(lane, 3)
    if lane >= 4:
        raise ValueError("RED2 control payload lane outside range")
    return (entry >> (lane * CONTROL_PAYLOAD_BITS)) & CONTROL_PAYLOAD_MASK


def control_tag(entry: int) -> int:
    require_unsigned(entry, CONTROL_WIDTH)
    return (entry >> CONTROL_TAG_SHIFT) & ((1 << CONTROL_TAG_BITS) - 1)


def require_address(value: int) -> int:
    """Validate a physical RAM cell address."""
    return require_unsigned(value, ADDRESS_BITS)


def require_frontier(value: int) -> int:
    """Validate an environment/frontier path, including one-past-64K RAM."""
    if type(value) is not int or value < 0 or value > FRONTIER_MAX:
        raise ValueError("RED2 frontier outside fixed-width ABI range")
    return value


def encode_optional_address(value: int) -> int:
    """Encode None as zero and address N as N+1 in a 17-bit register field."""
    if value == -1:
        return 0
    require_address(value)
    return value + 1


def decode_optional_address(value: int) -> int:
    value = require_unsigned(value, ADDRESS_BITS + 1)
    if value == 0:
        return -1
    address = value - 1
    require_address(address)
    return address


def _memory_layout_fault(memory: list[int], fsp: int, free_space: int) -> int:
    capacity = len(memory)
    if capacity <= 0 or capacity > FRONTIER_MAX:
        return FAULT_INVALID_ADDRESS
    if type(fsp) is not int or fsp < 0 or fsp >= capacity:
        return FAULT_INVALID_ADDRESS
    if type(free_space) is not int or free_space < 0 or free_space > capacity:
        return FAULT_GRAPH_ENV_COLLISION
    if fsp >= free_space:
        return FAULT_GRAPH_ENV_COLLISION
    return FAULT_NONE


def _environment_path_fault(memory: list[int], env: int) -> int:
    capacity = len(memory)
    if type(env) is not int or env < 0 or env > capacity:
        return FAULT_INVALID_ADDRESS
    return FAULT_NONE


def _packed_pnp(parent: int) -> int:
    return pack_word(1, MOP_PNP, DATA_SIGNED, signed_to_payload(parent), 0, 0, 0, 0)


def red2_push_graph(
    memory: list[int], fsp: int, free_space: int, word: int
) -> tuple[int, int, int]:
    fault = _memory_layout_fault(memory, fsp, free_space)
    if fault != FAULT_NONE:
        return fault, fsp, fsp
    address = fsp + 1
    if address >= free_space:
        return FAULT_GRAPH_ENV_COLLISION, fsp, fsp
    require_unsigned(word, WORD_WIDTH)
    memory[address] = word
    return FAULT_NONE, address, address


def red2_allocate_environment(
    memory: list[int], fsp: int, env: int, free_space: int, word: int
) -> tuple[int, int, int, int]:
    fault = _memory_layout_fault(memory, fsp, free_space)
    if fault != FAULT_NONE:
        return fault, free_space, env, free_space
    fault = _environment_path_fault(memory, env)
    if fault != FAULT_NONE:
        return fault, free_space, env, free_space
    require_unsigned(word, WORD_WIDTH)
    needs_bridge = free_space != env
    address = free_space - 1 - int(needs_bridge)
    if address <= fsp:
        return FAULT_GRAPH_ENV_COLLISION, free_space, env, free_space
    if needs_bridge:
        memory[free_space - 1] = _packed_pnp(env)
    memory[address] = word
    return FAULT_NONE, address, address, address


def red2_allocate_environment_block(
    memory: list[int],
    fsp: int,
    env: int,
    free_space: int,
    words: list[int],
) -> tuple[int, int, int, int]:
    count = len(words)
    if count <= 0:
        return FAULT_ILLEGAL_TRANSITION, free_space, env, free_space
    fault = _memory_layout_fault(memory, fsp, free_space)
    if fault != FAULT_NONE:
        return fault, free_space, env, free_space
    fault = _environment_path_fault(memory, env)
    if fault != FAULT_NONE:
        return fault, free_space, env, free_space
    needs_bridge = free_space != env
    address = free_space - count - int(needs_bridge)
    if address <= fsp:
        return FAULT_GRAPH_ENV_COLLISION, free_space, env, free_space
    offset = 0
    while offset < count:
        require_unsigned(words[offset], WORD_WIDTH)
        offset += 1
    if needs_bridge:
        memory[free_space - 1] = _packed_pnp(env)
    offset = 0
    while offset < count:
        memory[address + offset] = words[offset]
        offset += 1
    return FAULT_NONE, address, address, address


def red2_push_environment_marker(
    memory: list[int], fsp: int, free_space: int, parent: int
) -> tuple[int, int, int]:
    fault = _memory_layout_fault(memory, fsp, free_space)
    if fault != FAULT_NONE:
        return fault, free_space, free_space
    fault = _environment_path_fault(memory, parent)
    if fault != FAULT_NONE:
        return fault, free_space, free_space
    address = free_space - 1
    if address <= fsp:
        return FAULT_GRAPH_ENV_COLLISION, free_space, free_space
    memory[address] = _packed_pnp(parent)
    return FAULT_NONE, address, address


def red2_control_push(
    control_memory: list[int], c: int, entry: int
) -> tuple[int, int]:
    capacity = len(control_memory)
    if type(c) is not int or c < -1 or c >= capacity:
        return FAULT_INVALID_ADDRESS, c
    if type(entry) is not int or entry < 0 or entry >= (1 << CONTROL_WIDTH):
        return FAULT_INVALID_ADDRESS, c
    if control_tag(entry) == CONTROL_EMPTY:
        return FAULT_ILLEGAL_TRANSITION, c
    next_c = c + 1
    if next_c >= capacity:
        return FAULT_CONTROL_OVERFLOW, c
    control_memory[next_c] = entry
    return FAULT_NONE, next_c


def red2_control_pop(
    control_memory: list[int], c: int
) -> tuple[int, int, int]:
    capacity = len(control_memory)
    if type(c) is not int or c < -1 or c >= capacity:
        return FAULT_INVALID_ADDRESS, c, 0
    if c < 0:
        return FAULT_CONTROL_UNDERFLOW, c, 0
    entry = control_memory[c]
    if type(entry) is not int or entry < 0 or entry >= (1 << CONTROL_WIDTH):
        return FAULT_INVALID_ADDRESS, c, 0
    if control_tag(entry) == CONTROL_EMPTY:
        return FAULT_CONTROL_UNDERFLOW, c, 0
    control_memory[c] = 0
    return FAULT_NONE, c - 1, entry


# Legacy 32-bit word-level exploration entry: red2_step_word(pc_word, q, direction)
def decode_opcode(word: int) -> int:
    """Return the seven-bit legacy compiler opcode field from a 32-bit word."""
    return (word >> OPCODE_SHIFT) & OPCODE_MASK


def encode_word(head: int | bool, opcode: int, data: int) -> int:
    """Encode the retained legacy 32-bit compiler-image word format."""
    return (
        (int(bool(head)) << HEAD_SHIFT)
        | ((opcode & OPCODE_MASK) << OPCODE_SHIFT)
        | (data & DATA_MASK)
    )


def red2_step_word(pc_word: int, q: int, direction: int) -> int:
    """Retained word-local classifier used only by historical golden vectors."""
    word = pc_word & LEGACY_WORD_MASK
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
        ((word & LEGACY_WORD_MASK) << STATUS_WORD_SHIFT)
        | ((q & STATUS_Q_MASK) << STATUS_Q_SHIFT)
        | ((direction & 1) << STATUS_DIRECTION_SHIFT)
        | ((halted & 1) << STATUS_HALTED_SHIFT)
        | ((classification & 0x3F) << STATUS_CLASS_SHIFT)
    )

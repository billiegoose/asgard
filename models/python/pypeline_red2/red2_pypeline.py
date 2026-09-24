"""Synthesizable Pypeline/PipelineC top for the persistent RED2 processor.

``red2_processor.py`` remains the executable CPython architectural oracle.  This
module is independent hardware source and is accepted by the real Pypeline
frontend.  Reducer semantics are being ported slice-by-slice; until
``RED2_PYPELINE_SEMANTICS_COMPLETE`` becomes 1 the explicit synthesis gate must
withhold ``RED2_SYNTH_V1``.
"""

from typing import NamedTuple

from pypeline import MAIN, Reg, hw_func, struct, uint1_t, uint2_t, uint3_t, uint4_t, uint5_t, uint6_t, uint7_t, uint16_t, uint17_t, uint32_t, uint64_t
from ram import make_ram


RED2_PYPELINE_TOP_V1 = 1
RED2_PYPELINE_SEMANTICS_COMPLETE = 0

GRAPH_WORDS = 256
CONTROL_WORDS = 256
GRAPH_ADDR_BITS = 8
CONTROL_ADDR_BITS = 8
LITERAL_META_WORDS = 64
LITERAL_META_ADDR_BITS = 6

CMD_NOP = 0
CMD_RESET = 1
CMD_LOAD_MEMORY = 2
CMD_LOAD_CONTROL = 3
CMD_START = 4
CMD_RECHARGE = 5
CMD_RESUME = 6
CMD_CLOCK = 7
CMD_LOAD_STATE = 8
CMD_LOAD_LITERAL_META = 9

STATUS_RUNNING = 0
STATUS_COMPLETE = 1
STATUS_QUANTUM_EXHAUSTED = 2
STATUS_HOST_CALL = 3
STATUS_FAULT = 4

FAULT_NONE = 0
FAULT_INVALID_ADDRESS = 1
FAULT_GRAPH_ENV_COLLISION = 2
FAULT_CONTROL_OVERFLOW = 3
FAULT_CONTROL_UNDERFLOW = 4
FAULT_ILLEGAL_TRANSITION = 5
FAULT_UNSUPPORTED_VALUE = 6

HW_FAULT_NONE = 0
HW_FAULT_BAD_COMMAND = 1
HW_FAULT_ADDRESS_RANGE = 2
HW_FAULT_EXECUTION_NOT_IMPLEMENTED = 3

HOST_NONE = 0
HOST_CLOCK = 1
HOST_UART_RX = 2

PRIM0_ROLE_PASSIVE = 0
PRIM0_ROLE_IF = 1
PRIM0_ROLE_IO_BIND = 2
PRIM0_ROLE_DEFERRED = 3
PRIM0_ROLE_Y = 4
PRIM0_ROLE_IO_THEN = 5
PRIM0_ROLE_IO_RETURN = 6
CONTROL_ADDRESS = 1
CONTROL_SAVED_QUANTUM = 4
CONTROL_SAVED_DEFINITION_PATH = 5
CONTROL_SUBGRAPH = 6
CONTROL_EQUALITY = 7
DIRECTION_FORWARD = 0
DIRECTION_REVERSE = 1

DATA_NONE = 0
DATA_SIGNED = 1
DATA_FLOAT64 = 2
DATA_LITERAL_ID = 3

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

SCALAR_OP_NONE = 0
SCALAR_OP_DEC = 1
SCALAR_OP_INC = 2
SCALAR_OP_NEGATE = 3
SCALAR_OP_ABS = 4
SCALAR_OP_FLOOR = 5
SCALAR_OP_CEILING = 6
SCALAR_OP_EVEN = 7
SCALAR_OP_NULL = 8
SCALAR_OP_NOT = 9
SCALAR_OP_INTEGER_P = 10
SCALAR_OP_FLOAT_P = 11
SCALAR_OP_CHAR_P = 12
SCALAR_OP_SYMBOL_P = 13
SCALAR_OP_ADD = 14
SCALAR_OP_SUB = 15
SCALAR_OP_MUL = 16
SCALAR_OP_DIV = 17
SCALAR_OP_LT = 18
SCALAR_OP_GT = 19
SCALAR_OP_LE = 20
SCALAR_OP_GE = 21
SCALAR_OP_EQ = 22
SCALAR_OP_EXPT = 23
SCALAR_OP_MAX = 24
SCALAR_OP_MIN = 25
SCALAR_OP_MOD = 26

LITERAL_SPECIAL_TRUE = 1
LITERAL_SPECIAL_FALSE = 2
LITERAL_SPECIAL_NIL = 4
LITERAL_SPECIAL_EQUAL_STAR = 8
LITERAL_SPECIAL_EQUAL_IF = 16
LITERAL_SPECIAL_EQUALITY = 32
LITERAL_SPECIAL_EQUALITY_CONTINUE = 64
LITERAL_SPECIAL_EQUAL_STUCK = 128

MICRO_FETCH = 0
MICRO_EXECUTE = 1
MICRO_COMMIT = 2
MICRO_FAULT = 3
MICRO_LOOKUP_READ = 4
MICRO_LOOKUP_PUBLISH = 5
MICRO_LAMBDA_READ = 6
MICRO_LAMBDA_PUSH = 7
MICRO_LAMBDA_ENV = 8
MICRO_LAMBDA_BETA_ENV = 9
MICRO_LAMBDA_EP_CONTROL_READ = 10
MICRO_LAMBDA_EP_CONTROL_POP = 11
MICRO_LAMBDA_EP_ENV = 12
MICRO_LAMBDA_APP_CONTROL_READ = 13
MICRO_LAMBDA_APP_CONTROL_POP = 14
MICRO_LAMBDA_APP_BRIDGE = 15
MICRO_LAMBDA_APP_CLOSURE = 16
MICRO_LAMBDA_APP_POINTER = 17
MICRO_LAMBDA_ENV_BRIDGE = 18
MICRO_LAMBDA_ENV_BINDING = 19
MICRO_LAMBDA_BETA_BRIDGE = 20
MICRO_LAMBDA_BETA_BINDING = 21
MICRO_APP_CONTROL_READ = 22
MICRO_APP_BRIDGE = 23
MICRO_APP_FRAME = 24
MICRO_APP_JOIN = 25
MICRO_CLOSURE_READ = 26
MICRO_CLOSURE_MARKER = 27
MICRO_EP_CHASE = 28
MICRO_EP_FORWARD_PUBLISH = 29
MICRO_EP_REVERSE_CONTROL_READ = 30
MICRO_EP_REVERSE_MARKER = 31
MICRO_EP_REVERSE_PUBLISH = 32
MICRO_JOIN_PARENT_READ = 33
MICRO_JOIN_EP_TARGET_READ = 34
MICRO_JOIN_FRAME_READ = 35
MICRO_JOIN_TAIL_READ = 36
MICRO_JOIN_PUBLISH = 37
MICRO_JOIN_EP_CACHE = 38
MICRO_JOIN_EP_CHASE = 39
MICRO_JOIN_EP_RESULT_WRITE = 40
MICRO_JOIN_FLAT_SCAN = 41
MICRO_JOIN_CLOSURE_CODE_READ = 42
MICRO_JOIN_CLOSURE_LAMBDA_SCAN = 43
MICRO_JOIN_CLOSURE_BODY_READ = 44
MICRO_JOIN_CLOSURE_ENV_READ = 45
MICRO_JOIN_CLOSURE_WRITE_LAMBDA = 46
MICRO_JOIN_CLOSURE_WRITE_BODY = 47
MICRO_JOIN_CLOSURE_WRITE_LAMBDA_COMMIT = 48
MICRO_JOIN_CLOSURE_PREFLIGHT = 49
MICRO_JOIN_APP_SCAN = 50
MICRO_JOIN_APP_TARGET_READ = 51
MICRO_JOIN_APP_REWRITE_READ = 52
MICRO_JOIN_APP_REWRITE_WRITE = 53
MICRO_JOIN_MULTI_TARGET_READ = 54
MICRO_JOIN_MULTI_TARGET_CHASE = 55
MICRO_JOIN_MULTI_TARGET_ADVANCE = 56
MICRO_JOIN_MULTI_TARGET_WRITE_FIRST = 57
MICRO_JOIN_MULTI_TARGET_WRITE_SECOND = 58
MICRO_JOIN_CONTROL_CLEAR = 59
MICRO_JOIN_PRIM_META_SCAN = 60
MICRO_JOIN_SPECIAL_META_SCAN = 61
MICRO_JOIN_SPECIAL_META_DONE = 62
MICRO_JOIN_SCALAR_LEFT_READ = 63
MICRO_RUP_VALIDATE_REC = 64
MICRO_RUP_VALIDATE_CONTEXT = 65
MICRO_RUP_VALIDATE_BLOCK = 66
MICRO_RUP_VALIDATE_SOURCE = 67
MICRO_RUP_WRITE_CONTEXT = 68
MICRO_RUP_WRITE_BLOCK = 69
MICRO_RUP_ZERO_PUSH = 70
MICRO_RUP_ZERO_RESULT = 71
MICRO_RECP_VALIDATE_REC = 72
MICRO_RECP_VALIDATE_CONTEXT = 73
MICRO_RECP_VALIDATE_BLOCK = 74
MICRO_RECP_ACTION = 75
MICRO_RECP_RECON_SCAN = 76
MICRO_RECP_RECON_PREFLIGHT = 77
MICRO_RECP_RECON_MARKER = 78
MICRO_RECP_RECON_UBV = 79
MICRO_RECP_RECON_COPY_READ = 80
MICRO_RECP_RECON_COPY_WRITE = 81
MICRO_RECP_RECON_PATH = 82
MICRO_RECP_RECON_RUP_READ = 83
MICRO_RECP_RECON_RUP_WRITE = 84
MICRO_RECP_RECON_VAR_WRITE = 85
MICRO_RECP_REVERSE_BRIDGE = 86
MICRO_RECP_REVERSE_FRAME = 87
MICRO_RECP_REVERSE_JOIN = 88
MICRO_JOIN_RECP_RBLOCK_SCAN = 89
MICRO_JOIN_RECP_RBLOCK_BINDING_READ = 90
MICRO_JOIN_RECP_RBLOCK_BODY_READ = 91
MICRO_STRUCT_RESULT_READ = 92
MICRO_STRUCT_RECON_SAVED_Q = 93
MICRO_STRUCT_REVERSE_CONTROL_READ = 94
MICRO_STRUCT_REVERSE_POP = 95


@struct
class red2_word_t(NamedTuple):
    """Exact 128-bit RED2_ABI_V1 word, low 64 bits first."""

    lo: uint64_t
    hi: uint64_t


@struct
class red2_control_t(NamedTuple):
    """Exact 132-bit RED2_ABI_V1 control entry."""

    lo: uint64_t
    hi: uint64_t
    tag_hi: uint4_t


@struct
class red2_literal_meta_t(NamedTuple):
    """One associative semantic-metadata entry keyed by full RED2 literal id.

    ``valid`` distinguishes an unused slot from literal id zero.  The initial
    hardware slice consumes ``scalar_op``; the remaining fields establish the
    loader contract for later primitive/host slices without assigning meaning
    to codec allocation order.
    """

    literal_id: uint32_t
    scalar_op: uint5_t
    prim0_role: uint3_t
    host_op: uint3_t
    special_flags: uint16_t
    valid: uint1_t


@struct
class red2_u64_divmod_t(NamedTuple):
    q: uint64_t
    r: uint64_t


@hw_func
def red2_u64_ge(a: uint64_t, b: uint64_t) -> uint1_t:
    """Unsigned >= without PipelineC's generic 64-bit comparison helper."""

    a_hi: uint1_t = a[63]
    b_hi: uint1_t = b[63]
    ge: uint1_t = a_hi
    if a_hi == b_hi:
        a_low: uint64_t = a & 9223372036854775807
        b_low: uint64_t = b & 9223372036854775807
        delta: uint64_t = a_low - b_low
        ge = delta[63] == 0
    return ge


@hw_func
def red2_u64_divmod(dividend: uint64_t, divisor: uint64_t) -> red2_u64_divmod_t:
    """Fixed 64-step restoring divider used by RED2 checked integer scalars."""

    quotient: uint64_t = 0
    remainder: uint64_t = 0
    for i in range(64):
        next_bit: uint64_t = dividend[63 - i]
        remainder = (remainder << 1) | next_bit
        quotient = quotient << 1
        remainder_ge_divisor: uint1_t = red2_u64_ge(remainder, divisor)
        if remainder_ge_divisor:
            remainder = remainder - divisor
            quotient = quotient | 1
    return red2_u64_divmod_t(q=quotient, r=remainder)


@struct
class red2_arch_state_t(NamedTuple):
    """Scalar portion of EncodedArchitecturalState, in its wire encoding.

    ``control_top`` is Python ``c + 1``; ``argcnt`` is Python ``argcnt + 1``;
    ``s_a``/``s_d`` are optional addresses encoded as zero or address+1.
    """

    pc: uint16_t
    fsp: uint16_t
    env: uint17_t
    control_top: uint17_t
    direction: uint1_t
    q: uint32_t
    phi: uint32_t
    free_space: uint17_t
    argcnt: uint32_t
    prim_id: uint32_t
    fire: uint32_t
    s_a: uint17_t
    s_d: uint17_t
    halted: uint1_t
    pending_host_op: uint3_t
    pending_host_argument: uint64_t


@struct
class red2_command_t(NamedTuple):
    op: uint4_t
    address: uint16_t
    word: red2_word_t
    control: red2_control_t
    value: uint32_t
    aux: uint64_t
    state: red2_arch_state_t


@struct
class red2_status_t(NamedTuple):
    status: uint3_t
    red2_fault: uint3_t
    hw_fault: uint3_t
    microstate: uint7_t
    committed: uint1_t
    pc: uint16_t
    fsp: uint16_t
    env: uint17_t
    control_top: uint17_t
    direction: uint1_t
    q: uint32_t
    phi: uint32_t
    free_space: uint17_t
    argcnt: uint32_t
    prim_id: uint32_t
    fire: uint32_t
    s_a: uint17_t
    s_d: uint17_t
    halted: uint1_t
    pending_host_op: uint3_t
    pending_host_argument: uint64_t
    memory_read: red2_word_t
    control_read: red2_control_t
    semantics_complete: uint1_t


graph_ram, graph_ram_out_t = make_ram(
    red2_word_t, GRAPH_WORDS, ports=("rw",), read_latency=0
)
control_ram, control_ram_out_t = make_ram(
    red2_control_t, CONTROL_WORDS, ports=("rw",), read_latency=0
)
literal_meta_ram, literal_meta_ram_out_t = make_ram(
    red2_literal_meta_t, LITERAL_META_WORDS, ports=("rw",), read_latency=0
)


@MAIN(25.0)
def red2_processor_top(command: red2_command_t) -> red2_status_t:
    """Advance at most one RED2 hardware micro-clock."""

    pc: Reg[uint16_t]
    fsp: Reg[uint16_t]
    env: Reg[uint17_t]
    control_top: Reg[uint17_t]
    direction: Reg[uint1_t]
    q: Reg[uint32_t]
    phi: Reg[uint32_t]
    free_space: Reg[uint17_t]
    argcnt: Reg[uint32_t]
    prim_id: Reg[uint32_t]
    fire: Reg[uint32_t]
    s_a: Reg[uint17_t]
    s_d: Reg[uint17_t]
    halted: Reg[uint1_t]
    pending_host_op: Reg[uint3_t]
    pending_host_argument: Reg[uint64_t]
    red2_fault: Reg[uint3_t]
    hw_fault: Reg[uint3_t]
    microstate: Reg[uint7_t]
    fetched_word: Reg[red2_word_t]
    lookup_word: Reg[red2_word_t]
    lookup_address: Reg[uint17_t]
    lookup_remaining: Reg[uint64_t]
    lookup_hops: Reg[uint16_t]
    rup_count: Reg[uint16_t]
    rup_index: Reg[uint16_t]
    rup_block: Reg[uint16_t]
    rup_rec_binding: Reg[uint64_t]
    rup_rec_payload_bad: Reg[uint1_t]
    recp_binding: Reg[uint64_t]
    recp_context: Reg[uint64_t]
    recp_block: Reg[uint64_t]
    recp_count: Reg[uint16_t]
    recp_index: Reg[uint16_t]
    recp_selected: Reg[uint16_t]
    recp_replacement: Reg[uint17_t]
    recp_parent_environment: Reg[uint17_t]
    recp_reverse_zero: Reg[uint1_t]
    recp_reverse_needs_bridge: Reg[uint1_t]
    recp_reverse_parent_env: Reg[uint17_t]
    recp_reverse_entry_env: Reg[uint17_t]
    recp_copy_word: Reg[red2_word_t]
    recp_rup_word: Reg[red2_word_t]
    struct_saved_q: Reg[uint32_t]
    lambda_word: Reg[red2_word_t]
    lambda_path: Reg[uint32_t]
    app_parent_env: Reg[uint32_t]
    app_entry_env: Reg[uint17_t]
    app_child_pc: Reg[uint16_t]
    app_parent_pc: Reg[uint16_t]
    app_rblock_active: Reg[uint1_t]
    app_definition_active: Reg[uint1_t]
    app_definition_pop_saved: Reg[uint1_t]
    stop_cleanup_active: Reg[uint1_t]
    closure_target: Reg[uint16_t]
    ep_target: Reg[uint64_t]
    ep_hops: Reg[uint16_t]
    ep_terminal_word: Reg[red2_word_t]
    ep_publish_word: Reg[red2_word_t]
    ep_caller_path: Reg[uint32_t]
    join_parent_word: Reg[red2_word_t]
    join_publish_word: Reg[red2_word_t]
    join_cache_word: Reg[red2_word_t]
    join_parent_address: Reg[uint16_t]
    join_result_address: Reg[uint16_t]
    join_published_root: Reg[uint16_t]
    join_recp_rblock_cursor: Reg[uint16_t]
    join_recp_rblock_count: Reg[uint16_t]
    join_recp_binding_root: Reg[uint16_t]
    join_ep_target: Reg[uint16_t]
    join_frame_env: Reg[uint17_t]
    join_frame_free_space: Reg[uint17_t]
    join_frame_prim_id: Reg[uint32_t]
    join_frame_fire: Reg[uint32_t]
    join_saved_primitive: Reg[uint1_t]
    join_prim_meta_cursor: Reg[uint16_t]
    join_prim_scalar_op: Reg[uint5_t]
    join_scalar_preflight_done: Reg[uint1_t]
    join_scalar_contract: Reg[uint1_t]
    join_scalar_right_word: Reg[red2_word_t]
    join_scalar_return_ep: Reg[uint1_t]
    direct_scalar_active: Reg[uint1_t]
    ep_scalar_active: Reg[uint1_t]
    equality_atomic_active: Reg[uint1_t]
    equality_launch_active: Reg[uint1_t]
    equality_launch_phase: Reg[uint5_t]
    equality_launch_live_fsp: Reg[uint16_t]
    equality_launch_task_root: Reg[uint16_t]
    equality_launch_normalized_env: Reg[uint17_t]
    equality_launch_needs_bridge: Reg[uint1_t]
    equality_launch_clear_index: Reg[uint17_t]
    equality_launch_clear_remaining: Reg[uint16_t]
    equality_child_active: Reg[uint1_t]
    equality_child_phase: Reg[uint5_t]
    equality_child_task_root: Reg[uint16_t]
    equality_child_join_address: Reg[uint16_t]
    equality_child_left: Reg[uint64_t]
    equality_child_right: Reg[uint64_t]
    equality_child_lambdas: Reg[uint64_t]
    equality_child_descriptor: Reg[uint1_t]
    equality_child_left_word: Reg[red2_word_t]
    equality_child_right_word: Reg[red2_word_t]
    equality_child_left_code_word: Reg[red2_word_t]
    equality_child_build_join_word: Reg[red2_word_t]
    equality_child_build_root: Reg[uint16_t]
    equality_child_build_descriptor: Reg[uint1_t]
    equality_child_build_app_mode: Reg[uint1_t]
    equality_child_build_count: Reg[uint16_t]
    equality_child_build_index: Reg[uint16_t]
    equality_child_build_cursor: Reg[uint17_t]
    equality_child_build_false_root: Reg[uint16_t]
    equality_child_build_if_child_root: Reg[uint17_t]
    equality_child_struct_left_base: Reg[uint64_t]
    equality_child_struct_right_base: Reg[uint64_t]
    equality_child_struct_left_count: Reg[uint16_t]
    equality_child_struct_right_count: Reg[uint16_t]
    equality_continue_active: Reg[uint1_t]
    equality_continue_phase: Reg[uint4_t]
    equality_continue_result_pc: Reg[uint16_t]
    equality_continue_live_fsp: Reg[uint16_t]
    equality_continue_saved_q: Reg[uint64_t]
    equality_continue_child_id: Reg[uint32_t]
    prim0_meta_active: Reg[uint1_t]
    prim0_y_active: Reg[uint1_t]
    prim0_y_needs_scratch: Reg[uint1_t]
    prim0_y_argument_address: Reg[uint16_t]
    prim0_y_target: Reg[uint16_t]
    prim0_y_scratch_word: Reg[red2_word_t]
    join_special_meta_cursor: Reg[uint16_t]
    join_true_literal_id: Reg[uint32_t]
    join_false_literal_id: Reg[uint32_t]
    join_nil_literal_id: Reg[uint32_t]
    join_equal_star_literal_id: Reg[uint32_t]
    join_equal_if_literal_id: Reg[uint32_t]
    join_equality_continue_literal_id: Reg[uint32_t]
    join_equal_stuck_literal_id: Reg[uint32_t]
    join_frame_index: Reg[uint17_t]
    join_control_clear_index: Reg[uint17_t]
    join_parent_is_ep: Reg[uint1_t]
    join_parent_is_recp: Reg[uint1_t]
    join_needs_ep_cache: Reg[uint1_t]
    join_preserve_fsp: Reg[uint1_t]
    join_ep_chase_target: Reg[uint64_t]
    join_ep_hops: Reg[uint16_t]
    join_ep_publish_word: Reg[red2_word_t]
    join_ep_descriptor_hi: Reg[uint64_t]
    join_ep_descriptor_address: Reg[uint16_t]
    join_ep_general_root: Reg[uint1_t]
    join_ep_embedded: Reg[uint1_t]
    join_app_cursor: Reg[uint16_t]
    join_app_operator_address: Reg[uint16_t]
    join_app_shared_target: Reg[uint64_t]
    join_app_second_target: Reg[uint64_t]
    join_app_has_second_target: Reg[uint1_t]
    join_app_preflight_slot: Reg[uint1_t]
    join_app_preflight_root: Reg[uint64_t]
    join_app_preflight_descriptor_hi: Reg[uint64_t]
    join_app_preflight_chase_target: Reg[uint64_t]
    join_app_preflight_hops: Reg[uint16_t]
    join_app_first_write_needed: Reg[uint1_t]
    join_app_second_write_needed: Reg[uint1_t]
    join_app_first_write_word: Reg[red2_word_t]
    join_app_second_write_word: Reg[red2_word_t]
    join_app_rewrite_word: Reg[red2_word_t]
    join_flat_cursor: Reg[uint16_t]
    join_closure_address: Reg[uint16_t]
    join_closure_env: Reg[uint64_t]
    join_closure_code: Reg[uint64_t]
    join_closure_cursor: Reg[uint16_t]
    join_closure_lambda_count: Reg[uint16_t]
    join_closure_body_word: Reg[red2_word_t]
    join_closure_lambda_word: Reg[red2_word_t]
    join_closure_env_cursor: Reg[uint64_t]
    join_closure_env_remaining: Reg[uint64_t]
    join_closure_env_hops: Reg[uint16_t]
    join_closure_destination: Reg[uint16_t]
    join_closure_write_index: Reg[uint16_t]

    committed: uint1_t = 0

    memory_req: graph_ram.p0_in_t
    memory_req.addr = command.address[GRAPH_ADDR_BITS - 1 : 0]
    memory_req.wr_data = command.word
    memory_req.wr_en = 0
    memory_req.valid = 1

    control_req: control_ram.p0_in_t
    control_req.addr = command.address[CONTROL_ADDR_BITS - 1 : 0]
    control_req.wr_data = command.control
    control_req.wr_en = 0
    control_req.valid = 1

    literal_meta_load_valid: uint1_t = command.value != 0
    literal_meta_req: literal_meta_ram.p0_in_t
    literal_meta_req.addr = command.address[LITERAL_META_ADDR_BITS - 1 : 0]
    literal_meta_req.wr_data = red2_literal_meta_t(
        literal_id=command.value,
        scalar_op=command.aux[4:0],
        prim0_role=command.aux[7:5],
        host_op=command.aux[10:8],
        special_flags=command.aux[26:11],
        valid=literal_meta_load_valid,
    )
    literal_meta_req.wr_en = 0
    literal_meta_req.valid = 1

    memory_address_in_range: uint1_t = command.address[15:GRAPH_ADDR_BITS] == 0
    control_address_in_range: uint1_t = command.address[15:CONTROL_ADDR_BITS] == 0
    literal_meta_address_in_range: uint1_t = command.address[15:LITERAL_META_ADDR_BITS] == 0
    pc_in_range: uint1_t = pc[15:GRAPH_ADDR_BITS] == 0

    # EXECUTE is driven from the word captured on the preceding FETCH clock.
    fetched_valid: uint1_t = fetched_word.hi[26]
    fetched_opcode: uint5_t = fetched_word.hi[25:21]
    fetched_head: uint1_t = fetched_word.hi[20]
    fetched_kind: uint2_t = fetched_word.hi[18:17]

    # Request selection is combinational.  Keep every hardware comparison on
    # its own source line: the pinned frontend can otherwise assign duplicate
    # instance names to mixed-width comparisons synthesized inside and/or trees.
    command_is_clock: uint1_t = command.op == CMD_CLOCK
    command_is_load_memory: uint1_t = command.op == CMD_LOAD_MEMORY
    command_is_load_control: uint1_t = command.op == CMD_LOAD_CONTROL
    micro_is_fetch: uint1_t = microstate == MICRO_FETCH
    micro_is_execute: uint1_t = microstate == MICRO_EXECUTE
    micro_is_lookup_read: uint1_t = microstate == MICRO_LOOKUP_READ
    micro_is_lookup_publish: uint1_t = microstate == MICRO_LOOKUP_PUBLISH
    micro_is_lambda_read: uint1_t = microstate == MICRO_LAMBDA_READ
    micro_is_lambda_push: uint1_t = microstate == MICRO_LAMBDA_PUSH
    micro_is_lambda_env: uint1_t = microstate == MICRO_LAMBDA_ENV
    micro_is_lambda_beta_env: uint1_t = microstate == MICRO_LAMBDA_BETA_ENV
    micro_is_lambda_ep_control_read: uint1_t = microstate == MICRO_LAMBDA_EP_CONTROL_READ
    micro_is_lambda_ep_control_pop: uint1_t = microstate == MICRO_LAMBDA_EP_CONTROL_POP
    micro_is_lambda_ep_env: uint1_t = microstate == MICRO_LAMBDA_EP_ENV
    micro_is_lambda_app_control_read: uint1_t = microstate == MICRO_LAMBDA_APP_CONTROL_READ
    micro_is_lambda_app_control_pop: uint1_t = microstate == MICRO_LAMBDA_APP_CONTROL_POP
    micro_is_lambda_app_bridge: uint1_t = microstate == MICRO_LAMBDA_APP_BRIDGE
    micro_is_lambda_app_closure: uint1_t = microstate == MICRO_LAMBDA_APP_CLOSURE
    micro_is_lambda_app_pointer: uint1_t = microstate == MICRO_LAMBDA_APP_POINTER
    micro_is_lambda_env_bridge: uint1_t = microstate == MICRO_LAMBDA_ENV_BRIDGE
    micro_is_lambda_env_binding: uint1_t = microstate == MICRO_LAMBDA_ENV_BINDING
    micro_is_lambda_beta_bridge: uint1_t = microstate == MICRO_LAMBDA_BETA_BRIDGE
    micro_is_lambda_beta_binding: uint1_t = microstate == MICRO_LAMBDA_BETA_BINDING
    micro_is_app_control_read: uint1_t = microstate == MICRO_APP_CONTROL_READ
    micro_is_app_bridge: uint1_t = microstate == MICRO_APP_BRIDGE
    micro_is_app_frame: uint1_t = microstate == MICRO_APP_FRAME
    micro_is_app_join: uint1_t = microstate == MICRO_APP_JOIN
    micro_is_closure_read: uint1_t = microstate == MICRO_CLOSURE_READ
    micro_is_closure_marker: uint1_t = microstate == MICRO_CLOSURE_MARKER
    micro_is_ep_chase: uint1_t = microstate == MICRO_EP_CHASE
    micro_is_ep_forward_publish: uint1_t = microstate == MICRO_EP_FORWARD_PUBLISH
    micro_is_ep_reverse_control_read: uint1_t = microstate == MICRO_EP_REVERSE_CONTROL_READ
    micro_is_ep_reverse_marker: uint1_t = microstate == MICRO_EP_REVERSE_MARKER
    micro_is_ep_reverse_publish: uint1_t = microstate == MICRO_EP_REVERSE_PUBLISH
    micro_is_join_parent_read: uint1_t = microstate == MICRO_JOIN_PARENT_READ
    micro_is_join_ep_target_read: uint1_t = microstate == MICRO_JOIN_EP_TARGET_READ
    micro_is_join_frame_read: uint1_t = microstate == MICRO_JOIN_FRAME_READ
    micro_is_join_tail_read: uint1_t = microstate == MICRO_JOIN_TAIL_READ
    micro_is_join_publish: uint1_t = microstate == MICRO_JOIN_PUBLISH
    micro_is_join_ep_cache: uint1_t = microstate == MICRO_JOIN_EP_CACHE
    micro_is_join_ep_chase: uint1_t = microstate == MICRO_JOIN_EP_CHASE
    micro_is_join_ep_result_write: uint1_t = microstate == MICRO_JOIN_EP_RESULT_WRITE
    micro_is_join_flat_scan: uint1_t = microstate == MICRO_JOIN_FLAT_SCAN
    micro_is_join_closure_code_read: uint1_t = microstate == MICRO_JOIN_CLOSURE_CODE_READ
    micro_is_join_closure_lambda_scan: uint1_t = microstate == MICRO_JOIN_CLOSURE_LAMBDA_SCAN
    micro_is_join_closure_body_read: uint1_t = microstate == MICRO_JOIN_CLOSURE_BODY_READ
    micro_is_join_closure_env_read: uint1_t = microstate == MICRO_JOIN_CLOSURE_ENV_READ
    micro_is_join_closure_write_lambda: uint1_t = microstate == MICRO_JOIN_CLOSURE_WRITE_LAMBDA
    micro_is_join_closure_write_body: uint1_t = microstate == MICRO_JOIN_CLOSURE_WRITE_BODY
    micro_is_join_closure_write_lambda_commit: uint1_t = microstate == MICRO_JOIN_CLOSURE_WRITE_LAMBDA_COMMIT
    micro_is_join_closure_preflight: uint1_t = microstate == MICRO_JOIN_CLOSURE_PREFLIGHT
    micro_is_join_app_scan: uint1_t = microstate == MICRO_JOIN_APP_SCAN
    micro_is_join_app_target_read: uint1_t = microstate == MICRO_JOIN_APP_TARGET_READ
    micro_is_join_app_rewrite_read: uint1_t = microstate == MICRO_JOIN_APP_REWRITE_READ
    micro_is_join_app_rewrite_write: uint1_t = microstate == MICRO_JOIN_APP_REWRITE_WRITE
    micro_is_join_multi_target_read: uint1_t = microstate == MICRO_JOIN_MULTI_TARGET_READ
    micro_is_join_multi_target_chase: uint1_t = microstate == MICRO_JOIN_MULTI_TARGET_CHASE
    micro_is_join_multi_target_advance: uint1_t = microstate == MICRO_JOIN_MULTI_TARGET_ADVANCE
    micro_is_join_multi_target_write_first: uint1_t = microstate == MICRO_JOIN_MULTI_TARGET_WRITE_FIRST
    micro_is_join_multi_target_write_second: uint1_t = microstate == MICRO_JOIN_MULTI_TARGET_WRITE_SECOND
    micro_is_join_control_clear: uint1_t = microstate == MICRO_JOIN_CONTROL_CLEAR
    micro_is_join_prim_meta_scan: uint1_t = microstate == MICRO_JOIN_PRIM_META_SCAN
    micro_is_join_special_meta_scan: uint1_t = microstate == MICRO_JOIN_SPECIAL_META_SCAN
    micro_is_join_special_meta_done: uint1_t = microstate == MICRO_JOIN_SPECIAL_META_DONE
    micro_is_join_scalar_left_read: uint1_t = microstate == MICRO_JOIN_SCALAR_LEFT_READ
    micro_is_rup_validate_rec: uint1_t = microstate == MICRO_RUP_VALIDATE_REC
    micro_is_rup_validate_context: uint1_t = microstate == MICRO_RUP_VALIDATE_CONTEXT
    micro_is_rup_validate_block: uint1_t = microstate == MICRO_RUP_VALIDATE_BLOCK
    micro_is_rup_validate_source: uint1_t = microstate == MICRO_RUP_VALIDATE_SOURCE
    micro_is_rup_write_context: uint1_t = microstate == MICRO_RUP_WRITE_CONTEXT
    micro_is_rup_write_block: uint1_t = microstate == MICRO_RUP_WRITE_BLOCK
    micro_is_rup_zero_push: uint1_t = microstate == MICRO_RUP_ZERO_PUSH
    micro_is_rup_zero_result: uint1_t = microstate == MICRO_RUP_ZERO_RESULT
    micro_is_recp_validate_rec: uint1_t = microstate == MICRO_RECP_VALIDATE_REC
    micro_is_recp_validate_context: uint1_t = microstate == MICRO_RECP_VALIDATE_CONTEXT
    micro_is_recp_validate_block: uint1_t = microstate == MICRO_RECP_VALIDATE_BLOCK
    micro_is_recp_action: uint1_t = microstate == MICRO_RECP_ACTION
    micro_is_recp_recon_scan: uint1_t = microstate == MICRO_RECP_RECON_SCAN
    micro_is_recp_recon_preflight: uint1_t = microstate == MICRO_RECP_RECON_PREFLIGHT
    micro_is_recp_recon_marker: uint1_t = microstate == MICRO_RECP_RECON_MARKER
    micro_is_recp_recon_ubv: uint1_t = microstate == MICRO_RECP_RECON_UBV
    micro_is_recp_recon_copy_read: uint1_t = microstate == MICRO_RECP_RECON_COPY_READ
    micro_is_recp_recon_copy_write: uint1_t = microstate == MICRO_RECP_RECON_COPY_WRITE
    micro_is_recp_recon_path: uint1_t = microstate == MICRO_RECP_RECON_PATH
    micro_is_recp_recon_rup_read: uint1_t = microstate == MICRO_RECP_RECON_RUP_READ
    micro_is_recp_recon_rup_write: uint1_t = microstate == MICRO_RECP_RECON_RUP_WRITE
    micro_is_recp_recon_var_write: uint1_t = microstate == MICRO_RECP_RECON_VAR_WRITE
    micro_is_recp_reverse_bridge: uint1_t = microstate == MICRO_RECP_REVERSE_BRIDGE
    micro_is_recp_reverse_frame: uint1_t = microstate == MICRO_RECP_REVERSE_FRAME
    micro_is_recp_reverse_join: uint1_t = microstate == MICRO_RECP_REVERSE_JOIN
    micro_is_join_recp_rblock_scan: uint1_t = microstate == MICRO_JOIN_RECP_RBLOCK_SCAN
    micro_is_join_recp_rblock_binding_read: uint1_t = microstate == MICRO_JOIN_RECP_RBLOCK_BINDING_READ
    micro_is_join_recp_rblock_body_read: uint1_t = microstate == MICRO_JOIN_RECP_RBLOCK_BODY_READ
    micro_is_struct_result_read: uint1_t = microstate == MICRO_STRUCT_RESULT_READ
    micro_is_struct_recon_saved_q: uint1_t = microstate == MICRO_STRUCT_RECON_SAVED_Q
    micro_is_struct_reverse_control_read: uint1_t = microstate == MICRO_STRUCT_REVERSE_CONTROL_READ
    micro_is_struct_reverse_pop: uint1_t = microstate == MICRO_STRUCT_REVERSE_POP
    join_scalar_active: uint1_t = join_prim_scalar_op != SCALAR_OP_NONE
    join_scalar_binary: uint1_t = join_prim_scalar_op == SCALAR_OP_ADD
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_SUB
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_LT
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_GT
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_LE
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_GE
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_EQ
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_MAX
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_MIN
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_MUL
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_DIV
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_EXPT
    join_scalar_binary = join_scalar_binary or join_prim_scalar_op == SCALAR_OP_MOD
    direction_is_forward: uint1_t = direction == DIRECTION_FORWARD
    opcode_is_app: uint1_t = fetched_opcode == MOP_APP
    opcode_is_closure: uint1_t = fetched_opcode == MOP_CLOSURE
    opcode_is_ep: uint1_t = fetched_opcode == MOP_EP
    opcode_is_join: uint1_t = fetched_opcode == MOP_JOIN
    opcode_is_app_var: uint1_t = fetched_opcode == MOP_APP_VAR
    opcode_is_lambda: uint1_t = fetched_opcode == MOP_LAMBDA
    opcode_is_stop: uint1_t = fetched_opcode == MOP_STOP
    opcode_is_int: uint1_t = fetched_opcode == MOP_INT
    opcode_is_float: uint1_t = fetched_opcode == MOP_FLOAT
    opcode_is_char: uint1_t = fetched_opcode == MOP_CHAR
    opcode_is_sym: uint1_t = fetched_opcode == MOP_SYM
    opcode_is_prim0: uint1_t = fetched_opcode == MOP_PRIM_0
    opcode_is_prim1: uint1_t = fetched_opcode == MOP_PRIM_1
    opcode_is_prim2: uint1_t = fetched_opcode == MOP_PRIM_2
    opcode_is_ubv: uint1_t = fetched_opcode == MOP_UBV
    opcode_is_var: uint1_t = fetched_opcode == MOP_VAR
    opcode_is_rblock: uint1_t = fetched_opcode == MOP_RBLOCK
    opcode_is_rup: uint1_t = fetched_opcode == MOP_RUP
    opcode_is_recp: uint1_t = fetched_opcode == MOP_RECP
    opcode_is_struct: uint1_t = fetched_opcode == MOP_STRUCT
    kind_is_signed: uint1_t = fetched_kind == DATA_SIGNED
    kind_is_float64: uint1_t = fetched_kind == DATA_FLOAT64
    kind_is_literal: uint1_t = fetched_kind == DATA_LITERAL_ID
    passive_opcode: uint1_t = opcode_is_int or opcode_is_float or opcode_is_char
    int_kind_ok: uint1_t = opcode_is_int and kind_is_signed
    float_kind_ok: uint1_t = opcode_is_float and kind_is_float64
    char_kind_ok: uint1_t = opcode_is_char and kind_is_literal
    passive_kind_ok: uint1_t = int_kind_ok or float_kind_ok or char_kind_ok

    if command_is_load_memory:
        if memory_address_in_range:
            memory_req.wr_en = 1
    if command_is_load_control:
        if control_address_in_range:
            control_req.wr_en = 1

    if command_is_clock:
        if micro_is_fetch:
            memory_req.addr = pc[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_execute:
            passive_forward: uint1_t = direction_is_forward and passive_opcode
            sym_forward: uint1_t = direction_is_forward and opcode_is_sym
            prim0_forward: uint1_t = direction_is_forward and opcode_is_prim0
            prim0_nonhead_forward: uint1_t = prim0_forward and not fetched_head
            prim12_opcode_req: uint1_t = opcode_is_prim1 or opcode_is_prim2
            prim12_forward: uint1_t = direction_is_forward and prim12_opcode_req
            app_forward: uint1_t = direction_is_forward and opcode_is_app
            fsp_in_range: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            free_space_low_range: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            free_space_is_end: uint1_t = free_space == GRAPH_WORDS
            free_space_in_range: uint1_t = free_space_low_range or free_space_is_end
            destination: uint17_t = fsp + 1
            frontier_gap: uint17_t = free_space - destination
            frontier_gap_wrapped: uint1_t = frontier_gap[16]
            frontier_gap_nonzero: uint1_t = frontier_gap != 0
            frontier_gap_not_wrapped: uint1_t = frontier_gap_wrapped == 0
            destination_before_frontier: uint1_t = frontier_gap_not_wrapped and frontier_gap_nonzero
            graph_layout_ok: uint1_t = fsp_in_range and free_space_in_range
            graph_layout_ok = graph_layout_ok and destination_before_frontier

            env_low_range: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
            env_is_end: uint1_t = env == GRAPH_WORDS
            env_in_range: uint1_t = env_low_range or env_is_end
            control_top_low_range: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            control_top_is_end: uint1_t = control_top == CONTROL_WORDS
            control_top_in_range: uint1_t = control_top_low_range or control_top_is_end
            control_has_space: uint1_t = control_top_low_range

            can_push_passive: uint1_t = passive_forward and passive_kind_ok
            can_push_passive = can_push_passive and fetched_valid
            can_push_passive = can_push_passive and graph_layout_ok

            sym_payload_nonzero_req: uint1_t = fetched_word.lo != 0
            sym_forward_valid: uint1_t = sym_forward and kind_is_literal
            sym_forward_valid = sym_forward_valid and sym_payload_nonzero_req
            sym_forward_valid = sym_forward_valid and fetched_valid
            can_push_sym: uint1_t = sym_forward_valid and graph_layout_ok

            prim0_payload_nonzero_req: uint1_t = fetched_word.lo != 0
            prim0_forward_valid: uint1_t = prim0_nonhead_forward and kind_is_literal
            prim0_forward_valid = prim0_forward_valid and prim0_payload_nonzero_req
            prim0_forward_valid = prim0_forward_valid and fetched_valid
            can_push_prim0_nonhead: uint1_t = prim0_forward_valid and graph_layout_ok

            prim12_payload_nonzero_req: uint1_t = fetched_word.lo != 0
            prim12_forward_valid: uint1_t = prim12_forward and kind_is_literal
            prim12_forward_valid = prim12_forward_valid and prim12_payload_nonzero_req
            prim12_forward_valid = prim12_forward_valid and fetched_valid
            can_push_prim12: uint1_t = prim12_forward_valid and graph_layout_ok

            sym_reverse_req: uint1_t = direction_is_forward == 0
            sym_reverse_req = sym_reverse_req and opcode_is_sym
            sym_definition_req: uint1_t = fetched_word.hi[16]
            sym_expand_req: uint1_t = sym_reverse_req and fetched_head
            sym_expand_req = sym_expand_req and sym_definition_req
            sym_q_nonzero_req: uint1_t = q != 0
            sym_expand_req = sym_expand_req and sym_q_nonzero_req
            sym_expand_req = sym_expand_req and kind_is_literal
            sym_expand_req = sym_expand_req and sym_payload_nonzero_req
            sym_expand_req = sym_expand_req and fetched_valid
            sym_pc_nonzero_req: uint1_t = pc != 0
            sym_control_top_low_req: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            sym_control_top_end_req: uint1_t = control_top == CONTROL_WORDS
            sym_control_top_valid_req: uint1_t = sym_control_top_low_req or sym_control_top_end_req
            can_expand_sym: uint1_t = sym_expand_req and sym_pc_nonzero_req
            can_expand_sym = can_expand_sym and sym_control_top_valid_req
            can_expand_sym = can_expand_sym and sym_control_top_low_req

            can_push_app: uint1_t = app_forward and fetched_valid
            can_push_app = can_push_app and env_in_range
            can_push_app = can_push_app and control_top_in_range
            can_push_app = can_push_app and control_has_space
            can_push_app = can_push_app and graph_layout_ok

            ubv_forward: uint1_t = direction_is_forward and opcode_is_ubv
            can_push_ubv: uint1_t = ubv_forward and fetched_valid
            can_push_ubv = can_push_ubv and kind_is_signed
            can_push_ubv = can_push_ubv and graph_layout_ok
            phi_wide: uint64_t = phi
            ubv_payload: uint64_t = phi_wide - fetched_word.lo
            ubv_result: red2_word_t = red2_word_t(lo=ubv_payload, hi=112328704)

            write_original_graph_result: uint1_t = can_push_passive or can_push_app
            write_original_graph_result = write_original_graph_result or can_push_sym
            write_original_graph_result = write_original_graph_result or can_push_prim0_nonhead
            write_original_graph_result = write_original_graph_result or can_push_prim12
            if write_original_graph_result:
                memory_req.addr = destination[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = fetched_word
                memory_req.wr_en = 1
            if can_expand_sym:
                sym_next_path_req: uint64_t = pc - 1
                sym_app_hi_req: uint64_t = (fetched_word.hi & 131071) | 70451200
                memory_req.addr = pc[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = red2_word_t(lo=sym_next_path_req, hi=sym_app_hi_req)
                memory_req.wr_en = 1
            if can_push_ubv:
                memory_req.addr = destination[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = ubv_result
                memory_req.wr_en = 1
            if can_push_app:
                control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
                control_req.wr_data = red2_control_t(lo=env, hi=0, tag_hi=1)
                control_req.wr_en = 1
            if can_expand_sym:
                control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
                control_req.wr_data = red2_control_t(
                    lo=env, hi=0, tag_hi=CONTROL_SAVED_DEFINITION_PATH
                )
                control_req.wr_en = 1
        elif micro_is_rup_validate_rec:
            rup_req_index64: uint64_t = rup_index
            rup_req_env64: uint64_t = env
            rup_req_stride64: uint64_t = rup_req_index64 + rup_req_index64
            rup_req_stride64 = rup_req_stride64 + rup_req_index64
            rup_req_rec64: uint64_t = rup_req_env64 + rup_req_stride64
            memory_req.addr = rup_req_rec64[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_rup_validate_context:
            rup_req_index64: uint64_t = rup_index
            rup_req_env64: uint64_t = env
            rup_req_stride64: uint64_t = rup_req_index64 + rup_req_index64
            rup_req_stride64 = rup_req_stride64 + rup_req_index64
            rup_req_context64: uint64_t = rup_req_env64 + rup_req_stride64 + 1
            memory_req.addr = rup_req_context64[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_rup_validate_block:
            rup_req_index64: uint64_t = rup_index
            rup_req_env64: uint64_t = env
            rup_req_stride64: uint64_t = rup_req_index64 + rup_req_index64
            rup_req_stride64 = rup_req_stride64 + rup_req_index64
            rup_req_block_slot64: uint64_t = rup_req_env64 + rup_req_stride64 + 2
            memory_req.addr = rup_req_block_slot64[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_rup_validate_source:
            rup_req_source_offset: uint16_t = rup_count - 1 - rup_index
            rup_req_source17: uint17_t = rup_block + rup_req_source_offset
            memory_req.addr = rup_req_source17[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_rup_write_context:
            rup_req_index64: uint64_t = rup_index
            rup_req_env64: uint64_t = env
            rup_req_stride64: uint64_t = rup_req_index64 + rup_req_index64
            rup_req_stride64 = rup_req_stride64 + rup_req_index64
            rup_req_context64: uint64_t = rup_req_env64 + rup_req_stride64 + 1
            rup_req_env_payload: uint64_t = env
            memory_req.addr = rup_req_context64[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=rup_req_env_payload, hi=67239936)
            memory_req.wr_en = 1
        elif micro_is_rup_write_block:
            rup_req_index64: uint64_t = rup_index
            rup_req_env64: uint64_t = env
            rup_req_stride64: uint64_t = rup_req_index64 + rup_req_index64
            rup_req_stride64 = rup_req_stride64 + rup_req_index64
            rup_req_block_slot64: uint64_t = rup_req_env64 + rup_req_stride64 + 2
            rup_req_block_payload: uint64_t = rup_block
            memory_req.addr = rup_req_block_slot64[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=rup_req_block_payload, hi=67239936)
            memory_req.wr_en = 1
        elif micro_is_rup_zero_push:
            rup_req_env_payload: uint64_t = env
            control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(lo=rup_req_env_payload, hi=0, tag_hi=CONTROL_ADDRESS)
            control_req.wr_en = 1
        elif micro_is_rup_zero_result:
            rup_req_result_destination: uint17_t = fsp + 1
            memory_req.addr = rup_req_result_destination[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = fetched_word
            memory_req.wr_en = 1
        elif micro_is_recp_validate_rec:
            memory_req.addr = fetched_word.lo[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_recp_validate_context:
            recp_context_address_req: uint17_t = fetched_word.lo[16:0] + 1
            memory_req.addr = recp_context_address_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_recp_validate_block:
            recp_block_address_req: uint17_t = fetched_word.lo[16:0] + 2
            memory_req.addr = recp_block_address_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_recp_action:
            recp_action_forward: uint1_t = direction == DIRECTION_FORWARD
            if recp_action_forward:
                if fetched_word.hi[20]:
                    recp_context_payload_req: uint64_t = recp_context
                    recp_marker_address_req: uint17_t = free_space - 1
                    memory_req.addr = recp_marker_address_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=recp_context_payload_req, hi=113377280)
                    memory_req.wr_en = 1
                else:
                    recp_result_destination_req: uint17_t = fsp + 1
                    memory_req.addr = recp_result_destination_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = fetched_word
                    memory_req.wr_en = 1
            else:
                recp_binding_payload_req: uint64_t = recp_binding
                memory_req.addr = pc[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = red2_word_t(lo=recp_binding_payload_req, hi=69337088)
                memory_req.wr_en = 1
                recp_context_payload_req: uint64_t = recp_context
                control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
                control_req.wr_data = red2_control_t(
                    lo=recp_context_payload_req, hi=0, tag_hi=CONTROL_ADDRESS
                )
                control_req.wr_en = 1
        elif micro_is_recp_recon_scan:
            recp_scan_count64_req: uint64_t = recp_count
            recp_scan_address64_req: uint64_t = recp_block + recp_scan_count64_req
            memory_req.addr = recp_scan_address64_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_recp_recon_marker:
            recp_parent_payload_req: uint64_t = recp_parent_environment
            recp_marker_address_req: uint17_t = free_space - 1
            memory_req.addr = recp_marker_address_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=recp_parent_payload_req, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_recp_recon_ubv:
            recp_ubv_address_req: uint17_t = free_space - 1
            recp_ubv_payload_req: uint64_t = phi + 1
            memory_req.addr = recp_ubv_address_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=recp_ubv_payload_req, hi=109182976)
            memory_req.wr_en = 1
        elif micro_is_recp_recon_copy_read:
            recp_copy_index64_req: uint64_t = recp_index
            recp_copy_source64_req: uint64_t = recp_block + recp_copy_index64_req
            memory_req.addr = recp_copy_source64_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_recp_recon_copy_write:
            recp_copy_destination_req: uint17_t = fsp + 1
            memory_req.addr = recp_copy_destination_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = recp_copy_word
            memory_req.wr_en = 1
        elif micro_is_recp_recon_path:
            recp_replacement_payload_req: uint64_t = recp_replacement
            control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(
                lo=recp_replacement_payload_req, hi=0, tag_hi=CONTROL_ADDRESS
            )
            control_req.wr_en = 1
        elif micro_is_recp_recon_rup_read:
            recp_rup_count64_req: uint64_t = recp_count
            recp_rup_address64_req: uint64_t = recp_block + recp_rup_count64_req
            memory_req.addr = recp_rup_address64_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_recp_recon_rup_write:
            recp_rup_destination_req: uint17_t = fsp + 1
            memory_req.addr = recp_rup_destination_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = recp_rup_word
            memory_req.wr_en = 1
        elif micro_is_recp_recon_var_write:
            recp_var_destination_req: uint17_t = fsp + 1
            recp_selected_payload_req: uint64_t = recp_selected
            memory_req.addr = recp_var_destination_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=recp_selected_payload_req, hi=112328704)
            memory_req.wr_en = 1
        elif micro_is_recp_reverse_bridge:
            recp_reverse_parent_wide_req: uint64_t = recp_reverse_parent_env
            memory_req.addr = recp_reverse_entry_env[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=recp_reverse_parent_wide_req, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_recp_reverse_frame:
            recp_reverse_frame_env_wide_req: uint64_t = recp_reverse_entry_env
            recp_reverse_frame_lo_req: uint64_t = (
                recp_reverse_frame_env_wide_req | (recp_reverse_frame_env_wide_req << 32)
            )
            recp_reverse_frame_prim_req: uint64_t = prim_id
            recp_reverse_frame_fire_req: uint64_t = fire
            recp_reverse_frame_hi_req: uint64_t = (
                recp_reverse_frame_prim_req | (recp_reverse_frame_fire_req << 32)
            )
            control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(
                lo=recp_reverse_frame_lo_req,
                hi=recp_reverse_frame_hi_req,
                tag_hi=CONTROL_SUBGRAPH,
            )
            control_req.wr_en = 1
        elif micro_is_recp_reverse_join:
            recp_reverse_join_address_req: uint17_t = fsp + 1
            recp_reverse_parent_pc_wide_req: uint64_t = pc
            recp_reverse_join_hi_req: uint64_t = 77725696
            if fire != 0:
                recp_reverse_join_hi_req = 78315521
            memory_req.addr = recp_reverse_join_address_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(
                lo=recp_reverse_parent_pc_wide_req, hi=recp_reverse_join_hi_req
            )
            memory_req.wr_en = 1
        elif micro_is_struct_result_read:
            memory_req.addr = fsp[GRAPH_ADDR_BITS - 1 : 0]
            struct_control_address_req: uint17_t = control_top - 1
            control_req.addr = struct_control_address_req[CONTROL_ADDR_BITS - 1 : 0]
        elif micro_is_struct_recon_saved_q:
            struct_recon_destination_req: uint17_t = fsp + 1
            memory_req.addr = struct_recon_destination_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = fetched_word
            memory_req.wr_en = 1
            control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(
                lo=q, hi=0, tag_hi=CONTROL_SAVED_QUANTUM
            )
            control_req.wr_en = 1
        elif micro_is_struct_reverse_control_read:
            struct_saved_q_address_req: uint17_t = control_top - 1
            control_req.addr = struct_saved_q_address_req[CONTROL_ADDR_BITS - 1 : 0]
        elif micro_is_struct_reverse_pop:
            struct_saved_q_pop_address_req: uint17_t = control_top - 1
            control_req.addr = struct_saved_q_pop_address_req[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
            control_req.wr_en = 1
        elif micro_is_lookup_read:
            memory_req.addr = lookup_address[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_lookup_publish:
            lookup_fsp_in_range: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            lookup_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            lookup_free_end: uint1_t = free_space == GRAPH_WORDS
            lookup_free_valid: uint1_t = lookup_free_low or lookup_free_end
            lookup_destination: uint17_t = fsp + 1
            lookup_gap: uint17_t = free_space - lookup_destination
            lookup_gap_wrapped: uint1_t = lookup_gap[16]
            lookup_gap_nonzero: uint1_t = lookup_gap != 0
            lookup_gap_not_wrapped: uint1_t = lookup_gap_wrapped == 0
            lookup_before_frontier: uint1_t = lookup_gap_not_wrapped and lookup_gap_nonzero
            lookup_graph_ok: uint1_t = lookup_fsp_in_range and lookup_free_valid
            lookup_graph_ok = lookup_graph_ok and lookup_before_frontier
            if lookup_graph_ok:
                memory_req.addr = lookup_destination[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = lookup_word
                memory_req.wr_en = 1
        elif micro_is_lambda_read:
            memory_req.addr = fsp[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_lambda_push:
            lambda_destination: uint17_t = fsp + 1
            memory_req.addr = lambda_destination[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = fetched_word
            memory_req.wr_en = 1
        elif micro_is_lambda_env_bridge:
            lambda_env_parent_wide: uint64_t = env
            lambda_env_bridge_address: uint17_t = free_space - 1
            memory_req.addr = lambda_env_bridge_address[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=lambda_env_parent_wide, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_lambda_env_binding:
            lambda_env_needs_bridge_req: uint1_t = free_space != env
            lambda_env_count_req: uint17_t = 1
            if lambda_env_needs_bridge_req:
                lambda_env_count_req = 2
            lambda_env_base_req: uint17_t = free_space - lambda_env_count_req
            lambda_phi_wide: uint64_t = phi
            memory_req.addr = lambda_env_base_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=lambda_phi_wide, hi=109182976)
            memory_req.wr_en = 1
        elif micro_is_lambda_beta_bridge:
            lambda_beta_parent_wide: uint64_t = env
            lambda_beta_bridge_address: uint17_t = free_space - 1
            memory_req.addr = lambda_beta_bridge_address[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=lambda_beta_parent_wide, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_lambda_beta_binding:
            lambda_beta_needs_bridge_req: uint1_t = free_space != env
            lambda_beta_count_req: uint17_t = 1
            if lambda_beta_needs_bridge_req:
                lambda_beta_count_req = 2
            lambda_beta_base_req: uint17_t = free_space - lambda_beta_count_req
            memory_req.addr = lambda_beta_base_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = lambda_word
            memory_req.wr_en = 1
        elif micro_is_lambda_ep_control_read:
            lambda_ep_control_address: uint17_t = control_top - 1
            control_req.addr = lambda_ep_control_address[CONTROL_ADDR_BITS - 1 : 0]
        elif micro_is_lambda_ep_control_pop:
            lambda_ep_control_pop_address: uint17_t = control_top - 1
            control_req.addr = lambda_ep_control_pop_address[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
            control_req.wr_en = 1
        elif micro_is_lambda_app_control_read:
            lambda_app_control_address: uint17_t = control_top - 1
            control_req.addr = lambda_app_control_address[CONTROL_ADDR_BITS - 1 : 0]
        elif micro_is_lambda_app_control_pop:
            lambda_app_control_pop_address: uint17_t = control_top - 1
            control_req.addr = lambda_app_control_pop_address[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
            control_req.wr_en = 1
        elif micro_is_lambda_app_bridge:
            lambda_app_parent_wide: uint64_t = env
            lambda_app_bridge_address: uint17_t = free_space - 1
            memory_req.addr = lambda_app_bridge_address[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=lambda_app_parent_wide, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_lambda_app_closure:
            lambda_app_needs_bridge_req: uint1_t = free_space != env
            lambda_app_count_req: uint17_t = 2
            if app_rblock_active:
                lambda_app_count_req = 3
            if lambda_app_needs_bridge_req:
                lambda_app_count_req = lambda_app_count_req + 1
            lambda_app_base_req: uint17_t = free_space - lambda_app_count_req
            memory_req.addr = lambda_app_base_req[GRAPH_ADDR_BITS - 1 : 0]
            if app_rblock_active:
                rblock_binding_plus_one_req: uint64_t = fetched_word.lo + 1
                memory_req.wr_data = red2_word_t(lo=rblock_binding_plus_one_req, hi=107085824)
            else:
                lambda_app_path_wide: uint64_t = lambda_path
                memory_req.wr_data = red2_word_t(lo=lambda_app_path_wide, hi=73531392)
            memory_req.wr_en = 1
        elif micro_is_lambda_app_pointer:
            lambda_app_needs_bridge_pointer: uint1_t = free_space != env
            lambda_app_count_pointer: uint17_t = 2
            if app_rblock_active:
                lambda_app_count_pointer = 3
            if lambda_app_needs_bridge_pointer:
                lambda_app_count_pointer = lambda_app_count_pointer + 1
            lambda_app_base_pointer: uint17_t = free_space - lambda_app_count_pointer
            lambda_app_pointer_address: uint17_t = lambda_app_base_pointer + 1
            if app_rblock_active:
                rblock_second_none_req: uint1_t = lambda_path != 0
                if rblock_second_none_req:
                    lambda_app_pointer_address = lambda_app_base_pointer + 2
            memory_req.addr = lambda_app_pointer_address[GRAPH_ADDR_BITS - 1 : 0]
            if app_rblock_active:
                memory_req.wr_data = red2_word_t(lo=0, hi=67108864)
            else:
                memory_req.wr_data = lambda_word
            memory_req.wr_en = 1
        elif micro_is_app_control_read:
            app_control_address_req: uint17_t = control_top - 1
            control_req.addr = app_control_address_req[CONTROL_ADDR_BITS - 1 : 0]
        elif micro_is_app_bridge:
            app_parent_env_wide: uint64_t = app_parent_env
            memory_req.addr = app_entry_env[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=app_parent_env_wide, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_app_frame:
            app_frame_address_req: uint17_t = control_top - 1
            app_frame_env_wide: uint64_t = app_entry_env
            app_frame_lo: uint64_t = app_frame_env_wide | (app_frame_env_wide << 32)
            app_frame_prim_wide: uint64_t = prim_id
            app_frame_fire_wide: uint64_t = fire
            app_frame_hi: uint64_t = app_frame_prim_wide | (app_frame_fire_wide << 32)
            control_req.addr = app_frame_address_req[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(
                lo=app_frame_lo,
                hi=app_frame_hi,
                tag_hi=CONTROL_SUBGRAPH,
            )
            control_req.wr_en = 1
        elif micro_is_app_join:
            app_join_address_req: uint17_t = fsp + 1
            app_parent_pc_wide: uint64_t = app_parent_pc
            app_join_hi: uint64_t = 77725696
            app_saved_fire_active: uint1_t = fire != 0
            if app_saved_fire_active:
                app_join_hi = 78315521
            memory_req.addr = app_join_address_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=app_parent_pc_wide, hi=app_join_hi)
            memory_req.wr_en = 1
        elif micro_is_closure_read:
            closure_code_address_req: uint17_t = pc + 1
            memory_req.addr = closure_code_address_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_closure_marker:
            closure_marker_address_req: uint17_t = free_space - 1
            memory_req.addr = closure_marker_address_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=fetched_word.lo, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_ep_chase:
            memory_req.addr = ep_target[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_ep_forward_publish:
            ep_destination_req: uint17_t = fsp + 1
            memory_req.addr = ep_destination_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = fetched_word
            memory_req.wr_en = 1
            control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(lo=env, hi=0, tag_hi=CONTROL_ADDRESS)
            control_req.wr_en = 1
        elif micro_is_ep_reverse_control_read:
            ep_reverse_control_address_req: uint17_t = control_top - 1
            control_req.addr = ep_reverse_control_address_req[CONTROL_ADDR_BITS - 1 : 0]
        elif micro_is_ep_reverse_marker:
            ep_reverse_marker_address_req: uint17_t = free_space - 1
            ep_reverse_caller_wide: uint64_t = ep_caller_path
            memory_req.addr = ep_reverse_marker_address_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = red2_word_t(lo=ep_reverse_caller_wide, hi=113377280)
            memory_req.wr_en = 1
        elif micro_is_ep_reverse_publish:
            if stop_cleanup_active:
                stop_cleanup_pop_address_req: uint17_t = control_top - 1
                control_req.addr = stop_cleanup_pop_address_req[CONTROL_ADDR_BITS - 1 : 0]
                control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
                control_req.wr_en = 1
            elif app_definition_active:
                memory_req.addr = app_parent_pc[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = red2_word_t(lo=0, hi=81788928)
                memory_req.wr_en = 1
                if app_definition_pop_saved:
                    app_definition_pop_address_req: uint17_t = control_top - 1
                    control_req.addr = app_definition_pop_address_req[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
                    control_req.wr_en = 1
            else:
                memory_req.addr = pc[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = ep_publish_word
                memory_req.wr_en = 1
                ep_reverse_pop_address_req: uint17_t = control_top - 1
                control_req.addr = ep_reverse_pop_address_req[CONTROL_ADDR_BITS - 1 : 0]
                control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
                control_req.wr_en = 1
        elif micro_is_join_recp_rblock_scan:
            memory_req.addr = join_recp_rblock_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_recp_rblock_binding_read:
            memory_req.addr = join_recp_binding_root[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_recp_rblock_body_read:
            memory_req.addr = join_recp_rblock_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_parent_read:
            memory_req.addr = join_parent_address[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_ep_target_read:
            memory_req.addr = join_ep_target[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_frame_read:
            join_frame_address_req: uint17_t = join_control_clear_index - 1
            control_req.addr = join_frame_address_req[CONTROL_ADDR_BITS - 1 : 0]
        elif micro_is_join_tail_read:
            memory_req.addr = join_result_address[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_scalar_left_read:
            if equality_continue_active:
                if equality_continue_phase == 0:
                    memory_req.addr = join_result_address[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_continue_phase == 1:
                    equality_continue_eq_frame_req: uint17_t = join_frame_index - 1
                    control_req.addr = equality_continue_eq_frame_req[CONTROL_ADDR_BITS - 1 : 0]
                elif equality_continue_phase == 2:
                    equality_continue_saved_q_req: uint17_t = join_frame_index - 2
                    control_req.addr = equality_continue_saved_q_req[CONTROL_ADDR_BITS - 1 : 0]
                elif equality_continue_phase == 3:
                    memory_req.addr = join_parent_address[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_continue_child_id, hi=90570752)
                    memory_req.wr_en = 1
                elif equality_continue_phase == 4:
                    memory_req.addr = equality_continue_result_pc[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_continue_child_id, hi=91619328)
                    memory_req.wr_en = 1
                elif equality_continue_phase == 5:
                    control_req.addr = join_frame_index[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
                    control_req.wr_en = 1
                elif equality_continue_phase == 6:
                    equality_continue_eq_clear_req: uint17_t = join_frame_index - 1
                    control_req.addr = equality_continue_eq_clear_req[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
                    control_req.wr_en = 1
                elif equality_continue_phase == 7:
                    equality_continue_q_clear_req: uint17_t = join_frame_index - 2
                    control_req.addr = equality_continue_q_clear_req[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
                    control_req.wr_en = 1
            elif equality_child_active:
                if equality_child_phase == 0:
                    memory_req.addr = equality_child_task_root[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 1:
                    equality_child_right_field_req: uint17_t = equality_child_task_root + 1
                    memory_req.addr = equality_child_right_field_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 2:
                    equality_child_lambda_field_req: uint17_t = equality_child_task_root + 2
                    memory_req.addr = equality_child_lambda_field_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 3:
                    equality_child_descriptor_field_req: uint17_t = equality_child_task_root + 3
                    memory_req.addr = equality_child_descriptor_field_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 4:
                    memory_req.addr = equality_child_join_address[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 5:
                    memory_req.addr = equality_child_left[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 6:
                    memory_req.addr = equality_child_left[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 7:
                    memory_req.addr = equality_child_right[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 8:
                    memory_req.addr = equality_child_right[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 10:
                    equality_child_result_addr_req: uint17_t = equality_child_join_address + 1
                    memory_req.addr = equality_child_result_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = join_publish_word
                    memory_req.wr_en = 1
                elif equality_child_phase == 11:
                    equality_child_left_code_addr_req: uint17_t = equality_child_left + 1
                    memory_req.addr = equality_child_left_code_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 12:
                    equality_child_right_code_addr_req: uint17_t = equality_child_right + 1
                    memory_req.addr = equality_child_right_code_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 13:
                    memory_req.addr = equality_child_left[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 14:
                    memory_req.addr = equality_child_right[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 15:
                    memory_req.addr = equality_child_build_cursor[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_child_left, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_child_phase == 16:
                    equality_child_build_addr16: uint17_t = equality_child_build_cursor + 1
                    memory_req.addr = equality_child_build_addr16[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_child_right, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_child_phase == 17:
                    equality_child_build_addr17: uint17_t = equality_child_build_cursor + 2
                    memory_req.addr = equality_child_build_addr17[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_child_lambdas, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_child_phase == 18:
                    equality_child_build_addr18: uint17_t = equality_child_build_cursor + 3
                    memory_req.addr = equality_child_build_addr18[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_child_build_descriptor, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_child_phase == 19:
                    equality_child_build_addr19: uint17_t = equality_child_build_cursor + 4
                    memory_req.addr = equality_child_build_addr19[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=join_equal_star_literal_id, hi=93716480)
                    memory_req.wr_en = 1
                elif equality_child_phase == 20:
                    memory_req.addr = equality_child_build_cursor[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=join_true_literal_id, hi=91619328)
                    memory_req.wr_en = 1
                elif equality_child_phase == 21:
                    equality_child_build_addr21: uint17_t = equality_child_build_cursor + 1
                    memory_req.addr = equality_child_build_addr21[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=join_false_literal_id, hi=91619328)
                    memory_req.wr_en = 1
                elif equality_child_phase == 22:
                    memory_req.addr = equality_child_build_cursor[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_child_build_false_root, hi=69337088)
                    memory_req.wr_en = 1
                elif equality_child_phase == 23:
                    equality_child_build_addr23: uint17_t = equality_child_build_cursor + 1
                    memory_req.addr = equality_child_build_addr23[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_child_build_root, hi=69337088)
                    memory_req.wr_en = 1
                elif equality_child_phase == 24:
                    equality_child_build_addr24: uint17_t = equality_child_build_cursor + 2
                    memory_req.addr = equality_child_build_addr24[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_child_build_if_child_root, hi=69337088)
                    memory_req.wr_en = 1
                elif equality_child_phase == 25:
                    equality_child_build_addr25: uint17_t = equality_child_build_cursor + 3
                    memory_req.addr = equality_child_build_addr25[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=join_equal_if_literal_id, hi=93716480)
                    memory_req.wr_en = 1
                elif equality_child_phase == 26:
                    memory_req.addr = equality_child_build_cursor[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = equality_child_build_join_word
                    memory_req.wr_en = 1
                elif equality_child_phase == 27:
                    equality_child_struct_left_cursor_req: uint64_t = equality_child_struct_left_base + equality_child_struct_left_count
                    memory_req.addr = equality_child_struct_left_cursor_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 28:
                    equality_child_struct_right_cursor_req: uint64_t = equality_child_struct_right_base + equality_child_struct_right_count
                    memory_req.addr = equality_child_struct_right_cursor_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 30:
                    equality_child_app_left_cursor_req: uint64_t = equality_child_struct_left_base + equality_child_struct_left_count
                    memory_req.addr = equality_child_app_left_cursor_req[GRAPH_ADDR_BITS - 1 : 0]
                elif equality_child_phase == 31:
                    equality_child_app_right_cursor_req: uint64_t = equality_child_struct_right_base + equality_child_struct_right_count
                    memory_req.addr = equality_child_app_right_cursor_req[GRAPH_ADDR_BITS - 1 : 0]
            elif equality_launch_active:
                equality_launch_control_limit_req: uint17_t = join_frame_index + 3
                equality_launch_live17_req: uint17_t = equality_launch_live_fsp
                equality_launch_parent_req: uint17_t = equality_launch_live17_req + 6
                equality_launch_join_req: uint17_t = equality_launch_live17_req + 7
                if equality_launch_phase == 0:
                    if equality_launch_clear_remaining != 0:
                        equality_launch_clear_address_req: uint17_t = equality_launch_clear_index - 1
                        control_req.addr = equality_launch_clear_address_req[CONTROL_ADDR_BITS - 1 : 0]
                        control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
                        control_req.wr_en = 1
                elif equality_launch_phase == 1:
                    equality_launch_saved_q_req: uint64_t = q - 1
                    control_req.addr = join_frame_index[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(
                        lo=equality_launch_saved_q_req, hi=0, tag_hi=CONTROL_SAVED_QUANTUM
                    )
                    control_req.wr_en = 1
                elif equality_launch_phase == 2:
                    equality_launch_result_wide_req: uint64_t = join_parent_address
                    equality_launch_live_wide_req: uint64_t = equality_launch_live_fsp
                    equality_launch_frame_lo_req: uint64_t = (
                        equality_launch_result_wide_req | (equality_launch_live_wide_req << 32)
                    )
                    equality_launch_eq_frame_addr_req: uint17_t = join_frame_index + 1
                    control_req.addr = equality_launch_eq_frame_addr_req[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(
                        lo=equality_launch_frame_lo_req, hi=0, tag_hi=CONTROL_EQUALITY
                    )
                    control_req.wr_en = 1
                elif equality_launch_phase == 3:
                    equality_launch_env_wide_req: uint64_t = equality_launch_normalized_env
                    equality_launch_subgraph_lo_req: uint64_t = (
                        equality_launch_env_wide_req | (equality_launch_env_wide_req << 32)
                    )
                    equality_launch_cont_wide_req: uint64_t = join_equality_continue_literal_id
                    equality_launch_subgraph_hi_req: uint64_t = (
                        equality_launch_cont_wide_req | (1 << 32)
                    )
                    equality_launch_subgraph_addr_req: uint17_t = join_frame_index + 2
                    control_req.addr = equality_launch_subgraph_addr_req[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(
                        lo=equality_launch_subgraph_lo_req,
                        hi=equality_launch_subgraph_hi_req,
                        tag_hi=CONTROL_SUBGRAPH,
                    )
                    control_req.wr_en = 1
                elif equality_launch_phase == 4:
                    memory_req.addr = join_parent_address[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = join_publish_word
                    memory_req.wr_en = 1
                elif equality_launch_phase == 5:
                    equality_launch_left_payload_req: uint64_t = join_parent_address + 1
                    memory_req.addr = equality_launch_task_root[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_launch_left_payload_req, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_launch_phase == 6:
                    equality_launch_right_addr_req: uint17_t = equality_launch_task_root + 1
                    equality_launch_right_payload_req: uint64_t = join_parent_address
                    memory_req.addr = equality_launch_right_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_launch_right_payload_req, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_launch_phase == 7:
                    equality_launch_lambda_addr_req: uint17_t = equality_launch_task_root + 2
                    memory_req.addr = equality_launch_lambda_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=0, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_launch_phase == 8:
                    equality_launch_descriptor_addr_req: uint17_t = equality_launch_task_root + 3
                    memory_req.addr = equality_launch_descriptor_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=1, hi=84017152)
                    memory_req.wr_en = 1
                elif equality_launch_phase == 9:
                    equality_launch_primitive_addr_req: uint17_t = equality_launch_task_root + 4
                    equality_launch_star_wide_req: uint64_t = join_equal_star_literal_id
                    memory_req.addr = equality_launch_primitive_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_launch_star_wide_req, hi=93716480)
                    memory_req.wr_en = 1
                elif equality_launch_phase == 10:
                    equality_launch_parent_addr_req: uint17_t = equality_launch_task_root + 5
                    equality_launch_task_wide_req: uint64_t = equality_launch_task_root
                    memory_req.addr = equality_launch_parent_addr_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_launch_task_wide_req, hi=69337088)
                    memory_req.wr_en = 1
                elif equality_launch_phase == 11:
                    equality_launch_join_parent_wide_req: uint64_t = equality_launch_parent_req
                    memory_req.addr = equality_launch_join_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_launch_join_parent_wide_req, hi=77791233)
                    memory_req.wr_en = 1
                elif equality_launch_phase == 12:
                    equality_launch_bridge_parent_req: uint64_t = join_frame_env
                    memory_req.addr = equality_launch_normalized_env[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = red2_word_t(lo=equality_launch_bridge_parent_req, hi=113377280)
                    memory_req.wr_en = equality_launch_needs_bridge
            elif prim0_y_active:
                memory_req.addr = prim0_y_argument_address[GRAPH_ADDR_BITS - 1 : 0]
            else:
                join_scalar_left_address_req: uint17_t = join_parent_address + 1
                memory_req.addr = join_scalar_left_address_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_publish:
            memory_req.addr = join_parent_address[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_publish_word
            if join_parent_is_recp:
                join_recp_root_wide_req: uint64_t = join_published_root
                memory_req.wr_data = red2_word_t(lo=join_recp_root_wide_req, hi=69337088)
            join_publish_preflight_ready: uint1_t = join_scalar_preflight_done or not join_scalar_active
            # Reverse-EP fire==1 borrows the JOIN scalar evaluator only for
            # transactional preflight.  Its parent write is serialized later by
            # MICRO_EP_REVERSE_PUBLISH together with the caller-path pop.
            if ep_scalar_active:
                memory_req.wr_en = 0
            else:
                memory_req.wr_en = join_publish_preflight_ready
        elif micro_is_join_control_clear:
            join_clear_address_req: uint17_t = join_control_clear_index - 1
            control_req.addr = join_clear_address_req[CONTROL_ADDR_BITS - 1 : 0]
            control_req.wr_data = red2_control_t(lo=0, hi=0, tag_hi=0)
            control_req.wr_en = 1
        elif micro_is_join_ep_cache:
            memory_req.addr = join_ep_target[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_cache_word
            memory_req.wr_en = 1
        elif micro_is_join_ep_chase:
            memory_req.addr = join_ep_chase_target[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_ep_result_write:
            memory_req.addr = join_ep_descriptor_address[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_ep_publish_word
            join_ep_write_preflight_ready: uint1_t = join_scalar_preflight_done or not join_scalar_active
            memory_req.wr_en = join_ep_write_preflight_ready
        elif micro_is_join_app_scan:
            memory_req.addr = join_app_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_app_target_read:
            memory_req.addr = join_app_shared_target[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_multi_target_read:
            memory_req.addr = join_app_preflight_root[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_multi_target_chase:
            memory_req.addr = join_app_preflight_chase_target[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_multi_target_write_first:
            memory_req.addr = join_app_shared_target[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_app_first_write_word
            memory_req.wr_en = 1
        elif micro_is_join_multi_target_write_second:
            memory_req.addr = join_app_second_target[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_app_second_write_word
            memory_req.wr_en = 1
        elif micro_is_join_special_meta_done:
            if prim0_y_active:
                prim0_y_recursive_payload_req: uint64_t = prim0_y_argument_address
                memory_req.addr = fsp[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = red2_word_t(lo=prim0_y_recursive_payload_req, hi=69337088)
                memory_req.wr_en = 1
                if prim0_y_needs_scratch:
                    control_req.addr = control_top[CONTROL_ADDR_BITS - 1 : 0]
                    control_req.wr_data = red2_control_t(lo=env, hi=0, tag_hi=CONTROL_ADDRESS)
                    control_req.wr_en = 1
            elif prim0_meta_active:
                prim0_meta_fsp_ok_req: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                prim0_meta_free_low_req: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                prim0_meta_free_end_req: uint1_t = free_space == GRAPH_WORDS
                prim0_meta_free_valid_req: uint1_t = prim0_meta_free_low_req or prim0_meta_free_end_req
                prim0_meta_destination_req: uint17_t = fsp + 1
                prim0_meta_gap_req: uint17_t = free_space - prim0_meta_destination_req
                prim0_meta_gap_wrapped_req: uint1_t = prim0_meta_gap_req[16]
                prim0_meta_gap_nonzero_req: uint1_t = prim0_meta_gap_req != 0
                prim0_meta_gap_ok_req: uint1_t = prim0_meta_gap_wrapped_req == 0
                prim0_meta_gap_ok_req = prim0_meta_gap_ok_req and prim0_meta_gap_nonzero_req
                prim0_meta_can_push_req: uint1_t = prim0_meta_fsp_ok_req and prim0_meta_free_valid_req
                prim0_meta_can_push_req = prim0_meta_can_push_req and prim0_meta_gap_ok_req
                if prim0_meta_can_push_req:
                    memory_req.addr = prim0_meta_destination_req[GRAPH_ADDR_BITS - 1 : 0]
                    memory_req.wr_data = fetched_word
                    memory_req.wr_en = 1
        elif micro_is_join_special_meta_scan:
            if prim0_y_active:
                prim0_y_scratch_address_req: uint17_t = fsp + 1
                memory_req.addr = prim0_y_scratch_address_req[GRAPH_ADDR_BITS - 1 : 0]
                memory_req.wr_data = prim0_y_scratch_word
                memory_req.wr_en = 1
        elif micro_is_join_flat_scan:
            memory_req.addr = join_flat_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_closure_code_read:
            join_closure_code_slot_req: uint17_t = join_closure_address + 1
            memory_req.addr = join_closure_code_slot_req[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_closure_lambda_scan:
            memory_req.addr = join_closure_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_closure_body_read:
            memory_req.addr = join_closure_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_closure_env_read:
            memory_req.addr = join_closure_env_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_closure_write_lambda:
            memory_req.addr = join_closure_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_closure_write_lambda_commit:
            join_closure_lambda_destination_req: uint17_t = join_closure_destination + join_closure_write_index
            memory_req.addr = join_closure_lambda_destination_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_closure_lambda_word
            memory_req.wr_en = 1
        elif micro_is_join_closure_write_body:
            join_closure_body_destination_req: uint17_t = join_closure_destination + join_closure_lambda_count
            memory_req.addr = join_closure_body_destination_req[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_closure_body_word
            memory_req.wr_en = 1
        elif micro_is_join_app_rewrite_read:
            memory_req.addr = join_app_cursor[GRAPH_ADDR_BITS - 1 : 0]
        elif micro_is_join_app_rewrite_write:
            memory_req.addr = join_app_cursor[GRAPH_ADDR_BITS - 1 : 0]
            memory_req.wr_data = join_app_rewrite_word
            memory_req.wr_en = 1

    if command.op == CMD_LOAD_LITERAL_META:
        literal_meta_req.wr_en = literal_meta_address_in_range
    elif micro_is_join_prim_meta_scan:
        literal_meta_req.addr = join_prim_meta_cursor[LITERAL_META_ADDR_BITS - 1 : 0]
    elif micro_is_join_special_meta_scan:
        literal_meta_req.addr = join_special_meta_cursor[LITERAL_META_ADDR_BITS - 1 : 0]

    memory_out = graph_ram(memory_req)
    control_out = control_ram(control_req)
    literal_meta_out = literal_meta_ram(literal_meta_req)

    if command.op == CMD_RESET:
        pc = 0
        fsp = 0
        env = GRAPH_WORDS
        control_top = 0
        direction = DIRECTION_FORWARD
        q = 0
        phi = 0
        free_space = GRAPH_WORDS
        argcnt = 0
        prim_id = 0
        fire = 0
        s_a = 0
        s_d = 0
        halted = 0
        pending_host_op = HOST_NONE
        pending_host_argument = 0
        red2_fault = FAULT_NONE
        hw_fault = HW_FAULT_NONE
        microstate = MICRO_FETCH
        fetched_word = red2_word_t(lo=0, hi=0)
        lookup_word = red2_word_t(lo=0, hi=0)
        lookup_address = 0
        lookup_remaining = 0
        lookup_hops = 0
        rup_count = 0
        rup_index = 0
        rup_block = 0
        rup_rec_binding = 0
        rup_rec_payload_bad = 0
        recp_binding = 0
        recp_context = 0
        recp_block = 0
        recp_count = 0
        recp_index = 0
        recp_selected = 0
        recp_replacement = 0
        recp_parent_environment = 0
        recp_reverse_zero = 0
        recp_reverse_needs_bridge = 0
        recp_reverse_parent_env = 0
        recp_reverse_entry_env = 0
        recp_copy_word = red2_word_t(lo=0, hi=0)
        recp_rup_word = red2_word_t(lo=0, hi=0)
        struct_saved_q = 0
        lambda_word = red2_word_t(lo=0, hi=0)
        lambda_path = 0
        app_parent_env = 0
        app_entry_env = 0
        app_child_pc = 0
        app_parent_pc = 0
        app_rblock_active = 0
        app_definition_active = 0
        app_definition_pop_saved = 0
        stop_cleanup_active = 0
        closure_target = 0
        ep_target = 0
        ep_hops = 0
        ep_terminal_word = red2_word_t(lo=0, hi=0)
        ep_publish_word = red2_word_t(lo=0, hi=0)
        ep_caller_path = 0
        join_parent_word = red2_word_t(lo=0, hi=0)
        join_publish_word = red2_word_t(lo=0, hi=0)
        join_cache_word = red2_word_t(lo=0, hi=0)
        join_parent_address = 0
        join_result_address = 0
        join_published_root = 0
        join_recp_rblock_cursor = 0
        join_recp_rblock_count = 0
        join_recp_binding_root = 0
        join_ep_target = 0
        join_frame_env = 0
        join_frame_free_space = 0
        join_frame_prim_id = 0
        join_frame_fire = 0
        join_saved_primitive = 0
        join_prim_meta_cursor = 0
        join_prim_scalar_op = SCALAR_OP_NONE
        join_scalar_preflight_done = 0
        join_scalar_contract = 0
        join_scalar_right_word = red2_word_t(lo=0, hi=0)
        join_scalar_return_ep = 0
        direct_scalar_active = 0
        ep_scalar_active = 0
        equality_atomic_active = 0
        equality_launch_active = 0
        equality_launch_phase = 0
        equality_launch_live_fsp = 0
        equality_launch_task_root = 0
        equality_launch_normalized_env = 0
        equality_launch_needs_bridge = 0
        equality_launch_clear_index = 0
        equality_launch_clear_remaining = 0
        equality_child_active = 0
        equality_child_phase = 0
        equality_child_task_root = 0
        equality_child_join_address = 0
        equality_child_left = 0
        equality_child_right = 0
        equality_child_lambdas = 0
        equality_child_descriptor = 0
        equality_child_left_word = red2_word_t(lo=0, hi=0)
        equality_child_right_word = red2_word_t(lo=0, hi=0)
        equality_child_left_code_word = red2_word_t(lo=0, hi=0)
        equality_child_build_join_word = red2_word_t(lo=0, hi=0)
        equality_child_build_root = 0
        equality_child_build_descriptor = 0
        equality_child_build_app_mode = 0
        equality_child_build_count = 0
        equality_child_build_index = 0
        equality_child_build_cursor = 0
        equality_child_build_false_root = 0
        equality_child_build_if_child_root = 0
        equality_child_struct_left_base = 0
        equality_child_struct_right_base = 0
        equality_child_struct_left_count = 0
        equality_child_struct_right_count = 0
        equality_continue_active = 0
        equality_continue_phase = 0
        equality_continue_result_pc = 0
        equality_continue_live_fsp = 0
        equality_continue_saved_q = 0
        equality_continue_child_id = 0
        prim0_meta_active = 0
        prim0_y_active = 0
        prim0_y_needs_scratch = 0
        prim0_y_argument_address = 0
        prim0_y_target = 0
        prim0_y_scratch_word = red2_word_t(lo=0, hi=0)
        join_special_meta_cursor = 0
        join_true_literal_id = 0
        join_false_literal_id = 0
        join_nil_literal_id = 0
        join_equal_star_literal_id = 0
        join_equal_if_literal_id = 0
        join_equality_continue_literal_id = 0
        join_equal_stuck_literal_id = 0
        join_frame_index = 0
        join_control_clear_index = 0
        join_parent_is_ep = 0
        join_parent_is_recp = 0
        join_needs_ep_cache = 0
        join_preserve_fsp = 0
        join_ep_chase_target = 0
        join_ep_hops = 0
        join_ep_publish_word = red2_word_t(lo=0, hi=0)
        join_ep_descriptor_hi = 0
        join_ep_descriptor_address = 0
        join_ep_general_root = 0
        join_ep_embedded = 0
        join_app_cursor = 0
        join_app_operator_address = 0
        join_app_shared_target = 0
        join_app_second_target = 0
        join_app_has_second_target = 0
        join_app_preflight_slot = 0
        join_app_preflight_root = 0
        join_app_preflight_descriptor_hi = 0
        join_app_preflight_chase_target = 0
        join_app_preflight_hops = 0
        join_app_first_write_needed = 0
        join_app_second_write_needed = 0
        join_app_first_write_word = red2_word_t(lo=0, hi=0)
        join_app_second_write_word = red2_word_t(lo=0, hi=0)
        join_app_rewrite_word = red2_word_t(lo=0, hi=0)
        join_flat_cursor = 0
        join_closure_address = 0
        join_closure_env = 0
        join_closure_code = 0
        join_closure_cursor = 0
        join_closure_lambda_count = 0
        join_closure_body_word = red2_word_t(lo=0, hi=0)
        join_closure_lambda_word = red2_word_t(lo=0, hi=0)
        join_closure_env_cursor = 0
        join_closure_env_remaining = 0
        join_closure_env_hops = 0
        join_closure_destination = 0
        join_closure_write_index = 0
    elif command.op == CMD_LOAD_MEMORY:
        if memory_address_in_range:
            hw_fault = HW_FAULT_NONE
        else:
            hw_fault = HW_FAULT_ADDRESS_RANGE
    elif command.op == CMD_LOAD_CONTROL:
        if control_address_in_range:
            hw_fault = HW_FAULT_NONE
        else:
            hw_fault = HW_FAULT_ADDRESS_RANGE
    elif command.op == CMD_LOAD_LITERAL_META:
        if literal_meta_address_in_range:
            hw_fault = HW_FAULT_NONE
        else:
            hw_fault = HW_FAULT_ADDRESS_RANGE
    elif command.op == CMD_LOAD_STATE:
        pc = command.state.pc
        fsp = command.state.fsp
        env = command.state.env
        control_top = command.state.control_top
        direction = command.state.direction
        q = command.state.q
        phi = command.state.phi
        free_space = command.state.free_space
        argcnt = command.state.argcnt
        prim_id = command.state.prim_id
        fire = command.state.fire
        s_a = command.state.s_a
        s_d = command.state.s_d
        halted = command.state.halted
        pending_host_op = command.state.pending_host_op
        pending_host_argument = command.state.pending_host_argument
        red2_fault = FAULT_NONE
        hw_fault = HW_FAULT_NONE
        microstate = MICRO_FETCH
        lookup_word = red2_word_t(lo=0, hi=0)
        lookup_address = 0
        lookup_remaining = 0
        lookup_hops = 0
        rup_count = 0
        rup_index = 0
        rup_block = 0
        rup_rec_binding = 0
        rup_rec_payload_bad = 0
        recp_binding = 0
        recp_context = 0
        recp_block = 0
        recp_count = 0
        recp_index = 0
        recp_selected = 0
        recp_replacement = 0
        recp_parent_environment = 0
        recp_reverse_zero = 0
        recp_reverse_needs_bridge = 0
        recp_reverse_parent_env = 0
        recp_reverse_entry_env = 0
        recp_copy_word = red2_word_t(lo=0, hi=0)
        recp_rup_word = red2_word_t(lo=0, hi=0)
        struct_saved_q = 0
        lambda_word = red2_word_t(lo=0, hi=0)
        lambda_path = 0
        app_parent_env = 0
        app_entry_env = 0
        app_child_pc = 0
        app_parent_pc = 0
        app_rblock_active = 0
        app_definition_active = 0
        app_definition_pop_saved = 0
        stop_cleanup_active = 0
        closure_target = 0
        ep_target = 0
        ep_hops = 0
        ep_terminal_word = red2_word_t(lo=0, hi=0)
        ep_publish_word = red2_word_t(lo=0, hi=0)
        ep_caller_path = 0
        join_parent_word = red2_word_t(lo=0, hi=0)
        join_publish_word = red2_word_t(lo=0, hi=0)
        join_cache_word = red2_word_t(lo=0, hi=0)
        join_parent_address = 0
        join_result_address = 0
        join_published_root = 0
        join_recp_rblock_cursor = 0
        join_recp_rblock_count = 0
        join_recp_binding_root = 0
        join_ep_target = 0
        join_frame_env = 0
        join_frame_free_space = 0
        join_frame_prim_id = 0
        join_frame_fire = 0
        join_saved_primitive = 0
        join_prim_meta_cursor = 0
        join_prim_scalar_op = SCALAR_OP_NONE
        join_scalar_preflight_done = 0
        join_scalar_contract = 0
        join_scalar_right_word = red2_word_t(lo=0, hi=0)
        join_scalar_return_ep = 0
        direct_scalar_active = 0
        ep_scalar_active = 0
        equality_atomic_active = 0
        equality_launch_active = 0
        equality_launch_phase = 0
        equality_launch_live_fsp = 0
        equality_launch_task_root = 0
        equality_launch_normalized_env = 0
        equality_launch_needs_bridge = 0
        equality_launch_clear_index = 0
        equality_launch_clear_remaining = 0
        equality_child_active = 0
        equality_child_phase = 0
        equality_child_task_root = 0
        equality_child_join_address = 0
        equality_child_left = 0
        equality_child_right = 0
        equality_child_lambdas = 0
        equality_child_descriptor = 0
        equality_child_left_word = red2_word_t(lo=0, hi=0)
        equality_child_right_word = red2_word_t(lo=0, hi=0)
        equality_child_left_code_word = red2_word_t(lo=0, hi=0)
        equality_child_build_join_word = red2_word_t(lo=0, hi=0)
        equality_child_build_root = 0
        equality_child_build_descriptor = 0
        equality_child_build_app_mode = 0
        equality_child_build_count = 0
        equality_child_build_index = 0
        equality_child_build_cursor = 0
        equality_child_build_false_root = 0
        equality_child_build_if_child_root = 0
        equality_child_struct_left_base = 0
        equality_child_struct_right_base = 0
        equality_child_struct_left_count = 0
        equality_child_struct_right_count = 0
        equality_continue_active = 0
        equality_continue_phase = 0
        equality_continue_result_pc = 0
        equality_continue_live_fsp = 0
        equality_continue_saved_q = 0
        equality_continue_child_id = 0
        prim0_meta_active = 0
        prim0_y_active = 0
        prim0_y_needs_scratch = 0
        prim0_y_argument_address = 0
        prim0_y_target = 0
        prim0_y_scratch_word = red2_word_t(lo=0, hi=0)
        join_special_meta_cursor = 0
        join_true_literal_id = 0
        join_false_literal_id = 0
        join_nil_literal_id = 0
        join_equal_star_literal_id = 0
        join_equal_if_literal_id = 0
        join_equality_continue_literal_id = 0
        join_equal_stuck_literal_id = 0
        join_frame_index = 0
        join_control_clear_index = 0
        join_parent_is_ep = 0
        join_parent_is_recp = 0
        join_needs_ep_cache = 0
        join_preserve_fsp = 0
        join_ep_chase_target = 0
        join_ep_hops = 0
        join_ep_publish_word = red2_word_t(lo=0, hi=0)
        join_ep_descriptor_hi = 0
        join_ep_descriptor_address = 0
        join_ep_general_root = 0
        join_ep_embedded = 0
        join_app_cursor = 0
        join_app_operator_address = 0
        join_app_shared_target = 0
        join_app_second_target = 0
        join_app_has_second_target = 0
        join_app_preflight_slot = 0
        join_app_preflight_root = 0
        join_app_preflight_descriptor_hi = 0
        join_app_preflight_chase_target = 0
        join_app_preflight_hops = 0
        join_app_first_write_needed = 0
        join_app_second_write_needed = 0
        join_app_first_write_word = red2_word_t(lo=0, hi=0)
        join_app_second_write_word = red2_word_t(lo=0, hi=0)
        join_app_rewrite_word = red2_word_t(lo=0, hi=0)
        join_flat_cursor = 0
        join_closure_address = 0
        join_closure_env = 0
        join_closure_code = 0
        join_closure_cursor = 0
        join_closure_lambda_count = 0
        join_closure_body_word = red2_word_t(lo=0, hi=0)
        join_closure_lambda_word = red2_word_t(lo=0, hi=0)
        join_closure_env_cursor = 0
        join_closure_env_remaining = 0
        join_closure_env_hops = 0
        join_closure_destination = 0
        join_closure_write_index = 0
    elif command.op == CMD_START:
        if memory_address_in_range:
            pc = command.address
            q = command.value
            fsp = 0
            env = GRAPH_WORDS
            control_top = 0
            free_space = GRAPH_WORDS
            argcnt = 0
            halted = 0
            pending_host_op = HOST_NONE
            pending_host_argument = 0
            red2_fault = FAULT_NONE
            hw_fault = HW_FAULT_NONE
            microstate = MICRO_FETCH
            lookup_word = red2_word_t(lo=0, hi=0)
            lookup_address = 0
            lookup_remaining = 0
            lookup_hops = 0
            rup_count = 0
            rup_index = 0
            rup_block = 0
            rup_rec_binding = 0
            rup_rec_payload_bad = 0
            recp_binding = 0
            recp_context = 0
            recp_block = 0
            recp_count = 0
            recp_index = 0
            recp_selected = 0
            recp_replacement = 0
            recp_parent_environment = 0
            recp_reverse_zero = 0
            recp_reverse_needs_bridge = 0
            recp_reverse_parent_env = 0
            recp_reverse_entry_env = 0
            recp_copy_word = red2_word_t(lo=0, hi=0)
            recp_rup_word = red2_word_t(lo=0, hi=0)
            struct_saved_q = 0
            lambda_word = red2_word_t(lo=0, hi=0)
            lambda_path = 0
            app_parent_env = 0
            app_entry_env = 0
            app_child_pc = 0
            app_parent_pc = 0
            app_rblock_active = 0
            app_definition_active = 0
            app_definition_pop_saved = 0
            stop_cleanup_active = 0
            closure_target = 0
            ep_target = 0
            ep_hops = 0
            ep_terminal_word = red2_word_t(lo=0, hi=0)
            ep_publish_word = red2_word_t(lo=0, hi=0)
            ep_caller_path = 0
            join_parent_word = red2_word_t(lo=0, hi=0)
            join_publish_word = red2_word_t(lo=0, hi=0)
            join_cache_word = red2_word_t(lo=0, hi=0)
            join_parent_address = 0
            join_result_address = 0
            join_published_root = 0
            join_recp_rblock_cursor = 0
            join_recp_rblock_count = 0
            join_recp_binding_root = 0
            join_ep_target = 0
            join_frame_env = 0
            join_frame_free_space = 0
            join_frame_prim_id = 0
            join_frame_fire = 0
            join_saved_primitive = 0
            direct_scalar_active = 0
            ep_scalar_active = 0
            prim0_meta_active = 0
            prim0_y_active = 0
            prim0_y_needs_scratch = 0
            prim0_y_argument_address = 0
            prim0_y_target = 0
            prim0_y_scratch_word = red2_word_t(lo=0, hi=0)
            join_frame_index = 0
            join_control_clear_index = 0
            join_parent_is_ep = 0
            join_parent_is_recp = 0
            join_needs_ep_cache = 0
            join_ep_chase_target = 0
            join_ep_hops = 0
            join_ep_publish_word = red2_word_t(lo=0, hi=0)
            join_ep_descriptor_hi = 0
            join_ep_descriptor_address = 0
            join_ep_general_root = 0
            join_ep_embedded = 0
            join_app_cursor = 0
            join_app_operator_address = 0
            join_app_shared_target = 0
            join_app_second_target = 0
            join_app_has_second_target = 0
            join_app_preflight_slot = 0
            join_app_preflight_root = 0
            join_app_preflight_descriptor_hi = 0
            join_app_preflight_chase_target = 0
            join_app_preflight_hops = 0
            join_app_first_write_needed = 0
            join_app_second_write_needed = 0
            join_app_first_write_word = red2_word_t(lo=0, hi=0)
            join_app_second_write_word = red2_word_t(lo=0, hi=0)
            join_app_rewrite_word = red2_word_t(lo=0, hi=0)
            join_flat_cursor = 0
            join_closure_address = 0
            join_closure_env = 0
            join_closure_code = 0
            join_closure_cursor = 0
            join_closure_lambda_count = 0
            join_closure_body_word = red2_word_t(lo=0, hi=0)
            join_closure_lambda_word = red2_word_t(lo=0, hi=0)
            join_closure_env_cursor = 0
            join_closure_env_remaining = 0
            join_closure_env_hops = 0
            join_closure_destination = 0
            join_closure_write_index = 0
        else:
            hw_fault = HW_FAULT_ADDRESS_RANGE
    elif command.op == CMD_RECHARGE:
        q = command.value
        hw_fault = HW_FAULT_NONE
    elif command.op == CMD_RESUME:
        # Full RED2 resume validation/publication belongs to the later host slice.
        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
    elif command.op == CMD_CLOCK:
        hw_fault = HW_FAULT_NONE
        has_red2_fault: uint1_t = red2_fault != FAULT_NONE
        is_fault_microstate: uint1_t = microstate == MICRO_FAULT
        clock_faulted: uint1_t = has_red2_fault or is_fault_microstate
        if clock_faulted:
            microstate = MICRO_FAULT
        elif micro_is_fetch:
            pending_host: uint1_t = pending_host_op != HOST_NONE
            fetch_suspended: uint1_t = halted or pending_host
            pc_out_of_range: uint1_t = pc_in_range == 0
            fetched_ram_invalid: uint1_t = memory_out.p0.rd_data.hi[26] == 0
            if fetch_suspended:
                microstate = MICRO_FETCH
            elif pc_out_of_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif fetched_ram_invalid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                fetched_word = memory_out.p0.rd_data
                microstate = MICRO_EXECUTE
        elif micro_is_execute:
            fetched_invalid: uint1_t = fetched_valid == 0
            kind_bad: uint1_t = passive_kind_ok == 0
            direction_is_reverse: uint1_t = direction == DIRECTION_REVERSE
            fire_active: uint1_t = fire != 0
            if fetched_invalid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif passive_opcode:
                if kind_bad:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif direction_is_reverse:
                    if fire_active:
                        if prim_id == 0:
                            red2_fault = FAULT_ILLEGAL_TRANSITION
                            microstate = MICRO_FAULT
                        elif fire == 1:
                            # MOVE-BACKWARD decrements the countdown before firing.
                            # Preserve prim_id on evaluator faults, matching the
                            # architectural oracle, but expose fire==0 immediately.
                            fire = 0
                            direct_scalar_active = 1
                            ep_scalar_active = 0
                            equality_atomic_active = 0
                            join_frame_prim_id = prim_id
                            join_parent_address = pc
                            join_prim_meta_cursor = 0
                            join_prim_scalar_op = SCALAR_OP_NONE
                            join_scalar_preflight_done = 0
                            join_scalar_contract = 0
                            join_scalar_right_word = red2_word_t(lo=0, hi=0)
                            join_scalar_return_ep = 0
                            join_true_literal_id = 0
                            join_false_literal_id = 0
                            join_nil_literal_id = 0
                            join_equal_star_literal_id = 0
                            join_equal_if_literal_id = 0
                            join_equality_continue_literal_id = 0
                            join_equal_stuck_literal_id = 0
                            join_publish_word = fetched_word
                            microstate = MICRO_JOIN_PRIM_META_SCAN
                        else:
                            # Countdown bookkeeping is not a semantic contraction.
                            fire = fire - 1
                            pc = pc - 1
                            microstate = MICRO_COMMIT
                    else:
                        pc = pc - 1
                        microstate = MICRO_COMMIT
                else:
                    fsp_ok: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    fsp_bad: uint1_t = fsp_ok == 0
                    has_successor: uint1_t = fsp[GRAPH_ADDR_BITS - 1 : 0] != 255
                    no_successor: uint1_t = has_successor == 0
                    pushed: uint17_t = fsp + 1
                    collides: uint1_t = pushed == free_space
                    cannot_push: uint1_t = no_successor or collides
                    if fsp_bad:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif cannot_push:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        fsp = pushed[15:0]
                        argcnt = argcnt + 1
                        if fetched_head:
                            pc = pushed[15:0] - 1
                            direction = DIRECTION_REVERSE
                        else:
                            pc = pc + 1
                        microstate = MICRO_COMMIT
            elif opcode_is_sym:
                sym_kind_ok_exec: uint1_t = kind_is_literal
                sym_payload_nonzero_exec: uint1_t = fetched_word.lo != 0
                if not sym_kind_ok_exec or not sym_payload_nonzero_exec:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif direction_is_reverse:
                    sym_definition_valid_exec: uint1_t = fetched_word.hi[16]
                    sym_definition_fire_exec: uint1_t = fetched_head and sym_definition_valid_exec
                    sym_q_nonzero_exec: uint1_t = q != 0
                    sym_definition_fire_exec = sym_definition_fire_exec and sym_q_nonzero_exec
                    if sym_definition_fire_exec:
                        sym_pc_zero_exec: uint1_t = pc == 0
                        sym_control_top_low_exec: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
                        sym_control_top_end_exec: uint1_t = control_top == CONTROL_WORDS
                        sym_control_top_valid_exec: uint1_t = sym_control_top_low_exec or sym_control_top_end_exec
                        if sym_pc_zero_exec:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not sym_control_top_valid_exec:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not sym_control_top_low_exec:
                            red2_fault = FAULT_CONTROL_OVERFLOW
                            microstate = MICRO_FAULT
                        else:
                            control_top = control_top + 1
                            argcnt = argcnt - 1
                            microstate = MICRO_COMMIT
                    elif fire_active:
                        if prim_id == 0:
                            red2_fault = FAULT_ILLEGAL_TRANSITION
                            microstate = MICRO_FAULT
                        elif fire == 1:
                            fire = 0
                            direct_scalar_active = 1
                            ep_scalar_active = 0
                            equality_atomic_active = 0
                            join_frame_prim_id = prim_id
                            join_parent_address = pc
                            join_prim_meta_cursor = 0
                            join_prim_scalar_op = SCALAR_OP_NONE
                            join_scalar_preflight_done = 0
                            join_scalar_contract = 0
                            join_scalar_right_word = red2_word_t(lo=0, hi=0)
                            join_scalar_return_ep = 0
                            join_true_literal_id = 0
                            join_false_literal_id = 0
                            join_nil_literal_id = 0
                            join_equal_star_literal_id = 0
                            join_equal_if_literal_id = 0
                            join_equality_continue_literal_id = 0
                            join_equal_stuck_literal_id = 0
                            join_publish_word = fetched_word
                            microstate = MICRO_JOIN_PRIM_META_SCAN
                        else:
                            fire = fire - 1
                            pc = pc - 1
                            microstate = MICRO_COMMIT
                    else:
                        pc = pc - 1
                        microstate = MICRO_COMMIT
                else:
                    sym_fsp_ok_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    sym_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    sym_free_end_exec: uint1_t = free_space == GRAPH_WORDS
                    sym_free_valid_exec: uint1_t = sym_free_low_exec or sym_free_end_exec
                    sym_destination_exec: uint17_t = fsp + 1
                    sym_gap_exec: uint17_t = free_space - sym_destination_exec
                    sym_gap_wrapped_exec: uint1_t = sym_gap_exec[16]
                    sym_gap_nonzero_exec: uint1_t = sym_gap_exec != 0
                    sym_gap_ok_exec: uint1_t = sym_gap_wrapped_exec == 0
                    sym_gap_ok_exec = sym_gap_ok_exec and sym_gap_nonzero_exec
                    if not sym_fsp_ok_exec:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not sym_free_valid_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not sym_gap_ok_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        fsp = sym_destination_exec[15:0]
                        argcnt = argcnt + 1
                        if fetched_head:
                            sym_forward_definition: uint1_t = fetched_word.hi[16]
                            sym_forward_q_nonzero: uint1_t = q != 0
                            sym_forward_expand: uint1_t = sym_forward_definition and sym_forward_q_nonzero
                            if sym_forward_expand:
                                pc = sym_destination_exec[15:0]
                            else:
                                pc = sym_destination_exec[15:0] - 1
                            direction = DIRECTION_REVERSE
                        else:
                            pc = pc + 1
                        microstate = MICRO_COMMIT
            elif opcode_is_prim0:
                prim0_kind_ok_exec: uint1_t = kind_is_literal
                prim0_payload_nonzero_exec: uint1_t = fetched_word.lo != 0
                if not prim0_kind_ok_exec or not prim0_payload_nonzero_exec:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif direction_is_reverse:
                    # Reverse PRIM_0 is unconditionally passive. Primitive-role,
                    # equality, Y and host metadata are consulted only forward.
                    pc = pc - 1
                    microstate = MICRO_COMMIT
                elif not fetched_head:
                    # Non-head PRIM_0 cannot trigger any special primitive role.
                    # Publish exactly like _push_result(word), preserving metadata.
                    prim0_fsp_ok_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    prim0_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    prim0_free_end_exec: uint1_t = free_space == GRAPH_WORDS
                    prim0_free_valid_exec: uint1_t = prim0_free_low_exec or prim0_free_end_exec
                    prim0_destination_exec: uint17_t = fsp + 1
                    prim0_gap_exec: uint17_t = free_space - prim0_destination_exec
                    prim0_gap_wrapped_exec: uint1_t = prim0_gap_exec[16]
                    prim0_gap_nonzero_exec: uint1_t = prim0_gap_exec != 0
                    prim0_gap_ok_exec: uint1_t = prim0_gap_wrapped_exec == 0
                    prim0_gap_ok_exec = prim0_gap_ok_exec and prim0_gap_nonzero_exec
                    if not prim0_fsp_ok_exec:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not prim0_free_valid_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not prim0_gap_ok_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        fsp = prim0_destination_exec[15:0]
                        argcnt = argcnt + 1
                        pc = pc + 1
                        microstate = MICRO_COMMIT
                else:
                    # Head PRIM_0 resolves semantic identity through the same
                    # bounded associative metadata RAM used by scalar firing.
                    prim0_meta_active = 1
                    join_frame_prim_id = fetched_word.lo[31:0]
                    join_prim_meta_cursor = 0
                    microstate = MICRO_JOIN_PRIM_META_SCAN
            elif opcode_is_prim1 or opcode_is_prim2:
                prim12_kind_ok_exec: uint1_t = kind_is_literal
                prim12_payload_nonzero_exec: uint1_t = fetched_word.lo != 0
                if not prim12_kind_ok_exec or not prim12_payload_nonzero_exec:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif direction_is_reverse:
                    # Primitive descriptors are passive on MOVE-BACKWARD; unlike
                    # scalar values, they never consume the active fire countdown.
                    pc = pc - 1
                    microstate = MICRO_COMMIT
                else:
                    # Encoded argcnt is one greater than the oracle's internal
                    # counter, so visible arming thresholds are 2 for PRIM_1 and
                    # 3 for PRIM_2.  The oracle arms before _push_result(), which
                    # means an ensuing graph-collision fault preserves prim/fire.
                    prim12_q_nonzero_exec: uint1_t = q != 0
                    prim12_head_arm_exec: uint1_t = fetched_head and prim12_q_nonzero_exec
                    prim12_argcnt_zero_exec: uint1_t = argcnt == 0
                    prim12_argcnt_one_exec: uint1_t = argcnt == 1
                    prim12_argcnt_two_exec: uint1_t = argcnt == 2
                    prim12_argcnt_nonzero_exec: uint1_t = prim12_argcnt_zero_exec == 0
                    prim12_argcnt_not_one_exec: uint1_t = prim12_argcnt_one_exec == 0
                    prim12_argcnt_not_two_exec: uint1_t = prim12_argcnt_two_exec == 0
                    prim12_argcnt_p1_exec: uint1_t = prim12_argcnt_nonzero_exec and prim12_argcnt_not_one_exec
                    prim12_argcnt_p2_exec: uint1_t = prim12_argcnt_p1_exec and prim12_argcnt_not_two_exec
                    prim12_arm_p1_exec: uint1_t = opcode_is_prim1 and prim12_argcnt_p1_exec
                    prim12_arm_p2_exec: uint1_t = opcode_is_prim2 and prim12_argcnt_p2_exec
                    prim12_arm_exec: uint1_t = prim12_arm_p1_exec or prim12_arm_p2_exec
                    prim12_arm_exec = prim12_arm_exec and prim12_head_arm_exec
                    if prim12_arm_exec:
                        prim_id = fetched_word.lo[31:0]
                        if opcode_is_prim1:
                            fire = 1
                        else:
                            fire = 2

                    prim12_fsp_ok_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    prim12_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    prim12_free_end_exec: uint1_t = free_space == GRAPH_WORDS
                    prim12_free_valid_exec: uint1_t = prim12_free_low_exec or prim12_free_end_exec
                    prim12_destination_exec: uint17_t = fsp + 1
                    prim12_gap_exec: uint17_t = free_space - prim12_destination_exec
                    prim12_gap_wrapped_exec: uint1_t = prim12_gap_exec[16]
                    prim12_gap_nonzero_exec: uint1_t = prim12_gap_exec != 0
                    prim12_gap_ok_exec: uint1_t = prim12_gap_wrapped_exec == 0
                    prim12_gap_ok_exec = prim12_gap_ok_exec and prim12_gap_nonzero_exec
                    if not prim12_fsp_ok_exec:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not prim12_free_valid_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not prim12_gap_ok_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        fsp = prim12_destination_exec[15:0]
                        argcnt = argcnt + 1
                        if fetched_head:
                            pc = prim12_destination_exec[15:0] - 1
                            direction = DIRECTION_REVERSE
                        else:
                            pc = pc + 1
                        microstate = MICRO_COMMIT
            elif opcode_is_ubv:
                if direction_is_reverse:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif not kind_is_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    ubv_fsp_ok: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    ubv_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    ubv_free_end: uint1_t = free_space == GRAPH_WORDS
                    ubv_free_valid: uint1_t = ubv_free_low or ubv_free_end
                    ubv_destination: uint17_t = fsp + 1
                    ubv_gap: uint17_t = free_space - ubv_destination
                    ubv_gap_wrapped: uint1_t = ubv_gap[16]
                    ubv_gap_nonzero: uint1_t = ubv_gap != 0
                    ubv_gap_not_wrapped: uint1_t = ubv_gap_wrapped == 0
                    ubv_before_frontier: uint1_t = ubv_gap_not_wrapped and ubv_gap_nonzero
                    if not ubv_fsp_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not ubv_free_valid:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not ubv_before_frontier:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        fsp = ubv_destination[15:0]
                        argcnt = argcnt + 1
                        pc = ubv_destination[15:0] - 1
                        direction = DIRECTION_REVERSE
                        microstate = MICRO_COMMIT
            elif opcode_is_lambda:
                if direction_is_reverse:
                    phi_is_zero: uint1_t = phi == 0
                    if phi_is_zero:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        phi = phi - 1
                        pc = pc - 1
                        microstate = MICRO_COMMIT
                else:
                    fsp_in_range_lambda: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    if not fsp_in_range_lambda:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        microstate = MICRO_LAMBDA_READ
            elif opcode_is_ep:
                if not kind_is_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif fetched_word.lo[63]:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    ep_target = fetched_word.lo
                    ep_hops = 0
                    microstate = MICRO_EP_CHASE
            elif opcode_is_join:
                join_definition_valid: uint1_t = fetched_word.hi[16]
                join_definition_is_one: uint1_t = fetched_word.hi[15:0] == 1
                join_saved_primitive: uint1_t = join_definition_valid and join_definition_is_one
                join_parent_negative: uint1_t = fetched_word.lo[63]
                join_parent_upper_zero: uint1_t = fetched_word.lo[62:GRAPH_ADDR_BITS] == 0
                join_result_wide: uint17_t = pc + 1
                join_result_in_range: uint1_t = join_result_wide[16:GRAPH_ADDR_BITS] == 0
                join_result_gap: uint17_t = fsp - join_result_wide
                join_result_wrapped: uint1_t = join_result_gap[16]
                join_result_at_or_before_fsp: uint1_t = join_result_wrapped == 0
                if direction_is_forward:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif not kind_is_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_parent_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not join_parent_upper_zero:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not join_result_in_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not join_result_at_or_before_fsp:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_parent_address = fetched_word.lo[15:0]
                    join_result_address = join_result_wide[15:0]
                    join_saved_primitive = join_saved_primitive
                    join_parent_is_ep = 0
                    join_parent_is_recp = 0
                    join_recp_rblock_cursor = 0
                    join_recp_rblock_count = 0
                    join_recp_binding_root = 0
                    join_needs_ep_cache = 0
                    join_preserve_fsp = 0
                    join_prim_scalar_op = SCALAR_OP_NONE
                    join_scalar_preflight_done = 0
                    join_scalar_contract = 0
                    join_scalar_right_word = red2_word_t(lo=0, hi=0)
                    join_scalar_return_ep = 0
                    direct_scalar_active = 0
                    ep_scalar_active = 0
                    join_true_literal_id = 0
                    join_false_literal_id = 0
                    join_nil_literal_id = 0
                    join_equal_star_literal_id = 0
                    join_equal_if_literal_id = 0
                    join_equality_continue_literal_id = 0
                    join_equal_stuck_literal_id = 0
                    microstate = MICRO_JOIN_PARENT_READ
            elif opcode_is_closure:
                if direction_is_reverse:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif not kind_is_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif fetched_word.lo[63]:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    closure_code_address_exec: uint17_t = pc + 1
                    closure_code_wrapped: uint1_t = closure_code_address_exec[16]
                    closure_code_upper: uint1_t = closure_code_address_exec[15:GRAPH_ADDR_BITS] != 0
                    closure_code_bad: uint1_t = closure_code_wrapped or closure_code_upper
                    if closure_code_bad:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        microstate = MICRO_CLOSURE_READ
            elif opcode_is_stop:
                if direction_is_forward:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                else:
                    control_empty_for_stop: uint1_t = control_top == 0
                    if control_empty_for_stop:
                        pc = pc + 1
                        halted = 1
                        microstate = MICRO_COMMIT
                    else:
                        # STOP discards only the contiguous suffix of completed
                        # definition paths.  Any other lower control frame remains
                        # live while STOP itself still halts the machine.
                        stop_cleanup_active = 1
                        app_definition_active = 0
                        microstate = MICRO_APP_CONTROL_READ
            elif opcode_is_app:
                if direction_is_reverse:
                    reverse_app_definition_valid: uint1_t = fetched_word.hi[16]
                    reverse_app_q_nonzero: uint1_t = q != 0
                    reverse_app_definition_fire: uint1_t = reverse_app_definition_valid and reverse_app_q_nonzero
                    reverse_app_negative: uint1_t = fetched_word.lo[63]
                    app_rblock_active = 0
                    if reverse_app_definition_fire:
                        # Definition contraction ignores the APP payload entirely.
                        # Inspect only the optional SAVED_DEFINITION_PATH top entry
                        # before serializing STOP publication through the existing
                        # reverse-EP publish state.
                        app_definition_active = 1
                        app_definition_pop_saved = 0
                        app_child_pc = fetched_word.hi[15:0]
                        app_parent_pc = pc
                        microstate = MICRO_APP_CONTROL_READ
                    elif not kind_is_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif reverse_app_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        app_child_pc = fetched_word.lo[15:0]
                        app_parent_pc = pc
                        microstate = MICRO_APP_CONTROL_READ
                else:
                    app_rblock_active = 0
                    env_low_range_exec: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
                    env_is_end_exec: uint1_t = env == GRAPH_WORDS
                    env_in_range_exec: uint1_t = env_low_range_exec or env_is_end_exec
                    control_top_low_exec: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
                    control_top_end_exec: uint1_t = control_top == CONTROL_WORDS
                    control_top_valid_exec: uint1_t = control_top_low_exec or control_top_end_exec
                    fsp_in_range_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    free_space_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    free_space_end_exec: uint1_t = free_space == GRAPH_WORDS
                    free_space_valid_exec: uint1_t = free_space_low_exec or free_space_end_exec
                    app_destination: uint17_t = fsp + 1
                    app_gap: uint17_t = free_space - app_destination
                    app_gap_wrapped: uint1_t = app_gap[16]
                    app_gap_nonzero: uint1_t = app_gap != 0
                    app_gap_not_wrapped: uint1_t = app_gap_wrapped == 0
                    app_before_frontier: uint1_t = app_gap_not_wrapped and app_gap_nonzero
                    if not env_in_range_exec:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not control_top_valid_exec:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not control_top_low_exec:
                        red2_fault = FAULT_CONTROL_OVERFLOW
                        microstate = MICRO_FAULT
                    elif not fsp_in_range_exec:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not free_space_valid_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not app_before_frontier:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        fsp = app_destination[15:0]
                        argcnt = argcnt + 1
                        control_top = control_top + 1
                        pc = pc + 1
                        microstate = MICRO_COMMIT
            elif opcode_is_rblock:
                rblock_negative: uint1_t = fetched_word.lo[63]
                if not kind_is_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif rblock_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif direction_is_reverse:
                    # RBLOCK reverse is the same serialized subgraph-entry
                    # transaction as reverse APP after popping its saved caller
                    # path.  The only architectural distinction at commit is
                    # argcnt=-1 in the Python machine, encoded here as zero.
                    app_rblock_active = 1
                    app_child_pc = fetched_word.lo[15:0]
                    app_parent_pc = pc
                    microstate = MICRO_APP_CONTROL_READ
                elif q != 0:
                    # Positive-q RBLOCK allocates one three-word REC record, with
                    # an optional PNP bridge when env is not already the frontier.
                    # Preflight the complete allocation before the first RAM write.
                    rblock_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    rblock_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    rblock_free_end: uint1_t = free_space == GRAPH_WORDS
                    rblock_free_valid: uint1_t = rblock_free_low or rblock_free_end
                    rblock_layout_gap: uint17_t = free_space - fsp
                    rblock_layout_wrapped: uint1_t = rblock_layout_gap[16]
                    rblock_layout_nonzero: uint1_t = rblock_layout_gap != 0
                    rblock_layout_ok: uint1_t = rblock_layout_wrapped == 0
                    rblock_layout_ok = rblock_layout_ok and rblock_layout_nonzero
                    rblock_env_low: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
                    rblock_env_end: uint1_t = env == GRAPH_WORDS
                    rblock_env_valid: uint1_t = rblock_env_low or rblock_env_end
                    rblock_needs_bridge: uint1_t = free_space != env
                    rblock_count: uint17_t = 3
                    if rblock_needs_bridge:
                        rblock_count = 4
                    rblock_base: uint17_t = free_space - rblock_count
                    rblock_base_gap: uint17_t = rblock_base - fsp
                    rblock_base_wrapped: uint1_t = rblock_base_gap[16]
                    rblock_base_nonzero: uint1_t = rblock_base_gap != 0
                    rblock_base_after_fsp: uint1_t = rblock_base_wrapped == 0
                    rblock_base_after_fsp = rblock_base_after_fsp and rblock_base_nonzero
                    if not rblock_fsp_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not rblock_free_valid:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not rblock_layout_ok:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not rblock_env_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not rblock_base_after_fsp:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        app_rblock_active = 1
                        # RBLOCK does not need a saved closure path, so reuse this
                        # otherwise-idle register as the second-NONE write cursor.
                        lambda_path = 0
                        if rblock_needs_bridge:
                            microstate = MICRO_LAMBDA_APP_BRIDGE
                        else:
                            microstate = MICRO_LAMBDA_APP_CLOSURE
                else:
                    # q=0 copies the RBLOCK result and allocates UBV(phi+1).
                    # Preflight both writes together so a late environment
                    # collision cannot expose a partially copied result.
                    rblock_zero_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    rblock_zero_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    rblock_zero_free_end: uint1_t = free_space == GRAPH_WORDS
                    rblock_zero_free_valid: uint1_t = rblock_zero_free_low or rblock_zero_free_end
                    rblock_zero_destination: uint17_t = fsp + 1
                    rblock_zero_push_gap: uint17_t = free_space - rblock_zero_destination
                    rblock_zero_push_wrapped: uint1_t = rblock_zero_push_gap[16]
                    rblock_zero_push_nonzero: uint1_t = rblock_zero_push_gap != 0
                    rblock_zero_push_ok: uint1_t = rblock_zero_push_wrapped == 0
                    rblock_zero_push_ok = rblock_zero_push_ok and rblock_zero_push_nonzero
                    rblock_zero_env_low: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
                    rblock_zero_env_end: uint1_t = env == GRAPH_WORDS
                    rblock_zero_env_valid: uint1_t = rblock_zero_env_low or rblock_zero_env_end
                    rblock_zero_needs_bridge: uint1_t = free_space != env
                    rblock_zero_env_count: uint17_t = 1
                    if rblock_zero_needs_bridge:
                        rblock_zero_env_count = 2
                    rblock_zero_env_base: uint17_t = free_space - rblock_zero_env_count
                    rblock_zero_env_gap: uint17_t = rblock_zero_env_base - rblock_zero_destination
                    rblock_zero_env_wrapped: uint1_t = rblock_zero_env_gap[16]
                    rblock_zero_env_nonzero: uint1_t = rblock_zero_env_gap != 0
                    rblock_zero_env_after_result: uint1_t = rblock_zero_env_wrapped == 0
                    rblock_zero_env_after_result = rblock_zero_env_after_result and rblock_zero_env_nonzero
                    if not rblock_zero_fsp_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not rblock_zero_free_valid:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not rblock_zero_push_ok:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not rblock_zero_env_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not rblock_zero_env_after_result:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        app_rblock_active = 1
                        microstate = MICRO_LAMBDA_PUSH
            elif opcode_is_rup:
                rup_negative: uint1_t = fetched_word.lo[63]
                rup_bad_kind: uint1_t = kind_is_signed == 0
                rup_bad_payload: uint1_t = rup_bad_kind or rup_negative
                if rup_bad_payload:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif direction_is_reverse:
                    pc = pc - 1
                    microstate = MICRO_COMMIT
                elif q != 0:
                    rup_count_upper_nonzero: uint1_t = fetched_word.lo[63:16] != 0
                    rup_count16: uint16_t = fetched_word.lo[15:0]
                    rup_pc17: uint17_t = pc
                    rup_count17: uint17_t = rup_count16
                    rup_block17: uint17_t = rup_pc17 - rup_count17
                    rup_block_wrapped: uint1_t = rup_block17[16]
                    rup_block_bad: uint1_t = rup_count_upper_nonzero or rup_block_wrapped
                    if rup_block_bad:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif rup_count16 == 0:
                        pc = pc + 1
                        microstate = MICRO_COMMIT
                    else:
                        rup_count = rup_count16
                        rup_index = 0
                        rup_block = rup_block17[15:0]
                        rup_rec_binding = 0
                        rup_rec_payload_bad = 0
                        microstate = MICRO_RUP_VALIDATE_REC
                else:
                    # The bounded machine performs all ADDRESS pushes before the
                    # graph copy.  Preflight in that same fault order so direct
                    # RAM publication remains architecturally atomic.
                    rup_control_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
                    rup_control_end: uint1_t = control_top == CONTROL_WORDS
                    rup_control_valid: uint1_t = rup_control_low or rup_control_end
                    rup_count_upper_nonzero: uint1_t = fetched_word.lo[63:16] != 0
                    rup_count16: uint16_t = fetched_word.lo[15:0]
                    rup_control_room: uint17_t = CONTROL_WORDS - control_top
                    rup_count17: uint17_t = rup_count16
                    rup_control_gap: uint17_t = rup_control_room - rup_count17
                    rup_control_wrapped: uint1_t = rup_control_gap[16]
                    rup_control_overflow: uint1_t = rup_count_upper_nonzero or rup_control_wrapped
                    rup_zero_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    rup_zero_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    rup_zero_free_end: uint1_t = free_space == GRAPH_WORDS
                    rup_zero_free_valid: uint1_t = rup_zero_free_low or rup_zero_free_end
                    rup_zero_destination: uint17_t = fsp + 1
                    rup_zero_gap: uint17_t = free_space - rup_zero_destination
                    rup_zero_wrapped: uint1_t = rup_zero_gap[16]
                    rup_zero_nonzero: uint1_t = rup_zero_gap != 0
                    rup_zero_not_wrapped: uint1_t = rup_zero_wrapped == 0
                    rup_zero_graph_ok: uint1_t = rup_zero_not_wrapped and rup_zero_nonzero
                    if rup_count16 == 0:
                        # Count zero performs no control operation at all.  Match
                        # the bounded machine by validating only the graph push.
                        if not rup_zero_fsp_valid:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not rup_zero_free_valid:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        elif not rup_zero_graph_ok:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        else:
                            rup_count = 0
                            rup_index = 0
                            rup_block = 0
                            rup_rec_binding = 0
                            rup_rec_payload_bad = 0
                            microstate = MICRO_RUP_ZERO_RESULT
                    elif not rup_control_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif rup_control_overflow:
                        red2_fault = FAULT_CONTROL_OVERFLOW
                        microstate = MICRO_FAULT
                    elif not rup_zero_fsp_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not rup_zero_free_valid:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not rup_zero_graph_ok:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        rup_count = rup_count16
                        rup_index = 0
                        rup_block = 0
                        rup_rec_binding = 0
                        rup_rec_payload_bad = 0
                        microstate = MICRO_RUP_ZERO_PUSH
            elif opcode_is_struct:
                struct_payload_nonzero: uint1_t = fetched_word.lo != 0
                struct_literal_valid: uint1_t = kind_is_literal and struct_payload_nonzero
                if not struct_literal_valid:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif direction_is_reverse:
                    microstate = MICRO_STRUCT_REVERSE_CONTROL_READ
                else:
                    struct_fsp_valid_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    if not struct_fsp_valid_exec:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        microstate = MICRO_STRUCT_RESULT_READ
            elif opcode_is_recp:
                recp_address_negative: uint1_t = fetched_word.lo[63]
                recp_address_kind_bad: uint1_t = kind_is_signed == 0
                recp_address_upper_nonzero: uint1_t = fetched_word.lo[62:GRAPH_ADDR_BITS] != 0
                recp_address17: uint17_t = fetched_word.lo[16:0]
                recp_end17: uint17_t = recp_address17 + 2
                recp_end_out_of_range: uint1_t = recp_end17[16:GRAPH_ADDR_BITS] != 0
                if recp_address_kind_bad:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_address_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_address_upper_nonzero:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_end_out_of_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    recp_binding = 0
                    recp_context = 0
                    recp_block = 0
                    microstate = MICRO_RECP_VALIDATE_REC
            else:
                reverse_app_var: uint1_t = opcode_is_app_var and direction_is_reverse
                forward_app_var: uint1_t = opcode_is_app_var and direction_is_forward
                forward_var: uint1_t = opcode_is_var and direction_is_forward
                if reverse_app_var:
                    pc = pc - 1
                    microstate = MICRO_COMMIT
                elif opcode_is_var and direction_is_reverse:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif forward_app_var or forward_var:
                    lookup_index_negative: uint1_t = fetched_word.lo[63]
                    lookup_env_in_range: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
                    if not kind_is_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif lookup_index_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not lookup_env_in_range:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        lookup_address = env
                        lookup_remaining = fetched_word.lo
                        lookup_hops = 0
                        microstate = MICRO_LOOKUP_READ
                else:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
        elif micro_is_struct_result_read:
            struct_result_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            struct_result_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            struct_result_is_app: uint1_t = struct_result_opcode == MOP_APP
            struct_result_is_app_var: uint1_t = struct_result_opcode == MOP_APP_VAR
            struct_result_is_ep: uint1_t = struct_result_opcode == MOP_EP
            struct_result_special: uint1_t = struct_result_is_app or struct_result_is_app_var
            struct_result_special = struct_result_special or struct_result_is_ep
            struct_reconstruct: uint1_t = q == 0 or struct_result_special == 0

            struct_control_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            struct_control_top_end: uint1_t = control_top == CONTROL_WORDS
            struct_control_top_valid: uint1_t = struct_control_top_low or struct_control_top_end
            struct_control_empty: uint1_t = control_top == 0
            struct_control_entry_lo_zero: uint1_t = control_out.p0.rd_data.lo == 0
            struct_control_entry_hi_zero: uint1_t = control_out.p0.rd_data.hi == 0
            struct_control_entry_tag_zero: uint1_t = control_out.p0.rd_data.tag_hi == 0
            struct_control_entry_empty: uint1_t = struct_control_entry_lo_zero and struct_control_entry_hi_zero
            struct_control_entry_empty = struct_control_entry_empty and struct_control_entry_tag_zero
            struct_control_entry_address: uint1_t = control_out.p0.rd_data.tag_hi == CONTROL_ADDRESS

            struct_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            struct_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            struct_free_end: uint1_t = free_space == GRAPH_WORDS
            struct_free_valid: uint1_t = struct_free_low or struct_free_end
            struct_layout_gap: uint17_t = free_space - fsp
            struct_layout_wrapped: uint1_t = struct_layout_gap[16]
            struct_layout_nonzero: uint1_t = struct_layout_gap != 0
            struct_layout_ok: uint1_t = struct_layout_wrapped == 0
            struct_layout_ok = struct_layout_ok and struct_layout_nonzero
            struct_env_low: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
            struct_env_end: uint1_t = env == GRAPH_WORDS
            struct_env_valid: uint1_t = struct_env_low or struct_env_end
            struct_needs_bridge: uint1_t = free_space != env

            struct_env_words: uint17_t = 1
            if struct_result_is_app:
                struct_env_words = 2
            if struct_needs_bridge:
                struct_env_words = struct_env_words + 1
            struct_env_base: uint17_t = free_space - struct_env_words
            struct_env_gap: uint17_t = struct_env_base - fsp
            struct_env_wrapped: uint1_t = struct_env_gap[16]
            struct_env_nonzero: uint1_t = struct_env_gap != 0
            struct_env_after_fsp: uint1_t = struct_env_wrapped == 0
            struct_env_after_fsp = struct_env_after_fsp and struct_env_nonzero

            struct_recon_destination: uint17_t = fsp + 1
            struct_recon_destination_oob: uint1_t = struct_recon_destination[16:GRAPH_ADDR_BITS] != 0
            struct_recon_push_gap: uint17_t = free_space - struct_recon_destination
            struct_recon_push_wrapped: uint1_t = struct_recon_push_gap[16]
            struct_recon_push_nonzero: uint1_t = struct_recon_push_gap != 0
            struct_recon_push_ok: uint1_t = struct_recon_push_wrapped == 0
            struct_recon_push_ok = struct_recon_push_ok and struct_recon_push_nonzero
            struct_recon_env_words: uint17_t = 1
            if struct_needs_bridge:
                struct_recon_env_words = 2
            struct_recon_env_base: uint17_t = free_space - struct_recon_env_words
            struct_recon_env_gap: uint17_t = struct_recon_env_base - struct_recon_destination
            struct_recon_env_wrapped: uint1_t = struct_recon_env_gap[16]
            struct_recon_env_nonzero: uint1_t = struct_recon_env_gap != 0
            struct_recon_env_after_result: uint1_t = struct_recon_env_wrapped == 0
            struct_recon_env_after_result = struct_recon_env_after_result and struct_recon_env_nonzero

            struct_result_kind_signed: uint1_t = memory_out.p0.rd_data.hi[18:17] == DATA_SIGNED
            struct_result_negative: uint1_t = memory_out.p0.rd_data.lo[63]

            if not struct_result_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif struct_reconstruct:
                if not struct_control_top_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not struct_control_top_low:
                    red2_fault = FAULT_CONTROL_OVERFLOW
                    microstate = MICRO_FAULT
                elif struct_recon_destination_oob:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not struct_recon_push_ok:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not struct_free_valid:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not struct_env_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not struct_recon_env_after_result:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                else:
                    microstate = MICRO_STRUCT_RECON_SAVED_Q
            elif not struct_result_kind_signed:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif struct_result_negative:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif struct_result_is_app or struct_result_is_ep:
                if not struct_control_top_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif struct_control_empty:
                    red2_fault = FAULT_CONTROL_UNDERFLOW
                    microstate = MICRO_FAULT
                elif struct_control_entry_empty:
                    red2_fault = FAULT_CONTROL_UNDERFLOW
                    microstate = MICRO_FAULT
                elif not struct_control_entry_address:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif not struct_fsp_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not struct_free_valid:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not struct_layout_ok:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not struct_env_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not struct_env_after_fsp:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif struct_result_is_app:
                    lambda_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=67239936)
                    microstate = MICRO_LAMBDA_APP_CONTROL_READ
                else:
                    lambda_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=75628544)
                    microstate = MICRO_LAMBDA_EP_CONTROL_READ
            else:
                if not struct_fsp_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not struct_free_valid:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not struct_layout_ok:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not struct_env_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not struct_env_after_fsp:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                else:
                    struct_phi_wide: uint64_t = phi
                    struct_app_var_binding: uint64_t = struct_phi_wide - memory_out.p0.rd_data.lo
                    lambda_word = red2_word_t(lo=struct_app_var_binding, hi=109182976)
                    microstate = MICRO_LAMBDA_BETA_ENV
        elif micro_is_struct_recon_saved_q:
            struct_recon_pushed: uint17_t = fsp + 1
            control_top = control_top + 1
            q = 0
            fsp = struct_recon_pushed[15:0]
            argcnt = 1
            phi = phi + 1
            struct_recon_needs_bridge: uint1_t = free_space != env
            if struct_recon_needs_bridge:
                microstate = MICRO_LAMBDA_ENV_BRIDGE
            else:
                microstate = MICRO_LAMBDA_ENV_BINDING
        elif micro_is_struct_reverse_control_read:
            struct_reverse_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            struct_reverse_top_end: uint1_t = control_top == CONTROL_WORDS
            struct_reverse_top_valid: uint1_t = struct_reverse_top_low or struct_reverse_top_end
            struct_reverse_empty: uint1_t = control_top == 0
            struct_reverse_entry_lo_zero: uint1_t = control_out.p0.rd_data.lo == 0
            struct_reverse_entry_hi_zero: uint1_t = control_out.p0.rd_data.hi == 0
            struct_reverse_entry_tag_zero: uint1_t = control_out.p0.rd_data.tag_hi == 0
            struct_reverse_entry_empty: uint1_t = struct_reverse_entry_lo_zero and struct_reverse_entry_hi_zero
            struct_reverse_entry_empty = struct_reverse_entry_empty and struct_reverse_entry_tag_zero
            struct_reverse_saved_q: uint1_t = control_out.p0.rd_data.tag_hi == CONTROL_SAVED_QUANTUM
            if not struct_reverse_top_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif struct_reverse_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif struct_reverse_entry_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif not struct_reverse_saved_q:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif phi == 0:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                struct_saved_q = control_out.p0.rd_data.lo[31:0]
                microstate = MICRO_STRUCT_REVERSE_POP
        elif micro_is_struct_reverse_pop:
            control_top = control_top - 1
            q = struct_saved_q
            phi = phi - 1
            pc = pc - 1
            microstate = MICRO_COMMIT
        elif micro_is_lambda_read:
            lambda_result_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            lambda_result_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            lambda_result_is_stop: uint1_t = lambda_result_opcode == MOP_STOP
            lambda_q_zero: uint1_t = q == 0
            lambda_argcnt_zero: uint1_t = argcnt == 1
            lambda_reconstruct: uint1_t = lambda_q_zero or lambda_argcnt_zero
            lambda_reconstruct = lambda_reconstruct or lambda_result_is_stop

            lambda_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            lambda_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            lambda_free_end: uint1_t = free_space == GRAPH_WORDS
            lambda_free_valid: uint1_t = lambda_free_low or lambda_free_end
            lambda_env_low: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
            lambda_env_end: uint1_t = env == GRAPH_WORDS
            lambda_env_valid: uint1_t = lambda_env_low or lambda_env_end
            lambda_no_bridge: uint1_t = env == free_space
            lambda_push_address: uint17_t = fsp + 1
            lambda_env_address_check: uint17_t = free_space - 1
            lambda_graph_gap: uint17_t = free_space - lambda_push_address
            lambda_graph_gap_wrapped: uint1_t = lambda_graph_gap[16]
            lambda_graph_gap_nonzero: uint1_t = lambda_graph_gap != 0
            lambda_graph_gap_not_wrapped: uint1_t = lambda_graph_gap_wrapped == 0
            lambda_push_before_frontier: uint1_t = lambda_graph_gap_not_wrapped and lambda_graph_gap_nonzero
            lambda_env_gap: uint17_t = lambda_env_address_check - lambda_push_address
            lambda_env_gap_wrapped: uint1_t = lambda_env_gap[16]
            lambda_env_gap_nonzero: uint1_t = lambda_env_gap != 0
            lambda_env_gap_not_wrapped: uint1_t = lambda_env_gap_wrapped == 0
            lambda_env_after_push: uint1_t = lambda_env_gap_not_wrapped and lambda_env_gap_nonzero

            lambda_result_is_app: uint1_t = lambda_result_opcode == MOP_APP
            lambda_result_is_app_var: uint1_t = lambda_result_opcode == MOP_APP_VAR
            lambda_result_is_ep: uint1_t = lambda_result_opcode == MOP_EP
            lambda_result_special: uint1_t = lambda_result_is_app or lambda_result_is_app_var
            lambda_result_special = lambda_result_special or lambda_result_is_ep
            lambda_generic_clone: uint1_t = lambda_result_special == 0
            lambda_beta_env_gap: uint17_t = lambda_env_address_check - fsp
            lambda_beta_gap_wrapped: uint1_t = lambda_beta_env_gap[16]
            lambda_beta_gap_nonzero: uint1_t = lambda_beta_env_gap != 0
            lambda_beta_gap_not_wrapped: uint1_t = lambda_beta_gap_wrapped == 0
            lambda_beta_has_space: uint1_t = lambda_beta_gap_not_wrapped and lambda_beta_gap_nonzero

            if not lambda_result_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif lambda_reconstruct:
                if not lambda_fsp_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not lambda_free_valid:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not lambda_push_before_frontier:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                else:
                    microstate = MICRO_LAMBDA_PUSH
            elif lambda_result_is_app:
                lambda_app_kind_ok: uint1_t = memory_out.p0.rd_data.hi[18:17] == DATA_SIGNED
                lambda_app_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                if not lambda_app_kind_ok:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif lambda_app_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    lambda_word = red2_word_t(
                        lo=memory_out.p0.rd_data.lo,
                        hi=67239936,
                    )
                    microstate = MICRO_LAMBDA_APP_CONTROL_READ
            elif lambda_result_is_ep:
                lambda_ep_kind_ok: uint1_t = memory_out.p0.rd_data.hi[18:17] == DATA_SIGNED
                lambda_ep_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                if not lambda_ep_kind_ok:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif lambda_ep_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    lambda_word = red2_word_t(
                        lo=memory_out.p0.rd_data.lo,
                        hi=75628544,
                    )
                    microstate = MICRO_LAMBDA_EP_CONTROL_READ
            elif lambda_result_is_app_var:
                lambda_app_var_kind_ok: uint1_t = memory_out.p0.rd_data.hi[18:17] == DATA_SIGNED
                lambda_app_var_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                if not lambda_app_var_kind_ok:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif lambda_app_var_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    lambda_phi_for_app_var: uint64_t = phi
                    lambda_app_var_binding: uint64_t = lambda_phi_for_app_var - memory_out.p0.rd_data.lo
                    lambda_word = red2_word_t(
                        lo=lambda_app_var_binding,
                        hi=109182976,
                    )
                    microstate = MICRO_LAMBDA_BETA_ENV
            elif lambda_generic_clone:
                lambda_beta_hi: uint64_t = memory_out.p0.rd_data.hi & 133169151
                lambda_word = red2_word_t(
                    lo=memory_out.p0.rd_data.lo,
                    hi=lambda_beta_hi,
                )
                microstate = MICRO_LAMBDA_BETA_ENV
            else:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
        elif micro_is_lambda_push:
            lambda_pushed: uint17_t = fsp + 1
            fsp = lambda_pushed[15:0]
            if app_rblock_active:
                argcnt = argcnt + 1
            else:
                argcnt = 1
            phi = phi + 1
            microstate = MICRO_LAMBDA_ENV
        elif micro_is_lambda_env:
            lambda_env_fsp_valid_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            lambda_env_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            lambda_env_free_end_exec: uint1_t = free_space == GRAPH_WORDS
            lambda_env_free_valid_exec: uint1_t = lambda_env_free_low_exec or lambda_env_free_end_exec
            lambda_env_layout_gap_exec: uint17_t = free_space - fsp
            lambda_env_layout_wrapped_exec: uint1_t = lambda_env_layout_gap_exec[16]
            lambda_env_layout_nonzero_exec: uint1_t = lambda_env_layout_gap_exec != 0
            lambda_env_layout_not_wrapped_exec: uint1_t = lambda_env_layout_wrapped_exec == 0
            lambda_env_layout_ok_exec: uint1_t = lambda_env_layout_not_wrapped_exec and lambda_env_layout_nonzero_exec
            lambda_env_parent_low_exec: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
            lambda_env_parent_end_exec: uint1_t = env == GRAPH_WORDS
            lambda_env_parent_valid_exec: uint1_t = lambda_env_parent_low_exec or lambda_env_parent_end_exec
            lambda_env_needs_bridge_exec: uint1_t = free_space != env
            lambda_env_count_exec: uint17_t = 1
            if lambda_env_needs_bridge_exec:
                lambda_env_count_exec = 2
            lambda_env_base_exec: uint17_t = free_space - lambda_env_count_exec
            lambda_env_base_gap_exec: uint17_t = lambda_env_base_exec - fsp
            lambda_env_base_wrapped_exec: uint1_t = lambda_env_base_gap_exec[16]
            lambda_env_base_nonzero_exec: uint1_t = lambda_env_base_gap_exec != 0
            lambda_env_base_not_wrapped_exec: uint1_t = lambda_env_base_wrapped_exec == 0
            lambda_env_base_after_fsp_exec: uint1_t = lambda_env_base_not_wrapped_exec and lambda_env_base_nonzero_exec
            if not lambda_env_fsp_valid_exec:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_env_free_valid_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_env_layout_ok_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_env_parent_valid_exec:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_env_base_after_fsp_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif lambda_env_needs_bridge_exec:
                microstate = MICRO_LAMBDA_ENV_BRIDGE
            else:
                microstate = MICRO_LAMBDA_ENV_BINDING
        elif micro_is_lambda_env_bridge:
            microstate = MICRO_LAMBDA_ENV_BINDING
        elif micro_is_lambda_env_binding:
            lambda_env_finish_needs_bridge: uint1_t = free_space != env
            lambda_env_finish_count: uint17_t = 1
            if lambda_env_finish_needs_bridge:
                lambda_env_finish_count = 2
            lambda_env_finish_base: uint17_t = free_space - lambda_env_finish_count
            env = lambda_env_finish_base
            free_space = lambda_env_finish_base
            if app_rblock_active:
                app_rblock_active = 0
            pc = pc + 1
            microstate = MICRO_COMMIT
        elif micro_is_lambda_beta_env:
            lambda_beta_fsp_valid_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            lambda_beta_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            lambda_beta_free_end_exec: uint1_t = free_space == GRAPH_WORDS
            lambda_beta_free_valid_exec: uint1_t = lambda_beta_free_low_exec or lambda_beta_free_end_exec
            lambda_beta_layout_gap_exec: uint17_t = free_space - fsp
            lambda_beta_layout_wrapped_exec: uint1_t = lambda_beta_layout_gap_exec[16]
            lambda_beta_layout_nonzero_exec: uint1_t = lambda_beta_layout_gap_exec != 0
            lambda_beta_layout_not_wrapped_exec: uint1_t = lambda_beta_layout_wrapped_exec == 0
            lambda_beta_layout_ok_exec: uint1_t = lambda_beta_layout_not_wrapped_exec and lambda_beta_layout_nonzero_exec
            lambda_beta_parent_low_exec: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
            lambda_beta_parent_end_exec: uint1_t = env == GRAPH_WORDS
            lambda_beta_parent_valid_exec: uint1_t = lambda_beta_parent_low_exec or lambda_beta_parent_end_exec
            lambda_beta_needs_bridge_exec: uint1_t = free_space != env
            lambda_beta_count_exec: uint17_t = 1
            if lambda_beta_needs_bridge_exec:
                lambda_beta_count_exec = 2
            lambda_beta_base_exec: uint17_t = free_space - lambda_beta_count_exec
            lambda_beta_base_gap_exec: uint17_t = lambda_beta_base_exec - fsp
            lambda_beta_base_wrapped_exec: uint1_t = lambda_beta_base_gap_exec[16]
            lambda_beta_base_nonzero_exec: uint1_t = lambda_beta_base_gap_exec != 0
            lambda_beta_base_not_wrapped_exec: uint1_t = lambda_beta_base_wrapped_exec == 0
            lambda_beta_base_after_fsp_exec: uint1_t = lambda_beta_base_not_wrapped_exec and lambda_beta_base_nonzero_exec
            if not lambda_beta_fsp_valid_exec:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_beta_free_valid_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_beta_layout_ok_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_beta_parent_valid_exec:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_beta_base_after_fsp_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif lambda_beta_needs_bridge_exec:
                microstate = MICRO_LAMBDA_BETA_BRIDGE
            else:
                microstate = MICRO_LAMBDA_BETA_BINDING
        elif micro_is_lambda_beta_bridge:
            microstate = MICRO_LAMBDA_BETA_BINDING
        elif micro_is_lambda_beta_binding:
            lambda_beta_finish_needs_bridge: uint1_t = free_space != env
            lambda_beta_finish_count: uint17_t = 1
            if lambda_beta_finish_needs_bridge:
                lambda_beta_finish_count = 2
            lambda_beta_finish_base: uint17_t = free_space - lambda_beta_finish_count
            env = lambda_beta_finish_base
            free_space = lambda_beta_finish_base
            q = q - 1
            fsp = fsp - 1
            argcnt = argcnt - 1
            pc = pc + 1
            microstate = MICRO_COMMIT
        elif micro_is_lambda_ep_control_read:
            lambda_ep_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            lambda_ep_top_end: uint1_t = control_top == CONTROL_WORDS
            lambda_ep_top_valid: uint1_t = lambda_ep_top_low or lambda_ep_top_end
            lambda_ep_top_empty: uint1_t = control_top == 0
            lambda_ep_entry_lo_zero: uint1_t = control_out.p0.rd_data.lo == 0
            lambda_ep_entry_hi_zero: uint1_t = control_out.p0.rd_data.hi == 0
            lambda_ep_entry_tag_zero: uint1_t = control_out.p0.rd_data.tag_hi == 0
            lambda_ep_entry_empty: uint1_t = lambda_ep_entry_lo_zero and lambda_ep_entry_hi_zero
            lambda_ep_entry_empty = lambda_ep_entry_empty and lambda_ep_entry_tag_zero
            lambda_ep_entry_address: uint1_t = control_out.p0.rd_data.tag_hi == CONTROL_ADDRESS
            if not lambda_ep_top_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif lambda_ep_top_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif lambda_ep_entry_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif not lambda_ep_entry_address:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                microstate = MICRO_LAMBDA_EP_CONTROL_POP
        elif micro_is_lambda_ep_control_pop:
            control_top = control_top - 1
            microstate = MICRO_LAMBDA_EP_ENV
        elif micro_is_lambda_ep_env:
            lambda_ep_fsp_valid_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            lambda_ep_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            lambda_ep_free_end_exec: uint1_t = free_space == GRAPH_WORDS
            lambda_ep_free_valid_exec: uint1_t = lambda_ep_free_low_exec or lambda_ep_free_end_exec
            lambda_ep_layout_gap_exec: uint17_t = free_space - fsp
            lambda_ep_layout_wrapped_exec: uint1_t = lambda_ep_layout_gap_exec[16]
            lambda_ep_layout_nonzero_exec: uint1_t = lambda_ep_layout_gap_exec != 0
            lambda_ep_layout_not_wrapped_exec: uint1_t = lambda_ep_layout_wrapped_exec == 0
            lambda_ep_layout_ok_exec: uint1_t = lambda_ep_layout_not_wrapped_exec and lambda_ep_layout_nonzero_exec
            lambda_ep_parent_low_exec: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
            lambda_ep_parent_end_exec: uint1_t = env == GRAPH_WORDS
            lambda_ep_parent_valid_exec: uint1_t = lambda_ep_parent_low_exec or lambda_ep_parent_end_exec
            lambda_ep_needs_bridge_exec: uint1_t = free_space != env
            lambda_ep_count_exec: uint17_t = 1
            if lambda_ep_needs_bridge_exec:
                lambda_ep_count_exec = 2
            lambda_ep_base_exec: uint17_t = free_space - lambda_ep_count_exec
            lambda_ep_base_gap_exec: uint17_t = lambda_ep_base_exec - fsp
            lambda_ep_base_wrapped_exec: uint1_t = lambda_ep_base_gap_exec[16]
            lambda_ep_base_nonzero_exec: uint1_t = lambda_ep_base_gap_exec != 0
            lambda_ep_base_not_wrapped_exec: uint1_t = lambda_ep_base_wrapped_exec == 0
            lambda_ep_base_after_fsp_exec: uint1_t = lambda_ep_base_not_wrapped_exec and lambda_ep_base_nonzero_exec
            if not lambda_ep_fsp_valid_exec:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_ep_free_valid_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_ep_layout_ok_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_ep_parent_valid_exec:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_ep_base_after_fsp_exec:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif lambda_ep_needs_bridge_exec:
                microstate = MICRO_LAMBDA_BETA_BRIDGE
            else:
                microstate = MICRO_LAMBDA_BETA_BINDING
        elif micro_is_lambda_app_control_read:
            lambda_app_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            lambda_app_top_end: uint1_t = control_top == CONTROL_WORDS
            lambda_app_top_valid: uint1_t = lambda_app_top_low or lambda_app_top_end
            lambda_app_top_empty: uint1_t = control_top == 0
            lambda_app_entry_lo_zero: uint1_t = control_out.p0.rd_data.lo == 0
            lambda_app_entry_hi_zero: uint1_t = control_out.p0.rd_data.hi == 0
            lambda_app_entry_tag_zero: uint1_t = control_out.p0.rd_data.tag_hi == 0
            lambda_app_entry_empty: uint1_t = lambda_app_entry_lo_zero and lambda_app_entry_hi_zero
            lambda_app_entry_empty = lambda_app_entry_empty and lambda_app_entry_tag_zero
            lambda_app_entry_address: uint1_t = control_out.p0.rd_data.tag_hi == CONTROL_ADDRESS
            if not lambda_app_top_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif lambda_app_top_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif lambda_app_entry_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif not lambda_app_entry_address:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                lambda_path = control_out.p0.rd_data.lo[31:0]
                microstate = MICRO_LAMBDA_APP_CONTROL_POP
        elif micro_is_lambda_app_control_pop:
            lambda_app_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            lambda_app_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            lambda_app_free_end: uint1_t = free_space == GRAPH_WORDS
            lambda_app_free_valid: uint1_t = lambda_app_free_low or lambda_app_free_end
            lambda_app_layout_gap: uint17_t = free_space - fsp
            lambda_app_layout_wrapped: uint1_t = lambda_app_layout_gap[16]
            lambda_app_layout_nonzero: uint1_t = lambda_app_layout_gap != 0
            lambda_app_layout_not_wrapped: uint1_t = lambda_app_layout_wrapped == 0
            lambda_app_layout_ok: uint1_t = lambda_app_layout_not_wrapped and lambda_app_layout_nonzero
            lambda_app_env_low: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
            lambda_app_env_end: uint1_t = env == GRAPH_WORDS
            lambda_app_env_valid: uint1_t = lambda_app_env_low or lambda_app_env_end
            lambda_app_needs_bridge: uint1_t = free_space != env
            lambda_app_count: uint17_t = 2
            if lambda_app_needs_bridge:
                lambda_app_count = 3
            lambda_app_base: uint17_t = free_space - lambda_app_count
            lambda_app_base_gap: uint17_t = lambda_app_base - fsp
            lambda_app_base_wrapped: uint1_t = lambda_app_base_gap[16]
            lambda_app_base_nonzero: uint1_t = lambda_app_base_gap != 0
            lambda_app_base_not_wrapped: uint1_t = lambda_app_base_wrapped == 0
            lambda_app_base_after_fsp: uint1_t = lambda_app_base_not_wrapped and lambda_app_base_nonzero
            control_top = control_top - 1
            if not lambda_app_fsp_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_app_free_valid:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_app_layout_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not lambda_app_env_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not lambda_app_base_after_fsp:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif lambda_app_needs_bridge:
                microstate = MICRO_LAMBDA_APP_BRIDGE
            else:
                microstate = MICRO_LAMBDA_APP_CLOSURE
        elif micro_is_lambda_app_bridge:
            microstate = MICRO_LAMBDA_APP_CLOSURE
        elif micro_is_lambda_app_closure:
            microstate = MICRO_LAMBDA_APP_POINTER
        elif micro_is_lambda_app_pointer:
            if app_rblock_active:
                rblock_none_first_done: uint1_t = lambda_path != 0
                if not rblock_none_first_done:
                    lambda_path = 1
                    microstate = MICRO_LAMBDA_APP_POINTER
                else:
                    rblock_finish_needs_bridge: uint1_t = free_space != env
                    rblock_finish_count: uint17_t = 3
                    if rblock_finish_needs_bridge:
                        rblock_finish_count = 4
                    rblock_finish_base: uint17_t = free_space - rblock_finish_count
                    env = rblock_finish_base
                    free_space = rblock_finish_base
                    lambda_path = 0
                    app_rblock_active = 0
                    pc = pc + 1
                    microstate = MICRO_COMMIT
            else:
                lambda_app_finish_needs_bridge: uint1_t = free_space != env
                lambda_app_finish_count: uint17_t = 2
                if lambda_app_finish_needs_bridge:
                    lambda_app_finish_count = 3
                lambda_app_finish_base: uint17_t = free_space - lambda_app_finish_count
                env = lambda_app_finish_base
                free_space = lambda_app_finish_base
                q = q - 1
                fsp = fsp - 1
                argcnt = argcnt - 1
                pc = pc + 1
                microstate = MICRO_COMMIT
        elif micro_is_app_control_read:
            app_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            app_top_end: uint1_t = control_top == CONTROL_WORDS
            app_top_valid: uint1_t = app_top_low or app_top_end
            app_top_empty: uint1_t = control_top == 0
            app_entry_lo_zero: uint1_t = control_out.p0.rd_data.lo == 0
            app_entry_hi_zero: uint1_t = control_out.p0.rd_data.hi == 0
            app_entry_tag_zero: uint1_t = control_out.p0.rd_data.tag_hi == 0
            app_entry_empty: uint1_t = app_entry_lo_zero and app_entry_hi_zero
            app_entry_empty = app_entry_empty and app_entry_tag_zero
            app_entry_is_address: uint1_t = control_out.p0.rd_data.tag_hi == CONTROL_ADDRESS
            app_entry_is_saved_definition: uint1_t = (
                control_out.p0.rd_data.tag_hi == CONTROL_SAVED_DEFINITION_PATH
            )
            app_parent_lane: uint32_t = control_out.p0.rd_data.lo[31:0]
            app_parent_low: uint1_t = app_parent_lane[31:8] == 0
            app_parent_end: uint1_t = app_parent_lane == GRAPH_WORDS
            app_parent_valid: uint1_t = app_parent_low or app_parent_end
            app_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            app_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            app_free_end: uint1_t = free_space == GRAPH_WORDS
            app_free_valid: uint1_t = app_free_low or app_free_end
            app_layout_gap: uint17_t = free_space - fsp
            app_layout_wrapped: uint1_t = app_layout_gap[16]
            app_layout_nonzero: uint1_t = app_layout_gap != 0
            app_layout_not_wrapped: uint1_t = app_layout_wrapped == 0
            app_layout_ok: uint1_t = app_layout_not_wrapped and app_layout_nonzero
            app_needs_bridge: uint1_t = app_parent_lane != free_space
            app_normalized_env: uint17_t = app_parent_lane[16:0]
            if app_needs_bridge:
                app_normalized_env = free_space - 1
            app_join_address: uint17_t = fsp + 1
            app_join_gap: uint17_t = app_normalized_env - app_join_address
            app_join_wrapped: uint1_t = app_join_gap[16]
            app_join_nonzero: uint1_t = app_join_gap != 0
            app_join_not_wrapped: uint1_t = app_join_wrapped == 0
            app_join_before_env: uint1_t = app_join_not_wrapped and app_join_nonzero
            if stop_cleanup_active:
                if app_top_empty:
                    stop_cleanup_active = 0
                    pc = pc + 1
                    halted = 1
                    microstate = MICRO_COMMIT
                elif app_entry_is_saved_definition:
                    microstate = MICRO_EP_REVERSE_PUBLISH
                else:
                    stop_cleanup_active = 0
                    pc = pc + 1
                    halted = 1
                    microstate = MICRO_COMMIT
            elif app_definition_active:
                app_definition_pop_saved = 0
                if not app_top_empty and app_entry_is_saved_definition:
                    app_definition_pop_saved = 1
                microstate = MICRO_EP_REVERSE_PUBLISH
            elif not app_top_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif app_top_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif app_entry_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif not app_entry_is_address:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif not app_fsp_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not app_free_valid:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not app_layout_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not app_parent_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not app_join_before_env:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            else:
                app_parent_env = app_parent_lane
                app_entry_env = app_normalized_env
                if app_needs_bridge:
                    microstate = MICRO_APP_BRIDGE
                else:
                    microstate = MICRO_APP_FRAME
        elif micro_is_app_bridge:
            microstate = MICRO_APP_FRAME
        elif micro_is_app_frame:
            microstate = MICRO_APP_JOIN
        elif micro_is_app_join:
            env = app_entry_env
            free_space = app_entry_env
            fsp = fsp + 1
            if app_rblock_active:
                argcnt = 0
                app_rblock_active = 0
            else:
                argcnt = 1
            pc = app_child_pc
            direction = DIRECTION_FORWARD
            prim_id = 0
            fire = 0
            microstate = MICRO_COMMIT
        elif micro_is_ep_chase:
            ep_target_in_range: uint1_t = ep_target[63:GRAPH_ADDR_BITS] == 0
            if not ep_target_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                ep_chase_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                ep_chase_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                ep_chase_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                ep_chase_is_ep: uint1_t = ep_chase_opcode == MOP_EP
                if not ep_chase_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif ep_chase_is_ep:
                    ep_chase_signed: uint1_t = ep_chase_kind == DATA_SIGNED
                    ep_chase_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    ep_hops_at_limit: uint1_t = ep_hops == GRAPH_WORDS - 1
                    if not ep_chase_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif ep_chase_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif ep_hops_at_limit:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        ep_target = memory_out.p0.rd_data.lo
                        ep_hops = ep_hops + 1
                else:
                    ep_terminal_word = memory_out.p0.rd_data
                    if direction_is_forward:
                        ep_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                        ep_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                        ep_free_end: uint1_t = free_space == GRAPH_WORDS
                        ep_free_valid: uint1_t = ep_free_low or ep_free_end
                        ep_destination: uint17_t = fsp + 1
                        ep_gap: uint17_t = free_space - ep_destination
                        ep_gap_wrapped: uint1_t = ep_gap[16]
                        ep_gap_nonzero: uint1_t = ep_gap != 0
                        ep_gap_not_wrapped: uint1_t = ep_gap_wrapped == 0
                        ep_destination_before_frontier: uint1_t = ep_gap_not_wrapped and ep_gap_nonzero
                        ep_control_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
                        ep_control_top_end: uint1_t = control_top == CONTROL_WORDS
                        ep_control_top_valid: uint1_t = ep_control_top_low or ep_control_top_end
                        if not ep_fsp_valid:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not ep_free_valid:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        elif not ep_destination_before_frontier:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        elif not ep_control_top_valid:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not ep_control_top_low:
                            red2_fault = FAULT_CONTROL_OVERFLOW
                            microstate = MICRO_FAULT
                        else:
                            microstate = MICRO_EP_FORWARD_PUBLISH
                    else:
                        microstate = MICRO_EP_REVERSE_CONTROL_READ
        elif micro_is_ep_forward_publish:
            fsp = fsp + 1
            argcnt = argcnt + 1
            control_top = control_top + 1
            pc = pc + 1
            microstate = MICRO_COMMIT
        elif micro_is_ep_reverse_control_read:
            ep_reverse_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            ep_reverse_top_end: uint1_t = control_top == CONTROL_WORDS
            ep_reverse_top_valid: uint1_t = ep_reverse_top_low or ep_reverse_top_end
            ep_reverse_top_empty: uint1_t = control_top == 0
            ep_reverse_entry_lo_zero: uint1_t = control_out.p0.rd_data.lo == 0
            ep_reverse_entry_hi_zero: uint1_t = control_out.p0.rd_data.hi == 0
            ep_reverse_entry_tag_zero: uint1_t = control_out.p0.rd_data.tag_hi == 0
            ep_reverse_entry_empty: uint1_t = ep_reverse_entry_lo_zero and ep_reverse_entry_hi_zero
            ep_reverse_entry_empty = ep_reverse_entry_empty and ep_reverse_entry_tag_zero
            ep_reverse_entry_address: uint1_t = control_out.p0.rd_data.tag_hi == CONTROL_ADDRESS
            ep_reverse_caller_lane: uint32_t = control_out.p0.rd_data.lo[31:0]
            ep_reverse_caller_differs: uint1_t = ep_reverse_caller_lane != env
            ep_reverse_terminal_opcode: uint5_t = ep_terminal_word.hi[25:21]
            ep_reverse_terminal_kind: uint2_t = ep_terminal_word.hi[18:17]
            ep_reverse_is_closure: uint1_t = ep_reverse_terminal_opcode == MOP_CLOSURE
            ep_reverse_is_ubv: uint1_t = ep_reverse_terminal_opcode == MOP_UBV
            ep_reverse_is_int: uint1_t = ep_reverse_terminal_opcode == MOP_INT
            ep_reverse_is_float: uint1_t = ep_reverse_terminal_opcode == MOP_FLOAT
            ep_reverse_is_char: uint1_t = ep_reverse_terminal_opcode == MOP_CHAR
            ep_reverse_is_sym: uint1_t = ep_reverse_terminal_opcode == MOP_SYM
            ep_reverse_is_prim0: uint1_t = ep_reverse_terminal_opcode == MOP_PRIM_0
            ep_reverse_is_prim1: uint1_t = ep_reverse_terminal_opcode == MOP_PRIM_1
            ep_reverse_is_prim2: uint1_t = ep_reverse_terminal_opcode == MOP_PRIM_2
            ep_reverse_atomic: uint1_t = ep_reverse_is_int or ep_reverse_is_float
            ep_reverse_atomic = ep_reverse_atomic or ep_reverse_is_char
            ep_reverse_atomic = ep_reverse_atomic or ep_reverse_is_sym
            ep_reverse_atomic = ep_reverse_atomic or ep_reverse_is_prim0
            ep_reverse_atomic = ep_reverse_atomic or ep_reverse_is_prim1
            ep_reverse_atomic = ep_reverse_atomic or ep_reverse_is_prim2
            ep_reverse_caller_low: uint1_t = ep_reverse_caller_lane[31:8] == 0
            ep_reverse_caller_end: uint1_t = ep_reverse_caller_lane == GRAPH_WORDS
            ep_reverse_caller_valid: uint1_t = ep_reverse_caller_low or ep_reverse_caller_end
            ep_reverse_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            ep_reverse_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            ep_reverse_free_end: uint1_t = free_space == GRAPH_WORDS
            ep_reverse_free_valid: uint1_t = ep_reverse_free_low or ep_reverse_free_end
            ep_reverse_layout_gap: uint17_t = free_space - fsp
            ep_reverse_layout_wrapped: uint1_t = ep_reverse_layout_gap[16]
            ep_reverse_layout_nonzero: uint1_t = ep_reverse_layout_gap != 0
            ep_reverse_layout_not_wrapped: uint1_t = ep_reverse_layout_wrapped == 0
            ep_reverse_layout_ok: uint1_t = ep_reverse_layout_not_wrapped and ep_reverse_layout_nonzero
            ep_reverse_marker_address: uint17_t = free_space - 1
            ep_reverse_marker_gap: uint17_t = ep_reverse_marker_address - fsp
            ep_reverse_marker_wrapped: uint1_t = ep_reverse_marker_gap[16]
            ep_reverse_marker_nonzero: uint1_t = ep_reverse_marker_gap != 0
            ep_reverse_marker_not_wrapped: uint1_t = ep_reverse_marker_wrapped == 0
            ep_reverse_marker_after_fsp: uint1_t = ep_reverse_marker_not_wrapped and ep_reverse_marker_nonzero
            ep_reverse_env_differs_from_free: uint1_t = env != free_space
            ep_reverse_closure_needs_marker: uint1_t = ep_reverse_caller_differs or ep_reverse_env_differs_from_free
            ep_reverse_closure_env: uint17_t = env
            if ep_reverse_closure_needs_marker:
                ep_reverse_closure_env = free_space - 1
            ep_reverse_join_address: uint17_t = fsp + 1
            ep_reverse_join_gap: uint17_t = ep_reverse_closure_env - ep_reverse_join_address
            ep_reverse_join_wrapped: uint1_t = ep_reverse_join_gap[16]
            ep_reverse_join_nonzero: uint1_t = ep_reverse_join_gap != 0
            ep_reverse_join_not_wrapped: uint1_t = ep_reverse_join_wrapped == 0
            ep_reverse_join_before_env: uint1_t = ep_reverse_join_not_wrapped and ep_reverse_join_nonzero
            ep_reverse_fire_active: uint1_t = fire != 0
            ep_reverse_fire_one: uint1_t = fire == 1
            ep_reverse_prim_missing: uint1_t = prim_id == 0
            if not ep_reverse_top_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif ep_reverse_top_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif ep_reverse_entry_empty:
                red2_fault = FAULT_CONTROL_UNDERFLOW
                microstate = MICRO_FAULT
            elif not ep_reverse_entry_address:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif ep_reverse_is_ubv:
                ep_reverse_ubv_signed: uint1_t = ep_reverse_terminal_kind == DATA_SIGNED
                ep_reverse_ubv_negative: uint1_t = ep_terminal_word.lo[63]
                ep_reverse_phi_wide: uint64_t = phi
                ep_reverse_index: uint64_t = ep_reverse_phi_wide - ep_terminal_word.lo
                ep_reverse_index_negative: uint1_t = ep_reverse_index[63]
                if not ep_reverse_ubv_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif ep_reverse_ubv_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif ep_reverse_index_negative:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_caller_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_fsp_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_free_valid:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_layout_ok:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_marker_after_fsp:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                else:
                    ep_caller_path = ep_reverse_caller_lane
                    ep_publish_word = red2_word_t(lo=ep_reverse_index, hi=111280128)
                    if ep_reverse_caller_differs:
                        microstate = MICRO_EP_REVERSE_MARKER
                    else:
                        microstate = MICRO_EP_REVERSE_PUBLISH
            elif ep_reverse_atomic:
                if ep_reverse_fire_active and ep_reverse_prim_missing:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_caller_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_fsp_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_free_valid:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_layout_ok:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif ep_reverse_caller_differs and not ep_reverse_marker_after_fsp:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                else:
                    ep_caller_path = ep_reverse_caller_lane
                    ep_atomic_hi: uint64_t = ep_terminal_word.hi & 133169151
                    ep_atomic_word: red2_word_t = red2_word_t(
                        lo=ep_terminal_word.lo, hi=ep_atomic_hi
                    )
                    ep_publish_word = ep_atomic_word
                    if ep_reverse_fire_one:
                        # Task-4 EP semantics are failure-atomic: for q>0, resolve
                        # and evaluate the firing scalar before caller-pop, PNP marker,
                        # or parent publication.  q==0 reaches the boundary but skips
                        # semantic dispatch entirely, including unknown scalar ids.
                        ep_scalar_active = 1
                        direct_scalar_active = 0
                        equality_atomic_active = 0
                        join_scalar_preflight_done = 0
                        join_scalar_contract = 0
                        join_scalar_right_word = red2_word_t(lo=0, hi=0)
                        join_scalar_return_ep = 0
                        join_parent_address = pc
                        join_publish_word = ep_atomic_word
                        if q == 0:
                            if ep_reverse_caller_differs:
                                microstate = MICRO_EP_REVERSE_MARKER
                            else:
                                microstate = MICRO_EP_REVERSE_PUBLISH
                        else:
                            join_frame_prim_id = prim_id
                            join_prim_meta_cursor = 0
                            join_prim_scalar_op = SCALAR_OP_NONE
                            join_true_literal_id = 0
                            join_false_literal_id = 0
                            join_nil_literal_id = 0
                            join_equal_star_literal_id = 0
                            join_equal_if_literal_id = 0
                            join_equality_continue_literal_id = 0
                            join_equal_stuck_literal_id = 0
                            microstate = MICRO_JOIN_PRIM_META_SCAN
                    else:
                        ep_scalar_active = 0
                        if ep_reverse_caller_differs:
                            microstate = MICRO_EP_REVERSE_MARKER
                        else:
                            microstate = MICRO_EP_REVERSE_PUBLISH
            elif ep_reverse_is_closure:
                if not ep_reverse_caller_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not ep_reverse_fsp_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not ep_reverse_free_valid:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not ep_reverse_layout_ok:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif ep_reverse_closure_needs_marker and not ep_reverse_marker_after_fsp:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not ep_reverse_join_before_env:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                else:
                    app_parent_env = ep_reverse_caller_lane
                    app_entry_env = ep_reverse_closure_env
                    app_child_pc = ep_target[15:0]
                    app_parent_pc = pc
                    app_rblock_active = 0
                    if ep_reverse_closure_needs_marker:
                        microstate = MICRO_APP_BRIDGE
                    else:
                        microstate = MICRO_APP_FRAME
            else:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
        elif micro_is_ep_reverse_marker:
            ep_reverse_new_env: uint17_t = free_space - 1
            env = ep_reverse_new_env
            free_space = ep_reverse_new_env
            microstate = MICRO_EP_REVERSE_PUBLISH
        elif micro_is_ep_reverse_publish:
            if stop_cleanup_active:
                stop_cleanup_last_saved: uint1_t = control_top == 1
                control_top = control_top - 1
                if stop_cleanup_last_saved:
                    stop_cleanup_active = 0
                    pc = pc + 1
                    halted = 1
                    microstate = MICRO_COMMIT
                else:
                    microstate = MICRO_APP_CONTROL_READ
            elif app_definition_active:
                if app_definition_pop_saved:
                    control_top = control_top - 1
                fsp = fsp - 1
                pc = app_child_pc
                direction = DIRECTION_FORWARD
                q = q - 1
                app_definition_active = 0
                app_definition_pop_saved = 0
                microstate = MICRO_COMMIT
            else:
                control_top = control_top - 1
                ep_publish_opcode: uint5_t = ep_publish_word.hi[25:21]
                ep_publish_is_var: uint1_t = ep_publish_opcode == MOP_VAR
                if ep_scalar_active:
                    # The fire==1 boundary was either suppressed by q==0 or fully
                    # preflighted through the shared scalar evaluator.  Only now make
                    # its architectural register effects visible with EP publication.
                    prim_id = 0
                    fire = 0
                    if join_scalar_contract:
                        fsp = pc
                        q = q - 1
                    ep_scalar_active = 0
                    join_prim_scalar_op = SCALAR_OP_NONE
                elif not ep_publish_is_var:
                    ep_publish_fire_active: uint1_t = fire != 0
                    if ep_publish_fire_active:
                        fire = fire - 1
                pc = pc - 1
                microstate = MICRO_COMMIT
        elif micro_is_join_parent_read:
            join_parent_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_parent_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_parent_is_app: uint1_t = join_parent_opcode == MOP_APP
            join_parent_is_ep_now: uint1_t = join_parent_opcode == MOP_EP
            join_parent_is_rblock: uint1_t = join_parent_opcode == MOP_RBLOCK
            join_parent_is_recp_now: uint1_t = join_parent_opcode == MOP_RECP
            join_parent_supported_opcode: uint1_t = join_parent_is_app or join_parent_is_ep_now
            join_parent_supported_opcode = join_parent_supported_opcode or join_parent_is_recp_now
            join_parent_known_opcode: uint1_t = join_parent_supported_opcode or join_parent_is_rblock
            if not join_parent_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_parent_known_opcode:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif not join_parent_supported_opcode:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            else:
                join_parent_word = memory_out.p0.rd_data
                join_parent_is_ep = join_parent_is_ep_now
                join_parent_is_recp = join_parent_is_recp_now
                if join_parent_is_recp_now:
                    # RECP publication always leaves the published child graph live;
                    # the parent becomes APP(root) rather than compacting the child.
                    join_preserve_fsp = 1
                # Search for the SUBGRAPH frame using a private cursor.  Keep
                # architectural control_top and RAM untouched until all JOIN
                # validation/publication work has succeeded.
                join_control_clear_index = control_top
                if join_parent_is_ep_now:
                    join_ep_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                    join_ep_signed: uint1_t = join_ep_kind == DATA_SIGNED
                    join_ep_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    join_ep_upper_zero: uint1_t = memory_out.p0.rd_data.lo[62:GRAPH_ADDR_BITS] == 0
                    if not join_ep_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_ep_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not join_ep_upper_zero:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        join_ep_target = memory_out.p0.rd_data.lo[15:0]
                        microstate = MICRO_JOIN_EP_TARGET_READ
                else:
                    microstate = MICRO_JOIN_FRAME_READ
        elif micro_is_join_ep_target_read:
            join_ep_target_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_ep_target_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_ep_target_is_closure: uint1_t = join_ep_target_opcode == MOP_CLOSURE
            if not join_ep_target_valid:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif not join_ep_target_is_closure:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                microstate = MICRO_JOIN_FRAME_READ
        elif micro_is_join_frame_read:
            join_control_top_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
            join_control_top_end: uint1_t = control_top == CONTROL_WORDS
            join_control_top_valid: uint1_t = join_control_top_low or join_control_top_end
            join_control_empty: uint1_t = control_top == 0
            join_frame_tag: uint4_t = control_out.p0.rd_data.tag_hi
            join_frame_is_saved_definition: uint1_t = join_frame_tag == CONTROL_SAVED_DEFINITION_PATH
            join_frame_is_subgraph: uint1_t = join_frame_tag == CONTROL_SUBGRAPH
            join_frame_env_lane: uint32_t = control_out.p0.rd_data.lo[31:0]
            join_frame_free_lane: uint32_t = control_out.p0.rd_data.lo[63:32]
            join_frame_prim_lane: uint32_t = control_out.p0.rd_data.hi[31:0]
            join_frame_fire_lane: uint32_t = control_out.p0.rd_data.hi[63:32]
            join_saved_frame_prim_missing: uint1_t = join_frame_prim_lane == 0
            join_saved_frame_fire_zero: uint1_t = join_frame_fire_lane == 0
            join_saved_frame_fire_one: uint1_t = join_frame_fire_lane == 1
            join_saved_q_nonzero: uint1_t = q != 0
            join_frame_env_low: uint1_t = join_frame_env_lane[31:8] == 0
            join_frame_env_end: uint1_t = join_frame_env_lane == GRAPH_WORDS
            join_frame_env_in_range: uint1_t = join_frame_env_low or join_frame_env_end
            join_frame_free_low: uint1_t = join_frame_free_lane[31:8] == 0
            join_frame_free_end: uint1_t = join_frame_free_lane == GRAPH_WORDS
            join_frame_free_in_range: uint1_t = join_frame_free_low or join_frame_free_end
            join_frame_env17: uint17_t = join_frame_env_lane[16:0]
            join_frame_free17: uint17_t = join_frame_free_lane[16:0]
            join_frontier_gap: uint17_t = join_frame_free17 - free_space
            join_frontier_wrapped: uint1_t = join_frontier_gap[16]
            join_frontier_ok: uint1_t = join_frontier_wrapped == 0
            join_env_from_frontier: uint17_t = join_frame_env17 - free_space
            join_env_from_frontier_wrapped: uint1_t = join_env_from_frontier[16]
            join_env_at_or_after_frontier: uint1_t = join_env_from_frontier_wrapped == 0
            join_free_from_env: uint17_t = join_frame_free17 - join_frame_env17
            join_free_from_env_wrapped: uint1_t = join_free_from_env[16]
            join_free_from_env_nonzero: uint1_t = join_free_from_env != 0
            join_env_before_frame_free: uint1_t = join_free_from_env_wrapped == 0
            join_env_before_frame_free = join_env_before_frame_free and join_free_from_env_nonzero
            join_env_inside_reclaim: uint1_t = join_env_at_or_after_frontier and join_env_before_frame_free
            if not join_control_top_valid:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif join_control_empty:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif join_frame_is_saved_definition:
                join_frame_next_index: uint17_t = join_control_clear_index - 1
                join_control_clear_index = join_frame_next_index
                if join_frame_next_index == 0:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                else:
                    microstate = MICRO_JOIN_FRAME_READ
            elif not join_frame_is_subgraph:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif join_saved_primitive and join_saved_frame_prim_missing:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif join_saved_primitive and join_saved_frame_fire_zero:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif not join_frame_free_in_range:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif not join_frame_env_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_frontier_ok:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif join_env_inside_reclaim:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                join_frame_env = join_frame_env17
                join_frame_free_space = join_frame_free17
                join_frame_prim_id = join_frame_prim_lane
                join_frame_fire = join_frame_fire_lane
                # Cursor is encoded as frame_index+1 while reading cursor-1.
                join_frame_index = join_control_clear_index - 1
                if join_saved_primitive and join_saved_frame_fire_one and join_saved_q_nonzero:
                    # Resolve semantic metadata before any JOIN publication.
                    # This preserves architectural failure atomicity for unknown
                    # primitive ids and unsupported primitive classes.
                    join_prim_meta_cursor = 0
                    join_prim_scalar_op = SCALAR_OP_NONE
                    microstate = MICRO_JOIN_PRIM_META_SCAN
                else:
                    microstate = MICRO_JOIN_TAIL_READ
        elif micro_is_join_prim_meta_scan:
            if prim0_meta_active:
                prim0_scan_valid: uint1_t = literal_meta_out.p0.rd_data.valid
                prim0_scan_id_match: uint1_t = literal_meta_out.p0.rd_data.literal_id == join_frame_prim_id
                prim0_scan_match: uint1_t = prim0_scan_valid and prim0_scan_id_match
                prim0_scan_last: uint1_t = join_prim_meta_cursor == LITERAL_META_WORDS - 1
                if prim0_scan_match:
                    prim0_scan_role: uint3_t = literal_meta_out.p0.rd_data.prim0_role
                    prim0_scan_host: uint3_t = literal_meta_out.p0.rd_data.host_op
                    prim0_scan_special: uint16_t = literal_meta_out.p0.rd_data.special_flags
                    prim0_scan_equal_star: uint1_t = prim0_scan_special[3]
                    prim0_scan_equal_if: uint1_t = prim0_scan_special[4]
                    prim0_scan_is_y: uint1_t = prim0_scan_role == PRIM0_ROLE_Y
                    prim0_scan_q_nonzero: uint1_t = q != 0
                    prim0_scan_arg_one: uint1_t = argcnt == 1
                    prim0_scan_host_clock: uint1_t = prim0_scan_host == HOST_CLOCK
                    prim0_scan_host_rx: uint1_t = prim0_scan_host == HOST_UART_RX
                    prim0_scan_direct_host: uint1_t = prim0_scan_host_clock or prim0_scan_host_rx
                    prim0_scan_host_eligible: uint1_t = prim0_scan_direct_host and prim0_scan_arg_one
                    prim0_scan_host_eligible = prim0_scan_host_eligible and prim0_scan_q_nonzero
                    prim0_scan_arg_zero: uint1_t = argcnt == 0
                    prim0_scan_arg_two: uint1_t = argcnt == 2
                    prim0_scan_arg_three: uint1_t = argcnt == 3
                    prim0_scan_not_zero: uint1_t = prim0_scan_arg_zero == 0
                    prim0_scan_not_one: uint1_t = prim0_scan_arg_one == 0
                    prim0_scan_not_two: uint1_t = prim0_scan_arg_two == 0
                    prim0_scan_not_three: uint1_t = prim0_scan_arg_three == 0
                    prim0_scan_ge3: uint1_t = prim0_scan_not_zero and prim0_scan_not_one
                    prim0_scan_ge3 = prim0_scan_ge3 and prim0_scan_not_two
                    prim0_scan_ge4: uint1_t = prim0_scan_ge3 and prim0_scan_not_three
                    prim0_scan_is_if: uint1_t = prim0_scan_role == PRIM0_ROLE_IF
                    prim0_scan_is_bind: uint1_t = prim0_scan_role == PRIM0_ROLE_IO_BIND
                    prim0_scan_is_then: uint1_t = prim0_scan_role == PRIM0_ROLE_IO_THEN
                    prim0_scan_is_deferred: uint1_t = prim0_scan_role == PRIM0_ROLE_DEFERRED
                    prim0_scan_arm_if: uint1_t = prim0_scan_is_if and prim0_scan_ge4
                    prim0_scan_arm_io: uint1_t = prim0_scan_is_bind or prim0_scan_is_then
                    prim0_scan_arm_io = prim0_scan_arm_io and prim0_scan_ge3
                    prim0_scan_arm: uint1_t = prim0_scan_arm_if or prim0_scan_arm_io
                    prim0_scan_arm = prim0_scan_arm and prim0_scan_q_nonzero
                    # __EQUAL_IF__ pre-arms its one-shot fire at the encoded
                    # visible argcnt threshold >=4, independently of quantum,
                    # then continues through the ordinary PRIM_0 role/host path.
                    # __EQUAL_STAR__ instead launches the private structural
                    # equality machine and remains a separate hardware slice.
                    if prim0_scan_equal_if and prim0_scan_ge4:
                        prim_id = join_frame_prim_id
                        fire = 1
                    if prim0_scan_equal_star:
                        # __EQUAL_STAR__ owns a five-word private task ending at pc.
                        # Encoded argcnt is internal+1, so CHILD_INIT requires 5.
                        equalstar_pc_too_low: uint1_t = pc == 0
                        equalstar_pc_too_low = equalstar_pc_too_low or pc == 1
                        equalstar_pc_too_low = equalstar_pc_too_low or pc == 2
                        equalstar_pc_too_low = equalstar_pc_too_low or pc == 3
                        equalstar_fsp_too_low: uint1_t = fsp == 0
                        equalstar_fsp_too_low = equalstar_fsp_too_low or fsp == 1
                        equalstar_fsp_too_low = equalstar_fsp_too_low or fsp == 2
                        equalstar_fsp_too_low = equalstar_fsp_too_low or fsp == 3
                        equalstar_argcnt_ok: uint1_t = argcnt == 5
                        equalstar_argcnt_bad: uint1_t = equalstar_argcnt_ok == 0
                        equalstar_entry_bad: uint1_t = equalstar_argcnt_bad or equalstar_pc_too_low
                        equalstar_entry_bad = equalstar_entry_bad or equalstar_fsp_too_low
                        if equalstar_entry_bad:
                            red2_fault = FAULT_ILLEGAL_TRANSITION
                            microstate = MICRO_FAULT
                        else:
                            equality_child_active = 1
                            equality_child_phase = 0
                            equality_child_task_root = pc - 4
                            equality_child_join_address = fsp - 4
                            equality_child_left = 0
                            equality_child_right = 0
                            equality_child_lambdas = 0
                            equality_child_descriptor = 0
                            equality_child_left_word = red2_word_t(lo=0, hi=0)
                            equality_child_right_word = red2_word_t(lo=0, hi=0)
                            equality_child_left_code_word = red2_word_t(lo=0, hi=0)
                            equality_child_build_join_word = red2_word_t(lo=0, hi=0)
                            equality_child_build_root = 0
                            equality_child_build_descriptor = 0
                            equality_child_build_app_mode = 0
                            equality_child_build_count = 0
                            equality_child_build_index = 0
                            equality_child_build_cursor = 0
                            equality_child_build_false_root = 0
                            equality_child_build_if_child_root = 0
                            equality_child_struct_left_base = 0
                            equality_child_struct_right_base = 0
                            equality_child_struct_left_count = 0
                            equality_child_struct_right_count = 0
                            join_special_meta_cursor = 0
                            join_true_literal_id = 0
                            join_false_literal_id = 0
                            join_nil_literal_id = 0
                            join_equal_star_literal_id = 0
                            join_equal_if_literal_id = 0
                            join_equality_continue_literal_id = 0
                            join_equal_stuck_literal_id = 0
                            prim0_meta_active = 0
                            microstate = MICRO_JOIN_SPECIAL_META_SCAN
                    elif prim0_scan_is_y:
                        prim0_y_has_arg: uint1_t = prim0_scan_not_zero and prim0_scan_not_one
                        prim0_y_can_contract: uint1_t = prim0_y_has_arg and prim0_scan_q_nonzero
                        if prim0_y_can_contract:
                            if pc == 0:
                                red2_fault = FAULT_INVALID_ADDRESS
                                microstate = MICRO_FAULT
                            else:
                                prim0_y_active = 1
                                prim0_y_needs_scratch = 0
                                prim0_y_argument_address = pc - 1
                                prim0_meta_active = 0
                                microstate = MICRO_JOIN_SCALAR_LEFT_READ
                        else:
                            # Exhausted/no-argument Y is ordinary passive PRIM_0.
                            microstate = MICRO_JOIN_SPECIAL_META_DONE
                    elif prim0_scan_host_eligible:
                        pending_host_op = prim0_scan_host
                        pending_host_argument = 0
                        prim0_meta_active = 0
                        microstate = MICRO_COMMIT
                    elif prim0_scan_is_deferred and prim0_scan_q_nonzero:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        if prim0_scan_arm:
                            prim_id = join_frame_prim_id
                            fire = 1
                        microstate = MICRO_JOIN_SPECIAL_META_DONE
                elif prim0_scan_last:
                    # Unknown literal ids have the oracle's default PASSIVE role.
                    microstate = MICRO_JOIN_SPECIAL_META_DONE
                else:
                    join_prim_meta_cursor = join_prim_meta_cursor + 1
            else:
                join_meta_valid: uint1_t = literal_meta_out.p0.rd_data.valid
                join_meta_id_matches: uint1_t = literal_meta_out.p0.rd_data.literal_id == join_frame_prim_id
                join_meta_matches: uint1_t = join_meta_valid and join_meta_id_matches
                join_meta_last: uint1_t = join_prim_meta_cursor == LITERAL_META_WORDS - 1
                if join_meta_matches:
                    join_meta_scalar: uint5_t = literal_meta_out.p0.rd_data.scalar_op
                    join_meta_special: uint16_t = literal_meta_out.p0.rd_data.special_flags
                    join_meta_equality: uint1_t = join_meta_special[5]
                    join_meta_equality_continue: uint1_t = join_meta_special[6]
                    join_meta_is_dec: uint1_t = join_meta_scalar == SCALAR_OP_DEC
                    join_meta_is_inc: uint1_t = join_meta_scalar == SCALAR_OP_INC
                    join_meta_is_negate: uint1_t = join_meta_scalar == SCALAR_OP_NEGATE
                    join_meta_is_abs: uint1_t = join_meta_scalar == SCALAR_OP_ABS
                    join_meta_is_floor: uint1_t = join_meta_scalar == SCALAR_OP_FLOOR
                    join_meta_is_ceiling: uint1_t = join_meta_scalar == SCALAR_OP_CEILING
                    join_meta_supported_numeric: uint1_t = join_meta_is_dec or join_meta_is_inc
                    join_meta_supported_numeric = join_meta_supported_numeric or join_meta_is_negate
                    join_meta_supported_numeric = join_meta_supported_numeric or join_meta_is_abs
                    join_meta_supported_numeric = join_meta_supported_numeric or join_meta_is_floor
                    join_meta_supported_numeric = join_meta_supported_numeric or join_meta_is_ceiling
                    join_meta_is_even: uint1_t = join_meta_scalar == SCALAR_OP_EVEN
                    join_meta_is_null: uint1_t = join_meta_scalar == SCALAR_OP_NULL
                    join_meta_is_not: uint1_t = join_meta_scalar == SCALAR_OP_NOT
                    join_meta_is_integer_p: uint1_t = join_meta_scalar == SCALAR_OP_INTEGER_P
                    join_meta_is_float_p: uint1_t = join_meta_scalar == SCALAR_OP_FLOAT_P
                    join_meta_is_char_p: uint1_t = join_meta_scalar == SCALAR_OP_CHAR_P
                    join_meta_is_symbol_p: uint1_t = join_meta_scalar == SCALAR_OP_SYMBOL_P
                    join_meta_is_add: uint1_t = join_meta_scalar == SCALAR_OP_ADD
                    join_meta_is_sub: uint1_t = join_meta_scalar == SCALAR_OP_SUB
                    join_meta_is_mul: uint1_t = join_meta_scalar == SCALAR_OP_MUL
                    join_meta_is_div: uint1_t = join_meta_scalar == SCALAR_OP_DIV
                    join_meta_is_expt: uint1_t = join_meta_scalar == SCALAR_OP_EXPT
                    join_meta_is_mod: uint1_t = join_meta_scalar == SCALAR_OP_MOD
                    join_meta_is_lt: uint1_t = join_meta_scalar == SCALAR_OP_LT
                    join_meta_is_gt: uint1_t = join_meta_scalar == SCALAR_OP_GT
                    join_meta_is_le: uint1_t = join_meta_scalar == SCALAR_OP_LE
                    join_meta_is_ge: uint1_t = join_meta_scalar == SCALAR_OP_GE
                    join_meta_is_eq: uint1_t = join_meta_scalar == SCALAR_OP_EQ
                    join_meta_is_max: uint1_t = join_meta_scalar == SCALAR_OP_MAX
                    join_meta_is_min: uint1_t = join_meta_scalar == SCALAR_OP_MIN
                    join_meta_supported_binary_int: uint1_t = join_meta_is_add or join_meta_is_sub
                    join_meta_supported_binary_int = join_meta_supported_binary_int or join_meta_is_mul
                    join_meta_supported_binary_int = join_meta_supported_binary_int or join_meta_is_div
                    join_meta_supported_binary_int = join_meta_supported_binary_int or join_meta_is_expt
                    join_meta_supported_binary_int = join_meta_supported_binary_int or join_meta_is_mod
                    join_meta_supported_binary_int = join_meta_supported_binary_int or join_meta_is_max
                    join_meta_supported_binary_int = join_meta_supported_binary_int or join_meta_is_min
                    join_meta_supported_binary_bool: uint1_t = join_meta_is_lt or join_meta_is_gt
                    join_meta_supported_binary_bool = join_meta_supported_binary_bool or join_meta_is_le
                    join_meta_supported_binary_bool = join_meta_supported_binary_bool or join_meta_is_ge
                    join_meta_supported_binary_bool = join_meta_supported_binary_bool or join_meta_is_eq
                    join_meta_supported_boolean: uint1_t = join_meta_is_even or join_meta_is_null
                    join_meta_supported_boolean = join_meta_supported_boolean or join_meta_is_not
                    join_meta_supported_boolean = join_meta_supported_boolean or join_meta_is_integer_p
                    join_meta_supported_boolean = join_meta_supported_boolean or join_meta_is_float_p
                    join_meta_supported_boolean = join_meta_supported_boolean or join_meta_is_char_p
                    join_meta_supported_boolean = join_meta_supported_boolean or join_meta_is_symbol_p
                    join_meta_supported_boolean = join_meta_supported_boolean or join_meta_supported_binary_bool
                    if join_meta_equality_continue:
                        # __EQUALITY_CONTINUE__ is a private one-shot primitive.
                        # Validate the returned boolean and both lower equality
                        # frames before publishing or clearing any architectural RAM.
                        equality_continue_active = 1
                        equality_continue_phase = 0
                        equality_continue_result_pc = 0
                        equality_continue_live_fsp = 0
                        equality_continue_saved_q = 0
                        equality_continue_child_id = 0
                        join_special_meta_cursor = 0
                        join_true_literal_id = 0
                        join_false_literal_id = 0
                        join_nil_literal_id = 0
                        join_equal_star_literal_id = 0
                        join_equal_if_literal_id = 0
                        join_equality_continue_literal_id = 0
                        join_equal_stuck_literal_id = 0
                        microstate = MICRO_JOIN_SPECIAL_META_SCAN
                    elif join_meta_equality:
                        # Public structural EQUAL? shares the binary operand-read
                        # pipeline with scalar '=', but has different constant and
                        # float semantics. q==0 clears the firing boundary without
                        # consulting TRUE/FALSE metadata, exactly like the oracle.
                        join_prim_scalar_op = SCALAR_OP_EQ
                        equality_atomic_active = 1
                        join_scalar_preflight_done = 0
                        join_scalar_contract = 0
                        if direct_scalar_active and q == 0:
                            prim_id = 0
                            fire = 0
                            pc = join_parent_address - 1
                            direct_scalar_active = 0
                            equality_atomic_active = 0
                            microstate = MICRO_COMMIT
                        else:
                            join_special_meta_cursor = 0
                            join_true_literal_id = 0
                            join_false_literal_id = 0
                            join_nil_literal_id = 0
                            join_equal_star_literal_id = 0
                            join_equal_if_literal_id = 0
                            join_equality_continue_literal_id = 0
                            join_equal_stuck_literal_id = 0
                            microstate = MICRO_JOIN_SPECIAL_META_SCAN
                    elif join_meta_supported_numeric or join_meta_supported_binary_int:
                        equality_atomic_active = 0
                        join_prim_scalar_op = join_meta_scalar
                        join_scalar_preflight_done = 0
                        join_scalar_contract = 0
                        if direct_scalar_active:
                            if q == 0:
                                # Scalar identity was resolved, but exhausted quantum
                                # suppresses the contraction exactly as _finish_scalar_result(None).
                                prim_id = 0
                                fire = 0
                                pc = join_parent_address - 1
                                direct_scalar_active = 0
                                microstate = MICRO_COMMIT
                            else:
                                join_publish_word = fetched_word
                                microstate = MICRO_JOIN_PUBLISH
                        elif ep_scalar_active:
                            microstate = MICRO_JOIN_PUBLISH
                        else:
                            microstate = MICRO_JOIN_TAIL_READ
                    elif join_meta_supported_boolean:
                        equality_atomic_active = 0
                        join_prim_scalar_op = join_meta_scalar
                        join_scalar_preflight_done = 0
                        join_scalar_contract = 0
                        if direct_scalar_active and q == 0:
                            prim_id = 0
                            fire = 0
                            pc = join_parent_address - 1
                            direct_scalar_active = 0
                            microstate = MICRO_COMMIT
                        else:
                            join_special_meta_cursor = 0
                            join_true_literal_id = 0
                            join_false_literal_id = 0
                            join_nil_literal_id = 0
                            join_equal_star_literal_id = 0
                            join_equal_if_literal_id = 0
                            join_equality_continue_literal_id = 0
                            join_equal_stuck_literal_id = 0
                            microstate = MICRO_JOIN_SPECIAL_META_SCAN
                    else:
                        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                        microstate = MICRO_FAULT
                elif join_meta_last:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                else:
                    join_prim_meta_cursor = join_prim_meta_cursor + 1
        elif micro_is_join_special_meta_scan:
            if prim0_y_active:
                control_top = control_top + 1
                q = q - 1
                pc = fsp + 1
                prim0_y_active = 0
                prim0_y_needs_scratch = 0
                microstate = MICRO_COMMIT
            else:
                join_special_valid: uint1_t = literal_meta_out.p0.rd_data.valid
                join_special_flags: uint16_t = literal_meta_out.p0.rd_data.special_flags
                join_special_true: uint1_t = join_special_flags[0]
                join_special_false: uint1_t = join_special_flags[1]
                join_special_nil: uint1_t = join_special_flags[2]
                join_special_equal_star: uint1_t = join_special_flags[3]
                join_special_equal_if: uint1_t = join_special_flags[4]
                join_special_equality_continue: uint1_t = join_special_flags[6]
                join_special_equal_stuck: uint1_t = join_special_flags[7]
                join_special_last: uint1_t = join_special_meta_cursor == LITERAL_META_WORDS - 1
                join_special_duplicate: uint1_t = 0
                if join_special_valid:
                    if join_special_true:
                        if join_true_literal_id != 0:
                            join_special_duplicate = 1
                        else:
                            join_true_literal_id = literal_meta_out.p0.rd_data.literal_id
                    if join_special_false:
                        if join_false_literal_id != 0:
                            join_special_duplicate = 1
                        else:
                            join_false_literal_id = literal_meta_out.p0.rd_data.literal_id
                    if join_special_nil:
                        if join_nil_literal_id != 0:
                            join_special_duplicate = 1
                        else:
                            join_nil_literal_id = literal_meta_out.p0.rd_data.literal_id
                    if join_special_equal_star:
                        if join_equal_star_literal_id != 0:
                            join_special_duplicate = 1
                        else:
                            join_equal_star_literal_id = literal_meta_out.p0.rd_data.literal_id
                    if join_special_equal_if:
                        if join_equal_if_literal_id != 0:
                            join_special_duplicate = 1
                        else:
                            join_equal_if_literal_id = literal_meta_out.p0.rd_data.literal_id
                    if join_special_equality_continue:
                        if join_equality_continue_literal_id != 0:
                            join_special_duplicate = 1
                        else:
                            join_equality_continue_literal_id = literal_meta_out.p0.rd_data.literal_id
                    if join_special_equal_stuck:
                        if join_equal_stuck_literal_id != 0:
                            join_special_duplicate = 1
                        else:
                            join_equal_stuck_literal_id = literal_meta_out.p0.rd_data.literal_id
                if join_special_duplicate:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif join_special_last:
                    microstate = MICRO_JOIN_SPECIAL_META_DONE
                else:
                    join_special_meta_cursor = join_special_meta_cursor + 1
        elif micro_is_join_special_meta_done:
            if equality_continue_active:
                equality_continue_phase = 0
                microstate = MICRO_JOIN_SCALAR_LEFT_READ
            elif equality_child_active:
                equality_child_phase = 0
                microstate = MICRO_JOIN_SCALAR_LEFT_READ
            elif prim0_y_active:
                if prim0_y_needs_scratch:
                    microstate = MICRO_JOIN_SPECIAL_META_SCAN
                else:
                    q = q - 1
                    pc = prim0_y_target
                    prim0_y_active = 0
                    microstate = MICRO_COMMIT
            elif prim0_meta_active:
                prim0_meta_fsp_ok_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                prim0_meta_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                prim0_meta_free_end_exec: uint1_t = free_space == GRAPH_WORDS
                prim0_meta_free_valid_exec: uint1_t = prim0_meta_free_low_exec or prim0_meta_free_end_exec
                prim0_meta_destination_exec: uint17_t = fsp + 1
                prim0_meta_gap_exec: uint17_t = free_space - prim0_meta_destination_exec
                prim0_meta_gap_wrapped_exec: uint1_t = prim0_meta_gap_exec[16]
                prim0_meta_gap_nonzero_exec: uint1_t = prim0_meta_gap_exec != 0
                prim0_meta_gap_ok_exec: uint1_t = prim0_meta_gap_wrapped_exec == 0
                prim0_meta_gap_ok_exec = prim0_meta_gap_ok_exec and prim0_meta_gap_nonzero_exec
                if not prim0_meta_fsp_ok_exec:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not prim0_meta_free_valid_exec:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not prim0_meta_gap_ok_exec:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                else:
                    fsp = prim0_meta_destination_exec[15:0]
                    argcnt = argcnt + 1
                    pc = prim0_meta_destination_exec[15:0] - 1
                    direction = DIRECTION_REVERSE
                    prim0_meta_active = 0
                    microstate = MICRO_COMMIT
            elif direct_scalar_active:
                join_publish_word = fetched_word
                microstate = MICRO_JOIN_PUBLISH
            elif ep_scalar_active:
                microstate = MICRO_JOIN_PUBLISH
            else:
                microstate = MICRO_JOIN_TAIL_READ
        elif micro_is_join_tail_read:
            join_published_root = join_result_address
            join_ep_general_root = 0
            join_ep_embedded = 0
            join_tail_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_tail_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_tail_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_tail_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            join_tail_definition_valid: uint1_t = memory_out.p0.rd_data.hi[16]
            join_single_word: uint1_t = fsp == join_result_address
            join_tail_is_var: uint1_t = join_tail_opcode == MOP_VAR
            join_tail_is_ep: uint1_t = join_tail_opcode == MOP_EP
            join_tail_is_app: uint1_t = join_tail_opcode == MOP_APP
            join_tail_is_app_var: uint1_t = join_tail_opcode == MOP_APP_VAR
            join_tail_is_int: uint1_t = join_tail_opcode == MOP_INT
            join_tail_is_float: uint1_t = join_tail_opcode == MOP_FLOAT
            join_tail_is_char: uint1_t = join_tail_opcode == MOP_CHAR
            join_tail_is_sym: uint1_t = join_tail_opcode == MOP_SYM
            join_tail_sym_shareable: uint1_t = join_tail_is_sym and not join_tail_definition_valid
            join_tail_atomic: uint1_t = join_tail_is_int or join_tail_is_float
            join_tail_atomic = join_tail_atomic or join_tail_is_char
            join_tail_atomic = join_tail_atomic or join_tail_sym_shareable
            join_parent_head: uint1_t = join_parent_word.hi[20]
            join_tail_is_prim0: uint1_t = join_tail_opcode == MOP_PRIM_0
            join_tail_is_prim1: uint1_t = join_tail_opcode == MOP_PRIM_1
            join_tail_is_prim2: uint1_t = join_tail_opcode == MOP_PRIM_2
            join_tail_inline: uint1_t = join_tail_is_int or join_tail_is_float
            join_tail_inline = join_tail_inline or join_tail_is_char
            join_tail_inline = join_tail_inline or join_tail_is_sym
            join_tail_inline = join_tail_inline or join_tail_is_prim0
            join_tail_inline = join_tail_inline or join_tail_is_prim1
            join_tail_inline = join_tail_inline or join_tail_is_prim2
            if not join_tail_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_single_word:
                join_multi_parent_opcode: uint5_t = join_parent_word.hi[25:21]
                join_multi_parent_is_app: uint1_t = join_multi_parent_opcode == MOP_APP
                join_multi_parent_is_ep: uint1_t = join_multi_parent_opcode == MOP_EP
                join_multi_parent_is_recp: uint1_t = join_multi_parent_opcode == MOP_RECP
                join_multi_parent_supports_app_graph: uint1_t = join_multi_parent_is_app or join_multi_parent_is_recp
                join_multi_parent_supports_ep_root: uint1_t = join_multi_parent_supports_app_graph or join_multi_parent_is_ep
                if join_tail_is_app:
                    join_multi_app_signed: uint1_t = join_tail_kind == DATA_SIGNED
                    join_multi_app_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    if not join_multi_parent_supports_app_graph:
                        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                        microstate = MICRO_FAULT
                    elif not join_multi_app_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_multi_app_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        # Narrow PUB_APP_SCAN slice: one or more APP descriptors
                        # sharing one target, followed by a head inline operator.
                        # The entire prefix is validated before the shared target
                        # descriptor is rewritten, preserving failure atomicity.
                        join_app_shared_target = memory_out.p0.rd_data.lo
                        join_app_second_target = 0
                        join_app_has_second_target = 0
                        join_app_first_write_needed = 0
                        join_app_second_write_needed = 0
                        join_app_cursor = join_result_address + 1
                        join_preserve_fsp = 1
                        join_published_root = join_result_address
                        microstate = MICRO_JOIN_APP_SCAN
                elif join_tail_head and join_tail_is_ep:
                    join_multi_ep_signed: uint1_t = join_tail_kind == DATA_SIGNED
                    join_multi_ep_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    if not join_multi_parent_supports_ep_root:
                        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                        microstate = MICRO_FAULT
                    elif not join_multi_ep_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_multi_ep_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        # General PUB_GRAPH root: the graph may contain unrelated
                        # live suffix after the root.  Publication must preserve
                        # fsp and return either this descriptor or a newly
                        # materialized root rather than use the single-word JOIN
                        # compaction shortcut.
                        join_ep_general_root = 1
                        join_preserve_fsp = 1
                        join_ep_chase_target = memory_out.p0.rd_data.lo
                        join_ep_hops = 0
                        join_ep_descriptor_hi = memory_out.p0.rd_data.hi
                        join_ep_descriptor_address = join_result_address
                        microstate = MICRO_JOIN_EP_CHASE
                elif join_parent_is_recp and join_tail_opcode == MOP_RBLOCK:
                    join_recp_rblock_cursor = join_result_address
                    join_recp_rblock_count = 0
                    join_preserve_fsp = 1
                    microstate = MICRO_JOIN_RECP_RBLOCK_SCAN
                elif join_tail_is_app_var:
                    if not join_multi_parent_supports_app_graph:
                        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                        microstate = MICRO_FAULT
                    else:
                        join_flat_cursor = join_result_address + 1
                        join_preserve_fsp = 1
                        microstate = MICRO_JOIN_FLAT_SCAN
                elif not join_multi_parent_supports_app_graph:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
                elif join_tail_head and join_tail_inline:
                    join_publish_word = red2_word_t(
                        lo=join_result_address,
                        hi=69337088,
                    )
                    join_needs_ep_cache = 0
                    join_preserve_fsp = 1
                    microstate = MICRO_JOIN_PUBLISH
                elif join_tail_head:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
                elif not join_tail_inline:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
                else:
                    join_flat_cursor = join_result_address + 1
                    microstate = MICRO_JOIN_FLAT_SCAN
            elif not join_tail_head:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            elif join_tail_is_var:
                join_var_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                if join_tail_kind != DATA_SIGNED:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_var_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_var_hi: uint64_t = 71434240
                    if join_parent_head:
                        join_var_hi = 112328704
                    join_publish_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=join_var_hi)
                    join_needs_ep_cache = 0
                    microstate = MICRO_JOIN_PUBLISH
            elif join_tail_is_ep:
                join_ep_descriptor_signed: uint1_t = join_tail_kind == DATA_SIGNED
                join_ep_descriptor_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                if not join_ep_descriptor_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_ep_descriptor_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_ep_chase_target = memory_out.p0.rd_data.lo
                    join_ep_hops = 0
                    join_ep_descriptor_hi = memory_out.p0.rd_data.hi
                    join_ep_descriptor_address = join_result_address
                    microstate = MICRO_JOIN_EP_CHASE
            elif join_tail_atomic:
                join_atomic_base_hi: uint64_t = memory_out.p0.rd_data.hi & 132644863
                join_atomic_parent_hi: uint64_t = join_atomic_base_hi
                if join_parent_head:
                    join_atomic_parent_hi = join_atomic_parent_hi | 1048576
                if join_parent_is_ep:
                    join_publish_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=join_atomic_base_hi)
                    join_cache_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=join_atomic_base_hi | 524288)
                    join_needs_ep_cache = 1
                else:
                    join_publish_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=join_atomic_parent_hi)
                    join_needs_ep_cache = 0
                microstate = MICRO_JOIN_PUBLISH
            else:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
        elif micro_is_join_publish:
            if join_scalar_active and not join_scalar_preflight_done:
                join_scalar_opcode: uint5_t = join_publish_word.hi[25:21]
                join_scalar_kind: uint2_t = join_publish_word.hi[18:17]
                join_scalar_is_int: uint1_t = join_scalar_opcode == MOP_INT
                join_scalar_is_float: uint1_t = join_scalar_opcode == MOP_FLOAT
                join_scalar_is_char: uint1_t = join_scalar_opcode == MOP_CHAR
                join_scalar_is_sym: uint1_t = join_scalar_opcode == MOP_SYM
                join_scalar_is_prim0: uint1_t = join_scalar_opcode == MOP_PRIM_0
                join_scalar_is_prim1: uint1_t = join_scalar_opcode == MOP_PRIM_1
                join_scalar_is_prim2: uint1_t = join_scalar_opcode == MOP_PRIM_2
                join_scalar_is_app: uint1_t = join_scalar_opcode == MOP_APP
                join_scalar_is_app_var: uint1_t = join_scalar_opcode == MOP_APP_VAR
                join_scalar_is_var: uint1_t = join_scalar_opcode == MOP_VAR
                join_scalar_is_signed: uint1_t = join_scalar_kind == DATA_SIGNED
                join_scalar_is_literal: uint1_t = join_scalar_kind == DATA_LITERAL_ID
                join_scalar_int_contract: uint1_t = join_scalar_is_int and join_scalar_is_signed
                join_scalar_symbol_opcode: uint1_t = join_scalar_is_sym or join_scalar_is_prim0
                join_scalar_symbol_opcode = join_scalar_symbol_opcode or join_scalar_is_prim1
                join_scalar_symbol_opcode = join_scalar_symbol_opcode or join_scalar_is_prim2
                join_scalar_symbol_value: uint1_t = join_scalar_symbol_opcode and join_scalar_is_literal
                join_scalar_blocked_predicate: uint1_t = join_scalar_is_app or join_scalar_is_app_var
                join_scalar_blocked_predicate = join_scalar_blocked_predicate or join_scalar_is_var

                join_scalar_is_dec: uint1_t = join_prim_scalar_op == SCALAR_OP_DEC
                join_scalar_is_inc: uint1_t = join_prim_scalar_op == SCALAR_OP_INC
                join_scalar_is_negate: uint1_t = join_prim_scalar_op == SCALAR_OP_NEGATE
                join_scalar_is_abs: uint1_t = join_prim_scalar_op == SCALAR_OP_ABS
                join_scalar_is_floor: uint1_t = join_prim_scalar_op == SCALAR_OP_FLOOR
                join_scalar_is_ceiling: uint1_t = join_prim_scalar_op == SCALAR_OP_CEILING
                join_scalar_is_even: uint1_t = join_prim_scalar_op == SCALAR_OP_EVEN
                join_scalar_is_null: uint1_t = join_prim_scalar_op == SCALAR_OP_NULL
                join_scalar_is_not: uint1_t = join_prim_scalar_op == SCALAR_OP_NOT
                join_scalar_is_integer_p: uint1_t = join_prim_scalar_op == SCALAR_OP_INTEGER_P
                join_scalar_is_float_p: uint1_t = join_prim_scalar_op == SCALAR_OP_FLOAT_P
                join_scalar_is_char_p: uint1_t = join_prim_scalar_op == SCALAR_OP_CHAR_P
                join_scalar_is_symbol_p: uint1_t = join_prim_scalar_op == SCALAR_OP_SYMBOL_P
                join_scalar_is_add: uint1_t = join_prim_scalar_op == SCALAR_OP_ADD
                join_scalar_is_sub: uint1_t = join_prim_scalar_op == SCALAR_OP_SUB
                join_scalar_is_mul: uint1_t = join_prim_scalar_op == SCALAR_OP_MUL
                join_scalar_is_div: uint1_t = join_prim_scalar_op == SCALAR_OP_DIV
                join_scalar_is_expt: uint1_t = join_prim_scalar_op == SCALAR_OP_EXPT
                join_scalar_is_mod: uint1_t = join_prim_scalar_op == SCALAR_OP_MOD
                join_scalar_is_lt: uint1_t = join_prim_scalar_op == SCALAR_OP_LT
                join_scalar_is_gt: uint1_t = join_prim_scalar_op == SCALAR_OP_GT
                join_scalar_is_le: uint1_t = join_prim_scalar_op == SCALAR_OP_LE
                join_scalar_is_ge: uint1_t = join_prim_scalar_op == SCALAR_OP_GE
                join_scalar_is_eq: uint1_t = join_prim_scalar_op == SCALAR_OP_EQ
                join_scalar_is_max: uint1_t = join_prim_scalar_op == SCALAR_OP_MAX
                join_scalar_is_min: uint1_t = join_prim_scalar_op == SCALAR_OP_MIN
                join_scalar_binary_here: uint1_t = join_scalar_is_add or join_scalar_is_sub
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_mul
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_div
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_expt
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_mod
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_lt
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_gt
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_le
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_ge
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_eq
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_max
                join_scalar_binary_here = join_scalar_binary_here or join_scalar_is_min

                join_scalar_numeric: uint1_t = join_scalar_is_dec or join_scalar_is_inc
                join_scalar_numeric = join_scalar_numeric or join_scalar_is_negate
                join_scalar_numeric = join_scalar_numeric or join_scalar_is_abs
                join_scalar_numeric = join_scalar_numeric or join_scalar_is_floor
                join_scalar_numeric = join_scalar_numeric or join_scalar_is_ceiling
                join_scalar_predicate: uint1_t = join_scalar_is_integer_p or join_scalar_is_float_p
                join_scalar_predicate = join_scalar_predicate or join_scalar_is_char_p
                join_scalar_predicate = join_scalar_predicate or join_scalar_is_symbol_p
                join_scalar_supported: uint1_t = join_scalar_numeric or join_scalar_is_even
                join_scalar_supported = join_scalar_supported or join_scalar_is_null
                join_scalar_supported = join_scalar_supported or join_scalar_is_not
                join_scalar_supported = join_scalar_supported or join_scalar_predicate
                join_scalar_supported = join_scalar_supported or join_scalar_binary_here

                join_scalar_int_min: uint1_t = join_publish_word.lo == 9223372036854775808
                join_scalar_int_max: uint1_t = join_publish_word.lo == 9223372036854775807
                join_scalar_negative: uint1_t = join_publish_word.lo[63]
                join_scalar_min_overflow_op: uint1_t = join_scalar_is_dec or join_scalar_is_negate
                join_scalar_min_overflow_op = join_scalar_min_overflow_op or join_scalar_is_abs
                join_scalar_min_overflow: uint1_t = join_scalar_int_min and join_scalar_min_overflow_op
                join_scalar_max_overflow: uint1_t = join_scalar_int_max and join_scalar_is_inc
                join_scalar_overflow: uint1_t = join_scalar_min_overflow or join_scalar_max_overflow

                if join_scalar_binary_here:
                    join_scalar_right_word = join_publish_word
                    join_scalar_return_ep = 0
                    microstate = MICRO_JOIN_SCALAR_LEFT_READ
                elif not join_scalar_supported:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
                elif join_scalar_numeric:
                    if join_scalar_is_float:
                        red2_fault = FAULT_UNSUPPORTED_VALUE
                        microstate = MICRO_FAULT
                    elif join_scalar_int_contract:
                        if join_scalar_overflow:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_scalar_result_payload: uint64_t = join_publish_word.lo
                            if join_scalar_is_dec:
                                join_scalar_result_payload = join_publish_word.lo - 1
                            elif join_scalar_is_inc:
                                join_scalar_result_payload = join_publish_word.lo + 1
                            elif join_scalar_is_negate:
                                join_scalar_result_payload = 0 - join_publish_word.lo
                            elif join_scalar_is_abs and join_scalar_negative:
                                join_scalar_result_payload = 0 - join_publish_word.lo
                            join_publish_word = red2_word_t(lo=join_scalar_result_payload, hi=85065728)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                elif join_scalar_is_even:
                    if join_scalar_is_float:
                        red2_fault = FAULT_UNSUPPORTED_VALUE
                        microstate = MICRO_FAULT
                    elif join_scalar_int_contract:
                        join_scalar_even: uint1_t = join_publish_word.lo[0] == 0
                        join_scalar_bool_id: uint32_t = join_false_literal_id
                        if join_scalar_even:
                            join_scalar_bool_id = join_true_literal_id
                        if join_scalar_bool_id == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_scalar_bool_id, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                elif join_scalar_is_null:
                    join_scalar_null_contract: uint1_t = 0
                    join_scalar_null_value: uint1_t = 0
                    if join_scalar_symbol_value:
                        join_scalar_null_contract = 1
                        join_scalar_null_value = join_publish_word.lo == join_nil_literal_id
                    elif not join_scalar_blocked_predicate:
                        join_scalar_null_contract = 1
                    if join_scalar_null_contract:
                        join_scalar_bool_id_null: uint32_t = join_false_literal_id
                        if join_scalar_null_value:
                            join_scalar_bool_id_null = join_true_literal_id
                        if join_scalar_bool_id_null == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_scalar_bool_id_null, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                elif join_scalar_is_not:
                    join_scalar_true_id_present: uint1_t = join_true_literal_id != 0
                    join_scalar_false_id_present: uint1_t = join_false_literal_id != 0
                    join_scalar_not_true: uint1_t = join_scalar_symbol_value and join_scalar_true_id_present
                    join_scalar_not_true = join_scalar_not_true and join_publish_word.lo == join_true_literal_id
                    join_scalar_not_false: uint1_t = join_scalar_symbol_value and join_scalar_false_id_present
                    join_scalar_not_false = join_scalar_not_false and join_publish_word.lo == join_false_literal_id
                    if join_scalar_not_true or join_scalar_not_false:
                        join_scalar_bool_id_not: uint32_t = join_true_literal_id
                        if join_scalar_not_true:
                            join_scalar_bool_id_not = join_false_literal_id
                        if join_scalar_bool_id_not == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_scalar_bool_id_not, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                else:
                    if join_scalar_blocked_predicate:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                    else:
                        join_scalar_predicate_value: uint1_t = 0
                        if join_scalar_is_integer_p:
                            join_scalar_predicate_value = join_scalar_is_int
                        elif join_scalar_is_float_p:
                            join_scalar_predicate_value = join_scalar_is_float
                        elif join_scalar_is_char_p:
                            join_scalar_predicate_value = join_scalar_is_char
                        elif join_scalar_is_symbol_p:
                            join_scalar_predicate_value = join_scalar_symbol_value
                        join_scalar_bool_id_predicate: uint32_t = join_false_literal_id
                        if join_scalar_predicate_value:
                            join_scalar_bool_id_predicate = join_true_literal_id
                        if join_scalar_bool_id_predicate == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_scalar_bool_id_predicate, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
            else:
                if ep_scalar_active:
                    # Scalar preflight is complete and no architectural EP state has
                    # changed yet.  Hand the preflighted result back to the ordinary
                    # reverse-EP marker/pop/publication sequence.
                    ep_publish_word = join_publish_word
                    if ep_caller_path != env:
                        microstate = MICRO_EP_REVERSE_MARKER
                    else:
                        microstate = MICRO_EP_REVERSE_PUBLISH
                elif direct_scalar_active:
                    # The direct MOVE-BACKWARD firing path has no subgraph frame to
                    # reclaim.  The combinational write for this cycle publishes the
                    # scalar result at the original pc when contraction succeeded; a
                    # stuck scalar rewrites the identical original word.
                    prim_id = 0
                    fire = 0
                    if join_scalar_contract:
                        fsp = join_parent_address
                        q = q - 1
                    pc = join_parent_address - 1
                    direct_scalar_active = 0
                    microstate = MICRO_COMMIT
                else:
                    env = join_frame_env
                    free_space = join_frame_free_space
                    s_a = join_published_root + 1
                    if not join_preserve_fsp:
                        if join_parent_word.hi[20]:
                            fsp = join_parent_address
                        else:
                            fsp = fsp - 2
                    if join_scalar_contract and join_scalar_binary:
                        fsp = join_parent_address
                    # Parent/result publication is complete.  Clear the original control
                    # suffix down through the located frame; entries below survive.
                    join_control_clear_index = control_top
                    microstate = MICRO_JOIN_CONTROL_CLEAR
        elif micro_is_join_control_clear:
            join_control_next_index: uint17_t = join_control_clear_index - 1
            join_control_clear_index = join_control_next_index
            if join_control_next_index == join_frame_index:
                control_top = join_frame_index
                join_frame_fire_one_at_restore: uint1_t = join_frame_fire == 1
                if join_scalar_active:
                    prim_id = 0
                    fire = 0
                    if join_scalar_contract:
                        q = q - 1
                elif join_saved_primitive:
                    if join_frame_fire_one_at_restore:
                        # q==0 reaches the firing boundary but must not execute the
                        # primitive; ordinary reconstruction clears the exhausted
                        # countdown.  q>0 fire==1 was preflighted as scalar above.
                        prim_id = 0
                        fire = 0
                    else:
                        # Countdown steps greater than one are structural bookkeeping,
                        # not semantic contractions, and therefore survive q==0.
                        prim_id = join_frame_prim_id
                        fire = join_frame_fire - 1
                else:
                    prim_id = 0
                    fire = 0
                if join_needs_ep_cache:
                    microstate = MICRO_JOIN_EP_CACHE
                else:
                    pc = join_parent_address - 1
                    microstate = MICRO_COMMIT
            else:
                microstate = MICRO_JOIN_CONTROL_CLEAR
        elif micro_is_join_ep_cache:
            pc = join_parent_address - 1
            microstate = MICRO_COMMIT
        elif micro_is_join_ep_chase:
            join_ep_target_in_range: uint1_t = join_ep_chase_target[63:GRAPH_ADDR_BITS] == 0
            if not join_ep_target_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                join_ep_target_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                join_ep_target_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                join_ep_target_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                join_ep_target_definition_valid: uint1_t = memory_out.p0.rd_data.hi[16]
                join_ep_target_is_ep: uint1_t = join_ep_target_opcode == MOP_EP
                if not join_ep_target_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_ep_target_is_ep:
                    join_ep_next_signed: uint1_t = join_ep_target_kind == DATA_SIGNED
                    join_ep_next_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    join_ep_hops_at_limit: uint1_t = join_ep_hops == GRAPH_WORDS - 1
                    if not join_ep_next_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_ep_next_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_ep_hops_at_limit:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        join_ep_chase_target = memory_out.p0.rd_data.lo
                        join_ep_hops = join_ep_hops + 1
                else:
                    join_ep_target17: uint17_t = join_ep_chase_target[16:0]
                    join_ep_after_frontier_gap: uint17_t = join_ep_target17 - free_space
                    join_ep_after_frontier_wrapped: uint1_t = join_ep_after_frontier_gap[16]
                    join_ep_at_or_after_frontier: uint1_t = join_ep_after_frontier_wrapped == 0
                    join_ep_before_frame_gap: uint17_t = join_frame_free_space - join_ep_target17
                    join_ep_before_frame_wrapped: uint1_t = join_ep_before_frame_gap[16]
                    join_ep_before_frame_nonzero: uint1_t = join_ep_before_frame_gap != 0
                    join_ep_before_frame: uint1_t = join_ep_before_frame_wrapped == 0
                    join_ep_before_frame = join_ep_before_frame and join_ep_before_frame_nonzero
                    join_ep_inside_reclaim: uint1_t = join_ep_at_or_after_frontier and join_ep_before_frame
                    join_ep_target_is_int: uint1_t = join_ep_target_opcode == MOP_INT
                    join_ep_target_is_float: uint1_t = join_ep_target_opcode == MOP_FLOAT
                    join_ep_target_is_char: uint1_t = join_ep_target_opcode == MOP_CHAR
                    join_ep_target_is_sym: uint1_t = join_ep_target_opcode == MOP_SYM
                    join_ep_target_sym_shareable: uint1_t = join_ep_target_is_sym and not join_ep_target_definition_valid
                    join_ep_target_atomic: uint1_t = join_ep_target_is_int or join_ep_target_is_float
                    join_ep_target_atomic = join_ep_target_atomic or join_ep_target_is_char
                    join_ep_target_atomic = join_ep_target_atomic or join_ep_target_sym_shareable
                    join_ep_target_is_ubv: uint1_t = join_ep_target_opcode == MOP_UBV
                    join_ep_target_is_closure: uint1_t = join_ep_target_opcode == MOP_CLOSURE
                    join_ep_target_is_rec: uint1_t = join_ep_target_opcode == MOP_REC
                    if not join_ep_inside_reclaim:
                        # The EP terminal is already outside the child interval
                        # [free_space, frame_free_space), so reclaim cannot make
                        # the descriptor dangle.  Preserve the EP in place and
                        # publish the descriptor root through the parent APP.
                        join_publish_word = red2_word_t(
                            lo=join_result_address,
                            hi=69337088,
                        )
                        join_needs_ep_cache = 0
                        join_preserve_fsp = 1
                        microstate = MICRO_JOIN_PUBLISH
                    elif join_ep_target_atomic:
                        join_ep_atomic_hi: uint64_t = memory_out.p0.rd_data.hi & 132644863
                        join_ep_atomic_hi = join_ep_atomic_hi | 1048576
                        join_ep_publish_word = red2_word_t(
                            lo=memory_out.p0.rd_data.lo,
                            hi=join_ep_atomic_hi,
                        )
                        join_parent_head_ep_atomic: uint1_t = join_parent_word.hi[20]
                        join_ep_parent_atomic_hi: uint64_t = memory_out.p0.rd_data.hi & 132644863
                        if join_parent_head_ep_atomic:
                            join_ep_parent_atomic_hi = join_ep_parent_atomic_hi | 1048576
                        if join_ep_general_root:
                            join_publish_word = red2_word_t(
                                lo=join_result_address,
                                hi=69337088,
                            )
                            join_needs_ep_cache = 0
                            join_preserve_fsp = 1
                        elif join_parent_is_ep:
                            join_publish_word = red2_word_t(
                                lo=memory_out.p0.rd_data.lo,
                                hi=memory_out.p0.rd_data.hi & 132644863,
                            )
                            join_cache_word = red2_word_t(
                                lo=memory_out.p0.rd_data.lo,
                                hi=(memory_out.p0.rd_data.hi & 132644863) | 524288,
                            )
                            join_needs_ep_cache = 1
                        else:
                            join_publish_word = red2_word_t(
                                lo=memory_out.p0.rd_data.lo,
                                hi=join_ep_parent_atomic_hi,
                            )
                            join_needs_ep_cache = 0
                        microstate = MICRO_JOIN_EP_RESULT_WRITE
                    elif join_ep_target_is_ubv:
                        join_ep_ubv_signed: uint1_t = join_ep_target_kind == DATA_SIGNED
                        join_ep_phi_wide: uint64_t = phi
                        join_ep_ubv_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                        join_ep_ubv_index: uint64_t = join_ep_phi_wide - memory_out.p0.rd_data.lo
                        if join_ep_ubv_negative:
                            join_ep_ubv_magnitude: uint64_t = 0 - memory_out.p0.rd_data.lo
                            join_ep_ubv_index = join_ep_phi_wide + join_ep_ubv_magnitude
                        join_ep_ubv_index_negative: uint1_t = join_ep_ubv_index[63]
                        if not join_ep_ubv_signed:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not join_ep_ubv_negative and join_ep_ubv_index_negative:
                            red2_fault = FAULT_ILLEGAL_TRANSITION
                            microstate = MICRO_FAULT
                        else:
                            join_ep_descriptor_definition: uint64_t = join_ep_descriptor_hi & 131071
                            join_ep_publish_word = red2_word_t(
                                lo=join_ep_ubv_index,
                                hi=112328704 | join_ep_descriptor_definition,
                            )
                            join_parent_head_ep_ubv: uint1_t = join_parent_word.hi[20]
                            join_ep_parent_var_hi: uint64_t = 71434240
                            if join_parent_head_ep_ubv:
                                join_ep_parent_var_hi = 112328704
                            if join_ep_general_root:
                                join_publish_word = red2_word_t(
                                    lo=join_result_address,
                                    hi=69337088,
                                )
                                join_preserve_fsp = 1
                            else:
                                join_publish_word = red2_word_t(
                                    lo=join_ep_ubv_index,
                                    hi=join_ep_parent_var_hi,
                                )
                            join_needs_ep_cache = 0
                            microstate = MICRO_JOIN_EP_RESULT_WRITE
                    elif join_ep_target_is_closure:
                        join_closure_kind_signed: uint1_t = join_ep_target_kind == DATA_SIGNED
                        join_closure_env_negative_at_dispatch: uint1_t = memory_out.p0.rd_data.lo[63]
                        if not join_closure_kind_signed:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif join_closure_env_negative_at_dispatch:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        else:
                            join_closure_address = join_ep_target17
                            join_closure_env = memory_out.p0.rd_data.lo
                            join_closure_lambda_count = 0
                            join_closure_write_index = 0
                            microstate = MICRO_JOIN_CLOSURE_CODE_READ
                    elif join_ep_target_is_rec:
                        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                        microstate = MICRO_FAULT
                    else:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
        elif micro_is_join_ep_result_write:
            if join_scalar_active and not join_scalar_preflight_done:
                join_ep_scalar_opcode: uint5_t = join_publish_word.hi[25:21]
                join_ep_scalar_kind: uint2_t = join_publish_word.hi[18:17]
                join_ep_scalar_is_int: uint1_t = join_ep_scalar_opcode == MOP_INT
                join_ep_scalar_is_float: uint1_t = join_ep_scalar_opcode == MOP_FLOAT
                join_ep_scalar_is_char: uint1_t = join_ep_scalar_opcode == MOP_CHAR
                join_ep_scalar_is_sym: uint1_t = join_ep_scalar_opcode == MOP_SYM
                join_ep_scalar_is_prim0: uint1_t = join_ep_scalar_opcode == MOP_PRIM_0
                join_ep_scalar_is_prim1: uint1_t = join_ep_scalar_opcode == MOP_PRIM_1
                join_ep_scalar_is_prim2: uint1_t = join_ep_scalar_opcode == MOP_PRIM_2
                join_ep_scalar_is_app: uint1_t = join_ep_scalar_opcode == MOP_APP
                join_ep_scalar_is_app_var: uint1_t = join_ep_scalar_opcode == MOP_APP_VAR
                join_ep_scalar_is_var: uint1_t = join_ep_scalar_opcode == MOP_VAR
                join_ep_scalar_is_signed: uint1_t = join_ep_scalar_kind == DATA_SIGNED
                join_ep_scalar_is_literal: uint1_t = join_ep_scalar_kind == DATA_LITERAL_ID
                join_ep_scalar_int_contract: uint1_t = join_ep_scalar_is_int and join_ep_scalar_is_signed
                join_ep_scalar_symbol_opcode: uint1_t = join_ep_scalar_is_sym or join_ep_scalar_is_prim0
                join_ep_scalar_symbol_opcode = join_ep_scalar_symbol_opcode or join_ep_scalar_is_prim1
                join_ep_scalar_symbol_opcode = join_ep_scalar_symbol_opcode or join_ep_scalar_is_prim2
                join_ep_scalar_symbol_value: uint1_t = join_ep_scalar_symbol_opcode and join_ep_scalar_is_literal
                join_ep_scalar_blocked_predicate: uint1_t = join_ep_scalar_is_app or join_ep_scalar_is_app_var
                join_ep_scalar_blocked_predicate = join_ep_scalar_blocked_predicate or join_ep_scalar_is_var

                join_ep_scalar_is_dec: uint1_t = join_prim_scalar_op == SCALAR_OP_DEC
                join_ep_scalar_is_inc: uint1_t = join_prim_scalar_op == SCALAR_OP_INC
                join_ep_scalar_is_negate: uint1_t = join_prim_scalar_op == SCALAR_OP_NEGATE
                join_ep_scalar_is_abs: uint1_t = join_prim_scalar_op == SCALAR_OP_ABS
                join_ep_scalar_is_floor: uint1_t = join_prim_scalar_op == SCALAR_OP_FLOOR
                join_ep_scalar_is_ceiling: uint1_t = join_prim_scalar_op == SCALAR_OP_CEILING
                join_ep_scalar_is_even: uint1_t = join_prim_scalar_op == SCALAR_OP_EVEN
                join_ep_scalar_is_null: uint1_t = join_prim_scalar_op == SCALAR_OP_NULL
                join_ep_scalar_is_not: uint1_t = join_prim_scalar_op == SCALAR_OP_NOT
                join_ep_scalar_is_integer_p: uint1_t = join_prim_scalar_op == SCALAR_OP_INTEGER_P
                join_ep_scalar_is_float_p: uint1_t = join_prim_scalar_op == SCALAR_OP_FLOAT_P
                join_ep_scalar_is_char_p: uint1_t = join_prim_scalar_op == SCALAR_OP_CHAR_P
                join_ep_scalar_is_symbol_p: uint1_t = join_prim_scalar_op == SCALAR_OP_SYMBOL_P
                join_ep_scalar_is_add: uint1_t = join_prim_scalar_op == SCALAR_OP_ADD
                join_ep_scalar_is_sub: uint1_t = join_prim_scalar_op == SCALAR_OP_SUB
                join_ep_scalar_is_mul: uint1_t = join_prim_scalar_op == SCALAR_OP_MUL
                join_ep_scalar_is_div: uint1_t = join_prim_scalar_op == SCALAR_OP_DIV
                join_ep_scalar_is_expt: uint1_t = join_prim_scalar_op == SCALAR_OP_EXPT
                join_ep_scalar_is_mod: uint1_t = join_prim_scalar_op == SCALAR_OP_MOD
                join_ep_scalar_is_lt: uint1_t = join_prim_scalar_op == SCALAR_OP_LT
                join_ep_scalar_is_gt: uint1_t = join_prim_scalar_op == SCALAR_OP_GT
                join_ep_scalar_is_le: uint1_t = join_prim_scalar_op == SCALAR_OP_LE
                join_ep_scalar_is_ge: uint1_t = join_prim_scalar_op == SCALAR_OP_GE
                join_ep_scalar_is_eq: uint1_t = join_prim_scalar_op == SCALAR_OP_EQ
                join_ep_scalar_is_max: uint1_t = join_prim_scalar_op == SCALAR_OP_MAX
                join_ep_scalar_is_min: uint1_t = join_prim_scalar_op == SCALAR_OP_MIN
                join_ep_scalar_binary_here: uint1_t = join_ep_scalar_is_add or join_ep_scalar_is_sub
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_mul
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_div
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_expt
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_mod
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_lt
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_gt
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_le
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_ge
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_eq
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_max
                join_ep_scalar_binary_here = join_ep_scalar_binary_here or join_ep_scalar_is_min

                join_ep_scalar_numeric: uint1_t = join_ep_scalar_is_dec or join_ep_scalar_is_inc
                join_ep_scalar_numeric = join_ep_scalar_numeric or join_ep_scalar_is_negate
                join_ep_scalar_numeric = join_ep_scalar_numeric or join_ep_scalar_is_abs
                join_ep_scalar_numeric = join_ep_scalar_numeric or join_ep_scalar_is_floor
                join_ep_scalar_numeric = join_ep_scalar_numeric or join_ep_scalar_is_ceiling
                join_ep_scalar_predicate: uint1_t = join_ep_scalar_is_integer_p or join_ep_scalar_is_float_p
                join_ep_scalar_predicate = join_ep_scalar_predicate or join_ep_scalar_is_char_p
                join_ep_scalar_predicate = join_ep_scalar_predicate or join_ep_scalar_is_symbol_p
                join_ep_scalar_supported: uint1_t = join_ep_scalar_numeric or join_ep_scalar_is_even
                join_ep_scalar_supported = join_ep_scalar_supported or join_ep_scalar_is_null
                join_ep_scalar_supported = join_ep_scalar_supported or join_ep_scalar_is_not
                join_ep_scalar_supported = join_ep_scalar_supported or join_ep_scalar_predicate
                join_ep_scalar_supported = join_ep_scalar_supported or join_ep_scalar_binary_here

                join_ep_scalar_int_min: uint1_t = join_publish_word.lo == 9223372036854775808
                join_ep_scalar_int_max: uint1_t = join_publish_word.lo == 9223372036854775807
                join_ep_scalar_negative: uint1_t = join_publish_word.lo[63]
                join_ep_scalar_min_overflow_op: uint1_t = join_ep_scalar_is_dec or join_ep_scalar_is_negate
                join_ep_scalar_min_overflow_op = join_ep_scalar_min_overflow_op or join_ep_scalar_is_abs
                join_ep_scalar_min_overflow: uint1_t = join_ep_scalar_int_min and join_ep_scalar_min_overflow_op
                join_ep_scalar_max_overflow: uint1_t = join_ep_scalar_int_max and join_ep_scalar_is_inc
                join_ep_scalar_overflow: uint1_t = join_ep_scalar_min_overflow or join_ep_scalar_max_overflow

                if join_ep_scalar_binary_here:
                    join_scalar_right_word = join_publish_word
                    join_scalar_return_ep = 1
                    microstate = MICRO_JOIN_SCALAR_LEFT_READ
                elif not join_ep_scalar_supported:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
                elif join_ep_scalar_numeric:
                    if join_ep_scalar_is_float:
                        red2_fault = FAULT_UNSUPPORTED_VALUE
                        microstate = MICRO_FAULT
                    elif join_ep_scalar_int_contract:
                        if join_ep_scalar_overflow:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_ep_scalar_result_payload: uint64_t = join_publish_word.lo
                            if join_ep_scalar_is_dec:
                                join_ep_scalar_result_payload = join_publish_word.lo - 1
                            elif join_ep_scalar_is_inc:
                                join_ep_scalar_result_payload = join_publish_word.lo + 1
                            elif join_ep_scalar_is_negate:
                                join_ep_scalar_result_payload = 0 - join_publish_word.lo
                            elif join_ep_scalar_is_abs and join_ep_scalar_negative:
                                join_ep_scalar_result_payload = 0 - join_publish_word.lo
                            join_publish_word = red2_word_t(lo=join_ep_scalar_result_payload, hi=85065728)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                elif join_ep_scalar_is_even:
                    if join_ep_scalar_is_float:
                        red2_fault = FAULT_UNSUPPORTED_VALUE
                        microstate = MICRO_FAULT
                    elif join_ep_scalar_int_contract:
                        join_ep_scalar_even: uint1_t = join_publish_word.lo[0] == 0
                        join_ep_scalar_bool_id: uint32_t = join_false_literal_id
                        if join_ep_scalar_even:
                            join_ep_scalar_bool_id = join_true_literal_id
                        if join_ep_scalar_bool_id == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_ep_scalar_bool_id, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                elif join_ep_scalar_is_null:
                    join_ep_scalar_null_contract: uint1_t = 0
                    join_ep_scalar_null_value: uint1_t = 0
                    if join_ep_scalar_symbol_value:
                        join_ep_scalar_null_contract = 1
                        join_ep_scalar_null_value = join_publish_word.lo == join_nil_literal_id
                    elif not join_ep_scalar_blocked_predicate:
                        join_ep_scalar_null_contract = 1
                    if join_ep_scalar_null_contract:
                        join_ep_scalar_bool_id_null: uint32_t = join_false_literal_id
                        if join_ep_scalar_null_value:
                            join_ep_scalar_bool_id_null = join_true_literal_id
                        if join_ep_scalar_bool_id_null == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_ep_scalar_bool_id_null, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                elif join_ep_scalar_is_not:
                    join_ep_scalar_true_id_present: uint1_t = join_true_literal_id != 0
                    join_ep_scalar_false_id_present: uint1_t = join_false_literal_id != 0
                    join_ep_scalar_not_true: uint1_t = join_ep_scalar_symbol_value and join_ep_scalar_true_id_present
                    join_ep_scalar_not_true = join_ep_scalar_not_true and join_publish_word.lo == join_true_literal_id
                    join_ep_scalar_not_false: uint1_t = join_ep_scalar_symbol_value and join_ep_scalar_false_id_present
                    join_ep_scalar_not_false = join_ep_scalar_not_false and join_publish_word.lo == join_false_literal_id
                    if join_ep_scalar_not_true or join_ep_scalar_not_false:
                        join_ep_scalar_bool_id_not: uint32_t = join_true_literal_id
                        if join_ep_scalar_not_true:
                            join_ep_scalar_bool_id_not = join_false_literal_id
                        if join_ep_scalar_bool_id_not == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_ep_scalar_bool_id_not, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                    else:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                else:
                    if join_ep_scalar_blocked_predicate:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                    else:
                        join_ep_scalar_predicate_value: uint1_t = 0
                        if join_ep_scalar_is_integer_p:
                            join_ep_scalar_predicate_value = join_ep_scalar_is_int
                        elif join_ep_scalar_is_float_p:
                            join_ep_scalar_predicate_value = join_ep_scalar_is_float
                        elif join_ep_scalar_is_char_p:
                            join_ep_scalar_predicate_value = join_ep_scalar_is_char
                        elif join_ep_scalar_is_symbol_p:
                            join_ep_scalar_predicate_value = join_ep_scalar_symbol_value
                        join_ep_scalar_bool_id_predicate: uint32_t = join_false_literal_id
                        if join_ep_scalar_predicate_value:
                            join_ep_scalar_bool_id_predicate = join_true_literal_id
                        if join_ep_scalar_bool_id_predicate == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_ep_scalar_bool_id_predicate, hi=91619328)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
            else:
                microstate = MICRO_JOIN_PUBLISH
        elif micro_is_join_scalar_left_read:
            if equality_continue_active:
                if equality_continue_phase == 0:
                    equality_continue_child_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                    equality_continue_child_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                    equality_continue_child_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                    equality_continue_child_head: uint1_t = memory_out.p0.rd_data.hi[20]
                    equality_continue_child_is_sym: uint1_t = equality_continue_child_opcode == MOP_SYM
                    equality_continue_child_is_literal: uint1_t = equality_continue_child_kind == DATA_LITERAL_ID
                    equality_continue_child_shape_ok: uint1_t = equality_continue_child_valid and equality_continue_child_is_sym
                    equality_continue_child_shape_ok = equality_continue_child_shape_ok and equality_continue_child_is_literal
                    equality_continue_child_shape_ok = equality_continue_child_shape_ok and equality_continue_child_head
                    equality_continue_child_payload: uint32_t = memory_out.p0.rd_data.lo[31:0]
                    equality_continue_child_true: uint1_t = join_true_literal_id != 0
                    equality_continue_child_true = equality_continue_child_true and equality_continue_child_payload == join_true_literal_id
                    equality_continue_child_false: uint1_t = join_false_literal_id != 0
                    equality_continue_child_false = equality_continue_child_false and equality_continue_child_payload == join_false_literal_id
                    equality_continue_child_stuck: uint1_t = join_equal_stuck_literal_id != 0
                    equality_continue_child_stuck = equality_continue_child_stuck and equality_continue_child_payload == join_equal_stuck_literal_id
                    equality_continue_child_known: uint1_t = equality_continue_child_true or equality_continue_child_false
                    equality_continue_child_known = equality_continue_child_known or equality_continue_child_stuck
                    equality_continue_frame_has_two_lower: uint1_t = join_frame_index != 0
                    equality_continue_frame_not_one: uint1_t = join_frame_index != 1
                    equality_continue_frame_has_two_lower = equality_continue_frame_has_two_lower and equality_continue_frame_not_one
                    if not equality_continue_child_shape_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    elif not equality_continue_child_known:
                        # Only TRUE/FALSE/__EQUAL_STUCK__ may cross this private boundary.
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    elif not equality_continue_frame_has_two_lower:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_continue_child_id = equality_continue_child_payload
                        equality_continue_phase = 1
                elif equality_continue_phase == 1:
                    equality_continue_eq_tag: uint4_t = control_out.p0.rd_data.tag_hi
                    equality_continue_eq_ok: uint1_t = equality_continue_eq_tag == CONTROL_EQUALITY
                    equality_continue_result_lane: uint32_t = control_out.p0.rd_data.lo[31:0]
                    equality_continue_live_lane: uint32_t = control_out.p0.rd_data.lo[63:32]
                    equality_continue_result_in_range: uint1_t = equality_continue_result_lane[31:GRAPH_ADDR_BITS] == 0
                    if not equality_continue_eq_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    elif not equality_continue_result_in_range:
                        # The software oracle currently crashes on this malformed
                        # frame; hardware keeps the ABI typed instead of truncating.
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_continue_result_pc = equality_continue_result_lane[15:0]
                        equality_continue_live_fsp = equality_continue_live_lane[15:0]
                        equality_continue_phase = 2
                elif equality_continue_phase == 2:
                    equality_continue_q_tag: uint4_t = control_out.p0.rd_data.tag_hi
                    equality_continue_q_ok: uint1_t = equality_continue_q_tag == CONTROL_SAVED_QUANTUM
                    if not equality_continue_q_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_continue_saved_q = control_out.p0.rd_data.lo[31:0]
                        equality_continue_phase = 3
                elif equality_continue_phase == 3:
                    equality_continue_phase3_stuck: uint1_t = equality_continue_child_id == join_equal_stuck_literal_id
                    if equality_continue_phase3_stuck:
                        equality_continue_phase = 5
                    else:
                        equality_continue_phase = 4
                elif equality_continue_phase == 4:
                    equality_continue_phase = 5
                elif equality_continue_phase == 5:
                    equality_continue_phase = 6
                elif equality_continue_phase == 6:
                    equality_continue_phase = 7
                elif equality_continue_phase == 7:
                    equality_continue_phase = 8
                elif equality_continue_phase == 8:
                    equality_continue_pc_nonzero: uint1_t = equality_continue_result_pc != 0
                    if not equality_continue_pc_nonzero:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_continue_finish_stuck: uint1_t = equality_continue_child_id == join_equal_stuck_literal_id
                        pc = equality_continue_result_pc - 1
                        if equality_continue_finish_stuck:
                            fsp = equality_continue_live_fsp
                        else:
                            fsp = equality_continue_result_pc
                        control_top = join_frame_index - 2
                        direction = DIRECTION_REVERSE
                        q = equality_continue_saved_q
                        argcnt = 2
                        prim_id = 0
                        fire = 0
                        s_a = join_result_address + 1
                        env = join_frame_env
                        free_space = join_frame_free_space
                        equality_continue_active = 0
                        equality_continue_phase = 0
                        microstate = MICRO_COMMIT
                else:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
            elif equality_child_active:
                equality_child_word_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                equality_child_word_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                equality_child_word_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                equality_child_word_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                if equality_child_phase == 0:
                    equality_child_left_field_ok: uint1_t = equality_child_word_valid
                    equality_child_left_field_ok = equality_child_left_field_ok and equality_child_word_opcode == MOP_INT
                    equality_child_left_field_ok = equality_child_left_field_ok and equality_child_word_kind == DATA_SIGNED
                    equality_child_left_field_ok = equality_child_left_field_ok and not equality_child_word_negative
                    if not equality_child_left_field_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_child_left = memory_out.p0.rd_data.lo
                        equality_child_phase = 1
                elif equality_child_phase == 1:
                    equality_child_right_field_ok: uint1_t = equality_child_word_valid
                    equality_child_right_field_ok = equality_child_right_field_ok and equality_child_word_opcode == MOP_INT
                    equality_child_right_field_ok = equality_child_right_field_ok and equality_child_word_kind == DATA_SIGNED
                    equality_child_right_field_ok = equality_child_right_field_ok and not equality_child_word_negative
                    if not equality_child_right_field_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_child_right = memory_out.p0.rd_data.lo
                        equality_child_phase = 2
                elif equality_child_phase == 2:
                    equality_child_lambda_field_ok: uint1_t = equality_child_word_valid
                    equality_child_lambda_field_ok = equality_child_lambda_field_ok and equality_child_word_opcode == MOP_INT
                    equality_child_lambda_field_ok = equality_child_lambda_field_ok and equality_child_word_kind == DATA_SIGNED
                    equality_child_lambda_field_ok = equality_child_lambda_field_ok and not equality_child_word_negative
                    if not equality_child_lambda_field_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_child_lambdas = memory_out.p0.rd_data.lo
                        equality_child_phase = 3
                elif equality_child_phase == 3:
                    equality_child_descriptor_field_ok: uint1_t = equality_child_word_valid
                    equality_child_descriptor_field_ok = equality_child_descriptor_field_ok and equality_child_word_opcode == MOP_INT
                    equality_child_descriptor_field_ok = equality_child_descriptor_field_ok and equality_child_word_kind == DATA_SIGNED
                    equality_child_descriptor_zero: uint1_t = memory_out.p0.rd_data.lo == 0
                    equality_child_descriptor_one: uint1_t = memory_out.p0.rd_data.lo == 1
                    equality_child_descriptor_ok: uint1_t = equality_child_descriptor_zero or equality_child_descriptor_one
                    equality_child_descriptor_field_ok = equality_child_descriptor_field_ok and equality_child_descriptor_ok
                    if not equality_child_descriptor_field_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_child_descriptor = equality_child_descriptor_one
                        equality_child_phase = 4
                elif equality_child_phase == 4:
                    equality_child_join_ok: uint1_t = equality_child_word_valid
                    equality_child_join_ok = equality_child_join_ok and equality_child_word_opcode == MOP_JOIN
                    if not equality_child_join_ok:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_child_build_join_word = memory_out.p0.rd_data
                        equality_child_phase = 5
                elif equality_child_phase == 5:
                    equality_child_left_addr_ok: uint1_t = equality_child_left[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_left_addr_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif equality_child_descriptor and equality_child_word_opcode == MOP_APP:
                        equality_child_left_app_signed: uint1_t = equality_child_word_kind == DATA_SIGNED
                        equality_child_left_target_ok: uint1_t = memory_out.p0.rd_data.lo[63:GRAPH_ADDR_BITS] == 0
                        if not equality_child_left_app_signed or equality_child_word_negative:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not equality_child_left_target_ok:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        else:
                            equality_child_left = memory_out.p0.rd_data.lo
                            equality_child_phase = 6
                    elif equality_child_descriptor and equality_child_word_opcode == MOP_APP_VAR:
                        equality_child_left_app_var_signed: uint1_t = equality_child_word_kind == DATA_SIGNED
                        if not equality_child_left_app_var_signed or equality_child_word_negative:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        else:
                            equality_child_left_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=112328704)
                            equality_child_phase = 7
                    else:
                        equality_child_left_word = memory_out.p0.rd_data
                        equality_child_phase = 7
                elif equality_child_phase == 6:
                    equality_child_left_target_addr_ok: uint1_t = equality_child_left[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_left_target_addr_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_left_word = memory_out.p0.rd_data
                        equality_child_phase = 7
                elif equality_child_phase == 7:
                    equality_child_right_addr_ok: uint1_t = equality_child_right[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_right_addr_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif equality_child_descriptor and equality_child_word_opcode == MOP_APP:
                        equality_child_right_app_signed: uint1_t = equality_child_word_kind == DATA_SIGNED
                        equality_child_right_target_ok: uint1_t = memory_out.p0.rd_data.lo[63:GRAPH_ADDR_BITS] == 0
                        if not equality_child_right_app_signed or equality_child_word_negative:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not equality_child_right_target_ok:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        else:
                            equality_child_right = memory_out.p0.rd_data.lo
                            equality_child_phase = 8
                    elif equality_child_descriptor and equality_child_word_opcode == MOP_APP_VAR:
                        equality_child_right_app_var_signed: uint1_t = equality_child_word_kind == DATA_SIGNED
                        if not equality_child_right_app_var_signed or equality_child_word_negative:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        else:
                            equality_child_right_word = red2_word_t(lo=memory_out.p0.rd_data.lo, hi=112328704)
                            equality_child_phase = 9
                    else:
                        equality_child_right_word = memory_out.p0.rd_data
                        equality_child_phase = 9
                elif equality_child_phase == 8:
                    equality_child_right_target_addr_ok: uint1_t = equality_child_right[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_right_target_addr_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_right_word = memory_out.p0.rd_data
                        equality_child_phase = 9
                elif equality_child_phase == 9:
                    eqc_left_opcode: uint5_t = equality_child_left_word.hi[25:21]
                    eqc_right_opcode: uint5_t = equality_child_right_word.hi[25:21]
                    eqc_left_kind: uint2_t = equality_child_left_word.hi[18:17]
                    eqc_right_kind: uint2_t = equality_child_right_word.hi[18:17]
                    eqc_left_int: uint1_t = eqc_left_opcode == MOP_INT
                    eqc_left_int = eqc_left_int and eqc_left_kind == DATA_SIGNED
                    eqc_right_int: uint1_t = eqc_right_opcode == MOP_INT
                    eqc_right_int = eqc_right_int and eqc_right_kind == DATA_SIGNED
                    eqc_left_float: uint1_t = eqc_left_opcode == MOP_FLOAT
                    eqc_left_float = eqc_left_float and eqc_left_kind == DATA_FLOAT64
                    eqc_right_float: uint1_t = eqc_right_opcode == MOP_FLOAT
                    eqc_right_float = eqc_right_float and eqc_right_kind == DATA_FLOAT64
                    eqc_left_char: uint1_t = eqc_left_opcode == MOP_CHAR
                    eqc_left_char = eqc_left_char and eqc_left_kind == DATA_LITERAL_ID
                    eqc_right_char: uint1_t = eqc_right_opcode == MOP_CHAR
                    eqc_right_char = eqc_right_char and eqc_right_kind == DATA_LITERAL_ID
                    eqc_left_sym_opcode: uint1_t = eqc_left_opcode == MOP_SYM
                    eqc_left_sym_opcode = eqc_left_sym_opcode or eqc_left_opcode == MOP_PRIM_0
                    eqc_left_sym_opcode = eqc_left_sym_opcode or eqc_left_opcode == MOP_PRIM_1
                    eqc_left_sym_opcode = eqc_left_sym_opcode or eqc_left_opcode == MOP_PRIM_2
                    eqc_right_sym_opcode: uint1_t = eqc_right_opcode == MOP_SYM
                    eqc_right_sym_opcode = eqc_right_sym_opcode or eqc_right_opcode == MOP_PRIM_0
                    eqc_right_sym_opcode = eqc_right_sym_opcode or eqc_right_opcode == MOP_PRIM_1
                    eqc_right_sym_opcode = eqc_right_sym_opcode or eqc_right_opcode == MOP_PRIM_2
                    eqc_left_symbol: uint1_t = eqc_left_sym_opcode and eqc_left_kind == DATA_LITERAL_ID
                    eqc_right_symbol: uint1_t = eqc_right_sym_opcode and eqc_right_kind == DATA_LITERAL_ID
                    eqc_left_constant: uint1_t = eqc_left_int or eqc_left_float
                    eqc_left_constant = eqc_left_constant or eqc_left_char
                    eqc_left_constant = eqc_left_constant or eqc_left_symbol
                    eqc_right_constant: uint1_t = eqc_right_int or eqc_right_float
                    eqc_right_constant = eqc_right_constant or eqc_right_char
                    eqc_right_constant = eqc_right_constant or eqc_right_symbol
                    eqc_any_constant: uint1_t = eqc_left_constant or eqc_right_constant
                    eqc_left_ubv: uint1_t = eqc_left_opcode == MOP_UBV
                    eqc_right_ubv: uint1_t = eqc_right_opcode == MOP_UBV
                    eqc_any_ubv: uint1_t = eqc_left_ubv or eqc_right_ubv
                    eqc_left_var: uint1_t = eqc_left_opcode == MOP_VAR
                    eqc_right_var: uint1_t = eqc_right_opcode == MOP_VAR
                    eqc_any_var: uint1_t = eqc_left_var or eqc_right_var
                    eqc_left_closure: uint1_t = eqc_left_opcode == MOP_CLOSURE
                    eqc_right_closure: uint1_t = eqc_right_opcode == MOP_CLOSURE
                    eqc_any_closure: uint1_t = eqc_left_closure or eqc_right_closure
                    eqc_left_struct: uint1_t = eqc_left_opcode == MOP_STRUCT
                    eqc_left_struct = eqc_left_struct and eqc_left_kind == DATA_LITERAL_ID
                    eqc_right_struct: uint1_t = eqc_right_opcode == MOP_STRUCT
                    eqc_right_struct = eqc_right_struct and eqc_right_kind == DATA_LITERAL_ID
                    eqc_any_struct: uint1_t = eqc_left_struct or eqc_right_struct
                    eqc_left_lambda: uint1_t = eqc_left_opcode == MOP_LAMBDA
                    eqc_right_lambda: uint1_t = eqc_right_opcode == MOP_LAMBDA
                    eqc_any_lambda: uint1_t = eqc_left_lambda or eqc_right_lambda
                    eqc_left_inline_opcode: uint1_t = eqc_left_opcode == MOP_INT
                    eqc_left_inline_opcode = eqc_left_inline_opcode or eqc_left_opcode == MOP_FLOAT
                    eqc_left_inline_opcode = eqc_left_inline_opcode or eqc_left_opcode == MOP_CHAR
                    eqc_left_inline_opcode = eqc_left_inline_opcode or eqc_left_opcode == MOP_SYM
                    eqc_left_inline_opcode = eqc_left_inline_opcode or eqc_left_opcode == MOP_PRIM_0
                    eqc_left_inline_opcode = eqc_left_inline_opcode or eqc_left_opcode == MOP_PRIM_1
                    eqc_left_inline_opcode = eqc_left_inline_opcode or eqc_left_opcode == MOP_PRIM_2
                    eqc_right_inline_opcode: uint1_t = eqc_right_opcode == MOP_INT
                    eqc_right_inline_opcode = eqc_right_inline_opcode or eqc_right_opcode == MOP_FLOAT
                    eqc_right_inline_opcode = eqc_right_inline_opcode or eqc_right_opcode == MOP_CHAR
                    eqc_right_inline_opcode = eqc_right_inline_opcode or eqc_right_opcode == MOP_SYM
                    eqc_right_inline_opcode = eqc_right_inline_opcode or eqc_right_opcode == MOP_PRIM_0
                    eqc_right_inline_opcode = eqc_right_inline_opcode or eqc_right_opcode == MOP_PRIM_1
                    eqc_right_inline_opcode = eqc_right_inline_opcode or eqc_right_opcode == MOP_PRIM_2
                    eqc_left_nonhead_inline: uint1_t = not equality_child_left_word.hi[20]
                    eqc_left_nonhead_inline = eqc_left_nonhead_inline and eqc_left_inline_opcode
                    eqc_right_nonhead_inline: uint1_t = not equality_child_right_word.hi[20]
                    eqc_right_nonhead_inline = eqc_right_nonhead_inline and eqc_right_inline_opcode
                    eqc_left_app_prefix: uint1_t = eqc_left_opcode == MOP_APP
                    eqc_left_app_prefix = eqc_left_app_prefix or eqc_left_opcode == MOP_APP_VAR
                    eqc_left_app_prefix = eqc_left_app_prefix or eqc_left_nonhead_inline
                    eqc_right_app_prefix: uint1_t = eqc_right_opcode == MOP_APP
                    eqc_right_app_prefix = eqc_right_app_prefix or eqc_right_opcode == MOP_APP_VAR
                    eqc_right_app_prefix = eqc_right_app_prefix or eqc_right_nonhead_inline
                    eqc_any_app_prefix: uint1_t = eqc_left_app_prefix or eqc_right_app_prefix
                    eqc_left_ep: uint1_t = eqc_left_opcode == MOP_EP
                    eqc_right_ep: uint1_t = eqc_right_opcode == MOP_EP
                    eqc_any_ep: uint1_t = eqc_left_ep or eqc_right_ep

                    eqc_result_id: uint32_t = 0
                    eqc_result_ready: uint1_t = 0
                    eqc_result_unsupported: uint1_t = 0
                    if eqc_any_ubv:
                        eqc_both_ubv: uint1_t = eqc_left_ubv and eqc_right_ubv
                        eqc_left_ubv_signed: uint1_t = eqc_left_kind == DATA_SIGNED
                        eqc_right_ubv_signed: uint1_t = eqc_right_kind == DATA_SIGNED
                        eqc_ubv_both_signed: uint1_t = eqc_left_ubv_signed and eqc_right_ubv_signed
                        eqc_ubv_both_nonsigned: uint1_t = not eqc_left_ubv_signed and not eqc_right_ubv_signed
                        eqc_ubv_signed_equal: uint1_t = equality_child_left_word.lo == equality_child_right_word.lo
                        eqc_ubv_equal: uint1_t = eqc_both_ubv and eqc_ubv_both_nonsigned
                        eqc_ubv_signed_equal = eqc_ubv_signed_equal and eqc_ubv_both_signed
                        eqc_ubv_equal = eqc_ubv_equal or (eqc_both_ubv and eqc_ubv_signed_equal)
                        if eqc_ubv_equal:
                            eqc_result_id = join_true_literal_id
                        else:
                            eqc_result_id = join_equal_stuck_literal_id
                        eqc_result_ready = 1
                    elif eqc_any_constant:
                        eqc_equal: uint1_t = 0
                        eqc_same_int: uint1_t = eqc_left_int and eqc_right_int
                        eqc_same_float: uint1_t = eqc_left_float and eqc_right_float
                        eqc_same_char: uint1_t = eqc_left_char and eqc_right_char
                        eqc_same_symbol: uint1_t = eqc_left_symbol and eqc_right_symbol
                        if eqc_same_float:
                            eqc_left_exp: uint16_t = equality_child_left_word.lo[62:52]
                            eqc_right_exp: uint16_t = equality_child_right_word.lo[62:52]
                            eqc_left_mantissa: uint64_t = equality_child_left_word.lo & 4503599627370495
                            eqc_right_mantissa: uint64_t = equality_child_right_word.lo & 4503599627370495
                            eqc_left_exp_nan: uint1_t = eqc_left_exp == 2047
                            eqc_left_mantissa_nonzero: uint1_t = eqc_left_mantissa != 0
                            eqc_left_nan: uint1_t = eqc_left_exp_nan and eqc_left_mantissa_nonzero
                            eqc_right_exp_nan: uint1_t = eqc_right_exp == 2047
                            eqc_right_mantissa_nonzero: uint1_t = eqc_right_mantissa != 0
                            eqc_right_nan: uint1_t = eqc_right_exp_nan and eqc_right_mantissa_nonzero
                            eqc_any_nan: uint1_t = eqc_left_nan or eqc_right_nan
                            eqc_left_zero: uint1_t = (equality_child_left_word.lo & 9223372036854775807) == 0
                            eqc_right_zero: uint1_t = (equality_child_right_word.lo & 9223372036854775807) == 0
                            eqc_both_zero: uint1_t = eqc_left_zero and eqc_right_zero
                            if not eqc_any_nan:
                                eqc_equal = eqc_both_zero or equality_child_left_word.lo == equality_child_right_word.lo
                        elif eqc_same_int or eqc_same_char or eqc_same_symbol:
                            eqc_equal = equality_child_left_word.lo == equality_child_right_word.lo
                        eqc_result_id = join_false_literal_id
                        if eqc_equal:
                            eqc_result_id = join_true_literal_id
                        eqc_result_ready = 1
                    elif eqc_any_var:
                        eqc_variable_kind: uint2_t = eqc_left_kind
                        eqc_variable_negative: uint1_t = equality_child_left_word.lo[63]
                        if not eqc_left_var:
                            eqc_variable_kind = eqc_right_kind
                            eqc_variable_negative = equality_child_right_word.lo[63]
                        eqc_variable_signed: uint1_t = eqc_variable_kind == DATA_SIGNED
                        if not eqc_variable_signed or eqc_variable_negative:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif eqc_left_var and eqc_right_var:
                            eqc_left_var_signed: uint1_t = eqc_left_kind == DATA_SIGNED
                            eqc_right_var_signed: uint1_t = eqc_right_kind == DATA_SIGNED
                            eqc_left_var_negative: uint1_t = equality_child_left_word.lo[63]
                            eqc_right_var_negative: uint1_t = equality_child_right_word.lo[63]
                            eqc_var_kinds_ok: uint1_t = eqc_left_var_signed and eqc_right_var_signed
                            eqc_var_signs_ok: uint1_t = not eqc_left_var_negative and not eqc_right_var_negative
                            if not eqc_var_kinds_ok or not eqc_var_signs_ok:
                                red2_fault = FAULT_INVALID_ADDRESS
                                microstate = MICRO_FAULT
                            else:
                                eqc_var_same: uint1_t = equality_child_left_word.lo == equality_child_right_word.lo
                                eqc_left_var_ge_lambdas: uint1_t = red2_u64_ge(equality_child_left_word.lo, equality_child_lambdas)
                                eqc_right_var_ge_lambdas: uint1_t = red2_u64_ge(equality_child_right_word.lo, equality_child_lambdas)
                                eqc_left_var_bound: uint1_t = not eqc_left_var_ge_lambdas
                                eqc_right_var_bound: uint1_t = not eqc_right_var_ge_lambdas
                                if eqc_var_same:
                                    eqc_result_id = join_true_literal_id
                                elif eqc_left_var_bound or eqc_right_var_bound:
                                    eqc_result_id = join_false_literal_id
                                else:
                                    eqc_result_id = join_equal_stuck_literal_id
                                eqc_result_ready = 1
                        else:
                            eqc_variable_index: uint64_t = equality_child_left_word.lo
                            if not eqc_left_var:
                                eqc_variable_index = equality_child_right_word.lo
                            eqc_variable_ge_lambdas: uint1_t = red2_u64_ge(eqc_variable_index, equality_child_lambdas)
                            eqc_variable_bound: uint1_t = not eqc_variable_ge_lambdas
                            if eqc_variable_bound:
                                eqc_result_id = join_false_literal_id
                            else:
                                eqc_result_id = join_equal_stuck_literal_id
                            eqc_result_ready = 1
                    elif eqc_any_closure:
                        if not eqc_left_closure or not eqc_right_closure:
                            eqc_result_id = join_false_literal_id
                            eqc_result_ready = 1
                        else:
                            eqc_left_code_addr17: uint17_t = equality_child_left + 1
                            eqc_right_code_addr17: uint17_t = equality_child_right + 1
                            eqc_left_code_addr_ok: uint1_t = eqc_left_code_addr17[16:GRAPH_ADDR_BITS] == 0
                            eqc_right_code_addr_ok: uint1_t = eqc_right_code_addr17[16:GRAPH_ADDR_BITS] == 0
                            if not eqc_left_code_addr_ok or not eqc_right_code_addr_ok:
                                red2_fault = FAULT_INVALID_ADDRESS
                                microstate = MICRO_FAULT
                            else:
                                equality_child_phase = 11
                    elif eqc_any_struct:
                        if not eqc_left_struct or not eqc_right_struct:
                            eqc_result_id = join_false_literal_id
                            eqc_result_ready = 1
                        elif equality_child_left_word.lo != equality_child_right_word.lo:
                            eqc_result_id = join_false_literal_id
                            eqc_result_ready = 1
                        else:
                            equality_child_struct_left_base = equality_child_left + 1
                            equality_child_struct_right_base = equality_child_right + 1
                            equality_child_struct_left_count = 0
                            equality_child_struct_right_count = 0
                            equality_child_phase = 27
                    elif eqc_any_lambda:
                        if not eqc_left_lambda or not eqc_right_lambda:
                            eqc_result_id = join_false_literal_id
                            eqc_result_ready = 1
                        else:
                            equality_child_left = equality_child_left + 1
                            equality_child_right = equality_child_right + 1
                            equality_child_lambdas = equality_child_lambdas + 1
                            equality_child_phase = 13
                    elif eqc_any_app_prefix:
                        if not eqc_left_app_prefix or not eqc_right_app_prefix:
                            eqc_result_id = join_false_literal_id
                            eqc_result_ready = 1
                        else:
                            equality_child_struct_left_base = equality_child_left
                            equality_child_struct_right_base = equality_child_right
                            equality_child_struct_left_count = 0
                            equality_child_struct_right_count = 0
                            equality_child_phase = 30
                    elif eqc_any_ep:
                        eqc_both_ep: uint1_t = eqc_left_ep and eqc_right_ep
                        eqc_left_ep_signed: uint1_t = eqc_left_kind == DATA_SIGNED
                        eqc_right_ep_signed: uint1_t = eqc_right_kind == DATA_SIGNED
                        eqc_ep_both_signed: uint1_t = eqc_left_ep_signed and eqc_right_ep_signed
                        eqc_ep_both_nonsigned: uint1_t = not eqc_left_ep_signed and not eqc_right_ep_signed
                        eqc_ep_signed_equal: uint1_t = equality_child_left_word.lo == equality_child_right_word.lo
                        eqc_ep_equal: uint1_t = eqc_both_ep and eqc_ep_both_nonsigned
                        eqc_ep_signed_equal = eqc_ep_signed_equal and eqc_ep_both_signed
                        eqc_ep_equal = eqc_ep_equal or (eqc_both_ep and eqc_ep_signed_equal)
                        if eqc_ep_equal:
                            eqc_result_id = join_true_literal_id
                        else:
                            eqc_result_id = join_equal_stuck_literal_id
                        eqc_result_ready = 1
                    elif eqc_left_opcode != eqc_right_opcode:
                        eqc_result_id = join_false_literal_id
                        eqc_result_ready = 1
                    else:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT

                    if eqc_result_unsupported:
                        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                        microstate = MICRO_FAULT
                    elif eqc_result_ready:
                        eqc_destination17: uint17_t = equality_child_join_address + 1
                        eqc_destination_in_range: uint1_t = eqc_destination17[16:GRAPH_ADDR_BITS] == 0
                        eqc_gap: uint17_t = free_space - eqc_destination17
                        eqc_gap_wrapped: uint1_t = eqc_gap[16]
                        eqc_gap_nonzero: uint1_t = eqc_gap != 0
                        eqc_space_ok: uint1_t = eqc_gap_wrapped == 0
                        eqc_space_ok = eqc_space_ok and eqc_gap_nonzero
                        if eqc_result_id == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        elif not eqc_destination_in_range:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not eqc_space_ok:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=eqc_result_id, hi=91619328)
                            equality_child_phase = 10
                elif equality_child_phase == 10:
                    equality_child_final_fsp17: uint17_t = equality_child_join_address + 1
                    fsp = equality_child_final_fsp17[15:0]
                    argcnt = 2
                    pc = equality_child_join_address
                    direction = DIRECTION_REVERSE
                    equality_child_active = 0
                    equality_child_phase = 0
                    microstate = MICRO_COMMIT
                elif equality_child_phase == 11:
                    equality_child_left_code_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                    equality_child_left_code_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                    equality_child_left_code_is_none: uint1_t = equality_child_left_code_opcode == MOP_NONE
                    equality_child_left_code_bad: uint1_t = equality_child_left_code_valid == 0
                    equality_child_left_code_bad = equality_child_left_code_bad or equality_child_left_code_is_none == 0
                    if equality_child_left_code_bad:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_child_left_code_word = memory_out.p0.rd_data
                        equality_child_phase = 12
                elif equality_child_phase == 12:
                    equality_child_right_code_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                    equality_child_right_code_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                    equality_child_right_code_is_none: uint1_t = equality_child_right_code_opcode == MOP_NONE
                    equality_child_right_code_bad: uint1_t = equality_child_right_code_valid == 0
                    equality_child_right_code_bad = equality_child_right_code_bad or equality_child_right_code_is_none == 0
                    if equality_child_right_code_bad:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        equality_child_left_closure_signed: uint1_t = equality_child_left_word.hi[18:17] == DATA_SIGNED
                        equality_child_right_closure_signed: uint1_t = equality_child_right_word.hi[18:17] == DATA_SIGNED
                        equality_child_closure_both_signed: uint1_t = equality_child_left_closure_signed and equality_child_right_closure_signed
                        equality_child_closure_both_none: uint1_t = not equality_child_left_closure_signed and not equality_child_right_closure_signed
                        equality_child_closure_payload_equal: uint1_t = equality_child_left_word.lo == equality_child_right_word.lo
                        equality_child_closure_signed_equal: uint1_t = equality_child_closure_both_signed and equality_child_closure_payload_equal
                        equality_child_closure_equal: uint1_t = equality_child_closure_both_none or equality_child_closure_signed_equal

                        equality_child_left_code_signed: uint1_t = equality_child_left_code_word.hi[18:17] == DATA_SIGNED
                        equality_child_right_code_signed: uint1_t = memory_out.p0.rd_data.hi[18:17] == DATA_SIGNED
                        equality_child_code_both_signed: uint1_t = equality_child_left_code_signed and equality_child_right_code_signed
                        equality_child_code_both_none: uint1_t = not equality_child_left_code_signed and not equality_child_right_code_signed
                        equality_child_code_payload_equal: uint1_t = equality_child_left_code_word.lo == memory_out.p0.rd_data.lo
                        equality_child_code_signed_equal: uint1_t = equality_child_code_both_signed and equality_child_code_payload_equal
                        equality_child_code_equal: uint1_t = equality_child_code_both_none or equality_child_code_signed_equal
                        equality_child_closure_and_code_equal: uint1_t = equality_child_closure_equal and equality_child_code_equal
                        equality_child_closure_result_id: uint32_t = join_false_literal_id
                        if equality_child_closure_and_code_equal:
                            equality_child_closure_result_id = join_true_literal_id
                        equality_child_closure_destination17: uint17_t = equality_child_join_address + 1
                        equality_child_closure_destination_ok: uint1_t = equality_child_closure_destination17[16:GRAPH_ADDR_BITS] == 0
                        equality_child_closure_gap: uint17_t = free_space - equality_child_closure_destination17
                        equality_child_closure_gap_wrapped: uint1_t = equality_child_closure_gap[16]
                        equality_child_closure_gap_nonzero: uint1_t = equality_child_closure_gap != 0
                        equality_child_closure_space_ok: uint1_t = equality_child_closure_gap_wrapped == 0
                        equality_child_closure_space_ok = equality_child_closure_space_ok and equality_child_closure_gap_nonzero
                        if equality_child_closure_result_id == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        elif not equality_child_closure_destination_ok:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not equality_child_closure_space_ok:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=equality_child_closure_result_id, hi=91619328)
                            equality_child_phase = 10
                elif equality_child_phase == 13:
                    equality_child_lambda_left_addr_ok: uint1_t = equality_child_left[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_lambda_left_addr_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_left_word = memory_out.p0.rd_data
                        equality_child_phase = 14
                elif equality_child_phase == 14:
                    equality_child_lambda_right_addr_ok: uint1_t = equality_child_right[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_lambda_right_addr_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_right_word = memory_out.p0.rd_data
                        equality_child_lambda_left_opcode: uint5_t = equality_child_left_word.hi[25:21]
                        equality_child_lambda_right_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                        equality_child_lambda_left_is_lambda: uint1_t = equality_child_lambda_left_opcode == MOP_LAMBDA
                        equality_child_lambda_right_is_lambda: uint1_t = equality_child_lambda_right_opcode == MOP_LAMBDA
                        equality_child_lambda_both: uint1_t = equality_child_lambda_left_is_lambda and equality_child_lambda_right_is_lambda
                        equality_child_lambda_either: uint1_t = equality_child_lambda_left_is_lambda or equality_child_lambda_right_is_lambda
                        if equality_child_lambda_both:
                            equality_child_left = equality_child_left + 1
                            equality_child_right = equality_child_right + 1
                            equality_child_lambdas = equality_child_lambdas + 1
                            equality_child_phase = 13
                        elif equality_child_lambda_either:
                            equality_child_lambda_false_destination17: uint17_t = equality_child_join_address + 1
                            equality_child_lambda_false_destination_ok: uint1_t = equality_child_lambda_false_destination17[16:GRAPH_ADDR_BITS] == 0
                            equality_child_lambda_false_gap: uint17_t = free_space - equality_child_lambda_false_destination17
                            equality_child_lambda_false_gap_wrapped: uint1_t = equality_child_lambda_false_gap[16]
                            equality_child_lambda_false_gap_nonzero: uint1_t = equality_child_lambda_false_gap != 0
                            equality_child_lambda_false_space_ok: uint1_t = equality_child_lambda_false_gap_wrapped == 0
                            equality_child_lambda_false_space_ok = equality_child_lambda_false_space_ok and equality_child_lambda_false_gap_nonzero
                            if join_false_literal_id == 0:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            elif not equality_child_lambda_false_destination_ok:
                                red2_fault = FAULT_INVALID_ADDRESS
                                microstate = MICRO_FAULT
                            elif not equality_child_lambda_false_space_ok:
                                red2_fault = FAULT_GRAPH_ENV_COLLISION
                                microstate = MICRO_FAULT
                            else:
                                join_publish_word = red2_word_t(lo=join_false_literal_id, hi=91619328)
                                equality_child_phase = 10
                        else:
                            equality_child_lambda_final17: uint17_t = equality_child_join_address + 11
                            equality_child_lambda_final_in_range: uint1_t = equality_child_lambda_final17[16:GRAPH_ADDR_BITS] == 0
                            equality_child_lambda_gap: uint17_t = free_space - equality_child_lambda_final17
                            equality_child_lambda_gap_wrapped: uint1_t = equality_child_lambda_gap[16]
                            equality_child_lambda_gap_nonzero: uint1_t = equality_child_lambda_gap != 0
                            equality_child_lambda_space_ok: uint1_t = equality_child_lambda_gap_wrapped == 0
                            equality_child_lambda_space_ok = equality_child_lambda_space_ok and equality_child_lambda_gap_nonzero
                            equality_child_lambda_has_star: uint1_t = join_equal_star_literal_id != 0
                            equality_child_lambda_has_true: uint1_t = join_true_literal_id != 0
                            equality_child_lambda_has_false: uint1_t = join_false_literal_id != 0
                            equality_child_lambda_has_if: uint1_t = join_equal_if_literal_id != 0
                            equality_child_lambda_meta_ok: uint1_t = equality_child_lambda_has_star and equality_child_lambda_has_true
                            equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and equality_child_lambda_has_false
                            equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and equality_child_lambda_has_if
                            if not equality_child_lambda_meta_ok:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            elif not equality_child_lambda_final_in_range:
                                red2_fault = FAULT_INVALID_ADDRESS
                                microstate = MICRO_FAULT
                            elif not equality_child_lambda_space_ok:
                                red2_fault = FAULT_GRAPH_ENV_COLLISION
                                microstate = MICRO_FAULT
                            else:
                                equality_child_build_descriptor = 0
                                equality_child_build_app_mode = 0
                                equality_child_build_count = 1
                                equality_child_build_index = 0
                                equality_child_build_cursor = equality_child_join_address
                                equality_child_build_root = 0
                                equality_child_build_false_root = 0
                                equality_child_build_if_child_root = 0
                                equality_child_phase = 15
                elif equality_child_phase == 15:
                    equality_child_phase = 16
                elif equality_child_phase == 16:
                    equality_child_phase = 17
                elif equality_child_phase == 17:
                    equality_child_phase = 18
                elif equality_child_phase == 18:
                    equality_child_phase = 19
                elif equality_child_phase == 19:
                    equality_child_build_next_index: uint16_t = equality_child_build_index + 1
                    equality_child_build_more: uint1_t = equality_child_build_next_index != equality_child_build_count
                    if equality_child_build_more:
                        equality_child_build_index = equality_child_build_next_index
                        equality_child_build_cursor = equality_child_build_cursor + 5
                        if equality_child_build_app_mode:
                            equality_child_build_descriptor = 1
                            equality_child_app_index64: uint64_t = equality_child_build_next_index
                            equality_child_app_source_offset: uint64_t = equality_child_struct_left_count - equality_child_app_index64
                            equality_child_left = equality_child_struct_left_base + equality_child_app_source_offset
                            equality_child_right = equality_child_struct_right_base + equality_child_app_source_offset
                        else:
                            equality_child_left = equality_child_left - 1
                            equality_child_right = equality_child_right - 1
                        equality_child_phase = 15
                    else:
                        equality_child_build_if_child_root = equality_child_build_cursor
                        equality_child_build_cursor = equality_child_build_cursor + 5
                        equality_child_phase = 20
                elif equality_child_phase == 20:
                    equality_child_phase = 21
                elif equality_child_phase == 21:
                    equality_child_build_root = equality_child_build_cursor[15:0]
                    equality_child_build_false_root17: uint17_t = equality_child_build_cursor + 1
                    equality_child_build_false_root = equality_child_build_false_root17[15:0]
                    equality_child_build_index = equality_child_build_count
                    equality_child_build_cursor = equality_child_build_cursor + 2
                    equality_child_phase = 22
                elif equality_child_phase == 22:
                    equality_child_phase = 23
                elif equality_child_phase == 23:
                    equality_child_phase = 24
                elif equality_child_phase == 24:
                    equality_child_phase = 25
                elif equality_child_phase == 25:
                    equality_child_build_root = equality_child_build_cursor[15:0]
                    equality_child_build_cursor = equality_child_build_cursor + 4
                    if equality_child_build_index == 1:
                        equality_child_phase = 26
                    else:
                        equality_child_build_index = equality_child_build_index - 1
                        equality_child_build_if_child_root = equality_child_build_if_child_root - 5
                        equality_child_phase = 22
                elif equality_child_phase == 26:
                    pc = equality_child_build_root
                    fsp = equality_child_build_cursor[15:0]
                    argcnt = 1
                    direction = DIRECTION_FORWARD
                    prim_id = 0
                    fire = 0
                    equality_child_active = 0
                    equality_child_phase = 0
                    microstate = MICRO_COMMIT
                elif equality_child_phase == 27:
                    equality_child_struct_left_cursor: uint64_t = equality_child_struct_left_base + equality_child_struct_left_count
                    equality_child_struct_left_cursor_ok: uint1_t = equality_child_struct_left_cursor[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_struct_left_cursor_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_struct_left_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                        equality_child_struct_left_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                        equality_child_struct_left_head: uint1_t = memory_out.p0.rd_data.hi[20]
                        equality_child_struct_left_inline: uint1_t = equality_child_struct_left_opcode == MOP_INT
                        equality_child_struct_left_inline = equality_child_struct_left_inline or equality_child_struct_left_opcode == MOP_FLOAT
                        equality_child_struct_left_inline = equality_child_struct_left_inline or equality_child_struct_left_opcode == MOP_CHAR
                        equality_child_struct_left_inline = equality_child_struct_left_inline or equality_child_struct_left_opcode == MOP_SYM
                        equality_child_struct_left_inline = equality_child_struct_left_inline or equality_child_struct_left_opcode == MOP_PRIM_0
                        equality_child_struct_left_inline = equality_child_struct_left_inline or equality_child_struct_left_opcode == MOP_PRIM_1
                        equality_child_struct_left_inline = equality_child_struct_left_inline or equality_child_struct_left_opcode == MOP_PRIM_2
                        equality_child_struct_left_item: uint1_t = equality_child_struct_left_opcode == MOP_APP
                        equality_child_struct_left_item = equality_child_struct_left_item or equality_child_struct_left_opcode == MOP_APP_VAR
                        equality_child_struct_left_item = equality_child_struct_left_item or equality_child_struct_left_opcode == MOP_EP
                        equality_child_struct_left_nonhead_inline: uint1_t = not equality_child_struct_left_head
                        equality_child_struct_left_nonhead_inline = equality_child_struct_left_nonhead_inline and equality_child_struct_left_inline
                        equality_child_struct_left_item = equality_child_struct_left_item or equality_child_struct_left_nonhead_inline
                        if equality_child_struct_left_item:
                            equality_child_struct_left_count = equality_child_struct_left_count + 1
                        else:
                            equality_child_struct_left_var: uint1_t = equality_child_struct_left_opcode == MOP_VAR
                            equality_child_struct_left_signed: uint1_t = equality_child_struct_left_kind == DATA_SIGNED
                            equality_child_struct_left_zero: uint1_t = memory_out.p0.rd_data.lo == 0
                            equality_child_struct_left_end: uint1_t = equality_child_struct_left_var and equality_child_struct_left_signed
                            equality_child_struct_left_end = equality_child_struct_left_end and equality_child_struct_left_zero
                            if not equality_child_struct_left_end:
                                red2_fault = FAULT_ILLEGAL_TRANSITION
                                microstate = MICRO_FAULT
                            else:
                                equality_child_phase = 28
                elif equality_child_phase == 28:
                    equality_child_struct_right_cursor: uint64_t = equality_child_struct_right_base + equality_child_struct_right_count
                    equality_child_struct_right_cursor_ok: uint1_t = equality_child_struct_right_cursor[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_struct_right_cursor_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_struct_right_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                        equality_child_struct_right_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                        equality_child_struct_right_head: uint1_t = memory_out.p0.rd_data.hi[20]
                        equality_child_struct_right_inline: uint1_t = equality_child_struct_right_opcode == MOP_INT
                        equality_child_struct_right_inline = equality_child_struct_right_inline or equality_child_struct_right_opcode == MOP_FLOAT
                        equality_child_struct_right_inline = equality_child_struct_right_inline or equality_child_struct_right_opcode == MOP_CHAR
                        equality_child_struct_right_inline = equality_child_struct_right_inline or equality_child_struct_right_opcode == MOP_SYM
                        equality_child_struct_right_inline = equality_child_struct_right_inline or equality_child_struct_right_opcode == MOP_PRIM_0
                        equality_child_struct_right_inline = equality_child_struct_right_inline or equality_child_struct_right_opcode == MOP_PRIM_1
                        equality_child_struct_right_inline = equality_child_struct_right_inline or equality_child_struct_right_opcode == MOP_PRIM_2
                        equality_child_struct_right_item: uint1_t = equality_child_struct_right_opcode == MOP_APP
                        equality_child_struct_right_item = equality_child_struct_right_item or equality_child_struct_right_opcode == MOP_APP_VAR
                        equality_child_struct_right_item = equality_child_struct_right_item or equality_child_struct_right_opcode == MOP_EP
                        equality_child_struct_right_nonhead_inline: uint1_t = not equality_child_struct_right_head
                        equality_child_struct_right_nonhead_inline = equality_child_struct_right_nonhead_inline and equality_child_struct_right_inline
                        equality_child_struct_right_item = equality_child_struct_right_item or equality_child_struct_right_nonhead_inline
                        if equality_child_struct_right_item:
                            equality_child_struct_right_count = equality_child_struct_right_count + 1
                        else:
                            equality_child_struct_right_var: uint1_t = equality_child_struct_right_opcode == MOP_VAR
                            equality_child_struct_right_signed: uint1_t = equality_child_struct_right_kind == DATA_SIGNED
                            equality_child_struct_right_zero: uint1_t = memory_out.p0.rd_data.lo == 0
                            equality_child_struct_right_end: uint1_t = equality_child_struct_right_var and equality_child_struct_right_signed
                            equality_child_struct_right_end = equality_child_struct_right_end and equality_child_struct_right_zero
                            if not equality_child_struct_right_end:
                                red2_fault = FAULT_ILLEGAL_TRANSITION
                                microstate = MICRO_FAULT
                            else:
                                equality_child_phase = 29
                elif equality_child_phase == 29:
                    if equality_child_struct_left_count != equality_child_struct_right_count:
                        equality_child_struct_result_destination17: uint17_t = equality_child_join_address + 1
                        equality_child_struct_result_ok: uint1_t = equality_child_struct_result_destination17[16:GRAPH_ADDR_BITS] == 0
                        equality_child_struct_result_gap: uint17_t = free_space - equality_child_struct_result_destination17
                        equality_child_struct_result_wrapped: uint1_t = equality_child_struct_result_gap[16]
                        equality_child_struct_result_nonzero: uint1_t = equality_child_struct_result_gap != 0
                        equality_child_struct_result_space: uint1_t = equality_child_struct_result_wrapped == 0
                        equality_child_struct_result_space = equality_child_struct_result_space and equality_child_struct_result_nonzero
                        if join_false_literal_id == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        elif not equality_child_struct_result_ok:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not equality_child_struct_result_space:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_false_literal_id, hi=91619328)
                            equality_child_phase = 10
                    elif equality_child_struct_left_count == 0:
                        equality_child_struct_empty_destination17: uint17_t = equality_child_join_address + 1
                        equality_child_struct_empty_ok: uint1_t = equality_child_struct_empty_destination17[16:GRAPH_ADDR_BITS] == 0
                        equality_child_struct_empty_gap: uint17_t = free_space - equality_child_struct_empty_destination17
                        equality_child_struct_empty_wrapped: uint1_t = equality_child_struct_empty_gap[16]
                        equality_child_struct_empty_nonzero: uint1_t = equality_child_struct_empty_gap != 0
                        equality_child_struct_empty_space: uint1_t = equality_child_struct_empty_wrapped == 0
                        equality_child_struct_empty_space = equality_child_struct_empty_space and equality_child_struct_empty_nonzero
                        if join_true_literal_id == 0:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        elif not equality_child_struct_empty_ok:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not equality_child_struct_empty_space:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        else:
                            join_publish_word = red2_word_t(lo=join_true_literal_id, hi=91619328)
                            equality_child_phase = 10
                    else:
                        equality_child_struct_count32: uint32_t = equality_child_struct_left_count
                        equality_child_struct_span32: uint32_t = equality_child_struct_count32 + equality_child_struct_count32
                        equality_child_struct_span32 = equality_child_struct_span32 + equality_child_struct_count32
                        equality_child_struct_span32 = equality_child_struct_span32 + equality_child_struct_count32
                        equality_child_struct_span32 = equality_child_struct_span32 + equality_child_struct_count32
                        equality_child_struct_span32 = equality_child_struct_span32 + equality_child_struct_count32
                        equality_child_struct_span32 = equality_child_struct_span32 + equality_child_struct_count32
                        equality_child_struct_span32 = equality_child_struct_span32 + equality_child_struct_count32
                        equality_child_struct_span32 = equality_child_struct_span32 + equality_child_struct_count32
                        equality_child_struct_join32: uint32_t = equality_child_join_address
                        equality_child_struct_final32: uint32_t = equality_child_struct_join32 + equality_child_struct_span32
                        equality_child_struct_final32 = equality_child_struct_final32 + 2
                        equality_child_struct_final_ok: uint1_t = equality_child_struct_final32[31:GRAPH_ADDR_BITS] == 0
                        equality_child_struct_final17: uint17_t = equality_child_struct_final32[16:0]
                        equality_child_struct_gap: uint17_t = free_space - equality_child_struct_final17
                        equality_child_struct_gap_wrapped: uint1_t = equality_child_struct_gap[16]
                        equality_child_struct_gap_nonzero: uint1_t = equality_child_struct_gap != 0
                        equality_child_struct_space_ok: uint1_t = equality_child_struct_gap_wrapped == 0
                        equality_child_struct_space_ok = equality_child_struct_space_ok and equality_child_struct_gap_nonzero
                        equality_child_struct_has_star: uint1_t = join_equal_star_literal_id != 0
                        equality_child_struct_has_true: uint1_t = join_true_literal_id != 0
                        equality_child_struct_has_false: uint1_t = join_false_literal_id != 0
                        equality_child_struct_has_if: uint1_t = join_equal_if_literal_id != 0
                        equality_child_struct_meta_ok: uint1_t = equality_child_struct_has_star and equality_child_struct_has_true
                        equality_child_struct_meta_ok = equality_child_struct_meta_ok and equality_child_struct_has_false
                        equality_child_struct_meta_ok = equality_child_struct_meta_ok and equality_child_struct_has_if
                        if not equality_child_struct_meta_ok:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        elif not equality_child_struct_final_ok:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not equality_child_struct_space_ok:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        else:
                            equality_child_struct_count64: uint64_t = equality_child_struct_left_count
                            equality_child_struct_last_offset: uint64_t = equality_child_struct_count64 - 1
                            equality_child_left = equality_child_struct_left_base + equality_child_struct_last_offset
                            equality_child_right = equality_child_struct_right_base + equality_child_struct_last_offset
                            equality_child_lambdas = equality_child_lambdas + 1
                            equality_child_build_descriptor = 1
                            equality_child_build_app_mode = 0
                            equality_child_build_count = equality_child_struct_left_count
                            equality_child_build_index = 0
                            equality_child_build_cursor = equality_child_join_address
                            equality_child_build_root = 0
                            equality_child_build_false_root = 0
                            equality_child_build_if_child_root = 0
                            equality_child_phase = 15
                elif equality_child_phase == 30:
                    equality_child_app_left_cursor: uint64_t = equality_child_struct_left_base + equality_child_struct_left_count
                    equality_child_app_left_cursor_ok: uint1_t = equality_child_app_left_cursor[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_app_left_cursor_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_app_left_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                        equality_child_app_left_head: uint1_t = memory_out.p0.rd_data.hi[20]
                        equality_child_app_left_inline: uint1_t = equality_child_app_left_opcode == MOP_INT
                        equality_child_app_left_inline = equality_child_app_left_inline or equality_child_app_left_opcode == MOP_FLOAT
                        equality_child_app_left_inline = equality_child_app_left_inline or equality_child_app_left_opcode == MOP_CHAR
                        equality_child_app_left_inline = equality_child_app_left_inline or equality_child_app_left_opcode == MOP_SYM
                        equality_child_app_left_inline = equality_child_app_left_inline or equality_child_app_left_opcode == MOP_PRIM_0
                        equality_child_app_left_inline = equality_child_app_left_inline or equality_child_app_left_opcode == MOP_PRIM_1
                        equality_child_app_left_inline = equality_child_app_left_inline or equality_child_app_left_opcode == MOP_PRIM_2
                        equality_child_app_left_prefix: uint1_t = equality_child_app_left_opcode == MOP_APP
                        equality_child_app_left_prefix = equality_child_app_left_prefix or equality_child_app_left_opcode == MOP_APP_VAR
                        equality_child_app_left_nonhead_inline: uint1_t = not equality_child_app_left_head
                        equality_child_app_left_nonhead_inline = equality_child_app_left_nonhead_inline and equality_child_app_left_inline
                        equality_child_app_left_prefix = equality_child_app_left_prefix or equality_child_app_left_nonhead_inline
                        if equality_child_app_left_prefix:
                            equality_child_struct_left_count = equality_child_struct_left_count + 1
                        else:
                            equality_child_left = equality_child_app_left_cursor
                            equality_child_phase = 31
                elif equality_child_phase == 31:
                    equality_child_app_right_cursor: uint64_t = equality_child_struct_right_base + equality_child_struct_right_count
                    equality_child_app_right_cursor_ok: uint1_t = equality_child_app_right_cursor[63:GRAPH_ADDR_BITS] == 0
                    if not equality_child_app_right_cursor_ok:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not equality_child_word_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        equality_child_app_right_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                        equality_child_app_right_head: uint1_t = memory_out.p0.rd_data.hi[20]
                        equality_child_app_right_inline: uint1_t = equality_child_app_right_opcode == MOP_INT
                        equality_child_app_right_inline = equality_child_app_right_inline or equality_child_app_right_opcode == MOP_FLOAT
                        equality_child_app_right_inline = equality_child_app_right_inline or equality_child_app_right_opcode == MOP_CHAR
                        equality_child_app_right_inline = equality_child_app_right_inline or equality_child_app_right_opcode == MOP_SYM
                        equality_child_app_right_inline = equality_child_app_right_inline or equality_child_app_right_opcode == MOP_PRIM_0
                        equality_child_app_right_inline = equality_child_app_right_inline or equality_child_app_right_opcode == MOP_PRIM_1
                        equality_child_app_right_inline = equality_child_app_right_inline or equality_child_app_right_opcode == MOP_PRIM_2
                        equality_child_app_right_prefix: uint1_t = equality_child_app_right_opcode == MOP_APP
                        equality_child_app_right_prefix = equality_child_app_right_prefix or equality_child_app_right_opcode == MOP_APP_VAR
                        equality_child_app_right_nonhead_inline: uint1_t = not equality_child_app_right_head
                        equality_child_app_right_nonhead_inline = equality_child_app_right_nonhead_inline and equality_child_app_right_inline
                        equality_child_app_right_prefix = equality_child_app_right_prefix or equality_child_app_right_nonhead_inline
                        if equality_child_app_right_prefix:
                            equality_child_struct_right_count = equality_child_struct_right_count + 1
                        elif equality_child_struct_left_count != equality_child_struct_right_count:
                            equality_child_app_false_destination17: uint17_t = equality_child_join_address + 1
                            equality_child_app_false_ok: uint1_t = equality_child_app_false_destination17[16:GRAPH_ADDR_BITS] == 0
                            equality_child_app_false_gap: uint17_t = free_space - equality_child_app_false_destination17
                            equality_child_app_false_wrapped: uint1_t = equality_child_app_false_gap[16]
                            equality_child_app_false_nonzero: uint1_t = equality_child_app_false_gap != 0
                            equality_child_app_false_space: uint1_t = equality_child_app_false_wrapped == 0
                            equality_child_app_false_space = equality_child_app_false_space and equality_child_app_false_nonzero
                            if join_false_literal_id == 0:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            elif not equality_child_app_false_ok:
                                red2_fault = FAULT_INVALID_ADDRESS
                                microstate = MICRO_FAULT
                            elif not equality_child_app_false_space:
                                red2_fault = FAULT_GRAPH_ENV_COLLISION
                                microstate = MICRO_FAULT
                            else:
                                join_publish_word = red2_word_t(lo=join_false_literal_id, hi=91619328)
                                equality_child_phase = 10
                        else:
                            equality_child_right = equality_child_app_right_cursor
                            equality_child_app_count32: uint32_t = equality_child_struct_left_count
                            equality_child_app_count32 = equality_child_app_count32 + 1
                            equality_child_app_span32: uint32_t = equality_child_app_count32 + equality_child_app_count32
                            equality_child_app_span32 = equality_child_app_span32 + equality_child_app_count32
                            equality_child_app_span32 = equality_child_app_span32 + equality_child_app_count32
                            equality_child_app_span32 = equality_child_app_span32 + equality_child_app_count32
                            equality_child_app_span32 = equality_child_app_span32 + equality_child_app_count32
                            equality_child_app_span32 = equality_child_app_span32 + equality_child_app_count32
                            equality_child_app_span32 = equality_child_app_span32 + equality_child_app_count32
                            equality_child_app_span32 = equality_child_app_span32 + equality_child_app_count32
                            equality_child_app_join32: uint32_t = equality_child_join_address
                            equality_child_app_final32: uint32_t = equality_child_app_join32 + equality_child_app_span32
                            equality_child_app_final32 = equality_child_app_final32 + 2
                            equality_child_app_final_ok: uint1_t = equality_child_app_final32[31:GRAPH_ADDR_BITS] == 0
                            equality_child_app_final17: uint17_t = equality_child_app_final32[16:0]
                            equality_child_app_gap: uint17_t = free_space - equality_child_app_final17
                            equality_child_app_gap_wrapped: uint1_t = equality_child_app_gap[16]
                            equality_child_app_gap_nonzero: uint1_t = equality_child_app_gap != 0
                            equality_child_app_space_ok: uint1_t = equality_child_app_gap_wrapped == 0
                            equality_child_app_space_ok = equality_child_app_space_ok and equality_child_app_gap_nonzero
                            equality_child_app_has_star: uint1_t = join_equal_star_literal_id != 0
                            equality_child_app_has_true: uint1_t = join_true_literal_id != 0
                            equality_child_app_has_false: uint1_t = join_false_literal_id != 0
                            equality_child_app_has_if: uint1_t = join_equal_if_literal_id != 0
                            equality_child_app_meta_ok: uint1_t = equality_child_app_has_star and equality_child_app_has_true
                            equality_child_app_meta_ok = equality_child_app_meta_ok and equality_child_app_has_false
                            equality_child_app_meta_ok = equality_child_app_meta_ok and equality_child_app_has_if
                            if not equality_child_app_meta_ok:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            elif not equality_child_app_final_ok:
                                red2_fault = FAULT_INVALID_ADDRESS
                                microstate = MICRO_FAULT
                            elif not equality_child_app_space_ok:
                                red2_fault = FAULT_GRAPH_ENV_COLLISION
                                microstate = MICRO_FAULT
                            else:
                                equality_child_build_descriptor = 0
                                equality_child_build_app_mode = 1
                                equality_child_build_count = equality_child_struct_left_count + 1
                                equality_child_build_index = 0
                                equality_child_build_cursor = equality_child_join_address
                                equality_child_build_root = 0
                                equality_child_build_false_root = 0
                                equality_child_build_if_child_root = 0
                                equality_child_phase = 15
                else:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
            elif equality_launch_active:
                if equality_launch_phase == 0:
                    if equality_launch_clear_remaining != 0:
                        equality_launch_clear_index = equality_launch_clear_index - 1
                        equality_launch_clear_remaining = equality_launch_clear_remaining - 1
                    else:
                        equality_launch_phase = 1
                elif equality_launch_phase == 1:
                    equality_launch_phase = 2
                elif equality_launch_phase == 2:
                    equality_launch_phase = 3
                elif equality_launch_phase == 3:
                    equality_launch_phase = 4
                elif equality_launch_phase == 4:
                    equality_launch_phase = 5
                elif equality_launch_phase == 5:
                    equality_launch_phase = 6
                elif equality_launch_phase == 6:
                    equality_launch_phase = 7
                elif equality_launch_phase == 7:
                    equality_launch_phase = 8
                elif equality_launch_phase == 8:
                    equality_launch_phase = 9
                elif equality_launch_phase == 9:
                    equality_launch_phase = 10
                elif equality_launch_phase == 10:
                    equality_launch_phase = 11
                elif equality_launch_phase == 11:
                    if equality_launch_needs_bridge:
                        equality_launch_phase = 12
                    else:
                        equality_launch_final_fsp17: uint17_t = equality_launch_live_fsp + 7
                        equality_launch_final_control17: uint17_t = join_frame_index + 3
                        fsp = equality_launch_final_fsp17[15:0]
                        env = equality_launch_normalized_env
                        free_space = equality_launch_normalized_env
                        control_top = equality_launch_final_control17
                        direction = DIRECTION_FORWARD
                        q = q - 1
                        argcnt = 1
                        prim_id = 0
                        fire = 0
                        pc = equality_launch_task_root
                        s_a = join_published_root + 1
                        equality_launch_active = 0
                        equality_atomic_active = 0
                        join_prim_scalar_op = SCALAR_OP_NONE
                        join_scalar_preflight_done = 0
                        join_scalar_contract = 0
                        microstate = MICRO_COMMIT
                elif equality_launch_phase == 12:
                    equality_launch_final_fsp17_bridge: uint17_t = equality_launch_live_fsp + 7
                    equality_launch_final_control17_bridge: uint17_t = join_frame_index + 3
                    fsp = equality_launch_final_fsp17_bridge[15:0]
                    env = equality_launch_normalized_env
                    free_space = equality_launch_normalized_env
                    control_top = equality_launch_final_control17_bridge
                    direction = DIRECTION_FORWARD
                    q = q - 1
                    argcnt = 1
                    prim_id = 0
                    fire = 0
                    pc = equality_launch_task_root
                    s_a = join_published_root + 1
                    equality_launch_active = 0
                    equality_atomic_active = 0
                    join_prim_scalar_op = SCALAR_OP_NONE
                    join_scalar_preflight_done = 0
                    join_scalar_contract = 0
                    microstate = MICRO_COMMIT
                else:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
            elif prim0_y_active:
                prim0_y_argument_in_range: uint1_t = prim0_y_argument_address[15:GRAPH_ADDR_BITS] == 0
                prim0_y_argument_zero_lo: uint1_t = memory_out.p0.rd_data.lo == 0
                prim0_y_argument_zero_hi: uint1_t = memory_out.p0.rd_data.hi == 0
                prim0_y_argument_zero: uint1_t = prim0_y_argument_zero_lo and prim0_y_argument_zero_hi
                prim0_y_fsp_in_range: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                prim0_y_argument_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                prim0_y_argument_is_app: uint1_t = prim0_y_argument_opcode == MOP_APP
                prim0_y_argument_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                prim0_y_app_signed: uint1_t = prim0_y_argument_kind == DATA_SIGNED
                prim0_y_app_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                prim0_y_scratch_address: uint17_t = fsp + 1
                prim0_y_scratch_in_range: uint1_t = prim0_y_scratch_address[16:GRAPH_ADDR_BITS] == 0
                prim0_y_scratch_gap: uint17_t = free_space - prim0_y_scratch_address
                prim0_y_scratch_wrapped: uint1_t = prim0_y_scratch_gap[16]
                prim0_y_scratch_nonzero: uint1_t = prim0_y_scratch_gap != 0
                prim0_y_scratch_before_free: uint1_t = prim0_y_scratch_wrapped == 0
                prim0_y_scratch_before_free = prim0_y_scratch_before_free and prim0_y_scratch_nonzero
                prim0_y_env_low: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
                prim0_y_env_end: uint1_t = env == GRAPH_WORDS
                prim0_y_env_valid: uint1_t = prim0_y_env_low or prim0_y_env_end
                prim0_y_control_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
                prim0_y_control_end: uint1_t = control_top == CONTROL_WORDS
                prim0_y_control_valid: uint1_t = prim0_y_control_low or prim0_y_control_end
                if not prim0_y_argument_in_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif prim0_y_argument_zero:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not prim0_y_fsp_in_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif prim0_y_argument_is_app:
                    if not prim0_y_app_signed or prim0_y_app_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    else:
                        prim0_y_target = memory_out.p0.rd_data.lo[15:0]
                        prim0_y_needs_scratch = 0
                        microstate = MICRO_JOIN_SPECIAL_META_DONE
                elif not prim0_y_scratch_in_range:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not prim0_y_scratch_before_free:
                    red2_fault = FAULT_GRAPH_ENV_COLLISION
                    microstate = MICRO_FAULT
                elif not prim0_y_env_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not prim0_y_control_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif prim0_y_control_end:
                    red2_fault = FAULT_CONTROL_OVERFLOW
                    microstate = MICRO_FAULT
                else:
                    # Match the oracle's Y scratch clone exactly: closure-slot is
                    # cleared and head is set, while opcode/kind/definition stay intact.
                    prim0_y_clone_hi: uint64_t = memory_out.p0.rd_data.hi & 18446744073709027327
                    prim0_y_clone_hi = prim0_y_clone_hi | 1048576
                    prim0_y_scratch_word = red2_word_t(
                        lo=memory_out.p0.rd_data.lo,
                        hi=prim0_y_clone_hi,
                    )
                    prim0_y_needs_scratch = 1
                    microstate = MICRO_JOIN_SPECIAL_META_DONE
            else:
                join_scalar_left_address17: uint17_t = join_parent_address + 1
                join_scalar_left_in_range: uint1_t = join_scalar_left_address17[16:GRAPH_ADDR_BITS] == 0
                join_scalar_left_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                join_scalar_resume: uint6_t = MICRO_JOIN_PUBLISH
                if join_scalar_return_ep:
                    join_scalar_resume = MICRO_JOIN_EP_RESULT_WRITE
                if not join_scalar_left_in_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not join_scalar_left_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_scalar_left_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                    join_scalar_right_opcode: uint5_t = join_scalar_right_word.hi[25:21]
                    join_scalar_left_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                    join_scalar_right_kind: uint2_t = join_scalar_right_word.hi[18:17]
                    join_scalar_left_is_int: uint1_t = join_scalar_left_opcode == MOP_INT
                    join_scalar_right_is_int: uint1_t = join_scalar_right_opcode == MOP_INT
                    join_scalar_left_is_float: uint1_t = join_scalar_left_opcode == MOP_FLOAT
                    join_scalar_right_is_float: uint1_t = join_scalar_right_opcode == MOP_FLOAT
                    join_scalar_left_is_char: uint1_t = join_scalar_left_opcode == MOP_CHAR
                    join_scalar_right_is_char: uint1_t = join_scalar_right_opcode == MOP_CHAR
                    join_scalar_left_signed: uint1_t = join_scalar_left_kind == DATA_SIGNED
                    join_scalar_right_signed: uint1_t = join_scalar_right_kind == DATA_SIGNED
                    join_scalar_both_int: uint1_t = join_scalar_left_is_int and join_scalar_right_is_int
                    join_scalar_both_signed: uint1_t = join_scalar_left_signed and join_scalar_right_signed
                    join_scalar_int_pair: uint1_t = join_scalar_both_int and join_scalar_both_signed
                    join_scalar_any_float: uint1_t = join_scalar_left_is_float or join_scalar_right_is_float

                    join_scalar_left_is_sym: uint1_t = join_scalar_left_opcode == MOP_SYM
                    join_scalar_left_is_prim0: uint1_t = join_scalar_left_opcode == MOP_PRIM_0
                    join_scalar_left_is_prim1: uint1_t = join_scalar_left_opcode == MOP_PRIM_1
                    join_scalar_left_is_prim2: uint1_t = join_scalar_left_opcode == MOP_PRIM_2
                    join_scalar_left_symbol_opcode: uint1_t = join_scalar_left_is_sym or join_scalar_left_is_prim0
                    join_scalar_left_symbol_opcode = join_scalar_left_symbol_opcode or join_scalar_left_is_prim1
                    join_scalar_left_symbol_opcode = join_scalar_left_symbol_opcode or join_scalar_left_is_prim2
                    join_scalar_left_literal: uint1_t = join_scalar_left_kind == DATA_LITERAL_ID
                    join_scalar_left_symbol: uint1_t = join_scalar_left_symbol_opcode and join_scalar_left_literal

                    join_scalar_right_is_sym: uint1_t = join_scalar_right_opcode == MOP_SYM
                    join_scalar_right_is_prim0: uint1_t = join_scalar_right_opcode == MOP_PRIM_0
                    join_scalar_right_is_prim1: uint1_t = join_scalar_right_opcode == MOP_PRIM_1
                    join_scalar_right_is_prim2: uint1_t = join_scalar_right_opcode == MOP_PRIM_2
                    join_scalar_right_symbol_opcode: uint1_t = join_scalar_right_is_sym or join_scalar_right_is_prim0
                    join_scalar_right_symbol_opcode = join_scalar_right_symbol_opcode or join_scalar_right_is_prim1
                    join_scalar_right_symbol_opcode = join_scalar_right_symbol_opcode or join_scalar_right_is_prim2
                    join_scalar_right_literal: uint1_t = join_scalar_right_kind == DATA_LITERAL_ID
                    join_scalar_right_symbol: uint1_t = join_scalar_right_symbol_opcode and join_scalar_right_literal

                    join_scalar_left_is_app: uint1_t = join_scalar_left_opcode == MOP_APP
                    join_scalar_left_is_app_var: uint1_t = join_scalar_left_opcode == MOP_APP_VAR
                    join_scalar_left_is_var: uint1_t = join_scalar_left_opcode == MOP_VAR
                    join_scalar_left_blocked: uint1_t = join_scalar_left_is_app or join_scalar_left_is_app_var
                    join_scalar_left_blocked = join_scalar_left_blocked or join_scalar_left_is_var
                    join_scalar_right_is_app: uint1_t = join_scalar_right_opcode == MOP_APP
                    join_scalar_right_is_app_var: uint1_t = join_scalar_right_opcode == MOP_APP_VAR
                    join_scalar_right_is_var: uint1_t = join_scalar_right_opcode == MOP_VAR
                    join_scalar_right_blocked: uint1_t = join_scalar_right_is_app or join_scalar_right_is_app_var
                    join_scalar_right_blocked = join_scalar_right_blocked or join_scalar_right_is_var

                    join_scalar_op_add: uint1_t = join_prim_scalar_op == SCALAR_OP_ADD
                    join_scalar_op_sub: uint1_t = join_prim_scalar_op == SCALAR_OP_SUB
                    join_scalar_op_mul: uint1_t = join_prim_scalar_op == SCALAR_OP_MUL
                    join_scalar_op_div: uint1_t = join_prim_scalar_op == SCALAR_OP_DIV
                    join_scalar_op_expt: uint1_t = join_prim_scalar_op == SCALAR_OP_EXPT
                    join_scalar_op_mod: uint1_t = join_prim_scalar_op == SCALAR_OP_MOD
                    join_scalar_op_lt: uint1_t = join_prim_scalar_op == SCALAR_OP_LT
                    join_scalar_op_gt: uint1_t = join_prim_scalar_op == SCALAR_OP_GT
                    join_scalar_op_le: uint1_t = join_prim_scalar_op == SCALAR_OP_LE
                    join_scalar_op_ge: uint1_t = join_prim_scalar_op == SCALAR_OP_GE
                    join_scalar_op_eq: uint1_t = join_prim_scalar_op == SCALAR_OP_EQ
                    join_scalar_op_max: uint1_t = join_prim_scalar_op == SCALAR_OP_MAX
                    join_scalar_op_min: uint1_t = join_prim_scalar_op == SCALAR_OP_MIN

                    if join_scalar_op_eq and equality_atomic_active:
                        # _task9_constant_class: INT/signed, FLOAT/float64,
                        # CHAR/literal, and SYM/PRIM_*/literal form four classes.
                        join_eq_left_int: uint1_t = join_scalar_left_is_int and join_scalar_left_signed
                        join_eq_right_int: uint1_t = join_scalar_right_is_int and join_scalar_right_signed
                        join_eq_left_float: uint1_t = join_scalar_left_is_float and join_scalar_left_kind == DATA_FLOAT64
                        join_eq_right_float: uint1_t = join_scalar_right_is_float and join_scalar_right_kind == DATA_FLOAT64
                        join_eq_left_char: uint1_t = join_scalar_left_is_char and join_scalar_left_literal
                        join_eq_right_char: uint1_t = join_scalar_right_is_char and join_scalar_right_literal
                        join_eq_left_symbol: uint1_t = join_scalar_left_symbol
                        join_eq_right_symbol: uint1_t = join_scalar_right_symbol
                        join_eq_left_constant: uint1_t = join_eq_left_int or join_eq_left_float
                        join_eq_left_constant = join_eq_left_constant or join_eq_left_char
                        join_eq_left_constant = join_eq_left_constant or join_eq_left_symbol
                        join_eq_right_constant: uint1_t = join_eq_right_int or join_eq_right_float
                        join_eq_right_constant = join_eq_right_constant or join_eq_right_char
                        join_eq_right_constant = join_eq_right_constant or join_eq_right_symbol
                        if not join_eq_left_constant or not join_eq_right_constant:
                            # Structural EQUAL? is launched inside the same shadowed
                            # JOIN transaction. Preflight every later failure before
                            # publishing the JOIN parent or replacing its control frame.
                            equality_live_fsp_calc: uint16_t = fsp
                            if not join_preserve_fsp:
                                if join_parent_word.hi[20]:
                                    equality_live_fsp_calc = join_parent_address
                                else:
                                    equality_live_fsp_calc = fsp - 2
                            equality_live17: uint17_t = equality_live_fsp_calc
                            equality_control_two: uint17_t = join_frame_index + 2
                            equality_control_two_gap: uint17_t = CONTROL_WORDS - equality_control_two
                            equality_control_two_ok: uint1_t = equality_control_two_gap[16] == 0
                            equality_task_parent17: uint17_t = equality_live17 + 6
                            equality_task_gap: uint17_t = join_frame_free_space - equality_task_parent17
                            equality_task_gap_wrapped: uint1_t = equality_task_gap[16]
                            equality_task_gap_nonzero: uint1_t = equality_task_gap != 0
                            equality_task_space_ok: uint1_t = equality_task_gap_wrapped == 0
                            equality_task_space_ok = equality_task_space_ok and equality_task_gap_nonzero
                            equality_needs_bridge_calc: uint1_t = join_frame_env != join_frame_free_space
                            equality_normalized_env_calc: uint17_t = join_frame_env
                            if equality_needs_bridge_calc:
                                equality_normalized_env_calc = join_frame_free_space - 1
                            equality_join17: uint17_t = equality_live17 + 7
                            equality_join_gap: uint17_t = equality_normalized_env_calc - equality_join17
                            equality_join_gap_wrapped: uint1_t = equality_join_gap[16]
                            equality_join_gap_nonzero: uint1_t = equality_join_gap != 0
                            equality_join_space_ok: uint1_t = equality_join_gap_wrapped == 0
                            equality_join_space_ok = equality_join_space_ok and equality_join_gap_nonzero
                            equality_control_three: uint17_t = join_frame_index + 3
                            equality_control_three_gap: uint17_t = CONTROL_WORDS - equality_control_three
                            equality_control_three_ok: uint1_t = equality_control_three_gap[16] == 0
                            if not equality_control_two_ok:
                                red2_fault = FAULT_CONTROL_OVERFLOW
                                microstate = MICRO_FAULT
                            elif join_equal_star_literal_id == 0:
                                red2_fault = FAULT_ILLEGAL_TRANSITION
                                microstate = MICRO_FAULT
                            elif not equality_task_space_ok:
                                red2_fault = FAULT_GRAPH_ENV_COLLISION
                                microstate = MICRO_FAULT
                            elif join_equality_continue_literal_id == 0:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            elif not equality_join_space_ok:
                                red2_fault = FAULT_GRAPH_ENV_COLLISION
                                microstate = MICRO_FAULT
                            elif not equality_control_three_ok:
                                red2_fault = FAULT_CONTROL_OVERFLOW
                                microstate = MICRO_FAULT
                            else:
                                equality_new_control_top: uint17_t = join_frame_index + 3
                                equality_old_control_delta: uint17_t = control_top - equality_new_control_top
                                equality_old_control_wrapped: uint1_t = equality_old_control_delta[16]
                                equality_old_control_extra: uint16_t = 0
                                if not equality_old_control_wrapped:
                                    equality_old_control_extra = equality_old_control_delta[15:0]
                                equality_launch_active = 1
                                equality_launch_phase = 0
                                equality_launch_live_fsp = equality_live_fsp_calc
                                equality_launch_task_root = equality_live_fsp_calc + 1
                                equality_launch_normalized_env = equality_normalized_env_calc
                                equality_launch_needs_bridge = equality_needs_bridge_calc
                                equality_launch_clear_index = control_top
                                equality_launch_clear_remaining = equality_old_control_extra
                                equality_atomic_active = 0
                                microstate = MICRO_JOIN_SCALAR_LEFT_READ
                        else:
                            join_eq_same_class: uint1_t = join_eq_left_int and join_eq_right_int
                            join_eq_same_float: uint1_t = join_eq_left_float and join_eq_right_float
                            join_eq_same_char: uint1_t = join_eq_left_char and join_eq_right_char
                            join_eq_same_symbol: uint1_t = join_eq_left_symbol and join_eq_right_symbol
                            join_eq_same_class = join_eq_same_class or join_eq_same_float
                            join_eq_same_class = join_eq_same_class or join_eq_same_char
                            join_eq_same_class = join_eq_same_class or join_eq_same_symbol
                            join_eq_value: uint1_t = 0
                            if join_eq_same_float:
                                join_eq_left_exp: uint16_t = memory_out.p0.rd_data.lo[62:52]
                                join_eq_right_exp: uint16_t = join_scalar_right_word.lo[62:52]
                                join_eq_left_mantissa: uint64_t = memory_out.p0.rd_data.lo & 4503599627370495
                                join_eq_right_mantissa: uint64_t = join_scalar_right_word.lo & 4503599627370495
                                # Keep mixed-width comparisons in separate typed
                                # temporaries; pinned PipelineC otherwise assigns
                                # duplicate generated helper names inside one bool op.
                                join_eq_left_exp_nan: uint1_t = join_eq_left_exp == 2047
                                join_eq_left_mantissa_nonzero: uint1_t = join_eq_left_mantissa != 0
                                join_eq_left_nan: uint1_t = join_eq_left_exp_nan and join_eq_left_mantissa_nonzero
                                join_eq_right_exp_nan: uint1_t = join_eq_right_exp == 2047
                                join_eq_right_mantissa_nonzero: uint1_t = join_eq_right_mantissa != 0
                                join_eq_right_nan: uint1_t = join_eq_right_exp_nan and join_eq_right_mantissa_nonzero
                                join_eq_any_nan: uint1_t = join_eq_left_nan or join_eq_right_nan
                                join_eq_left_zero: uint1_t = (memory_out.p0.rd_data.lo & 9223372036854775807) == 0
                                join_eq_right_zero: uint1_t = (join_scalar_right_word.lo & 9223372036854775807) == 0
                                join_eq_both_zero: uint1_t = join_eq_left_zero and join_eq_right_zero
                                if not join_eq_any_nan:
                                    join_eq_value = join_eq_both_zero or memory_out.p0.rd_data.lo == join_scalar_right_word.lo
                            elif join_eq_same_class:
                                join_eq_value = memory_out.p0.rd_data.lo == join_scalar_right_word.lo
                            join_eq_bool_id: uint32_t = join_false_literal_id
                            if join_eq_value:
                                join_eq_bool_id = join_true_literal_id
                            if join_eq_bool_id == 0:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            else:
                                join_publish_word = red2_word_t(lo=join_eq_bool_id, hi=91619328)
                                join_scalar_contract = 1
                                join_scalar_preflight_done = 1
                                equality_atomic_active = 0
                                microstate = join_scalar_resume
                    elif join_scalar_op_eq:
                        if join_scalar_any_float:
                            red2_fault = FAULT_UNSUPPORTED_VALUE
                            microstate = MICRO_FAULT
                        else:
                            join_scalar_eq_contract: uint1_t = 0
                            join_scalar_eq_value: uint1_t = 0
                            if join_scalar_left_is_int and join_scalar_right_is_int:
                                join_scalar_eq_contract = 1
                                join_scalar_eq_value = memory_out.p0.rd_data.lo == join_scalar_right_word.lo
                            elif join_scalar_left_is_char and join_scalar_right_is_char:
                                join_scalar_eq_contract = 1
                                join_scalar_eq_value = memory_out.p0.rd_data.lo == join_scalar_right_word.lo
                            elif join_scalar_left_symbol and join_scalar_right_symbol:
                                join_scalar_eq_contract = 1
                                join_scalar_eq_value = memory_out.p0.rd_data.lo == join_scalar_right_word.lo
                            elif not join_scalar_left_blocked and not join_scalar_right_blocked:
                                join_scalar_eq_contract = 1
                            if join_scalar_eq_contract:
                                join_scalar_eq_bool_id: uint32_t = join_false_literal_id
                                if join_scalar_eq_value:
                                    join_scalar_eq_bool_id = join_true_literal_id
                                if join_scalar_eq_bool_id == 0:
                                    red2_fault = FAULT_UNSUPPORTED_VALUE
                                    microstate = MICRO_FAULT
                                else:
                                    join_publish_word = red2_word_t(lo=join_scalar_eq_bool_id, hi=91619328)
                                    join_scalar_contract = 1
                                    join_scalar_preflight_done = 1
                                    microstate = join_scalar_resume
                            else:
                                join_scalar_contract = 0
                                join_scalar_preflight_done = 1
                                microstate = join_scalar_resume
                    elif join_scalar_any_float:
                        red2_fault = FAULT_UNSUPPORTED_VALUE
                        microstate = MICRO_FAULT
                    elif not join_scalar_int_pair:
                        join_scalar_contract = 0
                        join_scalar_preflight_done = 1
                        microstate = join_scalar_resume
                    else:
                        join_scalar_left_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                        join_scalar_right_negative: uint1_t = join_scalar_right_word.lo[63]
                        join_scalar_signs_differ: uint1_t = join_scalar_left_negative != join_scalar_right_negative
                        # Avoid PipelineC's generic uint64 < helper here.  When the
                        # signs match, signed subtraction cannot overflow, so the
                        # difference sign is exactly the signed ordering relation.
                        join_scalar_compare_delta: uint64_t = memory_out.p0.rd_data.lo - join_scalar_right_word.lo
                        join_scalar_signed_lt: uint1_t = join_scalar_compare_delta[63]
                        if join_scalar_signs_differ:
                            join_scalar_signed_lt = join_scalar_left_negative
                        join_scalar_equal_payload: uint1_t = memory_out.p0.rd_data.lo == join_scalar_right_word.lo
                        if join_scalar_op_add or join_scalar_op_sub:
                            join_scalar_arith_payload: uint64_t = memory_out.p0.rd_data.lo + join_scalar_right_word.lo
                            if join_scalar_op_sub:
                                join_scalar_arith_payload = memory_out.p0.rd_data.lo - join_scalar_right_word.lo
                            join_scalar_result_negative: uint1_t = join_scalar_arith_payload[63]
                            join_scalar_add_same_sign: uint1_t = join_scalar_left_negative == join_scalar_right_negative
                            join_scalar_add_sign_changed: uint1_t = join_scalar_result_negative != join_scalar_left_negative
                            join_scalar_add_overflow: uint1_t = join_scalar_add_same_sign and join_scalar_add_sign_changed
                            join_scalar_sub_signs_differ: uint1_t = join_scalar_left_negative != join_scalar_right_negative
                            join_scalar_sub_sign_changed: uint1_t = join_scalar_result_negative != join_scalar_left_negative
                            join_scalar_sub_overflow: uint1_t = join_scalar_sub_signs_differ and join_scalar_sub_sign_changed
                            join_scalar_arith_overflow: uint1_t = join_scalar_add_overflow
                            if join_scalar_op_sub:
                                join_scalar_arith_overflow = join_scalar_sub_overflow
                            if join_scalar_arith_overflow:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            else:
                                join_publish_word = red2_word_t(lo=join_scalar_arith_payload, hi=85065728)
                                join_scalar_contract = 1
                                join_scalar_preflight_done = 1
                                microstate = join_scalar_resume
                        elif join_scalar_op_mul:
                            join_scalar_left_magnitude: uint64_t = memory_out.p0.rd_data.lo
                            if join_scalar_left_negative:
                                join_scalar_left_magnitude = 0 - memory_out.p0.rd_data.lo
                            join_scalar_right_magnitude: uint64_t = join_scalar_right_word.lo
                            if join_scalar_right_negative:
                                join_scalar_right_magnitude = 0 - join_scalar_right_word.lo
                            join_scalar_mul_negative: uint1_t = join_scalar_signs_differ
                            join_scalar_mul_limit: uint64_t = 9223372036854775807
                            if join_scalar_mul_negative:
                                join_scalar_mul_limit = 9223372036854775808
                            join_scalar_mul_overflow: uint1_t = 0
                            join_scalar_mul_magnitude: uint64_t = 0
                            join_scalar_mul_zero: uint1_t = join_scalar_left_magnitude == 0
                            join_scalar_mul_zero = join_scalar_mul_zero or join_scalar_right_magnitude == 0
                            if not join_scalar_mul_zero:
                                join_scalar_mul_bound: red2_u64_divmod_t = red2_u64_divmod(
                                    join_scalar_mul_limit, join_scalar_right_magnitude
                                )
                                join_scalar_mul_fits: uint1_t = red2_u64_ge(
                                    join_scalar_mul_bound.q, join_scalar_left_magnitude
                                )
                                if not join_scalar_mul_fits:
                                    join_scalar_mul_overflow = 1
                                else:
                                    join_scalar_mul_magnitude = (
                                        join_scalar_left_magnitude * join_scalar_right_magnitude
                                    )
                            if join_scalar_mul_overflow:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            else:
                                join_scalar_mul_payload: uint64_t = join_scalar_mul_magnitude
                                if join_scalar_mul_negative:
                                    join_scalar_mul_payload = 0 - join_scalar_mul_magnitude
                                join_publish_word = red2_word_t(lo=join_scalar_mul_payload, hi=85065728)
                                join_scalar_contract = 1
                                join_scalar_preflight_done = 1
                                microstate = join_scalar_resume
                        elif join_scalar_op_div:
                            join_scalar_div_left_magnitude: uint64_t = memory_out.p0.rd_data.lo
                            if join_scalar_left_negative:
                                join_scalar_div_left_magnitude = 0 - memory_out.p0.rd_data.lo
                            join_scalar_div_right_magnitude: uint64_t = join_scalar_right_word.lo
                            if join_scalar_right_negative:
                                join_scalar_div_right_magnitude = 0 - join_scalar_right_word.lo
                            if join_scalar_div_right_magnitude == 0:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            else:
                                join_scalar_div_result: red2_u64_divmod_t = red2_u64_divmod(
                                    join_scalar_div_left_magnitude, join_scalar_div_right_magnitude
                                )
                                join_scalar_div_inexact: uint1_t = join_scalar_div_result.r != 0
                                join_scalar_div_negative: uint1_t = join_scalar_signs_differ
                                join_scalar_div_positive_overflow: uint1_t = join_scalar_div_result.q[63]
                                join_scalar_div_positive_overflow = join_scalar_div_positive_overflow and not join_scalar_div_negative
                                if join_scalar_div_inexact or join_scalar_div_positive_overflow:
                                    red2_fault = FAULT_UNSUPPORTED_VALUE
                                    microstate = MICRO_FAULT
                                else:
                                    join_scalar_div_payload: uint64_t = join_scalar_div_result.q
                                    if join_scalar_div_negative:
                                        join_scalar_div_payload = 0 - join_scalar_div_result.q
                                    join_publish_word = red2_word_t(lo=join_scalar_div_payload, hi=85065728)
                                    join_scalar_contract = 1
                                    join_scalar_preflight_done = 1
                                    microstate = join_scalar_resume
                        elif join_scalar_op_mod:
                            join_scalar_mod_left_magnitude: uint64_t = memory_out.p0.rd_data.lo
                            if join_scalar_left_negative:
                                join_scalar_mod_left_magnitude = 0 - memory_out.p0.rd_data.lo
                            join_scalar_mod_right_magnitude: uint64_t = join_scalar_right_word.lo
                            if join_scalar_right_negative:
                                join_scalar_mod_right_magnitude = 0 - join_scalar_right_word.lo
                            if join_scalar_mod_right_magnitude == 0:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            else:
                                join_scalar_mod_result: red2_u64_divmod_t = red2_u64_divmod(
                                    join_scalar_mod_left_magnitude, join_scalar_mod_right_magnitude
                                )
                                join_scalar_mod_magnitude: uint64_t = join_scalar_mod_result.r
                                join_scalar_mod_nonzero: uint1_t = join_scalar_mod_result.r != 0
                                if join_scalar_signs_differ and join_scalar_mod_nonzero:
                                    join_scalar_mod_magnitude = (
                                        join_scalar_mod_right_magnitude - join_scalar_mod_result.r
                                    )
                                join_scalar_mod_payload: uint64_t = join_scalar_mod_magnitude
                                if join_scalar_right_negative and join_scalar_mod_nonzero:
                                    join_scalar_mod_payload = 0 - join_scalar_mod_magnitude
                                join_publish_word = red2_word_t(lo=join_scalar_mod_payload, hi=85065728)
                                join_scalar_contract = 1
                                join_scalar_preflight_done = 1
                                microstate = join_scalar_resume
                        elif join_scalar_op_expt:
                            if join_scalar_right_negative:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            else:
                                join_scalar_pow_base_magnitude: uint64_t = memory_out.p0.rd_data.lo
                                if join_scalar_left_negative:
                                    join_scalar_pow_base_magnitude = 0 - memory_out.p0.rd_data.lo
                                join_scalar_pow_exponent: uint64_t = join_scalar_right_word.lo
                                join_scalar_pow_exponent_zero: uint1_t = join_scalar_pow_exponent == 0
                                join_scalar_pow_base_zero: uint1_t = join_scalar_pow_base_magnitude == 0
                                join_scalar_pow_base_one: uint1_t = join_scalar_pow_base_magnitude == 1
                                join_scalar_pow_nontrivial: uint1_t = not join_scalar_pow_base_zero and not join_scalar_pow_base_one
                                join_scalar_pow_large_exponent: uint1_t = join_scalar_pow_exponent[63:6] != 0
                                if join_scalar_pow_nontrivial and join_scalar_pow_large_exponent:
                                    red2_fault = FAULT_UNSUPPORTED_VALUE
                                    microstate = MICRO_FAULT
                                else:
                                    join_scalar_pow_negative: uint1_t = join_scalar_left_negative and join_scalar_pow_exponent[0]
                                    join_scalar_pow_magnitude: uint64_t = 1
                                    join_scalar_pow_overflow: uint1_t = 0
                                    if join_scalar_pow_base_zero and not join_scalar_pow_exponent_zero:
                                        join_scalar_pow_magnitude = 0
                                    elif join_scalar_pow_nontrivial:
                                        join_scalar_pow_limit: uint64_t = 9223372036854775807
                                        if join_scalar_pow_negative:
                                            join_scalar_pow_limit = 9223372036854775808
                                        join_scalar_pow_bound: red2_u64_divmod_t = red2_u64_divmod(
                                            join_scalar_pow_limit, join_scalar_pow_base_magnitude
                                        )
                                        join_scalar_pow_remaining: uint64_t = join_scalar_pow_exponent
                                        for _pow_step in range(63):
                                            if join_scalar_pow_remaining != 0:
                                                join_scalar_pow_fits: uint1_t = red2_u64_ge(
                                                    join_scalar_pow_bound.q, join_scalar_pow_magnitude
                                                )
                                                if not join_scalar_pow_fits:
                                                    join_scalar_pow_overflow = 1
                                                else:
                                                    join_scalar_pow_magnitude = (
                                                        join_scalar_pow_magnitude * join_scalar_pow_base_magnitude
                                                    )
                                                join_scalar_pow_remaining = join_scalar_pow_remaining - 1
                                    if join_scalar_pow_overflow:
                                        red2_fault = FAULT_UNSUPPORTED_VALUE
                                        microstate = MICRO_FAULT
                                    else:
                                        join_scalar_pow_payload: uint64_t = join_scalar_pow_magnitude
                                        if join_scalar_pow_negative:
                                            join_scalar_pow_payload = 0 - join_scalar_pow_magnitude
                                        join_publish_word = red2_word_t(lo=join_scalar_pow_payload, hi=85065728)
                                        join_scalar_contract = 1
                                        join_scalar_preflight_done = 1
                                        microstate = join_scalar_resume
                        elif join_scalar_op_max or join_scalar_op_min:
                            join_scalar_select_left: uint1_t = join_scalar_signed_lt == 0
                            if join_scalar_op_min:
                                join_scalar_select_left = join_scalar_signed_lt or join_scalar_equal_payload
                            join_scalar_select_payload: uint64_t = join_scalar_right_word.lo
                            if join_scalar_select_left:
                                join_scalar_select_payload = memory_out.p0.rd_data.lo
                            join_publish_word = red2_word_t(lo=join_scalar_select_payload, hi=85065728)
                            join_scalar_contract = 1
                            join_scalar_preflight_done = 1
                            microstate = join_scalar_resume
                        else:
                            join_scalar_compare_value: uint1_t = 0
                            if join_scalar_op_lt:
                                join_scalar_compare_value = join_scalar_signed_lt
                            elif join_scalar_op_gt:
                                join_scalar_compare_value = not join_scalar_signed_lt and not join_scalar_equal_payload
                            elif join_scalar_op_le:
                                join_scalar_compare_value = join_scalar_signed_lt or join_scalar_equal_payload
                            elif join_scalar_op_ge:
                                join_scalar_compare_value = not join_scalar_signed_lt
                            join_scalar_compare_bool_id: uint32_t = join_false_literal_id
                            if join_scalar_compare_value:
                                join_scalar_compare_bool_id = join_true_literal_id
                            if join_scalar_compare_bool_id == 0:
                                red2_fault = FAULT_UNSUPPORTED_VALUE
                                microstate = MICRO_FAULT
                            else:
                                join_publish_word = red2_word_t(lo=join_scalar_compare_bool_id, hi=91619328)
                                join_scalar_contract = 1
                                join_scalar_preflight_done = 1
                                microstate = join_scalar_resume
        elif micro_is_join_closure_code_read:
            join_closure_code_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_closure_code_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_closure_code_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            join_closure_env_negative: uint1_t = join_closure_env[63]
            join_closure_code_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            join_closure_env_in_range: uint1_t = join_closure_env[63:GRAPH_ADDR_BITS] == 0
            join_closure_env_is_end: uint1_t = join_closure_env == GRAPH_WORDS
            join_closure_env_valid_range: uint1_t = join_closure_env_in_range or join_closure_env_is_end
            join_closure_code_in_range: uint1_t = memory_out.p0.rd_data.lo[63:GRAPH_ADDR_BITS] == 0
            join_closure_code_is_none: uint1_t = join_closure_code_opcode == MOP_NONE
            join_closure_has_code_slot: uint1_t = join_closure_address != GRAPH_WORDS - 1
            if not join_closure_has_code_slot:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_closure_env_negative:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_env_valid_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_code_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_code_is_none:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_closure_code_kind != DATA_SIGNED:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_closure_code_negative:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_code_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                join_closure_code = memory_out.p0.rd_data.lo
                join_closure_cursor = memory_out.p0.rd_data.lo[15:0]
                microstate = MICRO_JOIN_CLOSURE_LAMBDA_SCAN
        elif micro_is_join_closure_lambda_scan:
            join_closure_scan_cursor_in_range: uint1_t = join_closure_cursor[15:GRAPH_ADDR_BITS] == 0
            join_closure_scan_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_closure_scan_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            if not join_closure_scan_cursor_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_scan_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_closure_scan_opcode == MOP_LAMBDA:
                join_closure_lambda_count = join_closure_lambda_count + 1
                join_closure_cursor = join_closure_cursor + 1
            else:
                microstate = MICRO_JOIN_CLOSURE_BODY_READ
        elif micro_is_join_closure_body_read:
            join_closure_body_cursor_in_range: uint1_t = join_closure_cursor[15:GRAPH_ADDR_BITS] == 0
            join_closure_body_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_closure_body_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_closure_body_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            join_closure_body_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_closure_body_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            join_closure_has_lambda: uint1_t = join_closure_lambda_count != 0
            if not join_closure_body_cursor_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_body_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_has_lambda:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            elif join_closure_body_opcode != MOP_VAR:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            elif join_closure_body_kind != DATA_SIGNED:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_closure_body_negative:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_closure_body_head:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            else:
                join_closure_body_index: uint64_t = memory_out.p0.rd_data.lo
                join_closure_depth64: uint64_t = join_closure_lambda_count
                join_closure_destination17: uint17_t = fsp + 1
                join_closure_local_gap: uint64_t = join_closure_body_index - join_closure_depth64
                join_closure_body_is_local: uint1_t = join_closure_local_gap[63]
                join_closure_destination = join_closure_destination17[15:0]
                if join_closure_body_is_local:
                    join_closure_body_word = red2_word_t(
                        lo=memory_out.p0.rd_data.lo,
                        hi=(memory_out.p0.rd_data.hi & 132644863) | 1048576,
                    )
                    microstate = MICRO_JOIN_CLOSURE_PREFLIGHT
                else:
                    join_closure_env_remaining = join_closure_body_index - join_closure_depth64
                    join_closure_env_cursor = join_closure_env
                    join_closure_env_hops = 0
                    microstate = MICRO_JOIN_CLOSURE_ENV_READ
        elif micro_is_join_closure_env_read:
            join_closure_env_addr_in_range: uint1_t = join_closure_env_cursor[63:GRAPH_ADDR_BITS] == 0
            if not join_closure_env_addr_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                join_closure_env_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                join_closure_env_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                join_closure_env_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                join_closure_env_defvalid: uint1_t = memory_out.p0.rd_data.hi[16]
                join_closure_env_is_pnp: uint1_t = join_closure_env_opcode == MOP_PNP
                join_closure_env_is_int: uint1_t = join_closure_env_opcode == MOP_INT
                join_closure_env_is_float: uint1_t = join_closure_env_opcode == MOP_FLOAT
                join_closure_env_is_char: uint1_t = join_closure_env_opcode == MOP_CHAR
                join_closure_env_is_sym: uint1_t = join_closure_env_opcode == MOP_SYM
                join_closure_env_sym_shareable: uint1_t = join_closure_env_is_sym and not join_closure_env_defvalid
                join_closure_env_atomic: uint1_t = join_closure_env_is_int or join_closure_env_is_float
                join_closure_env_atomic = join_closure_env_atomic or join_closure_env_is_char
                join_closure_env_atomic = join_closure_env_atomic or join_closure_env_sym_shareable
                if not join_closure_env_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_closure_env_is_pnp:
                    join_closure_pnp_signed: uint1_t = join_closure_env_kind == DATA_SIGNED
                    join_closure_pnp_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    join_closure_env_hops_limit: uint1_t = join_closure_env_hops == GRAPH_WORDS - 1
                    if not join_closure_pnp_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_closure_pnp_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_closure_env_hops_limit:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        join_closure_env_cursor = memory_out.p0.rd_data.lo
                        join_closure_env_hops = join_closure_env_hops + 1
                elif join_closure_env_remaining != 0:
                    join_closure_env_is_rec: uint1_t = join_closure_env_opcode == MOP_REC
                    join_closure_env_is_closure: uint1_t = join_closure_env_opcode == MOP_CLOSURE
                    join_closure_env_is_closure_slot: uint1_t = memory_out.p0.rd_data.hi[19]
                    join_closure_env_remaining = join_closure_env_remaining - 1
                    if join_closure_env_is_rec:
                        join_closure_env_cursor = join_closure_env_cursor + 3
                    elif join_closure_env_is_closure or join_closure_env_is_closure_slot:
                        join_closure_env_cursor = join_closure_env_cursor + 2
                    else:
                        join_closure_env_cursor = join_closure_env_cursor + 1
                elif join_closure_env_atomic:
                    join_closure_body_word = red2_word_t(
                        lo=memory_out.p0.rd_data.lo,
                        hi=(memory_out.p0.rd_data.hi & 132644863) | 1048576,
                    )
                    microstate = MICRO_JOIN_CLOSURE_PREFLIGHT
                else:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
        elif micro_is_join_closure_preflight:
            # Match oracle ordering: validate/materialize the complete narrow
            # source first, then capacity-check before the first architectural
            # graph write.  Keep this subset out of overlapping source/destination
            # layouts because the generic oracle materializes into scratch first.
            join_closure_size17: uint17_t = join_closure_lambda_count + 1
            join_closure_last17: uint17_t = join_closure_destination + join_closure_size17 - 1
            join_closure_capacity_gap: uint17_t = free_space - join_closure_last17
            join_closure_capacity_wrapped: uint1_t = join_closure_capacity_gap[16]
            join_closure_capacity_nonzero: uint1_t = join_closure_capacity_gap != 0
            join_closure_capacity_ok: uint1_t = join_closure_capacity_wrapped == 0
            join_closure_capacity_ok = join_closure_capacity_ok and join_closure_capacity_nonzero
            join_closure_source_gap: uint16_t = fsp - join_closure_cursor
            join_closure_source_after_fsp: uint1_t = join_closure_source_gap[15]
            if not join_closure_capacity_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif join_closure_source_after_fsp:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            else:
                join_closure_write_index = 0
                join_closure_cursor = join_closure_code[15:0]
                microstate = MICRO_JOIN_CLOSURE_WRITE_LAMBDA
        elif micro_is_join_closure_write_lambda:
            # All source lambdas were validated before publication begins.  Read
            # one source word into scratch; the next state writes it to the graph.
            join_closure_lambda_word = red2_word_t(
                lo=memory_out.p0.rd_data.lo,
                hi=memory_out.p0.rd_data.hi & 132644863,
            )
            microstate = MICRO_JOIN_CLOSURE_WRITE_LAMBDA_COMMIT
        elif micro_is_join_closure_write_lambda_commit:
            join_closure_next_write_index: uint16_t = join_closure_write_index + 1
            join_closure_write_index = join_closure_next_write_index
            join_closure_cursor = join_closure_cursor + 1
            if join_closure_next_write_index == join_closure_lambda_count:
                microstate = MICRO_JOIN_CLOSURE_WRITE_BODY
            else:
                microstate = MICRO_JOIN_CLOSURE_WRITE_LAMBDA
        elif micro_is_join_closure_write_body:
            join_closure_new_fsp: uint16_t = join_closure_destination + join_closure_lambda_count
            fsp = join_closure_new_fsp
            join_needs_ep_cache = 0
            join_preserve_fsp = 1
            if join_ep_embedded:
                # PUB_GRAPH(join_app_shared_target) now returns a different root.
                # The EP descriptor itself remains untouched; PUB_APP_REWRITE
                # retargets each already-preflighted enclosing APP descriptor.
                join_app_cursor = join_result_address
                microstate = MICRO_JOIN_APP_REWRITE_READ
            else:
                join_published_root = join_closure_destination
                join_publish_word = red2_word_t(
                    lo=join_closure_destination,
                    hi=69337088,
                )
                microstate = MICRO_JOIN_PUBLISH
        elif micro_is_join_app_rewrite_read:
            # No validation/faults occur in this post-publication phase: every
            # slot was checked during MICRO_JOIN_APP_SCAN.  Only APP descriptors
            # target the materialized root; APP_VAR/non-head inline entries are
            # transparent and must remain byte-for-byte unchanged.
            join_app_rewrite_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_app_rewrite_is_app: uint1_t = join_app_rewrite_opcode == MOP_APP
            if join_app_rewrite_is_app:
                join_app_rewrite_word = red2_word_t(
                    lo=join_closure_destination,
                    hi=memory_out.p0.rd_data.hi,
                )
                microstate = MICRO_JOIN_APP_REWRITE_WRITE
            else:
                join_app_rewrite_next_cursor: uint16_t = join_app_cursor + 1
                join_app_cursor = join_app_rewrite_next_cursor
                if join_app_rewrite_next_cursor == join_app_operator_address:
                    join_publish_word = red2_word_t(
                        lo=join_result_address,
                        hi=69337088,
                    )
                    microstate = MICRO_JOIN_PUBLISH
                else:
                    microstate = MICRO_JOIN_APP_REWRITE_READ
        elif micro_is_join_app_rewrite_write:
            join_app_next_cursor: uint16_t = join_app_cursor + 1
            join_app_cursor = join_app_next_cursor
            if join_app_next_cursor == join_app_operator_address:
                join_publish_word = red2_word_t(
                    lo=join_result_address,
                    hi=69337088,
                )
                microstate = MICRO_JOIN_PUBLISH
            else:
                microstate = MICRO_JOIN_APP_REWRITE_READ
        elif micro_is_join_app_scan:
            join_app_cursor_in_range: uint1_t = join_app_cursor[15:GRAPH_ADDR_BITS] == 0
            join_app_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_app_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_app_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            join_app_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_app_is_app: uint1_t = join_app_opcode == MOP_APP
            join_app_is_app_var: uint1_t = join_app_opcode == MOP_APP_VAR
            join_app_is_int: uint1_t = join_app_opcode == MOP_INT
            join_app_is_float: uint1_t = join_app_opcode == MOP_FLOAT
            join_app_is_char: uint1_t = join_app_opcode == MOP_CHAR
            join_app_is_sym: uint1_t = join_app_opcode == MOP_SYM
            join_app_is_prim0: uint1_t = join_app_opcode == MOP_PRIM_0
            join_app_is_prim1: uint1_t = join_app_opcode == MOP_PRIM_1
            join_app_is_prim2: uint1_t = join_app_opcode == MOP_PRIM_2
            join_app_inline: uint1_t = join_app_is_int or join_app_is_float
            join_app_inline = join_app_inline or join_app_is_char
            join_app_inline = join_app_inline or join_app_is_sym
            join_app_inline = join_app_inline or join_app_is_prim0
            join_app_inline = join_app_inline or join_app_is_prim1
            join_app_inline = join_app_inline or join_app_is_prim2
            join_app_at_fsp: uint1_t = join_app_cursor == fsp
            if not join_app_cursor_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_app_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_app_is_app:
                join_app_descriptor_signed: uint1_t = join_app_kind == DATA_SIGNED
                join_app_descriptor_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                join_app_target_matches_first: uint1_t = memory_out.p0.rd_data.lo == join_app_shared_target
                join_app_target_matches_second: uint1_t = memory_out.p0.rd_data.lo == join_app_second_target
                if not join_app_descriptor_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_app_descriptor_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_app_at_fsp:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_app_target_matches_first:
                    join_app_cursor = join_app_cursor + 1
                elif join_app_has_second_target and join_app_target_matches_second:
                    join_app_cursor = join_app_cursor + 1
                elif not join_app_has_second_target:
                    # Bounded multi-target transaction: record one additional
                    # unique target, but do not publish either until both roots
                    # have been completely preflighted.
                    join_app_second_target = memory_out.p0.rd_data.lo
                    join_app_has_second_target = 1
                    join_app_cursor = join_app_cursor + 1
                else:
                    # A third unique target needs the generic publication stack.
                    # No graph publication writes have occurred at this point.
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
            elif join_app_is_app_var:
                # PUB_APP_SCAN treats APP_VAR as a transparent prefix entry.
                if join_app_at_fsp:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_app_cursor = join_app_cursor + 1
            elif not join_app_head and join_app_inline:
                # Non-head inline values are transparent application-prefix data.
                if join_app_at_fsp:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_app_cursor = join_app_cursor + 1
            elif join_app_head and join_app_inline:
                join_app_target_in_range: uint1_t = join_app_shared_target[63:GRAPH_ADDR_BITS] == 0
                if not join_app_target_in_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    # The entire narrow APP prefix is now validated.  Preserve
                    # its exclusive end so a closure publication that changes
                    # the target root can retarget every descriptor without any
                    # further fallible checks after graph publication begins.
                    join_app_operator_address = join_app_cursor
                    if join_app_has_second_target:
                        join_app_preflight_slot = 0
                        join_app_preflight_root = join_app_shared_target
                        join_app_first_write_needed = 0
                        join_app_second_write_needed = 0
                        microstate = MICRO_JOIN_MULTI_TARGET_READ
                    else:
                        microstate = MICRO_JOIN_APP_TARGET_READ
            else:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
        elif micro_is_join_app_target_read:
            join_app_target_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_app_target_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_app_target_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            join_app_target_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_app_target_is_ep: uint1_t = join_app_target_opcode == MOP_EP
            join_app_target_is_var: uint1_t = join_app_target_opcode == MOP_VAR
            join_app_target_is_ubv: uint1_t = join_app_target_opcode == MOP_UBV
            join_app_target_is_int: uint1_t = join_app_target_opcode == MOP_INT
            join_app_target_is_float: uint1_t = join_app_target_opcode == MOP_FLOAT
            join_app_target_is_char: uint1_t = join_app_target_opcode == MOP_CHAR
            join_app_target_is_sym: uint1_t = join_app_target_opcode == MOP_SYM
            join_app_target_is_prim0: uint1_t = join_app_target_opcode == MOP_PRIM_0
            join_app_target_is_prim1: uint1_t = join_app_target_opcode == MOP_PRIM_1
            join_app_target_is_prim2: uint1_t = join_app_target_opcode == MOP_PRIM_2
            join_app_target_inline: uint1_t = join_app_target_is_int or join_app_target_is_float
            join_app_target_inline = join_app_target_inline or join_app_target_is_char
            join_app_target_inline = join_app_target_inline or join_app_target_is_sym
            join_app_target_inline = join_app_target_inline or join_app_target_is_prim0
            join_app_target_inline = join_app_target_inline or join_app_target_is_prim1
            join_app_target_inline = join_app_target_inline or join_app_target_is_prim2
            join_app_target_head_inline: uint1_t = join_app_target_head and join_app_target_inline
            join_app_target_stable: uint1_t = join_app_target_head_inline or join_app_target_is_var
            join_app_target_stable = join_app_target_stable or join_app_target_is_ubv
            join_app_target_signed: uint1_t = join_app_target_kind == DATA_SIGNED
            join_app_target_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            if not join_app_target_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_app_target_stable:
                # PUB_GRAPH returns these roots unchanged.  The enclosing APP
                # descriptors already point at the correct published root.
                join_publish_word = red2_word_t(
                    lo=join_result_address,
                    hi=69337088,
                )
                join_needs_ep_cache = 0
                join_preserve_fsp = 1
                microstate = MICRO_JOIN_PUBLISH
            elif not join_app_target_is_ep:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            elif not join_app_target_signed:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_app_target_negative:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                join_ep_descriptor_address = join_app_shared_target[15:0]
                join_ep_descriptor_hi = memory_out.p0.rd_data.hi
                join_ep_chase_target = memory_out.p0.rd_data.lo
                join_ep_hops = 0
                join_ep_general_root = 1
                join_ep_embedded = 1
                join_publish_word = red2_word_t(
                    lo=join_result_address,
                    hi=69337088,
                )
                join_preserve_fsp = 1
                microstate = MICRO_JOIN_EP_CHASE
        elif micro_is_join_multi_target_read:
            join_multi_root_in_range: uint1_t = join_app_preflight_root[63:GRAPH_ADDR_BITS] == 0
            join_multi_root_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_multi_root_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_multi_root_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            join_multi_root_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_multi_root_is_ep: uint1_t = join_multi_root_opcode == MOP_EP
            join_multi_root_is_var: uint1_t = join_multi_root_opcode == MOP_VAR
            join_multi_root_is_ubv: uint1_t = join_multi_root_opcode == MOP_UBV
            join_multi_root_is_int: uint1_t = join_multi_root_opcode == MOP_INT
            join_multi_root_is_float: uint1_t = join_multi_root_opcode == MOP_FLOAT
            join_multi_root_is_char: uint1_t = join_multi_root_opcode == MOP_CHAR
            join_multi_root_is_sym: uint1_t = join_multi_root_opcode == MOP_SYM
            join_multi_root_is_prim0: uint1_t = join_multi_root_opcode == MOP_PRIM_0
            join_multi_root_is_prim1: uint1_t = join_multi_root_opcode == MOP_PRIM_1
            join_multi_root_is_prim2: uint1_t = join_multi_root_opcode == MOP_PRIM_2
            join_multi_root_inline: uint1_t = join_multi_root_is_int or join_multi_root_is_float
            join_multi_root_inline = join_multi_root_inline or join_multi_root_is_char
            join_multi_root_inline = join_multi_root_inline or join_multi_root_is_sym
            join_multi_root_inline = join_multi_root_inline or join_multi_root_is_prim0
            join_multi_root_inline = join_multi_root_inline or join_multi_root_is_prim1
            join_multi_root_inline = join_multi_root_inline or join_multi_root_is_prim2
            join_multi_root_head_inline: uint1_t = join_multi_root_head and join_multi_root_inline
            join_multi_root_stable: uint1_t = join_multi_root_head_inline or join_multi_root_is_var
            join_multi_root_stable = join_multi_root_stable or join_multi_root_is_ubv
            if not join_multi_root_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not join_multi_root_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_multi_root_stable:
                if join_app_preflight_slot:
                    join_app_second_write_needed = 0
                else:
                    join_app_first_write_needed = 0
                microstate = MICRO_JOIN_MULTI_TARGET_ADVANCE
            elif join_multi_root_is_ep:
                join_multi_root_signed: uint1_t = join_multi_root_kind == DATA_SIGNED
                join_multi_root_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                if not join_multi_root_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_multi_root_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_app_preflight_descriptor_hi = memory_out.p0.rd_data.hi
                    join_app_preflight_chase_target = memory_out.p0.rd_data.lo
                    join_app_preflight_hops = 0
                    microstate = MICRO_JOIN_MULTI_TARGET_CHASE
            else:
                # Allocating/nested publication belongs to the generic walker.
                # The transaction has not written either target yet.
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
        elif micro_is_join_multi_target_chase:
            join_multi_chase_in_range: uint1_t = join_app_preflight_chase_target[63:GRAPH_ADDR_BITS] == 0
            if not join_multi_chase_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                join_multi_target_valid: uint1_t = memory_out.p0.rd_data.hi[26]
                join_multi_target_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
                join_multi_target_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
                join_multi_target_defvalid: uint1_t = memory_out.p0.rd_data.hi[16]
                join_multi_target_is_ep: uint1_t = join_multi_target_opcode == MOP_EP
                if not join_multi_target_valid:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_multi_target_is_ep:
                    join_multi_next_signed: uint1_t = join_multi_target_kind == DATA_SIGNED
                    join_multi_next_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    join_multi_hops_at_limit: uint1_t = join_app_preflight_hops == GRAPH_WORDS - 1
                    if not join_multi_next_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_multi_next_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif join_multi_hops_at_limit:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
                    else:
                        join_app_preflight_chase_target = memory_out.p0.rd_data.lo
                        join_app_preflight_hops = join_app_preflight_hops + 1
                else:
                    join_multi_target17: uint17_t = join_app_preflight_chase_target[16:0]
                    join_multi_after_frontier_gap: uint17_t = join_multi_target17 - free_space
                    join_multi_after_frontier_wrapped: uint1_t = join_multi_after_frontier_gap[16]
                    join_multi_at_or_after_frontier: uint1_t = join_multi_after_frontier_wrapped == 0
                    join_multi_before_frame_gap: uint17_t = join_frame_free_space - join_multi_target17
                    join_multi_before_frame_wrapped: uint1_t = join_multi_before_frame_gap[16]
                    join_multi_before_frame_nonzero: uint1_t = join_multi_before_frame_gap != 0
                    join_multi_before_frame: uint1_t = join_multi_before_frame_wrapped == 0
                    join_multi_before_frame = join_multi_before_frame and join_multi_before_frame_nonzero
                    join_multi_inside_reclaim: uint1_t = join_multi_at_or_after_frontier and join_multi_before_frame
                    join_multi_is_int: uint1_t = join_multi_target_opcode == MOP_INT
                    join_multi_is_float: uint1_t = join_multi_target_opcode == MOP_FLOAT
                    join_multi_is_char: uint1_t = join_multi_target_opcode == MOP_CHAR
                    join_multi_is_sym: uint1_t = join_multi_target_opcode == MOP_SYM
                    join_multi_sym_shareable: uint1_t = join_multi_is_sym and not join_multi_target_defvalid
                    join_multi_atomic: uint1_t = join_multi_is_int or join_multi_is_float
                    join_multi_atomic = join_multi_atomic or join_multi_is_char
                    join_multi_atomic = join_multi_atomic or join_multi_sym_shareable
                    join_multi_is_ubv: uint1_t = join_multi_target_opcode == MOP_UBV
                    join_multi_is_closure: uint1_t = join_multi_target_opcode == MOP_CLOSURE
                    join_multi_is_rec: uint1_t = join_multi_target_opcode == MOP_REC
                    if not join_multi_inside_reclaim:
                        if join_app_preflight_slot:
                            join_app_second_write_needed = 0
                        else:
                            join_app_first_write_needed = 0
                        microstate = MICRO_JOIN_MULTI_TARGET_ADVANCE
                    elif join_multi_atomic:
                        join_multi_descriptor_head: uint64_t = join_app_preflight_descriptor_hi & 1048576
                        join_multi_atomic_hi: uint64_t = memory_out.p0.rd_data.hi & 132644863
                        join_multi_atomic_hi = join_multi_atomic_hi | join_multi_descriptor_head
                        if join_app_preflight_slot:
                            join_app_second_write_needed = 1
                            join_app_second_write_word = red2_word_t(
                                lo=memory_out.p0.rd_data.lo, hi=join_multi_atomic_hi
                            )
                        else:
                            join_app_first_write_needed = 1
                            join_app_first_write_word = red2_word_t(
                                lo=memory_out.p0.rd_data.lo, hi=join_multi_atomic_hi
                            )
                        microstate = MICRO_JOIN_MULTI_TARGET_ADVANCE
                    elif join_multi_is_ubv:
                        join_multi_ubv_signed: uint1_t = join_multi_target_kind == DATA_SIGNED
                        join_multi_phi_wide: uint64_t = phi
                        join_multi_ubv_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                        join_multi_ubv_index: uint64_t = join_multi_phi_wide - memory_out.p0.rd_data.lo
                        if join_multi_ubv_negative:
                            join_multi_ubv_magnitude: uint64_t = 0 - memory_out.p0.rd_data.lo
                            join_multi_ubv_index = join_multi_phi_wide + join_multi_ubv_magnitude
                        join_multi_ubv_index_negative: uint1_t = join_multi_ubv_index[63]
                        if not join_multi_ubv_signed:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not join_multi_ubv_negative and join_multi_ubv_index_negative:
                            red2_fault = FAULT_ILLEGAL_TRANSITION
                            microstate = MICRO_FAULT
                        else:
                            join_multi_descriptor_definition: uint64_t = join_app_preflight_descriptor_hi & 131071
                            join_multi_descriptor_head: uint64_t = join_app_preflight_descriptor_hi & 1048576
                            join_multi_var_hi: uint64_t = 111280128 | join_multi_descriptor_head
                            join_multi_var_hi = join_multi_var_hi | join_multi_descriptor_definition
                            if join_app_preflight_slot:
                                join_app_second_write_needed = 1
                                join_app_second_write_word = red2_word_t(
                                    lo=join_multi_ubv_index, hi=join_multi_var_hi
                                )
                            else:
                                join_app_first_write_needed = 1
                                join_app_first_write_word = red2_word_t(
                                    lo=join_multi_ubv_index, hi=join_multi_var_hi
                                )
                            microstate = MICRO_JOIN_MULTI_TARGET_ADVANCE
                    elif join_multi_is_closure or join_multi_is_rec:
                        # Allocation/reconstruction cannot join this bounded
                        # no-write-before-preflight transaction yet.
                        hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                        microstate = MICRO_FAULT
                    else:
                        red2_fault = FAULT_ILLEGAL_TRANSITION
                        microstate = MICRO_FAULT
        elif micro_is_join_multi_target_advance:
            if not join_app_preflight_slot:
                join_app_preflight_slot = 1
                join_app_preflight_root = join_app_second_target
                microstate = MICRO_JOIN_MULTI_TARGET_READ
            elif join_app_first_write_needed:
                microstate = MICRO_JOIN_MULTI_TARGET_WRITE_FIRST
            elif join_app_second_write_needed:
                microstate = MICRO_JOIN_MULTI_TARGET_WRITE_SECOND
            else:
                join_publish_word = red2_word_t(
                    lo=join_result_address, hi=69337088
                )
                join_needs_ep_cache = 0
                join_preserve_fsp = 1
                microstate = MICRO_JOIN_PUBLISH
        elif micro_is_join_multi_target_write_first:
            if join_app_second_write_needed:
                microstate = MICRO_JOIN_MULTI_TARGET_WRITE_SECOND
            else:
                join_publish_word = red2_word_t(
                    lo=join_result_address, hi=69337088
                )
                join_needs_ep_cache = 0
                join_preserve_fsp = 1
                microstate = MICRO_JOIN_PUBLISH
        elif micro_is_join_multi_target_write_second:
            join_publish_word = red2_word_t(
                lo=join_result_address, hi=69337088
            )
            join_needs_ep_cache = 0
            join_preserve_fsp = 1
            microstate = MICRO_JOIN_PUBLISH
        elif micro_is_join_recp_rblock_scan:
            join_recp_scan_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_recp_scan_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_recp_scan_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            if not join_recp_scan_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_recp_scan_opcode == MOP_RBLOCK:
                join_recp_binding_signed: uint1_t = join_recp_scan_kind == DATA_SIGNED
                join_recp_binding_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                join_recp_binding_plus_one: uint64_t = memory_out.p0.rd_data.lo + 1
                join_recp_binding_in_range: uint1_t = join_recp_binding_plus_one[63:GRAPH_ADDR_BITS] == 0
                if not join_recp_binding_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_recp_binding_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not join_recp_binding_in_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_recp_binding_root = join_recp_binding_plus_one[15:0]
                    microstate = MICRO_JOIN_RECP_RBLOCK_BINDING_READ
            else:
                join_recp_rup_signed: uint1_t = join_recp_scan_kind == DATA_SIGNED
                join_recp_rup_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                join_recp_rup_count_wide: uint64_t = join_recp_rblock_count
                join_recp_rup_count_match: uint1_t = memory_out.p0.rd_data.lo == join_recp_rup_count_wide
                join_recp_body_wide: uint17_t = join_recp_rblock_cursor + 1
                join_recp_body_in_range: uint1_t = join_recp_body_wide[16:GRAPH_ADDR_BITS] == 0
                if join_recp_scan_opcode != MOP_RUP:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif not join_recp_rup_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif join_recp_rup_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif not join_recp_rup_count_match:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif not join_recp_body_in_range:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_recp_rblock_cursor = join_recp_body_wide[15:0]
                    microstate = MICRO_JOIN_RECP_RBLOCK_BODY_READ
        elif micro_is_join_recp_rblock_binding_read:
            join_recp_binding_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_recp_binding_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_recp_binding_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_recp_binding_is_int: uint1_t = join_recp_binding_opcode == MOP_INT
            join_recp_binding_is_float: uint1_t = join_recp_binding_opcode == MOP_FLOAT
            join_recp_binding_is_char: uint1_t = join_recp_binding_opcode == MOP_CHAR
            join_recp_binding_is_sym: uint1_t = join_recp_binding_opcode == MOP_SYM
            join_recp_binding_is_prim0: uint1_t = join_recp_binding_opcode == MOP_PRIM_0
            join_recp_binding_is_prim1: uint1_t = join_recp_binding_opcode == MOP_PRIM_1
            join_recp_binding_is_prim2: uint1_t = join_recp_binding_opcode == MOP_PRIM_2
            join_recp_binding_inline: uint1_t = join_recp_binding_is_int or join_recp_binding_is_float
            join_recp_binding_inline = join_recp_binding_inline or join_recp_binding_is_char
            join_recp_binding_inline = join_recp_binding_inline or join_recp_binding_is_sym
            join_recp_binding_inline = join_recp_binding_inline or join_recp_binding_is_prim0
            join_recp_binding_inline = join_recp_binding_inline or join_recp_binding_is_prim1
            join_recp_binding_inline = join_recp_binding_inline or join_recp_binding_is_prim2
            join_recp_binding_prefix_inline: uint1_t = join_recp_binding_inline and not join_recp_binding_head
            join_recp_binding_composite: uint1_t = join_recp_binding_opcode == MOP_EP
            join_recp_binding_composite = join_recp_binding_composite or join_recp_binding_opcode == MOP_APP
            join_recp_binding_composite = join_recp_binding_composite or join_recp_binding_opcode == MOP_APP_VAR
            join_recp_binding_composite = join_recp_binding_composite or join_recp_binding_prefix_inline
            join_recp_binding_composite = join_recp_binding_composite or join_recp_binding_opcode == MOP_LAMBDA
            join_recp_binding_composite = join_recp_binding_composite or join_recp_binding_opcode == MOP_RBLOCK
            join_recp_binding_composite = join_recp_binding_composite or join_recp_binding_opcode == MOP_STRUCT
            if not join_recp_binding_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_recp_binding_composite:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            else:
                join_recp_rblock_cursor = join_recp_rblock_cursor + 1
                join_recp_rblock_count = join_recp_rblock_count + 1
                microstate = MICRO_JOIN_RECP_RBLOCK_SCAN
        elif micro_is_join_recp_rblock_body_read:
            join_recp_body_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_recp_body_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_recp_body_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_recp_body_is_int: uint1_t = join_recp_body_opcode == MOP_INT
            join_recp_body_is_float: uint1_t = join_recp_body_opcode == MOP_FLOAT
            join_recp_body_is_char: uint1_t = join_recp_body_opcode == MOP_CHAR
            join_recp_body_is_sym: uint1_t = join_recp_body_opcode == MOP_SYM
            join_recp_body_is_prim0: uint1_t = join_recp_body_opcode == MOP_PRIM_0
            join_recp_body_is_prim1: uint1_t = join_recp_body_opcode == MOP_PRIM_1
            join_recp_body_is_prim2: uint1_t = join_recp_body_opcode == MOP_PRIM_2
            join_recp_body_inline: uint1_t = join_recp_body_is_int or join_recp_body_is_float
            join_recp_body_inline = join_recp_body_inline or join_recp_body_is_char
            join_recp_body_inline = join_recp_body_inline or join_recp_body_is_sym
            join_recp_body_inline = join_recp_body_inline or join_recp_body_is_prim0
            join_recp_body_inline = join_recp_body_inline or join_recp_body_is_prim1
            join_recp_body_inline = join_recp_body_inline or join_recp_body_is_prim2
            join_recp_body_prefix_inline: uint1_t = join_recp_body_inline and not join_recp_body_head
            join_recp_body_composite: uint1_t = join_recp_body_opcode == MOP_EP
            join_recp_body_composite = join_recp_body_composite or join_recp_body_opcode == MOP_APP
            join_recp_body_composite = join_recp_body_composite or join_recp_body_opcode == MOP_APP_VAR
            join_recp_body_composite = join_recp_body_composite or join_recp_body_prefix_inline
            join_recp_body_composite = join_recp_body_composite or join_recp_body_opcode == MOP_LAMBDA
            join_recp_body_composite = join_recp_body_composite or join_recp_body_opcode == MOP_RBLOCK
            join_recp_body_composite = join_recp_body_composite or join_recp_body_opcode == MOP_STRUCT
            if not join_recp_body_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_recp_body_composite:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            else:
                join_published_root = join_result_address
                join_publish_word = red2_word_t(lo=join_result_address, hi=69337088)
                join_needs_ep_cache = 0
                join_preserve_fsp = 1
                microstate = MICRO_JOIN_PUBLISH
        elif micro_is_join_flat_scan:
            join_flat_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            join_flat_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            join_flat_head: uint1_t = memory_out.p0.rd_data.hi[20]
            join_flat_is_app_var: uint1_t = join_flat_opcode == MOP_APP_VAR
            join_flat_is_int: uint1_t = join_flat_opcode == MOP_INT
            join_flat_is_float: uint1_t = join_flat_opcode == MOP_FLOAT
            join_flat_is_char: uint1_t = join_flat_opcode == MOP_CHAR
            join_flat_is_sym: uint1_t = join_flat_opcode == MOP_SYM
            join_flat_is_prim0: uint1_t = join_flat_opcode == MOP_PRIM_0
            join_flat_is_prim1: uint1_t = join_flat_opcode == MOP_PRIM_1
            join_flat_is_prim2: uint1_t = join_flat_opcode == MOP_PRIM_2
            join_flat_inline: uint1_t = join_flat_is_int or join_flat_is_float
            join_flat_inline = join_flat_inline or join_flat_is_char
            join_flat_inline = join_flat_inline or join_flat_is_sym
            join_flat_inline = join_flat_inline or join_flat_is_prim0
            join_flat_inline = join_flat_inline or join_flat_is_prim1
            join_flat_inline = join_flat_inline or join_flat_is_prim2
            join_flat_at_fsp: uint1_t = join_flat_cursor == fsp
            if not join_flat_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif join_flat_is_app_var:
                if join_flat_at_fsp:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    join_flat_cursor = join_flat_cursor + 1
            elif not join_flat_inline:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            elif join_flat_head:
                join_flat_parent_hi: uint64_t = 69337088
                join_publish_word = red2_word_t(
                    lo=join_result_address,
                    hi=join_flat_parent_hi,
                )
                join_needs_ep_cache = 0
                join_preserve_fsp = 1
                microstate = MICRO_JOIN_PUBLISH
            elif join_flat_at_fsp:
                hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                microstate = MICRO_FAULT
            else:
                join_flat_cursor = join_flat_cursor + 1
        elif micro_is_closure_read:
            closure_code_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            closure_code_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            closure_code_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            closure_code_is_none: uint1_t = closure_code_opcode == MOP_NONE
            closure_code_signed: uint1_t = closure_code_kind == DATA_SIGNED
            closure_code_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            closure_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            closure_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            closure_free_end: uint1_t = free_space == GRAPH_WORDS
            closure_free_valid: uint1_t = closure_free_low or closure_free_end
            closure_layout_gap: uint17_t = free_space - fsp
            closure_layout_wrapped: uint1_t = closure_layout_gap[16]
            closure_layout_nonzero: uint1_t = closure_layout_gap != 0
            closure_layout_not_wrapped: uint1_t = closure_layout_wrapped == 0
            closure_layout_ok: uint1_t = closure_layout_not_wrapped and closure_layout_nonzero
            closure_parent_low: uint1_t = fetched_word.lo[63:8] == 0
            closure_parent_end: uint1_t = fetched_word.lo == GRAPH_WORDS
            closure_parent_valid: uint1_t = closure_parent_low or closure_parent_end
            closure_marker_address: uint17_t = free_space - 1
            closure_marker_gap: uint17_t = closure_marker_address - fsp
            closure_marker_wrapped: uint1_t = closure_marker_gap[16]
            closure_marker_nonzero: uint1_t = closure_marker_gap != 0
            closure_marker_not_wrapped: uint1_t = closure_marker_wrapped == 0
            closure_marker_after_fsp: uint1_t = closure_marker_not_wrapped and closure_marker_nonzero
            if not closure_code_valid:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif not closure_code_is_none:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif not closure_code_signed:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif closure_code_negative:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not closure_fsp_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not closure_free_valid:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not closure_layout_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not closure_parent_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not closure_marker_after_fsp:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            else:
                closure_target = memory_out.p0.rd_data.lo[15:0]
                microstate = MICRO_CLOSURE_MARKER
        elif micro_is_closure_marker:
            closure_new_env: uint17_t = free_space - 1
            env = closure_new_env
            free_space = closure_new_env
            pc = closure_target
            microstate = MICRO_COMMIT
        elif micro_is_rup_validate_rec:
            rup_exec_index64: uint64_t = rup_index
            rup_exec_env64: uint64_t = env
            rup_exec_stride64: uint64_t = rup_exec_index64 + rup_exec_index64
            rup_exec_stride64 = rup_exec_stride64 + rup_exec_index64
            rup_exec_rec64: uint64_t = rup_exec_env64 + rup_exec_stride64
            rup_exec_rec_end64: uint64_t = rup_exec_rec64 + 2
            rup_rec_range_bad: uint1_t = rup_exec_rec64[63:GRAPH_ADDR_BITS] != 0
            rup_rec_end_bad: uint1_t = rup_exec_rec_end64[63:GRAPH_ADDR_BITS] != 0
            rup_rec_address_bad: uint1_t = rup_rec_range_bad or rup_rec_end_bad
            rup_source_offset_exec: uint16_t = rup_count - 1 - rup_index
            rup_source17_exec: uint17_t = rup_block + rup_source_offset_exec
            rup_source_range_bad: uint1_t = rup_source17_exec[16:GRAPH_ADDR_BITS] != 0
            rup_rec_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            rup_rec_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            rup_rec_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            rup_rec_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            rup_rec_missing: uint1_t = rup_rec_valid == 0
            rup_rec_wrong_opcode: uint1_t = rup_rec_opcode != MOP_REC
            rup_rec_shape_bad: uint1_t = rup_rec_missing or rup_rec_wrong_opcode
            rup_rec_kind_bad: uint1_t = rup_rec_kind != DATA_SIGNED
            rup_rec_payload_bad_now: uint1_t = rup_rec_kind_bad or rup_rec_negative
            if rup_rec_address_bad:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif rup_source_range_bad:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif rup_rec_shape_bad:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                # The bounded RUP scan checks context/block/source structure
                # before interpreting either binding payload as signed data.
                rup_rec_binding = memory_out.p0.rd_data.lo
                rup_rec_payload_bad = rup_rec_payload_bad_now
                microstate = MICRO_RUP_VALIDATE_CONTEXT
        elif micro_is_rup_validate_context:
            rup_context_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            rup_context_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            if not rup_context_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif rup_context_opcode != MOP_NONE:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                microstate = MICRO_RUP_VALIDATE_BLOCK
        elif micro_is_rup_validate_block:
            rup_block_slot_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            rup_block_slot_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            if not rup_block_slot_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif rup_block_slot_opcode != MOP_NONE:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                microstate = MICRO_RUP_VALIDATE_SOURCE
        elif micro_is_rup_validate_source:
            rup_source_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            rup_source_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            rup_source_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            rup_source_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            rup_source_missing: uint1_t = rup_source_valid == 0
            rup_source_wrong_opcode: uint1_t = rup_source_opcode != MOP_RBLOCK
            rup_source_shape_bad: uint1_t = rup_source_missing or rup_source_wrong_opcode
            rup_source_kind_bad: uint1_t = rup_source_kind != DATA_SIGNED
            rup_source_data_bad: uint1_t = rup_source_kind_bad or rup_source_negative
            rup_binding_data_bad: uint1_t = rup_rec_payload_bad or rup_source_data_bad
            rup_source_plus_one: uint64_t = memory_out.p0.rd_data.lo + 1
            if rup_source_shape_bad:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif rup_binding_data_bad:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif rup_rec_binding != rup_source_plus_one:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                rup_next_validate_index: uint16_t = rup_index + 1
                if rup_next_validate_index == rup_count:
                    rup_index = 0
                    microstate = MICRO_RUP_WRITE_CONTEXT
                else:
                    rup_index = rup_next_validate_index
                    microstate = MICRO_RUP_VALIDATE_REC
        elif micro_is_rup_write_context:
            microstate = MICRO_RUP_WRITE_BLOCK
        elif micro_is_rup_write_block:
            rup_next_write_index: uint16_t = rup_index + 1
            if rup_next_write_index == rup_count:
                rup_index = 0
                pc = pc + 1
                microstate = MICRO_COMMIT
            else:
                rup_index = rup_next_write_index
                microstate = MICRO_RUP_WRITE_CONTEXT
        elif micro_is_rup_zero_push:
            control_top = control_top + 1
            rup_next_push_index: uint16_t = rup_index + 1
            if rup_next_push_index == rup_count:
                rup_index = 0
                microstate = MICRO_RUP_ZERO_RESULT
            else:
                rup_index = rup_next_push_index
        elif micro_is_rup_zero_result:
            fsp = fsp + 1
            argcnt = argcnt + 1
            pc = pc + 1
            rup_index = 0
            microstate = MICRO_COMMIT
        elif micro_is_recp_validate_rec:
            recp_rec_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            recp_rec_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            recp_rec_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            recp_rec_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            recp_rec_opcode_bad: uint1_t = recp_rec_opcode != MOP_REC
            recp_rec_kind_bad: uint1_t = recp_rec_kind != DATA_SIGNED
            if not recp_rec_valid:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif recp_rec_opcode_bad:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif recp_rec_kind_bad:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif recp_rec_negative:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                recp_binding = memory_out.p0.rd_data.lo
                microstate = MICRO_RECP_VALIDATE_CONTEXT
        elif micro_is_recp_validate_context:
            recp_context_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            recp_context_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            recp_context_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            if not recp_context_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif recp_context_opcode != MOP_NONE:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif recp_context_kind != DATA_SIGNED:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                recp_context = memory_out.p0.rd_data.lo
                microstate = MICRO_RECP_VALIDATE_BLOCK
        elif micro_is_recp_validate_block:
            recp_block_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            recp_block_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            recp_block_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            recp_forward_now: uint1_t = direction == DIRECTION_FORWARD
            recp_nonhead_now: uint1_t = fetched_word.hi[20] == 0
            recp_forward_nonhead: uint1_t = recp_forward_now and recp_nonhead_now
            if not recp_block_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif recp_block_opcode != MOP_NONE:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif recp_block_kind != DATA_SIGNED:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            else:
                recp_block = memory_out.p0.rd_data.lo
                if recp_forward_nonhead:
                    recp_copy_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    recp_copy_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    recp_copy_free_end: uint1_t = free_space == GRAPH_WORDS
                    recp_copy_free_valid: uint1_t = recp_copy_free_low or recp_copy_free_end
                    recp_copy_destination: uint17_t = fsp + 1
                    recp_copy_gap: uint17_t = free_space - recp_copy_destination
                    recp_copy_wrapped: uint1_t = recp_copy_gap[16]
                    recp_copy_nonzero: uint1_t = recp_copy_gap != 0
                    recp_copy_ok: uint1_t = recp_copy_wrapped == 0
                    recp_copy_ok = recp_copy_ok and recp_copy_nonzero
                    if not recp_copy_fsp_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not recp_copy_free_valid:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not recp_copy_ok:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        microstate = MICRO_RECP_ACTION
                elif q == 0:
                    if recp_forward_now:
                        recp_count = 0
                        recp_index = 0
                        recp_selected = 0
                        recp_replacement = 0
                        recp_parent_environment = 0
                        recp_copy_word = red2_word_t(lo=0, hi=0)
                        recp_rup_word = red2_word_t(lo=0, hi=0)
                        microstate = MICRO_RECP_RECON_SCAN
                    else:
                        # Reverse q=0 performs _enter_subgraph transactionally before
                        # reconstruction.  Match its fault order, but publish none of
                        # bridge/frame/JOIN until the reconstruction has also validated.
                        recp_reverse_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                        recp_reverse_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                        recp_reverse_free_end: uint1_t = free_space == GRAPH_WORDS
                        recp_reverse_free_valid: uint1_t = recp_reverse_free_low or recp_reverse_free_end
                        recp_reverse_layout_gap: uint17_t = free_space - fsp
                        recp_reverse_layout_wrapped: uint1_t = recp_reverse_layout_gap[16]
                        recp_reverse_layout_nonzero: uint1_t = recp_reverse_layout_gap != 0
                        recp_reverse_layout_ok: uint1_t = recp_reverse_layout_wrapped == 0
                        recp_reverse_layout_ok = recp_reverse_layout_ok and recp_reverse_layout_nonzero
                        recp_reverse_env_low: uint1_t = env[16:GRAPH_ADDR_BITS] == 0
                        recp_reverse_env_end: uint1_t = env == GRAPH_WORDS
                        recp_reverse_env_valid: uint1_t = recp_reverse_env_low or recp_reverse_env_end
                        recp_reverse_bridge_now: uint1_t = env != free_space
                        recp_reverse_normalized: uint17_t = env
                        if recp_reverse_bridge_now:
                            recp_reverse_normalized = free_space - 1
                        recp_reverse_join_address: uint17_t = fsp + 1
                        recp_reverse_join_gap: uint17_t = recp_reverse_normalized - recp_reverse_join_address
                        recp_reverse_join_wrapped: uint1_t = recp_reverse_join_gap[16]
                        recp_reverse_join_nonzero: uint1_t = recp_reverse_join_gap != 0
                        recp_reverse_join_ok: uint1_t = recp_reverse_join_wrapped == 0
                        recp_reverse_join_ok = recp_reverse_join_ok and recp_reverse_join_nonzero
                        recp_reverse_control_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
                        recp_reverse_control_end: uint1_t = control_top == CONTROL_WORDS
                        recp_reverse_control_valid: uint1_t = recp_reverse_control_low or recp_reverse_control_end
                        if not recp_reverse_fsp_valid:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not recp_reverse_free_valid:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        elif not recp_reverse_layout_ok:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        elif not recp_reverse_env_valid:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not recp_reverse_join_ok:
                            red2_fault = FAULT_GRAPH_ENV_COLLISION
                            microstate = MICRO_FAULT
                        elif not recp_reverse_control_valid:
                            red2_fault = FAULT_INVALID_ADDRESS
                            microstate = MICRO_FAULT
                        elif not recp_reverse_control_low:
                            red2_fault = FAULT_CONTROL_OVERFLOW
                            microstate = MICRO_FAULT
                        else:
                            recp_count = 0
                            recp_index = 0
                            recp_selected = 0
                            recp_replacement = 0
                            recp_parent_environment = 0
                            recp_copy_word = red2_word_t(lo=0, hi=0)
                            recp_rup_word = red2_word_t(lo=0, hi=0)
                            recp_reverse_zero = 1
                            recp_reverse_needs_bridge = recp_reverse_bridge_now
                            recp_reverse_parent_env = env
                            recp_reverse_entry_env = recp_reverse_normalized
                            microstate = MICRO_RECP_RECON_SCAN
                elif recp_forward_now:
                    recp_context_negative: uint1_t = recp_context[63]
                    recp_context_upper_nonzero: uint1_t = recp_context[62:GRAPH_ADDR_BITS] != 0
                    recp_fsp_valid: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
                    recp_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
                    recp_free_end: uint1_t = free_space == GRAPH_WORDS
                    recp_free_valid: uint1_t = recp_free_low or recp_free_end
                    recp_marker_address: uint17_t = free_space - 1
                    recp_marker_gap: uint17_t = recp_marker_address - fsp
                    recp_marker_wrapped: uint1_t = recp_marker_gap[16]
                    recp_marker_nonzero: uint1_t = recp_marker_gap != 0
                    recp_marker_after_fsp: uint1_t = recp_marker_wrapped == 0
                    recp_marker_after_fsp = recp_marker_after_fsp and recp_marker_nonzero
                    if recp_context_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif recp_context_upper_nonzero:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not recp_fsp_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not recp_free_valid:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    elif not recp_marker_after_fsp:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        microstate = MICRO_RECP_ACTION
                else:
                    recp_context_negative: uint1_t = recp_context[63]
                    recp_context_upper_nonzero: uint1_t = recp_context[62:32] != 0
                    recp_control_low: uint1_t = control_top[16:CONTROL_ADDR_BITS] == 0
                    recp_control_end: uint1_t = control_top == CONTROL_WORDS
                    recp_control_valid: uint1_t = recp_control_low or recp_control_end
                    if recp_context_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif recp_context_upper_nonzero:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not recp_control_valid:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not recp_control_low:
                        red2_fault = FAULT_CONTROL_OVERFLOW
                        microstate = MICRO_FAULT
                    else:
                        microstate = MICRO_RECP_ACTION
        elif micro_is_recp_recon_scan:
            recp_scan_count64: uint64_t = recp_count
            recp_scan_address64: uint64_t = recp_block + recp_scan_count64
            recp_scan_address_bad: uint1_t = recp_scan_address64[63:GRAPH_ADDR_BITS] != 0
            recp_scan_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            recp_scan_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            recp_scan_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            recp_scan_negative: uint1_t = memory_out.p0.rd_data.lo[63]
            recp_scan_is_rblock: uint1_t = recp_scan_opcode == MOP_RBLOCK
            recp_scan_is_rup: uint1_t = recp_scan_opcode == MOP_RUP
            if recp_scan_address_bad:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not recp_scan_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif recp_scan_is_rblock:
                recp_scan_payload_bad: uint1_t = recp_scan_kind != DATA_SIGNED
                recp_scan_payload_bad = recp_scan_payload_bad or recp_scan_negative
                recp_next_count: uint16_t = recp_count + 1
                if recp_scan_payload_bad:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_next_count[15:GRAPH_ADDR_BITS] != 0:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                else:
                    recp_count = recp_next_count
            elif recp_count == 0:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                recp_rup_count_match: uint1_t = recp_scan_kind == DATA_SIGNED
                recp_rup_count_match = recp_rup_count_match and recp_scan_is_rup
                recp_rup_count_match = recp_rup_count_match and (memory_out.p0.rd_data.lo == recp_count)
                recp_address64: uint64_t = fetched_word.lo
                recp_context_negative_scan: uint1_t = recp_context[63]
                recp_context_upper_scan: uint1_t = recp_context[62:GRAPH_ADDR_BITS] != 0
                recp_selected_delta64: uint64_t = recp_address64 - recp_context
                recp_selected_ge_context: uint1_t = red2_u64_ge(recp_address64, recp_context)
                recp_selected_wrapped: uint1_t = recp_selected_ge_context == 0
                recp_selected_div: red2_u64_divmod_t = red2_u64_divmod(recp_selected_delta64, 3)
                recp_selected_remainder_bad: uint1_t = recp_selected_div.r != 0
                recp_selected_upper_bad: uint1_t = recp_selected_div.q[63:16] != 0
                recp_selected16: uint16_t = recp_selected_div.q[15:0]
                recp_selected_outside: uint1_t = red2_u64_ge(recp_selected_div.q, recp_count)
                if not recp_rup_count_match:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                elif recp_context_negative_scan:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_context_upper_scan:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_selected_wrapped:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_selected_remainder_bad:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_selected_upper_bad:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif recp_selected_outside:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                else:
                    recp_selected = recp_selected16
                    microstate = MICRO_RECP_RECON_PREFLIGHT
        elif micro_is_recp_recon_preflight:
            recp_count17: uint17_t = recp_count
            recp_count64: uint64_t = recp_count
            recp_parent64: uint64_t = recp_context + recp_count64 + recp_count64 + recp_count64
            recp_parent_low: uint1_t = recp_parent64[63:17] == 0
            recp_parent17: uint17_t = recp_parent64[16:0]
            recp_parent_end: uint1_t = recp_parent17 == GRAPH_WORDS
            recp_parent_address: uint1_t = recp_parent17[16:GRAPH_ADDR_BITS] == 0
            recp_parent_valid: uint1_t = recp_parent_low and (recp_parent_address or recp_parent_end)
            recp_base_fsp: uint17_t = fsp
            recp_base_free: uint17_t = free_space
            recp_base_control: uint17_t = control_top
            if recp_reverse_zero:
                recp_base_fsp = fsp + 1
                recp_base_free = recp_reverse_entry_env
                recp_base_control = control_top + 1
            recp_fsp_valid_pre: uint1_t = recp_base_fsp[16:GRAPH_ADDR_BITS] == 0
            recp_free_low_pre: uint1_t = recp_base_free[16:GRAPH_ADDR_BITS] == 0
            recp_free_end_pre: uint1_t = recp_base_free == GRAPH_WORDS
            recp_free_valid_pre: uint1_t = recp_free_low_pre or recp_free_end_pre
            recp_env_words: uint17_t = recp_count17 + 1
            recp_env_base: uint17_t = recp_base_free - recp_env_words
            recp_env_gap: uint17_t = recp_env_base - recp_base_fsp
            recp_env_wrapped: uint1_t = recp_env_gap[16]
            recp_env_nonzero: uint1_t = recp_env_gap != 0
            recp_env_space_ok: uint1_t = recp_env_wrapped == 0
            recp_env_space_ok = recp_env_space_ok and recp_env_nonzero
            recp_copy_end: uint17_t = recp_base_fsp + recp_count17
            recp_copy_gap: uint17_t = recp_env_base - recp_copy_end
            recp_copy_wrapped: uint1_t = recp_copy_gap[16]
            recp_copy_nonzero: uint1_t = recp_copy_gap != 0
            recp_copy_space_ok: uint1_t = recp_copy_wrapped == 0
            recp_copy_space_ok = recp_copy_space_ok and recp_copy_nonzero
            recp_control_low_pre: uint1_t = recp_base_control[16:CONTROL_ADDR_BITS] == 0
            recp_control_end_pre: uint1_t = recp_base_control == CONTROL_WORDS
            recp_control_valid_pre: uint1_t = recp_control_low_pre or recp_control_end_pre
            recp_control_room: uint17_t = CONTROL_WORDS - recp_base_control
            recp_control_gap: uint17_t = recp_control_room - recp_count17
            recp_control_wrapped: uint1_t = recp_control_gap[16]
            recp_control_room_ok: uint1_t = recp_control_wrapped == 0
            recp_finish_end: uint17_t = recp_copy_end + 2
            recp_finish_gap: uint17_t = recp_env_base - recp_finish_end
            recp_finish_wrapped: uint1_t = recp_finish_gap[16]
            recp_finish_nonzero: uint1_t = recp_finish_gap != 0
            recp_finish_space_ok: uint1_t = recp_finish_wrapped == 0
            recp_finish_space_ok = recp_finish_space_ok and recp_finish_nonzero
            if not recp_fsp_valid_pre:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not recp_free_valid_pre:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not recp_parent_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not recp_env_space_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not recp_copy_space_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            elif not recp_control_valid_pre:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not recp_control_room_ok:
                red2_fault = FAULT_CONTROL_OVERFLOW
                microstate = MICRO_FAULT
            elif not recp_finish_space_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            else:
                recp_parent_environment = recp_parent17
                recp_index = 0
                if recp_reverse_zero:
                    if recp_reverse_needs_bridge:
                        microstate = MICRO_RECP_REVERSE_BRIDGE
                    else:
                        microstate = MICRO_RECP_REVERSE_FRAME
                else:
                    microstate = MICRO_RECP_RECON_MARKER
        elif micro_is_recp_reverse_bridge:
            microstate = MICRO_RECP_REVERSE_FRAME
        elif micro_is_recp_reverse_frame:
            microstate = MICRO_RECP_REVERSE_JOIN
        elif micro_is_recp_reverse_join:
            env = recp_reverse_entry_env
            free_space = recp_reverse_entry_env
            control_top = control_top + 1
            fsp = fsp + 1
            argcnt = 1
            prim_id = 0
            fire = 0
            recp_reverse_zero = 0
            recp_reverse_needs_bridge = 0
            recp_index = 0
            microstate = MICRO_RECP_RECON_MARKER
        elif micro_is_recp_recon_marker:
            recp_marker_new_env: uint17_t = free_space - 1
            env = recp_marker_new_env
            free_space = recp_marker_new_env
            recp_index = 0
            microstate = MICRO_RECP_RECON_UBV
        elif micro_is_recp_recon_ubv:
            recp_ubv_new_env: uint17_t = free_space - 1
            phi = phi + 1
            env = recp_ubv_new_env
            free_space = recp_ubv_new_env
            recp_next_ubv_index: uint16_t = recp_index + 1
            if recp_next_ubv_index == recp_count:
                recp_replacement = recp_ubv_new_env
                recp_index = 0
                microstate = MICRO_RECP_RECON_COPY_READ
            else:
                recp_index = recp_next_ubv_index
        elif micro_is_recp_recon_copy_read:
            recp_copy_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            recp_copy_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            if not recp_copy_valid:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            elif recp_copy_opcode != MOP_RBLOCK:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
            else:
                recp_copy_word = memory_out.p0.rd_data
                microstate = MICRO_RECP_RECON_COPY_WRITE
        elif micro_is_recp_recon_copy_write:
            fsp = fsp + 1
            argcnt = argcnt + 1
            recp_next_copy_index: uint16_t = recp_index + 1
            if recp_next_copy_index == recp_count:
                recp_index = 0
                microstate = MICRO_RECP_RECON_PATH
            else:
                recp_index = recp_next_copy_index
                microstate = MICRO_RECP_RECON_COPY_READ
        elif micro_is_recp_recon_path:
            control_top = control_top + 1
            recp_next_path_index: uint16_t = recp_index + 1
            if recp_next_path_index == recp_count:
                recp_index = 0
                microstate = MICRO_RECP_RECON_RUP_READ
            else:
                recp_index = recp_next_path_index
        elif micro_is_recp_recon_rup_read:
            recp_rup_word = memory_out.p0.rd_data
            microstate = MICRO_RECP_RECON_RUP_WRITE
        elif micro_is_recp_recon_rup_write:
            fsp = fsp + 1
            argcnt = argcnt + 1
            microstate = MICRO_RECP_RECON_VAR_WRITE
        elif micro_is_recp_recon_var_write:
            pc = fsp
            fsp = fsp + 1
            argcnt = argcnt + 1
            direction = DIRECTION_REVERSE
            microstate = MICRO_COMMIT
        elif micro_is_recp_action:
            recp_action_forward: uint1_t = direction == DIRECTION_FORWARD
            if recp_action_forward:
                if fetched_word.hi[20]:
                    recp_new_env: uint17_t = free_space - 1
                    env = recp_new_env
                    free_space = recp_new_env
                    pc = recp_binding[15:0]
                    q = q - 1
                else:
                    fsp = fsp + 1
                    argcnt = argcnt + 1
                    pc = pc + 1
                microstate = MICRO_COMMIT
            else:
                control_top = control_top + 1
                q = q - 1
                microstate = MICRO_COMMIT
        elif micro_is_lookup_read:
            binding_valid: uint1_t = memory_out.p0.rd_data.hi[26]
            binding_opcode: uint5_t = memory_out.p0.rd_data.hi[25:21]
            binding_definition_valid: uint1_t = memory_out.p0.rd_data.hi[16]
            binding_kind: uint2_t = memory_out.p0.rd_data.hi[18:17]
            binding_closure_slot: uint1_t = memory_out.p0.rd_data.hi[19]
            binding_is_pnp: uint1_t = binding_opcode == MOP_PNP
            binding_is_rec: uint1_t = binding_opcode == MOP_REC
            binding_is_closure: uint1_t = binding_opcode == MOP_CLOSURE
            lookup_address_in_range: uint1_t = lookup_address[16:GRAPH_ADDR_BITS] == 0
            lookup_has_remaining: uint1_t = lookup_remaining != 0
            binding_is_int: uint1_t = binding_opcode == MOP_INT
            binding_is_float: uint1_t = binding_opcode == MOP_FLOAT
            binding_is_char: uint1_t = binding_opcode == MOP_CHAR
            binding_is_sym: uint1_t = binding_opcode == MOP_SYM
            binding_is_ubv: uint1_t = binding_opcode == MOP_UBV
            binding_sym_undefined: uint1_t = binding_definition_valid == 0
            binding_shareable_sym: uint1_t = binding_is_sym and binding_sym_undefined
            binding_shareable_atomic: uint1_t = binding_is_int or binding_is_float
            binding_shareable_atomic = binding_shareable_atomic or binding_is_char
            binding_shareable_atomic = binding_shareable_atomic or binding_shareable_sym

            lookup_fsp_ok_exec: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            lookup_free_low_exec: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            lookup_free_end_exec: uint1_t = free_space == GRAPH_WORDS
            lookup_free_valid_exec: uint1_t = lookup_free_low_exec or lookup_free_end_exec
            lookup_destination_exec: uint17_t = fsp + 1
            lookup_gap_exec: uint17_t = free_space - lookup_destination_exec
            lookup_gap_wrapped_exec: uint1_t = lookup_gap_exec[16]
            lookup_gap_nonzero_exec: uint1_t = lookup_gap_exec != 0
            lookup_gap_not_wrapped_exec: uint1_t = lookup_gap_wrapped_exec == 0
            lookup_before_frontier_exec: uint1_t = lookup_gap_not_wrapped_exec and lookup_gap_nonzero_exec
            lookup_graph_ok_exec: uint1_t = lookup_fsp_ok_exec and lookup_free_valid_exec
            lookup_graph_ok_exec = lookup_graph_ok_exec and lookup_before_frontier_exec

            if not lookup_address_in_range:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif not binding_valid:
                red2_fault = FAULT_INVALID_ADDRESS
                microstate = MICRO_FAULT
            elif binding_is_pnp:
                pnp_kind_signed: uint1_t = binding_kind == DATA_SIGNED
                pnp_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                pnp_target_upper_nonzero: uint1_t = memory_out.p0.rd_data.lo[63:8] != 0
                next_lookup_hops: uint16_t = lookup_hops + 1
                pnp_hop_limit: uint1_t = next_lookup_hops[15:8] != 0
                if not pnp_kind_signed:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif pnp_negative:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif pnp_target_upper_nonzero:
                    red2_fault = FAULT_INVALID_ADDRESS
                    microstate = MICRO_FAULT
                elif pnp_hop_limit:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
                else:
                    lookup_address = memory_out.p0.rd_data.lo[16:0]
                    lookup_hops = next_lookup_hops
            elif lookup_has_remaining:
                lookup_remaining = lookup_remaining - 1
                if binding_is_rec:
                    lookup_address = lookup_address + 3
                elif binding_is_closure:
                    lookup_address = lookup_address + 2
                elif binding_closure_slot:
                    lookup_address = lookup_address + 2
                else:
                    lookup_address = lookup_address + 1
            elif opcode_is_var:
                if binding_is_ubv:
                    s_a = lookup_address + 1
                    s_d = 1
                    pc = lookup_address[15:0]
                    microstate = MICRO_COMMIT
                elif binding_shareable_atomic:
                    if not lookup_graph_ok_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        detached_var_hi: uint64_t = memory_out.p0.rd_data.hi & 132644863
                        detached_var_hi = detached_var_hi | 1048576
                        lookup_word = red2_word_t(
                            lo=memory_out.p0.rd_data.lo,
                            hi=detached_var_hi,
                        )
                        microstate = MICRO_LOOKUP_PUBLISH
                else:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
            elif opcode_is_app_var:
                if binding_is_ubv:
                    ubv_binding_signed: uint1_t = binding_kind == DATA_SIGNED
                    ubv_binding_negative: uint1_t = memory_out.p0.rd_data.lo[63]
                    if not ubv_binding_signed:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif ubv_binding_negative:
                        red2_fault = FAULT_INVALID_ADDRESS
                        microstate = MICRO_FAULT
                    elif not lookup_graph_ok_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        lookup_phi_wide: uint64_t = phi
                        app_var_payload: uint64_t = lookup_phi_wide - memory_out.p0.rd_data.lo
                        lookup_word = red2_word_t(lo=app_var_payload, hi=71434240)
                        microstate = MICRO_LOOKUP_PUBLISH
                elif binding_shareable_atomic:
                    if not lookup_graph_ok_exec:
                        red2_fault = FAULT_GRAPH_ENV_COLLISION
                        microstate = MICRO_FAULT
                    else:
                        detached_app_var_hi: uint64_t = memory_out.p0.rd_data.hi & 132644863
                        lookup_word = red2_word_t(
                            lo=memory_out.p0.rd_data.lo,
                            hi=detached_app_var_hi,
                        )
                        microstate = MICRO_LOOKUP_PUBLISH
                else:
                    hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED
                    microstate = MICRO_FAULT
            else:
                red2_fault = FAULT_ILLEGAL_TRANSITION
                microstate = MICRO_FAULT
        elif micro_is_lookup_publish:
            publish_fsp_ok: uint1_t = fsp[15:GRAPH_ADDR_BITS] == 0
            publish_free_low: uint1_t = free_space[16:GRAPH_ADDR_BITS] == 0
            publish_free_end: uint1_t = free_space == GRAPH_WORDS
            publish_free_valid: uint1_t = publish_free_low or publish_free_end
            publish_destination: uint17_t = fsp + 1
            publish_gap: uint17_t = free_space - publish_destination
            publish_gap_wrapped: uint1_t = publish_gap[16]
            publish_gap_nonzero: uint1_t = publish_gap != 0
            publish_gap_not_wrapped: uint1_t = publish_gap_wrapped == 0
            publish_before_frontier: uint1_t = publish_gap_not_wrapped and publish_gap_nonzero
            publish_graph_ok: uint1_t = publish_fsp_ok and publish_free_valid
            publish_graph_ok = publish_graph_ok and publish_before_frontier
            if not publish_graph_ok:
                red2_fault = FAULT_GRAPH_ENV_COLLISION
                microstate = MICRO_FAULT
            else:
                fsp = publish_destination[15:0]
                argcnt = argcnt + 1
                s_a = lookup_address + 1
                s_d = 1
                if opcode_is_var:
                    pc = publish_destination[15:0] - 1
                    direction = DIRECTION_REVERSE
                    microstate = MICRO_COMMIT
                elif opcode_is_app_var:
                    pc = pc + 1
                    microstate = MICRO_COMMIT
                else:
                    red2_fault = FAULT_ILLEGAL_TRANSITION
                    microstate = MICRO_FAULT
        elif microstate == MICRO_COMMIT:
            committed = 1
            microstate = MICRO_FETCH
        else:
            red2_fault = FAULT_ILLEGAL_TRANSITION
            microstate = MICRO_FAULT
    elif command.op == CMD_NOP:
        microstate = microstate
    else:
        hw_fault = HW_FAULT_BAD_COMMAND

    status: uint3_t = STATUS_RUNNING
    status_has_red2_fault: uint1_t = red2_fault != FAULT_NONE
    status_has_hw_fault: uint1_t = hw_fault != HW_FAULT_NONE
    status_is_fault_microstate: uint1_t = microstate == MICRO_FAULT
    status_any_fault: uint1_t = status_has_red2_fault or status_has_hw_fault
    status_any_fault = status_any_fault or status_is_fault_microstate
    status_pending_host: uint1_t = pending_host_op != HOST_NONE
    status_at_fetch: uint1_t = microstate == MICRO_FETCH
    status_host_call: uint1_t = status_pending_host and status_at_fetch
    status_halted: uint1_t = halted and status_at_fetch
    if status_any_fault:
        status = STATUS_FAULT
    elif status_host_call:
        status = STATUS_HOST_CALL
    elif status_halted:
        if q == 0:
            status = STATUS_QUANTUM_EXHAUSTED
        else:
            status = STATUS_COMPLETE

    return red2_status_t(
        status=status,
        red2_fault=red2_fault,
        hw_fault=hw_fault,
        microstate=microstate,
        committed=committed,
        pc=pc,
        fsp=fsp,
        env=env,
        control_top=control_top,
        direction=direction,
        q=q,
        phi=phi,
        free_space=free_space,
        argcnt=argcnt,
        prim_id=prim_id,
        fire=fire,
        s_a=s_a,
        s_d=s_d,
        halted=halted,
        pending_host_op=pending_host_op,
        pending_host_argument=pending_host_argument,
        memory_read=memory_out.p0.rd_data,
        control_read=control_out.p0.rd_data,
        semantics_complete=RED2_PYPELINE_SEMANTICS_COMPLETE,
    )

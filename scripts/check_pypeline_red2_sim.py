#!/usr/bin/env python3
"""Native Pypeline simulator parity checks for the synthesizable RED2 top.

This script intentionally requires the pinned external Pypeline checkout.  It is
invoked by the explicit Task-14 hardware gate, not by ordinary dependency-light
pytest.  The covered subset grows with the hardware port; unsupported reducer
semantics must remain explicit rather than approximated.
"""

from dataclasses import replace

from pypeline import sim_call, sim_reset

from pypeline_red2 import red2_stepper as abi
from pypeline_red2.red2_processor import (
    Red2Processor,
    SCALAR_OP_ABS,
    SCALAR_OP_ADD,
    SCALAR_OP_CEILING,
    SCALAR_OP_CHAR_P,
    SCALAR_OP_DEC,
    SCALAR_OP_EQ,
    SCALAR_OP_GE,
    SCALAR_OP_GT,
    SCALAR_OP_LE,
    SCALAR_OP_LT,
    SCALAR_OP_MAX,
    SCALAR_OP_MIN,
    SCALAR_OP_MUL,
    SCALAR_OP_DIV,
    SCALAR_OP_EXPT,
    SCALAR_OP_MOD,
    SCALAR_OP_EVEN,
    SCALAR_OP_FLOAT_P,
    SCALAR_OP_FLOOR,
    SCALAR_OP_INC,
    SCALAR_OP_INTEGER_P,
    SCALAR_OP_NEGATE,
    SCALAR_OP_NOT,
    SCALAR_OP_NULL,
    SCALAR_OP_NONE,
    SCALAR_OP_SUB,
    SCALAR_OP_SYMBOL_P,
    PRIM0_ROLE_PASSIVE,
    PRIM0_ROLE_IF,
    PRIM0_ROLE_IO_BIND,
    PRIM0_ROLE_DEFERRED,
    PRIM0_ROLE_Y,
    PRIM0_ROLE_IO_THEN,
    PRIM0_ROLE_IO_RETURN,
)
from pypeline_red2.red2_pypeline import (
    CMD_CLOCK,
    CMD_LOAD_CONTROL,
    CMD_LOAD_MEMORY,
    CMD_LOAD_LITERAL_META,
    CMD_LOAD_STATE,
    CMD_NOP,
    FAULT_GRAPH_ENV_COLLISION,
    FAULT_INVALID_ADDRESS,
    HW_FAULT_ADDRESS_RANGE,
    HW_FAULT_EXECUTION_NOT_IMPLEMENTED,
    HW_FAULT_NONE,
    LITERAL_SPECIAL_FALSE,
    LITERAL_SPECIAL_NIL,
    LITERAL_SPECIAL_TRUE,
    LITERAL_SPECIAL_EQUAL_IF,
    LITERAL_SPECIAL_EQUALITY,
    LITERAL_SPECIAL_EQUAL_STAR,
    LITERAL_SPECIAL_EQUALITY_CONTINUE,
    LITERAL_SPECIAL_EQUAL_STUCK,
    STATUS_FAULT,
    STATUS_RUNNING,
    red2_arch_state_t,
    red2_command_t,
    red2_control_t,
    red2_processor_top,
    red2_word_t,
)
from red2_engine.mured import (
    Direction,
    MuredMachine,
    MuredMachineState,
    MuredOpcode,
    Word,
)
from red2_engine.pipelinec_vectors import EncodedArchitecturalState, RED2ABICodec

MASK64 = (1 << 64) - 1
ZERO_WORD = red2_word_t(lo=0, hi=0)
ZERO_CONTROL = red2_control_t(lo=0, hi=0, tag_hi=0)
ZERO_STATE = red2_arch_state_t(
    pc=0,
    fsp=0,
    env=0,
    control_top=0,
    direction=0,
    q=0,
    phi=0,
    free_space=0,
    argcnt=0,
    prim_id=0,
    fire=0,
    s_a=0,
    s_d=0,
    halted=0,
    pending_host_op=0,
    pending_host_argument=0,
)


def _word_struct(packed: int) -> red2_word_t:
    return red2_word_t(lo=packed & MASK64, hi=(packed >> 64) & MASK64)


def _control_struct(packed: int) -> red2_control_t:
    return red2_control_t(
        lo=packed & MASK64,
        hi=(packed >> 64) & MASK64,
        tag_hi=(packed >> 128) & 0xF,
    )


def _command(
    op: int,
    *,
    address: int = 0,
    word: red2_word_t = ZERO_WORD,
    control: red2_control_t = ZERO_CONTROL,
    value: int = 0,
    aux: int = 0,
    state: red2_arch_state_t = ZERO_STATE,
) -> red2_command_t:
    return red2_command_t(
        op=op,
        address=address,
        word=word,
        control=control,
        value=value,
        aux=aux,
        state=state,
    )


def _load_literal_meta(
    slot: int,
    literal_id: int,
    *,
    scalar_op: int = 0,
    prim0_role: int = 0,
    host_op: int = 0,
    special_flags: int = 0,
) -> None:
    aux = scalar_op | (prim0_role << 5) | (host_op << 8) | (special_flags << 11)
    sim_call(
        red2_processor_top,
        _command(CMD_LOAD_LITERAL_META, address=slot, value=literal_id, aux=aux),
    )


def _state_struct(state) -> red2_arch_state_t:
    return red2_arch_state_t(
        pc=state.pc,
        fsp=state.fsp,
        env=state.env,
        control_top=state.c,
        direction=state.direction,
        q=state.q,
        phi=state.phi,
        free_space=state.free_space,
        argcnt=state.argcnt,
        prim_id=state.prim_id,
        fire=state.fire,
        s_a=state.s_a,
        s_d=state.s_d,
        halted=state.halted,
        pending_host_op=state.pending_host_op,
        pending_host_argument=state.pending_host_argument,
    )


def _packed_memory_read(result) -> int:
    return int(result.memory_read.lo) | (int(result.memory_read.hi) << 64)


def _packed_control_read(result) -> int:
    return (
        int(result.control_read.lo)
        | (int(result.control_read.hi) << 64)
        | (int(result.control_read.tag_hi) << 128)
    )


def _load_hardware(encoded) -> None:
    sim_reset()
    for index, packed in enumerate(encoded.memory):
        sim_call(
            red2_processor_top,
            _command(CMD_LOAD_MEMORY, address=index, word=_word_struct(packed)),
        )
    for index, packed in enumerate(encoded.control_stack):
        if packed:
            sim_call(
                red2_processor_top,
                _command(
                    CMD_LOAD_CONTROL,
                    address=index,
                    control=_control_struct(packed),
                ),
            )
    sim_call(
        red2_processor_top,
        _command(CMD_LOAD_STATE, state=_state_struct(encoded)),
    )


def _assert_scalar_checkpoint(result, expected) -> None:
    assert int(result.pc) == expected.pc
    assert int(result.fsp) == expected.fsp
    assert int(result.env) == expected.env
    assert int(result.control_top) == expected.c
    assert int(result.direction) == expected.direction
    assert int(result.q) == expected.q
    assert int(result.phi) == expected.phi
    assert int(result.free_space) == expected.free_space
    assert int(result.argcnt) == expected.argcnt
    assert int(result.prim_id) == expected.prim_id
    assert int(result.fire) == expected.fire
    assert int(result.s_a) == expected.s_a
    assert int(result.s_d) == expected.s_d
    assert int(result.halted) == expected.halted
    assert int(result.pending_host_op) == expected.pending_host_op
    assert int(result.pending_host_argument) == expected.pending_host_argument


def _run_one_commit(machine: MuredMachine, codec: RED2ABICodec) -> tuple[object, object]:
    encoded = codec.encode_state(machine.state)
    processor = Red2Processor(encoded)
    _load_hardware(encoded)

    expected_pulses = []
    actual_pulses = []
    result = None
    for _ in range(3):
        expected_pulses.append(bool(processor.clock()))
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        actual_pulses.append(bool(int(result.committed)))

    assert expected_pulses == [False, False, True]
    assert actual_pulses == expected_pulses
    expected = processor.checkpoint()
    assert result is not None
    _assert_scalar_checkpoint(result, expected)
    return result, expected


def _run_bounded_to_same_commit(
    machine: MuredMachine, codec: RED2ABICodec
) -> tuple[object, object]:
    """Compare one committed transition without requiring identical micro-latency."""
    encoded = codec.encode_state(machine.state)
    processor = Red2Processor(encoded)
    _load_hardware(encoded)

    assert processor.run_to_commit(), "Python RED2 oracle failed to reach a commit"
    expected = processor.checkpoint()

    result = None
    for _ in range(32):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        assert int(result.status) != 4, (
            f"hardware faulted before commit: red2={int(result.red2_fault)} "
            f"hw={int(result.hw_fault)} micro={int(result.microstate)}"
        )
        if int(result.committed):
            break
    else:
        raise AssertionError("hardware failed to reach a bounded commit")

    assert result is not None
    _assert_scalar_checkpoint(result, expected)
    return result, expected


def _with_control_entry(encoded, entry: int, *, index: int = 0):
    control_stack = list(encoded.control_stack)
    control_stack[index] = entry
    return replace(encoded, control_stack=tuple(control_stack), c=index + 1)


def _run_encoded_to_same_commit(encoded) -> tuple[object, object]:
    processor = Red2Processor(encoded)
    _load_hardware(encoded)
    assert processor.run_to_commit(), "Python RED2 oracle failed to reach a commit"
    expected = processor.checkpoint()

    result = None
    for _ in range(32):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        assert int(result.status) != STATUS_FAULT, (
            f"hardware faulted before commit: red2={int(result.red2_fault)} "
            f"hw={int(result.hw_fault)} micro={int(result.microstate)}"
        )
        if int(result.committed):
            break
    else:
        raise AssertionError("hardware failed to reach a bounded commit")

    assert result is not None
    _assert_scalar_checkpoint(result, expected)
    return result, expected


def _run_encoded_to_same_fault(
    encoded, *, max_clocks: int = 32
) -> tuple[object, object, int]:
    processor = Red2Processor(encoded)
    assert not processor.run_to_commit()
    expected_fault = processor.fault
    expected = processor.checkpoint()

    _load_hardware(encoded)
    result = None
    for _ in range(max_clocks):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("hardware failed to reach the expected bounded fault")

    assert result is not None
    assert int(result.red2_fault) == expected_fault
    assert int(result.hw_fault) == HW_FAULT_NONE
    _assert_scalar_checkpoint(result, expected)
    return result, expected, expected_fault


def _direct_lookup_machine(
    opcode: MuredOpcode,
    binding: Word | None,
    *,
    phi: int = 5,
    index: int = 0,
    env: int = 10,
    free_space: int = 10,
) -> MuredMachine:
    memory: list[Word | None] = [None] * 64
    memory[0] = Word(opcode, index, False)
    memory[1] = Word(MuredOpcode.STOP)
    if binding is not None:
        memory[env] = binding
    return MuredMachine(
        MuredMachineState(
            memory=memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=env,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=phi,
            free_space=free_space,
            argcnt=0,
        )
    )


def _assert_hardware_fault_without_publication(
    machine: MuredMachine,
    codec: RED2ABICodec,
    *,
    expected_red2_fault: int,
    expected_hw_fault: int = HW_FAULT_NONE,
    compare_oracle_fault: bool = True,
) -> None:
    encoded = codec.encode_state(machine.state)
    destination = encoded.fsp + 1

    if compare_oracle_fault:
        processor = Red2Processor(encoded)
        assert not processor.run_to_commit()
        assert processor.fault == expected_red2_fault

    _load_hardware(encoded)
    result = None
    for _ in range(32):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("hardware failed to reach the expected bounded fault")

    assert result is not None
    assert int(result.red2_fault) == expected_red2_fault
    assert int(result.hw_fault) == expected_hw_fault
    _assert_scalar_checkpoint(result, encoded)

    if destination < len(encoded.memory):
        readback = sim_call(
            red2_processor_top,
            _command(CMD_NOP, address=destination),
        )
        assert _packed_memory_read(readback) == encoded.memory[destination]


def check() -> None:
    for word in (
        Word(MuredOpcode.INT, 3, True),
        Word(MuredOpcode.FLOAT, 2.5, True),
        Word(MuredOpcode.CHAR, "x", True),
    ):
        codec = RED2ABICodec()
        machine = MuredMachine.load(
            [word], quantum=8, memory_words=64, control_words=32
        )
        result, _ = _run_one_commit(machine, codec)
        assert int(result.status) == STATUS_RUNNING

    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 32,
        pc=1,
        fsp=2,
        env=64,
        c=-1,
        direction=Direction.B,
        q=8,
        phi=0,
        argcnt=1,
    )
    state.memory[0] = Word(MuredOpcode.INT, 0, False)
    state.memory[1] = Word(MuredOpcode.INT, 7, False)
    state.memory[2] = Word(MuredOpcode.INT, 99, True)
    _run_one_commit(MuredMachine(state), codec)

    codec = RED2ABICodec()
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.APP_VAR, 0, False)],
        quantum=8,
        memory_words=64,
        control_words=32,
    )
    machine.state.direction = Direction.B
    machine.state.pc = 1
    _run_one_commit(machine, codec)

    codec = RED2ABICodec()
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 5, True)],
        quantum=0,
        memory_words=64,
        control_words=32,
    )
    encoded = codec.encode_state(machine.state)
    _load_hardware(encoded)
    result = sim_call(red2_processor_top, _command(CMD_NOP))
    assert int(result.q) == 0
    assert int(result.halted) == 0
    assert int(result.status) == STATUS_RUNNING

    sim_reset()
    packed_control = abi.pack_control_entry(abi.CONTROL_ADDRESS, 37, 0, 0, 0)
    sim_call(
        red2_processor_top,
        _command(
            CMD_LOAD_CONTROL,
            address=5,
            control=_control_struct(packed_control),
        ),
    )
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=5))
    assert _packed_control_read(result) == packed_control

    codec = RED2ABICodec()
    machine = MuredMachine.load(
        [Word(MuredOpcode.APP, 0, False), Word(MuredOpcode.INT, 1, True)],
        quantum=8,
        memory_words=64,
        control_words=32,
    )
    encoded = codec.encode_state(machine.state)
    processor = Red2Processor(encoded)
    _load_hardware(encoded)
    pulses = []
    result = None
    expected_pulses = [False, False, True]
    for expected_pulse in expected_pulses:
        assert bool(processor.clock()) is expected_pulse
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        pulses.append(bool(int(result.committed)))
    assert pulses == [False, False, True]
    assert result is not None
    expected = processor.checkpoint()
    _assert_scalar_checkpoint(result, expected)
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.fsp),
    )
    assert _packed_memory_read(result) == expected.memory[expected.fsp]
    control_address = expected.c - 1
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=control_address),
    )
    assert _packed_control_read(result) == expected.control_stack[control_address]

    # Reverse APP enters a child subgraph by replacing the saved caller path
    # with a CONTROL_SUBGRAPH frame and publishing JOIN at fsp+1.  Verify both
    # the contiguous and PNP-normalized environment forms.
    codec = RED2ABICodec()
    for parent_env, current_env, free_space, expected_entry_env in (
        (20, 30, 20, 20),
        (20, 30, 40, 39),
    ):
        reverse_app_memory: list[Word | None] = [None] * 64
        reverse_app_memory[0] = Word(MuredOpcode.APP, 7, True)
        reverse_app_memory[1] = Word(MuredOpcode.INT, 9, True)
        reverse_app_machine = MuredMachine(
            MuredMachineState(
                memory=reverse_app_memory,
                control_stack=[None] * 32,
                pc=0,
                fsp=1,
                env=current_env,
                c=-1,
                direction=Direction.B,
                q=8,
                phi=0,
                free_space=free_space,
                argcnt=1,
            )
        )
        reverse_app_encoded = _with_control_entry(
            codec.encode_state(reverse_app_machine.state),
            abi.pack_control_entry(abi.CONTROL_ADDRESS, parent_env, 0, 0, 0),
        )
        result, expected = _run_encoded_to_same_commit(reverse_app_encoded)
        assert expected.pc == 7
        assert expected.fsp == 2
        assert expected.env == expected_entry_env
        assert expected.free_space == expected_entry_env
        assert expected.c == 1
        assert expected.direction == abi.DIRECTION_FORWARD
        assert expected.argcnt == 1
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
        assert _packed_memory_read(result) == expected.memory[2]
        if expected_entry_env != parent_env:
            result = sim_call(
                red2_processor_top,
                _command(CMD_NOP, address=expected_entry_env),
            )
            assert _packed_memory_read(result) == expected.memory[expected_entry_env]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == expected.control_stack[0]

    # Entry collision is preflighted before replacing the saved caller path.
    collision_memory: list[Word | None] = [None] * 64
    collision_memory[0] = Word(MuredOpcode.APP, 7, True)
    collision_memory[19] = Word(MuredOpcode.INT, 9, True)
    collision_machine = MuredMachine(
        MuredMachineState(
            memory=collision_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=19,
            env=30,
            c=-1,
            direction=Direction.B,
            q=8,
            phi=0,
            free_space=20,
            argcnt=1,
        )
    )
    collision_encoded = _with_control_entry(
        codec.encode_state(collision_machine.state),
        abi.pack_control_entry(abi.CONTROL_ADDRESS, 20, 0, 0, 0),
    )
    result, expected, fault = _run_encoded_to_same_fault(collision_encoded)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Forward CLOSURE validates its following NONE code descriptor, pushes a
    # PNP marker for the captured environment, and jumps to the code target.
    closure_base_machine = MuredMachine(
        MuredMachineState(
            memory=[None] * 64,
            control_stack=[None] * 32,
            pc=0,
            fsp=0,
            env=30,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=0,
            free_space=40,
            argcnt=0,
        )
    )
    closure_base = codec.encode_state(closure_base_machine.state)
    closure_memory = list(closure_base.memory)
    closure_memory[0] = abi.pack_word(
        1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 20, 1, 0, 0, 0
    )
    closure_memory[1] = abi.pack_word(
        1, abi.MOP_NONE, abi.DATA_SIGNED, 7, 0, 0, 0, 0
    )
    closure_encoded = replace(closure_base, memory=tuple(closure_memory))
    result, expected = _run_encoded_to_same_commit(closure_encoded)
    assert expected.pc == 7
    assert expected.fsp == 0
    assert expected.env == 39
    assert expected.free_space == 39
    assert expected.argcnt == 1
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=39))
    assert _packed_memory_read(result) == expected.memory[39]

    # Closure/code validation faults occur before the environment marker is
    # published.  Exercise payload-kind, descriptor-opcode, and collision cases.
    bad_closure_kind_memory = list(closure_base.memory)
    bad_closure_kind_memory[0] = abi.pack_word(
        1, abi.MOP_CLOSURE, abi.DATA_LITERAL_ID, 20, 1, 0, 0, 0
    )
    bad_closure_kind_memory[1] = closure_memory[1]
    bad_closure_kind = replace(
        closure_base,
        memory=tuple(bad_closure_kind_memory),
    )
    _, _, fault = _run_encoded_to_same_fault(bad_closure_kind)
    assert fault == abi.FAULT_INVALID_ADDRESS

    wrong_code_memory = list(closure_base.memory)
    wrong_code_memory[0] = closure_memory[0]
    wrong_code_memory[1] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0
    )
    wrong_code = replace(closure_base, memory=tuple(wrong_code_memory))
    _, _, fault = _run_encoded_to_same_fault(wrong_code)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION

    tight_closure_base = replace(closure_base, free_space=1)
    tight_closure_memory = list(tight_closure_base.memory)
    tight_closure_memory[0] = closure_memory[0]
    tight_closure_memory[1] = closure_memory[1]
    tight_closure = replace(
        tight_closure_base,
        memory=tuple(tight_closure_memory),
    )
    result, expected, fault = _run_encoded_to_same_fault(tight_closure)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_memory_read(result) == expected.memory[0]

    # Forward EP chases EP aliases without publishing intermediate state, then
    # republishes the original EP and saves the current environment path.
    for chained in (False, True):
        ep_memory: list[Word | None] = [None] * 64
        ep_memory[0] = Word(MuredOpcode.EP, 10, True)
        if chained:
            ep_memory[10] = Word(MuredOpcode.EP, 11)
            ep_memory[11] = Word(MuredOpcode.INT, 7)
        else:
            ep_memory[10] = Word(MuredOpcode.INT, 7)
        ep_machine = MuredMachine(
            MuredMachineState(
                memory=ep_memory,
                control_stack=[None] * 32,
                pc=0,
                fsp=0,
                env=20,
                c=-1,
                direction=Direction.F,
                q=8,
                phi=0,
                free_space=40,
                argcnt=0,
            )
        )
        ep_encoded = codec.encode_state(ep_machine.state)
        result, expected = _run_encoded_to_same_commit(ep_encoded)
        assert expected.pc == 1
        assert expected.fsp == 1
        assert expected.c == 1
        assert expected.argcnt == 2
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
        assert _packed_memory_read(result) == expected.memory[1]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == expected.control_stack[0]

    ep_empty_memory: list[Word | None] = [None] * 64
    ep_empty_memory[0] = Word(MuredOpcode.EP, 10, True)
    ep_empty_machine = MuredMachine(
        MuredMachineState(
            memory=ep_empty_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=0,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=0,
            free_space=40,
            argcnt=0,
        )
    )
    _, _, fault = _run_encoded_to_same_fault(codec.encode_state(ep_empty_machine.state))
    assert fault == abi.FAULT_INVALID_ADDRESS

    ep_cycle_memory: list[Word | None] = [None] * 256
    ep_cycle_memory[0] = Word(MuredOpcode.EP, 10, True)
    ep_cycle_memory[10] = Word(MuredOpcode.EP, 10)
    ep_cycle_machine = MuredMachine(
        MuredMachineState(
            memory=ep_cycle_memory,
            control_stack=[None] * 256,
            pc=0,
            fsp=0,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=0,
            free_space=40,
            argcnt=0,
        )
    )
    _, _, fault = _run_encoded_to_same_fault(
        codec.encode_state(ep_cycle_machine.state), max_clocks=300
    )
    assert fault == abi.FAULT_ILLEGAL_TRANSITION

    ep_collision_memory: list[Word | None] = [None] * 64
    ep_collision_memory[0] = Word(MuredOpcode.EP, 10, True)
    ep_collision_memory[10] = Word(MuredOpcode.INT, 7)
    ep_collision_machine = MuredMachine(
        MuredMachineState(
            memory=ep_collision_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=19,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=0,
            free_space=20,
            argcnt=0,
        )
    )
    _, _, fault = _run_encoded_to_same_fault(codec.encode_state(ep_collision_machine.state))
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION

    ep_overflow_memory: list[Word | None] = [None] * 256
    ep_overflow_memory[0] = Word(MuredOpcode.EP, 10, True)
    ep_overflow_memory[10] = Word(MuredOpcode.INT, 7)
    ep_overflow_controls = [None] * 256
    ep_overflow_controls[255] = abi.pack_control_entry(
        abi.CONTROL_ADDRESS, 20, 0, 0, 0
    )
    ep_overflow_machine = MuredMachine(
        MuredMachineState(
            memory=ep_overflow_memory,
            control_stack=[None] * 256,
            pc=0,
            fsp=0,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=0,
            free_space=40,
            argcnt=0,
        )
    )
    ep_overflow_encoded = codec.encode_state(ep_overflow_machine.state)
    ep_overflow_encoded = replace(
        ep_overflow_encoded,
        control_stack=tuple(ep_overflow_controls),
        c=256,
    )
    _, _, fault = _run_encoded_to_same_fault(ep_overflow_encoded)
    assert fault == abi.FAULT_CONTROL_OVERFLOW

    # SYM is passive except for defined heads.  Forward publication pushes the
    # symbol unchanged; a defined head at q>0 reverses at the new fsp so that the
    # copied symbol immediately performs definition expansion.  Reverse expansion
    # transactionally pushes SAVED_DEFINITION_PATH(env), rewrites SYM -> APP(pc-1),
    # and decrements argcnt without consuming q or touching an active primitive.
    def sym_encoded(
        *,
        direction: int,
        q_value: int = 8,
        head: int = 1,
        definition_valid: int = 1,
        definition: int = 10,
        literal_id: int = 501,
        pc_value: int = 3,
        fsp_value: int = 6,
        free_value: int = 20,
        control_top_value: int = 0,
        control_entries: tuple[int, ...] = (),
        prim_id_value: int = 0,
        fire_value: int = 0,
    ):
        memory = [0] * 256
        memory[pc_value] = abi.pack_word(
            1,
            abi.MOP_SYM,
            abi.DATA_LITERAL_ID,
            literal_id,
            head,
            0,
            definition_valid,
            definition if definition_valid else 0,
        )
        controls = [0] * 256
        for index, entry in enumerate(control_entries):
            controls[index] = entry
        return EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple(controls),
            pc=pc_value,
            fsp=fsp_value,
            env=12,
            c=control_top_value,
            direction=direction,
            q=q_value,
            phi=4,
            free_space=free_value,
            argcnt=3,
            prim_id=prim_id_value,
            fire=fire_value,
            s_a=0,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )

    def check_sym_commit(encoded, addresses=(3, 7), controls=(0,)):
        result, expected = _run_encoded_to_same_commit(encoded)
        _assert_scalar_checkpoint(result, expected)
        for address in addresses:
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]
        for address in controls:
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_control_read(result) == expected.control_stack[address]
        return expected

    sym_rev = check_sym_commit(
        sym_encoded(direction=1),
        addresses=(3,),
        controls=(0,),
    )
    assert sym_rev.pc == 3 and sym_rev.c == 1 and sym_rev.q == 8
    assert sym_rev.argcnt == 2
    assert abi.control_tag(sym_rev.control_stack[0]) == abi.CONTROL_SAVED_DEFINITION_PATH
    assert abi.control_field(sym_rev.control_stack[0], 0) == 12
    assert abi.word_field(sym_rev.memory[3], abi.WORD_OPCODE_SHIFT, abi.OPCODE_BITS) == abi.MOP_APP
    assert abi.payload_to_signed(
        abi.word_field(sym_rev.memory[3], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS)
    ) == 2
    assert abi.word_field(sym_rev.memory[3], abi.WORD_DEFINITION_SHIFT, abi.WORD_DEFINITION_BITS) == 10

    sym_rev_active_prim = check_sym_commit(
        sym_encoded(direction=1, prim_id_value=571, fire_value=2),
        addresses=(3,),
        controls=(0,),
    )
    assert sym_rev_active_prim.prim_id == 571 and sym_rev_active_prim.fire == 2

    lower_address = abi.pack_control_entry(abi.CONTROL_ADDRESS, 7, 0, 0, 0)
    sym_rev_existing_control = check_sym_commit(
        sym_encoded(
            direction=1,
            control_top_value=1,
            control_entries=(lower_address,),
        ),
        addresses=(3,),
        controls=(0, 1),
    )
    assert sym_rev_existing_control.c == 2
    assert sym_rev_existing_control.control_stack[0] == lower_address
    assert abi.control_tag(sym_rev_existing_control.control_stack[1]) == abi.CONTROL_SAVED_DEFINITION_PATH

    sym_rev_nonhead = check_sym_commit(
        sym_encoded(direction=1, head=0),
        addresses=(3,),
        controls=(0,),
    )
    assert sym_rev_nonhead.pc == 2 and sym_rev_nonhead.c == 0

    sym_rev_qzero = check_sym_commit(
        sym_encoded(direction=1, q_value=0),
        addresses=(3,),
        controls=(0,),
    )
    assert sym_rev_qzero.pc == 2 and sym_rev_qzero.c == 0

    sym_forward_defined = check_sym_commit(
        sym_encoded(direction=0),
        addresses=(3, 7),
        controls=(0,),
    )
    assert sym_forward_defined.fsp == 7
    assert sym_forward_defined.pc == 7
    assert sym_forward_defined.direction == 1
    assert sym_forward_defined.memory[7] == sym_forward_defined.memory[3]

    sym_forward_qzero = check_sym_commit(
        sym_encoded(direction=0, q_value=0),
        addresses=(3, 7),
        controls=(0,),
    )
    assert sym_forward_qzero.fsp == 7
    assert sym_forward_qzero.pc == 6
    assert sym_forward_qzero.direction == 1

    sym_forward_nonhead = check_sym_commit(
        sym_encoded(direction=0, head=0),
        addresses=(3, 7),
        controls=(0,),
    )
    assert sym_forward_nonhead.fsp == 7
    assert sym_forward_nonhead.pc == 4
    assert sym_forward_nonhead.direction == 0

    # Expansion preflight is failure-atomic.
    for sym_fault_case, expected_fault in (
        (sym_encoded(direction=1, pc_value=0), abi.FAULT_INVALID_ADDRESS),
        (sym_encoded(direction=1, control_top_value=256), abi.FAULT_CONTROL_OVERFLOW),
        (sym_encoded(direction=0, free_value=7), abi.FAULT_GRAPH_ENV_COLLISION),
        (sym_encoded(direction=1, literal_id=0), abi.FAULT_ILLEGAL_TRANSITION),
    ):
        original_memory = tuple(sym_fault_case.memory)
        original_control = tuple(sym_fault_case.control_stack)
        result, expected, fault = _run_encoded_to_same_fault(sym_fault_case)
        assert fault == expected_fault
        assert expected.memory == original_memory
        assert expected.control_stack == original_control

    # PRIM_0 metadata-independent slice: reverse traversal is always passive,
    # and forward non-head descriptors simply publish. Forward head PRIM_0 is
    # intentionally left to metadata dispatch because equality/Y/host/IF/IO may
    # intercept before ordinary graph publication.
    def prim0_passive_encoded(
        *,
        direction: int = 0,
        head: int = 0,
        literal_id: int = 501,
        kind: int = abi.DATA_LITERAL_ID,
        fsp_value: int = 6,
        free_value: int = 20,
        prim_id_value: int = 777,
        fire_value: int = 9,
    ):
        memory = [0] * 256
        memory[3] = abi.pack_word(
            1, abi.MOP_PRIM_0, kind, literal_id, head, 0, 0, 0
        )
        return EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple([0] * 256),
            pc=3,
            fsp=fsp_value,
            env=12,
            c=0,
            direction=direction,
            q=8,
            phi=4,
            free_space=free_value,
            argcnt=4,
            prim_id=prim_id_value,
            fire=fire_value,
            s_a=0,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )

    prim0_nonhead = prim0_passive_encoded()
    result, expected = _run_encoded_to_same_commit(prim0_nonhead)
    _assert_scalar_checkpoint(result, expected)
    assert expected.pc == 4 and expected.fsp == 7 and expected.argcnt == 5
    assert expected.direction == 0
    assert expected.prim_id == 777 and expected.fire == 9
    for address in (3, 7):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    for reverse_head in (0, 1):
        prim0_reverse = prim0_passive_encoded(direction=1, head=reverse_head)
        result, expected = _run_encoded_to_same_commit(prim0_reverse)
        _assert_scalar_checkpoint(result, expected)
        assert expected.pc == 2 and expected.fsp == 6 and expected.argcnt == 4
        assert expected.prim_id == 777 and expected.fire == 9
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
        assert _packed_memory_read(result) == expected.memory[3]

    prim0_collision = prim0_passive_encoded(free_value=7)
    initial_memory = tuple(prim0_collision.memory)
    result, expected, fault = _run_encoded_to_same_fault(prim0_collision)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert expected.memory == initial_memory
    _assert_scalar_checkpoint(result, expected)

    for malformed_prim0 in (
        prim0_passive_encoded(direction=1, head=1, kind=abi.DATA_SIGNED),
        prim0_passive_encoded(direction=1, head=1, literal_id=0),
        prim0_passive_encoded(head=0, kind=abi.DATA_SIGNED),
        prim0_passive_encoded(head=0, literal_id=0),
    ):
        initial_memory = tuple(malformed_prim0.memory)
        result, expected, fault = _run_encoded_to_same_fault(malformed_prim0)
        assert fault == abi.FAULT_ILLEGAL_TRANSITION
        assert expected.memory == initial_memory
        _assert_scalar_checkpoint(result, expected)

    # Configured head PRIM_0 dispatch uses the same associative literal
    # metadata table on both sides. Missing metadata defaults to PASSIVE.
    def head_prim0_encoded(
        *,
        argcnt_value: int = 4,
        q_value: int = 8,
        free_value: int = 20,
        prim_id_value: int = 777,
        fire_value: int = 9,
        literal_id: int = 501,
    ):
        memory = [0] * 256
        memory[3] = abi.pack_word(
            1, abi.MOP_PRIM_0, abi.DATA_LITERAL_ID, literal_id, 1, 0, 0, 0
        )
        return EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple([0] * 256),
            pc=3,
            fsp=6,
            env=12,
            c=0,
            direction=0,
            q=q_value,
            phi=4,
            free_space=free_value,
            argcnt=argcnt_value,
            prim_id=prim_id_value,
            fire=fire_value,
            s_a=0,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )

    def run_head_prim0(
        *,
        role: int | None = None,
        host_op: int = abi.HOST_NONE,
        argcnt_value: int = 4,
        q_value: int = 8,
        free_value: int = 20,
        prim_id_value: int = 777,
        fire_value: int = 9,
        expect_fault: int | None = None,
        load_metadata: bool = True,
        special_flags: int = 0,
        equal_if: bool = False,
    ):
        literal_id = 501
        encoded = head_prim0_encoded(
            argcnt_value=argcnt_value,
            q_value=q_value,
            free_value=free_value,
            prim_id_value=prim_id_value,
            fire_value=fire_value,
            literal_id=literal_id,
        )
        roles = [0] * (literal_id + 1)
        hosts = [0] * (literal_id + 1)
        if role is not None:
            roles[literal_id] = role
        hosts[literal_id] = host_op
        processor = Red2Processor(
            encoded,
            prim0_roles=tuple(roles),
            host_ops=tuple(hosts),
            equal_if_literal_id=literal_id if equal_if else 0,
        )
        initial_memory = tuple(encoded.memory)
        if expect_fault is None:
            assert processor.run_to_commit(), "configured PRIM_0 oracle failed to commit"
        else:
            assert not processor.run_to_commit(), "configured PRIM_0 oracle unexpectedly committed"
            assert processor.fault == expect_fault
        expected = processor.checkpoint()

        _load_hardware(encoded)
        if load_metadata:
            _load_literal_meta(
                27,
                literal_id,
                prim0_role=PRIM0_ROLE_PASSIVE if role is None else role,
                host_op=host_op,
                special_flags=special_flags,
            )

        result = None
        for _ in range(96):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if expect_fault is not None:
                if int(result.status) == STATUS_FAULT:
                    break
            elif int(result.committed):
                break
            elif int(result.status) == STATUS_FAULT:
                raise AssertionError(
                    f"configured PRIM_0 hardware faulted: red2={int(result.red2_fault)} "
                    f"hw={int(result.hw_fault)} micro={int(result.microstate)}"
                )
        else:
            raise AssertionError("configured PRIM_0 hardware did not terminate")

        assert result is not None
        if expect_fault is not None:
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
        _assert_scalar_checkpoint(result, expected)
        for address in (3, 7):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]
        return expected, initial_memory

    # No table row is the oracle's default PASSIVE role.
    missing_meta, _ = run_head_prim0(load_metadata=False)
    assert missing_meta.pc == 6 and missing_meta.fsp == 7
    assert missing_meta.argcnt == 5
    assert missing_meta.prim_id == 777 and missing_meta.fire == 9

    passive_meta, _ = run_head_prim0(role=PRIM0_ROLE_PASSIVE)
    assert passive_meta.pc == 6 and passive_meta.fsp == 7
    assert passive_meta.prim_id == 777 and passive_meta.fire == 9

    # Visible encoded thresholds: IF >=4; IO_BIND/IO_THEN >=3.
    for role, below_count, armed_count in (
        (PRIM0_ROLE_IF, 3, 4),
        (PRIM0_ROLE_IO_BIND, 2, 3),
        (PRIM0_ROLE_IO_THEN, 2, 3),
    ):
        below, _ = run_head_prim0(
            role=role,
            argcnt_value=below_count,
            prim_id_value=0,
            fire_value=0,
        )
        assert below.prim_id == 0 and below.fire == 0
        armed, _ = run_head_prim0(
            role=role,
            argcnt_value=armed_count,
            prim_id_value=777,
            fire_value=9,
        )
        assert armed.prim_id == 501 and armed.fire == 1

        collision, initial_memory = run_head_prim0(
            role=role,
            argcnt_value=armed_count,
            free_value=7,
            prim_id_value=777,
            fire_value=9,
            expect_fault=abi.FAULT_GRAPH_ENV_COLLISION,
        )
        assert collision.prim_id == 501 and collision.fire == 1
        assert collision.memory == initial_memory

    io_return, _ = run_head_prim0(role=PRIM0_ROLE_IO_RETURN)
    assert io_return.prim_id == 777 and io_return.fire == 9

    exhausted_if, _ = run_head_prim0(
        role=PRIM0_ROLE_IF,
        argcnt_value=4,
        q_value=0,
        prim_id_value=0,
        fire_value=0,
    )
    assert exhausted_if.prim_id == 0 and exhausted_if.fire == 0

    deferred, deferred_initial = run_head_prim0(
        role=PRIM0_ROLE_DEFERRED,
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )
    assert deferred.memory == deferred_initial
    deferred_q0, _ = run_head_prim0(role=PRIM0_ROLE_DEFERRED, q_value=0)
    assert deferred_q0.pc == 6 and deferred_q0.fsp == 7

    # Direct host suspension has precedence over IF/DEFERRED when encoded
    # argcnt==1 and q>0, and it performs no graph publication.
    for direct_host in (abi.HOST_CLOCK, abi.HOST_UART_RX):
        for role in (PRIM0_ROLE_PASSIVE, PRIM0_ROLE_IF, PRIM0_ROLE_DEFERRED):
            host_result, host_initial = run_head_prim0(
                role=role,
                host_op=direct_host,
                argcnt_value=1,
            )
            assert host_result.pc == 3 and host_result.fsp == 6
            assert host_result.argcnt == 1
            assert host_result.pending_host_op == direct_host
            assert host_result.pending_host_argument == 0
            assert host_result.memory == host_initial

        host_ineligible, _ = run_head_prim0(
            role=PRIM0_ROLE_PASSIVE,
            host_op=direct_host,
            argcnt_value=2,
        )
        assert host_ineligible.pending_host_op == abi.HOST_NONE
        assert host_ineligible.pc == 6 and host_ineligible.fsp == 7

        host_q0, _ = run_head_prim0(
            role=PRIM0_ROLE_PASSIVE,
            host_op=direct_host,
            argcnt_value=1,
            q_value=0,
        )
        assert host_q0.pending_host_op == abi.HOST_NONE
        assert host_q0.pc == 6 and host_q0.fsp == 7

    # __EQUAL_IF__ is an internal PRIM_0 identity.  It pre-arms fire=1 at
    # visible encoded argcnt >=4 even with exhausted quantum, then continues
    # through normal role/host processing.  Arming therefore survives a later
    # graph collision just like ordinary primitive arming.
    equal_if_below, _ = run_head_prim0(
        argcnt_value=3,
        prim_id_value=777,
        fire_value=9,
        special_flags=LITERAL_SPECIAL_EQUAL_IF,
        equal_if=True,
    )
    assert equal_if_below.prim_id == 777 and equal_if_below.fire == 9

    equal_if_armed, _ = run_head_prim0(
        argcnt_value=4,
        prim_id_value=777,
        fire_value=9,
        special_flags=LITERAL_SPECIAL_EQUAL_IF,
        equal_if=True,
    )
    assert equal_if_armed.prim_id == 501 and equal_if_armed.fire == 1

    equal_if_q0, _ = run_head_prim0(
        argcnt_value=4,
        q_value=0,
        prim_id_value=777,
        fire_value=9,
        special_flags=LITERAL_SPECIAL_EQUAL_IF,
        equal_if=True,
    )
    assert equal_if_q0.prim_id == 501 and equal_if_q0.fire == 1

    equal_if_collision, equal_if_collision_initial = run_head_prim0(
        argcnt_value=4,
        free_value=7,
        prim_id_value=777,
        fire_value=9,
        special_flags=LITERAL_SPECIAL_EQUAL_IF,
        equal_if=True,
        expect_fault=abi.FAULT_GRAPH_ENV_COLLISION,
    )
    assert equal_if_collision.prim_id == 501 and equal_if_collision.fire == 1
    assert equal_if_collision.memory == equal_if_collision_initial

    # Below the equality threshold, later direct-host handling still wins.
    equal_if_clock, equal_if_clock_initial = run_head_prim0(
        argcnt_value=1,
        host_op=abi.HOST_CLOCK,
        special_flags=LITERAL_SPECIAL_EQUAL_IF,
        equal_if=True,
    )
    assert equal_if_clock.pending_host_op == abi.HOST_CLOCK
    assert equal_if_clock.memory == equal_if_clock_initial

    # Active Y is metadata-selected before host dispatch.  Its visible encoded
    # argcnt threshold is >=2 (oracle internal argcnt >=1).  APP arguments take
    # the direct jump branch; other values allocate one scratch clone and push
    # CONTROL_ADDRESS.  Every failure is preflighted before graph/control writes.
    def run_head_prim0_y(
        argument: int,
        *,
        argcnt_value: int = 2,
        q_value: int = 8,
        fsp_value: int = 6,
        free_value: int = 20,
        env_value: int = 12,
        control_top_value: int = 0,
        expect_fault: int | None = None,
    ):
        literal_id = 501
        memory = [0] * 256
        memory[2] = argument
        memory[3] = abi.pack_word(
            1, abi.MOP_PRIM_0, abi.DATA_LITERAL_ID, literal_id, 1, 0, 0, 0
        )
        encoded = EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple([0] * 256),
            pc=3,
            fsp=fsp_value,
            env=env_value,
            c=control_top_value,
            direction=0,
            q=q_value,
            phi=4,
            free_space=free_value,
            argcnt=argcnt_value,
            prim_id=777,
            fire=9,
            s_a=0,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )
        roles = [0] * (literal_id + 1)
        roles[literal_id] = PRIM0_ROLE_Y
        processor = Red2Processor(encoded, prim0_roles=tuple(roles))
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        if expect_fault is None:
            assert processor.run_to_commit(), "configured Y oracle failed to commit"
        else:
            assert not processor.run_to_commit(), "configured Y oracle unexpectedly committed"
            assert processor.fault == expect_fault
        expected = processor.checkpoint()

        _load_hardware(encoded)
        _load_literal_meta(27, literal_id, prim0_role=PRIM0_ROLE_Y)
        result = None
        for _ in range(96):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if expect_fault is not None:
                if int(result.status) == STATUS_FAULT:
                    break
            elif int(result.committed):
                break
            elif int(result.status) == STATUS_FAULT:
                raise AssertionError(
                    f"configured Y hardware faulted: red2={int(result.red2_fault)} "
                    f"hw={int(result.hw_fault)} micro={int(result.microstate)}"
                )
        else:
            raise AssertionError("configured Y hardware did not terminate")

        assert result is not None
        if expect_fault is not None:
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
        _assert_scalar_checkpoint(result, expected)

        touched_memory = {
            i for i, (before, after) in enumerate(zip(initial_memory, expected.memory))
            if before != after
        }
        touched_memory.update((2, 3))
        if 0 <= fsp_value < 256:
            touched_memory.add(fsp_value)
        if 0 <= fsp_value + 1 < 256:
            touched_memory.add(fsp_value + 1)
        for address in sorted(touched_memory):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            actual_memory = _packed_memory_read(result)
            assert actual_memory == expected.memory[address], (
                f"configured Y memory mismatch at {address}: "
                f"actual={actual_memory:#x} expected={expected.memory[address]:#x} "
                f"initial={initial_memory[address]:#x}"
            )

        # Read the control slot written by Y through the ordinary NOP control view.
        # Existing simulator result exposes the selected control RAM lane alongside
        # graph RAM; use LOAD_CONTROL only for initial state population, never here.
        touched_control = [
            i for i, (before, after) in enumerate(zip(initial_control, expected.control_stack))
            if before != after
        ]
        for address in touched_control:
            result = sim_call(
                red2_processor_top,
                _command(CMD_NOP, address=address),
            )
            assert _packed_control_read(result) == expected.control_stack[address]
        return expected, initial_memory, initial_control

    y_int = abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0)
    y_sym_closure = abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 77, 0, 1, 1, 123
    )
    y_app_11 = abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 11, 0, 0, 0, 0)
    y_app_256 = abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 256, 0, 0, 0, 0)
    y_app_bad_kind = abi.pack_word(
        1, abi.MOP_APP, abi.DATA_LITERAL_ID, 7, 0, 0, 0, 0
    )
    y_app_negative = abi.pack_word(
        1, abi.MOP_APP, abi.DATA_SIGNED, abi.signed_to_payload(-1), 0, 0, 0, 0
    )

    y_direct, _, _ = run_head_prim0_y(y_app_11)
    assert y_direct.pc == 11 and y_direct.fsp == 6 and y_direct.q == 7
    assert y_direct.c == 0 and y_direct.argcnt == 2
    assert y_direct.prim_id == 777 and y_direct.fire == 9

    # The oracle deliberately accepts a nonnegative APP payload even when the
    # resulting next pc is just beyond graph RAM; the following fetch owns that fault.
    y_direct_oob_next, _, _ = run_head_prim0_y(y_app_256)
    assert y_direct_oob_next.pc == 256 and y_direct_oob_next.q == 7

    y_scratch, _, _ = run_head_prim0_y(y_int)
    assert y_scratch.pc == 7 and y_scratch.fsp == 6 and y_scratch.q == 7
    assert y_scratch.c == 1 and y_scratch.argcnt == 2
    assert y_scratch.prim_id == 777 and y_scratch.fire == 9

    y_clone, _, _ = run_head_prim0_y(y_sym_closure)
    assert y_clone.memory[7] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 77, 1, 0, 1, 123
    )

    y_q0, _, _ = run_head_prim0_y(y_int, q_value=0)
    assert y_q0.pc == 6 and y_q0.fsp == 7 and y_q0.q == 0
    assert y_q0.c == 0 and y_q0.argcnt == 3

    y_noarg, _, _ = run_head_prim0_y(y_int, argcnt_value=1)
    assert y_noarg.pc == 6 and y_noarg.fsp == 7 and y_noarg.q == 8
    assert y_noarg.c == 0 and y_noarg.argcnt == 2

    for bad_argument in (0, y_app_bad_kind, y_app_negative):
        y_bad, y_bad_memory, y_bad_control = run_head_prim0_y(
            bad_argument,
            expect_fault=abi.FAULT_INVALID_ADDRESS,
        )
        assert y_bad.memory == y_bad_memory
        assert y_bad.control_stack == y_bad_control
        assert y_bad.q == 8

    y_collision, y_collision_memory, y_collision_control = run_head_prim0_y(
        y_int,
        free_value=7,
        expect_fault=abi.FAULT_GRAPH_ENV_COLLISION,
    )
    assert y_collision.memory == y_collision_memory
    assert y_collision.control_stack == y_collision_control
    assert y_collision.q == 8

    y_bad_env, y_bad_env_memory, y_bad_env_control = run_head_prim0_y(
        y_int,
        env_value=257,
        expect_fault=abi.FAULT_INVALID_ADDRESS,
    )
    assert y_bad_env.memory == y_bad_env_memory
    assert y_bad_env.control_stack == y_bad_env_control

    y_control_full, y_control_full_memory, y_control_full_control = run_head_prim0_y(
        y_int,
        control_top_value=256,
        expect_fault=abi.FAULT_CONTROL_OVERFLOW,
    )
    assert y_control_full.memory == y_control_full_memory
    assert y_control_full.control_stack == y_control_full_control

    # Boundary-valid allocation: scratch may occupy graph slot 255, env may
    # equal GRAPH_WORDS, and control slot 255 may be pushed (new top == 256).
    y_last_slots, _, _ = run_head_prim0_y(
        y_int,
        fsp_value=254,
        free_value=256,
        env_value=256,
        control_top_value=255,
    )
    assert y_last_slots.pc == 255 and y_last_slots.fsp == 254
    assert y_last_slots.c == 256 and y_last_slots.q == 7

    # fsp itself must be a graph address even on the direct-APP branch.
    y_bad_fsp, y_bad_fsp_memory, y_bad_fsp_control = run_head_prim0_y(
        y_app_11,
        fsp_value=256,
        free_value=256,
        expect_fault=abi.FAULT_INVALID_ADDRESS,
    )
    assert y_bad_fsp.memory == y_bad_fsp_memory
    assert y_bad_fsp.control_stack == y_bad_fsp_control
    assert y_bad_fsp.q == 8

    # PRIM_1/PRIM_2 descriptors are passive graph values whose head form arms
    # the primitive countdown only when the visible encoded argcnt reaches 2/3.
    # Arming precedes graph publication, so a push fault preserves prim/fire.
    def prim12_encoded(
        opcode: int,
        *,
        direction: int = 0,
        argcnt_value: int = 1,
        q_value: int = 8,
        head: int = 1,
        literal_id: int = 501,
        fsp_value: int = 6,
        free_value: int = 20,
        prim_id_value: int = 0,
        fire_value: int = 0,
    ):
        memory = [0] * 256
        memory[3] = abi.pack_word(
            1, opcode, abi.DATA_LITERAL_ID, literal_id, head, 0, 0, 0
        )
        return EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple([0] * 256),
            pc=3,
            fsp=fsp_value,
            env=12,
            c=0,
            direction=direction,
            q=q_value,
            phi=4,
            free_space=free_value,
            argcnt=argcnt_value,
            prim_id=prim_id_value,
            fire=fire_value,
            s_a=0,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )

    def check_prim12_commit(encoded, addresses=(3, 7)):
        result, expected = _run_encoded_to_same_commit(encoded)
        _assert_scalar_checkpoint(result, expected)
        for address in addresses:
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]
        return expected

    for prim_opcode, threshold, expected_fire in (
        (abi.MOP_PRIM_1, 2, 1),
        (abi.MOP_PRIM_2, 3, 2),
    ):
        below = check_prim12_commit(
            prim12_encoded(prim_opcode, argcnt_value=threshold - 1)
        )
        assert below.prim_id == 0 and below.fire == 0
        assert below.fsp == 7 and below.argcnt == threshold
        assert below.pc == 6 and below.direction == 1

        armed = check_prim12_commit(
            prim12_encoded(prim_opcode, argcnt_value=threshold)
        )
        assert armed.prim_id == 501 and armed.fire == expected_fire
        assert armed.fsp == 7 and armed.argcnt == threshold + 1
        assert armed.pc == 6 and armed.direction == 1

        overwrite = check_prim12_commit(
            prim12_encoded(
                prim_opcode,
                argcnt_value=threshold,
                prim_id_value=777,
                fire_value=9,
            )
        )
        assert overwrite.prim_id == 501 and overwrite.fire == expected_fire

        exhausted = check_prim12_commit(
            prim12_encoded(prim_opcode, argcnt_value=threshold, q_value=0)
        )
        assert exhausted.prim_id == 0 and exhausted.fire == 0

        nonhead = check_prim12_commit(
            prim12_encoded(prim_opcode, argcnt_value=threshold, head=0)
        )
        assert nonhead.pc == 4 and nonhead.direction == 0
        assert nonhead.prim_id == 0 and nonhead.fire == 0

        reverse = check_prim12_commit(
            prim12_encoded(
                prim_opcode,
                direction=1,
                argcnt_value=threshold,
                prim_id_value=777,
                fire_value=9,
            ),
            addresses=(3,),
        )
        assert reverse.pc == 2
        assert reverse.prim_id == 777 and reverse.fire == 9

        collision_case = prim12_encoded(
            prim_opcode,
            argcnt_value=threshold,
            free_value=7,
        )
        initial_memory = tuple(collision_case.memory)
        result, expected, fault = _run_encoded_to_same_fault(collision_case)
        assert fault == abi.FAULT_GRAPH_ENV_COLLISION
        assert expected.prim_id == 501 and expected.fire == expected_fire
        assert expected.memory == initial_memory
        _assert_scalar_checkpoint(result, expected)
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
        assert _packed_memory_read(result) == initial_memory[3]

    for malformed_prim in (
        replace(
            prim12_encoded(abi.MOP_PRIM_1, argcnt_value=2),
            memory=tuple(
                abi.pack_word(1, abi.MOP_PRIM_1, abi.DATA_SIGNED, 501, 1, 0, 0, 0)
                if i == 3 else 0
                for i in range(256)
            ),
        ),
        prim12_encoded(abi.MOP_PRIM_2, argcnt_value=3, literal_id=0),
    ):
        initial_memory = tuple(malformed_prim.memory)
        result, expected, fault = _run_encoded_to_same_fault(malformed_prim)
        assert fault == abi.FAULT_ILLEGAL_TRANSITION
        assert expected.memory == initial_memory
        _assert_scalar_checkpoint(result, expected)

    # Reverse STOP strips only a contiguous SAVED_DEFINITION_PATH suffix, then
    # advances pc and halts.  Lower ADDRESS/SUBGRAPH frames and even an explicit
    # empty slot below the architectural top are not interpreted by STOP.
    def reverse_stop_encoded(entries: list[int], *, explicit_top: int | None = None):
        memory = [0] * 64
        memory[3] = abi.pack_word(1, abi.MOP_STOP, abi.DATA_NONE, 0, 0, 0, 0, 0)
        memory[4] = abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 9, 1, 0, 0, 0)
        controls = [0] * 32
        for index, entry in enumerate(entries):
            controls[index] = entry
        return EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple(controls),
            pc=3,
            fsp=6,
            env=12,
            c=len(entries) if explicit_top is None else explicit_top,
            direction=1,
            q=8,
            phi=4,
            free_space=20,
            argcnt=2,
            prim_id=0,
            fire=0,
            s_a=0,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )

    saved_def = lambda path: abi.pack_control_entry(
        abi.CONTROL_SAVED_DEFINITION_PATH, path, 0, 0, 0
    )
    address_entry = lambda path: abi.pack_control_entry(
        abi.CONTROL_ADDRESS, path, 0, 0, 0
    )
    subgraph_entry = lambda path: abi.pack_control_entry(
        abi.CONTROL_SUBGRAPH, path, 0, 0, 0
    )

    for stop_entries in (
        [],
        [saved_def(10)],
        [saved_def(10), saved_def(20)],
        [address_entry(10)],
        [address_entry(10), saved_def(20)],
        [address_entry(10), saved_def(20), saved_def(30)],
        [subgraph_entry(10)],
        [subgraph_entry(10), saved_def(20)],
    ):
        encoded = reverse_stop_encoded(stop_entries)
        result, expected = _run_encoded_to_same_commit(encoded)
        _assert_scalar_checkpoint(result, expected)
        assert expected.pc == 4
        assert expected.halted == 1
        for index in range(max(1, len(stop_entries))):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=index))
            assert _packed_control_read(result) == expected.control_stack[index]

    # c/control_top may designate an empty top entry.  The oracle simply sees a
    # non-SAVED tag, leaves it in place, and halts rather than reporting underflow.
    stop_empty_top = reverse_stop_encoded([], explicit_top=1)
    result, expected = _run_encoded_to_same_commit(stop_empty_top)
    _assert_scalar_checkpoint(result, expected)
    assert expected.pc == 4 and expected.halted == 1 and expected.c == 1
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == 0

    # Reverse APP definition contraction takes precedence over the APP payload at
    # q>0.  It optionally discards one top SAVED_DEFINITION_PATH, publishes STOP
    # at the APP, drops one fsp slot, jumps to the definition, flips forward, and
    # consumes one quantum.  Other control entries are intentionally untouched.
    def reverse_app_definition_encoded(
        *,
        definition: int = 10,
        payload: int = 7,
        q_value: int = 8,
        control_entry: int | None = None,
    ):
        memory = [0] * 64
        memory[1] = abi.pack_word(
            1,
            abi.MOP_APP,
            abi.DATA_SIGNED,
            payload & MASK64,
            1,
            0,
            1,
            definition,
        )
        if definition < len(memory):
            memory[definition] = abi.pack_word(
                1, abi.MOP_INT, abi.DATA_SIGNED, 77, 1, 0, 0, 0
            )
        controls = [0] * 32
        c_value = 0
        if control_entry is not None:
            controls[0] = control_entry
            c_value = 1
        return EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple(controls),
            pc=1,
            fsp=2,
            env=20,
            c=c_value,
            direction=1,
            q=q_value,
            phi=5,
            free_space=40,
            argcnt=2,
            prim_id=0,
            fire=0,
            s_a=0,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )

    def check_reverse_app_definition(encoded):
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        result, expected = _run_encoded_to_same_commit(encoded)
        _assert_scalar_checkpoint(result, expected)
        for address in (1, 10):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == expected.control_stack[0]
        assert expected.memory[1] != initial_memory[1]
        return expected, initial_control

    reverse_def_no_control, _ = check_reverse_app_definition(
        reverse_app_definition_encoded()
    )
    assert reverse_def_no_control.pc == 10
    assert reverse_def_no_control.fsp == 1
    assert reverse_def_no_control.c == 0
    assert reverse_def_no_control.q == 7
    assert reverse_def_no_control.direction == 0
    assert reverse_def_no_control.memory[1] == abi.pack_word(
        1, abi.MOP_STOP, abi.DATA_NONE, 0, 0, 0, 0, 0
    )

    reverse_def_saved, _ = check_reverse_app_definition(
        reverse_app_definition_encoded(
            control_entry=abi.pack_control_entry(
                abi.CONTROL_SAVED_DEFINITION_PATH, 23, 0, 0, 0
            )
        )
    )
    assert reverse_def_saved.c == 0
    assert reverse_def_saved.control_stack[0] == 0

    wrong_control = abi.pack_control_entry(abi.CONTROL_ADDRESS, 15, 0, 0, 0)
    reverse_def_wrong, initial_wrong_control = check_reverse_app_definition(
        reverse_app_definition_encoded(control_entry=wrong_control)
    )
    assert reverse_def_wrong.c == 1
    assert reverse_def_wrong.control_stack == initial_wrong_control

    # The definition field, not the APP payload, selects the jump target.  A
    # negative payload therefore does not participate in this q>0 contraction.
    reverse_def_negative_payload, _ = check_reverse_app_definition(
        reverse_app_definition_encoded(payload=MASK64)
    )
    assert reverse_def_negative_payload.pc == 10

    # Definition addresses are fixed-width fields.  The contraction itself does
    # not fetch/validate the target; an out-of-graph value commits and will fault
    # only on a later FETCH, matching the software oracle.
    reverse_def_large, _ = check_reverse_app_definition(
        reverse_app_definition_encoded(definition=511)
    )
    assert reverse_def_large.pc == 511

    # At q==0 definition firing is bypassed.  A SAVED_DEFINITION_PATH is then an
    # invalid ordinary reverse-APP caller path, so the transition faults without
    # STOP publication or control mutation.
    reverse_def_qzero = reverse_app_definition_encoded(
        q_value=0,
        control_entry=abi.pack_control_entry(
            abi.CONTROL_SAVED_DEFINITION_PATH, 23, 0, 0, 0
        ),
    )
    qzero_memory = tuple(reverse_def_qzero.memory)
    qzero_control = tuple(reverse_def_qzero.control_stack)
    result, expected, fault = _run_encoded_to_same_fault(reverse_def_qzero)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    assert expected.pc == 1 and expected.fsp == 2 and expected.q == 0
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == qzero_memory[1]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == qzero_control[0]

    # Reverse EP chases to a terminal under Task-4 shadow semantics.  UBV and
    # atomic terminals publish at the parent only after the caller-path pop and
    # optional PNP normalization have been fully preflighted.
    def reverse_ep_encoded(
        terminal_word: int,
        *,
        caller: int = 20,
        env: int = 20,
        free_space: int = 40,
        fsp: int = 2,
        phi: int = 5,
        prim_id: int = 0,
        fire: int = 0,
        control_tag: int = abi.CONTROL_ADDRESS,
        terminal_tail: int | None = None,
    ):
        ep_memory: list[Word | None] = [None] * 64
        ep_memory[1] = Word(MuredOpcode.EP, 10, True)
        ep_memory[2] = Word(MuredOpcode.INT, 9, True)
        ep_machine = MuredMachine(
            MuredMachineState(
                memory=ep_memory,
                control_stack=[None] * 32,
                pc=1,
                fsp=fsp,
                env=env,
                c=-1,
                direction=Direction.B,
                q=8,
                phi=phi,
                free_space=free_space,
                argcnt=1,
            )
        )
        encoded = codec.encode_state(ep_machine.state)
        memory = list(encoded.memory)
        memory[10] = terminal_word
        if terminal_tail is not None:
            memory[11] = terminal_tail
        encoded = replace(
            encoded,
            memory=tuple(memory),
            prim_id=prim_id,
            fire=fire,
        )
        return _with_control_entry(
            encoded,
            abi.pack_control_entry(control_tag, caller, 0, 0, 0),
        )

    reverse_ep_ubv = reverse_ep_encoded(
        abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 3, 0, 0, 0, 0),
        caller=12,
    )
    result, expected = _run_encoded_to_same_commit(reverse_ep_ubv)
    assert expected.pc == 0
    assert expected.env == 39
    assert expected.free_space == 39
    assert expected.c == 0
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == expected.memory[1]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=39))
    assert _packed_memory_read(result) == expected.memory[39]

    reverse_ep_atomic = reverse_ep_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
        caller=12,
    )
    result, expected = _run_encoded_to_same_commit(reverse_ep_atomic)
    assert expected.pc == 0
    assert expected.env == 39
    assert expected.free_space == 39
    assert expected.c == 0
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == expected.memory[1]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=39))
    assert _packed_memory_read(result) == expected.memory[39]

    # Active primitive countdown greater than one decrements after atomic EP
    # publication; the fire==1 scalar bridge remains a later semantic slice.
    reverse_ep_atomic_fire = reverse_ep_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
        prim_id=17,
        fire=2,
    )
    result, expected = _run_encoded_to_same_commit(reverse_ep_atomic_fire)
    assert expected.prim_id == 17
    assert expected.fire == 1
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == expected.memory[1]
    assert _packed_control_read(result) == expected.control_stack[0]

    # fire==1 on a reverse atomic EP is preflighted transactionally before the
    # caller pop/marker/publication.  q==0 is the oracle's special case: it skips
    # semantic lookup entirely, so even an otherwise unknown nonzero primitive id
    # reconstructs the EP and clears prim/fire.
    def run_reverse_ep_scalar(
        scalar_op: int,
        primitive_id: int,
        terminal_word: int,
        *,
        left_word: int | None = None,
        caller: int = 12,
        q_value: int = 8,
        expect_fault: int | None = None,
        expect_bool_metadata: bool = False,
        load_metadata: bool = True,
    ):
        encoded = reverse_ep_encoded(
            terminal_word,
            caller=caller,
            prim_id=primitive_id,
            fire=1,
        )
        memory = list(encoded.memory)
        if left_word is not None:
            memory[2] = left_word
        encoded = replace(encoded, memory=tuple(memory), q=q_value)

        max_id = max(primitive_id, 607, 613)
        ops = [0] * (max_id + 1)
        if load_metadata:
            ops[primitive_id] = scalar_op
        processor = Red2Processor(
            encoded,
            scalar_ops=tuple(ops),
            true_literal_id=607,
            false_literal_id=613,
        )
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        oracle_ok = processor.run_to_commit()
        expected = processor.checkpoint()

        _load_hardware(encoded)
        if load_metadata:
            _load_literal_meta(27, primitive_id, scalar_op=scalar_op)
        if expect_bool_metadata:
            _load_literal_meta(28, 607, special_flags=LITERAL_SPECIAL_TRUE)
            _load_literal_meta(29, 613, special_flags=LITERAL_SPECIAL_FALSE)

        result = None
        for _ in range(220):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT or int(result.committed):
                break
        else:
            raise AssertionError(f"reverse EP scalar {scalar_op} did not terminate")
        assert result is not None

        if expect_fault is None:
            assert oracle_ok
            assert int(result.status) != STATUS_FAULT, (
                f"reverse EP scalar {scalar_op} hardware faulted: "
                f"red2={int(result.red2_fault)} hw={int(result.hw_fault)} "
                f"micro={int(result.microstate)}"
            )
            assert int(result.committed)
            _assert_scalar_checkpoint(result, expected)
            for address in (1, 2, 10, 39):
                result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
                assert _packed_memory_read(result) == expected.memory[address]
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
            assert _packed_control_read(result) == expected.control_stack[0]
        else:
            assert not oracle_ok
            assert processor.fault == expect_fault
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
            _assert_scalar_checkpoint(result, expected)
            for address in (1, 2, 10, 39):
                result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
                assert _packed_memory_read(result) == initial_memory[address]
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
            assert _packed_control_read(result) == initial_control[0]
        return expected

    reverse_ep_inc = run_reverse_ep_scalar(
        SCALAR_OP_INC,
        571,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
    )
    assert reverse_ep_inc.pc == 0 and reverse_ep_inc.fsp == 1
    assert reverse_ep_inc.q == 7
    assert reverse_ep_inc.prim_id == 0 and reverse_ep_inc.fire == 0
    assert reverse_ep_inc.memory[1] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 3, 1, 0, 0, 0
    )

    reverse_ep_add = run_reverse_ep_scalar(
        SCALAR_OP_ADD,
        577,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
        left_word=abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
    )
    assert reverse_ep_add.fsp == 1 and reverse_ep_add.q == 7
    assert reverse_ep_add.memory[1] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 9, 1, 0, 0, 0
    )

    reverse_ep_lt = run_reverse_ep_scalar(
        SCALAR_OP_LT,
        587,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
        left_word=abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
        expect_bool_metadata=True,
    )
    assert reverse_ep_lt.memory[1] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 607, 1, 0, 0, 0
    )

    reverse_ep_stuck = run_reverse_ep_scalar(
        SCALAR_OP_ADD,
        593,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 1, 0, 0, 0, 0),
        left_word=abi.pack_word(
            1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('A'), 0, 0, 0, 0
        ),
    )
    assert reverse_ep_stuck.fsp == 2 and reverse_ep_stuck.q == 8
    assert reverse_ep_stuck.prim_id == 0 and reverse_ep_stuck.fire == 0

    reverse_ep_overflow = run_reverse_ep_scalar(
        SCALAR_OP_ADD,
        599,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 1, 0, 0, 0, 0),
        left_word=abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, (1 << 63) - 1, 0, 0, 0, 0
        ),
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
    )
    assert reverse_ep_overflow.pc == 1 and reverse_ep_overflow.fsp == 2
    assert reverse_ep_overflow.prim_id == 599 and reverse_ep_overflow.fire == 1

    reverse_ep_unknown_q8 = run_reverse_ep_scalar(
        SCALAR_OP_NONE,
        601,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
        load_metadata=False,
    )
    assert reverse_ep_unknown_q8.prim_id == 601 and reverse_ep_unknown_q8.fire == 1

    reverse_ep_unknown_q0 = run_reverse_ep_scalar(
        SCALAR_OP_NONE,
        603,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
        q_value=0,
        load_metadata=False,
    )
    assert reverse_ep_unknown_q0.pc == 0 and reverse_ep_unknown_q0.fsp == 2
    assert reverse_ep_unknown_q0.q == 0
    assert reverse_ep_unknown_q0.prim_id == 0 and reverse_ep_unknown_q0.fire == 0

    # Same-environment publication skips the PNP marker but uses the same scalar
    # preflight and final register effects.
    reverse_ep_same_env = run_reverse_ep_scalar(
        SCALAR_OP_INC,
        605,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
        caller=20,
    )
    assert reverse_ep_same_env.env == 20 and reverse_ep_same_env.free_space == 40
    assert reverse_ep_same_env.fsp == 1 and reverse_ep_same_env.q == 7

    # Closure terminals enter the same serialized subgraph machinery as reverse
    # APP.  Cover both the subgraph-only bridge and caller-path normalization.
    reverse_ep_closure_word = abi.pack_word(
        1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 25, 0, 0, 0, 0
    )
    reverse_ep_closure_tail = abi.pack_word(
        1, abi.MOP_NONE, abi.DATA_SIGNED, 7, 0, 0, 0, 0
    )
    for caller in (20, 12):
        reverse_ep_closure = reverse_ep_encoded(
            reverse_ep_closure_word,
            caller=caller,
            terminal_tail=reverse_ep_closure_tail,
        )
        result, expected = _run_encoded_to_same_commit(reverse_ep_closure)
        assert expected.pc == 10
        assert expected.fsp == 3
        assert expected.env == 39
        assert expected.free_space == 39
        assert expected.c == 1
        assert expected.argcnt == 1
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
        assert _packed_memory_read(result) == expected.memory[3]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=39))
        assert _packed_memory_read(result) == expected.memory[39]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == expected.control_stack[0]

    # Failures discovered after reading the terminal remain architecturally
    # atomic: no caller pop, PNP marker, or parent publication may leak.
    reverse_ep_bad_ubv = reverse_ep_encoded(
        abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 8, 0, 0, 0, 0),
        caller=12,
        phi=5,
    )
    result, expected, fault = _run_encoded_to_same_fault(reverse_ep_bad_ubv)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == expected.memory[1]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=39))
    assert _packed_memory_read(result) == expected.memory[39]

    reverse_ep_wrong_control = reverse_ep_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
        control_tag=abi.CONTROL_SUBGRAPH,
    )
    result, expected, fault = _run_encoded_to_same_fault(reverse_ep_wrong_control)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == expected.memory[1]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    reverse_ep_marker_collision = reverse_ep_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
        caller=12,
        free_space=3,
        fsp=2,
    )
    result, expected, fault = _run_encoded_to_same_fault(reverse_ep_marker_collision)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == expected.memory[1]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Simple reverse JOIN return: a single-word head VAR or shareable atomic
    # needs no graph materialization.  The frame remains untouched until all
    # parent/frame/tail validation has completed, then parent publication and
    # frame reclamation commit together (with an extra serialized closure-cache
    # write for EP-parent atomic returns).
    def simple_join_encoded(
        parent_word: int,
        result_word: int,
        *,
        parent_address: int = 2,
        join_address: int = 5,
        result_address: int = 6,
        env: int = 30,
        free_space: int = 30,
        frame_env: int = 20,
        frame_free_space: int = 40,
        frame_tag: int = abi.CONTROL_SUBGRAPH,
        frame_prim_id: int = 0,
        frame_fire: int = 0,
        ep_target_word: int | None = None,
        memory_words: int = 64,
    ):
        memory: list[Word | None] = [None] * memory_words
        memory[parent_address] = Word(MuredOpcode.APP, 9, False)
        memory[join_address] = Word(MuredOpcode.JOIN, parent_address)
        machine = MuredMachine(
            MuredMachineState(
                memory=memory,
                control_stack=[None] * 32,
                pc=join_address,
                fsp=result_address,
                env=env,
                c=-1,
                direction=Direction.B,
                q=8,
                phi=5,
                free_space=free_space,
                argcnt=1,
            )
        )
        encoded = codec.encode_state(machine.state)
        packed_memory = list(encoded.memory)
        packed_memory[parent_address] = parent_word
        packed_memory[join_address] = abi.pack_word(
            1, abi.MOP_JOIN, abi.DATA_SIGNED, parent_address, 0, 0, 0, 0
        )
        packed_memory[result_address] = result_word
        if ep_target_word is not None:
            packed_memory[10] = ep_target_word
            packed_memory[11] = abi.pack_word(
                1, abi.MOP_NONE, abi.DATA_SIGNED, 15, 0, 0, 0, 0
            )
        controls = list(encoded.control_stack)
        controls[0] = abi.pack_control_entry(
            frame_tag, frame_env, frame_free_space, frame_prim_id, frame_fire
        )
        return replace(
            encoded,
            memory=tuple(packed_memory),
            control_stack=tuple(controls),
            c=1,
        )

    join_var = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_VAR, abi.DATA_SIGNED, 3, 1, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(join_var)
    assert expected.pc == 1
    assert expected.fsp == 4
    assert expected.env == 20
    assert expected.free_space == 40
    assert expected.c == 0
    assert expected.s_a == 7
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_var_parent_head = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 1, 0, 0, 0),
        abi.pack_word(1, abi.MOP_VAR, abi.DATA_SIGNED, 3, 1, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(join_var_parent_head)
    assert expected.fsp == 2
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]

    join_atomic = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(join_atomic)
    assert expected.pc == 1
    assert expected.fsp == 4
    assert expected.env == 20
    assert expected.free_space == 40
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]

    join_atomic_parent_head = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 1, 0, 0, 0),
        abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 65, 1, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(join_atomic_parent_head)
    assert expected.fsp == 2
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]

    join_ep_atomic = simple_join_encoded(
        abi.pack_word(1, abi.MOP_EP, abi.DATA_SIGNED, 10, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
        ep_target_word=abi.pack_word(
            1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 20, 0, 0, 0, 0
        ),
    )
    result, expected = _run_encoded_to_same_commit(join_ep_atomic)
    assert expected.pc == 1
    assert expected.fsp == 4
    assert expected.env == 20
    assert expected.free_space == 40
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=10))
    assert _packed_memory_read(result) == expected.memory[10]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # JOIN failure preflight remains architectural: no frame clear or parent
    # publication is allowed before the failure is known.
    join_wrong_frame = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
        frame_tag=abi.CONTROL_ADDRESS,
        frame_free_space=0,
    )
    result, expected, fault = _run_encoded_to_same_fault(join_wrong_frame)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_bad_parent = simple_join_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
    )
    result, expected, fault = _run_encoded_to_same_fault(join_bad_parent)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_bad_frontier = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
        frame_free_space=20,
    )
    result, expected, fault = _run_encoded_to_same_fault(join_bad_frontier)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_env_in_reclaim = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
        frame_env=35,
        frame_free_space=40,
    )
    result, expected, fault = _run_encoded_to_same_fault(join_env_in_reclaim)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Full 256-word hardware frontier bounds: 256 is the one-past-end value,
    # while 257 must be rejected even though it still fits in the 17-bit lane.
    join_frame_env_257 = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
        frame_env=257,
        frame_free_space=256,
        memory_words=256,
    )
    _, expected, fault = _run_encoded_to_same_fault(join_frame_env_257)
    assert fault == abi.FAULT_INVALID_ADDRESS

    join_frame_free_257 = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
        frame_env=20,
        frame_free_space=257,
        memory_words=256,
    )
    _, expected, fault = _run_encoded_to_same_fault(join_frame_free_257)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION

    # JOIN publication of a head EP must resolve and publish the child value
    # before the reclaimed environment interval is restored.  This includes
    # bounded EP chains, shareable atomics, and UBV -> graph VAR rewriting.
    def join_ep_result_encoded(
        target_word: int | None,
        *,
        descriptor_definition_valid: int = 0,
        descriptor_definition: int = 0,
        target_address: int = 29,
        extra_words: dict[int, int] | None = None,
    ):
        encoded = simple_join_encoded(
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
            abi.pack_word(
                1,
                abi.MOP_EP,
                abi.DATA_SIGNED,
                target_address,
                1,
                0,
                descriptor_definition_valid,
                descriptor_definition,
            ),
            parent_address=3,
            join_address=4,
            result_address=5,
            env=28,
            free_space=28,
            frame_env=32,
            frame_free_space=32,
        )
        memory = list(encoded.memory)
        if target_word is not None:
            memory[target_address] = target_word
        if extra_words is not None:
            for address, word in extra_words.items():
                memory[address] = word
        return replace(encoded, memory=tuple(memory), phi=7)

    join_ep_int = join_ep_result_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0)
    )
    result, expected = _run_encoded_to_same_commit(join_ep_int)
    assert expected.pc == 2
    assert expected.fsp == 3
    assert expected.env == 32
    assert expected.free_space == 32
    assert expected.s_a == 6
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == expected.memory[3]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=5))
    assert _packed_memory_read(result) == expected.memory[5]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Definition metadata comes from the EP descriptor being rewritten, while
    # the compacted parent APP_VAR remains definition-free.  Negative UBV
    # binders are signed values and therefore increase phi - binder.
    join_ep_ubv_negative = join_ep_result_encoded(
        abi.pack_word(
            1,
            abi.MOP_UBV,
            abi.DATA_SIGNED,
            abi.signed_to_payload(-3),
            0,
            0,
            0,
            0,
        ),
        descriptor_definition_valid=1,
        descriptor_definition=12,
    )
    result, expected = _run_encoded_to_same_commit(join_ep_ubv_negative)
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == expected.memory[3]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=5))
    assert _packed_memory_read(result) == expected.memory[5]
    assert ((expected.memory[5] >> (64 + 16)) & 1) == 1
    assert ((expected.memory[5] >> 64) & 0xFFFF) == 12
    assert (expected.memory[5] & ((1 << 64) - 1)) == 10

    join_ep_chain_int = join_ep_result_encoded(
        abi.pack_word(1, abi.MOP_EP, abi.DATA_SIGNED, 30, 0, 0, 0, 0),
        extra_words={
            30: abi.pack_word(
                1, abi.MOP_INT, abi.DATA_SIGNED, 42, 0, 0, 0, 0
            )
        },
    )
    result, expected = _run_encoded_to_same_commit(join_ep_chain_int)
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == expected.memory[3]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=5))
    assert _packed_memory_read(result) == expected.memory[5]

    # EP publication only rewrites descriptors whose terminal lives in the
    # child interval [free_space, frame_free_space).  Targets below the interval
    # or at/above its stop remain EP descriptors and are published by pointer.
    for outside_target in (27, 32, 40):
        outside_target_word = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0
        )
        join_ep_outside = join_ep_result_encoded(
            outside_target_word, target_address=outside_target
        )
        original_descriptor = join_ep_outside.memory[5]
        result, expected = _run_encoded_to_same_commit(join_ep_outside)
        assert expected.fsp == 5
        assert expected.s_a == 6
        assert expected.memory[5] == original_descriptor
        for address in (3, 5, outside_target):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_memory_read(result) == expected.memory[address]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == expected.control_stack[0]

    join_ep_missing = join_ep_result_encoded(None)
    result, expected, fault = _run_encoded_to_same_fault(join_ep_missing)
    assert fault == abi.FAULT_INVALID_ADDRESS
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == expected.memory[3]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=5))
    assert _packed_memory_read(result) == expected.memory[5]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_ep_bad_binder = join_ep_result_encoded(
        abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 8, 0, 0, 0, 0)
    )
    result, expected, fault = _run_encoded_to_same_fault(join_ep_bad_binder)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == expected.memory[3]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=5))
    assert _packed_memory_read(result) == expected.memory[5]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_ep_cycle = join_ep_result_encoded(
        abi.pack_word(1, abi.MOP_EP, abi.DATA_SIGNED, 30, 0, 0, 0, 0),
        extra_words={
            30: abi.pack_word(1, abi.MOP_EP, abi.DATA_SIGNED, 29, 0, 0, 0, 0)
        },
    )
    result, expected, fault = _run_encoded_to_same_fault(
        join_ep_cycle, max_clocks=300
    )
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == expected.memory[3]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=5))
    assert _packed_memory_read(result) == expected.memory[5]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # A head EP can be the root of a result graph even when unrelated live graph
    # words remain above it.  PUB_GRAPH must preserve fsp, rewrite the descriptor
    # for in-arena atomic/UBV terminals, and publish APP(descriptor_address).
    def join_general_ep_encoded(
        target_word: int, *, target_address: int = 28, parent_is_ep: bool = False
    ):
        parent_word = abi.pack_word(
            1, abi.MOP_EP if parent_is_ep else abi.MOP_APP,
            abi.DATA_SIGNED, 9, 0, 0, 0, 0
        )
        encoded = simple_join_encoded(
            parent_word,
            abi.pack_word(1, abi.MOP_EP, abi.DATA_SIGNED, target_address, 1, 0, 0, 0),
            parent_address=3,
            join_address=4,
            result_address=5,
            env=28,
            free_space=28,
            frame_env=32,
            frame_free_space=32,
            memory_words=64,
        )
        memory = list(encoded.memory)
        memory[target_address] = target_word
        if parent_is_ep:
            memory[9] = abi.pack_word(1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 50, 0, 0, 0, 0)
            memory[10] = abi.pack_word(1, abi.MOP_NONE, abi.DATA_SIGNED, 60, 0, 0, 0, 0)
        memory[20] = abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 777, 0, 0, 0, 0)
        memory[21] = abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 88, 1, 0, 0, 0)
        return replace(encoded, memory=tuple(memory), fsp=21, phi=7)

    for general_ep_case in (
        join_general_ep_encoded(abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0)),
        join_general_ep_encoded(abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 3, 0, 0, 0, 0)),
        join_general_ep_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 99, 0, 0, 0, 0),
            target_address=27,
        ),
        join_general_ep_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0),
            parent_is_ep=True,
        ),
        join_general_ep_encoded(
            abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 3, 0, 0, 0, 0),
            parent_is_ep=True,
        ),
    ):
        result, expected = _run_encoded_to_same_commit(general_ep_case)
        assert expected.fsp == 21
        for address in (3, 5, 20, 21):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address], (
                f"general-root EP mismatch at {address}"
            )

    # Saved scalar firing after general-root EP publication.  This pins whether
    # the primitive consumes the published APP(descriptor) root or the resolved
    # terminal cached into the descriptor; the software oracle is authoritative.
    general_root_inc_id = 197
    general_root_inc = join_general_ep_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0)
    )
    general_root_control = list(general_root_inc.control_stack)
    general_root_control[0] = abi.pack_control_entry(
        abi.CONTROL_SUBGRAPH, 32, 32, general_root_inc_id, 1
    )
    general_root_inc = replace(
        general_root_inc,
        control_stack=tuple(general_root_control),
        c=1,
    )
    general_root_ops = [0] * (general_root_inc_id + 1)
    general_root_ops[general_root_inc_id] = SCALAR_OP_INC
    general_root_processor = Red2Processor(
        general_root_inc,
        scalar_ops=tuple(general_root_ops),
    )
    assert general_root_processor.run_to_commit()
    general_root_expected = general_root_processor.checkpoint()
    _load_hardware(general_root_inc)
    _load_literal_meta(31, general_root_inc_id, scalar_op=SCALAR_OP_INC)
    general_root_result = None
    for _ in range(256):
        general_root_result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(general_root_result.status) == STATUS_FAULT:
            break
        if int(general_root_result.committed):
            break
    assert general_root_result is not None
    assert int(general_root_result.status) != STATUS_FAULT
    _assert_scalar_checkpoint(general_root_result, general_root_expected)
    for address in (3, 5, 20, 21, 28):
        general_root_result = sim_call(
            red2_processor_top, _command(CMD_NOP, address=address)
        )
        assert _packed_memory_read(general_root_result) == general_root_expected.memory[address], (
            f"saved-scalar general-root EP mismatch at {address}"
        )

    # JOIN publication of an EP -> CLOSURE materializes a narrow lambda graph
    # into graph-owned memory before reclaim.  This hardware slice intentionally
    # covers lambda spines ending in VAR, with local variables preserved and
    # captured variables resolved to shareable atomics through the environment.
    def join_closure_encoded(
        *,
        body_index: int = 1,
        env_words: dict[int, int] | None = None,
        fsp: int = 21,
        lambda_count: int = 1,
        lambda_definition_valid: int = 0,
        lambda_definition: int = 0,
    ):
        encoded = simple_join_encoded(
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_EP, abi.DATA_SIGNED, 28, 1, 0, 0, 0),
            parent_address=3,
            join_address=4,
            result_address=5,
            env=28,
            free_space=28,
            frame_env=32,
            frame_free_space=32,
            memory_words=64,
        )
        memory = list(encoded.memory)
        for lambda_index in range(lambda_count):
            memory[20 + lambda_index] = abi.pack_word(
                1, abi.MOP_LAMBDA, abi.DATA_LITERAL_ID, lambda_index + 1, 0, 0,
                lambda_definition_valid if lambda_index == 0 else 0,
                lambda_definition if lambda_index == 0 else 0,
            )
        memory[20 + lambda_count] = abi.pack_word(
            1, abi.MOP_VAR, abi.DATA_SIGNED, body_index, 1, 0, 0, 0
        )
        memory[28] = abi.pack_word(
            1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 30, 0, 0, 0, 0
        )
        memory[29] = abi.pack_word(
            1, abi.MOP_NONE, abi.DATA_SIGNED, 20, 0, 0, 0, 0
        )
        if env_words is None:
            env_words = {
                30: abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 42, 0, 0, 0, 0),
                31: abi.pack_word(1, abi.MOP_PNP, abi.DATA_SIGNED, 64, 0, 0, 0, 0),
            }
        for address, word in env_words.items():
            memory[address] = word
        return replace(encoded, memory=tuple(memory), fsp=fsp)

    join_closure_captured = join_closure_encoded()
    result, expected = _run_encoded_to_same_commit(join_closure_captured)
    assert expected.pc == 2
    assert expected.fsp == 23
    assert expected.env == 32
    assert expected.free_space == 32
    assert expected.s_a == 23
    for address in (3, 5, 22, 23, 28, 29, 30, 31):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address], (
            f"closure captured-atomic mismatch at {address}"
        )
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_closure_local = join_closure_encoded(body_index=0)
    result, expected = _run_encoded_to_same_commit(join_closure_local)
    assert expected.fsp == 23
    for address in (3, 22, 23):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address], (
            f"closure local-var mismatch at {address}"
        )

    join_closure_char = join_closure_encoded(
        env_words={
            30: abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 65, 0, 0, 0, 0),
            31: abi.pack_word(1, abi.MOP_PNP, abi.DATA_SIGNED, 64, 0, 0, 0, 0),
        },
        lambda_definition_valid=1,
        lambda_definition=13,
    )
    result, expected = _run_encoded_to_same_commit(join_closure_char)
    for address in (3, 22, 23):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address], (
            f"closure char/metadata mismatch at {address}"
        )

    join_closure_var2 = join_closure_encoded(
        body_index=2,
        env_words={
            30: abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 42, 0, 0, 0, 0),
            31: abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 65, 0, 0, 0, 0),
            32: abi.pack_word(1, abi.MOP_PNP, abi.DATA_SIGNED, 64, 0, 0, 0, 0),
        },
    )
    result, expected = _run_encoded_to_same_commit(join_closure_var2)
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=23))
    assert _packed_memory_read(result) == expected.memory[23]

    join_closure_pnp = join_closure_encoded(
        env_words={
            30: abi.pack_word(1, abi.MOP_PNP, abi.DATA_SIGNED, 40, 0, 0, 0, 0),
            40: abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 55, 0, 0, 0, 0),
            41: abi.pack_word(1, abi.MOP_PNP, abi.DATA_SIGNED, 64, 0, 0, 0, 0),
        }
    )
    result, expected = _run_encoded_to_same_commit(join_closure_pnp)
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=23))
    assert _packed_memory_read(result) == expected.memory[23]

    # Malformed closure inputs must fail before any publication write.
    join_closure_missing_env = join_closure_encoded(env_words={})
    result, expected, fault = _run_encoded_to_same_fault(join_closure_missing_env)
    assert fault == abi.FAULT_INVALID_ADDRESS
    for address in (3, 5, 22, 23, 30):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    join_closure_bad_code = join_closure_encoded()
    bad_code_memory = list(join_closure_bad_code.memory)
    bad_code_memory[29] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 20, 0, 0, 0, 0
    )
    join_closure_bad_code = replace(
        join_closure_bad_code, memory=tuple(bad_code_memory)
    )
    result, expected, fault = _run_encoded_to_same_fault(join_closure_bad_code)
    assert fault == abi.FAULT_INVALID_ADDRESS
    for address in (3, 5, 22, 23, 29):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    join_closure_pnp_cycle = join_closure_encoded(
        env_words={
            30: abi.pack_word(1, abi.MOP_PNP, abi.DATA_SIGNED, 30, 0, 0, 0, 0),
        }
    )
    result, expected, fault = _run_encoded_to_same_fault(
        join_closure_pnp_cycle, max_clocks=300
    )
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    for address in (3, 5, 22, 23, 30):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Two leading lambdas make this compact fixture's source 20..22 overlap the
    # destination 22..24.  The oracle is safe because it materializes into scratch;
    # until hardware has equivalent scratch, this case must fail explicitly before
    # the first write rather than corrupting the source while copying it.
    join_closure_overlap = join_closure_encoded(lambda_count=2, body_index=0)
    overlap_initial_memory = tuple(join_closure_overlap.memory)
    overlap_initial_control = tuple(join_closure_overlap.control_stack)
    _load_hardware(join_closure_overlap)
    overlap_result = None
    for _ in range(64):
        overlap_result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(overlap_result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("overlapping closure materialization did not fault")
    assert overlap_result is not None
    assert int(overlap_result.red2_fault) == abi.FAULT_NONE
    assert int(overlap_result.hw_fault) == HW_FAULT_EXECUTION_NOT_IMPLEMENTED
    for address in (3, 5, 20, 21, 22, 23, 24):
        overlap_result = sim_call(
            red2_processor_top, _command(CMD_NOP, address=address)
        )
        assert _packed_memory_read(overlap_result) == overlap_initial_memory[address]
    overlap_result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(overlap_result) == overlap_initial_control[0]

    # The oracle materializes into scratch first and only then capacity-checks.
    # Hardware must therefore fault before publishing any graph/control mutation.
    join_closure_no_space = join_closure_encoded(fsp=26)
    result, expected, fault = _run_encoded_to_same_fault(join_closure_no_space)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    for address in (3, 22, 23, 27):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Oracle PUB_APP_SCAN treats APP_VAR and non-head inline entries as
    # transparent prefix slots, and PUB_GRAPH returns already graph-owned
    # head-inline/VAR targets unchanged.
    def transparent_app_join_encoded(middle_word: int, target_word: int):
        encoded = simple_join_encoded(
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 20, 0, 0, 0, 0),
            parent_address=5,
            join_address=6,
            result_address=7,
            env=28,
            free_space=28,
            frame_env=32,
            frame_free_space=32,
            memory_words=64,
        )
        memory = list(encoded.memory)
        memory[8] = middle_word
        memory[9] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, 3, 1, 0, 0, 0
        )
        memory[20] = target_word
        return replace(encoded, memory=tuple(memory), fsp=9, phi=7)

    for transparent_case in (
        transparent_app_join_encoded(
            abi.pack_word(1, abi.MOP_APP_VAR, abi.DATA_SIGNED, 4, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 1, 0, 0, 0),
        ),
        transparent_app_join_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_VAR, abi.DATA_SIGNED, 2, 1, 0, 0, 0),
        ),
    ):
        result, expected = _run_encoded_to_same_commit(transparent_case)
        assert expected.fsp == 9
        assert expected.s_a == 8
        for address in (5, 7, 8, 9, 20):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address], (
                f"transparent APP-prefix mismatch at {address}"
            )

    # APP_VAR can itself be the root app-prefix entry.
    root_app_var = simple_join_encoded(
        abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_APP_VAR, abi.DATA_SIGNED, 4, 0, 0, 0, 0),
        parent_address=5,
        join_address=6,
        result_address=7,
        env=28,
        free_space=28,
        frame_env=32,
        frame_free_space=32,
        memory_words=64,
    )
    root_app_var_memory = list(root_app_var.memory)
    root_app_var_memory[8] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 3, 1, 0, 0, 0
    )
    root_app_var = replace(root_app_var, memory=tuple(root_app_var_memory), fsp=8)
    result, expected = _run_encoded_to_same_commit(root_app_var)
    for address in (5, 7, 8):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    # APP-prefix publication: validate the full prefix first, then rewrite a
    # shared EP target in place before reclaim.  Both APP descriptors remain
    # graph-owned pointers to the same published descriptor.
    def shared_app_join_encoded(target_word: int, *, second_target: int = 10):
        encoded = simple_join_encoded(
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 10, 0, 0, 0, 0),
            parent_address=5,
            join_address=6,
            result_address=7,
            env=28,
            free_space=28,
            frame_env=32,
            frame_free_space=32,
            memory_words=64,
        )
        memory = list(encoded.memory)
        memory[8] = abi.pack_word(
            1, abi.MOP_APP, abi.DATA_SIGNED, second_target, 0, 0, 0, 0
        )
        memory[9] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, 3, 1, 0, 0, 0
        )
        memory[10] = abi.pack_word(
            1, abi.MOP_EP, abi.DATA_SIGNED, 29, 1, 0, 0, 0
        )
        memory[29] = target_word
        if second_target != 10:
            memory[second_target] = abi.pack_word(
                1, abi.MOP_EP, abi.DATA_SIGNED, 30, 1, 0, 0, 0
            )
            memory[30] = abi.pack_word(
                1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 65, 0, 0, 0, 0
            )
        return replace(encoded, memory=tuple(memory), fsp=max(10, second_target), phi=7)

    for shared_app_case in (
        shared_app_join_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0)
        ),
        shared_app_join_encoded(
            abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 3, 0, 0, 0, 0)
        ),
    ):
        result, expected = _run_encoded_to_same_commit(shared_app_case)
        assert expected.fsp == 10
        assert expected.s_a == 8
        for address in (5, 7, 8, 9, 10, 29):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address], (
                f"shared APP target mismatch at {address}"
            )
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == expected.control_stack[0]

    # When closure publication changes an APP target root, the post-publication
    # retarget pass rewrites only APP descriptors and leaves transparent prefix
    # entries untouched.
    mixed_closure = transparent_app_join_encoded(
        abi.pack_word(1, abi.MOP_APP_VAR, abi.DATA_SIGNED, 4, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_EP, abi.DATA_SIGNED, 28, 1, 0, 0, 0),
    )
    mixed_closure_memory = list(mixed_closure.memory)
    mixed_closure_memory[20] = abi.pack_word(
        1, abi.MOP_EP, abi.DATA_SIGNED, 28, 1, 0, 0, 0
    )
    mixed_closure_memory[21] = abi.pack_word(
        1, abi.MOP_LAMBDA, abi.DATA_LITERAL_ID, 1, 0, 0, 0, 0
    )
    mixed_closure_memory[22] = abi.pack_word(
        1, abi.MOP_VAR, abi.DATA_SIGNED, 1, 1, 0, 0, 0
    )
    mixed_closure_memory[28] = abi.pack_word(
        1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 30, 0, 0, 0, 0
    )
    mixed_closure_memory[29] = abi.pack_word(
        1, abi.MOP_NONE, abi.DATA_SIGNED, 21, 0, 0, 0, 0
    )
    mixed_closure_memory[30] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 42, 0, 0, 0, 0
    )
    mixed_closure_memory[31] = abi.pack_word(
        1, abi.MOP_PNP, abi.DATA_SIGNED, 64, 0, 0, 0, 0
    )
    mixed_closure = replace(mixed_closure, memory=tuple(mixed_closure_memory), fsp=22)
    result, expected = _run_encoded_to_same_commit(mixed_closure)
    for address in (5, 7, 8, 9, 20, 23, 24):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address], (
            f"mixed-prefix closure rewrite mismatch at {address}"
        )

    shared_app_closure = shared_app_join_encoded(
        abi.pack_word(1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 30, 0, 0, 0, 0)
    )
    shared_closure_memory = list(shared_app_closure.memory)
    shared_closure_memory[10] = abi.pack_word(
        1, abi.MOP_EP, abi.DATA_SIGNED, 28, 1, 0, 0, 0
    )
    shared_closure_memory[20] = abi.pack_word(
        1, abi.MOP_LAMBDA, abi.DATA_LITERAL_ID, 1, 0, 0, 0, 0
    )
    shared_closure_memory[21] = abi.pack_word(
        1, abi.MOP_VAR, abi.DATA_SIGNED, 1, 1, 0, 0, 0
    )
    shared_closure_memory[28] = abi.pack_word(
        1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 30, 0, 0, 0, 0
    )
    shared_closure_memory[29] = abi.pack_word(
        1, abi.MOP_NONE, abi.DATA_SIGNED, 20, 0, 0, 0, 0
    )
    shared_closure_memory[30] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 42, 0, 0, 0, 0
    )
    shared_closure_memory[31] = abi.pack_word(
        1, abi.MOP_PNP, abi.DATA_SIGNED, 64, 0, 0, 0, 0
    )
    shared_app_closure = replace(
        shared_app_closure, memory=tuple(shared_closure_memory), fsp=21
    )
    result, expected = _run_encoded_to_same_commit(shared_app_closure)
    assert expected.fsp == 23
    assert expected.s_a == 8
    for address in (5, 7, 8, 9, 10, 22, 23, 28, 29, 30, 31):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address], (
            f"shared APP closure mismatch at {address}"
        )

    # Two unique APP target roots are preflighted transactionally before either
    # descriptor is rewritten.  Cover atomic/atomic, atomic/UBV, UBV/atomic, and
    # one outside-reclaim terminal in each position.
    def distinct_app_join_encoded(
        first_terminal: int, second_terminal: int, *, first_target: int = 29, second_target: int = 30
    ):
        encoded = shared_app_join_encoded(
            first_terminal, second_target=11
        )
        memory = list(encoded.memory)
        memory[10] = abi.pack_word(
            1, abi.MOP_EP, abi.DATA_SIGNED, first_target, 1, 0, 0, 0
        )
        memory[11] = abi.pack_word(
            1, abi.MOP_EP, abi.DATA_SIGNED, second_target, 1, 0, 0, 0
        )
        memory[first_target] = first_terminal
        memory[second_target] = second_terminal
        return replace(encoded, memory=tuple(memory), fsp=11, phi=7)

    distinct_cases = (
        distinct_app_join_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 65, 0, 0, 0, 0),
        ),
        distinct_app_join_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 3, 0, 0, 0, 0),
        ),
        distinct_app_join_encoded(
            abi.pack_word(1, abi.MOP_UBV, abi.DATA_SIGNED, 3, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0),
        ),
        distinct_app_join_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 99, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0),
            first_target=27, second_target=30,
        ),
        distinct_app_join_encoded(
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 88, 0, 0, 0, 0),
            first_target=29, second_target=27,
        ),
    )
    for distinct_case in distinct_cases:
        result, expected = _run_encoded_to_same_commit(distinct_case)
        assert expected.fsp == 11
        assert expected.s_a == 8
        for address in (5, 7, 8, 9, 10, 11, 27, 29, 30):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address], (
                f"distinct APP-target mismatch at {address}"
            )
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == expected.control_stack[0]

    # If the second target needs allocation, both targets must remain untouched:
    # the bounded two-target transaction rejects it during preflight, before the
    # already-valid first target can be published.
    distinct_allocating = distinct_app_join_encoded(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_CLOSURE, abi.DATA_SIGNED, 32, 0, 0, 0, 0),
    )
    allocating_initial_memory = tuple(distinct_allocating.memory)
    allocating_initial_control = tuple(distinct_allocating.control_stack)
    _load_hardware(distinct_allocating)
    allocating_result = None
    for _ in range(64):
        allocating_result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(allocating_result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("allocating second APP target did not fault")
    assert allocating_result is not None
    assert int(allocating_result.red2_fault) == abi.FAULT_NONE
    assert int(allocating_result.hw_fault) == HW_FAULT_EXECUTION_NOT_IMPLEMENTED
    for address in (5, 7, 8, 9, 10, 11, 29, 30):
        allocating_result = sim_call(
            red2_processor_top, _command(CMD_NOP, address=address)
        )
        assert _packed_memory_read(allocating_result) == allocating_initial_memory[address]
    allocating_result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(allocating_result) == allocating_initial_control[0]

    # Saved-primitive JOIN markers restore the typed frame primitive state and
    # consume exactly one countdown step.  fire==1 is deliberately deferred
    # because it immediately dispatches the primitive rather than merely counting.
    def saved_primitive_join_encoded(prim_id: int, fire: int, *, saved: bool = True):
        encoded = simple_join_encoded(
            abi.pack_word(
                1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0
            ),
            abi.pack_word(
                1, abi.MOP_INT, abi.DATA_SIGNED, 41, 1, 0, 0, 0
            ),
            parent_address=3, join_address=4, result_address=5,
            env=28, free_space=28, frame_env=32, frame_free_space=32,
            memory_words=64,
        )
        memory = list(encoded.memory)
        memory[4] = abi.pack_word(
            1, abi.MOP_JOIN, abi.DATA_SIGNED, 3, 0,
            0, 1 if saved else 0, 1 if saved else 0
        )
        control = list(encoded.control_stack)
        control[0] = abi.pack_control_entry(
            abi.CONTROL_SUBGRAPH, 32, 32, prim_id, fire
        )
        return replace(encoded, memory=tuple(memory), control_stack=tuple(control), c=1)

    for saved_case, expected_fire in (
        (saved_primitive_join_encoded(77, 3), 2),
        (saved_primitive_join_encoded(77, 2), 1),
    ):
        result, expected = _run_encoded_to_same_commit(saved_case)
        assert expected.prim_id == 77
        assert expected.fire == expected_fire
        assert int(result.prim_id) == expected.prim_id
        assert int(result.fire) == expected.fire
        for address in (3, 5):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]

    ordinary_prim_frame = saved_primitive_join_encoded(77, 3, saved=False)
    result, expected = _run_encoded_to_same_commit(ordinary_prim_frame)
    assert expected.prim_id == 0 and expected.fire == 0
    assert int(result.prim_id) == 0 and int(result.fire) == 0

    for malformed_saved in (
        saved_primitive_join_encoded(0, 2),
        saved_primitive_join_encoded(77, 0),
    ):
        initial_memory = tuple(malformed_saved.memory)
        initial_control = tuple(malformed_saved.control_stack)
        result, expected, fault = _run_encoded_to_same_fault(malformed_saved)
        assert fault == abi.FAULT_ILLEGAL_TRANSITION
        for address in (3, 4, 5):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == initial_memory[address]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == initial_control[0]

    # q==0 suppresses primitive dispatch even when the restored countdown is 1.
    # The JOIN still publishes normally, then clears prim/fire.
    saved_fire_one_qzero = replace(saved_primitive_join_encoded(77, 1), q=0)
    result, expected = _run_encoded_to_same_commit(saved_fire_one_qzero)
    assert expected.q == 0
    assert expected.prim_id == 0 and expected.fire == 0
    assert int(result.q) == 0
    assert int(result.prim_id) == 0 and int(result.fire) == 0
    for address in (3, 5):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    # q==0 does not erase a countdown that has not reached the firing boundary.
    # fire=3 therefore restores the primitive with fire=2 exactly as the oracle.
    saved_fire_three_qzero = replace(saved_primitive_join_encoded(77, 3), q=0)
    result, expected = _run_encoded_to_same_commit(saved_fire_three_qzero)
    assert expected.q == 0
    assert expected.prim_id == 77 and expected.fire == 2
    assert int(result.q) == 0
    assert int(result.prim_id) == 77 and int(result.fire) == 2
    for address in (3, 5):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    # Literal metadata is a bounded 64-entry associative table.  The final slot
    # is writable, slot 64 is rejected without aliasing to slot 0, and literal id
    # zero deterministically invalidates a slot for program reloads.
    metadata_probe_id = 0xA5A55A5A
    metadata_result = sim_call(
        red2_processor_top,
        _command(
            CMD_LOAD_LITERAL_META,
            address=63,
            value=metadata_probe_id,
            aux=SCALAR_OP_INC,
        ),
    )
    assert int(metadata_result.hw_fault) == HW_FAULT_NONE
    metadata_result = sim_call(
        red2_processor_top,
        _command(
            CMD_LOAD_LITERAL_META,
            address=64,
            value=0x11223344,
            aux=SCALAR_OP_INC,
        ),
    )
    assert int(metadata_result.hw_fault) == HW_FAULT_ADDRESS_RANGE

    # Prove the rejected slot-64 write did not truncate its address and overwrite
    # slot 0.  A distinct literal mapped only in slot 0 must still resolve and fire.
    slot_zero_literal_id = 0xC0FFEE
    slot_zero_ops = [0] * (slot_zero_literal_id + 1)
    slot_zero_ops[slot_zero_literal_id] = SCALAR_OP_INC
    slot_zero_case = saved_primitive_join_encoded(slot_zero_literal_id, 1)
    slot_zero_memory = list(slot_zero_case.memory)
    slot_zero_memory[5] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 10, 1, 0, 0, 0
    )
    slot_zero_case = replace(slot_zero_case, memory=tuple(slot_zero_memory))
    slot_zero_oracle = Red2Processor(slot_zero_case, scalar_ops=tuple(slot_zero_ops))
    assert slot_zero_oracle.run_to_commit()
    slot_zero_expected = slot_zero_oracle.checkpoint()
    _load_hardware(slot_zero_case)
    _load_literal_meta(0, slot_zero_literal_id, scalar_op=SCALAR_OP_INC)
    metadata_result = sim_call(
        red2_processor_top,
        _command(
            CMD_LOAD_LITERAL_META,
            address=64,
            value=0x11223344,
            aux=SCALAR_OP_DEC,
        ),
    )
    assert int(metadata_result.hw_fault) == HW_FAULT_ADDRESS_RANGE
    for _ in range(128):
        metadata_result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        assert int(metadata_result.status) != STATUS_FAULT, (
            f"slot-0 alias guard faulted: red2={int(metadata_result.red2_fault)} "
            f"hw={int(metadata_result.hw_fault)} micro={int(metadata_result.microstate)}"
        )
        if int(metadata_result.committed):
            break
    else:
        raise AssertionError("slot-0 alias guard did not commit")
    _assert_scalar_checkpoint(metadata_result, slot_zero_expected)
    metadata_result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(metadata_result) == slot_zero_expected.memory[3]

    metadata_invalidation_case = saved_primitive_join_encoded(metadata_probe_id, 1)
    _load_hardware(metadata_invalidation_case)
    _load_literal_meta(63, metadata_probe_id, scalar_op=SCALAR_OP_INC)
    # value==0 clears valid rather than installing a semantic literal zero entry.
    _load_literal_meta(63, 0, scalar_op=SCALAR_OP_INC)
    invalidated_memory = tuple(metadata_invalidation_case.memory)
    invalidated_control = tuple(metadata_invalidation_case.control_stack)
    metadata_result = None
    for _ in range(96):
        metadata_result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(metadata_result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("invalidated metadata entry still resolved")
    assert metadata_result is not None
    assert int(metadata_result.red2_fault) == abi.FAULT_ILLEGAL_TRANSITION
    assert int(metadata_result.hw_fault) == HW_FAULT_NONE
    for address in (3, 4, 5):
        metadata_result = sim_call(
            red2_processor_top, _command(CMD_NOP, address=address)
        )
        assert _packed_memory_read(metadata_result) == invalidated_memory[address]
    metadata_result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(metadata_result) == invalidated_control[0]

    # fire==1 resolves semantic metadata before touching graph/control RAM.  An
    # unknown primitive therefore matches the oracle ILLEGAL_TRANSITION and is
    # failure-atomic even though the associative lookup takes multiple clocks.
    saved_fire_one = saved_primitive_join_encoded(77, 1)
    fire_one_memory = tuple(saved_fire_one.memory)
    fire_one_control = tuple(saved_fire_one.control_stack)
    fire_one_result, _, fire_one_fault = _run_encoded_to_same_fault(
        saved_fire_one, max_clocks=96
    )
    assert fire_one_fault == abi.FAULT_ILLEGAL_TRANSITION
    for address in (3, 4, 5):
        fire_one_result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(fire_one_result) == fire_one_memory[address]
    fire_one_result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(fire_one_result) == fire_one_control[0]

    # Literal ids are codec allocation-order dependent.  Exercise INC using a
    # deliberately noncanonical id and a nonzero metadata-table slot so hardware
    # proves it uses the loaded semantic mapping rather than a baked-in id.
    dynamic_inc_id = 37
    scalar_ops = [0] * (dynamic_inc_id + 1)
    scalar_ops[dynamic_inc_id] = SCALAR_OP_INC

    def run_configured_inc(encoded):
        processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))
        assert processor.run_to_commit(), "configured INC oracle failed to commit"
        expected = processor.checkpoint()
        _load_hardware(encoded)
        _load_literal_meta(17, dynamic_inc_id, scalar_op=SCALAR_OP_INC)
        result = None
        for _ in range(128):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            assert int(result.status) != STATUS_FAULT, (
                f"configured INC hardware faulted: red2={int(result.red2_fault)} "
                f"hw={int(result.hw_fault)} micro={int(result.microstate)}"
            )
            if int(result.committed):
                break
        else:
            raise AssertionError("configured INC failed to reach bounded commit")
        assert result is not None
        _assert_scalar_checkpoint(result, expected)
        return result, expected

    inc_direct = saved_primitive_join_encoded(dynamic_inc_id, 1)
    inc_direct_memory = list(inc_direct.memory)
    inc_direct_memory[5] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 2, 1, 0, 0, 0
    )
    inc_direct = replace(inc_direct, memory=tuple(inc_direct_memory))
    result, expected = run_configured_inc(inc_direct)
    assert expected.q == 7 and expected.prim_id == 0 and expected.fire == 0
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == expected.memory[3]

    inc_ep = saved_primitive_join_encoded(dynamic_inc_id, 1)
    inc_ep_memory = list(inc_ep.memory)
    inc_ep_memory[5] = abi.pack_word(
        1, abi.MOP_EP, abi.DATA_SIGNED, 29, 1, 0, 0, 0
    )
    inc_ep_memory[29] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0
    )
    inc_ep = replace(inc_ep, memory=tuple(inc_ep_memory))
    result, expected = run_configured_inc(inc_ep)
    assert expected.q == 7 and expected.prim_id == 0 and expected.fire == 0
    for address in (3, 5, 29):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    def assert_configured_inc_fault(word: int) -> None:
        encoded = saved_primitive_join_encoded(dynamic_inc_id, 1)
        memory = list(encoded.memory)
        memory[5] = word
        encoded = replace(encoded, memory=tuple(memory))
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        processor = Red2Processor(encoded, scalar_ops=tuple(scalar_ops))
        assert not processor.run_to_commit()
        assert processor.fault == abi.FAULT_UNSUPPORTED_VALUE
        expected = processor.checkpoint()
        _load_hardware(encoded)
        _load_literal_meta(17, dynamic_inc_id, scalar_op=SCALAR_OP_INC)
        result = None
        for _ in range(128):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT:
                break
        else:
            raise AssertionError("configured INC fault did not arrive")
        assert result is not None
        assert int(result.red2_fault) == abi.FAULT_UNSUPPORTED_VALUE
        assert int(result.hw_fault) == HW_FAULT_NONE
        _assert_scalar_checkpoint(result, expected)
        for address in (3, 4, 5):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == initial_memory[address]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == initial_control[0]

    assert_configured_inc_fault(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, (1 << 63) - 1, 1, 0, 0, 0)
    )
    assert_configured_inc_fault(
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 0x4000000000000000, 1, 0, 0, 0)
    )

    # The same transactional path covers the rest of the unary integer family.
    # Give every operation an unrelated literal id and metadata slot so none can
    # accidentally depend on codec allocation order or table position.
    unary_cases = (
        (SCALAR_OP_DEC, 41, 3, 2),
        (SCALAR_OP_NEGATE, 43, 5, (-5) & MASK64),
        (SCALAR_OP_ABS, 47, (-7) & MASK64, 7),
        (SCALAR_OP_FLOOR, 53, (-9) & MASK64, (-9) & MASK64),
        (SCALAR_OP_CEILING, 59, 11, 11),
    )
    for table_slot, (scalar_op, literal_id, input_payload, output_payload) in enumerate(
        unary_cases, start=18
    ):
        ops = [0] * (literal_id + 1)
        ops[literal_id] = scalar_op
        encoded = saved_primitive_join_encoded(literal_id, 1)
        memory = list(encoded.memory)
        memory[5] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, input_payload, 1, 0, 0, 0
        )
        encoded = replace(encoded, memory=tuple(memory))
        processor = Red2Processor(encoded, scalar_ops=tuple(ops))
        assert processor.run_to_commit()
        expected = processor.checkpoint()
        assert expected.q == 7 and expected.prim_id == 0 and expected.fire == 0
        assert expected.memory[3] == abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, output_payload, 1, 0, 0, 0
        )
        _load_hardware(encoded)
        _load_literal_meta(table_slot, literal_id, scalar_op=scalar_op)
        result = None
        for _ in range(128):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            assert int(result.status) != STATUS_FAULT, (
                f"unary scalar {scalar_op} hardware faulted: "
                f"red2={int(result.red2_fault)} hw={int(result.hw_fault)} "
                f"micro={int(result.microstate)}"
            )
            if int(result.committed):
                break
        else:
            raise AssertionError(f"unary scalar {scalar_op} did not commit")
        assert result is not None
        _assert_scalar_checkpoint(result, expected)
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
        assert _packed_memory_read(result) == expected.memory[3]

    # Exercise the duplicated EP-backed preflight with a non-INC operation.
    negate_literal_id = 61
    negate_ops = [0] * (negate_literal_id + 1)
    negate_ops[negate_literal_id] = SCALAR_OP_NEGATE
    negate_ep = saved_primitive_join_encoded(negate_literal_id, 1)
    negate_ep_memory = list(negate_ep.memory)
    negate_ep_memory[5] = abi.pack_word(
        1, abi.MOP_EP, abi.DATA_SIGNED, 29, 1, 0, 0, 0
    )
    negate_ep_memory[29] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, (-12) & MASK64, 0, 0, 0, 0
    )
    negate_ep = replace(negate_ep, memory=tuple(negate_ep_memory))
    processor = Red2Processor(negate_ep, scalar_ops=tuple(negate_ops))
    assert processor.run_to_commit()
    expected = processor.checkpoint()
    _load_hardware(negate_ep)
    _load_literal_meta(23, negate_literal_id, scalar_op=SCALAR_OP_NEGATE)
    result = None
    for _ in range(128):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        assert int(result.status) != STATUS_FAULT
        if int(result.committed):
            break
    else:
        raise AssertionError("EP-backed NEGATE did not commit")
    assert result is not None
    _assert_scalar_checkpoint(result, expected)
    for address in (3, 5, 29):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    # DEC/NEGATE/ABS share the signed-minimum overflow boundary.
    for table_slot, (scalar_op, literal_id) in enumerate(
        ((SCALAR_OP_DEC, 63), (SCALAR_OP_NEGATE, 67), (SCALAR_OP_ABS, 71)),
        start=24,
    ):
        ops = [0] * (literal_id + 1)
        ops[literal_id] = scalar_op
        encoded = saved_primitive_join_encoded(literal_id, 1)
        memory = list(encoded.memory)
        memory[5] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, 1 << 63, 1, 0, 0, 0
        )
        encoded = replace(encoded, memory=tuple(memory))
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        processor = Red2Processor(encoded, scalar_ops=tuple(ops))
        assert not processor.run_to_commit()
        assert processor.fault == abi.FAULT_UNSUPPORTED_VALUE
        expected = processor.checkpoint()
        _load_hardware(encoded)
        _load_literal_meta(table_slot, literal_id, scalar_op=scalar_op)
        result = None
        for _ in range(128):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT:
                break
        else:
            raise AssertionError(f"unary scalar {scalar_op} overflow did not fault")
        assert result is not None
        assert int(result.red2_fault) == abi.FAULT_UNSUPPORTED_VALUE
        assert int(result.hw_fault) == HW_FAULT_NONE
        _assert_scalar_checkpoint(result, expected)
        for address in (3, 4, 5):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == initial_memory[address]
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
        assert _packed_control_read(result) == initial_control[0]

    # Boolean-producing unary scalars consume semantic TRUE/FALSE/NIL ids from
    # metadata rather than assuming codec allocation order.  Keep all ids and
    # table slots deliberately noncanonical.
    bool_true_id = 101
    bool_false_id = 103
    bool_nil_id = 107

    def load_bool_specials() -> None:
        _load_literal_meta(28, bool_true_id, special_flags=LITERAL_SPECIAL_TRUE)
        _load_literal_meta(29, bool_false_id, special_flags=LITERAL_SPECIAL_FALSE)
        _load_literal_meta(30, bool_nil_id, special_flags=LITERAL_SPECIAL_NIL)

    def run_configured_bool_unary(
        scalar_op: int,
        primitive_id: int,
        operand: int,
        *,
        ep_backed: bool = False,
    ):
        ops = [0] * (max(primitive_id, bool_true_id, bool_false_id, bool_nil_id) + 1)
        ops[primitive_id] = scalar_op
        encoded = saved_primitive_join_encoded(primitive_id, 1)
        memory = list(encoded.memory)
        if ep_backed:
            memory[5] = abi.pack_word(
                1, abi.MOP_EP, abi.DATA_SIGNED, 29, 1, 0, 0, 0
            )
            memory[29] = operand
        else:
            memory[5] = operand
        encoded = replace(encoded, memory=tuple(memory))
        processor = Red2Processor(
            encoded,
            scalar_ops=tuple(ops),
            true_literal_id=bool_true_id,
            false_literal_id=bool_false_id,
            nil_literal_id=bool_nil_id,
        )
        assert processor.run_to_commit(), f"boolean scalar {scalar_op} oracle failed"
        expected = processor.checkpoint()
        _load_hardware(encoded)
        _load_literal_meta(27, primitive_id, scalar_op=scalar_op)
        load_bool_specials()
        result = None
        for _ in range(220):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            assert int(result.status) != STATUS_FAULT, (
                f"boolean scalar {scalar_op} hardware faulted: "
                f"red2={int(result.red2_fault)} hw={int(result.hw_fault)} "
                f"micro={int(result.microstate)}"
            )
            if int(result.committed):
                break
        else:
            raise AssertionError(f"boolean scalar {scalar_op} did not commit")
        assert result is not None
        _assert_scalar_checkpoint(result, expected)
        addresses = (3, 5, 29) if ep_backed else (3, 5)
        for address in addresses:
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]
        return expected

    bool_cases = (
        (SCALAR_OP_EVEN, 109, abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 8, 1, 0, 0, 0)),
        (SCALAR_OP_EVEN, 113, abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 9, 1, 0, 0, 0)),
        (SCALAR_OP_NULL, 127, abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, bool_nil_id, 1, 0, 0, 0)),
        (SCALAR_OP_NULL, 131, abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('x'), 1, 0, 0, 0)),
        (SCALAR_OP_NOT, 137, abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, bool_true_id, 1, 0, 0, 0)),
        (SCALAR_OP_NOT, 139, abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, bool_false_id, 1, 0, 0, 0)),
        (SCALAR_OP_INTEGER_P, 149, abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 4, 1, 0, 0, 0)),
        (SCALAR_OP_FLOAT_P, 151, abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 0x4004000000000000, 1, 0, 0, 0)),
        (SCALAR_OP_CHAR_P, 157, abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('z'), 1, 0, 0, 0)),
        (SCALAR_OP_SYMBOL_P, 163, abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 211, 1, 0, 0, 0)),
    )
    for scalar_op, primitive_id, operand in bool_cases:
        expected = run_configured_bool_unary(scalar_op, primitive_id, operand)
        assert expected.q == 7
        assert expected.prim_id == 0 and expected.fire == 0

    # Stuck cases do not consume quantum and preserve the reconstructed operand.
    stuck_not = run_configured_bool_unary(
        SCALAR_OP_NOT,
        167,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 22, 1, 0, 0, 0),
    )
    assert stuck_not.q == 8
    stuck_predicate = run_configured_bool_unary(
        SCALAR_OP_INTEGER_P,
        173,
        abi.pack_word(1, abi.MOP_VAR, abi.DATA_SIGNED, 0, 1, 0, 0, 0),
    )
    assert stuck_predicate.q == 8

    # Exercise the duplicated EP-backed boolean preflight with EVEN?.
    ep_even = run_configured_bool_unary(
        SCALAR_OP_EVEN,
        179,
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 12, 0, 0, 0, 0),
        ep_backed=True,
    )
    assert ep_even.q == 7

    # FLOAT is a typed error for EVEN? and must fault before any publication.
    even_float_id = 181
    even_float_ops = [0] * (max(even_float_id, bool_true_id, bool_false_id, bool_nil_id) + 1)
    even_float_ops[even_float_id] = SCALAR_OP_EVEN
    even_float = saved_primitive_join_encoded(even_float_id, 1)
    even_float_memory = list(even_float.memory)
    even_float_memory[5] = abi.pack_word(
        1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 0x4004000000000000, 1, 0, 0, 0
    )
    even_float = replace(even_float, memory=tuple(even_float_memory))
    initial_memory = tuple(even_float.memory)
    initial_control = tuple(even_float.control_stack)
    processor = Red2Processor(
        even_float,
        scalar_ops=tuple(even_float_ops),
        true_literal_id=bool_true_id,
        false_literal_id=bool_false_id,
        nil_literal_id=bool_nil_id,
    )
    assert not processor.run_to_commit()
    assert processor.fault == abi.FAULT_UNSUPPORTED_VALUE
    expected = processor.checkpoint()
    _load_hardware(even_float)
    _load_literal_meta(27, even_float_id, scalar_op=SCALAR_OP_EVEN)
    load_bool_specials()
    result = None
    for _ in range(220):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("EVEN? FLOAT did not fault")
    assert result is not None
    assert int(result.red2_fault) == abi.FAULT_UNSUPPORTED_VALUE
    assert int(result.hw_fault) == HW_FAULT_NONE
    _assert_scalar_checkpoint(result, expected)
    for address in (3, 4, 5):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == initial_memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == initial_control[0]

    # Missing TRUE/FALSE metadata must fail before JOIN publication.  This is the
    # hardware equivalent of _bool_word() rejecting an absent semantic literal.
    missing_bool_id = 191
    missing_bool = saved_primitive_join_encoded(missing_bool_id, 1)
    missing_bool_memory = list(missing_bool.memory)
    missing_bool_memory[5] = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 2, 1, 0, 0, 0
    )
    missing_bool = replace(missing_bool, memory=tuple(missing_bool_memory))
    missing_memory = tuple(missing_bool.memory)
    missing_control = tuple(missing_bool.control_stack)
    _load_hardware(missing_bool)
    _load_literal_meta(27, missing_bool_id, scalar_op=SCALAR_OP_EVEN)
    result = None
    for _ in range(220):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("EVEN? without boolean metadata did not fault")
    assert result is not None
    assert int(result.red2_fault) == abi.FAULT_UNSUPPORTED_VALUE
    assert int(result.hw_fault) == HW_FAULT_NONE
    for address in (3, 4, 5):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == missing_memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == missing_control[0]

    # Binary saved primitives preflight parent+1 before any graph/control mutation.
    # Exercise success, signed ordering, polymorphic equality, stuck contracts,
    # EP-backed reconstruction, and typed failure atomicity with noncanonical ids.
    binary_true_id = 301
    binary_false_id = 303

    def load_binary_specials() -> None:
        _load_literal_meta(31, binary_true_id, special_flags=LITERAL_SPECIAL_TRUE)
        _load_literal_meta(32, binary_false_id, special_flags=LITERAL_SPECIAL_FALSE)

    def binary_join_encoded(primitive_id: int, left: int, right: int, *, ep_backed: bool = False):
        encoded = saved_primitive_join_encoded(primitive_id, 1)
        memory = list(encoded.memory)
        # The left operand occupies parent+1.  Move the saved JOIN/result pair one
        # slot to the right so the scalar evaluator sees left at pc+1 after restore.
        memory[4] = left
        memory[5] = abi.pack_word(
            1, abi.MOP_JOIN, abi.DATA_SIGNED, 3, 0, 0, 1, 1
        )
        if ep_backed:
            memory[6] = abi.pack_word(
                1, abi.MOP_EP, abi.DATA_SIGNED, 29, 1, 0, 0, 0
            )
            memory[29] = right
        else:
            memory[6] = right
        return replace(encoded, memory=tuple(memory), pc=5, fsp=6, argcnt=2)

    def run_binary_scalar(
        scalar_op: int,
        primitive_id: int,
        left: int,
        right: int,
        *,
        ep_backed: bool = False,
        expect_fault: int | None = None,
        expect_bool_metadata: bool = False,
    ):
        encoded = binary_join_encoded(
            primitive_id, left, right, ep_backed=ep_backed
        )
        ops = [0] * (max(primitive_id, binary_true_id, binary_false_id) + 1)
        ops[primitive_id] = scalar_op
        processor = Red2Processor(
            encoded,
            scalar_ops=tuple(ops),
            true_literal_id=binary_true_id,
            false_literal_id=binary_false_id,
        )
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        oracle_ok = processor.run_to_commit()
        expected = processor.checkpoint()
        _load_hardware(encoded)
        _load_literal_meta(30, primitive_id, scalar_op=scalar_op)
        if expect_bool_metadata:
            load_binary_specials()
        result = None
        for _ in range(260):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT or int(result.committed):
                break
        else:
            raise AssertionError(f"binary scalar {scalar_op} did not terminate")
        assert result is not None
        if expect_fault is None:
            assert oracle_ok, f"binary scalar {scalar_op} oracle faulted"
            assert int(result.status) != STATUS_FAULT, (
                f"binary scalar {scalar_op} hardware faulted: "
                f"red2={int(result.red2_fault)} hw={int(result.hw_fault)} "
                f"micro={int(result.microstate)}"
            )
            assert int(result.committed)
            _assert_scalar_checkpoint(result, expected)
            for address in ((3, 4, 5, 6, 29) if ep_backed else (3, 4, 5, 6)):
                result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
                assert _packed_memory_read(result) == expected.memory[address]
        else:
            assert not oracle_ok
            assert processor.fault == expect_fault
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
            _assert_scalar_checkpoint(result, expected)
            for address in ((3, 4, 5, 6, 29) if ep_backed else (3, 4, 5, 6)):
                result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
                assert _packed_memory_read(result) == initial_memory[address]
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
            assert _packed_control_read(result) == initial_control[0]
        return expected

    def sint(value: int, *, head: int = 0) -> int:
        return abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, value & MASK64, head, 0, 0, 0
        )

    # Arithmetic and signed comparisons, including negative ordering.
    binary_success_cases = (
        (SCALAR_OP_ADD, 211, sint(7), sint(2, head=1), False, False),
        (SCALAR_OP_SUB, 223, sint(2), sint(7, head=1), False, False),
        (SCALAR_OP_LT, 227, sint(-7), sint(2, head=1), False, True),
        (SCALAR_OP_GT, 229, sint(-7), sint(2, head=1), False, True),
        (SCALAR_OP_LE, 233, sint(2), sint(2, head=1), False, True),
        (SCALAR_OP_GE, 239, sint(2), sint(2, head=1), False, True),
        (SCALAR_OP_MAX, 241, sint(-7), sint(2, head=1), False, False),
        (SCALAR_OP_MIN, 251, sint(-7), sint(2, head=1), False, False),
        # EP-backed right operand exercises the pre-publication descriptor rewrite path.
        (SCALAR_OP_ADD, 257, sint(7), sint(2), True, False),
        (SCALAR_OP_LT, 263, sint(2), sint(7), True, True),
    )
    for scalar_op, primitive_id, left, right, ep_backed, needs_bool in binary_success_cases:
        expected = run_binary_scalar(
            scalar_op,
            primitive_id,
            left,
            right,
            ep_backed=ep_backed,
            expect_bool_metadata=needs_bool,
        )
        assert expected.q == 7
        assert expected.fsp == 3
        assert expected.prim_id == 0 and expected.fire == 0

    # Remaining integer binary operators use the same pre-publication left-read
    # path.  Division is exact-only; MOD follows Python/floor-division sign rules.
    remaining_binary_success = (
        (SCALAR_OP_MUL, 331, sint(7), sint(-3, head=1), False),
        (SCALAR_OP_MUL, 337, sint(-7), sint(-3, head=1), False),
        (SCALAR_OP_DIV, 347, sint(-6), sint(2, head=1), False),
        (SCALAR_OP_DIV, 349, sint(6), sint(-2, head=1), True),
        (SCALAR_OP_MOD, 353, sint(7), sint(3, head=1), False),
        (SCALAR_OP_MOD, 359, sint(-7), sint(3, head=1), False),
        (SCALAR_OP_MOD, 367, sint(7), sint(-3, head=1), False),
        (SCALAR_OP_MOD, 373, sint(-7), sint(-3, head=1), False),
        (SCALAR_OP_EXPT, 379, sint(2), sint(10, head=1), False),
        (SCALAR_OP_EXPT, 383, sint(-2), sint(63, head=1), False),
        (SCALAR_OP_EXPT, 389, sint(0), sint(0, head=1), False),
        (SCALAR_OP_EXPT, 397, sint(-1), sint(101, head=1), False),
    )
    for scalar_op, primitive_id, left, right, ep_backed in remaining_binary_success:
        expected = run_binary_scalar(
            scalar_op, primitive_id, left, right, ep_backed=ep_backed
        )
        assert expected.q == 7 and expected.fsp == 3
        assert expected.prim_id == 0 and expected.fire == 0

    # Equality has wider RED2 contracts than arithmetic.
    for primitive_id, left, right in (
        (269, sint(7), sint(7, head=1)),
        (
            271,
            abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('A'), 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('A'), 1, 0, 0, 0),
        ),
        (
            277,
            abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 55, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 55, 1, 0, 0, 0),
        ),
        (
            281,
            abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('A'), 0, 0, 0, 0),
            sint(ord('A'), head=1),
        ),
    ):
        expected = run_binary_scalar(
            SCALAR_OP_EQ, primitive_id, left, right, expect_bool_metadata=True
        )
        assert expected.q == 7 and expected.fsp == 3

    # Non-applicable binary contracts complete the JOIN but do not consume q.
    stuck_add = run_binary_scalar(
        SCALAR_OP_ADD,
        283,
        abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('A'), 0, 0, 0, 0),
        sint(1, head=1),
    )
    assert stuck_add.q == 8 and stuck_add.fsp == 4
    stuck_eq = run_binary_scalar(
        SCALAR_OP_EQ,
        293,
        abi.pack_word(1, abi.MOP_VAR, abi.DATA_SIGNED, 0, 0, 0, 0, 0),
        sint(1, head=1),
        expect_bool_metadata=True,
    )
    assert stuck_eq.q == 8 and stuck_eq.fsp == 4

    # Typed faults must occur before any JOIN/EP publication.
    run_binary_scalar(
        SCALAR_OP_ADD,
        307,
        sint((1 << 63) - 1),
        sint(1, head=1),
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
    )
    run_binary_scalar(
        SCALAR_OP_SUB,
        311,
        sint(-(1 << 63)),
        sint(1, head=1),
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
    )
    run_binary_scalar(
        SCALAR_OP_EQ,
        313,
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 0, 0, 0, 0, 0),
        sint(1, head=1),
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
        expect_bool_metadata=True,
    )

    # Remaining arithmetic failures are typed and failure-atomic too.
    for scalar_op, primitive_id, left, right in (
        (SCALAR_OP_MUL, 401, sint((1 << 63) - 1), sint(2, head=1)),
        (SCALAR_OP_DIV, 409, sint(7), sint(2, head=1)),
        (SCALAR_OP_DIV, 419, sint(-(1 << 63)), sint(-1, head=1)),
        (SCALAR_OP_DIV, 421, sint(1), sint(0, head=1)),
        (SCALAR_OP_MOD, 431, sint(1), sint(0, head=1)),
        (SCALAR_OP_EXPT, 433, sint(2), sint(63, head=1)),
        (SCALAR_OP_EXPT, 439, sint(2), sint(-1, head=1)),
    ):
        run_binary_scalar(
            scalar_op, primitive_id, left, right,
            expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
        )

    # A contracting comparison without semantic TRUE/FALSE ids is also a typed,
    # failure-atomic unsupported-value error.
    missing_binary_bool_id = 317
    missing_binary_bool = binary_join_encoded(
        missing_binary_bool_id, sint(2), sint(7, head=1)
    )
    missing_binary_memory = tuple(missing_binary_bool.memory)
    missing_binary_control = tuple(missing_binary_bool.control_stack)
    _load_hardware(missing_binary_bool)
    _load_literal_meta(30, missing_binary_bool_id, scalar_op=SCALAR_OP_LT)
    result = None
    for _ in range(260):
        result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("binary comparison without boolean metadata did not fault")
    assert result is not None
    assert int(result.red2_fault) == abi.FAULT_UNSUPPORTED_VALUE
    assert int(result.hw_fault) == HW_FAULT_NONE
    for address in (3, 4, 5, 6):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == missing_binary_memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == missing_binary_control[0]

    # A passive value executing backward can itself exhaust an active strict
    # primitive countdown.  This is the non-JOIN firing path: fire>1 only
    # decrements, while fire==1 resolves scalar metadata and either contracts,
    # stays stuck, or faults without touching graph/control state.
    def direct_fire_encoded(
        primitive_id: int,
        fire_count: int,
        right: int,
        *,
        left: int | None = None,
        q_value: int = 8,
    ):
        encoded = saved_primitive_join_encoded(primitive_id, max(fire_count, 1))
        memory = list(encoded.memory)
        memory[3] = right
        memory[4] = 0 if left is None else left
        return replace(
            encoded,
            memory=tuple(memory),
            pc=3,
            fsp=3 if left is None else 4,
            direction=1,
            q=q_value,
            prim_id=primitive_id,
            fire=fire_count,
        )

    def run_direct_scalar(
        scalar_op: int,
        primitive_id: int,
        right: int,
        *,
        left: int | None = None,
        q_value: int = 8,
        expect_fault: int | None = None,
        expect_bool_metadata: bool = False,
        load_metadata: bool = True,
    ):
        encoded = direct_fire_encoded(
            primitive_id, 1, right, left=left, q_value=q_value
        )
        ops = [0] * (max(primitive_id, binary_true_id, binary_false_id) + 1)
        if load_metadata:
            ops[primitive_id] = scalar_op
        processor = Red2Processor(
            encoded,
            scalar_ops=tuple(ops),
            true_literal_id=binary_true_id,
            false_literal_id=binary_false_id,
        )
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        oracle_ok = processor.run_to_commit()
        expected = processor.checkpoint()

        _load_hardware(encoded)
        if load_metadata:
            _load_literal_meta(30, primitive_id, scalar_op=scalar_op)
        if expect_bool_metadata:
            load_binary_specials()
        result = None
        for _ in range(220):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT or int(result.committed):
                break
        else:
            raise AssertionError(f"direct scalar {scalar_op} did not terminate")
        assert result is not None

        if expect_fault is None:
            assert oracle_ok
            assert int(result.status) != STATUS_FAULT, (
                f"direct scalar {scalar_op} hardware faulted: "
                f"red2={int(result.red2_fault)} hw={int(result.hw_fault)} "
                f"micro={int(result.microstate)}"
            )
            assert int(result.committed)
            _assert_scalar_checkpoint(result, expected)
            for address in (3, 4):
                result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
                assert _packed_memory_read(result) == expected.memory[address]
        else:
            assert not oracle_ok
            assert processor.fault == expect_fault
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
            _assert_scalar_checkpoint(result, expected)
            for address in (3, 4):
                result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
                assert _packed_memory_read(result) == initial_memory[address]
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
            assert _packed_control_read(result) == initial_control[0]
        return expected

    direct_inc = run_direct_scalar(
        SCALAR_OP_INC, 503, sint(2, head=1)
    )
    assert direct_inc.pc == 2 and direct_inc.fsp == 3 and direct_inc.q == 7
    assert direct_inc.prim_id == 0 and direct_inc.fire == 0
    assert direct_inc.memory[3] == sint(3, head=1)

    direct_add = run_direct_scalar(
        SCALAR_OP_ADD, 509, sint(2, head=1), left=sint(7)
    )
    assert direct_add.pc == 2 and direct_add.fsp == 3 and direct_add.q == 7
    assert direct_add.memory[3] == sint(9, head=1)
    assert direct_add.memory[4] == sint(7)

    direct_lt = run_direct_scalar(
        SCALAR_OP_LT,
        521,
        sint(2, head=1),
        left=sint(-7),
        expect_bool_metadata=True,
    )
    assert direct_lt.pc == 2 and direct_lt.fsp == 3 and direct_lt.q == 7
    assert direct_lt.memory[3] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_true_id, 1, 0, 0, 0
    )

    # Public structural EQUAL? has a dedicated atomic fast path.  It differs
    # from scalar '=' by accepting FLOAT constants, treating +/-0.0 as equal,
    # treating every NaN comparison as false, and comparing the common
    # SYM/PRIM literal class by payload rather than opcode.
    def run_direct_structural_equality(left: int, right: int, *, q_value: int = 8):
        equality_id = 557
        encoded = direct_fire_encoded(
            equality_id, 1, right, left=left, q_value=q_value
        )
        processor = Red2Processor(
            encoded,
            true_literal_id=binary_true_id,
            false_literal_id=binary_false_id,
            equality_literal_id=equality_id,
        )
        assert processor.run_to_commit(), processor.fault
        expected = processor.checkpoint()

        _load_hardware(encoded)
        _load_literal_meta(30, equality_id, special_flags=LITERAL_SPECIAL_EQUALITY)
        load_binary_specials()
        result = None
        for _ in range(260):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT or int(result.committed):
                break
        else:
            raise AssertionError('direct structural equality did not terminate')
        assert result is not None
        assert int(result.status) != STATUS_FAULT, (
            f'direct structural equality hardware faulted: red2={int(result.red2_fault)} '
            f'hw={int(result.hw_fault)} micro={int(result.microstate)}'
        )
        assert int(result.committed)
        _assert_scalar_checkpoint(result, expected)
        for address in (3, 4):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]
        return expected

    eq_int = run_direct_structural_equality(sint(7), sint(7, head=1))
    assert eq_int.q == 7 and eq_int.fsp == 3
    assert eq_int.memory[3] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_true_id, 1, 0, 0, 0
    )
    run_direct_structural_equality(sint(7), sint(8, head=1))
    run_direct_structural_equality(
        abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 65, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 65, 1, 0, 0, 0),
    )
    run_direct_structural_equality(
        abi.pack_word(1, abi.MOP_PRIM_0, abi.DATA_LITERAL_ID, 77, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 77, 1, 0, 0, 0),
    )
    run_direct_structural_equality(
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, 7, 1, 0, 0, 0),
    )
    run_direct_structural_equality(
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 0, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 9223372036854775808, 1, 0, 0, 0),
    )
    run_direct_structural_equality(
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 4609434218613702656, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 4609434218613702656, 1, 0, 0, 0),
    )
    run_direct_structural_equality(
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 9221120237041090561, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_FLOAT, abi.DATA_FLOAT64, 9221120237041090561, 1, 0, 0, 0),
    )
    eq_q0 = run_direct_structural_equality(sint(7), sint(7, head=1), q_value=0)
    assert eq_q0.q == 0 and eq_q0.fsp == 4
    assert eq_q0.prim_id == 0 and eq_q0.fire == 0
    assert eq_q0.memory[3] == sint(7, head=1)

    # Nonconstant public EQUAL? is launched transactionally from the saved-
    # primitive JOIN boundary.  The launch replaces the returned SUBGRAPH frame
    # with SAVED_QUANTUM/EQUALITY/new SUBGRAPH frames, appends the five-word
    # __EQUAL_STAR__ task plus parent APP/JOIN, and only then commits the parent
    # publication.  Exercise both the ordinary restored frontier and the PNP-
    # bridge case, plus the private-identity fault boundaries.
    equality_join_id = 571
    equal_star_join_id = 577
    equality_continue_join_id = 587

    def structural_equality_join_encoded(*, bridge: bool = False):
        encoded = simple_join_encoded(
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_VAR, abi.DATA_SIGNED, 3, 1, 0, 0, 0),
            parent_address=2,
            join_address=5,
            result_address=6,
            env=30,
            free_space=30,
            frame_env=28 if bridge else 32,
            frame_free_space=32,
            frame_prim_id=equality_join_id,
            frame_fire=1,
            memory_words=64,
        )
        memory = list(encoded.memory)
        # Binary EQUAL? reads the already-live left operand immediately after
        # its result/parent slot when the saved primitive reaches fire==1.
        memory[3] = abi.pack_word(
            1, abi.MOP_APP, abi.DATA_SIGNED, 18, 0, 0, 0, 0
        )
        memory[5] = abi.pack_word(
            1, abi.MOP_JOIN, abi.DATA_SIGNED, 2, 0, 0, 1, 1
        )
        return replace(encoded, memory=tuple(memory))

    def run_structural_equality_join_launch(
        *,
        bridge: bool = False,
        load_star: bool = True,
        load_continue: bool = True,
        expect_fault: int | None = None,
    ):
        encoded = structural_equality_join_encoded(bridge=bridge)
        processor = Red2Processor(
            encoded,
            true_literal_id=binary_true_id,
            false_literal_id=binary_false_id,
            equality_literal_id=equality_join_id,
            equal_star_literal_id=equal_star_join_id if load_star else 0,
            equality_continue_literal_id=(
                equality_continue_join_id if load_continue else 0
            ),
        )
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        if expect_fault is None:
            assert processor.run_to_commit(), processor.fault
        else:
            assert not processor.run_to_commit()
            assert processor.fault == expect_fault
        expected = processor.checkpoint()

        _load_hardware(encoded)
        _load_literal_meta(
            30, equality_join_id, special_flags=LITERAL_SPECIAL_EQUALITY
        )
        load_binary_specials()
        if load_star:
            _load_literal_meta(
                33, equal_star_join_id, special_flags=LITERAL_SPECIAL_EQUAL_STAR
            )
        if load_continue:
            _load_literal_meta(
                34,
                equality_continue_join_id,
                special_flags=LITERAL_SPECIAL_EQUALITY_CONTINUE,
            )

        result = None
        for _ in range(360):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT or int(result.committed):
                break
        else:
            raise AssertionError('structural equality JOIN launch did not terminate')
        assert result is not None
        if expect_fault is None:
            assert int(result.status) != STATUS_FAULT, (
                f'structural equality JOIN launch hardware faulted: '
                f'red2={int(result.red2_fault)} hw={int(result.hw_fault)} '
                f'micro={int(result.microstate)}'
            )
            assert int(result.committed)
        else:
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
        _assert_scalar_checkpoint(result, expected)

        # Compare the complete software-sized architectural memories.  This
        # catches stale reclaimed controls and partial launch publication, not
        # merely the obvious task words.
        for address, expected_word in enumerate(expected.memory):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_memory_read(result) == expected_word, (
                f'structural equality memory mismatch at {address}'
            )
        for address, expected_entry in enumerate(expected.control_stack):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_control_read(result) == expected_entry, (
                f'structural equality control mismatch at {address}'
            )
        if expect_fault is not None:
            assert expected.memory == initial_memory
            assert expected.control_stack == initial_control
        return expected

    equality_launch = run_structural_equality_join_launch()
    assert equality_launch.q == 7
    assert equality_launch.direction == abi.DIRECTION_FORWARD
    assert equality_launch.c == 3
    assert equality_launch.pc == 5 and equality_launch.fsp == 11
    assert abi.control_tag(equality_launch.control_stack[0]) == abi.CONTROL_SAVED_QUANTUM
    assert abi.control_tag(equality_launch.control_stack[1]) == abi.CONTROL_EQUALITY
    assert abi.control_tag(equality_launch.control_stack[2]) == abi.CONTROL_SUBGRAPH

    equality_bridge_launch = run_structural_equality_join_launch(bridge=True)
    assert equality_bridge_launch.env == 31
    assert equality_bridge_launch.free_space == 31
    assert equality_bridge_launch.memory[31] == abi.pack_word(
        1, abi.MOP_PNP, abi.DATA_SIGNED, 28, 0, 0, 0, 0
    )

    run_structural_equality_join_launch(
        load_star=False, expect_fault=abi.FAULT_ILLEGAL_TRANSITION
    )
    run_structural_equality_join_launch(
        load_continue=False, expect_fault=abi.FAULT_UNSUPPORTED_VALUE
    )

    # The first private __EQUAL_STAR__ child slice starts at the exact post-launch
    # T21 shape: a five-word task at pc-4..pc, four copied task arguments above an
    # existing saved JOIN, and descriptor mode selecting whether APP prefixes are
    # dereferenced before comparison.  Compare the complete graph/control images,
    # not merely the pushed boolean, so CHILD_INIT remains failure-atomic.
    equal_star_child_id = equal_star_join_id
    equality_child_continue_id = equality_continue_join_id
    equal_stuck_child_id = 593

    def equalstar_child_encoded(
        *,
        left_target_value: int = 1,
        right_target_value: int = 1,
        descriptor: int = 1,
        left_address_value: int | None = None,
        right_address_value: int | None = None,
        argcnt_value: int = 5,
        lambdas_value: int = 0,
        left_word_override: int | None = None,
        right_word_override: int | None = None,
        left_code_word_override: int | None = None,
        right_code_word_override: int | None = None,
        memory_overrides: dict[int, int] | None = None,
        free_space_value: int = 256,
    ):
        memory = [0] * 256
        if descriptor:
            # Descriptor mode 1 compares APP-prefix entries by dereferencing the
            # fixed wrappers at 11/10 to the actual words at 14/17.
            left_address = 11
            right_address = 10
            left_target_address = 14
            right_target_address = 17
            memory[10] = abi.pack_word(
                1, abi.MOP_APP, abi.DATA_SIGNED, right_target_address, 0, 0, 0, 0
            )
            memory[11] = abi.pack_word(
                1, abi.MOP_APP, abi.DATA_SIGNED, left_target_address, 0, 0, 0, 0
            )
        else:
            # Descriptor mode 0 compares these addresses directly; custom values
            # let recursive STRUCT fixtures live away from the private task graph.
            left_address = 14 if left_address_value is None else left_address_value
            right_address = 17 if right_address_value is None else right_address_value
            left_target_address = left_address
            right_target_address = right_address

        memory[left_target_address] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, left_target_value, 1, 0, 0, 0
        )
        memory[right_target_address] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, right_target_value, 1, 0, 0, 0
        )
        if left_word_override is not None:
            memory[left_target_address] = left_word_override
        if right_word_override is not None:
            memory[right_target_address] = right_word_override
        if left_code_word_override is not None:
            memory[left_target_address + 1] = left_code_word_override
        if right_code_word_override is not None:
            memory[right_target_address + 1] = right_code_word_override
        if memory_overrides is not None:
            for address, word in memory_overrides.items():
                memory[address] = word
        memory[19] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, left_address, 0, 0, 0, 0
        )
        memory[20] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, right_address, 0, 0, 0, 0
        )
        memory[21] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, lambdas_value, 0, 0, 0, 0
        )
        memory[22] = abi.pack_word(
            1, abi.MOP_INT, abi.DATA_SIGNED, descriptor, 0, 0, 0, 0
        )
        memory[23] = abi.pack_word(
            1,
            abi.MOP_PRIM_0,
            abi.DATA_LITERAL_ID,
            equal_star_child_id,
            1,
            0,
            0,
            0,
        )
        memory[24] = abi.pack_word(
            1, abi.MOP_APP, abi.DATA_SIGNED, 19, 0, 0, 0, 0
        )
        memory[25] = abi.pack_word(
            1, abi.MOP_JOIN, abi.DATA_SIGNED, 24, 0, 0, 1, 1
        )
        # These are the four live copied task arguments that make internal
        # argcnt==4 (encoded argcnt==5) and place the saved JOIN at fsp-4.
        memory[26] = memory[19]
        memory[27] = memory[20]
        memory[28] = memory[21]
        memory[29] = memory[22]

        controls = [0] * 256
        controls[0] = abi.pack_control_entry(
            abi.CONTROL_SAVED_QUANTUM, 9, 0, 0, 0
        )
        controls[1] = abi.pack_control_entry(
            abi.CONTROL_EQUALITY, 10, 18, 0, 0
        )
        controls[2] = abi.pack_control_entry(
            abi.CONTROL_SUBGRAPH, 256, free_space_value, equality_child_continue_id, 1
        )
        return EncodedArchitecturalState(
            memory=tuple(memory),
            control_stack=tuple(controls),
            pc=23,
            fsp=29,
            env=256,
            c=3,
            direction=abi.DIRECTION_FORWARD,
            q=9,
            phi=0,
            free_space=free_space_value,
            argcnt=argcnt_value,
            prim_id=0,
            fire=0,
            s_a=18,
            s_d=0,
            halted=0,
            pending_host_op=0,
            pending_host_argument=0,
        )

    def run_equalstar_child(
        *,
        left_target_value: int = 1,
        right_target_value: int = 1,
        descriptor: int = 1,
        left_address_value: int | None = None,
        right_address_value: int | None = None,
        argcnt_value: int = 5,
        lambdas_value: int = 0,
        left_word_override: int | None = None,
        right_word_override: int | None = None,
        left_code_word_override: int | None = None,
        right_code_word_override: int | None = None,
        memory_overrides: dict[int, int] | None = None,
        load_equal_if: bool = True,
        load_true: bool = True,
        load_false: bool = True,
        load_stuck: bool = True,
        free_space_value: int = 256,
        expect_fault: int | None = None,
    ):
        encoded = equalstar_child_encoded(
            left_target_value=left_target_value,
            right_target_value=right_target_value,
            descriptor=descriptor,
            left_address_value=left_address_value,
            right_address_value=right_address_value,
            argcnt_value=argcnt_value,
            lambdas_value=lambdas_value,
            left_word_override=left_word_override,
            right_word_override=right_word_override,
            left_code_word_override=left_code_word_override,
            right_code_word_override=right_code_word_override,
            memory_overrides=memory_overrides,
            free_space_value=free_space_value,
        )
        equal_if_child_id = 599
        processor = Red2Processor(
            encoded,
            true_literal_id=binary_true_id if load_true else 0,
            false_literal_id=binary_false_id if load_false else 0,
            equal_star_literal_id=equal_star_child_id,
            equal_if_literal_id=equal_if_child_id if load_equal_if else 0,
            equality_continue_literal_id=equality_child_continue_id,
            equal_stuck_literal_id=equal_stuck_child_id if load_stuck else 0,
        )
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        if expect_fault is None:
            assert processor.run_to_commit(), processor.fault
        else:
            assert not processor.run_to_commit()
            assert processor.fault == expect_fault
        expected = processor.checkpoint()

        _load_hardware(encoded)
        _load_literal_meta(
            33, equal_star_child_id, special_flags=LITERAL_SPECIAL_EQUAL_STAR
        )
        if load_true:
            _load_literal_meta(
                31, binary_true_id, special_flags=LITERAL_SPECIAL_TRUE
            )
        if load_false:
            _load_literal_meta(
                32, binary_false_id, special_flags=LITERAL_SPECIAL_FALSE
            )
        if load_stuck:
            _load_literal_meta(
                35, equal_stuck_child_id, special_flags=LITERAL_SPECIAL_EQUAL_STUCK
            )
        if load_equal_if:
            _load_literal_meta(
                36, equal_if_child_id, special_flags=LITERAL_SPECIAL_EQUAL_IF
            )
        result = None
        for _ in range(260):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT or int(result.committed):
                break
        else:
            raise AssertionError('__EQUAL_STAR__ CHILD_INIT did not terminate')
        assert result is not None
        if expect_fault is None:
            assert int(result.status) != STATUS_FAULT, (
                f'__EQUAL_STAR__ CHILD_INIT hardware faulted: '
                f'red2={int(result.red2_fault)} hw={int(result.hw_fault)} '
                f'micro={int(result.microstate)}'
            )
            assert int(result.committed)
        else:
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
        _assert_scalar_checkpoint(result, expected)
        for address, expected_word in enumerate(expected.memory):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_memory_read(result) == expected_word, (
                f'__EQUAL_STAR__ child memory mismatch at {address}'
            )
        for address, expected_entry in enumerate(expected.control_stack):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_control_read(result) == expected_entry, (
                f'__EQUAL_STAR__ child control mismatch at {address}'
            )
        if expect_fault is not None:
            assert expected.memory == initial_memory
            assert expected.control_stack == initial_control
        return expected

    equalstar_equal = run_equalstar_child()
    assert equalstar_equal.pc == 25
    assert equalstar_equal.fsp == 26
    assert equalstar_equal.direction == abi.DIRECTION_REVERSE
    assert equalstar_equal.q == 9
    assert equalstar_equal.argcnt == 2
    assert equalstar_equal.memory[26] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_true_id, 1, 0, 0, 0
    )

    equalstar_unequal = run_equalstar_child(right_target_value=2)
    assert equalstar_unequal.memory[26] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_false_id, 1, 0, 0, 0
    )

    # Descriptor zero compares the pointed-to words directly instead of first
    # interpreting APP/APP_VAR prefix descriptors.
    run_equalstar_child(descriptor=0)

    run_equalstar_child(
        argcnt_value=4, expect_fault=abi.FAULT_ILLEGAL_TRANSITION
    )
    run_equalstar_child(
        load_true=False, expect_fault=abi.FAULT_UNSUPPORTED_VALUE
    )
    run_equalstar_child(
        right_target_value=2,
        load_false=False,
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
    )

    def equality_child_word(opcode: int, payload: int, *, kind: int = abi.DATA_SIGNED):
        return abi.pack_word(1, opcode, kind, payload, 1, 0, 0, 0)

    equalstar_ubv_same = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_UBV, 7),
        right_word_override=equality_child_word(abi.MOP_UBV, 7),
    )
    assert abi.word_field(equalstar_ubv_same.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_true_id

    equalstar_ubv_stuck = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_UBV, 7),
        right_word_override=equality_child_word(abi.MOP_UBV, 8),
    )
    assert abi.word_field(equalstar_ubv_stuck.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == equal_stuck_child_id

    equalstar_var_same = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_VAR, 2),
        right_word_override=equality_child_word(abi.MOP_VAR, 2),
    )
    assert abi.word_field(equalstar_var_same.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_true_id

    equalstar_var_stuck = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_VAR, 2),
        right_word_override=equality_child_word(abi.MOP_VAR, 3),
        lambdas_value=0,
    )
    assert abi.word_field(equalstar_var_stuck.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == equal_stuck_child_id

    equalstar_var_false = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_VAR, 2),
        right_word_override=equality_child_word(abi.MOP_VAR, 3),
        lambdas_value=3,
    )
    assert abi.word_field(equalstar_var_false.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_false_id

    equalstar_ep_same = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_EP, 40),
        right_word_override=equality_child_word(abi.MOP_EP, 40),
    )
    assert abi.word_field(equalstar_ep_same.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_true_id

    equalstar_ep_stuck = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_EP, 40),
        right_word_override=equality_child_word(abi.MOP_EP, 41),
    )
    assert abi.word_field(equalstar_ep_stuck.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == equal_stuck_child_id

    equalstar_opcode_false = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_PNP, 40),
        right_word_override=equality_child_word(abi.MOP_REC, 41),
    )
    assert abi.word_field(equalstar_opcode_false.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_false_id

    run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_UBV, 7),
        right_word_override=equality_child_word(abi.MOP_UBV, 8),
        load_stuck=False,
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
    )

    def equality_closure_code(payload: int, *, kind: int = abi.DATA_SIGNED):
        return abi.pack_word(1, abi.MOP_NONE, kind, payload, 0, 0, 0, 0)

    equalstar_closure_equal = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        right_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        left_code_word_override=equality_closure_code(12),
        right_code_word_override=equality_closure_code(12),
    )
    assert abi.word_field(equalstar_closure_equal.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_true_id

    equalstar_closure_env_mismatch = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        right_word_override=equality_child_word(abi.MOP_CLOSURE, 8),
        left_code_word_override=equality_closure_code(12),
        right_code_word_override=equality_closure_code(12),
    )
    assert abi.word_field(equalstar_closure_env_mismatch.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_false_id

    equalstar_closure_code_mismatch = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        right_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        left_code_word_override=equality_closure_code(12),
        right_code_word_override=equality_closure_code(13),
    )
    assert abi.word_field(equalstar_closure_code_mismatch.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_false_id

    equalstar_one_closure = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        right_word_override=equality_child_word(abi.MOP_RBLOCK, 0),
        left_code_word_override=equality_closure_code(12),
    )
    assert abi.word_field(equalstar_one_closure.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_false_id

    run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        right_word_override=equality_child_word(abi.MOP_CLOSURE, 7),
        left_code_word_override=equality_child_word(abi.MOP_INT, 12),
        right_code_word_override=equality_closure_code(12),
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )

    equalstar_closure_nonsigned_none = run_equalstar_child(
        descriptor=0,
        left_word_override=equality_child_word(abi.MOP_CLOSURE, 7, kind=abi.DATA_LITERAL_ID),
        right_word_override=equality_child_word(abi.MOP_CLOSURE, 9, kind=abi.DATA_LITERAL_ID),
        left_code_word_override=equality_closure_code(12, kind=abi.DATA_LITERAL_ID),
        right_code_word_override=equality_closure_code(13, kind=abi.DATA_LITERAL_ID),
    )
    assert abi.word_field(equalstar_closure_nonsigned_none.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_true_id

    # STRUCT equality scans contiguous field descriptors through a signed VAR 0
    # terminator.  Empty structures resolve immediately; one field reuses the
    # recursive child writer with descriptor=1 and lambdas+1.
    struct_literal_id = 700
    struct_word = equality_child_word(
        abi.MOP_STRUCT, struct_literal_id, kind=abi.DATA_LITERAL_ID
    )
    struct_field = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0
    )
    struct_end = abi.pack_word(
        1, abi.MOP_VAR, abi.DATA_SIGNED, 0, 0, 0, 0, 0
    )

    equalstar_struct_empty = run_equalstar_child(
        descriptor=0,
        left_address_value=40,
        right_address_value=50,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={41: struct_end, 51: struct_end},
    )
    assert equalstar_struct_empty.pc == 25
    assert equalstar_struct_empty.fsp == 26
    assert equalstar_struct_empty.direction == abi.DIRECTION_REVERSE
    assert abi.word_field(
        equalstar_struct_empty.memory[26], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS
    ) == binary_true_id

    equalstar_struct_count_mismatch = run_equalstar_child(
        descriptor=0,
        left_address_value=40,
        right_address_value=50,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={41: struct_field, 42: struct_end, 51: struct_end},
    )
    assert abi.word_field(
        equalstar_struct_count_mismatch.memory[26],
        abi.WORD_PAYLOAD_SHIFT,
        abi.WORD_PAYLOAD_BITS,
    ) == binary_false_id

    equalstar_struct_one = run_equalstar_child(
        descriptor=0,
        left_address_value=40,
        right_address_value=50,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={
            41: struct_field, 42: struct_end,
            51: struct_field, 52: struct_end,
        },
    )
    assert equalstar_struct_one.pc == 32
    assert equalstar_struct_one.fsp == 36
    assert equalstar_struct_one.direction == abi.DIRECTION_FORWARD
    assert equalstar_struct_one.argcnt == 1
    assert equalstar_struct_one.memory[25] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 41, 0, 0, 0, 0
    )
    assert equalstar_struct_one.memory[26] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 51, 0, 0, 0, 0
    )
    assert equalstar_struct_one.memory[27] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 1, 0, 0, 0, 0
    )
    assert equalstar_struct_one.memory[28] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 1, 0, 0, 0, 0
    )
    assert abi.word_field(
        equalstar_struct_one.memory[29], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS
    ) == equal_star_child_id
    assert abi.word_field(
        equalstar_struct_one.memory[35], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS
    ) == 599
    assert equalstar_struct_one.memory[36] == abi.pack_word(
        1, abi.MOP_JOIN, abi.DATA_SIGNED, 24, 0, 0, 1, 1
    )

    # Multi-field STRUCTs use the same recursive builder for every field.
    # Keep source descriptors above the private build region: two fields end
    # at graph word 45 and three fields at graph word 54.
    equalstar_struct_two = run_equalstar_child(
        descriptor=0,
        left_address_value=100,
        right_address_value=110,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={
            101: struct_field, 102: struct_field, 103: struct_end,
            111: struct_field, 112: struct_field, 113: struct_end,
        },
    )
    assert equalstar_struct_two.pc == 41
    assert equalstar_struct_two.fsp == 45
    assert equalstar_struct_two.direction == abi.DIRECTION_FORWARD
    assert equalstar_struct_two.argcnt == 1

    equalstar_struct_three = run_equalstar_child(
        descriptor=0,
        left_address_value=100,
        right_address_value=110,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={
            101: struct_field, 102: struct_field, 103: struct_field, 104: struct_end,
            111: struct_field, 112: struct_field, 113: struct_field, 114: struct_end,
        },
    )
    assert equalstar_struct_three.pc == 50
    assert equalstar_struct_three.fsp == 54
    assert equalstar_struct_three.direction == abi.DIRECTION_FORWARD
    assert equalstar_struct_three.argcnt == 1

    # Whole-build preflight is failure-atomic at the exact two-child boundary.
    run_equalstar_child(
        descriptor=0,
        left_address_value=100,
        right_address_value=110,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={
            101: struct_field, 102: struct_field, 103: struct_end,
            111: struct_field, 112: struct_field, 113: struct_end,
        },
        free_space_value=45,
        expect_fault=abi.FAULT_GRAPH_ENV_COLLISION,
    )

    malformed_struct_end = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 0, 1, 0, 0, 0
    )
    run_equalstar_child(
        descriptor=0,
        left_address_value=40,
        right_address_value=50,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={41: malformed_struct_end, 51: struct_end},
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )

    run_equalstar_child(
        descriptor=0,
        left_address_value=40,
        right_address_value=50,
        left_word_override=struct_word,
        right_word_override=struct_word,
        memory_overrides={
            41: struct_field, 42: struct_end,
            51: struct_field, 52: struct_end,
        },
        free_space_value=36,
        expect_fault=abi.FAULT_GRAPH_ENV_COLLISION,
    )

    # Recursive application equality scans both contiguous APP-prefixes, then
    # compares the terminal operator first and each prefix descriptor backwards.
    app_head = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0
    )
    app_target = abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 9, 1, 0, 0, 0
    )
    app_left = abi.pack_word(
        1, abi.MOP_APP, abi.DATA_SIGNED, 120, 0, 0, 0, 0
    )
    app_right = abi.pack_word(
        1, abi.MOP_APP, abi.DATA_SIGNED, 130, 0, 0, 0, 0
    )
    equalstar_app = run_equalstar_child(
        descriptor=0,
        left_address_value=100,
        right_address_value=110,
        left_word_override=app_left,
        right_word_override=app_right,
        memory_overrides={
            101: app_head, 111: app_head,
            120: app_target, 130: app_target,
        },
    )
    assert equalstar_app.pc == 41
    assert equalstar_app.fsp == 45
    assert equalstar_app.direction == abi.DIRECTION_FORWARD
    assert equalstar_app.argcnt == 1

    app_var = abi.pack_word(
        1, abi.MOP_APP_VAR, abi.DATA_SIGNED, 3, 0, 0, 0, 0
    )
    equalstar_app_var = run_equalstar_child(
        descriptor=0,
        left_address_value=100,
        right_address_value=110,
        left_word_override=app_var,
        right_word_override=app_var,
        memory_overrides={101: app_head, 111: app_head},
    )
    assert equalstar_app_var.pc == 41
    assert equalstar_app_var.fsp == 45
    assert equalstar_app_var.direction == abi.DIRECTION_FORWARD

    # Descriptor-mode APP_VAR is normalized to a head VAR rather than treated
    # as an unsupported hardware case.
    equalstar_descriptor_app_var = run_equalstar_child(
        descriptor=1,
        memory_overrides={10: app_var, 11: app_var},
    )
    assert abi.word_field(
        equalstar_descriptor_app_var.memory[26],
        abi.WORD_PAYLOAD_SHIFT,
        abi.WORD_PAYLOAD_BITS,
    ) == binary_true_id

    # Whole recursive APP build preflights all child tasks and IF wrappers.
    run_equalstar_child(
        descriptor=0,
        left_address_value=100,
        right_address_value=110,
        left_word_override=app_left,
        right_word_override=app_right,
        memory_overrides={
            101: app_head, 111: app_head,
            120: app_target, 130: app_target,
        },
        free_space_value=45,
        expect_fault=abi.FAULT_GRAPH_ENV_COLLISION,
    )

    # Paired LAMBDAs recurse by stripping binders, increasing the bound-variable
    # depth, then rebuilding one private child plus TRUE/FALSE/__EQUAL_IF__/JOIN.
    lambda_word = equality_child_word(abi.MOP_LAMBDA, 0)
    lambda_body_left = equality_child_word(abi.MOP_VAR, 0, kind=abi.DATA_SIGNED)
    lambda_body_right = equality_child_word(abi.MOP_VAR, 0, kind=abi.DATA_SIGNED)
    equalstar_lambda = run_equalstar_child(
        descriptor=0,
        left_word_override=lambda_word,
        right_word_override=lambda_word,
        memory_overrides={15: lambda_body_left, 18: lambda_body_right},
    )
    assert equalstar_lambda.pc == 32
    assert equalstar_lambda.fsp == 36
    assert equalstar_lambda.direction == abi.DIRECTION_FORWARD
    assert equalstar_lambda.q == 9
    assert equalstar_lambda.argcnt == 1
    assert equalstar_lambda.memory[25] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 15, 0, 0, 0, 0
    )
    assert equalstar_lambda.memory[26] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 18, 0, 0, 0, 0
    )
    assert equalstar_lambda.memory[27] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 1, 0, 0, 0, 0
    )
    assert equalstar_lambda.memory[28] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 0, 0, 0, 0, 0
    )
    assert abi.word_field(equalstar_lambda.memory[29], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == equal_star_child_id
    assert abi.word_field(equalstar_lambda.memory[30], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_true_id
    assert abi.word_field(equalstar_lambda.memory[31], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == binary_false_id
    assert equalstar_lambda.memory[32] == abi.pack_word(
        1, abi.MOP_APP, abi.DATA_SIGNED, 31, 0, 0, 0, 0
    )
    assert equalstar_lambda.memory[33] == abi.pack_word(
        1, abi.MOP_APP, abi.DATA_SIGNED, 30, 0, 0, 0, 0
    )
    assert equalstar_lambda.memory[34] == abi.pack_word(
        1, abi.MOP_APP, abi.DATA_SIGNED, 25, 0, 0, 0, 0
    )
    assert abi.word_field(equalstar_lambda.memory[35], abi.WORD_PAYLOAD_SHIFT, abi.WORD_PAYLOAD_BITS) == 599
    assert equalstar_lambda.memory[36] == abi.pack_word(
        1, abi.MOP_JOIN, abi.DATA_SIGNED, 24, 0, 0, 1, 1
    )

    run_equalstar_child(
        descriptor=0,
        left_word_override=lambda_word,
        right_word_override=lambda_word,
        memory_overrides={15: lambda_body_left, 18: lambda_body_right},
        load_equal_if=False,
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
    )

    # Nested binder depth must be walked in lockstep.  If only one side remains
    # a LAMBDA after stripping the shared outer binder, structural equality is FALSE.
    nested_lambda_false = run_equalstar_child(
        descriptor=0,
        left_word_override=lambda_word,
        right_word_override=lambda_word,
        memory_overrides={
            15: lambda_word,
            18: equality_child_word(abi.MOP_INT, 7),
        },
    )
    assert nested_lambda_false.pc == 25
    assert nested_lambda_false.fsp == 26
    assert nested_lambda_false.direction == abi.DIRECTION_REVERSE
    assert nested_lambda_false.argcnt == 2
    assert abi.word_field(
        nested_lambda_false.memory[26],
        abi.WORD_PAYLOAD_SHIFT,
        abi.WORD_PAYLOAD_BITS,
    ) == binary_false_id

    # The recursive rebuild needs addresses join..join+11.  With free_space==36
    # the final slot collides exactly at the boundary; both oracle and hardware
    # must fault before replacing the saved JOIN or writing any child graph word.
    run_equalstar_child(
        descriptor=0,
        left_word_override=lambda_word,
        right_word_override=lambda_word,
        memory_overrides={15: lambda_body_left, 18: lambda_body_right},
        free_space_value=36,
        expect_fault=abi.FAULT_GRAPH_ENV_COLLISION,
    )

    # T22: the returned child boolean reaches the saved JOIN with
    # __EQUALITY_CONTINUE__ fire==1.  The continuation must atomically publish the
    # non-head child at the private parent, publish the headed answer at the
    # original EQUAL? result slot, clear SUBGRAPH/EQUALITY/SAVED_QUANTUM, and
    # restore the saved quantum in one architectural commit.
    def equality_continue_encoded(
        child_id: int,
        *,
        equality_tag: int = abi.CONTROL_EQUALITY,
        quantum_tag: int = abi.CONTROL_SAVED_QUANTUM,
    ):
        encoded = equalstar_child_encoded()
        memory = list(encoded.memory)
        memory[26] = abi.pack_word(
            1, abi.MOP_SYM, abi.DATA_LITERAL_ID, child_id, 1, 0, 0, 0
        )
        controls = list(encoded.control_stack)
        controls[0] = abi.pack_control_entry(quantum_tag, 9, 0, 0, 0)
        controls[1] = abi.pack_control_entry(equality_tag, 10, 18, 0, 0)
        controls[2] = abi.pack_control_entry(
            abi.CONTROL_SUBGRAPH, 256, 256, equality_child_continue_id, 1
        )
        return replace(
            encoded,
            memory=tuple(memory),
            control_stack=tuple(controls),
            pc=25,
            fsp=26,
            c=3,
            direction=abi.DIRECTION_REVERSE,
            q=9,
            argcnt=2,
            prim_id=0,
            fire=0,
            s_a=27,
        )

    def run_equality_continue(
        child_id: int,
        *,
        equality_tag: int = abi.CONTROL_EQUALITY,
        quantum_tag: int = abi.CONTROL_SAVED_QUANTUM,
        load_true: bool = True,
        load_false: bool = True,
        load_stuck: bool = True,
        expect_fault: int | None = None,
    ):
        encoded = equality_continue_encoded(
            child_id,
            equality_tag=equality_tag,
            quantum_tag=quantum_tag,
        )
        processor = Red2Processor(
            encoded,
            true_literal_id=binary_true_id if load_true else 0,
            false_literal_id=binary_false_id if load_false else 0,
            equal_star_literal_id=equal_star_child_id,
            equality_continue_literal_id=equality_child_continue_id,
            equal_stuck_literal_id=equal_stuck_child_id if load_stuck else 0,
        )
        initial_memory = tuple(encoded.memory)
        initial_control = tuple(encoded.control_stack)
        if expect_fault is None:
            assert processor.run_to_commit(), processor.fault
        else:
            assert not processor.run_to_commit()
            assert processor.fault == expect_fault
        expected = processor.checkpoint()

        _load_hardware(encoded)
        _load_literal_meta(
            34,
            equality_child_continue_id,
            special_flags=LITERAL_SPECIAL_EQUALITY_CONTINUE,
        )
        if load_true:
            _load_literal_meta(
                31, binary_true_id, special_flags=LITERAL_SPECIAL_TRUE
            )
        if load_false:
            _load_literal_meta(
                32, binary_false_id, special_flags=LITERAL_SPECIAL_FALSE
            )
        if load_stuck:
            _load_literal_meta(
                35, equal_stuck_child_id, special_flags=LITERAL_SPECIAL_EQUAL_STUCK
            )

        result = None
        for _ in range(360):
            result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            if int(result.status) == STATUS_FAULT or int(result.committed):
                break
        else:
            raise AssertionError('__EQUALITY_CONTINUE__ T22 did not terminate')
        assert result is not None
        if expect_fault is None:
            assert int(result.status) != STATUS_FAULT, (
                f'__EQUALITY_CONTINUE__ hardware faulted: '
                f'red2={int(result.red2_fault)} hw={int(result.hw_fault)} '
                f'micro={int(result.microstate)}'
            )
            assert int(result.committed)
        else:
            assert int(result.status) == STATUS_FAULT
            assert int(result.red2_fault) == expect_fault
            assert int(result.hw_fault) == HW_FAULT_NONE
        _assert_scalar_checkpoint(result, expected)
        for address, expected_word in enumerate(expected.memory):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_memory_read(result) == expected_word, (
                f'__EQUALITY_CONTINUE__ memory mismatch at {address}'
            )
        for address, expected_entry in enumerate(expected.control_stack):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_control_read(result) == expected_entry, (
                f'__EQUALITY_CONTINUE__ control mismatch at {address}'
            )
        if expect_fault is not None:
            assert expected.memory == initial_memory
            assert expected.control_stack == initial_control
        return expected

    equality_continue_true = run_equality_continue(binary_true_id)
    assert equality_continue_true.pc == 9
    assert equality_continue_true.fsp == 10
    assert equality_continue_true.c == 0
    assert equality_continue_true.direction == abi.DIRECTION_REVERSE
    assert equality_continue_true.q == 9
    assert equality_continue_true.argcnt == 2
    assert equality_continue_true.prim_id == 0
    assert equality_continue_true.fire == 0
    assert equality_continue_true.s_a == 27
    assert equality_continue_true.memory[10] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_true_id, 1, 0, 0, 0
    )
    assert equality_continue_true.memory[24] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_true_id, 0, 0, 0, 0
    )
    assert equality_continue_true.control_stack[:3] == (0, 0, 0)

    equality_continue_false = run_equality_continue(binary_false_id)
    assert equality_continue_false.memory[10] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_false_id, 1, 0, 0, 0
    )
    assert equality_continue_false.memory[24] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, binary_false_id, 0, 0, 0, 0
    )

    equality_continue_stuck = run_equality_continue(equal_stuck_child_id)
    assert equality_continue_stuck.pc == 9
    assert equality_continue_stuck.fsp == 18
    assert equality_continue_stuck.c == 0
    assert equality_continue_stuck.direction == abi.DIRECTION_REVERSE
    assert equality_continue_stuck.q == 9
    assert equality_continue_stuck.argcnt == 2
    assert equality_continue_stuck.prim_id == 0
    assert equality_continue_stuck.fire == 0
    assert equality_continue_stuck.s_a == 27
    # STUCK must leave the original equality result slot untouched.  This
    # fixture inherits the pre-existing APP at address 10 from equalstar_child_encoded().
    assert equality_continue_stuck.memory[10] == equality_continue_encoded(
        equal_stuck_child_id
    ).memory[10]
    assert equality_continue_stuck.memory[24] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, equal_stuck_child_id, 0, 0, 0, 0
    )
    assert equality_continue_stuck.memory[26] == abi.pack_word(
        1, abi.MOP_SYM, abi.DATA_LITERAL_ID, equal_stuck_child_id, 1, 0, 0, 0
    )
    assert equality_continue_stuck.control_stack[:3] == (0, 0, 0)

    run_equality_continue(
        equal_stuck_child_id,
        load_stuck=False,
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )

    run_equality_continue(
        binary_true_id,
        load_true=False,
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )
    run_equality_continue(
        binary_false_id,
        load_false=False,
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )
    run_equality_continue(999, expect_fault=abi.FAULT_ILLEGAL_TRANSITION)
    run_equality_continue(
        binary_true_id,
        equality_tag=abi.CONTROL_ADDRESS,
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )
    run_equality_continue(
        binary_true_id,
        quantum_tag=abi.CONTROL_ADDRESS,
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
    )

    direct_stuck = run_direct_scalar(
        SCALAR_OP_ADD,
        523,
        sint(1, head=1),
        left=abi.pack_word(
            1, abi.MOP_CHAR, abi.DATA_LITERAL_ID, ord('A'), 0, 0, 0, 0
        ),
    )
    assert direct_stuck.pc == 2 and direct_stuck.fsp == 4 and direct_stuck.q == 8
    assert direct_stuck.prim_id == 0 and direct_stuck.fire == 0

    direct_overflow = run_direct_scalar(
        SCALAR_OP_ADD,
        541,
        sint(1, head=1),
        left=sint((1 << 63) - 1),
        expect_fault=abi.FAULT_UNSUPPORTED_VALUE,
    )
    assert direct_overflow.prim_id == 541 and direct_overflow.fire == 0

    direct_qzero = run_direct_scalar(
        SCALAR_OP_INC, 547, sint(2, head=1), q_value=0
    )
    assert direct_qzero.pc == 2 and direct_qzero.fsp == 3 and direct_qzero.q == 0
    assert direct_qzero.prim_id == 0 and direct_qzero.fire == 0
    assert direct_qzero.memory[3] == sint(2, head=1)

    direct_unknown = run_direct_scalar(
        SCALAR_OP_NONE,
        557,
        sint(2, head=1),
        q_value=0,
        expect_fault=abi.FAULT_ILLEGAL_TRANSITION,
        load_metadata=False,
    )
    assert direct_unknown.prim_id == 557 and direct_unknown.fire == 0

    direct_countdown = direct_fire_encoded(563, 2, sint(2, head=1))
    countdown_processor = Red2Processor(direct_countdown)
    assert countdown_processor.run_to_commit()
    countdown_expected = countdown_processor.checkpoint()
    _load_hardware(direct_countdown)
    countdown_result = None
    for _ in range(8):
        countdown_result = sim_call(red2_processor_top, _command(CMD_CLOCK))
        if int(countdown_result.committed):
            break
    else:
        raise AssertionError("direct fire>1 countdown did not commit")
    assert countdown_result is not None
    _assert_scalar_checkpoint(countdown_result, countdown_expected)
    assert countdown_expected.pc == 2
    assert countdown_expected.prim_id == 563 and countdown_expected.fire == 1
    countdown_result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(countdown_result) == countdown_expected.memory[3]

    # JOIN searches downward through a contiguous SAVED_DEFINITION_PATH suffix
    # without mutating control RAM.  On success it clears that suffix plus the
    # SUBGRAPH frame; entries below the frame survive.  Malformed searches are
    # failure-atomic.
    def join_with_control_stack(entries: list[int]):
        encoded = simple_join_encoded(
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
            abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 41, 1, 0, 0, 0),
            parent_address=3,
            join_address=4,
            result_address=5,
            env=28,
            free_space=28,
            frame_env=32,
            frame_free_space=32,
            memory_words=64,
        )
        control = list(encoded.control_stack)
        for i in range(len(control)):
            control[i] = 0
        for i, entry in enumerate(entries):
            control[i] = entry
        return replace(encoded, control_stack=tuple(control), c=len(entries))

    saved17 = abi.pack_control_entry(
        abi.CONTROL_SAVED_DEFINITION_PATH, 17, 0, 0, 0
    )
    saved23 = abi.pack_control_entry(
        abi.CONTROL_SAVED_DEFINITION_PATH, 23, 0, 0, 0
    )
    frame32 = abi.pack_control_entry(
        abi.CONTROL_SUBGRAPH, 32, 32, 0, 0
    )
    lower_saved = abi.pack_control_entry(
        abi.CONTROL_SAVED_DEFINITION_PATH, 7, 0, 0, 0
    )
    wrong_address = abi.pack_control_entry(
        abi.CONTROL_ADDRESS, 9, 0, 0, 0
    )

    for saved_case in (
        join_with_control_stack([frame32, saved17]),
        join_with_control_stack([frame32, saved17, saved23]),
        join_with_control_stack([lower_saved, frame32]),
    ):
        result, expected = _run_encoded_to_same_commit(saved_case)
        for address in (3, 5):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]
        for control_address in range(3):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=control_address)
            )
            assert _packed_control_read(result) == expected.control_stack[control_address], (
                f"JOIN saved-definition control mismatch at {control_address}"
            )

    for malformed_saved_case in (
        join_with_control_stack([saved17]),
        join_with_control_stack([wrong_address, saved17]),
        join_with_control_stack([frame32, wrong_address]),
    ):
        initial_memory = tuple(malformed_saved_case.memory)
        initial_control = tuple(malformed_saved_case.control_stack)
        result, expected, fault = _run_encoded_to_same_fault(malformed_saved_case)
        assert fault == abi.FAULT_ILLEGAL_TRANSITION
        for address in (3, 5):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == initial_memory[address]
        for control_address in range(3):
            result = sim_call(
                red2_processor_top, _command(CMD_NOP, address=control_address)
            )
            assert _packed_control_read(result) == initial_control[control_address]

    # Flat multiword JOIN publication preserves already graph-owned inline
    # application prefixes in place and publishes APP(result_root).
    def flat_join_encoded(words: list[int]):
        encoded = simple_join_encoded(
            abi.pack_word(1, abi.MOP_APP, abi.DATA_SIGNED, 9, 0, 0, 0, 0),
            words[0],
            parent_address=3,
            join_address=4,
            result_address=5,
            env=28,
            free_space=28,
            frame_env=32,
            frame_free_space=32,
        )
        memory = list(encoded.memory)
        for offset, word in enumerate(words):
            memory[5 + offset] = word
        return replace(encoded, memory=tuple(memory), fsp=4 + len(words))

    flat_two_int = flat_join_encoded([
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 42, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0),
    ])
    result, expected = _run_encoded_to_same_commit(flat_two_int)
    assert expected.pc == 2
    assert expected.fsp == 6
    assert expected.env == 32
    assert expected.free_space == 32
    assert expected.s_a == 6
    for address in (3, 5, 6):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    flat_three_int = flat_join_encoded([
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 1, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 3, 1, 0, 0, 0),
    ])
    result, expected = _run_encoded_to_same_commit(flat_three_int)
    assert expected.fsp == 7
    for address in (3, 5, 6, 7):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    flat_int_sym = flat_join_encoded([
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 7, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_SYM, abi.DATA_LITERAL_ID, 77, 1, 0, 1, 12),
    ])
    result, expected = _run_encoded_to_same_commit(flat_int_sym)
    for address in (3, 5, 6):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    # A head inline root is already a complete publication root even when fsp
    # extends beyond it; the extra suffix is not scanned or compacted.
    flat_head_root = flat_join_encoded([
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 1, 1, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 1, 0, 0, 0),
    ])
    result, expected = _run_encoded_to_same_commit(flat_head_root)
    assert expected.fsp == 6
    for address in (3, 5, 6):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    # An unterminated inline prefix is intentionally still outside this hardware
    # slice.  It must fail as an implementation gap without publishing/clearing.
    flat_unterminated = flat_join_encoded([
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 1, 0, 0, 0, 0),
        abi.pack_word(1, abi.MOP_INT, abi.DATA_SIGNED, 2, 0, 0, 0, 0),
    ])
    _load_hardware(flat_unterminated)
    flat_unterminated_result = None
    for _ in range(32):
        flat_unterminated_result = sim_call(
            red2_processor_top, _command(CMD_CLOCK)
        )
        if int(flat_unterminated_result.status) == STATUS_FAULT:
            break
    else:
        raise AssertionError("unterminated flat JOIN failed to reach hardware fault")
    assert int(flat_unterminated_result.red2_fault) == abi.FAULT_NONE
    assert int(flat_unterminated_result.hw_fault) == HW_FAULT_EXECUTION_NOT_IMPLEMENTED
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=3))
    assert _packed_memory_read(result) == flat_unterminated.memory[3]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == flat_unterminated.control_stack[0]

    # End-to-end nested generated subgraphs: keep one hardware instance live
    # across all seven semantic commits so APP entry, generated JOINs, inner
    # atomic compaction, and outer flat multiword publication compose exactly.
    nested_memory: list[Word | None] = [None] * 64
    nested_memory[0] = Word(MuredOpcode.INT, 0, False)
    nested_memory[1] = Word(MuredOpcode.APP, 8, False)
    nested_memory[2] = Word(MuredOpcode.INT, 1, True)
    nested_memory[8] = Word(MuredOpcode.APP, 12, False)
    nested_memory[9] = Word(MuredOpcode.INT, 7, True)
    nested_memory[12] = Word(MuredOpcode.INT, 42, True)
    nested_state = MuredMachineState(
        memory=nested_memory,
        control_stack=[None] * 32,
        pc=1,
        fsp=2,
        env=64,
        c=0,
        direction=Direction.B,
        q=64,
        phi=0,
        free_space=64,
        argcnt=0,
    )
    nested_state.control_stack[0] = 64
    nested_encoded = RED2ABICodec().encode_state(nested_state)
    nested_oracle = Red2Processor(nested_encoded)
    _load_hardware(nested_encoded)

    nested_expected_boundaries = [
        (8, 3, 1, abi.DIRECTION_FORWARD),
        (9, 4, 2, abi.DIRECTION_FORWARD),
        (4, 5, 2, abi.DIRECTION_REVERSE),
        (12, 6, 2, abi.DIRECTION_FORWARD),
        (6, 7, 2, abi.DIRECTION_REVERSE),
        (3, 5, 1, abi.DIRECTION_REVERSE),
        (0, 5, 0, abi.DIRECTION_REVERSE),
    ]
    for commit_index, (expected_pc, expected_fsp, expected_c, expected_direction) in enumerate(
        nested_expected_boundaries
    ):
        assert nested_oracle.run_to_commit(), (
            f"nested oracle failed before commit {commit_index}: "
            f"fault={nested_oracle.fault}"
        )
        nested_expected = nested_oracle.checkpoint()
        nested_result = None
        for _ in range(32):
            nested_result = sim_call(red2_processor_top, _command(CMD_CLOCK))
            assert int(nested_result.status) != STATUS_FAULT, (
                f"nested hardware fault before commit {commit_index}: "
                f"red2={int(nested_result.red2_fault)} "
                f"hw={int(nested_result.hw_fault)} "
                f"micro={int(nested_result.microstate)}"
            )
            if int(nested_result.committed):
                break
        else:
            raise AssertionError(
                f"nested hardware failed to commit boundary {commit_index}"
            )
        assert nested_result is not None
        _assert_scalar_checkpoint(nested_result, nested_expected)
        assert int(nested_result.pc) == expected_pc
        assert int(nested_result.fsp) == expected_fsp
        assert int(nested_result.control_top) == expected_c
        assert int(nested_result.direction) == expected_direction

        # Compare all graph words touched by the nested sequence at every
        # boundary, not merely the final parent.
        for address in (1, 3, 4, 5, 6, 7, 8, 9, 12):
            nested_read = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_memory_read(nested_read) == nested_expected.memory[address], (
                f"nested memory mismatch after commit {commit_index} "
                f"at {address}"
            )
        for address in (0, 1, 2):
            nested_control = sim_call(
                red2_processor_top, _command(CMD_NOP, address=address)
            )
            assert _packed_control_read(nested_control) == nested_expected.control_stack[address], (
                f"nested control mismatch after commit {commit_index} "
                f"at {address}"
            )

    nested_final = nested_oracle.checkpoint()
    assert nested_final.memory[1] == abi.pack_word(
        1, abi.MOP_APP, abi.DATA_SIGNED, 4, 0, 0, 0, 0
    )
    assert nested_final.memory[4] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 42, 0, 0, 0, 0
    )
    assert nested_final.memory[5] == abi.pack_word(
        1, abi.MOP_INT, abi.DATA_SIGNED, 7, 1, 0, 0, 0
    )

    # UBV forward at zero quantum still performs ordinary reconstruction: it
    # publishes VAR(phi-binder), reverses, and commits without consuming q.
    codec = RED2ABICodec()
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 32,
        pc=0,
        fsp=1,
        env=64,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=3,
        argcnt=0,
    )
    state.memory[0] = Word(MuredOpcode.UBV, 1, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    result, expected = _run_one_commit(machine, codec)
    assert int(result.q) == 0
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.fsp),
    )
    assert _packed_memory_read(result) == expected.memory[expected.fsp]

    # Reverse LAMBDA is the plain phi/pc spine transition.
    codec = RED2ABICodec()
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.LAMBDA, "x", True)],
        quantum=8,
        memory_words=64,
        control_words=32,
    )
    machine.state.direction = Direction.B
    machine.state.pc = 1
    machine.state.phi = 2
    _run_one_commit(machine, codec)

    # Ordinary reverse STOP with no saved-definition-path entries increments pc,
    # sets halted, then commits.  Definition-path cleanup is a later Task-5 slice.
    codec = RED2ABICodec()
    machine = MuredMachine.load(
        [Word(MuredOpcode.INT, 1, True)],
        quantum=8,
        memory_words=64,
        control_words=32,
    )
    machine.state.pc = 1
    machine.state.direction = Direction.B
    machine.state.memory[2] = Word(MuredOpcode.INT, 0, False)
    result, expected = _run_one_commit(machine, codec)
    assert expected.halted == 1
    assert int(result.halted) == 1

    # Direct VAR -> shareable atomic.  The oracle's Task-4 shadow transaction is
    # deliberately slower than this hardware subset, so compare committed state
    # and publication rather than individual micro-clocks.
    codec = RED2ABICodec()
    machine = _direct_lookup_machine(MuredOpcode.VAR, Word(MuredOpcode.INT, 42))
    result, expected = _run_bounded_to_same_commit(machine, codec)
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.fsp),
    )
    assert _packed_memory_read(result) == expected.memory[expected.fsp]

    # Direct VAR -> UBV does not detach the UBV.  It records the lookup address
    # and redirects pc to the environment cell itself.
    codec = RED2ABICodec()
    machine = _direct_lookup_machine(MuredOpcode.VAR, Word(MuredOpcode.UBV, 2))
    _, expected = _run_bounded_to_same_commit(machine, codec)
    assert expected.pc == 10
    assert expected.fsp == 1

    # Direct APP_VAR -> shareable atomic publishes a detached non-head value and
    # advances the source pc.
    codec = RED2ABICodec()
    machine = _direct_lookup_machine(
        MuredOpcode.APP_VAR,
        Word(MuredOpcode.CHAR, "q", True, closure_slot=True),
    )
    result, expected = _run_bounded_to_same_commit(machine, codec)
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.fsp),
    )
    assert _packed_memory_read(result) == expected.memory[expected.fsp]

    # Direct APP_VAR -> UBV rewrites to APP_VAR(phi-binder), preserving the
    # ordinary forward direction and publishing s_a/s_d from the completed lookup.
    codec = RED2ABICodec()
    machine = _direct_lookup_machine(
        MuredOpcode.APP_VAR,
        Word(MuredOpcode.UBV, 2),
        phi=5,
    )
    result, expected = _run_bounded_to_same_commit(machine, codec)
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.fsp),
    )
    assert _packed_memory_read(result) == expected.memory[expected.fsp]

    # Negative lookup indices fault before Task-4 begins and must not publish.
    codec = RED2ABICodec()
    machine = _direct_lookup_machine(
        MuredOpcode.VAR,
        Word(MuredOpcode.INT, 1),
        index=-1,
    )
    _assert_hardware_fault_without_publication(
        machine,
        codec,
        expected_red2_fault=FAULT_INVALID_ADDRESS,
    )

    # An empty direct environment cell is an invalid address in both machines.
    codec = RED2ABICodec()
    machine = _direct_lookup_machine(MuredOpcode.APP_VAR, None)
    _assert_hardware_fault_without_publication(
        machine,
        codec,
        expected_red2_fault=FAULT_INVALID_ADDRESS,
    )

    # Publication is preflighted against the graph/environment frontier.  A
    # valid binding at env=2 with fsp=1 leaves no result slot and must fault
    # without overwriting that environment binding.
    codec = RED2ABICodec()
    machine = _direct_lookup_machine(
        MuredOpcode.VAR,
        Word(MuredOpcode.INT, 9),
        env=2,
        free_space=2,
    )
    _assert_hardware_fault_without_publication(
        machine,
        codec,
        expected_red2_fault=FAULT_GRAPH_ENV_COLLISION,
    )

    # Nonzero lexical lookup walks the environment rather than approximating
    # index zero.  Verify contiguous APP_VAR lookup first.
    codec = RED2ABICodec()
    lookup_memory: list[Word | None] = [None] * 64
    lookup_memory[0] = Word(MuredOpcode.APP_VAR, 1, True)
    lookup_memory[20] = Word(MuredOpcode.INT, 10)
    lookup_memory[21] = Word(MuredOpcode.INT, 22)
    lookup_machine = MuredMachine(
        MuredMachineState(
            memory=lookup_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=0,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=5,
            free_space=40,
            argcnt=0,
        )
    )
    result, expected = _run_bounded_to_same_commit(lookup_machine, codec)
    assert expected.s_a == 22
    assert expected.s_d == 1
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=expected.fsp))
    assert _packed_memory_read(result) == expected.memory[expected.fsp]

    # PNP redirects the environment cursor without consuming the lexical index.
    pnp_memory: list[Word | None] = [None] * 64
    pnp_memory[0] = Word(MuredOpcode.VAR, 1, True)
    pnp_memory[20] = Word(MuredOpcode.PNP, 30, True)
    pnp_memory[30] = Word(MuredOpcode.INT, 33)
    pnp_memory[31] = Word(MuredOpcode.INT, 44)
    pnp_machine = MuredMachine(
        MuredMachineState(
            memory=pnp_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=0,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=5,
            free_space=40,
            argcnt=0,
        )
    )
    result, expected = _run_bounded_to_same_commit(pnp_machine, codec)
    assert expected.s_a == 32
    assert expected.s_d == 1
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=expected.fsp))
    assert _packed_memory_read(result) == expected.memory[expected.fsp]

    # Closure-slot bindings occupy two environment words and therefore change
    # the stride used while consuming a nonzero lexical index.
    closure_slot_memory: list[Word | None] = [None] * 64
    closure_slot_memory[0] = Word(MuredOpcode.VAR, 1, True)
    closure_slot_memory[20] = Word(MuredOpcode.INT, 10, closure_slot=True)
    closure_slot_memory[21] = Word(MuredOpcode.INT, 99)
    closure_slot_memory[22] = Word(MuredOpcode.INT, 12)
    closure_slot_machine = MuredMachine(
        MuredMachineState(
            memory=closure_slot_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=0,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=5,
            free_space=40,
            argcnt=0,
        )
    )
    result, expected = _run_bounded_to_same_commit(closure_slot_machine, codec)
    assert expected.s_a == 23
    assert expected.s_d == 1
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=expected.fsp))
    assert _packed_memory_read(result) == expected.memory[expected.fsp]

    # A PNP payload outside physical graph RAM is invalid before narrowing; this
    # guards against a large 64-bit target aliasing to a small hardware address.
    bad_pnp_memory: list[Word | None] = [None] * 64
    bad_pnp_memory[0] = Word(MuredOpcode.VAR, 0, True)
    bad_pnp_memory[20] = Word(MuredOpcode.PNP, (1 << 17) + 20, True)
    bad_pnp_machine = MuredMachine(
        MuredMachineState(
            memory=bad_pnp_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=0,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=5,
            free_space=40,
            argcnt=0,
        )
    )
    bad_pnp_encoded = codec.encode_state(bad_pnp_machine.state)
    _, _, fault = _run_encoded_to_same_fault(bad_pnp_encoded)
    assert fault == abi.FAULT_INVALID_ADDRESS

    # Forward LAMBDA reconstruction at q=0 serializes two writes through the
    # single graph-RAM port: push the lambda result, then allocate UBV(phi+1).
    codec = RED2ABICodec()
    machine = MuredMachine.load(
        [Word(MuredOpcode.LAMBDA, "x", True)],
        quantum=0,
        memory_words=64,
        control_words=32,
    )
    result, expected = _run_bounded_to_same_commit(machine, codec)
    assert expected.q == 0
    assert expected.phi == 1
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.fsp),
    )
    assert _packed_memory_read(result) == expected.memory[expected.fsp]
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.env),
    )
    assert _packed_memory_read(result) == expected.memory[expected.env]

    # Encoded argcnt==1 means the processor's internal argcnt==0.  This takes
    # the same reconstruction branch even with quantum available.
    codec = RED2ABICodec()
    machine = MuredMachine.load(
        [Word(MuredOpcode.LAMBDA, "x", True)],
        quantum=8,
        memory_words=64,
        control_words=32,
    )
    result, expected = _run_bounded_to_same_commit(machine, codec)
    assert expected.q == 8
    assert expected.argcnt == 1
    assert expected.phi == 1
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.env),
    )
    assert _packed_memory_read(result) == expected.memory[expected.env]

    # Reconstruction with a split environment frontier publishes the graph
    # result first, then preserves the old environment with PNP and allocates
    # the fresh UBV below it.  Match all three observable writes.
    codec = RED2ABICodec()
    bridge_memory: list[Word | None] = [None] * 64
    bridge_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
    bridge_memory[1] = Word(MuredOpcode.STOP)
    bridge_machine = MuredMachine(
        MuredMachineState(
            memory=bridge_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=20,
            c=-1,
            direction=Direction.F,
            q=0,
            phi=0,
            free_space=21,
            argcnt=0,
        )
    )
    result, expected = _run_bounded_to_same_commit(bridge_machine, codec)
    assert expected.pc == 1
    assert expected.fsp == 2
    assert expected.env == 19
    assert expected.free_space == 19
    assert expected.q == 0
    assert expected.argcnt == 1
    assert expected.phi == 1
    for address in (2, 19, 20):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]

    # Oracle ordering is intentionally visible on a late allocation collision:
    # the reconstructed graph result, fsp, argcnt, and phi have already changed.
    tight_bridge_memory: list[Word | None] = [None] * 64
    tight_bridge_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
    tight_bridge_memory[1] = Word(MuredOpcode.LAMBDA, "y", True)
    tight_bridge_machine = MuredMachine(
        MuredMachineState(
            memory=tight_bridge_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=2,
            c=-1,
            direction=Direction.F,
            q=0,
            phi=4,
            free_space=3,
            argcnt=0,
        )
    )
    tight_encoded = codec.encode_state(tight_bridge_machine.state)
    result, expected, fault = _run_encoded_to_same_fault(tight_encoded)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert expected.fsp == 2
    assert expected.argcnt == 1
    assert expected.phi == 5
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=2))
    assert _packed_memory_read(result) == expected.memory[2]

    # Immediate atomic beta clones the argument into the environment with head
    # cleared, while preserving definition and closure-slot metadata.  It then
    # consumes exactly one q, one graph argument, and one encoded argcnt unit.
    codec = RED2ABICodec()
    beta_memory: list[Word | None] = [None] * 64
    beta_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
    beta_memory[1] = Word(
        MuredOpcode.INT,
        7,
        True,
        definition=3,
        closure_slot=True,
    )
    beta_machine = MuredMachine(
        MuredMachineState(
            memory=beta_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=4,
            free_space=20,
            argcnt=1,
        )
    )
    result, expected = _run_bounded_to_same_commit(beta_machine, codec)
    assert expected.pc == 1
    assert expected.fsp == 0
    assert expected.env == 19
    assert expected.free_space == 19
    assert expected.q == 7
    assert expected.argcnt == 1
    assert expected.phi == 4
    result = sim_call(
        red2_processor_top,
        _command(CMD_NOP, address=expected.env),
    )
    assert _packed_memory_read(result) == expected.memory[expected.env]

    # Immediate APP_VAR beta binds UBV(phi-index).  A negative phi-index is a
    # valid signed RED2 payload; only a negative source APP_VAR index is invalid.
    for beta_phi, beta_index in ((5, 2), (1, 3)):
        codec = RED2ABICodec()
        app_var_memory: list[Word | None] = [None] * 64
        app_var_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
        app_var_memory[1] = Word(MuredOpcode.APP_VAR, beta_index, True)
        app_var_machine = MuredMachine(
            MuredMachineState(
                memory=app_var_memory,
                control_stack=[None] * 32,
                pc=0,
                fsp=1,
                env=20,
                c=-1,
                direction=Direction.F,
                q=8,
                phi=beta_phi,
                free_space=20,
                argcnt=1,
            )
        )
        result, expected = _run_bounded_to_same_commit(app_var_machine, codec)
        assert expected.pc == 1
        assert expected.fsp == 0
        assert expected.env == 19
        assert expected.q == 7
        assert expected.argcnt == 1
        assert expected.phi == beta_phi
        result = sim_call(
            red2_processor_top,
            _command(CMD_NOP, address=expected.env),
        )
        assert _packed_memory_read(result) == expected.memory[expected.env]

    # Every remaining immediate LAMBDA argument except APP, APP_VAR, and EP
    # follows the oracle's generic clone rule: preserve opcode/kind/payload,
    # definition, and closure-slot metadata while clearing only head.
    generic_bindings = (
        Word(MuredOpcode.UBV, 2, True, definition=4, closure_slot=True),
        Word(MuredOpcode.VAR, 1, True, definition=5, closure_slot=True),
        Word(MuredOpcode.SYM, "foo", True, definition=6, closure_slot=True),
        Word(MuredOpcode.LAMBDA, "y", True, definition=7, closure_slot=True),
    )
    for generic_argument in generic_bindings:
        codec = RED2ABICodec()
        generic_memory: list[Word | None] = [None] * 64
        generic_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
        generic_memory[1] = generic_argument
        generic_machine = MuredMachine(
            MuredMachineState(
                memory=generic_memory,
                control_stack=[None] * 32,
                pc=0,
                fsp=1,
                env=20,
                c=-1,
                direction=Direction.F,
                q=8,
                phi=4,
                free_space=20,
                argcnt=1,
            )
        )
        result, expected = _run_bounded_to_same_commit(generic_machine, codec)
        assert expected.pc == 1
        assert expected.fsp == 0
        assert expected.env == 19
        assert expected.free_space == 19
        assert expected.q == 7
        assert expected.argcnt == 1
        assert expected.phi == 4
        result = sim_call(
            red2_processor_top,
            _command(CMD_NOP, address=expected.env),
        )
        assert _packed_memory_read(result) == expected.memory[expected.env]

    # The same single-word allocator must insert PNP when env and free_space
    # differ for both generic clone and APP_VAR beta bindings.
    bridge_beta_arguments = (
        Word(MuredOpcode.VAR, 1, True, definition=5, closure_slot=True),
        Word(MuredOpcode.APP_VAR, 2, True),
    )
    for bridge_argument in bridge_beta_arguments:
        bridge_beta_memory: list[Word | None] = [None] * 64
        bridge_beta_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
        bridge_beta_memory[1] = bridge_argument
        bridge_beta_machine = MuredMachine(
            MuredMachineState(
                memory=bridge_beta_memory,
                control_stack=[None] * 32,
                pc=0,
                fsp=1,
                env=20,
                c=-1,
                direction=Direction.F,
                q=8,
                phi=4,
                free_space=21,
                argcnt=1,
            )
        )
        result, expected = _run_bounded_to_same_commit(bridge_beta_machine, codec)
        assert expected.pc == 1
        assert expected.fsp == 0
        assert expected.env == 19
        assert expected.free_space == 19
        assert expected.q == 7
        assert expected.argcnt == 1
        for address in (19, 20):
            result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
            assert _packed_memory_read(result) == expected.memory[address]

    # LAMBDA consuming EP pops a saved CONTROL_ADDRESS, then allocates a fresh
    # EP binding.  Match both the successful architectural checkpoint and the
    # observable RAM/control mutations.
    codec = RED2ABICodec()
    ep_memory: list[Word | None] = [None] * 64
    ep_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
    ep_memory[1] = Word(MuredOpcode.EP, 7, True)
    ep_machine = MuredMachine(
        MuredMachineState(
            memory=ep_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=4,
            free_space=20,
            argcnt=1,
        )
    )
    ep_encoded = codec.encode_state(ep_machine.state)
    ep_encoded = _with_control_entry(
        ep_encoded,
        abi.pack_control_entry(abi.CONTROL_ADDRESS, 13, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(ep_encoded)
    assert expected.pc == 1
    assert expected.fsp == 0
    assert expected.env == 19
    assert expected.free_space == 19
    assert expected.c == 0
    assert expected.q == 7
    assert expected.argcnt == 1
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=expected.env))
    assert _packed_memory_read(result) == expected.memory[expected.env]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0] == 0

    # EP uses the same PNP-preserving single-word allocator after popping the
    # saved path.  Both environment words and the cleared control entry matter.
    bridge_ep_machine = MuredMachine(
        MuredMachineState(
            memory=list(ep_memory),
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=4,
            free_space=21,
            argcnt=1,
        )
    )
    bridge_ep_encoded = _with_control_entry(
        codec.encode_state(bridge_ep_machine.state),
        abi.pack_control_entry(abi.CONTROL_ADDRESS, 13, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(bridge_ep_encoded)
    assert expected.env == 19
    assert expected.free_space == 19
    assert expected.c == 0
    for address in (19, 20):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0] == 0

    # Empty control stack faults before mutation.
    empty_encoded = codec.encode_state(ep_machine.state)
    _, expected, fault = _run_encoded_to_same_fault(empty_encoded)
    assert fault == abi.FAULT_CONTROL_UNDERFLOW
    assert expected.c == 0

    # A non-address control entry is an illegal transition and remains present.
    wrong_tag_encoded = _with_control_entry(
        codec.encode_state(ep_machine.state),
        abi.pack_control_entry(abi.CONTROL_SAVED_PRIM, 13, 0, 0, 0),
    )
    result, expected, fault = _run_encoded_to_same_fault(wrong_tag_encoded)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Oracle ordering is deliberately non-transactional here: the saved path is
    # popped before environment allocation, so a later collision leaves c
    # decremented and the control cell cleared.  Hardware must match that exact
    # fault checkpoint rather than retaining the pre-pop state.
    collision_memory: list[Word | None] = [None] * 64
    collision_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
    collision_memory[1] = Word(MuredOpcode.EP, 7, True)
    collision_machine = MuredMachine(
        MuredMachineState(
            memory=collision_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=2,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=4,
            free_space=2,
            argcnt=1,
        )
    )
    collision_encoded = _with_control_entry(
        codec.encode_state(collision_machine.state),
        abi.pack_control_entry(abi.CONTROL_ADDRESS, 13, 0, 0, 0),
    )
    result, expected, fault = _run_encoded_to_same_fault(collision_encoded)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert expected.c == 0
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0] == 0
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=1))
    assert _packed_memory_read(result) == expected.memory[1]

    # LAMBDA consuming APP pops the caller path and allocates a two-word
    # [CLOSURE(saved_path), pointer(target)] environment block.
    app_memory: list[Word | None] = [None] * 64
    app_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
    app_memory[1] = Word(MuredOpcode.APP, 7, True)
    app_machine = MuredMachine(
        MuredMachineState(
            memory=app_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=4,
            free_space=20,
            argcnt=1,
        )
    )
    codec = RED2ABICodec()
    app_encoded = _with_control_entry(
        codec.encode_state(app_machine.state),
        abi.pack_control_entry(abi.CONTROL_ADDRESS, 13, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(app_encoded)
    assert expected.pc == 1
    assert expected.fsp == 0
    assert expected.env == 18
    assert expected.free_space == 18
    assert expected.c == 0
    assert expected.q == 7
    assert expected.argcnt == 1
    for address in (18, 19):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0] == 0

    # When free_space no longer equals env, allocation first preserves the old
    # environment path with a PNP bridge and then writes the same closure block.
    bridge_app_machine = MuredMachine(
        MuredMachineState(
            memory=list(app_memory),
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=20,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=4,
            free_space=21,
            argcnt=1,
        )
    )
    bridge_app_encoded = _with_control_entry(
        codec.encode_state(bridge_app_machine.state),
        abi.pack_control_entry(abi.CONTROL_ADDRESS, 13, 0, 0, 0),
    )
    result, expected = _run_encoded_to_same_commit(bridge_app_encoded)
    assert expected.env == 18
    assert expected.free_space == 18
    assert expected.c == 0
    for address in (18, 19, 20):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0] == 0

    # APP shares EP's saved-path validation rules.
    empty_app_encoded = codec.encode_state(app_machine.state)
    _, expected, fault = _run_encoded_to_same_fault(empty_app_encoded)
    assert fault == abi.FAULT_CONTROL_UNDERFLOW
    assert expected.c == 0

    wrong_app_encoded = _with_control_entry(
        codec.encode_state(app_machine.state),
        abi.pack_control_entry(abi.CONTROL_SAVED_PRIM, 13, 0, 0, 0),
    )
    result, expected, fault = _run_encoded_to_same_fault(wrong_app_encoded)
    assert fault == abi.FAULT_ILLEGAL_TRANSITION
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0]

    # Allocation collision occurs after the saved path is popped.  No closure
    # words may publish, but the cleared control cell and decremented c survive.
    collision_app_memory: list[Word | None] = [None] * 64
    collision_app_memory[0] = Word(MuredOpcode.LAMBDA, "x", True)
    collision_app_memory[1] = Word(MuredOpcode.APP, 7, True)
    collision_app_machine = MuredMachine(
        MuredMachineState(
            memory=collision_app_memory,
            control_stack=[None] * 32,
            pc=0,
            fsp=1,
            env=3,
            c=-1,
            direction=Direction.F,
            q=8,
            phi=4,
            free_space=3,
            argcnt=1,
        )
    )
    collision_app_encoded = _with_control_entry(
        codec.encode_state(collision_app_machine.state),
        abi.pack_control_entry(abi.CONTROL_ADDRESS, 13, 0, 0, 0),
    )
    result, expected, fault = _run_encoded_to_same_fault(collision_app_encoded)
    assert fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert expected.c == 0
    result = sim_call(red2_processor_top, _command(CMD_NOP, address=0))
    assert _packed_control_read(result) == expected.control_stack[0] == 0
    for address in (1, 2):
        result = sim_call(red2_processor_top, _command(CMD_NOP, address=address))
        assert _packed_memory_read(result) == expected.memory[address]


if __name__ == "__main__":
    check()
    print("PipelineC native RED2 first-slice parity: PASS")

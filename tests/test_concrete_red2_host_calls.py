import pytest

from abstract_red2_machine.machine import AbstractRED2Machine, MuredOpcode, Word
from concrete_red2_machine import abi
from concrete_red2_machine.machine import (
    PRIM0_ROLE_IO_BIND,
    PRIM0_ROLE_IO_RETURN,
    PRIM0_ROLE_IO_THEN,
    RED2_HOSTCALL_V1,
    SCALAR_OP_ADD,
    ConcreteRED2Machine,
)
from concrete_red2_machine.pipelinec_vectors import RED2ABICodec
from thor_compile.red2 import load_faithful_machine
from thor_lang.normalization import normalize_expr
from thor_lang.parser import parse_expr


def _machine(source: str, *, quantum: int = 100) -> AbstractRED2Machine:
    return load_faithful_machine(
        normalize_expr(parse_expr(source)),
        quantum=quantum,
        memory_words=128,
        control_words=32,
    )


def _processor(machine: AbstractRED2Machine, codec: RED2ABICodec) -> ConcreteRED2Machine:
    encoded = codec.encode_state(machine.state, machine.pending_host_call)

    host_names = {
        "CLOCK": abi.HOST_CLOCK,
        "UART-RX": abi.HOST_UART_RX,
        "UART-TX": abi.HOST_UART_TX,
        "UART-TX-BYTES": abi.HOST_UART_TX_BYTES,
    }
    host_ids = {name: codec.literal_id(name) for name in host_names}
    host_image = [abi.HOST_NONE] * (max(host_ids.values()) + 1)
    for name, literal_id in host_ids.items():
        host_image[literal_id] = host_names[name]

    io_roles = {
        "IO-BIND": PRIM0_ROLE_IO_BIND,
        "IO-THEN": PRIM0_ROLE_IO_THEN,
        "IO-RETURN": PRIM0_ROLE_IO_RETURN,
    }
    io_ids = {name: codec.literal_id(name) for name in io_roles}
    role_image = [0] * (max(io_ids.values(), default=0) + 1)
    for name, literal_id in io_ids.items():
        role_image[literal_id] = io_roles[name]

    add_id = codec.literal_id("+")
    scalar_ops = [0] * (add_id + 1)
    scalar_ops[add_id] = SCALAR_OP_ADD

    return ConcreteRED2Machine(
        encoded,
        host_ops=tuple(host_image),
        prim0_roles=tuple(role_image),
        scalar_ops=tuple(scalar_ops),
        true_literal_id=codec.literal_id("TRUE"),
        false_literal_id=codec.literal_id("FALSE"),
        nil_literal_id=codec.literal_id("NIL"),
    )


def _assert_checkpoint_matches(
    machine: AbstractRED2Machine,
    processor: ConcreteRED2Machine,
    codec: RED2ABICodec,
) -> None:
    assert processor.checkpoint() == codec.encode_state(
        machine.state, machine.pending_host_call
    )


def _run_both_until_host_call(
    machine: AbstractRED2Machine,
    processor: ConcreteRED2Machine,
    codec: RED2ABICodec,
) -> None:
    for _ in range(256):
        assert machine.pending_host_call is None
        machine.step()
        assert processor.run_to_commit(), processor.fault
        _assert_checkpoint_matches(machine, processor, codec)
        if machine.pending_host_call is not None:
            assert processor.status() == abi.STATUS_HOST_CALL
            return
    pytest.fail("host primitive did not suspend")


def _finish_both(
    machine: AbstractRED2Machine,
    processor: ConcreteRED2Machine,
    codec: RED2ABICodec,
) -> None:
    for _ in range(256):
        if machine.state.halted:
            assert processor.status() == abi.STATUS_COMPLETE
            assert processor.halted
            return
        assert machine.pending_host_call is None
        machine.step()
        assert processor.run_to_commit(), processor.fault
        _assert_checkpoint_matches(machine, processor, codec)
    pytest.fail("resumed RED2 program did not halt")


def test_red2_hostcall_v1_is_explicit() -> None:
    assert RED2_HOSTCALL_V1 == 1


def test_run_until_suspend_exposes_host_call_only_after_architectural_commit() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    commits_before = processor.commits
    assert processor.run_until_suspend() == abi.STATUS_HOST_CALL
    assert processor.microstate == 0
    assert processor.commits == commits_before + 1
    assert processor.pending_host_op == abi.HOST_CLOCK
    assert processor.resume_host_call(
        codec.encode_word(Word(MuredOpcode.INT, 123))
    ) == abi.STATUS_RUNNING


@pytest.mark.parametrize(
    ("source", "name", "host_op", "result"),
    [
        ("(CLOCK)", "CLOCK", abi.HOST_CLOCK, Word(MuredOpcode.INT, 1_700_000_000_789)),
        ("(UART-RX)", "UART-RX", abi.HOST_UART_RX, Word(MuredOpcode.INT, 90)),
    ],
)
def test_zero_arity_host_call_suspends_freezes_and_resumes_same_machine(
    source: str,
    name: str,
    host_op: int,
    result: Word,
) -> None:
    machine = _machine(source)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _run_both_until_host_call(machine, processor, codec)

    call = machine.pending_host_call
    assert call is not None
    assert call.name == name
    assert call.argument_address is None
    assert processor.pending_host_op == host_op
    assert processor.pending_host_argument == 0

    frozen = processor.checkpoint()
    for _ in range(16):
        assert not processor.clock()
        assert processor.checkpoint() == frozen

    quantum_before = machine.state.q
    machine.resume_host_call(result)
    assert processor.resume_host_call(codec.encode_word(result)) == abi.STATUS_RUNNING
    assert machine.state.q == quantum_before - 1
    _assert_checkpoint_matches(machine, processor, codec)
    _finish_both(machine, processor, codec)


@pytest.mark.parametrize(
    ("name", "host_op"),
    [
        ("UART-TX", abi.HOST_UART_TX),
        ("UART-TX-BYTES", abi.HOST_UART_TX_BYTES),
    ],
)
def test_strict_host_call_waits_for_argument_then_resumes_exactly_once(
    name: str,
    host_op: int,
) -> None:
    machine = _machine(f"({name} (+ 64 1))")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _run_both_until_host_call(machine, processor, codec)

    call = machine.pending_host_call
    assert call is not None
    assert call.name == name
    assert call.argument_address is not None
    assert machine.state.memory[call.argument_address] == Word(MuredOpcode.INT, 65, False)
    assert processor.pending_host_op == host_op
    assert processor.pending_host_argument == abi.encode_optional_address(call.argument_address)
    assert processor.prim_id == 0
    assert processor.fire == 0

    quantum_before = machine.state.q
    result = Word(MuredOpcode.SYM, "NIL")
    machine.resume_host_call(result)
    assert processor.resume_host_call(codec.encode_word(result)) == abi.STATUS_RUNNING
    assert machine.state.q == quantum_before - 1
    _assert_checkpoint_matches(machine, processor, codec)
    _finish_both(machine, processor, codec)


@pytest.mark.parametrize("source", ["(CLOCK)", "(UART-TX 65)"])
def test_host_primitive_does_not_dispatch_at_zero_quantum(source: str) -> None:
    machine = _machine(source, quantum=0)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    for _ in range(256):
        if machine.state.halted:
            break
        machine.step()
        assert machine.pending_host_call is None
        assert processor.run_to_commit(), processor.fault
        assert processor.pending_host_op == abi.HOST_NONE
        _assert_checkpoint_matches(machine, processor, codec)
    else:
        pytest.fail("q=0 host residual did not reach the bounded halt")

    assert processor.status() == abi.STATUS_QUANTUM_EXHAUSTED


def test_resume_without_pending_host_call_faults_without_architectural_mutation() -> None:
    machine = _machine("7")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    before = processor.checkpoint()

    assert processor.resume_host_call(codec.encode_word(Word(MuredOpcode.INT, 2))) == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_INVALID_RESUME
    assert processor.checkpoint() == before


def test_non_atomic_host_result_faults_without_partial_resume() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    _run_both_until_host_call(machine, processor, codec)
    before = processor.checkpoint()

    invalid = codec.encode_word(Word(MuredOpcode.APP, 0, True))
    assert processor.resume_host_call(invalid) == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_INVALID_RESUME
    assert processor.checkpoint() == before


def test_direct_host_resume_capacity_fault_matches_oracle_without_partial_publication() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    _run_both_until_host_call(machine, processor, codec)

    machine.state.free_space = machine.state.fsp + 1
    processor.free_space = processor.fsp + 1
    before = processor.checkpoint()

    result = codec.encode_word(Word(MuredOpcode.INT, 123))
    assert processor.resume_host_call(result) == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_GRAPH_ENV_COLLISION
    assert processor.checkpoint() == before


def test_resume_rejects_definition_payload_without_valid_bit_atomically() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    _run_both_until_host_call(machine, processor, codec)
    before = processor.checkpoint()

    malformed = codec.encode_word(Word(MuredOpcode.INT, 7)) | (1 << abi.WORD_DEFINITION_SHIFT)
    assert processor.resume_host_call(malformed) == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_INVALID_RESUME
    assert processor.checkpoint() == before


def test_resume_rejects_reserved_word_bits_atomically() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    _run_both_until_host_call(machine, processor, codec)
    before = processor.checkpoint()

    malformed = codec.encode_word(Word(MuredOpcode.INT, 7)) | (1 << 127)
    assert processor.resume_host_call(malformed) == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_INVALID_RESUME
    assert processor.checkpoint() == before


def test_resume_rejects_literal_id_payload_above_abi_width_atomically() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    _run_both_until_host_call(machine, processor, codec)
    before = processor.checkpoint()

    encoded = codec.encode_word(Word(MuredOpcode.SYM, "NIL"))
    malformed = (encoded & ~abi.WORD_PAYLOAD_MASK) | (abi.LITERAL_ID_MAX + 1)
    assert processor.resume_host_call(malformed) == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_INVALID_RESUME
    assert processor.checkpoint() == before


def test_resume_rejects_atomic_closure_slot_metadata_atomically() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    _run_both_until_host_call(machine, processor, codec)
    before = processor.checkpoint()

    malformed = codec.encode_word(
        Word(MuredOpcode.INT, 7, head=False, closure_slot=True)
    )
    assert processor.resume_host_call(malformed) == abi.STATUS_FAULT
    assert processor.fault == abi.FAULT_INVALID_RESUME
    assert processor.checkpoint() == before


def test_resume_accepts_noncanonical_head_and_reheads_like_oracle() -> None:
    machine = _machine("(CLOCK)")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    _run_both_until_host_call(machine, processor, codec)

    result = Word(MuredOpcode.INT, 7, head=False, definition=3)
    machine.resume_host_call(result)
    assert processor.resume_host_call(codec.encode_word(result)) == abi.STATUS_RUNNING
    assert processor.checkpoint() == codec.encode_state(
        machine.state, machine.pending_host_call
    )


def test_ordered_uart_effects_resume_exactly_once_on_same_machine() -> None:
    machine = _machine(
        "(IO-THEN (UART-TX 65) (IO-THEN (UART-TX 66) (IO-RETURN 7)))"
    )
    codec = RED2ABICodec()
    processor = _processor(machine, codec)
    effects: list[int] = []

    for _ in range(256):
        if machine.pending_host_call is not None:
            call = machine.pending_host_call
            assert call.name == "UART-TX"
            assert call.argument_address is not None
            argument = machine.state.memory[call.argument_address]
            assert argument is not None and argument.opcode is MuredOpcode.INT
            effects.append(argument.data)

            frozen = processor.checkpoint()
            frozen_commits = processor.commits
            assert processor.run_until_suspend() == abi.STATUS_HOST_CALL
            assert processor.checkpoint() == frozen
            assert processor.commits == frozen_commits

            result = Word(MuredOpcode.SYM, "NIL")
            machine.resume_host_call(result)
            assert processor.resume_host_call(codec.encode_word(result)) == abi.STATUS_RUNNING
            _assert_checkpoint_matches(machine, processor, codec)
            continue

        if machine.state.halted:
            break
        machine.step()
        assert processor.run_to_commit(), processor.fault
        _assert_checkpoint_matches(machine, processor, codec)
    else:
        pytest.fail("ordered host-effect program did not complete")

    assert machine.state.halted
    assert processor.status() == abi.STATUS_COMPLETE
    assert effects == [65, 66]


def test_clock_result_flows_through_io_bind_on_same_machine() -> None:
    machine = _machine("(IO-BIND (CLOCK) (LAMBDA (now) (IO-RETURN now)))")
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _run_both_until_host_call(machine, processor, codec)
    assert machine.pending_host_call is not None
    assert machine.pending_host_call.name == "CLOCK"

    result = Word(MuredOpcode.INT, 1234)
    machine.resume_host_call(result)
    assert processor.resume_host_call(codec.encode_word(result)) == abi.STATUS_RUNNING
    _assert_checkpoint_matches(machine, processor, codec)

    for _ in range(256):
        if machine.state.halted:
            break
        assert machine.pending_host_call is None
        machine.step()
        assert processor.run_to_commit(), processor.fault
        _assert_checkpoint_matches(machine, processor, codec)
    else:
        pytest.fail("IO-BIND host-result program did not complete")

    assert machine.state.halted
    assert processor.status() == abi.STATUS_COMPLETE

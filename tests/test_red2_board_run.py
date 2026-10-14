"""Live execution must preserve clock budgets, read latency and fault outcomes."""

import io
import json
from types import SimpleNamespace

import pytest
from scripts.boards.red2_basys3 import run


def test_transport_encodes_burst_and_records_actual_packet():
    packets = []
    hw = SimpleNamespace(CMD_CLOCK=7, _command=lambda op, **fields: op)
    layout = SimpleNamespace(
        input_type="in",
        output_type="out",
        pack=lambda typ, cmd: (cmd, 722),
        unpack=lambda typ, bits: bits,
    )
    transcript = io.StringIO()
    device = run.Device(
        hw, layout, lambda bits, seq: packets.append((bits, seq)) or 123, transcript
    )
    assert device.command(7, edges=65536, phase="run") == 123
    assert packets == [(10 | (65536 << 280), 0)]
    assert device.delivered_run_clocks == 65536
    assert json.loads(transcript.getvalue())["response"] == "7B"
    with pytest.raises(ValueError, match="only CLOCK"):
        device.command(0, edges=2)


def test_uncertain_uart_delivery_is_recorded_without_retry():
    attempts = []

    def fail(bits, seq):
        attempts.append(bits)
        raise TimeoutError("uncertain response")

    transcript = io.StringIO()
    hw = SimpleNamespace(CMD_CLOCK=7, _command=lambda op, **fields: op)
    layout = SimpleNamespace(input_type="in", pack=lambda typ, cmd: (cmd, 722))
    device = run.Device(hw, layout, fail, transcript)
    with pytest.raises(TimeoutError):
        device.command(7, edges=20, phase="run")
    assert len(attempts) == 1
    assert device.packets == device.delivered_run_clocks == 0
    assert json.loads(transcript.getvalue())["engine_edges"] == 20


def statuses():
    return SimpleNamespace(
        STATUS_RUNNING=0,
        STATUS_COMPLETE=1,
        STATUS_QUANTUM_EXHAUSTED=2,
        STATUS_HOST_CALL=3,
        STATUS_FAULT=4,
        CMD_CLOCK=7,
    )


def test_clock_budget_ends_at_exact_limit_without_waiting_for_timeout():
    delivered = []
    device = SimpleNamespace(
        hw=statuses(),
        delivered_run_clocks=0,
        load=lambda *args: SimpleNamespace(status=0),
    )

    def command(op, *, edges, phase):
        delivered.append(edges)
        device.delivered_run_clocks += edges
        return SimpleNamespace(status=0)

    device.command = command
    with pytest.raises(RuntimeError, match="10 delivered clocks"):
        run.execute(
            device,
            None,
            None,
            None,
            quantum=1,
            burst_clocks=6,
            max_clocks=10,
            host=None,
        )
    assert delivered == [6, 4]


@pytest.mark.parametrize("status,code", [(2, 3), (4, 5)])
def test_exhaustion_and_hardware_fault_are_never_success(status, code):
    result = SimpleNamespace(status=status, red2_fault=17, hw_fault=0, microstate=123)
    device = SimpleNamespace(hw=statuses(), load=lambda *args: result)
    report = run.execute(
        device, None, None, None, quantum=1, burst_clocks=6, max_clocks=10, host=None
    )
    assert not report["completed"] and report["exit_code"] == code


def test_complete_requires_an_actual_halted_checkpoint():
    device = SimpleNamespace(
        hw=statuses(),
        load=lambda *args: SimpleNamespace(status=1),
        checkpoint=lambda result: SimpleNamespace(halted=False, pending_host_op=0),
    )
    with pytest.raises(RuntimeError, match="without a halted checkpoint"):
        run.execute(
            device,
            None,
            None,
            None,
            quantum=1,
            burst_clocks=6,
            max_clocks=10,
            host=None,
        )


def test_resume_fault_is_not_erased_by_recharge():
    commands = []
    hw = statuses()
    hw.CMD_RESUME, hw.CMD_RECHARGE = 6, 5
    hw._word_struct = lambda value: value
    hw.dispatch_encoded_host_call = lambda *args, **kwargs: 7
    device = SimpleNamespace(
        hw=hw,
        load=lambda *args: SimpleNamespace(status=3),
        checkpoint=lambda result: SimpleNamespace(pending_host_op=1),
    )

    def command(op, **fields):
        commands.append(op)
        return SimpleNamespace(status=4, red2_fault=17, hw_fault=0, microstate=123)

    device.command = command
    report = run.execute(
        device,
        None,
        SimpleNamespace(working_memory_limit=256),
        None,
        quantum=1,
        burst_clocks=6,
        max_clocks=10,
        host=None,
    )
    assert not report["completed"] and report["red2_fault"] == 17
    assert commands == [6]


def test_checkpoint_primes_both_synchronous_banks_at_each_address():
    addresses, pending = [], [0]
    hw = SimpleNamespace(
        GRAPH_WORDS=2,
        CONTROL_WORDS=2,
        CMD_NOP=0,
        _packed_word=lambda value: value,
        _packed_control=lambda value: value,
        EncodedArchitecturalState=SimpleNamespace,
    )

    def command(op, *, address, phase):
        addresses.append(address)
        previous, pending[0] = pending[0], address
        return SimpleNamespace(memory_read=100 + previous, control_read=200 + previous)

    device = SimpleNamespace(hw=hw, command=command)
    fields = dict.fromkeys(
        (
            "pc",
            "fsp",
            "env",
            "direction",
            "q",
            "phi",
            "free_space",
            "argcnt",
            "prim_id",
            "fire",
            "s_a",
            "s_d",
            "halted",
            "pending_host_op",
            "pending_host_argument",
            "control_top",
        ),
        0,
    )
    checkpoint = run.Device.checkpoint(device, SimpleNamespace(busy=False, **fields))
    assert checkpoint.memory == (100, 101)
    assert checkpoint.control_stack == (200, 201)
    assert addresses == [0, 0, 1, 1]


@pytest.mark.parametrize("quantum", [-1, 1 << 32])
def test_quantum_cannot_silently_truncate_in_hardware_fields(quantum):
    with pytest.raises(ValueError, match="unsigned 32-bit"):
        run.compile_program(None, "7", quantum)


def test_cached_runtime_from_a_different_memory_profile_is_rejected(monkeypatch):
    import sys

    monkeypatch.setenv("RED2_SYN_GRAPH_WORDS", "256")
    monkeypatch.setenv("RED2_SYN_FLOAT", "0")
    monkeypatch.setitem(
        sys.modules,
        "run_syn",
        SimpleNamespace(
            GRAPH_WORDS=8192,
            CONTROL_WORDS=256,
            LITERAL_META_WORDS=64,
            _syn_machine=SimpleNamespace(RED2_SYN_FLOAT=0),
        ),
    )
    with pytest.raises(ValueError, match="board profile"):
        run.runtime()

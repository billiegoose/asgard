"""Trace queued lifecycle commands through the candidate's public ports."""

# isort: skip_file
import importlib.util
import os
import sys
from paths import INTEGRATED, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import run_syn  # noqa: F401 -- verified enhanced runtime bootstrap
import pypeline as py
from native_runtime import cache_scalar_types
from rtl_trace import Trace

cache_scalar_types(py)
spec = importlib.util.spec_from_file_location(
    "public_lifecycle_candidate", INTEGRATED / "machine.py"
)
hw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hw
spec.loader.exec_module(hw)
zero_state = hw.red2_arch_state_t(**{name: 0 for name in hw.red2_arch_state_t._fields})
empty = hw.red2_command_t(
    op=hw.CMD_NOP,
    address=0,
    word=hw.red2_word_t(lo=0, hi=0),
    control=hw.red2_control_t(lo=0, hi=0, tag_hi=0),
    value=0,
    aux=0,
    state=zero_state,
)
loaded = hw.red2_arch_state_t(
    **{
        **zero_state._asdict(),
        "pc": 7,
        "fsp": 9,
        "env": 256,
        "control_top": 1,
        "direction": 1,
        "q": 0x12345678,
        "phi": 11,
        "free_space": 240,
        "argcnt": 2,
        "prim_id": 5,
        "fire": 1,
        "s_a": 17,
        "s_d": 19,
        "halted": 1,
        "pending_host_op": 1,
        "pending_host_argument": 0xABCD9876543210,
    }
)
trace = Trace(INTEGRATED, os.environ["RED2_CFG_PILOT_TRACE"])


def call(command):
    command = hw.red2_command_t(**command._asdict())
    out = py.sim_call(hw.SynthesizableRED2Machine, command)
    trace.append(command, out)
    return out


py.sim_reset()
# Keep one continuous machine state, as the RTL replay does. Public RESET
# separates cases; there is no internal state injection between cases.
for op, address in [(hw.CMD_LOAD_STATE, 7), (hw.CMD_START, 7), (hw.CMD_START, 256)]:
    out = call(empty._replace(op=hw.CMD_RESET))
    assert int(out.busy)
    for _ in range(2):
        out = call(empty._replace(op=hw.CMD_CLOCK))
        assert int(out.busy)
    command = empty._replace(
        op=op,
        address=address,
        state=loaded,
        value=0x87654321,
        word=hw.red2_word_t(lo=0xDEADBEEF12345678, hi=0xFEDCBA9876543210),
        control=hw.red2_control_t(
            lo=0x8877665544332211, hi=0x1122334455667788, tag_hi=15
        ),
        aux=0xABCD0123456789EF,
    )
    out = call(command)
    assert int(out.busy)
    before = tuple(int(getattr(out, field)) for field in loaded._fields)
    for _ in range(3):
        out = call(empty)
        assert int(out.busy)
        assert tuple(int(getattr(out, field)) for field in loaded._fields) == before
    for _ in range(20000):
        out = call(empty._replace(op=hw.CMD_CLOCK))
        if not int(out.busy):
            break
    else:
        raise AssertionError("queued lifecycle command did not complete")
    if op == hw.CMD_LOAD_STATE:
        for field in loaded._fields:
            assert int(getattr(out, field)) == int(getattr(loaded, field)), field
    elif address == 7:
        assert int(out.pc) == 7 and int(out.q) == 0x87654321
        assert int(out.hw_fault) == hw.HW_FAULT_NONE
    else:
        assert int(out.pc) == 0 and int(out.q) == 0
        assert int(out.hw_fault) == hw.HW_FAULT_ADDRESS_RANGE
    print("PUBLIC_QUEUED_LIFECYCLE_PASS", op, address, flush=True)
trace.close()
print("PUBLIC_LIFECYCLE_TRACE_PASS", trace.count, flush=True)

# isort: skip_file
"""White-box native checks of integrated state/RAM/protocol boundaries.

Only the fixture setup touches pinned-runtime internals: arbitrary original
microstates cannot be loaded through the public architectural command port.
Every tested transition then runs the emitted complete top cycle by cycle.
"""

import functools
import importlib.util
import json
import sys
from paths import INTEGRATED, OUT, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import run_syn  # noqa: F401 -- verified compiler/runtime bootstrap
import pypeline as py

original_make_ctype = py._make_ctype
scalar_make_ctype = functools.cache(original_make_ctype)


def cached_scalar_type(name):
    # Array descriptors carry mutable factory metadata; leave them uncached.
    if (
        name.startswith(("uint", "int"))
        and name.endswith("_t")
        and name.removesuffix("_t").removeprefix("uint").removeprefix("int").isdigit()
    ):
        return scalar_make_ctype(name)
    return original_make_ctype(name)


py._make_ctype = cached_scalar_type
spec = importlib.util.spec_from_file_location(
    "integrated_boundary", INTEGRATED / "machine.py"
)
hw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hw
spec.loader.exec_module(hw)
m = json.loads((OUT / "control.json").read_text())
integration = json.loads((INTEGRATED / "integration.json").read_text())
sync_states = {
    getattr(hw, name)
    for name in integration.get(
        "synchronous_states",
        [
            "MICRO_LAMBDA_READ",
            "MICRO_LAMBDA_EP_CONTROL_READ",
            "MICRO_LAMBDA_APP_CONTROL_READ",
            "MICRO_APP_CONTROL_READ",
            "MICRO_LOOKUP_READ",
            "MICRO_LOOKUP_CLOSURE_CODE_READ",
            "MICRO_LOOKUP_VAR_EP_CHASE",
        ],
    )
}
cases = json.loads((OUT / "native-cases.json").read_text())
zero_word = hw.red2_word_t(lo=0, hi=0)
zero_control = hw.red2_control_t(lo=0, hi=0, tag_hi=0)
zero_state = hw.red2_arch_state_t(**{k: 0 for k in hw.red2_arch_state_t._fields})
empty = hw.red2_command_t(
    op=hw.CMD_NOP,
    address=0,
    word=zero_word,
    control=zero_control,
    value=0,
    aux=0,
    state=zero_state,
)
clock = empty._replace(op=hw.CMD_CLOCK)


def call(cmd):
    # NamedTuple._replace bypasses @struct's typed constructor.
    typed = hw.red2_command_t(**cmd._asdict())
    return py.sim_call(hw.SynthesizableRED2Machine, typed)


def top_regs():
    return next(v for k, v in py._sim_reg_state.items() if len(k) == 1)


private = set(integration.get("private_fields", []))


def scratch():
    return next(
        v["__sim_model__"]
        for k, v in py._sim_reg_state.items()
        if "__sim_model__" in v
        and any(frame[0] == "cfg_red2_app_lambda_cfg" for frame in k)
        and k[-1][0].startswith("ram_uint64_t_")
        and "_rw_" in k[-1][0]
    )


def drain(out):
    for _ in range(20000):
        if not int(out.busy):
            return out
        out = call(clock)
    raise AssertionError("lifecycle command did not complete")


def leaf(regs, name):
    if name in private:
        model = scratch()
        address = m["slots"][name]
        result = model.mem[address]
        for addr, value, _ in model.pending:
            if addr == address:
                result = value
        return int(result)
    value = regs[name.split(".")[0]]
    for field in name.split(".")[1:]:
        value = getattr(value, field)
    return int(value)


def fixture(case):
    py.sim_reset()
    drain(call(empty._replace(op=hw.CMD_RESET)))
    call(empty)
    req, response = case["request"], case["response"]
    call(
        empty._replace(
            op=hw.CMD_LOAD_MEMORY,
            address=req[0],
            word=hw.red2_word_t(lo=response[0], hi=response[1]),
        )
    )
    call(
        empty._replace(
            op=hw.CMD_LOAD_CONTROL,
            address=req[4],
            control=hw.red2_control_t(
                lo=response[2], hi=response[3], tag_hi=response[4]
            ),
        )
    )
    regs = top_regs()
    for name, value in case["values"].items():
        if name in private:
            scratch().mem[m["slots"][name]] = py._sim_cast(value, hw.uint64_t)
        elif "." not in name:
            regs[name] = py._sim_cast(value, hw.make_uint_t(m["widths"][name]))
    for name in {
        k.split(".")[0] for k in case["values"] if "." in k and k not in private
    }:
        regs[name] = hw.red2_word_t(
            lo=case["values"][name + ".lo"], hi=case["values"][name + ".hi"]
        )
    # The fixture starts at the admitted side of the original read bubble.
    regs["sync_read_pending"] = py._sim_cast(case["state"] in sync_states, hw.uint1_t)
    return regs


chosen = [] if "--lifecycle" in sys.argv else cases
if "--quick" in sys.argv:
    chosen = [cases[0], next(c for c in cases if c["state"] == hw.MICRO_EXECUTE)]
elif "--entries" in sys.argv:
    chosen = list({c["state"]: c for c in reversed(cases)}.values())
for index, case in enumerate(chosen):
    regs = fixture(case)
    out = call(clock)
    assert int(out.busy), ("not admitted", index, case["state"])
    visible = {
        k: int(getattr(out, k)) for k in integration.get("visible_snapshot_fields", [])
    }
    issues = 0
    for cycle in range(20000):
        before = int(regs["cfg_mem_phase"])
        # Pause in setup, controller execution and scalar transfer; read response
        # capture may settle while paused, but no logical or graph write advances.
        if cycle in {0, 20, 44, 65, 150, 500, 900}:
            stage = int(regs["cfg_stage"])
            cursor = int(regs["cfg_index"])
            values = {k: leaf(regs, k) for k in case["values"]}
            for _ in range(3):
                paused = call(empty)
                assert int(paused.busy) and not int(paused.committed)
                assert all(int(getattr(paused, k)) == v for k, v in visible.items()), (
                    "partial scalar observation during pause"
                )
                assert int(regs["cfg_stage"]) == stage
                assert int(regs["cfg_index"]) == cursor
                assert all(leaf(regs, k) == v for k, v in values.items())
        out = call(clock)
        after = int(regs["cfg_mem_phase"])
        issues += before == 0 and after == 1
        if not int(out.busy):
            break
        assert all(int(getattr(out, k)) == v for k, v in visible.items()), (
            "partial scalar publication"
        )
        assert int(out.status) == hw.STATUS_RUNNING
        assert not int(out.committed)
    else:
        raise AssertionError(("no completion", index))
    assert issues == 1, ("RAM issue count", index, issues)
    for name, wanted in case["expected"].items():
        assert leaf(regs, name) == wanted, (
            index,
            case["state"],
            name,
            leaf(regs, name),
            wanted,
        )
    req, response = case["request"], case["response"]
    for address, control in [(req[0], False), (req[4], True)]:
        cmd = empty._replace(address=address)
        call(cmd)
        out = call(cmd)
        if control:
            wanted = req[5:8] if req[8] else response[2:5]
            got = [
                int(out.control_read.lo),
                int(out.control_read.hi),
                int(out.control_read.tag_hi),
            ]
        else:
            wanted = req[1:3] if req[3] else response[:2]
            got = [int(out.memory_read.lo), int(out.memory_read.hi)]
        assert got == wanted, ("RAM result", index, control, got, wanted)
    print("INTEGRATED_BOUNDARY_PASS", index, case["state"], cycle + 2, flush=True)
print("INTEGRATED_BOUNDARY_ALL_PASS", len(chosen), flush=True)
# Reset must cancel writes and state transfer at different physical phases.
for offset in (
    () if "--lifecycle" in sys.argv else (0, 1, 20, 42, 43, 44, 45, 80, 200, 500)
):
    fixture(cases[0])
    out = call(clock)
    for _ in range(offset):
        if not int(out.busy):
            break
        out = call(clock)
    out = call(empty._replace(op=hw.CMD_RESET))
    out = drain(out)
    assert not int(out.busy)
    assert int(out.microstate) == hw.MICRO_FETCH
    for _ in range(5):
        out = call(empty)
        assert not int(out.busy) and not int(out.committed)
        assert int(out.pc) == 0 and int(out.q) == 0
print("INTEGRATED_RESET_BOUNDARY_PASS", flush=True)

if private:
    # Lifecycle initializer masks are deliberately different; invalid START
    # must not initialize private state at all.
    for op, address in [
        (hw.CMD_RESET, 0),
        (hw.CMD_LOAD_STATE, 0),
        (hw.CMD_START, 0),
        (hw.CMD_START, 256),
    ]:
        fixture(cases[0])
        call(empty)
        for k in private:
            scratch().mem[m["slots"][k]] = py._sim_cast(
                (1 << m["widths"][k]) - 1, hw.uint64_t
            )
        before = {k: leaf(top_regs(), k) for k in private}
        out = drain(call(empty._replace(op=op, address=address)))
        on_start = set(integration["initialize_on_start"])
        for k in private:
            clear = op in {hw.CMD_RESET, hw.CMD_LOAD_STATE} or (
                op == hw.CMD_START and address == 0 and k in on_start
            )
            assert leaf(top_regs(), k) == (0 if clear else before[k]), (
                "lifecycle mask",
                op,
                address,
                k,
            )
    print("INTEGRATED_PRIVATE_LIFECYCLE_PASS", flush=True)

    # Once a RAM write is accepted or scalar export starts, a queued invalid
    # START must preserve the completed transition, then report its own fault.
    witness = next(c for c in cases if c["request"][3] or c["request"][8])
    for phase in ("accepted_write", "scalar_export"):
        regs = fixture(witness)
        out = call(clock)
        for _ in range(20000):
            ready = (
                int(regs["cfg_mem_phase"]) == 1
                if phase == "accepted_write"
                else int(regs["cfg_stage"]) == 5 and int(regs["cfg_index"]) > 0
            )
            if ready:
                break
            assert int(out.busy)
            out = call(clock)
        else:
            raise AssertionError("cancellation phase unreachable")
        out = call(empty._replace(op=hw.CMD_START, address=256))
        assert int(out.busy), "invalid START interrupted a logical transition"
        out = drain(out)
        for k, wanted in witness["expected"].items():
            if k == "hw_fault":
                wanted = hw.HW_FAULT_ADDRESS_RANGE
            assert leaf(regs, k) == wanted, (
                "queued invalid START",
                phase,
                k,
                leaf(regs, k),
                wanted,
            )
    print("INTEGRATED_QUEUED_LIFECYCLE_PASS", flush=True)

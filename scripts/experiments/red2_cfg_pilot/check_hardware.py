# isort: skip_file
"""Compare the emitted physical controller against typed handler witnesses."""

import importlib.util
import json
import sys
from paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import run_syn  # noqa: F401 -- compiler bootstrap must precede pypeline
from pypeline import sim_call, sim_reset
from paths import OUT as P

m = json.loads((P / "control.json").read_text())
cases = json.loads((P / "native-cases.json").read_text())
spec = importlib.util.spec_from_file_location(
    "cfg_hardware",
    P / ("baseline/machine.py" if "--baseline" in sys.argv else "machine.py"),
)
hw = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hw
spec.loader.exec_module(hw)
empty = hw.input_t(
    reset=0,
    start=0,
    state=0,
    setup_addr=0,
    setup_write=0,
    setup_data=0,
    response_valid=0,
    graph_lo=0,
    graph_hi=0,
    control_lo=0,
    control_hi=0,
    control_tag=0,
)
fn = hw.red2_app_lambda_baseline if "--baseline" in sys.argv else hw.red2_app_lambda_cfg
fields = [
    "graph_addr",
    "graph_lo",
    "graph_hi",
    "graph_write",
    "control_addr",
    "control_lo",
    "control_hi",
    "control_tag",
    "control_write",
]
sim_reset()
for case_index, c in enumerate(cases):
    for name, value in c["values"].items():
        sim_call(
            fn,
            empty._replace(
                setup_addr=m["slots"][name], setup_write=1, setup_data=value
            ),
        )
    out = sim_call(fn, empty._replace(start=1, state=c["state"]))
    requests = 0
    responded = False
    response_delay = case_index % 5
    for cycle in range(20000):
        # Only the accepted start carries a meaningful dispatch state. Busy
        # starts and setup writes must not alter this admitted transition.
        i = empty._replace(
            state=(c["state"] + cycle + 1) & 255,
            start=cycle % 7 == 0,
            setup_write=cycle % 11 == 0,
            setup_addr=m["slots"]["microstate"],
            setup_data=18446744073709551615,
        )
        if int(out.request_valid):
            assert not responded, ("duplicate request", case_index, cycle)
            req = [int(getattr(out.request, k)) for k in fields]
            assert req == c["request"], ("request", case_index, req, c["request"])
            if response_delay:
                response_delay -= 1
            else:
                response = c["response"]
                i = i._replace(
                    response_valid=1,
                    graph_lo=response[0],
                    graph_hi=response[1],
                    control_lo=response[2],
                    control_hi=response[3],
                    control_tag=response[4],
                )
                requests += 1
                responded = True
        out = sim_call(fn, i)
        # Acknowledged request_valid may remain visible for its acceptance cycle.
        if responded and int(out.request_valid) and not int(out.done):
            out = sim_call(fn, empty)
            assert not int(out.request_valid), ("request did not retire", case_index)
        if int(out.done):
            break
    else:
        raise AssertionError(("no completion", case_index))
    assert requests == 1
    for name, wanted in c["expected"].items():
        i = empty._replace(setup_addr=m["slots"][name])
        sim_call(fn, i)
        out = sim_call(fn, i)
        assert int(out.setup_data) == wanted, (
            "state",
            case_index,
            name,
            int(out.setup_data),
            wanted,
        )
    print("CFG_PHYSICAL_CONTROLLER_PASS", case_index, c["state"], cycle + 1, flush=True)
print("CFG_PHYSICAL_CONTROLLER_ALL_PASS", len(cases), flush=True)
for offset in (0, 1, 2, 3, 4, 5, 10, 25):
    sim_call(fn, empty._replace(start=1, state=cases[0]["state"]))
    for _ in range(offset):
        sim_call(fn, empty)
    sim_call(fn, empty._replace(reset=1))
    for _ in range(10):
        out = sim_call(fn, empty)
        assert int(out.ready) and not int(out.done) and not int(out.request_valid)
print("CFG_RESET_CANCEL_PASS", flush=True)
if "--baseline" not in sys.argv:
    addr = m["writable_words"]
    wanted = m["initial"][str(addr)]
    sim_call(fn, empty._replace(setup_addr=addr, setup_write=1, setup_data=wanted ^ 1))
    sim_call(fn, empty._replace(setup_addr=addr))
    out = sim_call(fn, empty._replace(setup_addr=addr))
    assert int(out.setup_data) == wanted
    print("CFG_CONSTANT_PROTECTION_PASS", flush=True)

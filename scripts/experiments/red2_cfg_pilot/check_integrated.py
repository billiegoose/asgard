# isort: skip_file
"""Run existing architectural parity checks through the complete candidate top."""

import importlib.util
import os
import sys
import time
from paths import INTEGRATED, ROOT

os.environ.setdefault("RED2_SYN_FLOAT", "1")
sys.path.insert(0, str(ROOT / "scripts"))
import run_syn  # noqa: F401 -- compiler/runtime bootstrap
import pypeline

# Simulation creates a fresh immutable C type descriptor for every bit slice.
# Intern descriptors by their exact name to avoid millions of duplicate Python
# classes during long physical-clock runs. No compiler/source/RTL is modified.
from native_runtime import cache_scalar_types

cache_scalar_types(pypeline)

name = "synthesizable_red2_machine.machine"
spec = importlib.util.spec_from_file_location(name, INTEGRATED / "machine.py")
hw = importlib.util.module_from_spec(spec)
sys.modules[name] = hw
spec.loader.exec_module(hw)
raw = pypeline.sim_call
trace = None
if os.environ.get("RED2_CFG_PILOT_TRACE"):
    from rtl_trace import Trace

    trace = Trace(INTEGRATED, os.environ["RED2_CFG_PILOT_TRACE"])
    native_raw = raw

    def raw(fn, command):
        out = native_raw(fn, command)
        if fn is hw.SynthesizableRED2Machine:
            trace.append(command, out)
        return out


physical_clocks = 0
admitted = 0
max_latency = 0


def call(fn, command):
    global physical_clocks, admitted, max_latency
    out = raw(fn, command)
    if fn is hw.SynthesizableRED2Machine:
        physical_clocks += 1
        if int(out.busy):
            assert int(command.op) in {
                hw.CMD_CLOCK,
                hw.CMD_RESET,
                hw.CMD_LOAD_STATE,
                hw.CMD_START,
            }
            admitted += 1
            for cycles in range(20000):
                assert not int(out.committed)
                advance = hw.red2_command_t(**{**command._asdict(), "op": hw.CMD_CLOCK})
                out = raw(fn, advance)
                physical_clocks += 1
                if not int(out.busy):
                    max_latency = max(max_latency, cycles + 2)
                    if admitted % 25 == 0:
                        print(
                            "INTEGRATED_PROGRESS",
                            admitted,
                            physical_clocks,
                            "max_latency",
                            max_latency,
                            flush=True,
                        )
                    break
            else:
                raise AssertionError("integrated transition failed to finish")
    return out


pypeline.sim_call = call
import check_syn_sim as suite  # noqa: E402 -- install physical-clock adapter first


def application_smoke():
    for source in ("((LAMBDA (x) x) 7)", "(CAR (CONS 7 (CONS 8 NIL)))"):
        _, commits = suite._run_program_lockstep(source)
        assert commits > 0
        print("INTEGRATED_PROGRAM_PASS", source, flush=True)


def scalar_core_smoke():
    for source in (
        "(+ 7 8)",
        "(EQUAL? 7 7)",
        "(EQUAL? (CONS 7 NIL) (CONS 7 NIL))",
        "(EQUAL? (CONS 7 NIL) (CONS 8 NIL))",
        "((Y (LAMBDA (self) (LAMBDA (x) x))) 7)",
    ):
        _, commits = suite._run_program_lockstep(source)
        assert commits > 0
        print("INTEGRATED_PROGRAM_PASS", source, flush=True)


def single_program():
    source = os.environ["RED2_CFG_PILOT_PROGRAM"]
    _, commits = suite._run_program_lockstep(source)
    assert commits > 0
    print("INTEGRATED_PROGRAM_PASS", source, flush=True)


checks = {
    "--application": application_smoke,
    "--full": suite.check,
    "--fibonacci": suite.check_fibonacci,
    "--recp": suite.check_recp,
    "--selector": suite.check_selector_shared_app_promotion,
    "--publication": suite.check_generic_ep_patch_journal,
    "--closure": suite.check_generic_closure_materialization,
    "--scalar-core": scalar_core_smoke,
    "--program": single_program,
}
choice = sys.argv[1] if len(sys.argv) > 1 else "--full"
assert choice in checks
started = time.monotonic()
checks[choice]()
if trace is not None:
    trace.close()
print(
    "INTEGRATED_NATIVE_PARITY_PASS",
    choice,
    "physical_clocks",
    physical_clocks,
    "admitted",
    admitted,
    "max_latency",
    max_latency,
    "seconds",
    round(time.monotonic() - started, 3),
    flush=True,
)

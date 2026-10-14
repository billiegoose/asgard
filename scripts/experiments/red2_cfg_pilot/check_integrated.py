# isort: skip_file
"""Run existing architectural parity checks through the complete candidate top."""

import importlib.util
import os
import runpy
import sys
import time
from paths import INTEGRATED, ROOT

os.environ.setdefault("RED2_SYN_FLOAT", "1")
sys.path.insert(0, str(ROOT / "scripts"))
import run_syn  # noqa: F401 -- compiler/runtime bootstrap
import pypeline

# Simulation creates a fresh immutable C type descriptor for every bit slice.
# Intern descriptors by their exact name to avoid millions of duplicate Python
# classes during long simulated-clock runs. No compiler/source/RTL is modified.
from native_runtime import cache_scalar_types

cache_scalar_types(pypeline)

name = "synthesizable_red2_machine.machine"
spec = importlib.util.spec_from_file_location(name, INTEGRATED / "machine.py")
hw = importlib.util.module_from_spec(spec)
sys.modules[name] = hw
spec.loader.exec_module(hw)
transport = None
environment = "native_hardware_source_simulation"
if os.environ.get("RED2_CFG_PILOT_RTL_INTERACTIVE", "0") == "1":
    from rtl_interactive import RTLServer

    assert not os.environ.get("RED2_CFG_PILOT_TRACE"), (
        "Interactive RTL results are observations, not native expected-output vectors"
    )
    transport = RTLServer(INTEGRATED)
    raw = transport.call
    pypeline.sim_reset = transport.reset
    environment = "Verilator_RTL_compared_with_Concrete_RED2"
else:
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


simulated_clocks = 0
admitted = 0
max_latency = 0


def call(fn, command):
    global simulated_clocks, admitted, max_latency
    out = raw(fn, command)
    if fn is hw.SynthesizableRED2Machine:
        simulated_clocks += 1
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
                simulated_clocks += 1
                if not int(out.busy):
                    max_latency = max(max_latency, cycles + 2)
                    if admitted % 25 == 0:
                        print(
                            "INTEGRATED_PROGRESS",
                            admitted,
                            simulated_clocks,
                            "max_latency",
                            max_latency,
                            flush=True,
                        )
                    break
            else:
                raise AssertionError("integrated transition failed to finish")
    return out


pypeline.sim_call = call
import check_syn_sim as suite  # noqa: E402 -- install simulated-clock adapter first


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


def saved_if_fixtures():
    previous = sys.argv
    try:
        sys.argv = ["check_syn_equality_if.py", "--fixtures-only"]
        runpy.run_path(
            str(ROOT / "scripts/check_syn_equality_if.py"), run_name="__main__"
        )
    finally:
        sys.argv = previous


def equality_checkpoint():
    """Replay the saved IF transition that previously requested stack slot zero.

    Construct its reachable starting state using Concrete RED2, then load it
    through the public hardware ports. This isolates commit 41 without replaying
    the long hardware prefix. Full-program validation remains a separate gate.
    """
    source = "(EQUAL? (CONS 7 NIL) (CONS 7 NIL))"
    action, definitions = suite._prepare_thor_program(source)
    machine = suite.load_faithful_machine(
        action,
        quantum=2000,
        definitions=definitions,
        memory_words=256,
        control_words=256,
    )
    codec = suite.RED2ABICodec()
    image = codec.encode_program(machine)
    metadata = suite._program_literal_metadata(codec, image.struct_selectors)
    processor = suite.ConcreteRED2Machine(
        image.state, **suite._program_concrete_kwargs(codec, image, metadata)
    )
    for _ in range(40):
        assert processor.run_to_commit(), processor.fault
    before = processor.checkpoint()
    assert processor.run_to_commit(), processor.fault
    expected = processor.checkpoint()
    suite._load_program_hardware(before, metadata)
    for _logical in range(1024):
        result = suite.sim_call(
            hw.SynthesizableRED2Machine, suite._command(hw.CMD_CLOCK)
        )
        assert int(result.status) != hw.STATUS_FAULT, (
            "equality checkpoint fault",
            int(result.red2_fault),
            int(result.hw_fault),
        )
        if int(result.committed):
            break
    else:
        raise AssertionError("equality checkpoint did not commit")
    suite._assert_scalar_checkpoint(result, expected)
    assert int(result.status) == processor.status()
    for address in range(256):
        result = suite.sim_call(
            hw.SynthesizableRED2Machine, suite._command(hw.CMD_NOP, address=address)
        )
        assert suite._packed_memory_read(result) == expected.memory[address], address
        assert suite._packed_control_read(result) == expected.control_stack[address], (
            address
        )
    print(
        "EQUALITY_CHECKPOINT_PARITY_PASS",
        41,
        "logical_clocks",
        _logical + 1,
        "comparison",
        "architectural fields and all graph/control RAM words",
        flush=True,
    )


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
    "--equality-checkpoint": equality_checkpoint,
    "--saved-if-fixtures": saved_if_fixtures,
}
choice = sys.argv[1] if len(sys.argv) > 1 else "--full"
assert choice in checks
if transport is not None:
    assert choice in {
        "--application",
        "--scalar-core",
        "--program",
        "--equality-checkpoint",
        "--saved-if-fixtures",
    }
started = time.monotonic()
try:
    checks[choice]()
finally:
    if transport is not None:
        transport.close()
if trace is not None:
    trace.close()
print(
    "INTEGRATED_NATIVE_PARITY_PASS"
    if transport is None
    else "INTEGRATED_RTL_CONCRETE_PARITY_PASS",
    choice,
    "environment",
    environment,
    "simulated_clocks",
    simulated_clocks,
    "admitted",
    admitted,
    "max_latency",
    max_latency,
    "seconds",
    round(time.monotonic() - started, 3),
    flush=True,
)

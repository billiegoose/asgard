"""Native concrete parity for saved equality IF, ordinary IF and list equality.

Requires the pinned enhanced PipelineC runtime, like check_syn_sim.py. Compare
all public architectural fields and every graph/control RAM word for 26 saved
IF cases, then compare four list programs at every architectural commit.
"""

# isort: skip_file
# ruff: noqa: E402
import sys
import importlib
from pathlib import Path

project = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project / "scripts"))
import run_syn  # noqa: F401 -- deterministic compiler/runtime bootstrap
import pypeline as py

sys.path.insert(0, str(project / "scripts/experiments/red2_cfg_pilot"))
from native_runtime import cache_scalar_types

cache_scalar_types(py)
hw = importlib.import_module("synthesizable_red2_machine.machine")
import check_syn_sim as suite

assert hw.GRAPH_WORDS == 256, "this fixture requires a 256-word graph"

abi = suite.abi
private, true, false, stuck = 501, 502, 503, 504


def word(opcode, kind, data, head=0):
    return abi.pack_word(1, opcode, kind, data, head, 0, 0, 0)


count = 0
for mode in ["equality", "ordinary"]:
    for quantum in [0, 9]:
        for condition in [true, false, stuck] if mode == "equality" else [true, false]:
            for kind in (
                ["inline", "app", "ep"] if mode == "equality" else ["app", "ep"]
            ):
                memory = [0] * 256
                branches = [
                    word(abi.MOP_INT, abi.DATA_SIGNED, 71),
                    word(abi.MOP_INT, abi.DATA_SIGNED, 81),
                ]
                if kind != "inline":
                    branches = [
                        word(
                            abi.MOP_APP if kind == "app" else abi.MOP_EP,
                            abi.DATA_SIGNED,
                            9,
                        ),
                        word(
                            abi.MOP_APP if kind == "app" else abi.MOP_EP,
                            abi.DATA_SIGNED,
                            10,
                        ),
                    ]
                memory[2], memory[3] = branches
                memory[4] = word(abi.MOP_APP, abi.DATA_SIGNED, 90)
                memory[5] = abi.pack_word(
                    1, abi.MOP_JOIN, abi.DATA_SIGNED, 4, 0, 0, 1, 1
                )
                memory[6] = word(abi.MOP_SYM, abi.DATA_LITERAL_ID, condition, 1)
                memory[9] = word(abi.MOP_INT, abi.DATA_SIGNED, 99, 1)
                memory[10] = word(abi.MOP_INT, abi.DATA_SIGNED, 42, 1)
                controls = [0] * 256
                top = 0
                if kind != "inline":
                    controls[0] = abi.pack_control_entry(
                        abi.CONTROL_ADDRESS, 200, 0, 0, 0
                    )
                    controls[1] = abi.pack_control_entry(
                        abi.CONTROL_ADDRESS, 201, 0, 0, 0
                    )
                    top = 2
                controls[top] = abi.pack_control_entry(
                    abi.CONTROL_SUBGRAPH, 220, 220, private, 1
                )
                top += 1
                encoded = suite.EncodedArchitecturalState(
                    memory=tuple(memory),
                    control_stack=tuple(controls),
                    pc=5,
                    fsp=6,
                    env=170,
                    c=top,
                    direction=abi.DIRECTION_REVERSE,
                    q=quantum,
                    phi=0,
                    free_space=170,
                    argcnt=4,
                    prim_id=0,
                    fire=0,
                    s_a=0,
                    s_d=0,
                    halted=0,
                    pending_host_op=0,
                    pending_host_argument=0,
                )
                roles = [0] * (private + 1)
                if mode == "ordinary":
                    roles[private] = hw.PRIM0_ROLE_IF
                oracle = suite.ConcreteRED2Machine(
                    encoded,
                    equal_if_literal_id=private if mode == "equality" else 0,
                    prim0_roles=tuple(roles),
                    true_literal_id=true,
                    false_literal_id=false,
                    equal_stuck_literal_id=stuck,
                )
                assert oracle.run_to_commit(), oracle.fault
                expected = oracle.checkpoint()
                suite._load_hardware(encoded)
                for address, literal, flags in [
                    (
                        27,
                        private,
                        hw.LITERAL_SPECIAL_EQUAL_IF if mode == "equality" else 0,
                    ),
                    (28, true, hw.LITERAL_SPECIAL_TRUE),
                    (29, false, hw.LITERAL_SPECIAL_FALSE),
                    (30, stuck, hw.LITERAL_SPECIAL_EQUAL_STUCK),
                ]:
                    suite._load_literal_meta(
                        address,
                        literal,
                        special_flags=flags,
                        prim0_role=hw.PRIM0_ROLE_IF
                        if mode == "ordinary" and literal == private
                        else hw.PRIM0_ROLE_PASSIVE,
                    )
                for _clocks in range(1024):
                    result = suite.sim_call(
                        hw.SynthesizableRED2Machine, suite._command(hw.CMD_CLOCK)
                    )
                    assert int(result.status) != hw.STATUS_FAULT, (
                        quantum,
                        condition,
                        kind,
                        int(result.red2_fault),
                        int(result.hw_fault),
                        int(result.microstate),
                    )
                    if int(result.committed):
                        break
                else:
                    raise AssertionError("Private IF did not commit")
                suite._assert_scalar_checkpoint(result, expected)
                assert expected.q == (
                    quantum if mode == "equality" or quantum == 0 else quantum - 1
                )
                assert int(result.q) == expected.q
                for address in range(256):
                    result = suite.sim_call(
                        hw.SynthesizableRED2Machine,
                        suite._command(hw.CMD_NOP, address=address),
                    )
                    assert (
                        suite._packed_memory_read(result) == expected.memory[address]
                    ), ("memory", quantum, condition, kind, address)
                    result = suite.sim_call(
                        hw.SynthesizableRED2Machine,
                        suite._command(hw.CMD_NOP, address=address),
                    )
                    assert (
                        suite._packed_control_read(result)
                        == expected.control_stack[address]
                    ), ("control", quantum, condition, kind, address)
                count += 1
                print(
                    "SAVED_IF_PARITY_PASS",
                    mode,
                    quantum,
                    condition,
                    kind,
                    _clocks + 1,
                    flush=True,
                )
print("SAVED_IF_PARITY_ALL_PASS", count, flush=True)

programs = (
    []
    if "--fixtures-only" in sys.argv
    else [
        "(EQUAL? (CONS 7 NIL) (CONS 7 NIL))",
        "(EQUAL? (CONS 7 NIL) (CONS 8 NIL))",
        "(EQUAL? (CONS 7 (CONS 8 NIL)) (CONS 7 (CONS 8 NIL)))",
        "(EQUAL? (CONS 7 (CONS 8 NIL)) (CONS 7 (CONS 9 NIL)))",
    ]
)
for source in programs:
    _, commits = suite._run_program_lockstep(source)
    assert commits > 0
    print("SYN_EQUALITY_PROGRAM_PASS", source, commits, flush=True)
if "--fixtures-only" in sys.argv:
    print("SYN_SAVED_IF_FIXTURES_ALL_PASS", count, flush=True)
else:
    print("SYN_EQUALITY_IF_ALL_PASS", count, len(programs), flush=True)

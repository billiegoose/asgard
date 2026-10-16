"""Check exhausted IF capture in the typed hardware source before RTL lowering."""
# isort: skip_file
# run_syn bootstraps PipelineC before importing pypeline.

from dataclasses import replace
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["RED2_SYN_FLOAT"] = "0"
os.environ["RED2_SYN_GRAPH_WORDS"] = "256"
import run_syn as hw  # noqa: E402
from abstract_red2_machine.machine import AbstractRED2Machine  # noqa: E402
from experiments.red2_cfg_pilot.native_runtime import cache_scalar_types  # noqa: E402
import pypeline  # noqa: E402
from red2.representation import MuredOpcode, Word  # noqa: E402

cache_scalar_types(pypeline)
for comparison, expected in (("=", 42), ("<", 40)):
    source = f"((LAMBDA (x) (if ({comparison} x x) (+ x 1) (- x 1))) 41)"
    for quantum in (1, 2, 3):
        action, definitions = hw._prepare_program(source)
        machine = hw.load_faithful_machine(
            action,
            quantum=quantum,
            definitions=definitions,
            memory_words=256,
            control_words=256,
        )
        codec = hw.RED2ABICodec()
        image = codec.encode_program(machine)
        metadata = hw._literal_metadata(codec, image.struct_selectors)
        hw._load_hardware(image.state, metadata)
        result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_NOP))
        for _clocks in range(100_000):
            if int(result.status) != hw.STATUS_RUNNING:
                break
            result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_CLOCK))
        assert int(result.status) == hw.STATUS_QUANTUM_EXHAUSTED, result
        state = codec.decode_state(hw._checkpoint(result))
        view = AbstractRED2Machine(
            state, working_memory_limit=image.working_memory_limit
        )
        view.recharge_quantum(1000)
        view.run_until_suspend(cycle_limit=10000)
        value = view.result_expr()
        assert value.value == expected, value
        print(
            f"PASS IF {comparison} q={quantum}: residual evaluates to {expected}; "
            f"clocks={_clocks}",
            flush=True,
        )

# Compaction preserves inline arguments instead of boxing each one in APP.
# Exercise that residual representation directly, as well as a Boolean returned
# through an environment pointer. Each branch has a distinct observable effect.


def check_uart_branch(condition, *, inline):
    source = f"((LAMBDA (x) (if x (UART-TX 65) (UART-TX 66))) {condition})"
    action, definitions = hw._prepare_program(source)
    machine = hw.load_faithful_machine(
        action, quantum=4, definitions=definitions, memory_words=256, control_words=256
    )
    codec = hw.RED2ABICodec()
    image = codec.encode_program(machine)
    metadata = hw._literal_metadata(codec, image.struct_selectors)
    state = image.state
    if inline:
        words = [
            Word(MuredOpcode.APP, 6),
            Word(MuredOpcode.APP, 4),
            Word(MuredOpcode.SYM, condition),
            Word(MuredOpcode.PRIM_0, "IF", True),
            Word(MuredOpcode.INT, 65),
            Word(MuredOpcode.PRIM_1, "UART-TX", True),
            Word(MuredOpcode.INT, 66),
            Word(MuredOpcode.PRIM_1, "UART-TX", True),
            Word(MuredOpcode.STOP),
        ]
        memory = list(state.memory)
        memory[: len(words)] = [codec.encode_word(word) for word in words]
        state = replace(state, memory=tuple(memory), fsp=8, q=2)
    hw._load_hardware(state, metadata)
    result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_NOP))
    for _clocks in range(10000):
        if int(result.status) != hw.STATUS_RUNNING:
            break
        result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_CLOCK))
    assert int(result.status) == hw.STATUS_HOST_CALL, result
    assert int(result.pending_host_op) == hw._syn_machine.HOST_UART_TX
    checkpoint = hw._checkpoint(result)
    actual = codec.decode_word(checkpoint.memory[int(result.pending_host_argument) - 1])
    expected = 65 if condition == "TRUE" else 66
    assert actual.opcode is MuredOpcode.INT and actual.data == expected, actual
    print(f"PASS IF {condition} inline={inline}: UART {expected}", flush=True)


for _condition in ("TRUE", "FALSE"):
    for _inline in (True, False):
        check_uart_branch(_condition, inline=_inline)

for _condition in ("TRUE", "FALSE"):
    action, definitions = hw._prepare_program(f"(if {_condition} 65 66)")
    machine = hw.load_faithful_machine(
        action, quantum=2, definitions=definitions, memory_words=256, control_words=256
    )
    codec = hw.RED2ABICodec()
    image = codec.encode_program(machine)
    metadata = hw._literal_metadata(codec, image.struct_selectors)
    memory = list(image.state.memory)
    words = [
        Word(MuredOpcode.INT, 66),
        Word(MuredOpcode.INT, 65),
        Word(MuredOpcode.SYM, _condition),
        Word(MuredOpcode.PRIM_0, "IF", True),
        Word(MuredOpcode.STOP),
    ]
    memory[: len(words)] = [codec.encode_word(word) for word in words]
    hw._load_hardware(replace(image.state, memory=tuple(memory), fsp=4), metadata)
    result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_NOP))
    for _clocks in range(10000):
        if int(result.status) != hw.STATUS_RUNNING:
            break
        result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_CLOCK))
    assert int(result.status) == hw.STATUS_COMPLETE, result
    checkpoint = hw._checkpoint(result)
    value = codec.decode_word(checkpoint.memory[checkpoint.pc])
    expected = 65 if _condition == "TRUE" else 66
    assert value.opcode is MuredOpcode.INT and value.data == expected, value
    assert int(result.q) == 1, result
    print(
        f"PASS IF {_condition} inline branches: result {expected}, one contraction",
        flush=True,
    )

"""Check sequencing values that no longer have a child JOIN after reconstruction."""
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
from experiments.red2_cfg_pilot.native_runtime import cache_scalar_types  # noqa: E402
import pypeline  # noqa: E402
from red2.representation import MuredOpcode, Word  # noqa: E402
from io_fixture import inline_words  # noqa: E402

cache_scalar_types(pypeline)


def check(role, *, inline):
    if role == "IO-THEN":
        source = "((LAMBDA (v) (IO-THEN v (UART-TX 65))) NIL)"
    else:
        source = "(IO-BIND (IO-RETURN 65) (LAMBDA (x) (UART-TX x)))"
    action, definitions = hw._prepare_program(source)
    machine = hw.load_faithful_machine(
        action, quantum=20, definitions=definitions, memory_words=256, control_words=256
    )
    codec = hw.RED2ABICodec()
    image = codec.encode_program(machine)
    metadata = hw._literal_metadata(codec, image.struct_selectors)
    state = image.state
    if inline:
        words = inline_words(role, Word, MuredOpcode)
        memory = list(state.memory)
        memory[: len(words)] = [codec.encode_word(word) for word in words]
        state = replace(state, memory=tuple(memory), fsp=len(words) - 1, q=3)
    hw._load_hardware(state, metadata)
    result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_NOP))
    for _clocks in range(10000):
        if int(result.status) != hw.STATUS_RUNNING:
            break
        result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_CLOCK))
    assert int(result.status) == hw.STATUS_HOST_CALL, result
    assert int(result.pending_host_op) == hw._syn_machine.HOST_UART_TX, result
    checkpoint = hw._checkpoint(result)
    actual = codec.decode_word(checkpoint.memory[int(result.pending_host_argument) - 1])
    assert actual.opcode is MuredOpcode.INT and actual.data == 65, actual
    if inline:
        assert int(result.q) == (2 if role == "IO-THEN" else 1), result
    print(f"PASS IO {role} inline={inline}: UART A; clocks={_clocks}", flush=True)


for _role in ("IO-THEN", "IO-BIND"):
    for _inline in (True, False):
        check(_role, inline=_inline)

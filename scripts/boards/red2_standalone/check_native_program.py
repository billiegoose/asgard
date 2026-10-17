"""Check full UART programs in the typed hardware source with quantum relocation.

This simulates the reducer itself. Relocation between completed quanta is modeled
with the standalone supervisor's FIFO spine traversal; frontend RTL and physical
board checks separately qualify that controller and the lowered reducer.
"""

import argparse
import hashlib
import json
import sys
from collections import deque
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from scripts.boards.red2_basys3.run import runtime  # noqa: E402
from scripts.boards.red2_standalone.run import quantum_for  # noqa: E402
from scripts.experiments.red2_cfg_pilot.native_runtime import (  # noqa: E402
    cache_scalar_types,
)

PROGRAMS = {
    "uart-alphanumerics": (
        b"",
        b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz\n",
    ),
    "uart-caesar-plus4": (b"Az09!\x1b", b"Ed09!"),
}


def relocate(memory, root, arena_limit):
    """Match restart.v's latest forwarding entry when graph spines overlap."""
    output, forwarding, pending = [], {}, deque([root])
    while pending:
        cursor = pending.popleft()
        if cursor in forwarding:
            continue
        while True:
            if not 0 <= cursor < len(memory):
                raise ValueError(f"residual address out of range: {cursor}")
            word = memory[cursor]
            opcode, head = word >> 85 & 31, word >> 84 & 1
            if not word >> 90 & 1 or opcode not in (
                1,
                2,
                6,
                8,
                9,
                10,
                11,
                12,
                13,
                14,
                15,
                16,
                17,
                21,
            ):
                raise ValueError(f"invalid residual word at {cursor}: {word:x}")
            forwarding[cursor] = len(output)
            output.append(word)
            if opcode in (1, 16):
                pending.append(word & ((1 << 64) - 1))
            if (8 <= opcode <= 14 and head) or opcode == 21:
                break
            cursor += 1
    for index, word in enumerate(output):
        if word >> 85 & 31 in (1, 16):
            output[index] = word & ~((1 << 64) - 1) | forwarding[word & ((1 << 64) - 1)]
    used = len(output)
    if used + 1 >= arena_limit:
        raise ValueError(f"residual needs {used + 1} of {arena_limit} arena words")
    output.append(1 << 90 | 7 << 85)  # Valid STOP after the relocated residual.
    return output + list(memory[len(output) :]), used


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=PROGRAMS, required=True)
    parser.add_argument(
        "--quantum", type=int, help="override the program's board budget"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-clocks", type=int, default=2_000_000)
    args = parser.parse_args()
    source = ROOT / "examples" / (args.case + ".thor")
    args.quantum = quantum_for(source, args.quantum)
    if not 0 < args.quantum < 1 << 32:
        parser.error("quantum must be positive and fit 32 bits")
    if args.max_clocks <= 0:
        parser.error("logical clock bound must be positive")
    hw = runtime()
    import pypeline

    from red2.representation import MuredOpcode, Word

    cache_scalar_types(pypeline)
    source_hash = hashlib.sha256(
        Path(hw._syn_machine.__file__).read_bytes()
    ).hexdigest()
    action, definitions = hw._prepare_program(source.read_text())
    machine = hw.load_faithful_machine(
        action,
        quantum=args.quantum,
        definitions=definitions,
        memory_words=256,
        control_words=256,
    )
    codec = hw.RED2ABICodec()
    image = codec.encode_program(machine)
    metadata = hw._literal_metadata(codec, image.struct_selectors)
    incoming, expected = PROGRAMS[args.case]
    args.output.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.output / "checkpoint.json"
    record = {
        "case": args.case,
        "quantum": args.quantum,
        "core_source_sha256": source_hash,
        "program_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "working_arena_words": image.working_memory_limit,
        "clocks": 0,
        "restarts": 0,
        "peak_residual_words": 0,
        "input_count": 0,
        "output_hex": "",
        "passed": False,
    }
    state = image.state
    if args.resume:
        saved = json.loads(checkpoint_path.read_text())
        for key in ("case", "quantum", "core_source_sha256", "program_sha256"):
            if saved[key] != record[key]:
                raise ValueError(f"checkpoint mismatch: {key}")
        record.update(saved["record"])
        fields = saved["state"]
        fields["memory"] = tuple(fields["memory"])
        fields["control_stack"] = tuple(fields["control_stack"])
        state = replace(image.state, **fields)
    hw._load_hardware(state, metadata)
    result = hw.sim_call(hw.SynthesizableRED2Machine, hw._command(hw.CMD_NOP))
    seen = bytearray.fromhex(record["output_hex"])
    print(f"START {args.case} q={args.quantum} source={source_hash}", flush=True)
    try:
        while record["clocks"] < args.max_clocks:
            status = int(result.status)
            if status == hw.STATUS_HOST_CALL:
                op = int(result.pending_host_op)
                if op == hw.abi.HOST_UART_RX:
                    index = record["input_count"]
                    if index >= len(incoming):
                        raise ValueError(
                            "program requested unexpected extra UART input"
                        )
                    value = Word(MuredOpcode.INT, incoming[index])
                    record["input_count"] += 1
                elif op == hw.abi.HOST_UART_TX:
                    snapshot = hw._checkpoint(result)
                    value = codec.decode_word(
                        snapshot.memory[int(result.pending_host_argument) - 1]
                    )
                    if value.opcode is not MuredOpcode.INT:
                        raise ValueError(f"UART output is not an integer: {value}")
                    seen.append(value.data & 255)
                    record["output_hex"] = seen.hex()
                    if not expected.startswith(seen):
                        raise ValueError(f"unexpected UART output: {bytes(seen)!r}")
                    print(f"UART {bytes(seen)!r}", flush=True)
                    value = Word(MuredOpcode.SYM, "NIL")
                else:
                    raise ValueError(f"unexpected host operation: {op}")
                result = hw.sim_call(
                    hw.SynthesizableRED2Machine,
                    hw._command(
                        hw.CMD_RESUME, word=hw._word_struct(codec.encode_word(value))
                    ),
                )
            elif status == hw.STATUS_QUANTUM_EXHAUSTED:
                snapshot = hw._checkpoint(result)
                memory, used = relocate(
                    snapshot.memory, snapshot.pc, image.working_memory_limit
                )
                state = replace(
                    image.state, memory=tuple(memory), fsp=used, q=args.quantum
                )
                record["restarts"] += 1
                record["peak_residual_words"] = max(record["peak_residual_words"], used)
                saved = {
                    key: record[key]
                    for key in (
                        "case",
                        "quantum",
                        "core_source_sha256",
                        "program_sha256",
                    )
                }
                saved.update(record=record, state=asdict(state))
                temporary = checkpoint_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(saved, indent=2) + "\n")
                temporary.replace(checkpoint_path)
                hw._native_ram_model("graph_ram").mem[:] = [
                    hw._word_struct(word) for word in memory
                ]
                result = hw.sim_call(
                    hw.SynthesizableRED2Machine,
                    hw._command(hw.CMD_LOAD_STATE, state=hw._state_struct(state)),
                )
                print(
                    f"RESTART {record['restarts']} words={used} "
                    f"clocks={record['clocks']}",
                    flush=True,
                )
            elif status == hw.STATUS_COMPLETE:
                if bytes(seen) != expected or record["input_count"] != len(incoming):
                    raise ValueError("program halted before completing expected I/O")
                record["passed"] = True
                print("NATIVE_UART_PROGRAM_PASS", record, flush=True)
                return
            elif status == hw.STATUS_FAULT:
                record.update(
                    red2_fault=int(result.red2_fault),
                    hw_fault=int(result.hw_fault),
                    microstate=int(result.microstate),
                    pc=int(result.pc),
                    fsp=int(result.fsp),
                )
                raise ValueError(f"reducer fault: {record}")
            else:
                result = hw.sim_call(
                    hw.SynthesizableRED2Machine, hw._command(hw.CMD_CLOCK)
                )
                record["clocks"] += 1
        raise ValueError("finite logical clock bound reached before expected halt")
    except BaseException as error:
        record["error"] = str(error)
        raise
    finally:
        (args.output / "result.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()

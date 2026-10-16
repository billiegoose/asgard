#!/usr/bin/env python3
"""Compile THOR on the host and execute its RED2 graph on a Basys 3."""

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from scripts.boards.red2_basys3.burst_monitor import (  # noqa: E402
    MAX_CLOCK_BURST,
    clock_burst_command,
)
from scripts.boards.red2_basys3.host import SerialLink  # noqa: E402
from scripts.experiments.red2_cfg_pilot.rtl_trace import PortLayout  # noqa: E402


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def runtime():
    # These are the compiled board profile, not simulator capacity defaults.
    os.environ["RED2_SYN_GRAPH_WORDS"] = "256"
    os.environ["RED2_SYN_FLOAT"] = "0"
    import run_syn

    if (
        run_syn.GRAPH_WORDS,
        run_syn.CONTROL_WORDS,
        run_syn.LITERAL_META_WORDS,
        run_syn._syn_machine.RED2_SYN_FLOAT,
    ) != (256, 256, 64, 0):
        raise ValueError(
            "host runtime does not match the 256-word integer board profile"
        )
    return run_syn


def compile_program(hw, source, quantum):
    if not 0 <= quantum < 1 << 32:
        raise ValueError("quantum must fit the board's unsigned 32-bit field")
    action, definitions = hw._prepare_program(source)
    machine = hw.load_faithful_machine(
        action,
        quantum=quantum,
        definitions=definitions,
        memory_words=hw.GRAPH_WORDS,
        control_words=hw.CONTROL_WORDS,
    )
    codec = hw.RED2ABICodec()
    image = codec.encode_program(machine)
    metadata = hw._literal_metadata(codec, image.struct_selectors)
    if len(metadata) > hw.LITERAL_META_WORDS:
        raise ValueError("program exceeds the board's literal metadata capacity")
    return codec, image, metadata


def verify_preparation(prepared, hw, *, allow_standalone=False):
    build = json.loads((prepared / "build-result.json").read_text())
    if not build.get("built"):
        raise ValueError("prepared board has no successful bitstream build")
    for name, digest in build["files_sha256"].items():
        if sha(prepared / name) != digest:
            raise ValueError(f"prepared build artifact changed: {name}")
    timing = json.loads((prepared / "board-timing.json").read_text())
    if not timing or any(value["status"] != "PASS" for value in timing.values()):
        raise ValueError("prepared board did not pass its timing requirement")
    provenance = json.loads((prepared / "provenance.json").read_text())
    if (provenance["input_width"], provenance["output_width"]) != (722, 626):
        raise ValueError("prepared board has an incompatible public interface")
    options = json.loads((prepared / "board-placement-options.json").read_text())
    if not options.get("burst_clock") and not (
        allow_standalone and provenance.get("standalone")
    ):
        raise ValueError("live runner requires a burst-clock board image")
    top = Path(provenance["mapped_core_path"]).parent
    core = json.loads((top / "provenance.json").read_text())
    if sha(top / "machine.py") != provenance["candidate_source_sha256"]:
        raise ValueError("candidate source differs from the prepared board")
    if sha(Path(hw._syn_machine.__file__)) != core["original_source_sha256"]:
        raise ValueError("host ABI source differs from the prepared board's source")
    layout = PortLayout(top)
    if (layout.schema(layout.input_type)[0], layout.schema(layout.output_type)[0]) != (
        722,
        626,
    ):
        raise ValueError("candidate layout differs from the board protocol")
    return provenance, layout


class Device:
    """Public-port commands only: no native reducer or internal RAM access."""

    def __init__(self, hw, layout, exchange, transcript):
        self.hw, self.layout, self.exchange = hw, layout, exchange
        self.transcript = transcript
        self.packets = self.delivered_run_clocks = 0

    def command(self, op, *, edges=1, phase="setup", **fields):
        if not 1 <= edges <= MAX_CLOCK_BURST:
            raise ValueError("invalid engine-clock count")
        if edges != 1 and op != self.hw.CMD_CLOCK:
            raise ValueError("only CLOCK commands can be repeated")
        bits, width = self.layout.pack(
            self.layout.input_type, self.hw._command(op, **fields)
        )
        if width != 722:
            raise ValueError("incorrect packed command width")
        if edges > 1:
            bits = clock_burst_command(bits, edges)
        sequence = self.packets % 256
        packet = {
            "packet": self.packets + 1,
            "sequence": sequence,
            "phase": phase,
            "engine_edges": edges,
            "command": f"{bits:X}",
        }
        try:
            actual = self.exchange(bits, sequence)
        except BaseException as error:
            self.transcript.write(json.dumps({**packet, "error": str(error)}) + "\n")
            self.transcript.flush()
            raise
        self.packets += 1
        if phase == "run":
            self.delivered_run_clocks += edges
        self.transcript.write(json.dumps({**packet, "response": f"{actual:X}"}) + "\n")
        self.transcript.flush()
        return self.layout.unpack(self.layout.output_type, actual)

    def load(self, image, metadata):
        hw = self.hw
        result = self.command(hw.CMD_RESET)
        for _ in range(20000):
            if not result.busy:
                break
            result = self.command(hw.CMD_CLOCK)
        else:
            raise RuntimeError("FPGA reset did not become idle")
        for address, packed in enumerate(image.state.memory):
            self.command(
                hw._syn_machine.CMD_LOAD_MEMORY,
                address=address,
                word=hw._word_struct(packed),
            )
        for address, packed in enumerate(image.state.control_stack):
            if packed:
                self.command(
                    hw._syn_machine.CMD_LOAD_CONTROL,
                    address=address,
                    control=hw._control_struct(packed),
                )
        for slot, meta in enumerate(metadata):
            aux = meta["scalar_op"] | meta["prim0_role"] << 5 | meta["host_op"] << 8
            aux |= meta["special_flags"] << 11
            struct = (meta["struct_tag_id"] & 0xFFFFFFFF) | (
                (meta["struct_offset"] & 0xFFFFFFFF) << 32
            )
            struct |= (meta["struct_role"] & 3) << 64
            self.command(
                hw.CMD_LOAD_LITERAL_META,
                address=slot,
                value=meta["literal_id"],
                aux=aux,
                word=hw._word_struct(struct),
            )
        self.command(hw.CMD_LOAD_STATE, state=hw._state_struct(image.state))
        return self.command(hw.CMD_NOP)

    def checkpoint(self, result):
        if result.busy:
            raise RuntimeError("cannot read a checkpoint while the FPGA is busy")
        graph, control = [], []
        # Both synchronous banks use the same address and return in one response.
        for address in range(max(self.hw.GRAPH_WORDS, self.hw.CONTROL_WORDS)):
            self.command(self.hw.CMD_NOP, address=address, phase="readback")
            readback = self.command(self.hw.CMD_NOP, address=address, phase="readback")
            if address < self.hw.GRAPH_WORDS:
                graph.append(self.hw._packed_word(readback.memory_read))
            if address < self.hw.CONTROL_WORDS:
                control.append(self.hw._packed_control(readback.control_read))
        fields = {
            name: int(getattr(result, name))
            for name in (
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
            )
        }
        return self.hw.EncodedArchitecturalState(
            memory=tuple(graph),
            control_stack=tuple(control),
            c=int(result.control_top),
            **fields,
        )


def execute(device, codec, image, metadata, *, quantum, burst_clocks, max_clocks, host):
    hw = device.hw
    result = device.load(image, metadata)
    host_calls = 0
    while True:
        status = int(result.status)
        if status == hw.STATUS_RUNNING:
            remaining = max_clocks - device.delivered_run_clocks
            if remaining <= 0:
                raise RuntimeError(
                    f"FPGA still RUNNING after {max_clocks} delivered clocks"
                )
            result = device.command(
                hw.CMD_CLOCK, edges=min(burst_clocks, remaining), phase="run"
            )
        elif status == hw.STATUS_HOST_CALL:
            suspended = device.checkpoint(result)
            value = hw.dispatch_encoded_host_call(
                codec,
                suspended,
                host,
                working_memory_limit=image.working_memory_limit,
            )
            result = device.command(
                hw.CMD_RESUME, word=hw._word_struct(value), phase="resume"
            )
            if int(result.status) != hw.STATUS_FAULT:
                result = device.command(hw.CMD_RECHARGE, value=quantum, phase="resume")
            host_calls += 1
        elif status == hw.STATUS_COMPLETE:
            final = device.checkpoint(result)
            if not final.halted or final.pending_host_op:
                raise RuntimeError("FPGA reported COMPLETE without a halted checkpoint")
            decoded = codec.decode_state(final)
            view = hw.AbstractRED2Machine(
                decoded, working_memory_limit=image.working_memory_limit
            )
            text = hw.to_source(view.result_expr())
            return {
                "completed": True,
                "result": text,
                "host_calls": host_calls,
                "final_checkpoint": {
                    name: int(getattr(final, name))
                    for name in (
                        "pc",
                        "fsp",
                        "env",
                        "c",
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
                    )
                },
                "final_graph_sha256": hashlib.sha256(
                    json.dumps(final.memory).encode()
                ).hexdigest(),
                "final_control_sha256": hashlib.sha256(
                    json.dumps(final.control_stack).encode()
                ).hexdigest(),
            }
        elif status == hw.STATUS_QUANTUM_EXHAUSTED:
            return {"completed": False, "status": "QUANTUM_EXHAUSTED", "exit_code": 3}
        elif status == hw.STATUS_FAULT:
            return {
                "completed": False,
                "status": "FAULT",
                "exit_code": 5,
                "red2_fault": int(result.red2_fault),
                "hw_fault": int(result.hw_fault),
                "microstate": int(result.microstate),
            }
        else:
            raise RuntimeError(f"unknown FPGA status: {status}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--expr")
    source.add_argument("--file", type=Path)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument(
        "--serial", required=True, help="Basys 3 USB/JTAG serial number"
    )
    parser.add_argument("--port", required=True)
    parser.add_argument(
        "--log", type=Path, required=True, help="new execution receipt JSON"
    )
    parser.add_argument("--quantum", type=int, default=2000)
    parser.add_argument("--burst-clocks", type=int, default=65536)
    parser.add_argument("--max-clocks", type=int, default=100_000_000)
    parser.add_argument("--clock", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.burst_clocks <= MAX_CLOCK_BURST or args.max_clocks <= 0:
        parser.error("clock burst and total clock budget must be positive and in range")
    started = time.monotonic()
    hw = runtime()
    text = args.expr if args.expr is not None else args.file.read_text()
    codec, image, metadata = compile_program(hw, text, args.quantum)
    provenance, layout = verify_preparation(args.prepared, hw)
    record = {
        "started_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "scope": "THOR compiled on host; graph reductions executed on physical FPGA; "
        "no expected-output vectors or host RED2 reducer",
        "source": text,
        "candidate_source_sha256": provenance["candidate_source_sha256"],
        "bitstream_sha256": sha(args.prepared / "red2_basys3.bit"),
        "runner_sha256": sha(Path(__file__)),
        "completed": False,
        "clock_count_scope": "delivered run-clock edges including any idle tail "
        "within a burst; not exact cycles to halt",
        "burst_clocks": args.burst_clocks,
        "port": args.port,
        "usb_serial": args.serial,
    }
    args.log.parent.mkdir(parents=True, exist_ok=True)
    device = None
    with (
        args.log.open("x") as receipt,
        args.log.with_suffix(".packets.jsonl").open("x") as transcript,
    ):
        try:
            command = [
                "openFPGALoader",
                "--board",
                "basys3",
                "--ftdi-serial",
                args.serial,
                "--write-sram",
                "--bitstream",
                str(args.prepared / "red2_basys3.bit"),
            ]
            record["load_command"] = command
            with args.log.with_suffix(".load.log").open("x") as log:
                subprocess.run(
                    command, stdout=log, stderr=subprocess.STDOUT, check=True
                )
            record["loaded_on_board"] = True
            with contextlib.closing(SerialLink(args.port)) as link:
                device = Device(hw, layout, link.exchange, transcript)
                clock = (
                    hw.LatestFileClockSource(args.clock)
                    if args.clock
                    else hw.SystemClockSource()
                )
                host = hw.TextRed2IoHost(
                    stdin=sys.stdin, stdout=sys.stdout, clock=clock
                )
                with hw.terminal_input_mode(sys.stdin):
                    record.update(
                        execute(
                            device,
                            codec,
                            image,
                            metadata,
                            quantum=args.quantum,
                            burst_clocks=args.burst_clocks,
                            max_clocks=args.max_clocks,
                            host=host,
                        )
                    )
            record.update(
                packets=device.packets, delivered_run_clocks=device.delivered_run_clocks
            )
            if record["completed"]:
                if not record["host_calls"]:
                    print(record["result"])
                if args.verbose:
                    print(
                        "fpga: complete "
                        f"delivered_run_clocks={device.delivered_run_clocks} "
                        f"packets={device.packets}",
                        file=sys.stderr,
                    )
            else:
                print(f"fpga: {record['status']}", file=sys.stderr)
            return record.get("exit_code", 0)
        except BaseException as error:
            record["error"] = str(error)
            raise
        finally:
            if device is not None:
                record.update(
                    confirmed_packets=device.packets,
                    confirmed_run_clocks=device.delivered_run_clocks,
                )
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            record["finished_at_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
            transcript.flush()
            record["transcript_sha256"] = sha(args.log.with_suffix(".packets.jsonl"))
            receipt.write(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        RuntimeError,
        TypeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"fpga: {error}", file=sys.stderr)
        raise SystemExit(2) from error

"""Walk scalar LOAD_STATE bits through RTL and optionally physical UART readback.

This diagnostic never starts a RED2 program. It checks state transport/storage,
not graph reduction correctness. Physical comparisons occur at packet endpoints.
"""

import argparse
import contextlib
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/experiments/red2_cfg_pilot"))
from scripts.boards.red2_basys3.burst_monitor import clock_burst_command  # noqa: E402
from scripts.boards.red2_basys3.host import SerialLink  # noqa: E402
from scripts.experiments.red2_cfg_pilot.rtl_interactive import RTLServer  # noqa: E402
from scripts.experiments.red2_cfg_pilot.rtl_trace import PortLayout  # noqa: E402

CMD_NOP, CMD_CLOCK, CMD_LOAD_STATE = 0, 7, 8


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state_layout(layout):
    fields = layout.records[layout.input_type]
    offset = 0
    for name, typ in fields:
        if name == "state":
            state_type, state_offset = typ, offset
            break
        offset += layout.schema(typ)[0]
    else:
        raise ValueError("input has no state record")
    outputs, offset = {}, 0
    for name, typ in layout.records[layout.output_type]:
        outputs[name] = (offset, layout.schema(typ)[0])
        offset += layout.schema(typ)[0]
    state_fields, offset = [], 0
    for name, typ in layout.records[state_type]:
        width = layout.schema(typ)[0]
        output_offset, output_width = outputs[name]
        assert width == output_width
        state_fields.append((name, offset, width, output_offset))
        offset += width
    assert (state_offset, offset) == (376, 346)
    return state_offset, offset, state_fields


def probe(exchange, patterns, state_offset, fields, clock_plan=None):
    rows, packets = [], 0

    def send(command):
        nonlocal packets
        value = exchange(command, packets % 256)
        packets += 1
        return value

    for index, (label, expected) in enumerate(patterns):
        # LOAD_STATE replaces all scalar state and cancels outstanding work.
        # Two NOPs avoid relying on the response phase of the loading edge.
        send(CMD_LOAD_STATE | expected << state_offset)
        if clock_plan is None:
            # LOAD_STATE itself uses the microcoded register/RAM bridge. Drain
            # it before checking the requested state. A timeout is a failure.
            clocks, status = 1, send(CMD_CLOCK)
            while status >> 625 & 1:
                if clocks >= 4096:
                    raise RuntimeError("LOAD_STATE did not become idle")
                clocks += 1
                status = send(CMD_CLOCK)
        else:
            clocks = clock_plan[index]
            send(clock_burst_command(CMD_CLOCK, clocks) if clocks > 1 else CMD_CLOCK)
        send(CMD_NOP)
        status = send(CMD_NOP)
        actual = sum(
            ((status >> output_offset) & ((1 << width) - 1)) << offset
            for _, offset, width, output_offset in fields
        )
        errors = []
        for name, offset, width, _ in fields:
            mask = (1 << width) - 1
            wanted, observed = expected >> offset & mask, actual >> offset & mask
            if wanted != observed:
                errors.append({"field": name, "expected": wanted, "actual": observed})
        rows.append(
            {
                "pattern": label,
                "settle_clocks": clocks,
                "expected_state": f"{expected:X}",
                "actual_state": f"{actual:X}",
                "status": f"{status:X}",
                "errors": errors,
            }
        )
    return {
        "passed": all(not row["errors"] for row in rows),
        "patterns": len(rows),
        "packets": packets,
        "delivered_core_edges": sum(row["settle_clocks"] + 3 for row in rows),
        "mismatching_patterns": sum(bool(row["errors"]) for row in rows),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--port")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--load-result", type=Path)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    if args.port and (args.image is None or args.load_result is None):
        parser.error("physical mode requires --image and --load-result")
    prepared = json.loads((args.prepared / "provenance.json").read_text())
    top = Path(prepared["mapped_core_path"]).parent
    layout = PortLayout(top)
    state_offset, width, fields = state_layout(layout)
    source_hash = sha(top / "machine.py")
    assert source_hash == prepared["candidate_source_sha256"]
    patterns = [("zero", 0), ("ones", (1 << width) - 1)]
    patterns += [(f"bit_{bit}", 1 << bit) for bit in range(width)]
    record = {
        "scope": __doc__,
        "candidate_source_sha256": source_hash,
        "script_sha256": sha(Path(__file__)),
        "state_fields": fields,
        "physical": None,
    }
    with args.log.open("x") as stream:
        try:
            server = RTLServer(top)
            try:
                record["rtl"] = probe(
                    lambda cmd, seq: server.exchange(cmd),
                    patterns,
                    state_offset,
                    fields,
                )
                record["rtl_binary_sha256"] = sha(server.binary)
            finally:
                server.close()
            assert record["rtl"]["passed"], "RTL state diagnostic failed"
            print("STATE_RTL_PASS", len(patterns), "patterns", flush=True)
            if args.port:
                loaded = json.loads(args.load_result.read_text())
                build_path = args.prepared / "build-result.json"
                build = json.loads(build_path.read_text())
                options = json.loads(
                    (args.prepared / "board-placement-options.json").read_text()
                )
                assert build["built"] and options["burst_clock"]
                assert loaded["loaded_on_board"]
                assert sha(args.image) == loaded["bitstream_sha256"]
                assert sha(args.image) == build["files_sha256"]["red2_basys3.bit"]
                assert sha(build_path) == loaded["build_result_sha256"]
                record.update(
                    image_sha256=sha(args.image),
                    build_result_sha256=sha(build_path),
                    prepared_provenance_sha256=sha(args.prepared / "provenance.json"),
                    load_result_sha256=sha(args.load_result),
                    comparison_scope="physical packet endpoints only",
                )
                with contextlib.closing(SerialLink(args.port)) as link:
                    record["physical"] = probe(
                        link.exchange,
                        patterns,
                        state_offset,
                        fields,
                        [row["settle_clocks"] for row in record["rtl"]["rows"]],
                    )
                physical = record["physical"]
                print(
                    "STATE_PHYSICAL_RESULT",
                    physical["patterns"],
                    "patterns",
                    physical["mismatching_patterns"],
                    "mismatches",
                    flush=True,
                )
        except BaseException as error:
            record["error"] = str(error)
            raise
        finally:
            stream.write(json.dumps(record, indent=2) + "\n")
    if record["physical"] and not record["physical"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

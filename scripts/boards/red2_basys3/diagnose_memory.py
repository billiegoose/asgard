"""Write and read graph RAM patterns, checking physical response-byte lanes."""

import argparse
import collections
import contextlib
import hashlib
import json
import sys
from pathlib import Path

from host import SerialLink

GRAPH_BITS = 128
MEMORY_READ_OFFSET = 364


def analyze(values, actual):
    if len(values) != len(actual):
        raise ValueError("Expected and observed word counts differ")
    errors = []
    for address, (expected, observed) in enumerate(zip(values, actual, strict=True)):
        if not 0 <= expected < 1 << GRAPH_BITS or not 0 <= observed < 1 << GRAPH_BITS:
            raise ValueError("Graph word exceeds 128 bits")
        if expected != observed:
            errors.append(
                {
                    "address": address,
                    "expected": f"{expected:032X}",
                    "actual": f"{observed:032X}",
                    "differing_graph_bits": [
                        bit
                        for bit in range(GRAPH_BITS)
                        if (expected ^ observed) >> bit & 1
                    ],
                }
            )
    lanes = collections.Counter(
        (bit + MEMORY_READ_OFFSET) % 8
        for error in errors
        for bit in error["differing_graph_bits"]
    )
    return {
        "passed": not errors,
        "checked_words": len(values),
        "errors": errors,
        "differing_response_byte_lanes": dict(sorted(lanes.items())),
    }


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--load-result", type=Path, required=True)
    parser.add_argument("--baud", type=int, choices=(115200, 96000), default=115200)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    preparation = json.loads((args.prepared / "provenance.json").read_text())
    loaded = json.loads(args.load_result.read_text())
    if not loaded["loaded_on_board"] or sha(args.image) != loaded["bitstream_sha256"]:
        raise ValueError("Image differs from the successful SRAM load record")
    if args.baud == 96000 and sys.platform != "darwin":
        raise ValueError("The 96000-baud clock probe currently requires macOS")
    values = [0, (1 << GRAPH_BITS) - 1, 0x0123456789ABCDEF0011223344556677]
    values += [1 << bit for bit in range(GRAPH_BITS)]
    rows, observed = [], []
    record = {
        "diagnostic_only": True,
        "scope": (
            "Graph RAM write/read patterns; does not prove RED2 reduction correctness"
        ),
        "requires_initial_idle_state": True,
        "candidate_source_sha256": preparation["candidate_source_sha256"],
        "image_sha256": sha(args.image),
        "load_result_sha256": sha(args.load_result),
        "prepared_provenance_sha256": sha(args.prepared / "provenance.json"),
        "script_sha256": sha(Path(__file__)),
        "baud": args.baud,
        "rows": rows,
    }
    with args.log.open("x") as log:
        try:
            with contextlib.closing(SerialLink(args.port)) as link:
                if args.baud == 96000:
                    import fcntl
                    import struct

                    fcntl.ioctl(link.fd, 0x80085402, struct.pack("Q", args.baud))

                def exchange(op, address, word=0):
                    command = op | address << 4 | word << 20
                    status = link.exchange(command, len(rows) % 256)
                    readback = status >> MEMORY_READ_OFFSET & ((1 << GRAPH_BITS) - 1)
                    rows.append(
                        {
                            "command": f"{command:X}",
                            "status": f"{status:X}",
                            "memory_read": f"{readback:032X}",
                        }
                    )
                    return readback

                for address, value in enumerate(values):
                    exchange(2, address, value)
                for address in range(len(values)):
                    # NOP still performs a synchronous graph read. Observe on
                    # the second accepted command, after the first read edge.
                    exchange(0, address)
                    observed.append(exchange(0, address))
            record.update(analyze(values, observed))
            record["set_response_byte_lanes"] = dict(
                sorted(
                    collections.Counter(
                        bit % 8
                        for row in rows
                        for bit in range(626)
                        if int(row["status"], 16) >> bit & 1
                    ).items()
                )
            )
        except BaseException as error:
            record["error"] = str(error)
            raise
        finally:
            log.write(json.dumps(record, indent=2) + "\n")
    print(
        "GRAPH_MEMORY_DIAGNOSTIC",
        record["checked_words"],
        "words",
        len(record["errors"]),
        "mismatches; response lanes",
        record["differing_response_byte_lanes"],
        flush=True,
    )
    if not record["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

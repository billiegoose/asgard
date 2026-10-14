"""Simulate exact burst counts, payloads, TX stalls and invalid-count recovery."""

import argparse
import binascii
from pathlib import Path

from burst_monitor import burst_clock, clock_burst_command
from check import run
from host import request_frame

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--snapshot-response", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    monitor = output / "monitor.v"
    source = (HERE / "monitor.v").read_text()
    if args.snapshot_response:
        from snapshot_monitor import snapshot_response

        source = snapshot_response(source)
    monitor.write_text(burst_clock(source))
    mask = (1 << 626) - 1
    counts = [1, 2, 257, 65537, 1048575]
    commands = [
        7 | (0x123456789ABCDEF << 376) | (0xABC << 20) | (0xFEDC << 312) for _ in counts
    ]
    requests = []
    responses = []
    base = 0
    for packet, (command, count) in enumerate(zip(commands, counts, strict=True)):
        wire = clock_burst_command(command, count)
        requests.extend(request_frame(wire, packet))
        expected = (command & mask) ^ (base + count - 1)
        body = bytes([packet]) + expected.to_bytes(79, "little")
        responses.extend(
            b"\x5a\xa5" + body + binascii.crc_hqx(body, 0xFFFF).to_bytes(2, "little")
        )
        base += count
    for case, invalid in enumerate([0, 1 << 20, (1 << 32) - 1]):
        command = commands[0]
        sequence = 5 + case * 2
        requests.extend(
            request_frame((command & ~15) | 10 | (invalid << 280), sequence)
        )
        requests.extend(request_frame(command, sequence + 1))
        expected = (command & mask) ^ base
        body = bytes([sequence + 1]) + expected.to_bytes(79, "little")
        responses.extend(
            b"\x5a\xa5" + body + binascii.crc_hqx(body, 0xFFFF).to_bytes(2, "little")
        )
        base += 1
    for name, values in [("requests", requests), ("responses", responses)]:
        (output / (name + ".hex")).write_text("".join(f"{v:02x}\n" for v in values))

    bench = (HERE / "burst_check.sv").read_text()
    bench = bench.replace("__REQUESTS__", str(output / "requests.hex"))
    bench = bench.replace("__RESPONSES__", str(output / "responses.hex"))
    run(output, "burst", [monitor], bench)


if __name__ == "__main__":
    main()

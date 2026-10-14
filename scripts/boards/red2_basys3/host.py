"""Replay concrete-checked public-port vectors over the Basys 3 USB UART."""

import argparse
import binascii
import contextlib
import datetime
import hashlib
import json
import os
import select
import tempfile
import termios
import time
import tty
from pathlib import Path

INPUT_BITS = 722
OUTPUT_BITS = 626
INPUT_BYTES = (INPUT_BITS + 7) // 8
OUTPUT_BYTES = (OUTPUT_BITS + 7) // 8
RESPONSE_BYTES = 2 + 1 + OUTPUT_BYTES + 2


class ReplayProgress:
    """Atomic matched-clock checkpoints; interrupted UART delivery cannot resume."""

    def __init__(self, path: Path):
        self.path = path
        with path.open("x"):
            pass

    def update(self, record, state, elapsed_seconds):
        snapshot = {
            **record,
            "state": state,
            "pid": os.getpid(),
            "updated_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "resume_supported": False,
        }
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(snapshot, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def request_frame(command: int, sequence: int) -> bytes:
    if not 0 <= command < 1 << INPUT_BITS:
        raise ValueError("command exceeds the hardware input width")
    if not 0 <= sequence < 256:
        raise ValueError("sequence exceeds one byte")
    body = bytes([sequence]) + command.to_bytes(INPUT_BYTES, "little")
    return b"\xa5\x5a" + body + binascii.crc_hqx(body, 0xFFFF).to_bytes(2, "little")


def response_value(frame: bytes, sequence: int) -> int:
    if len(frame) != RESPONSE_BYTES or frame[:2] != b"\x5a\xa5":
        raise ValueError("invalid response framing; check the loaded bitstream")
    if frame[2] != sequence:
        raise ValueError("response sequence mismatch; aborting without retry")
    if binascii.crc_hqx(frame[2:-2], 0xFFFF) != int.from_bytes(frame[-2:], "little"):
        raise ValueError("response CRC mismatch; aborting without retry")
    value = int.from_bytes(frame[3:-2], "little")
    if value >= 1 << OUTPUT_BITS:
        raise ValueError("response padding is nonzero")
    return value


class SerialLink:
    """POSIX serial, with no optional Python dependencies and no implicit retry."""

    def __init__(self, port: str, timeout: float = 3):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.original = termios.tcgetattr(self.fd)
        self.timeout = timeout
        try:
            tty.setraw(self.fd)
            attrs = termios.tcgetattr(self.fd)
            attrs[4] = attrs[5] = termios.B115200
            attrs[2] |= termios.CLOCAL | termios.CREAD
            if hasattr(termios, "CRTSCTS"):
                attrs[2] &= ~termios.CRTSCTS
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
            termios.tcflush(self.fd, termios.TCIOFLUSH)
        except BaseException:
            os.close(self.fd)
            raise

    def close(self):
        try:
            termios.tcsetattr(self.fd, termios.TCSANOW, self.original)
        finally:
            os.close(self.fd)

    def exchange(self, command: int, sequence: int) -> int:
        packet = memoryview(request_frame(command, sequence))
        deadline = time.monotonic() + self.timeout
        while packet:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([], [self.fd], [], remaining)[1]:
                raise TimeoutError("UART write timed out; no command retry was sent")
            try:
                packet = packet[os.write(self.fd, packet) :]
            except BlockingIOError:
                continue
        response = bytearray()
        while len(response) < RESPONSE_BYTES:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                raise TimeoutError("UART response timed out; no command retry was sent")
            try:
                chunk = os.read(self.fd, RESPONSE_BYTES - len(response))
            except BlockingIOError:
                continue
            if not chunk:
                raise ConnectionError("UART disconnected")
            response.extend(chunk)
        return response_value(bytes(response), sequence)


def verify_vectors(path: Path, candidate_sha: str) -> dict:
    metadata = json.loads(path.with_suffix(".json").read_text())
    if (metadata["input_width"], metadata["output_width"]) != (
        INPUT_BITS,
        OUTPUT_BITS,
    ):
        raise ValueError("trace port layout differs from the board interface")
    if metadata["candidate_sha256"] != candidate_sha:
        raise ValueError("trace source differs from the prepared board candidate")
    origin = metadata.get("expected_output_origin")
    if origin not in {
        None,
        "native hardware-source simulation",
        "Verilator RTL simulation",
    }:
        raise ValueError("unrecognized expected-output trace origin")
    if origin == "Verilator RTL simulation":
        validation = metadata.get("semantic_validation", {})
        model = metadata.get("rtl_model", {})
        if (
            not isinstance(validation, dict)
            or not isinstance(model, dict)
            or validation.get("passed") is not True
            or not validation.get("program")
            or validation.get("termination") != "HALTED"
            or model.get("candidate_source_sha256") != candidate_sha
            or not all(
                isinstance(model.get(key), str)
                and len(model[key]) == 64
                and set(model[key]) <= set("0123456789abcdef")
                for key in ("binary_sha256", "manifest_sha256")
            )
        ):
            raise ValueError(
                "RTL observations lack a completed same-source semantic gate"
            )
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["vectors_sha256"]:
        raise ValueError("trace hash differs from its completed validation record")
    # Validate all rows before the first hardware command is sent.
    count = 0
    with path.open() as rows:
        for row in rows:
            incoming, expected = (int(token, 16) for token in row.split())
            if not 0 <= incoming < 1 << INPUT_BITS:
                raise ValueError("trace command exceeds input width")
            if not 0 <= expected < 1 << OUTPUT_BITS:
                raise ValueError("trace expectation exceeds output width")
            count += 1
    if count != metadata["cycles"] or not count:
        raise ValueError("trace row count differs from its completed validation record")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="USB-UART channel, usually *1")
    parser.add_argument("--prepared", type=Path, default=Path("build/red2-basys3"))
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("vectors", type=Path)
    parser.add_argument("--log", type=Path, required=True, help="new result JSON path")
    parser.add_argument(
        "--burst-clock",
        action="store_true",
        help="Combine identical CLOCKs on a burst-capable image; compare endpoints",
    )
    args = parser.parse_args()
    preparation = json.loads((args.prepared / "provenance.json").read_text())
    metadata = verify_vectors(args.vectors, preparation["candidate_source_sha256"])
    options_path = args.prepared / "board-placement-options.json"
    burst_capable = False
    if options_path.exists():
        expected_hash = preparation["files_sha256"].get(options_path.name)
        if hashlib.sha256(options_path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("prepared monitor options differ from their provenance")
        burst_capable = json.loads(options_path.read_text()).get("burst_clock", False)
    if args.burst_clock and not burst_capable:
        parser.error("--burst-clock requires a build prepared with --burst-clock")
    packets = None
    if burst_capable:
        # Preflight the complete trace before touching hardware: opcode 10 belongs
        # to the frontend on this image and must never arrive as a native command.
        rows = [
            tuple(int(word, 16) for word in row.split())
            for row in args.vectors.read_text().splitlines()
        ]
        if any(command & 15 == 10 for command, _ in rows):
            raise ValueError("native opcode 10 is reserved by the burst frontend")
        if args.burst_clock:
            from burst_monitor import burst_trace

            packets = list(burst_trace(rows))
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    started = time.monotonic()
    record = {
        "port": args.port,
        "candidate_source_sha256": preparation["candidate_source_sha256"],
        "prepared_provenance_sha256": hashlib.sha256(
            (args.prepared / "provenance.json").read_bytes()
        ).hexdigest(),
        "vectors_sha256": metadata["vectors_sha256"],
        "expected_output_origin": metadata.get(
            "expected_output_origin", "native hardware-source simulation (legacy trace)"
        ),
        "expected_clocks": metadata["cycles"],
        "completed_pass": False,
        "compared_clocks": 0,
    }
    if metadata.get("expected_output_origin") == "Verilator RTL simulation":
        record["expected_rtl_model"] = metadata["rtl_model"]
        record["expected_semantic_validation"] = metadata["semantic_validation"]
    if args.burst_clock:
        del record["compared_clocks"]
        record.update(
            burst_clock=True,
            comparison_scope="packet endpoints only",
            executed_clock_count_scope="confirmed packets; lower bound on failure",
            executed_clocks=0,
            compared_samples=0,
            expected_samples=len(packets),
        )
    # Reserve the result file before touching hardware; never erase earlier evidence.
    with args.log.open("x") as log:
        progress = ReplayProgress(args.log.with_suffix(".progress.json"))
        progress.update(record, "running", time.monotonic() - started)
        try:
            with contextlib.closing(SerialLink(args.port, args.timeout)) as link:
                with args.vectors.open() as rows:
                    one_edge_packets = (
                        (*[int(token, 16) for token in row.split()], 1) for row in rows
                    )
                    executed = 0
                    for index, (incoming, expected, edges) in enumerate(
                        packets if packets is not None else one_edge_packets
                    ):
                        endpoint = executed + edges - 1
                        actual = link.exchange(incoming, index % 256)
                        if actual != expected:
                            record.update(
                                mismatch_clock=endpoint,
                                actual=f"{actual:X}",
                                expected=f"{expected:X}",
                            )
                            raise ValueError(
                                f"FPGA output mismatch at clock {endpoint}"
                            )
                        executed += edges
                        if args.burst_clock:
                            record.update(
                                executed_clocks=executed,
                                compared_samples=index + 1,
                                last_compared_clock=endpoint,
                            )
                        else:
                            record["compared_clocks"] = index + 1
                        if (index + 1) % 100 == 0:
                            progress.update(
                                record, "running", time.monotonic() - started
                            )
                            print("BOARD_REPLAY_PROGRESS", executed, flush=True)
            record["completed_pass"] = True
            if args.burst_clock:
                print(
                    "BOARD_BURST_REPLAY_PASS",
                    executed,
                    "endpoint_samples",
                    record["compared_samples"],
                    flush=True,
                )
            else:
                print("BOARD_REPLAY_PASS", metadata["cycles"], flush=True)
        except BaseException as exc:
            record["error"] = str(exc)
            raise
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            log.write(json.dumps(record, indent=2) + "\n")
            log.flush()
            progress.update(
                record,
                "passed" if record["completed_pass"] else "failed",
                record["elapsed_seconds"],
            )


if __name__ == "__main__":
    main()

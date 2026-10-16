"""Program a standalone image and observe raw UART without sending runtime commands."""

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import select
import subprocess
import sys
import termios
import time
import tty
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from scripts.boards.red2_standalone.image import (  # noqa: E402
    FLASH_OFFSET,
    HEADER,
    MAGIC,
)


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def verify(prepared, image):
    build = json.loads((prepared / "build-result.json").read_text())
    assert build["built"]
    for name, digest in build["files_sha256"].items():
        assert sha(prepared / name) == digest, name
    provenance = json.loads((prepared / "provenance.json").read_text())
    assert provenance["standalone"]["flash_offset"] == FLASH_OFFSET
    for name, digest in provenance["files_sha256"].items():
        assert sha(prepared / name) == digest, name
    assert all(
        c["status"] == "PASS"
        for c in json.loads((prepared / "board-timing.json").read_text()).values()
    )
    assert (
        json.loads((prepared / "board-physical-lut-sites.json").read_text())[
            "unique_physical_lut_sites"
        ]
        <= 20800
    )
    record = json.loads(image.with_suffix(".json").read_text())
    assert sha(image) == record["sha256"]
    assert provenance["candidate_source_sha256"] == record["core_source_sha256"]
    data = image.read_bytes()
    magic, version, count, quantum, words, nil, size, crc, pair, pad = HEADER.unpack(
        data[:64]
    )
    assert magic == MAGIC and version == 1 and words == 256 and quantum > 0 and pair > 0
    assert size == len(data) - 64 == count * 91 and zlib.crc32(data[64:]) == crc
    nil_bits = int.from_bytes(nil, "little")
    assert pad == bytes(12) and pair == record["literal_ids"]["PAIR"]
    assert nil_bits & (1 << 90) and (nil_bits >> 85) & 31 == 11
    assert (nil_bits >> 81) & 3 == 3
    assert nil_bits & ((1 << 64) - 1) == record["literal_ids"]["NIL"]
    return provenance


@contextlib.contextmanager
def receiver(port):
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        attrs = termios.tcgetattr(fd)
        attrs[4] = attrs[5] = termios.B115200
        attrs[2] |= termios.CLOCAL | termios.CREAD
        if hasattr(termios, "CRTSCTS"):
            attrs[2] &= ~termios.CRTSCTS
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        termios.tcflush(fd, termios.TCIFLUSH)
        yield fd
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, saved)
        os.close(fd)


def observe(fd, expected, seconds):
    start = time.monotonic()
    data = bytearray()
    times = []
    while not bytes(data).startswith(expected):
        remaining = seconds - (time.monotonic() - start)
        if remaining <= 0:
            raise RuntimeError(f"missing expected UART; received {bytes(data)!r}")
        if not select.select([fd], [], [], min(remaining, 1))[0]:
            continue
        part = os.read(fd, 4096)
        if not part:
            continue
        data.extend(part)
        times.append({"seconds": round(time.monotonic() - start, 6), "hex": part.hex()})
        sys.stdout.write(part.decode("ascii", errors="backslashreplace"))
        sys.stdout.flush()
        if not (expected.startswith(data) or data.startswith(expected)):
            raise RuntimeError(f"unexpected UART {bytes(data)!r}")
    print(flush=True)
    return {
        "received_hex": bytes(data).hex(),
        "samples": times,
        "host_uart_bytes_written": 0,
        "scope": "raw UART observation; no host clock values or runtime commands",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared", type=Path, required=True)
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--serial", default="210183735787")
    p.add_argument("--port", default="/dev/cu.usbserial-2101837357871")
    p.add_argument("--expected", default="...")
    p.add_argument("--observe-seconds", type=float, default=60)
    p.add_argument(
        "--persistent",
        action="store_true",
        help="After SRAM qualification, program configuration flash and test reboot",
    )
    a = p.parse_args()
    verify(a.prepared, a.image)
    assert not a.log.exists()
    a.log.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "started_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "image_sha256": sha(a.image),
        "bitstream_sha256": sha(a.prepared / "red2_basys3.bit"),
        "persistent_requested": a.persistent,
        "passed": False,
        "stages": [],
    }
    base = ["openFPGALoader", "--board", "basys3", "--ftdi-serial", a.serial]
    fallback = ROOT / "build/red2-basys3-shared-multiplier/red2_basys3.bit"

    def run(name, command):
        log = a.log.with_name(a.log.stem + "-" + name + ".log")
        with log.open("x") as f:
            subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, check=True)
        record["stages"].append(
            {"stage": name, "command": command, "log": str(log), "passed": True}
        )

    try:
        # Use fpgatool's reserved-area checks and verified binary programmer.
        run(
            "program-data",
            [
                sys.executable,
                str(ROOT.parent / "fpgatool/fpgatool.py"),
                "program-data",
                str(a.image.resolve()),
                "--offset",
                hex(FLASH_OFFSET),
            ],
        )
        with receiver(a.port) as fd:
            run(
                "load-sram",
                [
                    *base,
                    "--write-sram",
                    "--bitstream",
                    str(a.prepared / "red2_basys3.bit"),
                ],
            )
            termios.tcflush(fd, termios.TCIFLUSH)
            record["sram_observation"] = observe(
                fd, a.expected.encode(), a.observe_seconds
            )
        if a.persistent:
            with receiver(a.port) as fd:
                run(
                    "program-config",
                    [
                        *base,
                        "--write-flash",
                        "--verify",
                        "--bitstream",
                        str(a.prepared / "red2_basys3.bit"),
                    ],
                )
                termios.tcflush(fd, termios.TCIFLUSH)
                record["flash_observation"] = observe(
                    fd, a.expected.encode(), a.observe_seconds
                )
            with receiver(a.port) as fd:
                run("reset-from-flash", [*base, "--reset"])
                termios.tcflush(fd, termios.TCIFLUSH)
                record["reset_observation"] = observe(
                    fd, a.expected.encode(), a.observe_seconds
                )
        record["passed"] = True
    except BaseException as error:
        record["error"] = str(error)
        try:
            run(
                "restore-qualified-sram",
                [*base, "--write-sram", "--bitstream", str(fallback)],
            )
        except BaseException as restore_error:
            record["restore_error"] = str(restore_error)
        raise
    finally:
        record["finished_at_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
        a.log.write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()

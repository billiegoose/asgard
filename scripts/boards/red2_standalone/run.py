"""Compile and persist a THOR program for the installed standalone RED2 engine."""

import argparse
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.boards.red2_standalone.deploy import verify  # noqa: E402
from scripts.boards.red2_standalone.image import (  # noqa: E402
    DEFAULT_PREPARED,
    FLASH_OFFSET,
    compile_image,
)


def quantum_for(source, override):
    if override is not None:
        return override
    try:
        name = source.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return 5
    profiles = tomllib.loads(Path(__file__).with_name("programs.toml").read_text())
    return profiles.get("programs", {}).get(name, {}).get("quantum", 5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="THOR source file")
    parser.add_argument(
        "--quantum", type=int, help="override the program's board budget"
    )
    parser.add_argument("--prepared", type=Path, default=DEFAULT_PREPARED)
    parser.add_argument(
        "--compile-only", action="store_true", help="check and save the image only"
    )
    args = parser.parse_args()
    source = args.file.resolve()
    quantum = quantum_for(source, args.quantum)
    prepared = args.prepared.resolve()
    fpgatool = ROOT / "tools/fpgatool/fpgatool.py"
    if not args.compile_only:
        if not fpgatool.is_file():
            parser.error(
                "initialize fpgatool: git submodule update --init tools/fpgatool"
            )
        if shutil.which("openFPGALoader") is None:
            parser.error("openFPGALoader must be installed and available on PATH")

    data, metadata = compile_image(source.read_text(), prepared, quantum)
    output_root = ROOT / "build/red2-standalone/programs"
    output_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=f"{source.stem}-", dir=output_root))
    image = output / "program.bin"
    image.write_bytes(data)
    metadata["source_path"] = str(source)
    image.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    verify(prepared, image)
    print(
        f"Compiled {source.name}: {len(data)} bytes, "
        f"{metadata['command_count']} commands, quantum {quantum}",
        flush=True,
    )
    print(f"Image: {image}", flush=True)
    if args.compile_only:
        print("Image checks passed; board unchanged.")
        return

    receipt = {
        "started_at_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "source_path": str(source),
        "prepared": str(prepared),
        "image_sha256": metadata["sha256"],
        "flash_offset": FLASH_OFFSET,
        "scope": "verified flash write and reset; runtime not observed",
        "passed": False,
        "stages": [],
    }
    try:
        for name, command in (
            (
                "program-data",
                [
                    sys.executable,
                    str(fpgatool),
                    "program-data",
                    str(image),
                    "--board",
                    "basys3",
                    "--offset",
                    hex(FLASH_OFFSET),
                ],
            ),
            ("reset-from-flash", ["openFPGALoader", "--board", "basys3", "--reset"]),
        ):
            subprocess.run(command, check=True)
            receipt["stages"].append({"stage": name, "passed": True})
        receipt["passed"] = True
    except BaseException as error:
        receipt["error"] = str(error)
        raise
    finally:
        receipt["finished_at_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
        (output / "deployment.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Program stored in flash; FPGA restarted to load it.")
    print("UART: 115200 baud, 8N1. LD4 running; LD5 halted; LD6 runtime fault.")


if __name__ == "__main__":
    main()

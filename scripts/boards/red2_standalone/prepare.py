"""Prepare autonomous peripherals around the existing qualified mapped RED2 core."""

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from scripts.experiments.red2_cfg_pilot.rtl_trace import PortLayout  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    subprocess.run(
        [
            sys.executable,
            str(HERE.parent / "red2_basys3/prepare.py"),
            "--report",
            str(ROOT / "docs/handoffs/synth-red2-shared-multiplier-results.json"),
            "--variant",
            "shared-multiply",
            "--no-relocate-response-byte",
            "--output",
            str(a.output),
        ],
        check=True,
    )
    out = a.output.resolve()
    record = json.loads((out / "provenance.json").read_text())
    # Fail if hand-written signal slices no longer match the qualified ABI.
    layout = PortLayout(Path(record["mapped_core_path"]).parent)
    lines = [
        "// Packed public ABI, verified against the qualified core during preparation."
    ]
    for prefix, typ in [("IN", layout.input_type), ("OUT", layout.output_type)]:
        offset = 0
        for name, sub in layout.records[typ]:
            width = layout.schema(sub)[0]
            lines.append(
                f"`define {prefix}_{name.upper()} {offset + width - 1}:{offset}"
            )
            offset += width
    assert (HERE / "layout.vh").read_text() == "\n".join(lines) + "\n"
    for name in ["board.v", "controller.v", "flash.v", "layout.vh"]:
        shutil.copy2(HERE / name, out / name)
    ys = (
        (out / "board.ys")
        .read_text()
        .replace(
            "uart.v monitor.v packed.v board.v",
            "uart.v flash.v controller.v packed.v board.v",
        )
    )
    (out / "board.ys").write_text(ys)
    pins = {
        "QspiDQ0": "D18",
        "QspiDQ1": "D19",
        "QspiDQ2": "G18",
        "QspiDQ3": "F18",
        "QspiCSn": "K19",
    }
    with (out / "board.xdc").open("a") as f:
        for port, pin in pins.items():
            f.write(f"set_property LOC {pin} [get_ports {{{port}}}]\n")
            f.write(f"set_property IOSTANDARD LVCMOS33 [get_ports {{{port}}}]\n")
        f.write("set_property PULLUP true [get_ports QspiDQ1]\n")
    # Reuse the exact backend that produced the qualified image. Avoid a new
    # Nix evaluation or chip database build during a board integration change.
    runtime = ROOT / "build/red2-basys3-shared-multiplier"
    for name in ["frozen-runtime-env.sh", "backend-pin.json", "fast-fasm2frames.py"]:
        shutil.copy2(runtime / name, out / name)
    pin = json.loads((out / "backend-pin.json").read_text())
    shim = (ROOT / "tools/fpgatool/toolchain/compat/nextpnr-xilinx").read_text()
    shim = shim.replace("__FPGATOOL_REAL_NEXTPNR_HIMBAECHEL__", pin["path"])
    bash = "/nix/store/v8llyqw71lygr2llhmcc8ya5bdlzq45v-bash-5.3p9/bin/bash"
    shim = shim.replace("#!/usr/bin/env bash", "#!" + bash, 1)
    (out / "nextpnr-xilinx").write_text(shim)
    (out / "nextpnr-xilinx").chmod(0o755)
    (out / "check-backend.py").write_text(
        "import hashlib,json\nfrom pathlib import Path\n"
        "p=json.loads(Path('backend-pin.json').read_text())\n"
        "assert hashlib.sha256(Path(p['path']).read_bytes()).hexdigest()==p['sha256']\n"
        "assert Path(p['chipdb']).is_file()\n"
    )
    implement = (
        (out / "implement.sh")
        .read_text()
        .replace(
            'fasm2frames --part "$part" --db-root "$PRJXRAY_DB_DIR/artix7" '
            "board.fasm > board.frames",
            'python3 fast-fasm2frames.py --part "$part" '
            '--db-root "$PRJXRAY_DB_DIR/artix7" board.fasm board.frames',
        )
    )
    (out / "implement.sh").write_text(implement)
    command = [
        "podman",
        "run",
        "--rm",
        "--network",
        "none",
        "-v",
        "fpgatool-nix:/nix",
        "-v",
        f"{out}:/design",
        "-w",
        "/design",
        "--entrypoint",
        bash,
        record["container_image"],
        "-c",
        "set -euo pipefail\nsource frozen-runtime-env.sh\n"
        "export PATH=/design:$PATH\npython3 check-backend.py\nbash implement.sh",
    ]
    (out / "build.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n" + shlex.join(command) + "\n"
    )
    record["standalone"] = {
        "flash_offset": 0x220000,
        "image_format": "RED2FLSH v1",
        "clock": "64-bit milliseconds since successful program load",
        "uart": "physical 115200 baud, 8N1; no serial debug monitor",
    }
    record["files_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(out.iterdir())
        if p.name != "provenance.json"
    }
    (out / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()

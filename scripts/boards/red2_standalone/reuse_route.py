"""Reuse an identical board's completed route for an exporter-only correction."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.prepared.resolve()
    built = json.loads((source / "build-result.json").read_text())
    assert built["built"]
    for name, digest in built["files_sha256"].items():
        assert sha(source / name) == digest, name
    assert all(
        item["status"] == "PASS"
        for item in json.loads((source / "board-timing.json").read_text()).values()
    )
    assert (
        json.loads((source / "board-physical-lut-sites.json").read_text())[
            "unique_physical_lut_sites"
        ]
        <= 20800
    )
    unchanged = [
        "core.json",
        "uart.v",
        "packed.v",
        "board.v",
        "controller.v",
        "flash.v",
        "layout.vh",
        "board.ys",
        "area.abc",
        "board.xdc",
        "board.sdc",
        "clocks.py",
        "board-placement-options.json",
        "relocate_monitor.py",
        "audit.py",
        "audit_bram.py",
        "backend-pin.json",
        "frozen-runtime-env.sh",
    ]
    for name in unchanged:
        assert sha(source / name) == sha(out / name), name
    artifacts = [
        "board.json",
        "board-resources.json",
        "board-map.log",
        "board-place.log",
        "board-placed.json",
        "board-selected-placement.json",
        "board-clock-names.json",
        "board-route.sdc",
        "backend-versions.txt",
        "board-route-report.json",
        "board-route.log",
        "board-routed.json",
    ]
    assert not any((out / name).exists() for name in artifacts)
    assert not (out / "board-original.fasm").exists()
    for name in artifacts:
        shutil.copy2(source / name, out / name)
    shutil.copy2(source / "board.fasm", out / "board-original.fasm")
    reuse = {
        "source": str(source),
        "source_build_result_sha256": sha(source / "build-result.json"),
        "scope": (
            "Identical HDL, mapping recipes, constraints and backend; "
            "reuse placement/routing and regenerate FASM configuration, "
            "frames and bitstream only"
        ),
        "input_files_sha256": {
            name: sha(out / name)
            for name in unchanged + artifacts + ["board-original.fasm"]
        },
    }
    (out / "route-reuse.json").write_text(json.dumps(reuse, indent=2) + "\n")
    implement = (out / "implement.sh").read_text()
    finish = """#!/usr/bin/env bash
set -euo pipefail
source frozen-runtime-env.sh
python3 - <<'PY'
import hashlib,json
from pathlib import Path
r=json.loads(Path('route-reuse.json').read_text())
for name,digest in r['input_files_sha256'].items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest,name
PY
python3 complete-bufg-fasm.py --input board-original.fasm \\
    --output board.fasm --report board-bufg-routethroughs.json
placement=board-placed.json
"""
    finish += implement[implement.index('python3 audit.py "$placement"') :]
    (out / "finish-reused-route.sh").write_text(finish)
    launch = (
        (out / "build.sh")
        .read_text()
        .replace("bash implement.sh", "bash finish-reused-route.sh")
    )
    assert launch != (out / "build.sh").read_text()
    (out / "finish-reused-route-build.sh").write_text(launch)
    provenance = json.loads((out / "provenance.json").read_text())
    for name in [
        "board-original.fasm",
        "route-reuse.json",
        "finish-reused-route.sh",
        "finish-reused-route-build.sh",
    ]:
        provenance["files_sha256"][name] = sha(out / name)
    provenance["standalone"]["route_reuse"] = reuse
    (out / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("IDENTICAL_BOARD_ROUTE_REUSE_PREPARED", out, flush=True)


if __name__ == "__main__":
    main()

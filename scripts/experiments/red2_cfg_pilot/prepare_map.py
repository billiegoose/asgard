"""Prepare the recorded GHDL/Yosys experiment; never modify production tools."""

import hashlib
import json
import sys
from pathlib import Path

from paths import INTEGRATED, OUT, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import pipelinec_toolchain as tc

tc.verify_enhanced_compiler(tc.configured_root())
root = (
    INTEGRATED
    if "--integrated" in sys.argv
    else OUT / "baseline"
    if "--baseline" in sys.argv
    else OUT
)
hdl = root / "hdl"
files = [Path(f).resolve() for f in (hdl / "vhdl_files.txt").read_text().split()]
assert files and all(f.is_file() for f in files)
paths = ["/experiment/hdl/" + str(f.relative_to(hdl)) for f in files]
(root / "frontend.ys").write_text(
    "ghdl --std=08 " + " ".join(paths) + " -e top\n"
    "hierarchy -check -top top\nwrite_rtlil /experiment/frontend.il\n"
    "flatten\nopt -full\nopt_muxtree\nopt -full\n"
    "write_json /experiment/coarse.json\nstat -width\n"
)
(root / "area.abc").write_text("strash\ndc2\nif -a\n")
(root / "baseline-area.ys").write_text(
    "read_json /experiment/coarse.json\n"
    "synth_xilinx -arch xc7 -noiopad -top top -run begin:map_luts\n"
    "write_rtlil /experiment/baseline-preabc.il\n"
    "abc -lut 6 -script /experiment/area.abc\nclean\n"
    "techmap -map +/xilinx/ff_map.v\n"
    "techmap -map +/xilinx/lut_map.v -map +/xilinx/cells_map.v -D LUT_WIDTH=6\n"
    "xilinx_dffopt\nopt_lut_ins -tech xilinx\n"
    "synth_xilinx -arch xc7 -noiopad -top top -run finalize:edif\n"
    "write_json /experiment/baseline-area.json\n"
)
yosys = "/nix/store/8xp00x56zj0nxqk3h334176g2d25jmvd-yosys-0.67/bin"
ghdl = "/nix/store/4gcl6ba0jcmvq2py06cz57fimap9xjvm-ghdl-mcode-6.0.0/bin"
plugin = (
    "/nix/store/c01zl2b0iqg31j0lpc904cf8jj6f1djv-yosys-ghdl-0-unstable-2025-05-23"
    "/share/yosys/plugins/ghdl.so"
)
(root / "run.sh").write_text(
    "#!/usr/bin/env bash\nset -euo pipefail\n"
    f"export PATH={yosys}:{ghdl}:$PATH\n"
    "yosys -V > /experiment/backend-versions.txt\n"
    "ghdl --version >> /experiment/backend-versions.txt\n"
    f"yosys -Q -T -m {plugin} -s /experiment/frontend.ys "
    "> /experiment/map-frontend.log 2>&1\n"
    "yosys -Q -T -s /experiment/baseline-area.ys "
    "> /experiment/baseline-area.log 2>&1\n"
    "printf 'AREA_MAPPING_COMPLETE\\n'\n"
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


control = json.loads((OUT / "control.json").read_text())
assert control["source_sha256"] == sha(
    ROOT / "src/machines/synthesizable_red2_machine/machine.py"
)
record = {
    "scope": (
        "Complete experimental top, selected RED2 family shared controller "
        "and serial state bridge"
        if "--integrated" in sys.argv
        else "Standalone family, addressed state and graph/control handshake"
    ),
    "original_source_sha256": control["source_sha256"],
    "candidate_source_sha256": sha(root / "machine.py"),
    "compiler_manifest": json.loads(tc.MANIFEST.read_text()),
    "compiler_manifest_sha256": sha(tc.MANIFEST),
    "hdl_files_sha256": {str(f.relative_to(hdl)): sha(f) for f in files},
    "mapping_scripts_sha256": {
        n: sha(root / n)
        for n in ("frontend.ys", "area.abc", "baseline-area.ys", "run.sh")
    },
    "include_lookup": control["include_lookup"],
    "include_graph": control.get("include_graph", False),
    "entry_opcodes": control.get("entry_opcodes", []),
}
(root / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")
print("PREPARED_FAMILY_MAPPING", root, len(files), "VHDL files")

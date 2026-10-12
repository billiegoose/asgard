"""Elaborate a family experiment with the verified enhanced PipelineC compiler."""

import os
import subprocess
import sys

from paths import OUT, ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import pipelinec_toolchain as tc

compiler = tc.configured_root()
tc.verify_enhanced_compiler(compiler)
root = OUT / "baseline" if "--baseline" in sys.argv else OUT
environment = os.environ.copy()
search_paths = [
    compiler / "src",
    compiler / "include",
    compiler / "include" / "pypeline",
    ROOT / "src" / "lib",
    ROOT / "src" / "machines",
]
environment["PYTHONPATH"] = os.pathsep.join(
    [str(p) for p in search_paths] + [environment.get("PYTHONPATH", "")]
)
with (root / "frontend.log").open("w") as log:
    subprocess.run(
        [
            sys.executable,
            str(compiler / "src" / "pypelinec"),
            str(root / "machine.py"),
            "--comb",
            "--no_synth",
            "--out_dir",
            str(root / "hdl"),
        ],
        env=environment,
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
    )
print("ENHANCED_FRONTEND_COMPLETE", root)

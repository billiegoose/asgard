"""One reproducible enhanced PipelineC selection for simulation and lowering."""

import hashlib
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "tools" / "pipelinec" / "manifest.json"
PIPELINEC_PATCHES = REPO_ROOT / "tools" / "fpgatool" / "toolchain" / "patches"
# Keep each manifest's installation separate so a pin upgrade preserves the
# previous compiler and never mistakes it for the new default.
DEFAULT_PIPELINEC_ROOT = REPO_ROOT / "build" / (
    "pipelinec-enhanced-" + hashlib.sha256(MANIFEST.read_bytes()).hexdigest()[:12]
)


def configured_root() -> Path:
    configured = os.environ.get("PIPELINEC_ROOT")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else DEFAULT_PIPELINEC_ROOT
    )


def verify_enhanced_compiler(root: Path) -> str:
    manifest = json.loads(MANIFEST.read_text())
    for relative, expected in manifest["files"].items():
        path = root / relative
        actual = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        if actual != expected:
            raise RuntimeError(
                f"enhanced PipelineC mismatch: {relative}; "
                "run python scripts/setup_pipelinec.py, or set PIPELINEC_ROOT "
                "to the compiler matching tools/pipelinec/manifest.json"
            )
    return manifest["base_revision"] + "+red2-enhancements"

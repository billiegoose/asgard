"""One reproducible enhanced PipelineC selection for simulation and lowering."""

import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "tools" / "pipelinec" / "manifest.json"
PIPELINEC_PATCHES = REPO_ROOT / "tools" / "fpgatool" / "toolchain" / "patches"
# Keep each manifest's installation separate so a pin upgrade preserves the
# previous compiler and never mistakes it for the new default.
DEFAULT_PIPELINEC_ROOT = REPO_ROOT / "build" / (
    "pipelinec-enhanced-" + hashlib.sha256(MANIFEST.read_bytes()).hexdigest()[:12]
)


def ensure_python_compatibility() -> None:
    """Provide PipelineC's legacy directory utility on Python 3.12 and later."""
    try:
        importlib.import_module("distutils.dir_util")
    except ModuleNotFoundError as error:
        if error.name not in {"distutils", "distutils.dir_util"}:
            raise
        # setuptools installs its maintained distutils implementation. This
        # avoids relying on a temporary, locally recreated stdlib package.
        importlib.import_module("setuptools")
        importlib.import_module("distutils.dir_util")


def compiler_python_command(script: Path, *arguments: str) -> list[str]:
    """Bootstrap legacy imports without modifying the pinned compiler source."""
    bootstrap = (
        "import importlib, runpy, sys\n"
        "try:\n"
        "    importlib.import_module('distutils.dir_util')\n"
        "except ModuleNotFoundError as error:\n"
        "    if error.name not in {'distutils', 'distutils.dir_util'}:\n"
        "        raise\n"
        "    importlib.import_module('setuptools')\n"
        "    importlib.import_module('distutils.dir_util')\n"
        "sys.argv = sys.argv[1:]\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    return [sys.executable, "-c", bootstrap, str(script), *arguments]


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

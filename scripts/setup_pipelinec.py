#!/usr/bin/env python3
"""Build the enhanced compiler from a Git checkout without changing that checkout."""

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from pipelinec_toolchain import (
    DEFAULT_PIPELINEC_ROOT,
    MANIFEST,
    PIPELINEC_PATCHES,
    REPO_ROOT,
    verify_enhanced_compiler,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkout", type=Path, default=REPO_ROOT.parent / "PipelineC"
    )
    args = parser.parse_args()
    root = DEFAULT_PIPELINEC_ROOT
    if root.exists():
        print(f"{verify_enhanced_compiler(root)}: {root}")
        return
    manifest = json.loads(MANIFEST.read_text())
    patches = []
    for entry in manifest["patches"]:
        patch = PIPELINEC_PATCHES / entry["file"]
        if not patch.is_file():
            raise SystemExit(
                f"missing compiler patch: {patch}; "
                "run git submodule update --init tools/fpgatool"
            )
        if hashlib.sha256(patch.read_bytes()).hexdigest() != entry["sha256"]:
            raise SystemExit(f"compiler patch checksum mismatch: {patch}")
        patches.append(patch)
    archive = subprocess.check_output(
        ["git", "-C", str(args.checkout), "archive", manifest["base_revision"]]
    )
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pipelinec-", dir=root.parent) as tmp:
        stage = Path(tmp) / "compiler"
        stage.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
            contents.extractall(stage, filter="data")
        for patch in patches:
            subprocess.run(["git", "apply", str(patch)], cwd=stage, check=True)
        identity = verify_enhanced_compiler(stage)
        shutil.move(stage, root)
    print(f"{identity}: {root}")


if __name__ == "__main__":
    main()

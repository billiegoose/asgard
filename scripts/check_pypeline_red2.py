#!/usr/bin/env python3
"""Explicit real-toolchain gate for the Pypeline RED2 processor.

This command is intentionally stricter than the ordinary Python test suite.  It
must never turn an absent frontend, an absent processor hardware top, or a
PipelineC "skipping synthesis" warning into a successful hardware verdict.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


PIPELINEC_TESTED_REVISION = "171c52b3f1411f632a07ccfc3dbfb177efa901cd"
PROCESSOR_SOURCE = Path("models/python/pypeline_red2/red2_pypeline.py")
MISSING_FRONTEND_DIAGNOSTIC = (
    "pypeline-red2-check: missing PipelineC/Pypeline frontend; "
    f"set PIPELINEC_ROOT to a checkout at {PIPELINEC_TESTED_REVISION} "
    "or put pypelinec/pipelinec on PATH"
)
MISSING_TOP_DIAGNOSTIC = (
    "pypeline-red2-check: RED2 hardware top missing: persistent reducer source "
    "has no Pypeline @MAIN; refusing to validate legacy red2_step_word"
)
SYNTHESIS_SKIPPED_DIAGNOSTIC = (
    "pypeline-red2-check: PipelineC skipped synthesis because no configured "
    "synthesis target/tool was available"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _frontend_from_root(root: Path) -> Path | None:
    for relative in ("src/pypelinec", "src/pipelinec"):
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return None


def discover_frontend() -> tuple[Path, Path | None] | None:
    """Return (frontend executable/script, checkout root when known)."""
    configured = os.environ.get("PIPELINEC_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
        frontend = _frontend_from_root(root)
        if frontend is not None:
            return frontend, root
        return None

    for name in ("pypelinec", "pipelinec"):
        found = shutil.which(name)
        if found:
            return Path(found).resolve(), None
    return None


def _checkout_revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "pypeline-red2-check: cannot determine configured PipelineC checkout revision"
        )
    return result.stdout.strip()


def _pipelinec_environment(root: Path | None, repo: Path) -> dict[str, str]:
    env = os.environ.copy()
    pieces: list[str] = []
    if root is not None:
        pieces.extend(
            (str(root / "src"), str(root / "include"), str(root / "include" / "pypeline"))
        )
    pieces.append(str(repo / "models" / "python"))
    inherited = env.get("PYTHONPATH")
    if inherited:
        pieces.append(inherited)
    env["PYTHONPATH"] = os.pathsep.join(pieces)
    return env


def _frontend_command(frontend: Path, checkout_root: Path | None) -> list[str]:
    # A checkout script is deliberately run with this gate's interpreter so the
    # explicit mise task can provision Python-side PipelineC dependencies without
    # installing PipelineC into the Asgard environment.  An installed executable
    # keeps its own launcher/shebang environment.
    if checkout_root is not None:
        return [sys.executable, str(frontend)]
    return [str(frontend)]


def _run_pipelinec(
    frontend: Path,
    checkout_root: Path | None,
    source: Path,
    out_dir: Path,
    *,
    frontend_only: bool,
) -> subprocess.CompletedProcess[str]:
    command = _frontend_command(frontend, checkout_root)
    command.extend((str(source), "--out_dir", str(out_dir)))
    if frontend_only:
        command.append("--no_synth")
    else:
        command.append("--comb")
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=_pipelinec_environment(checkout_root, _repo_root()),
    )


def _run_frontend_elaboration(
    frontend: Path,
    checkout_root: Path | None,
    source: Path,
    out_dir: Path,
) -> subprocess.CompletedProcess[str]:
    """Run PipelineC's supported frontend + HDL emission path without synthesis."""
    return _run_pipelinec(
        frontend,
        checkout_root,
        source,
        out_dir,
        frontend_only=True,
    )


def _find_emitted_top(out_dir: Path) -> Path | None:
    top_dir = out_dir / "red2_processor_top"
    if not top_dir.is_dir():
        return None
    candidates = sorted(top_dir.glob("red2_processor_top_*.vhd"))
    return candidates[0] if candidates else None


def _run_native_sim(checkout_root: Path | None, repo: Path) -> subprocess.CompletedProcess[str]:
    script = repo / "scripts" / "check_pypeline_red2_sim.py"
    return subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=_pipelinec_environment(checkout_root, repo),
    )


def _print_failure_output(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, file=sys.stderr, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="" if result.stderr.endswith("\n") else "\n")


def _summarize_synthesis(output: str) -> list[str]:
    interesting = (
        "part",
        "target",
        "lut",
        "ff",
        "register",
        "resource",
        "timing",
        "mhz",
        "slack",
        "utilization",
    )
    summary: list[str] = []
    for raw in output.splitlines():
        line = raw.strip()
        lower = line.lower()
        if line and any(token in lower for token in interesting):
            summary.append(line)
    return summary[-30:]


def check(frontend_only: bool = False) -> int:
    repo = _repo_root()
    discovered = discover_frontend()
    if discovered is None:
        print(MISSING_FRONTEND_DIAGNOSTIC, file=sys.stderr)
        return 2

    frontend, checkout_root = discovered
    if checkout_root is not None:
        try:
            revision = _checkout_revision(checkout_root)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if revision != PIPELINEC_TESTED_REVISION:
            print(
                "pypeline-red2-check: PipelineC revision mismatch: "
                f"expected {PIPELINEC_TESTED_REVISION}, got {revision}",
                file=sys.stderr,
            )
            return 2
        print(f"PipelineC revision: {revision}")
    else:
        print(f"PipelineC frontend: {frontend} (revision not inspectable from PATH)")

    source = repo / PROCESSOR_SOURCE
    if not source.is_file():
        print(f"pypeline-red2-check: processor source missing: {source}", file=sys.stderr)
        return 2
    source_text = source.read_text()
    semantics_complete = "RED2_PYPELINE_SEMANTICS_COMPLETE = 1" in source_text

    with tempfile.TemporaryDirectory(prefix="asgard-pypeline-red2-") as tmp:
        frontend_out = Path(tmp) / "frontend"
        result = _run_frontend_elaboration(
            frontend,
            checkout_root,
            source,
            frontend_out,
        )
        combined = result.stdout + "\n" + result.stderr
        if result.returncode != 0:
            if "No functions were decorated as @MAIN?" in combined:
                print(MISSING_TOP_DIAGNOSTIC, file=sys.stderr)
                return 3
            _print_failure_output(result)
            print(
                f"pypeline-red2-check: PipelineC frontend failed with exit {result.returncode}",
                file=sys.stderr,
            )
            return 4

        emitted_top = _find_emitted_top(frontend_out)
        if emitted_top is None:
            print(
                "pypeline-red2-check: PipelineC frontend exited successfully but did not "
                "emit red2_processor_top VHDL",
                file=sys.stderr,
            )
            return 4
        print(
            "PipelineC frontend+HDL: PASS "
            f"({emitted_top.name}, {emitted_top.stat().st_size} bytes)"
        )
        native_sim = _run_native_sim(checkout_root, repo)
        if native_sim.returncode != 0:
            _print_failure_output(native_sim)
            print(
                f"pypeline-red2-check: native Pypeline RED2 parity failed with exit {native_sim.returncode}",
                file=sys.stderr,
            )
            return 9
        if native_sim.stdout:
            print(native_sim.stdout, end="" if native_sim.stdout.endswith("\n") else "\n")
        if frontend_only:
            return 0
        if not semantics_complete:
            print(
                "pypeline-red2-check: frontend accepted the hardware top, but persistent "
                "RED2 execution semantics are not yet complete; RED2_SYNTH_V1 withheld",
                file=sys.stderr,
            )
            return 8

        synth_out = Path(tmp) / "synth"
        synth = _run_pipelinec(
            frontend,
            checkout_root,
            source,
            synth_out,
            frontend_only=False,
        )
        synth_combined = synth.stdout + "\n" + synth.stderr
        if "Skipping synthesis" in synth_combined or "No synthesis tool install detected" in synth_combined:
            print(SYNTHESIS_SKIPPED_DIAGNOSTIC, file=sys.stderr)
            return 5
        if synth.returncode != 0:
            _print_failure_output(synth)
            print(
                f"pypeline-red2-check: synthesis failed with exit {synth.returncode}",
                file=sys.stderr,
            )
            return 6

        summary = _summarize_synthesis(synth_combined)
        if not summary:
            print(
                "pypeline-red2-check: synthesis exited successfully but emitted no "
                "target/resource/timing summary",
                file=sys.stderr,
            )
            return 7
        print("PipelineC synthesis: PASS")
        print("Synthesis summary:")
        for line in summary:
            print(f"  {line}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frontend-only",
        action="store_true",
        help="run supported PipelineC frontend + VHDL emission plus native parity, not synthesis",
    )
    args = parser.parse_args()
    return check(frontend_only=args.frontend_only)


if __name__ == "__main__":
    raise SystemExit(main())

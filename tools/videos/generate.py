from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "examples" / "README.md"
MEDIA_DIR = ROOT / "examples" / "media"
BREAKOUT_CAST = MEDIA_DIR / "breakout.cast"
BREAKOUT_TITLE = "Asgard Breakout deterministic playthrough"

BREAKOUT_STEPS: tuple[tuple[int, str, float], ...] = (
    (1_700_000_000_200, "\x1b[C", 0.35),
    (1_700_000_000_300, "\x1b[D", 0.35),
    (1_700_000_000_400, " ", 0.35),
    (1_700_000_000_500, "\x1b[C", 0.35),
    (1_700_000_000_600, " ", 0.35),
    (1_700_000_000_700, "\x1b[D", 0.35),
    (1_700_000_000_800, "q", 0.1),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and upload example videos.")
    parser.add_argument("video", choices=("breakout",))
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="regenerate the local cast without uploading or updating the URL",
    )
    args = parser.parse_args(argv)

    if args.video == "breakout":
        url = generate_breakout(upload=not args.no_upload)
        if url:
            print(url)
        return 0
    return 2


def generate_breakout(*, upload: bool) -> str | None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="asgard-breakout-video-") as tmp:
        tmp_path = Path(tmp)
        clock = tmp_path / "clock.txt"
        driver = tmp_path / "drive_breakout.py"
        clock.write_text("1700000000000\n")
        driver.write_text(_driver_source(clock))
        command = (
            f"{sys.executable} {driver} | "
            "mise run thor examples/breakout.thor "
            f"--clock {clock} --quantum 12000"
        )
        env = os.environ | {
            "TERM": "xterm-256color",
            "COLUMNS": "80",
            "LINES": "24",
        }
        subprocess.run(
            [
                "asciinema",
                "rec",
                "--overwrite",
                "-q",
                "-t",
                BREAKOUT_TITLE,
                "-c",
                command,
                str(BREAKOUT_CAST),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
    if not upload:
        return None
    upload_result = subprocess.run(
        ["asciinema", "upload", str(BREAKOUT_CAST)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    url = _extract_asciinema_url(upload_result.stdout + upload_result.stderr)
    _write_examples_readme(url)
    return url


def _driver_source(clock: Path) -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "import sys",
            "import time",
            "from pathlib import Path",
            f"clock = Path({str(clock)!r})",
            f"steps = {BREAKOUT_STEPS!r}",
            "for timestamp, keys, delay in steps:",
            "    clock.write_text(f'{timestamp}\\n')",
            "    sys.stdout.write(keys)",
            "    sys.stdout.flush()",
            "    time.sleep(delay)",
            "",
        ]
    )


def _extract_asciinema_url(output: str) -> str:
    match = re.search(r"https://asciinema\.org/a/[A-Za-z0-9]+", output)
    if match is None:
        msg = f"could not find asciinema URL in upload output: {output!r}"
        raise RuntimeError(msg)
    return match.group(0)


def _write_examples_readme(url: str) -> None:
    svg_url = f"{url}.svg"
    README.write_text(
        "# Examples\n\n"
        "## Recordings\n\n"
        "### Breakout\n\n"
        f"[![Asgard Breakout asciicast]({svg_url})]({url})\n\n"
        "Replay the committed local cast:\n\n"
        "```sh\n"
        "asciinema play examples/media/breakout.cast\n"
        "```\n\n"
        "Regenerate and upload this recording:\n\n"
        "```sh\n"
        "mise run generate-video breakout\n"
        "```\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())

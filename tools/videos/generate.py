import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "examples" / "README.md"
MEDIA_DIR = ROOT / "examples" / "media"
BREAKOUT_CAST = MEDIA_DIR / "breakout.cast"
BREAKOUT_WASM_CAST = MEDIA_DIR / "breakout-wasm.cast"
BREAKOUT_TITLE = "Asgard Breakout deterministic playthrough"
BREAKOUT_WASM_TITLE = "Asgard Breakout WASM"


def _breakout_steps() -> tuple[tuple[int, str, float], ...]:
    keys_by_tick = {
        10: "\x1b[C",
        11: "\x1b[C",
        12: "\x1b[C",
        23: "\x1b[D",
        24: "\x1b[D",
        25: "\x1b[D",
        26: "\x1b[D",
        38: "\x1b[C",
        39: "\x1b[C",
        51: "\x1b[D",
        52: "\x1b[D",
        53: "\x1b[D",
        66: "\x1b[C",
        67: "\x1b[C",
        68: "\x1b[C",
    }
    steps: list[tuple[int, str, float]] = []
    for tick in range(1, 71):
        keys = keys_by_tick.get(tick, " ")
        steps.append((1_700_000_000_000 + (tick * TICK_MS), keys, 0.1))
    steps.append((1_700_000_007_200, "q", 0.1))
    return tuple(steps)


def _breakout_wasm_steps() -> tuple[tuple[int, str, float], ...]:
    return BREAKOUT_STEPS


TICK_MS = 100
BREAKOUT_STEPS = _breakout_steps()
BREAKOUT_WASM_STEPS = _breakout_wasm_steps()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and upload example videos.")
    parser.add_argument("video", choices=("breakout", "breakout-wasm"))
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
    if args.video == "breakout-wasm":
        url = generate_breakout_wasm(upload=not args.no_upload)
        if url:
            print(url)
        return 0
    return 2


def generate_breakout(*, upload: bool) -> str | None:
    return _generate_breakout_video(
        upload=upload,
        cast=BREAKOUT_CAST,
        title=BREAKOUT_TITLE,
        command_model="red2",
        steps=BREAKOUT_STEPS,
        readme_writer=_write_examples_readme,
    )


def generate_breakout_wasm(*, upload: bool) -> str | None:
    return _generate_breakout_video(
        upload=upload,
        cast=BREAKOUT_WASM_CAST,
        title=BREAKOUT_WASM_TITLE,
        command_model="wasm",
        steps=BREAKOUT_WASM_STEPS,
        readme_writer=_write_examples_readme_wasm,
    )


def _generate_breakout_video(
    *,
    upload: bool,
    cast: Path,
    title: str,
    command_model: str,
    steps: tuple[tuple[int, str, float], ...],
    readme_writer: Callable[[str], None],
) -> str | None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"asgard-{command_model}-breakout-video-"
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        tmp_path = Path(tmp)
        clock = tmp_path / "clock.txt"
        driver = tmp_path / "drive_breakout.py"
        clock.write_text("1700000000000\n")
        driver.write_text(_driver_source(clock, steps))
        command = (
            f"{sys.executable} {driver} | "
            f"mise run {command_model} examples/breakout.thor "
            f"--clock {clock} --quantum 50000"
        )
        env = os.environ | {
            "TERM": "xterm-256color",
            "COLUMNS": "20",
            "LINES": "16",
        }
        subprocess.run(
            [
                "asciinema",
                "rec",
                "--overwrite",
                "-q",
                "-t",
                title,
                "-c",
                command,
                str(cast),
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )
        _normalize_cast_duration(cast, duration=5.2, title=title)
    if not upload:
        return None
    upload_result = subprocess.run(
        ["asciinema", "upload", str(cast)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    url = _extract_asciinema_url(upload_result.stdout + upload_result.stderr)
    readme_writer(url)
    return url


def _driver_source(clock: Path, steps: tuple[tuple[int, str, float], ...]) -> str:
    return "\n".join(
        [
            "from __future__ import annotations",
            "import sys",
            "import time",
            "from pathlib import Path",
            f"clock = Path({str(clock)!r})",
            f"steps = {steps!r}",
            "for timestamp, keys, delay in steps:",
            "    clock.write_text(f'{timestamp}\\n')",
            "    sys.stdout.write(keys)",
            "    sys.stdout.flush()",
            "    time.sleep(delay)",
            "",
        ]
    )


def _normalize_cast_duration(
    cast: Path,
    *,
    duration: float,
    title: str | None = None,
) -> None:
    lines = cast.read_text().splitlines()
    if len(lines) <= 1:
        return
    header = lines[0]
    if title is not None:
        header_data = json.loads(header)
        header_data["timestamp"] = 1_700_000_000
        header_data["title"] = title
        header = json.dumps(header_data, separators=(",", ":"))
    events = [json.loads(line) for line in lines[1:]]
    last_time = events[-1][0]
    if last_time <= 0:
        return
    normalized = [header]
    for event in events:
        event[0] = round((event[0] / last_time) * duration, 6)
        normalized.append(json.dumps(event, separators=(",", ":")))
    cast.write_text("\n".join(normalized) + "\n")


def _extract_asciinema_url(output: str) -> str:
    match = re.search(r"https://asciinema\.org/a/[A-Za-z0-9]+", output)
    if match is None:
        msg = f"could not find asciinema URL in upload output: {output!r}"
        raise RuntimeError(msg)
    return match.group(0)


def _write_examples_readme(url: str) -> None:
    svg_url = f"{url}.svg"
    text = README.read_text()
    text = re.sub(
        r"\[!\[Asgard Breakout asciicast\]\([^)]*\)\]\([^)]+\)",
        f"[![Asgard Breakout asciicast]({svg_url})]({url})",
        text,
    )
    README.write_text(text)


def _write_examples_readme_wasm(url: str) -> None:
    svg_url = f"{url}.svg"
    text = README.read_text()
    text = re.sub(
        r"\[!\[Asgard Breakout WASM asciicast\]\([^)]*\)\]\([^)]+\)",
        f"[![Asgard Breakout WASM asciicast]({svg_url})]({url})",
        text,
    )
    README.write_text(text)


if __name__ == "__main__":
    raise SystemExit(main())

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
ROOT_README = ROOT / "README.md"
EXAMPLES_README = ROOT / "examples" / "README.md"
MEDIA_DIR = ROOT / "examples" / "media"
BREAKOUT_CAST = MEDIA_DIR / "breakout.cast"
BREAKOUT_WASM_CAST = MEDIA_DIR / "breakout-wasm.cast"
PONG_CAST = MEDIA_DIR / "pong.cast"
BREAKOUT_TITLE = "Asgard Breakout Python RED2"
BREAKOUT_WASM_TITLE = "Asgard Breakout WASM"
PONG_TITLE = "Asgard Pong Python RED2"


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
    scaled_keys_by_tick = {tick * 6: keys for tick, keys in keys_by_tick.items()}
    steps: list[tuple[int, str, float]] = []
    for tick in range(1, 421):
        keys = scaled_keys_by_tick.get(tick, " ")
        steps.append((1_700_000_000_000 + (tick * TICK_MS), keys, 0.1))
    steps.append((1_700_000_042_200, "q", 0.1))
    return tuple(steps)


def _breakout_wasm_steps() -> tuple[tuple[int, str, float], ...]:
    return BREAKOUT_STEPS


def _pong_steps() -> tuple[tuple[int, str, float], ...]:
    keys_by_tick = {
        3: "\x1b[A",
        4: "\x1b[A",
        8: "\x1b[B",
        9: "\x1b[B",
    }
    steps: list[tuple[int, str, float]] = [
        (1_700_000_000_000, " ", 3.0),
    ]
    for tick in range(1, 19):
        keys = keys_by_tick.get(tick, " ")
        steps.append((1_700_000_000_000 + (tick * 200), keys, 0.05))
    steps.append((1_700_000_003_800, "q", 0.05))
    return tuple(steps)


TICK_MS = 100
BREAKOUT_STEPS = _breakout_steps()
BREAKOUT_WASM_STEPS = _breakout_wasm_steps()
PONG_STEPS = _pong_steps()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and upload example videos.")
    parser.add_argument("video", choices=("breakout", "breakout-wasm", "pong"))
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
    if args.video == "pong":
        url = generate_pong(upload=not args.no_upload)
        if url:
            print(url)
        return 0
    return 2


def generate_breakout(*, upload: bool) -> str | None:
    return _generate_terminal_video(
        upload=upload,
        cast=BREAKOUT_CAST,
        title=BREAKOUT_TITLE,
        command_model="red2",
        source="examples/breakout.thor",
        steps=BREAKOUT_STEPS,
        height=16,
        readme_writer=_write_examples_readme,
        memory_words=4_194_304,
    )


def generate_breakout_wasm(*, upload: bool) -> str | None:
    return _generate_terminal_video(
        upload=upload,
        cast=BREAKOUT_WASM_CAST,
        title=BREAKOUT_WASM_TITLE,
        command_model="wasm",
        source="examples/breakout.thor",
        steps=BREAKOUT_WASM_STEPS,
        height=16,
        readme_writer=_write_examples_readme_wasm,
    )


def generate_pong(*, upload: bool) -> str | None:
    return _generate_terminal_video(
        upload=upload,
        cast=PONG_CAST,
        title=PONG_TITLE,
        command_model="red2",
        source="examples/pong.thor",
        steps=PONG_STEPS,
        height=17,
        readme_writer=_write_examples_readme_pong,
    )


def _generate_terminal_video(
    *,
    upload: bool,
    cast: Path,
    title: str,
    command_model: str,
    source: str,
    steps: tuple[tuple[int, str, float], ...],
    height: int,
    readme_writer: Callable[[str], None],
    memory_words: int | None = None,
) -> str | None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"asgard-{command_model}-{Path(source).stem}-video-"
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        tmp_path = Path(tmp)
        clock = tmp_path / "clock.txt"
        driver = tmp_path / "drive_terminal_game.py"
        clock.write_text("1700000000000\n")
        driver.write_text(_driver_source(clock, steps))
        memory_arg = (
            f" --memory-words {memory_words}"
            if command_model == "red2" and memory_words is not None
            else ""
        )
        command = (
            f"{sys.executable} {driver} | "
            f"mise run {command_model} {source} "
            f"--clock {clock} --quantum 50000{memory_arg}"
        )
        env = os.environ | {
            "TERM": "xterm-256color",
            "COLUMNS": "20",
            "LINES": str(height),
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
        output = "".join(
            json.loads(line)[2] for line in cast.read_text().splitlines()[1:]
        )
        failure_markers = (
            "ERROR task failed",
            "Traceback (most recent call last)",
            "BrokenPipeError:",
            "graph and environment collide",
        )
        for marker in failure_markers:
            if marker in output:
                raise RuntimeError(f"recorded command failed: found {marker!r} in cast")
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


def _replace_asciinema_embed(path: Path, alt_text: str, url: str) -> None:
    lines = path.read_text().splitlines()
    prefix = f"[![{alt_text}]"
    open_paren = chr(40)
    close_paren = chr(41)
    replacement = (
        f"[![{alt_text}]"
        f"{open_paren}{url}.svg{close_paren}]"
        f"{open_paren}{url}{close_paren}"
    )
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            path.write_text(chr(10).join(lines) + chr(10))
            return
    msg = f"could not find {alt_text!r} embed in {path}"
    raise RuntimeError(msg)


def _write_examples_readme(url: str) -> None:
    alt_text = "Asgard Breakout asciicast"
    _replace_asciinema_embed(EXAMPLES_README, alt_text, url)
    _replace_asciinema_embed(ROOT_README, alt_text, url)


def _write_examples_readme_wasm(url: str) -> None:
    _replace_asciinema_embed(
        EXAMPLES_README,
        "Asgard Breakout WASM asciicast",
        url,
    )


def _write_examples_readme_pong(url: str) -> None:
    _replace_asciinema_embed(EXAMPLES_README, "Asgard Pong asciicast", url)


if __name__ == "__main__":
    raise SystemExit(main())

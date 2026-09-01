import json
import re
from itertools import pairwise
from pathlib import Path


def test_breakout_cast_is_committed_asciicast_v2() -> None:
    cast = Path("examples/media/breakout.cast")

    assert cast.is_file()
    header = json.loads(cast.read_text().splitlines()[0])
    assert header["version"] == 2
    assert header["width"] == 20
    assert header["height"] == 16


def test_breakout_cast_hides_cursor_during_play_and_restores_it_on_exit() -> None:
    cast = Path("examples/media/breakout.cast")
    output = "".join(json.loads(line)[2] for line in cast.read_text().splitlines()[1:])

    assert output.startswith("\x1b[?25l")
    assert "\x1b[?25hQUIT" in output


def test_breakout_cast_shows_five_seconds_of_play() -> None:
    cast = Path("examples/media/breakout.cast")
    events = [json.loads(line) for line in cast.read_text().splitlines()[1:]]

    assert events[-1][0] >= 5.0
    assert events[-1][0] <= 6.0


def test_breakout_cast_uses_compact_hud() -> None:
    cast = Path("examples/media/breakout.cast")
    output = "".join(json.loads(line)[2] for line in cast.read_text().splitlines()[1:])

    assert "PADDLE:" not in output
    assert "ARROWS MOVE; Q QUITS\r\nSCORE: 0  LIVES: 3\r\n" in output


def test_breakout_cast_contains_real_playthrough_updates() -> None:
    cast = Path("examples/media/breakout.cast")
    output = "".join(json.loads(line)[2] for line in cast.read_text().splitlines()[1:])

    assert "===============" in output
    assert output.count("o") >= 10
    assert "\x1b[3;8H4 " in output


def test_breakout_cast_runs_at_playable_frame_rate() -> None:
    cast = Path("examples/media/breakout.cast")
    events = [json.loads(line) for line in cast.read_text().splitlines()[1:]]
    output = "".join(event[2] for event in events)
    duration = events[-1][0]
    ball_draws = len(re.findall(r"\x1b\[(\d+);(\d+)Ho", output))

    assert ball_draws / duration >= 1.0


def test_breakout_cast_shows_at_least_six_horizontal_bounces() -> None:
    cast = Path("examples/media/breakout.cast")
    output = "".join(json.loads(line)[2] for line in cast.read_text().splitlines()[1:])
    ball_points = [
        (int(row), int(col))
        for row, col in re.findall(r"\x1b\[(\d+);(\d+)Ho", output)
    ]
    previous_direction = 0
    reversals = 0
    for (_, previous_col), (_, col) in pairwise(ball_points):
        direction = (col > previous_col) - (col < previous_col)
        if direction and previous_direction and direction != previous_direction:
            reversals += 1
        if direction:
            previous_direction = direction

    assert reversals >= 6


def test_wasm_breakout_cast_is_real_long_timed_recording_without_trap_output() -> None:
    cast = Path("examples/media/breakout-wasm.cast")
    lines = cast.read_text().splitlines()
    header = json.loads(lines[0])
    events = [json.loads(line) for line in lines[1:]]
    output = "".join(event[2] for event in events)
    ball_draws = len(re.findall(r"\x1b\[(\d+);(\d+)Ho", output))

    assert header["version"] == 2
    assert header["title"] == "Asgard Breakout WASM"
    assert len(events) >= 1000
    assert events[-1][0] >= 5.0
    assert events[-1][0] <= 6.0
    assert ball_draws >= 10
    assert "BREAKOUT 20x12" in output
    assert "\x1b[?25hQUIT" in output
    assert "wasm trap" not in output.lower()
    assert "stack" not in output.lower()


def test_generate_video_task_supports_breakout_and_breakout_wasm() -> None:
    mise = Path(".mise.toml").read_text()
    generator = Path("tools/videos/generate.py").read_text()

    assert "[tasks.generate-video]" in mise
    assert 'arg "<video>"' in mise
    assert 'choices "breakout" "breakout-wasm"' in mise
    assert 'choices=("breakout", "breakout-wasm")' in generator
    assert "generate_breakout_wasm" in generator
    assert "generate-videos" not in mise

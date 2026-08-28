from __future__ import annotations

import json
from pathlib import Path


def test_breakout_cast_is_committed_asciicast_v2() -> None:
    cast = Path("examples/media/breakout.cast")

    assert cast.is_file()
    header = json.loads(cast.read_text().splitlines()[0])
    assert header["version"] == 2
    assert header["width"] == 80
    assert header["height"] == 24


def test_generate_video_task_is_named_and_single_video() -> None:
    mise = Path(".mise.toml").read_text()

    assert "[tasks.generate-video]" in mise
    assert 'arg "<video>"' in mise
    assert 'choices "breakout"' in mise
    assert "generate-videos" not in mise

from __future__ import annotations

from pathlib import Path


def test_vscode_extension_lives_under_tools() -> None:
    assert Path("tools/vscode-thor/package.json").is_file()
    assert Path("tools/vscode-thor/syntaxes/thor.tmLanguage.json").is_file()
    assert not Path("vscode-thor/package.json").exists()


def test_thesis_transcription_lives_under_thesis() -> None:
    assert Path("thesis/transcription/scripts/compile.sh").is_file()
    assert Path("thesis/transcription/src/main.tex").is_file()
    assert not Path("thesis-transcription/scripts/compile.sh").exists()

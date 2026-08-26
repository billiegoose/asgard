from pathlib import Path


def test_pypeline_stepper_artifact_has_expected_entry_points() -> None:
    source = Path("pypeline_red2/red2_stepper.py").read_text()
    assert "def decode_opcode" in source
    assert "def encode_word" in source
    assert "def red2_step_word" in source
    assert "@MAIN" in source or "# PypelineC entry" in source


def test_pypeline_readme_names_validation_path() -> None:
    text = Path("pypeline_red2/README.md").read_text()
    assert "PipelineC" in text
    assert "golden vectors" in text
    assert "uv run pytest tests/test_pipelinec_vectors.py" in text

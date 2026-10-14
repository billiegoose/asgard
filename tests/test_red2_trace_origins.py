"""Physical replay must retain the expected-output model and validation scope."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "red2_trace_origin_host", ROOT / "scripts/boards/red2_basys3/host.py"
)
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
SOURCE = "a" * 64


def vectors(tmp_path, **extra):
    path = tmp_path / "vectors.txt"
    path.write_text("0 0\n")
    metadata = {
        "input_width": 722,
        "output_width": 626,
        "cycles": 1,
        "candidate_sha256": SOURCE,
        "vectors_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        **extra,
    }
    path.with_suffix(".json").write_text(json.dumps(metadata))
    return path


def rtl_metadata():
    return {
        "expected_output_origin": "Verilator RTL simulation",
        "rtl_model": {
            "candidate_source_sha256": SOURCE,
            "binary_sha256": "b" * 64,
            "manifest_sha256": "c" * 64,
        },
        "semantic_validation": {
            "passed": True,
            "program": "(+ 7 8)",
            "termination": "HALTED",
        },
    }


def test_legacy_native_vectors_still_validate(tmp_path):
    assert host.verify_vectors(vectors(tmp_path), SOURCE)["cycles"] == 1


def test_validated_rtl_origin_is_retained(tmp_path):
    result = host.verify_vectors(vectors(tmp_path, **rtl_metadata()), SOURCE)
    assert result["expected_output_origin"] == "Verilator RTL simulation"
    assert result["semantic_validation"]["program"] == "(+ 7 8)"


@pytest.mark.parametrize(
    "fault",
    ["missing_gate", "wrong_model", "not_passed", "not_halted", "wrong_boolean"],
)
def test_rtl_observations_require_completed_same_source_semantics(tmp_path, fault):
    metadata = rtl_metadata()
    if fault == "missing_gate":
        del metadata["semantic_validation"]
    elif fault == "wrong_model":
        metadata["rtl_model"]["candidate_source_sha256"] = "d" * 64
    elif fault == "not_passed":
        metadata["semantic_validation"]["passed"] = False
    elif fault == "wrong_boolean":
        metadata["semantic_validation"]["passed"] = "true"
    else:
        metadata["semantic_validation"]["termination"] = "QUANTUM_EXHAUSTED"
    with pytest.raises(ValueError, match="same-source semantic gate"):
        host.verify_vectors(vectors(tmp_path, **metadata), SOURCE)


def test_unknown_trace_origin_is_not_treated_as_native(tmp_path):
    with pytest.raises(ValueError, match="unrecognized"):
        host.verify_vectors(vectors(tmp_path, expected_output_origin="unknown"), SOURCE)

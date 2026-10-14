"""Check packed port boundaries independently of a generated replay model."""

import hashlib
import importlib.util
import json
from collections import namedtuple
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "red2_rtl_trace", ROOT / "scripts/experiments/red2_cfg_pilot/rtl_trace.py"
)
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


@pytest.fixture
def layout(tmp_path):
    hdl = tmp_path / "hdl"
    (hdl / "top").mkdir(parents=True)
    (hdl / "c_structs_pkg.pkg.vhd").write_text(
        "type payload_t is record\n"
        "lo : unsigned(63 downto 0); hi : unsigned(63 downto 0); end record;\n"
        "type command_t is record\n"
        "op : unsigned(3 downto 0); word : payload_t; end record;\n"
        "type result_t is record\n"
        "status : unsigned(2 downto 0); word : payload_t; end record;\n"
    )
    (hdl / "top/top.vhd").write_text(
        "incoming_command : in command_t; return_output : out result_t;"
    )
    return trace.PortLayout(tmp_path)


def test_pack_crosses_word_boundaries_and_truncates_scalars(layout):
    payload = namedtuple("Payload", "lo hi")
    command = namedtuple("Command", "op word")
    bits, width = layout.pack(
        layout.input_type, command(19, payload((1 << 64) + 7, 1 << 63))
    )
    # VHDL order places op at bit 0, lo at bit 4, and hi at bit 68.
    assert width == 132
    assert bits == 3 + (7 << 4) + (1 << 131)


def test_unpack_respects_nested_record_offsets(layout):
    bits = 5 + (0xFEDCBA9876543210 << 3) + (0x8000000000000001 << 67)
    result = layout.unpack(layout.output_type, bits)
    assert result.status == 5
    assert result.word.lo == 0xFEDCBA9876543210
    assert result.word.hi == 0x8000000000000001
    assert layout.schema(layout.output_type)[0] == 131


def test_port_field_mismatch_cannot_silently_reorder_values(layout):
    wrong_command = namedtuple("WrongCommand", "op payload")
    with pytest.raises(AssertionError):
        layout.pack(layout.input_type, wrong_command(0, 0))


def test_native_trace_keeps_existing_hex_and_metadata_format(layout, tmp_path):
    (layout.top / "machine.py").write_text("# fixture hardware\n")
    payload = namedtuple("Payload", "lo hi")
    command = namedtuple("Command", "op word")
    result = namedtuple("Result", "status word")
    destination = tmp_path / "vectors.txt"
    recorder = trace.Trace(layout.top, destination)
    recorder.append(command(3, payload(7, 0)), result(5, payload(9, 0)))
    recorder.close()
    assert [int(value, 16) for value in destination.read_text().split()] == [0x73, 0x4D]
    metadata = json.loads(destination.with_suffix(".json").read_text())
    assert metadata["cycles"] == 1
    assert metadata["input_width"] == 132
    assert metadata["output_width"] == 131
    assert metadata["expected_output_origin"] == "native hardware-source simulation"


def test_rtl_observations_keep_model_and_completed_program_provenance(layout, tmp_path):
    (layout.top / "machine.py").write_text("# fixture hardware\n")
    source_hash = hashlib.sha256((layout.top / "machine.py").read_bytes()).hexdigest()
    path = tmp_path / "rtl-observations.txt"
    recorder = trace.Trace(layout.top, path)
    command = layout.unpack(layout.input_type, 0x73)
    result = layout.unpack(layout.output_type, 0x4D)
    recorder.append(command, result)
    model = {
        "candidate_source_sha256": source_hash,
        "binary_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
    }
    recorder.close(rtl_model=model, checked_program="(+ 7 8)")
    metadata = json.loads(path.with_suffix(".json").read_text())
    assert metadata["expected_output_origin"] == "Verilator RTL simulation"
    assert metadata["rtl_model"] == model
    assert metadata["semantic_validation"]["program"] == "(+ 7 8)"
    assert metadata["semantic_validation"]["termination"] == "HALTED"


def test_mismatched_rtl_model_cannot_publish_completed_trace_metadata(layout, tmp_path):
    (layout.top / "machine.py").write_text("# fixture hardware\n")
    path = tmp_path / "wrong-source.txt"
    recorder = trace.Trace(layout.top, path)
    recorder.append(
        layout.unpack(layout.input_type, 0), layout.unpack(layout.output_type, 0)
    )
    with pytest.raises(AssertionError):
        recorder.close(
            rtl_model={"candidate_source_sha256": "f" * 64},
            checked_program="(+ 7 8)",
        )
    assert not path.with_suffix(".json").exists()

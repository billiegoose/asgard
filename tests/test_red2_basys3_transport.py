import binascii
import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/boards/red2_basys3/host.py"
SPEC = importlib.util.spec_from_file_location("red2_board_host", SOURCE)
host = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(host)


def response(value, sequence=255):
    body = bytes([sequence]) + value.to_bytes(host.OUTPUT_BYTES, "little")
    return b"\x5a\xa5" + body + binascii.crc_hqx(body, 0xFFFF).to_bytes(2, "little")


def test_request_carries_low_and_high_command_bits_and_sequence_wrap():
    command = (1 << 721) | 7
    frame = host.request_frame(command, 0)
    assert len(frame) == 96
    assert frame[:4] == b"\xa5\x5a\x00\x07"
    assert frame[-3] == 2
    assert int.from_bytes(frame[3:-2], "little") == command
    assert int.from_bytes(frame[-2:], "little") == binascii.crc_hqx(frame[2:-2], 0xFFFF)
    with pytest.raises(ValueError):
        host.request_frame(1 << 722, 0)


def test_response_checks_all_output_bits_and_padding():
    value = (1 << 625) | (1 << 491) | 0x123456789
    assert host.response_value(response(value), 255) == value
    with pytest.raises(ValueError, match="padding"):
        host.response_value(response(1 << 626), 255)


def test_response_rejects_corruption_stale_sequence_and_truncation():
    packet = response(42)
    broken = bytearray(packet)
    broken[23] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        host.response_value(bytes(broken), 255)
    with pytest.raises(ValueError, match="sequence"):
        host.response_value(packet, 0)
    with pytest.raises(ValueError, match="framing"):
        host.response_value(packet[:-1], 255)


def test_replay_checks_identity_count_and_all_rows_before_hardware(tmp_path):
    import hashlib

    vectors = tmp_path / "vectors.txt"
    vectors.write_text("1 2\n")
    metadata = {
        "input_width": 722,
        "output_width": 626,
        "candidate_sha256": "candidate",
        "vectors_sha256": hashlib.sha256(vectors.read_bytes()).hexdigest(),
        "cycles": 1,
    }
    vectors.with_suffix(".json").write_text(json.dumps(metadata))
    assert host.verify_vectors(vectors, "candidate")["cycles"] == 1
    with pytest.raises(ValueError, match="source"):
        host.verify_vectors(vectors, "different candidate")
    metadata["cycles"] = 2
    vectors.with_suffix(".json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="count"):
        host.verify_vectors(vectors, "candidate")
    vectors.write_text("1 3\n")
    with pytest.raises(ValueError, match="hash"):
        host.verify_vectors(vectors, "candidate")

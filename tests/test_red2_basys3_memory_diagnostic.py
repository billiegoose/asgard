import importlib.util
import sys
from pathlib import Path

import pytest

DIRECTORY = Path(__file__).resolve().parents[1] / "scripts/boards/red2_basys3"
spec = importlib.util.spec_from_file_location(
    "board_memory_diagnostic", DIRECTORY / "diagnose_memory.py"
)
diagnostic = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(DIRECTORY))
try:
    spec.loader.exec_module(diagnostic)
finally:
    sys.path.pop(0)


def test_byte_lane_analysis_accounts_for_non_byte_aligned_memory_field():
    values = [(1 << 128) - 1] + [1 << bit for bit in range(128)]
    mask = int.from_bytes(b"\x97" * 16, "little")
    report = diagnostic.analyze(values, [value & mask for value in values])
    assert not report["passed"]
    assert set(report["differing_response_byte_lanes"]) == {1, 2, 7}
    assert len(report["errors"]) == 49
    assert report["errors"][1]["differing_graph_bits"] == [3]


def test_correct_readback_passes():
    values = [0, (1 << 128) - 1, 0x0123456789ABCDEF0011223344556677]
    report = diagnostic.analyze(values, values)
    assert report["passed"]
    assert report["errors"] == []
    assert report["differing_response_byte_lanes"] == {}


@pytest.mark.parametrize("values,actual", [([1], []), ([1 << 128], [0]), ([0], [-1])])
def test_invalid_readback_is_rejected(values, actual):
    with pytest.raises(ValueError):
        diagnostic.analyze(values, actual)

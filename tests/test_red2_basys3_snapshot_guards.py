from pathlib import Path

import pytest
from scripts.boards.red2_basys3.snapshot_monitor import snapshot_response

MONITOR = (
    Path(__file__).resolve().parents[1] / "scripts/boards/red2_basys3/monitor.v"
).read_text()


@pytest.mark.parametrize(
    "before,after",
    [
        ("input [625:0] result", "input [626:0] result"),
        ("reg [6:0] index = 0;", "reg [7:0] index = 0;"),
        ("response <= {6'b0, result};", "response <= {5'b0, result};"),
        ("if (index >= 3 && index <= 81)", "if (index >= 4 && index <= 81)"),
        ("crc <= update_crc(crc, response[7:0]);", "crc <= 0;"),
        ("response <= {8'b0, response[631:8]};", "response <= 0;"),
    ],
)
def test_changed_frame_or_writer_assumptions_are_rejected(before, after):
    assert MONITOR.count(before) == 1
    with pytest.raises(ValueError):
        snapshot_response(MONITOR.replace(before, after))


def test_additional_response_writer_is_rejected():
    changed = MONITOR.replace("state <= IDLE;", "state <= IDLE; response <= 0;", 1)
    with pytest.raises(ValueError):
        snapshot_response(changed)


def test_duplicate_capture_is_rejected():
    with pytest.raises(ValueError):
        snapshot_response(MONITOR + "\nresponse <= {6'b0, result};\n")

from pathlib import Path

import pytest
from scripts.boards.red2_basys3 import burst_monitor
from scripts.boards.red2_basys3.snapshot_monitor import snapshot_response

MONITOR = (
    Path(__file__).resolve().parents[1] / "scripts/boards/red2_basys3/monitor.v"
).read_text()


@pytest.mark.parametrize("count", [1, 2, 257, 65537, (1 << 20) - 1])
def test_wire_encoding_preserves_every_non_value_field(count):
    command = ((1 << 722) - 1) & ~(0xFFFFFFFF << 280) & ~15 | 7
    wire = burst_monitor.clock_burst_command(command, count)
    assert wire & 15 == 10
    assert (wire >> 280) & 0xFFFFFFFF == count
    assert (wire & ~15 & ~(0xFFFFFFFF << 280)) == (command & ~15)


@pytest.mark.parametrize(
    "command,count",
    [
        (7, 0),
        (7, 1 << 20),
        (7, -1),
        (0, 2),
        (10, 2),
        (7 | (1 << 280), 2),
        (-1, 2),
        ((1 << 722) | 7, 2),
    ],
)
def test_unsafe_burst_request_is_rejected(command, count):
    with pytest.raises(ValueError):
        burst_monitor.clock_burst_command(command, count)


def test_grouping_preserves_observations_commands_and_last_pre_edge_status():
    other_clock = 7 | (1 << 312)
    valued_clock = 7 | (1 << 280)
    rows = [
        (7, 11),
        (7, 12),
        (0, 13),
        (0, 14),
        (7, 15),
        (other_clock, 16),
        (other_clock, 17),
        (valued_clock, 18),
        (valued_clock, 19),
        (7, 20),
    ]
    packets = list(burst_monitor.burst_trace(rows))
    assert packets == [
        (burst_monitor.clock_burst_command(7, 2), 12, 2),
        (0, 13, 1),
        (0, 14, 1),
        (7, 15, 1),
        (burst_monitor.clock_burst_command(other_clock, 2), 17, 2),
        (valued_clock, 18, 1),
        (valued_clock, 19, 1),
        (7, 20, 1),
    ]
    assert sum(edges for _, _, edges in packets) == len(rows)


def test_bursts_split_at_count_limit(monkeypatch):
    monkeypatch.setattr(burst_monitor, "MAX_CLOCK_BURST", 3)
    assert list(burst_monitor.burst_trace((7, n) for n in range(7))) == [
        (burst_monitor.clock_burst_command(7, 3), 2, 3),
        (burst_monitor.clock_burst_command(7, 3), 5, 3),
        (7, 6, 1),
    ]
    assert list(burst_monitor.burst_trace([])) == []


def test_reserved_wire_opcode_is_not_reinterpreted_as_native():
    with pytest.raises(ValueError):
        list(burst_monitor.burst_trace([(10, 0)]))


@pytest.mark.parametrize(
    "fragment",
    [
        "input [625:0] result",
        "output reg [721:0] command",
        "reg [3:0] state = IDLE;",
        "reg [727:0] request = 0;",
        "core_ce <= 0;",
        "request[727:722] == 0",
        "command <= request[721:0];",
        "reg [631:0] response = 0;",
    ],
)
def test_changed_monitor_contract_fails_closed(fragment):
    with pytest.raises(ValueError):
        burst_monitor.burst_clock(MONITOR.replace(fragment, "", 1))


def test_transform_is_explicit_and_composes_with_snapshot():
    with pytest.raises(ValueError):
        burst_monitor.burst_clock(burst_monitor.burst_clock(MONITOR))
    assert "BURST_RUN" in burst_monitor.burst_clock(snapshot_response(MONITOR))

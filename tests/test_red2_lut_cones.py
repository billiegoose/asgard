"""Mapped connectivity must preserve sharing and stop at storage boundaries."""

from scripts.experiments.red2_cfg_pilot.lut_cones import endpoint_cones


def cell(kind, inputs, outputs):
    return {
        "type": kind,
        "connections": {**inputs, **outputs},
        "port_directions": {
            **dict.fromkeys(inputs, "input"),
            **dict.fromkeys(outputs, "output"),
        },
    }


def report(cells, owners=None, output=()):
    return endpoint_cones(
        {
            "cells": cells,
            "ports": {"out": {"direction": "output", "bits": list(output)}}
            if output
            else {},
        },
        owners or {},
    )


def partitions(result):
    return {
        tuple(entry["endpoint_groups"]): entry["luts"]
        for entry in result["disjoint_endpoint_sets"]
    }


def test_reconvergent_lut_counts_once_per_group_and_shared_partition():
    result = report(
        {
            "shared": cell("LUT2", {"I0": [1], "I1": [2]}, {"O": [3]}),
            "join": cell("LUT2", {"I0": [3], "I1": [3]}, {"O": [4]}),
            "a": cell("FDRE", {"D": [4], "C": [0]}, {"Q": [10]}),
            "b": cell("FDRE", {"D": [3], "C": [0]}, {"Q": [11]}),
        },
        {10: {"a"}, 11: {"b"}},
    )
    assert result["overlapping_lut_cones"] == {"a": 2, "b": 1}
    assert partitions(result) == {("a",): 1, ("a", "b"): 1}
    assert sum(partitions(result).values()) == result["combinational_luts"] == 2


def test_flipflop_boundary_stops_fanin_and_clock_logic_is_excluded():
    result = report(
        {
            "first": cell("LUT1", {"I0": [1]}, {"O": [2]}),
            "clock": cell("LUT1", {"I0": [3]}, {"O": [4]}),
            "a": cell("FDRE", {"D": [2], "C": [4]}, {"Q": [10]}),
            "second": cell("LUT1", {"I0": [10]}, {"O": [11]}),
            "b": cell("FDRE", {"D": [11], "C": [4]}, {"Q": [12]}),
        },
        {10: {"a"}, 12: {"b"}},
    )
    assert result["overlapping_lut_cones"] == {"a": 1, "b": 1}
    assert partitions(result) == {(): 1, ("a",): 1, ("b",): 1}


def test_memory_input_and_read_output_are_separate_cones():
    result = report(
        {
            "write": cell("LUT1", {"I0": [1]}, {"O": [2]}),
            "graph_ram_machine_py_10": cell(
                "RAMB36E1", {"DIADI": [2], "CLKARDCLK": [0]}, {"DOADO": [3]}
            ),
            "read": cell("LUT1", {"I0": [3]}, {"O": [4]}),
            "a": cell("FDRE", {"D": [4], "C": [0]}, {"Q": [10]}),
        },
        {10: {"a"}},
    )
    assert result["overlapping_lut_cones"] == {"a": 1, "memory:graph_ram": 1}


def test_dsp_c_is_data_but_dsp_clock_is_excluded():
    result = report(
        {
            "data": cell("LUT1", {"I0": [1]}, {"O": [2]}),
            "clock": cell("LUT1", {"I0": [3]}, {"O": [4]}),
            "dsp": cell("DSP48E1", {"C": [2], "CLK": [4]}, {"P": [5]}),
        },
        output=[5],
    )
    assert result["overlapping_lut_cones"] == {"DSP_inputs": 1, "public_outputs": 0}
    assert partitions(result) == {(): 1, ("DSP_inputs",): 1}


def test_carry_and_dedicated_mux_are_transparent_to_lut_reachability():
    result = report(
        {
            "low": cell("LUT1", {"I0": [1]}, {"O": [2]}),
            "high": cell("LUT1", {"I0": [3]}, {"O": [4]}),
            "carry": cell("CARRY4", {"DI": [2, 4]}, {"CO": [5, 6]}),
            "mux": cell("MUXF7", {"I0": [5], "I1": [6]}, {"O": [7]}),
        },
        output=[7],
    )
    assert result["overlapping_lut_cones"]["public_outputs"] == 2
    assert partitions(result) == {("public_outputs",): 2}

import pytest
from scripts.boards.red2_basys3.clocks import clock_names


def packed_design(core="core.clk_25p0"):
    return {
        "modules": {
            "top": {
                "cells": {
                    "monitor_buffer": {"type": "BUFGCTRL", "connections": {"O": [10]}},
                    "core_buffer": {"type": "BUFGCTRL", "connections": {"O": [20]}},
                },
                "netnames": {"clock": {"bits": [10]}, core: {"bits": [20]}},
            }
        }
    }


@pytest.mark.parametrize("alias", ["core_clock", "core.clk_25p0"])
def test_constraints_follow_the_retained_packed_core_clock(alias):
    assert clock_names(packed_design(alias)) == {
        "monitor_buffer": "clock",
        "core_buffer": alias,
    }


def test_missing_packed_core_clock_is_rejected():
    design = packed_design()
    del design["modules"]["top"]["netnames"]["core.clk_25p0"]
    with pytest.raises(ValueError, match="No retained clock net"):
        clock_names(design)


def test_core_and_monitor_cannot_use_the_same_clock_net():
    design = packed_design()
    design["modules"]["top"]["cells"]["core_buffer"]["connections"]["O"] = [10]
    with pytest.raises(ValueError, match="must be distinct"):
        clock_names(design)

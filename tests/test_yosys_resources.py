from scripts.yosys_resources import count_resources


def test_counts_hierarchy_multiplicity_and_ignores_blackbox_simulation_cells():
    netlist = {
        "modules": {
            "top": {
                "attributes": {"top": "0001"},
                "cells": {
                    "a": {"type": "worker"},
                    "b": {"type": "worker"},
                    "metadata": {"type": "$scopeinfo"},
                    "clock": {"type": "MMCME2_ADV"},
                    "clock_gate": {"type": "BUFGCE"},
                },
            },
            "worker": {
                "cells": {
                    "lut": {"type": "LUT6"},
                    "ff": {"type": "FDRE"},
                    "ram": {"type": "RAMB18E1"},
                    "dsp": {"type": "DSP48E1"},
                }
            },
            "LUT6": {
                "attributes": {"blackbox": "0001"},
                "cells": {"simulation": {"type": "$mux"}},
            },
            "FDRE": {"attributes": {"blackbox": "0001"}, "cells": {}},
            "RAMB18E1": {
                "attributes": {"blackbox": "0001"},
                "cells": {"simulation": {"type": "LUT6"}},
            },
            "DSP48E1": {"attributes": {"blackbox": "0001"}, "cells": {}},
            "MMCME2_ADV": {
                "attributes": {"blackbox": "0001"},
                "cells": {"simulation": {"type": "$mul"}},
            },
        }
    }
    resources = count_resources(netlist)
    assert resources["lut"] == 2
    assert resources["flipflops"] == 2
    assert resources["bram36_equivalent"] == 1
    assert resources["dsp48"] == 2
    assert "$mux" not in resources["primitives"]
    assert "$scopeinfo" not in resources["primitives"]
    assert "$mul" not in resources["primitives"]
    assert resources["primitives"]["MMCME2_ADV"] == 1
    assert resources["primitives"]["BUFGCE"] == 1
    assert resources["within_basys3_resource_limits"]


def test_distributed_memory_consumes_luts_and_unknown_memories_prevent_fit_claim():
    netlist = {
        "modules": {
            "top": {
                "attributes": {"top": 1},
                "cells": {
                    "ram": {"type": "RAM256X1S"},
                    "future_ram": {"type": "RAM_UNKNOWN"},
                },
            }
        }
    }
    resources = count_resources(netlist)
    assert resources["lut_total"] == 4
    assert resources["unknown_memory_primitives"] == ["RAM_UNKNOWN"]
    assert not resources["within_basys3_resource_limits"]


def test_unmapped_logic_and_unknown_ip_prevent_fit_claim():
    netlist = {
        "modules": {
            "top": {
                "attributes": {"top": 1},
                "cells": {"adder": {"type": "$add"}, "ip": {"type": "custom_blackbox"}},
            }
        }
    }
    resources = count_resources(netlist)
    assert resources["unaccounted_primitives"] == ["$add", "custom_blackbox"]
    assert not resources["within_basys3_resource_limits"]


def test_configuration_flash_access_uses_one_dedicated_startup_site():
    cells = {"flash_clock": {"type": "STARTUPE2"}}
    netlist = {"modules": {"top": {"attributes": {"top": 1}, "cells": cells}}}
    resources = count_resources(netlist)
    assert resources["startup"] == 1
    assert resources["lut_total"] == 0
    assert resources["unaccounted_primitives"] == []
    assert resources["within_basys3_resource_limits"]
    cells["second_flash_clock"] = {"type": "STARTUPE2"}
    resources = count_resources(netlist)
    assert resources["basys3_over_budget"]["startup"] == {"used": 2, "available": 1}
    assert not resources["within_basys3_resource_limits"]

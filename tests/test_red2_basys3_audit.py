import json

import pytest
from scripts.boards.red2_basys3.audit import audit, canonical_bel


def write_netlist(path, bels):
    cells = {
        str(index): {"type": "SLICE_LUTX", "attributes": {"NEXTPNR_BEL": bel}}
        for index, bel in enumerate(bels)
    }
    path.write_text(json.dumps({"modules": {"top": {"cells": cells}}}))


def test_audit_handles_export_names_and_shared_lut_outputs(tmp_path):
    placed, routed, grid = [tmp_path / name for name in ("p.json", "r.json", "g.json")]
    grid.write_text(
        json.dumps(
            {
                "tile": {
                    "grid_x": 52,
                    "grid_y": 69,
                    "sites": {"SLICE_X30Y83": "SLICEM", "SLICE_X31Y83": "SLICEL"},
                }
            }
        )
    )
    write_netlist(
        placed,
        [
            "X52Y69/SLICE_X0Y0.A5LUT",
            "X52Y69/SLICE_X0Y0.A6LUT",
            "X52Y69/SLICE_X1Y0.A6LUT",
        ],
    )
    write_netlist(
        routed,
        [
            "SLICE_X30Y83/A5LUT",
            "SLICE_X30Y83/A6LUT",
            "SLICE_X31Y83/A6LUT",
        ],
    )
    result = audit(placed, routed, grid)
    assert result["preserved_cell_placements"] == 3
    assert result["lut_half_cells"] == 3
    assert result["unique_physical_lut_sites"] == 2

    write_netlist(
        routed,
        [
            "SLICE_X31Y83/A5LUT",
            "SLICE_X30Y83/A6LUT",
            "SLICE_X31Y83/A6LUT",
        ],
    )
    with pytest.raises(AssertionError, match="0"):
        audit(placed, routed, grid)


def test_canonical_bel_handles_typed_ram_name_and_relative_y():
    tiles = {(19, 5): {"RAMB18_X0Y58": "RAMB18E1", "RAMB18_X0Y59": "RAMB18E1"}}
    assert canonical_bel("X19Y5/RAMB18_X0Y1.RAMB18E1~RAMB18E1", tiles) == (
        "RAMB18_X0Y59/RAMB18E1"
    )
    assert canonical_bel("X0Y0/PSEUDO_GND", tiles) == "X0Y0/PSEUDO_GND"

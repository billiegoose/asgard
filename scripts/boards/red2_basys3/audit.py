#!/usr/bin/env python3
"""Check physical LUT fit and preserved placement across nextpnr export."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def canonical_bel(bel, tiles):
    """Convert generic tile-relative BEL names to Xilinx site/BEL names."""
    match = re.fullmatch(r"X(\d+)Y(\d+)/(.+)_X(\d+)Y(\d+)\.(.+)", bel)
    if not match:
        return bel
    x, y, prefix, rel_x, rel_y, name = match.groups()
    sites = [re.fullmatch(r"(.+)_X(\d+)Y(\d+)", site) for site in tiles[int(x), int(y)]]
    sites = [site for site in sites if site and site[1] == prefix]
    assert sites, f"no physical site for {bel}"
    site_x = min(int(site[2]) for site in sites) + int(rel_x)
    site_y = min(int(site[3]) for site in sites) + int(rel_y)
    site = f"{prefix}_X{site_x}Y{site_y}"
    assert site in tiles[int(x), int(y)], site
    return f"{site}/{name.split('~')[0]}"


def audit(placed, routed, tilegrid):
    grid = json.loads(tilegrid.read_text())
    tiles = {(tile["grid_x"], tile["grid_y"]): tile["sites"] for tile in grid.values()}
    original = json.loads(placed.read_text())["modules"]["top"]["cells"]
    final = json.loads(routed.read_text())["modules"]["top"]["cells"]
    checked = 0
    for name, cell in original.items():
        bel = cell["attributes"].get("NEXTPNR_BEL")
        if bel:
            assert final[name]["type"] == cell["type"], name
            assert canonical_bel(bel, tiles) == canonical_bel(
                final[name]["attributes"]["NEXTPNR_BEL"], tiles
            ), name
            checked += 1
    sites = set()
    halves = 0
    for cell in final.values():
        if cell["type"] == "SLICE_LUTX":
            bel = canonical_bel(cell["attributes"]["NEXTPNR_BEL"], tiles)
            assert re.search(r"/[ABCD][56]LUT$", bel), bel
            sites.add(re.sub(r"([ABCD])[56]LUT$", r"\1LUT", bel))
            halves += 1
    assert len(sites) <= 20800, len(sites)
    return {
        "placed_netlist_sha256": hashlib.sha256(placed.read_bytes()).hexdigest(),
        "routed_netlist_sha256": hashlib.sha256(routed.read_bytes()).hexdigest(),
        "tilegrid_sha256": hashlib.sha256(tilegrid.read_bytes()).hexdigest(),
        "preserved_cell_placements": checked,
        "lut_half_cells": halves,
        "unique_physical_lut_sites": len(sites),
        "basys3_lut_limit": 20800,
        "within_basys3_physical_lut_limit": True,
        "normalization": (
            "physical site/BEL names; merge A5LUT/A6LUT only in identical site"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("placed", type=Path)
    parser.add_argument("routed", type=Path)
    parser.add_argument("tilegrid", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.placed, args.routed, args.tilegrid), indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Experimental placement isolation for the 625 variable snapshot capture FFs."""

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.boards.red2_basys3.relocate_monitor import (  # noqa: E402
    control_set,
    coordinates,
)


def isolate_response(original):
    """Return an isolated placement and prove that only capture FF BELs changed."""
    design = copy.deepcopy(original)
    m = design["modules"]["top"]
    cells = m["cells"]
    assert not any(
        v["attributes"].get("ROUTING", "").strip() for v in m["netnames"].values()
    )
    flops = {
        c["connections"]["Q"][0]: (n, c)
        for n, c in cells.items()
        if c["type"] == "SLICE_FFX"
    }
    targets = []
    for n, v in m["netnames"].items():
        match = re.fullmatch("monitor.response\\[(\\d+)\\]", n)
        if match and v["bits"][0] in flops:
            targets.append((int(match[1]), *flops[v["bits"][0]]))
    assert len(targets) == 625
    targets.sort()
    ctl = control_set(targets[0][2])
    assert all(
        (
            control_set(c) == ctl and "monitor.v:" in c["attributes"].get("src", "")
            for _, _, c in targets
        )
    )
    occupied = {c["attributes"].get("NEXTPNR_BEL", "") for c in cells.values()}
    controls = defaultdict(list)
    sites = set()
    tiles = set()
    carry = set()
    lut_pairs = set()
    for c in cells.values():
        bel = c["attributes"].get("NEXTPNR_BEL", "")
        match = re.match("(X\\d+Y\\d+)/SLICE_X([01])Y0\\.", bel)
        if not match:
            continue
        site = bel.split(".")[0]
        sites.add(site)
        tiles.add(match[1])
        if c["type"] == "SLICE_FFX":
            controls[site].append(control_set(c))
        if "CARRY" in c["type"]:
            carry.add(site)
        if c["type"] == "SLICE_LUTX":
            lut_pairs.add((site, bel.split(".")[-1][0]))
    # Both CLBLL and CLBLM tiles have two slices. Use empty siblings in tiles
    # already occupied by this design instead of expanding its placement area.
    for tile in tiles:
        for half in (0, 1):
            sites.add(f"{tile}/SLICE_X{half}Y0")
    choices = []
    for site in sorted(sites - carry):
        if any(c != ctl for c in controls[site]):
            continue
        for letter in "ABCD":
            if (site, letter) in lut_pairs:
                continue
            if any(
                f"{site}.{letter}{suffix}" in occupied
                for suffix in ("FF", "5FF", "6LUT", "5LUT")
            ):
                continue
            choices.append((site, letter))
    initial_candidates = len(choices)
    assert initial_candidates >= len(targets), (initial_candidates, len(targets))
    moves = []
    for bit, name, ff in targets:
        old = ff["attributes"]["NEXTPNR_BEL"]
        x, y = coordinates(old)
        distance, site, letter = min(
            (
                (abs(coordinates(s)[0] - x) + abs(coordinates(s)[1] - y), s, slot)
                for s, slot in choices
            )
        )
        choices.remove((site, letter))
        new = f"{site}.{letter}FF"
        ff["attributes"]["NEXTPNR_BEL"] = new
        assert new not in occupied
        occupied.add(new)
        moves.append(
            {
                "public_status_bit": bit,
                "cell": name,
                "old_bel": old,
                "new_bel": new,
                "distance_tiles": distance,
            }
        )
    target_names = {n for _, n, _ in targets}
    for name, c in cells.items():
        before = copy.deepcopy(original["modules"]["top"]["cells"][name])
        after = copy.deepcopy(c)
        if name in target_names:
            before["attributes"].pop("NEXTPNR_BEL")
            after["attributes"].pop("NEXTPNR_BEL")
        assert before == after, name
    assert len({c["attributes"]["NEXTPNR_BEL"] for _, _, c in targets}) == 625
    for _, _, c in targets:
        site, bel = c["attributes"]["NEXTPNR_BEL"].split(".")
        assert bel.endswith("FF") and (not bel.endswith("5FF"))
        assert site not in carry and (site, bel[0]) not in lut_pairs
    return (design, moves, initial_candidates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("placed", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.report.resolve():
        parser.error("output and report must differ")
    if args.output.exists() or args.report.exists():
        parser.error("output and report must be new files")
    design, moves, candidates = isolate_response(json.loads(args.placed.read_text()))
    args.output.write_text(json.dumps(design, separators=(",", ":")))

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    report = {
        "scope": (
            "Experimental placement only: all 625 response capture FFs moved to "
            "primary FFs with empty companion LUT/FF pairs, no carry in the "
            "destination slice, matching clock/reset/enable/inversions; only "
            "already-used CLB tiles and their sibling slices are eligible. "
            "All cell types/parameters/connections, all core placements and "
            "every other placement are unchanged. Global rerouting and "
            "physical qualification are required."
        ),
        "source_placement_sha256": sha(args.placed),
        "modified_placement_sha256": sha(args.output),
        "initial_free_compatible_pairs": candidates,
        "moved_response_FFs": len(moves),
        "unchanged_cells": len(design["modules"]["top"]["cells"]) - len(moves),
        "moves": moves,
        "passed": True,
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        "RESPONSE_ISOLATION_PLACEMENT_PASS",
        len(moves),
        "moved;",
        report["unchanged_cells"],
        "unchanged",
    )


if __name__ == "__main__":
    main()

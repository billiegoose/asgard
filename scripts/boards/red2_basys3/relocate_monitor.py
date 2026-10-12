#!/usr/bin/env python3
"""Reproduce the experimental Basys 3 monitor placement without changing logic."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def relocate(design, first_bit=364, count=13):
    module = design["modules"]["top"]
    cells = module["cells"]
    for net in module["netnames"].values():
        if net["attributes"].get("ROUTING", "").strip():
            raise ValueError("Use a saved placement before routing")
    drivers = {}
    users = {}
    flops = {}
    occupied = set()
    sites = set()
    all_bels = set()
    controls = {}
    for name, cell in cells.items():
        bel = cell["attributes"].get("NEXTPNR_BEL", "")
        all_bels.add(bel)
        match = re.fullmatch(r"(X\d+Y\d+/SLICE_X\d+Y\d+)\.([ABCD])[56]LUT", bel)
        if match:
            occupied.add((match[1], match[2]))
            sites.add(match[1])
        if cell["type"] == "SLICE_FFX":
            flops[cell["connections"]["Q"][0]] = (name, cell)
            controls.setdefault(bel.split(".")[0], []).append(control_set(cell))
        for port, bits in cell["connections"].items():
            if cell["port_directions"][port] == "output":
                for bit in bits:
                    drivers[bit] = (name, cell)
            else:
                for bit in bits:
                    users.setdefault(bit, set()).add(name)

    moves = []
    for index in range(first_bit, first_bit + count):
        result = module["netnames"][f"result[{index}]"]["bits"]
        response = module["netnames"][f"monitor.response[{index}]"]["bits"][0]
        ff_name, ff = flops[response]
        if "monitor.v:" not in ff["attributes"].get("src", ""):
            raise ValueError(f"Response bit {index} is not a monitor flip-flop")
        data = ff["connections"]["D"][0]
        lut_name, lut = drivers[data]
        if users[data] != {ff_name}:
            raise ValueError(f"Response bit {index} shares its LUT output")
        if lut["type"] != "SLICE_LUTX":
            raise ValueError(f"Response bit {index} has no direct LUT driver")
        pins = [
            key.removeprefix("X_ORIG_PORT_")
            for key, value in lut["attributes"].items()
            if key.startswith("X_ORIG_PORT_") and value == "I0"
        ]
        if len(pins) != 1 or lut["connections"][pins[0]] != result:
            raise ValueError(f"Response bit {index} has an unexpected load mux")
        old_lut = lut["attributes"]["NEXTPNR_BEL"]
        old_ff = ff["attributes"]["NEXTPNR_BEL"]
        position = coordinates(old_lut)
        control = control_set(ff)
        ff_suffix = old_ff.split(".")[-1][1:]
        candidates = []
        for site in sites:
            if any(existing != control for existing in controls.get(site, [])):
                continue
            x, y = coordinates(site)
            distance = abs(x - position[0]) + abs(y - position[1])
            for letter in "ABCD":
                if (site, letter) in occupied:
                    continue
                if f"{site}.{letter}{ff_suffix}" in all_bels:
                    continue
                candidates.append((distance, site, letter))
        if not candidates:
            raise ValueError(f"No compatible free LUT/flip-flop pair for bit {index}")
        distance, site, letter = min(candidates)
        occupied.add((site, letter))
        new_ff = f"{site}.{letter}{ff_suffix}"
        half = "5LUT" if old_lut.endswith("5LUT") else "6LUT"
        new_lut = f"{site}.{letter}{half}"
        ff["attributes"]["NEXTPNR_BEL"] = new_ff
        lut["attributes"]["NEXTPNR_BEL"] = new_lut
        all_bels.add(new_ff)
        controls.setdefault(site, []).append(control)
        moves.append(
            {
                "status_bit": index,
                "lut": lut_name,
                "flip_flop": ff_name,
                "old_lut_bel": old_lut,
                "new_lut_bel": new_lut,
                "old_ff_bel": old_ff,
                "new_ff_bel": new_ff,
                "distance_tiles": distance,
            }
        )
    return moves


def coordinates(bel):
    match = re.match(r"X(\d+)Y(\d+)", bel)
    if not match:
        raise ValueError(f"Expected a native himbaechel BEL, got {bel}")
    return tuple(map(int, match.groups()))


def control_set(cell):
    connections = tuple(
        tuple(cell["connections"].get(port, [])) for port in ("CK", "SR", "CE")
    )
    params = cell["parameters"]
    clock_inverted = int(params.get("IS_C_INVERTED", "0"), 2) != 0
    reset_inverted = any(
        int(params.get(name, "0"), 2) != 0
        for name in (
            "IS_R_INVERTED",
            "IS_S_INVERTED",
            "IS_CLR_INVERTED",
            "IS_PRE_INVERTED",
        )
    )
    flags = (
        clock_inverted,
        reset_inverted,
        "X_FFSYNC" in cell["attributes"],
        "X_FF_AS_LATCH" in cell["attributes"],
    )
    return connections, flags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("placed", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--first-bit", type=int, default=364)
    parser.add_argument("--count", type=int, default=13)
    args = parser.parse_args()
    if args.first_bit < 0 or args.count < 1 or args.first_bit + args.count > 626:
        parser.error("Select at least one response bit within 0..625")
    if args.output.resolve() == args.report.resolve():
        parser.error("Output and report must be different files")
    if args.output.exists() or args.report.exists():
        parser.error("Output and report must be new files")
    raw = args.placed.read_bytes()
    design = json.loads(raw)
    moves = relocate(design, args.first_bit, args.count)
    output = json.dumps(design, separators=(",", ":")) + "\n"
    with args.output.open("x") as stream:
        stream.write(output)
    report = {
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "scope": (
            "Move monitor LUT/FF pairs only; preserve all logic and core placements"
        ),
        "moves": moves,
    }
    with args.report.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(f"MONITOR_PAIRS_RELOCATED {len(moves)}")


if __name__ == "__main__":
    main()

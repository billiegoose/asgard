"""Reload clock constraints using the net names retained in a saved placement."""

import argparse
import json
import re
from pathlib import Path


def clock_names(design):
    module = design["modules"]["top"]
    names = {}
    for buffer in ("monitor_buffer", "core_buffer"):
        cell = module["cells"][buffer]
        if cell["type"] != "BUFGCTRL":
            raise ValueError(f"Unexpected packed clock buffer: {buffer}")
        bits = cell["connections"]["O"]
        aliases = [
            name for name, net in module["netnames"].items() if net["bits"] == bits
        ]
        if not aliases:
            raise ValueError(f"No retained clock net for {buffer}")
        name = min(aliases, key=lambda value: (len(value), value))
        if not re.fullmatch(r"[A-Za-z0-9_.$]+", name):
            raise ValueError(f"Unsupported clock net name: {name}")
        names[buffer] = name
    if len(set(names.values())) != 2:
        raise ValueError("Monitor and gated core clocks must be distinct")
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("placed", type=Path)
    parser.add_argument("--sdc", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    names = clock_names(json.loads(args.placed.read_text()))
    args.sdc.write_text(
        "create_clock -period 10 [get_ports clk_100p0]\n"
        + "".join(
            f"create_clock -period 100 [get_nets {{{name}}}]\n"
            for name in names.values()
        )
    )
    args.report.write_text(json.dumps(names, indent=2) + "\n")


if __name__ == "__main__":
    main()

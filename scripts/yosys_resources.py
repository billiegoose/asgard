#!/usr/bin/env python3
"""Count instantiated FPGA primitives without expanding their simulation models."""

import argparse
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path


def attribute_true(value):
    return str(value).strip("0") == "1"


def count_resources(netlist, top=None):
    modules = netlist["modules"]
    if top is None:
        roots = [
            name
            for name, module in modules.items()
            if attribute_true(module.get("attributes", {}).get("top", 0))
        ]
        if len(roots) != 1:
            raise ValueError(f"Expected one top module, found {roots}")
        top = roots[0]
    visiting = set()

    @lru_cache(None)
    def count(name):
        if name == "$scopeinfo":
            return Counter()
        module = modules.get(name)
        if module is None or attribute_true(
            module.get("attributes", {}).get("blackbox", 0)
        ):
            return Counter({name: 1})
        if name in visiting:
            raise ValueError(f"Recursive module hierarchy: {name}")
        visiting.add(name)
        result = Counter()
        for cell in module.get("cells", {}).values():
            result.update(count(cell["type"]))
        visiting.remove(name)
        return result

    primitives = count(top)
    luts = sum(
        n for name, n in primitives.items() if re.fullmatch(r"LUT[1-6](?:_2)?", name)
    )
    memory_lut_cost = {
        "RAM32X1S": 1,
        "RAM64X1S": 1,
        "RAM128X1S": 2,
        "RAM256X1S": 4,
        "RAM32X1D": 2,
        "RAM64X1D": 2,
        "RAM128X1D": 4,
        "RAM32M": 4,
        "RAM64M": 4,
        "SRL16E": 1,
        "SRLC32E": 1,
    }
    memory_luts = sum(primitives[name] * cost for name, cost in memory_lut_cost.items())
    unknown_memories = [
        name
        for name in primitives
        if name.startswith(("RAM", "SRL"))
        and not name.startswith("RAMB")
        and name not in memory_lut_cost
    ]
    ff = sum(
        n
        for name, n in primitives.items()
        if re.fullmatch(r"(?:FD|LD)[A-Z0-9_]*", name)
    )
    bram18 = sum(n for name, n in primitives.items() if name.startswith("RAMB18"))
    bram36 = sum(n for name, n in primitives.items() if name.startswith("RAMB36"))
    dsp = sum(n for name, n in primitives.items() if name.startswith("DSP48"))
    known_primitive = re.compile(
        r"(?:LUT[1-6](?:_2)?|(?:FD|LD)[A-Z0-9_]*|RAM[A-Z0-9_]*|"
        r"SRL[A-Z0-9_]*|DSP48[A-Z0-9_]*|CARRY4|MUXF[5-9]|"
        r"(?:I|O|IO)BUF[A-Z0-9_]*|BUF[A-Z0-9_]*|"
        r"MMCME2_(?:ADV|BASE)|PLLE2_(?:ADV|BASE)|STARTUPE2|INV|GND|VCC)"
    )
    unaccounted = [name for name in primitives if not known_primitive.fullmatch(name)]
    resources = {
        "top": top,
        "lut": luts,
        "lut_memory": memory_luts,
        "lut_total": luts + memory_luts,
        "unknown_memory_primitives": unknown_memories,
        "unaccounted_primitives": unaccounted,
        "flipflops": ff,
        "bram18": bram18,
        "bram36": bram36,
        "bram36_equivalent": bram36 + bram18 / 2,
        "dsp48": dsp,
        "carry4": primitives["CARRY4"],
        "muxf7": primitives["MUXF7"],
        "muxf8": primitives["MUXF8"],
        "startup": primitives["STARTUPE2"],
        "primitives": dict(sorted(primitives.items())),
    }
    limits = {
        "lut_total": 20800,
        "flipflops": 41600,
        "bram36_equivalent": 50,
        "dsp48": 90,
        "carry4": 5200,
        "muxf7": 10400,
        "muxf8": 5200,
        "startup": 1,
    }
    resources["basys3_over_budget"] = {
        name: {"used": resources[name], "available": limit}
        for name, limit in limits.items()
        if resources[name] > limit
    }
    resources["within_basys3_resource_limits"] = not (
        resources["basys3_over_budget"] or unknown_memories or unaccounted
    )
    return resources


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("--top")
    args = parser.parse_args()
    print(
        json.dumps(
            count_resources(json.loads(args.netlist.read_text()), args.top), indent=2
        )
    )

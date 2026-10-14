"""Measure mapped LUT reachability without inventing source-function ownership."""

from collections import Counter, defaultdict

FLIPFLOPS = {"FDRE", "FDCE", "FDPE", "FDSE"}
MEMORIES = {"RAMB18E1", "RAMB36E1", "RAM64X1S", "RAM256X1S"}
LUTS = {f"LUT{width}" for width in range(1, 7)}
COMBINATIONAL = LUTS | {"INV", "CARRY4", "MUXF7", "MUXF8"}
CLOCK_PORTS = {"CLK", "CLKA", "CLKB", "CLKARDCLK", "CLKBWRCLK"}


def endpoint_cones(design, register_owners):
    """Return overlapping cones and a disjoint partition by endpoint-group set.

    Stop at every register, memory and DSP primitive. Include sequential data,
    enable/reset/control inputs and public outputs, but exclude clock pins.
    LUT RAM is a memory boundary and is not counted as a combinational LUT.
    """
    cells = design["cells"]
    luts = {name for name, cell in cells.items() if cell["type"] in LUTS}
    drivers, inputs = {}, {}
    for name, cell in cells.items():
        if cell["type"] not in COMBINATIONAL:
            continue
        inputs[name] = []
        for port, bits in cell["connections"].items():
            direction = cell["port_directions"][port]
            for bit in bits:
                if not isinstance(bit, int):
                    continue
                if direction == "input":
                    inputs[name].append(bit)
                elif direction == "output":
                    if bit in drivers and drivers[bit] != name:
                        raise ValueError(
                            f"multiple combinational drivers for bit {bit}"
                        )
                    drivers[bit] = name

    endpoints = defaultdict(set)
    endpoint_counts = Counter()
    for name, cell in cells.items():
        kind = cell["type"]
        if kind in FLIPFLOPS:
            groups = register_owners.get(cell["connections"]["Q"][0], set())
            group = (
                next(iter(groups))
                if len(groups) == 1
                else "shared_register"
                if groups
                else "unattributed_register"
            )
        elif kind in MEMORIES:
            instance = next(
                part.split("_machine_py_")[0]
                for part in name.split(".")
                if "_ram_machine_py_" in part or "_rom_machine_py_" in part
            )
            group = "memory:" + instance
        elif kind == "DSP48E1":
            group = "DSP_inputs"
        else:
            continue
        endpoint_counts[group] += 1
        for port, bits in cell["connections"].items():
            if cell["port_directions"][port] != "input":
                continue
            if port in CLOCK_PORTS or (kind in FLIPFLOPS and port == "C"):
                continue
            endpoints[group].update(bit for bit in bits if isinstance(bit, int))
    for port in design["ports"].values():
        if port["direction"] == "output":
            endpoints["public_outputs"].update(
                bit for bit in port["bits"] if isinstance(bit, int)
            )

    membership = defaultdict(set)
    cone_sizes = {}
    for group, bits in endpoints.items():
        todo, visited, reached = list(bits), set(), set()
        while todo:
            name = drivers.get(todo.pop())
            if name is None or name in visited:
                continue
            visited.add(name)
            if name in luts:
                reached.add(name)
                membership[name].add(group)
            todo.extend(inputs[name])
        cone_sizes[group] = len(reached)
    partitions = Counter(tuple(sorted(membership[name])) for name in luts)
    return {
        "method": "Conservative primitive-level combinational fan-in through "
        "LUT/INV/CARRY4/MUXF7/MUXF8 "
        "to sequential data/control inputs and public outputs; stop at every "
        "register, memory and DSP primitive; exclude clock pins",
        "limitation": "Reachability is not source-function ownership or predicted "
        "removable area. Multi-output primitives traverse all input pins. "
        "Overlapping cones must not be summed. Disjoint sets "
        "partition combinational LUTs only; LUT RAM is reported separately.",
        "combinational_luts": len(luts),
        "sequential_endpoint_counts": dict(sorted(endpoint_counts.items())),
        "overlapping_lut_cones": dict(sorted(cone_sizes.items())),
        "disjoint_endpoint_sets": [
            {"endpoint_groups": list(groups), "luts": count}
            for groups, count in sorted(
                partitions.items(), key=lambda item: (-item[1], item[0])
            )
        ],
    }

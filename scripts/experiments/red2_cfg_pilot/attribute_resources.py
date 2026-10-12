#!/usr/bin/env python3
"""Attribute mapped storage to named RED2 registers and memory instances.

This deliberately does not invent source-level LUT ownership after ABC flattens
and shares the logic. Run against the exact generated source and mapped core.
"""

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def register_names(tree, function):
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function
    )
    return {
        n.target.id
        for n in ast.walk(node)
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and isinstance(n.annotation, ast.Subscript)
        and ast.unparse(n.annotation.value) == "Reg"
    }


def attribute(source, mapped, module):
    tree = ast.parse(source.read_text())
    root_registers = register_names(tree, "SynthesizableRED2Machine")
    engine_registers = register_names(tree, "cfg_red2_app_lambda_cfg")
    design = json.loads(mapped.read_text())["modules"][module]
    owners = defaultdict(set)
    for name, net in design["netnames"].items():
        if name.startswith("$"):
            continue
        parts = name.split(".")
        group = None
        if len(parts) == 2 and parts[-1] in root_registers:
            variable = parts[-1]
            if variable.startswith("cfg_"):
                group = "transfer_bridge"
            elif variable.startswith(("u64_div_", "u64_mul_", "join_scalar_int_")):
                group = "integer_arithmetic"
            else:
                group = "remaining_core_state"
        elif (
            len(parts) == 3
            and parts[1].startswith("cfg_red2_app_lambda_cfg_")
            and parts[-1] in engine_registers
        ):
            group = "microengine"
        if group:
            for bit in net["bits"]:
                if isinstance(bit, int):
                    owners[bit].add(group)

    flipflops = Counter()
    memories = defaultdict(Counter)
    multipliers = Counter()
    primitives = Counter()
    for name, cell in design["cells"].items():
        kind = cell["type"]
        primitives[kind] += 1
        if kind in ("FDRE", "FDCE", "FDSE", "FDPE"):
            groups = owners[cell["connections"]["Q"][0]]
            group = (
                next(iter(groups))
                if len(groups) == 1
                else "shared"
                if groups
                else "unattributed"
            )
            flipflops[group] += 1
        elif kind in ("RAMB36E1", "RAMB18E1", "RAM64X1S", "RAM256X1S"):
            instance = next(
                part
                for part in name.split(".")
                if "_rom_machine_py_" in part or "_ram_machine_py_" in part
            )
            instance = instance.split("_machine_py_")[0]
            memories[instance][kind] += 1
        elif kind == "DSP48E1":
            instance = next(
                part for part in name.split(".") if "bin_op_inferred_mult_" in part
            )
            multipliers[instance] += 1

    return {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "mapped_core_sha256": hashlib.sha256(mapped.read_bytes()).hexdigest(),
        "module": module,
        "method": (
            "Match declared Reg variable net aliases to mapped flip-flop Q bits; "
            "group RAM and DSP primitives by preserved instance names."
        ),
        "limitation": (
            "Register ownership is not a functional LUT budget. ABC flattened "
            "and shared combinational logic; source-function LUT totals cannot "
            "be recovered from these names."
        ),
        "declared_register_variables": {
            "root": len(root_registers),
            "microengine": len(engine_registers),
        },
        "flipflops_by_named_register_owner": dict(sorted(flipflops.items())),
        "memories_by_instance": {k: dict(v) for k, v in sorted(memories.items())},
        "dsp48_by_multiplier_instance": dict(sorted(multipliers.items())),
        "primitives": dict(sorted(primitives.items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("mapped", type=Path)
    parser.add_argument("--module", default="red2_core")
    args = parser.parse_args()
    print(json.dumps(attribute(args.source, args.mapped, args.module), indent=2))


if __name__ == "__main__":
    main()

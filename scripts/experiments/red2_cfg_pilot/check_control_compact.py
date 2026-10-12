"""Check typed copy fusion, branch remapping, packet preservation and guards."""

import copy

from control_compact import compact

ops = {
    n: i
    for i, n in enumerate(
        (
            "copy",
            "add",
            "sub",
            "and",
            "or",
            "eq",
            "ne",
            "not",
            "bool_and",
            "bool_or",
            "shr",
            "shl",
            "ge",
            "branch",
            "jump",
            "request",
            "response",
            "halt",
        )
    )
}


def row(op, **values):
    return {
        "op": ops[op],
        "a": 0,
        "b": 0,
        "d": 0,
        "width": 8,
        "yes": 0,
        "no": 0,
        **values,
    }


m = {
    "ops": ops,
    "entry_pc": {"1": 1},
    "request_sentinel": 63,
    "slots": {
        "input": 0,
        "$constant_1": 1,
        "$temp_2": 2,
        "held": 3,
        "condition": 4,
        "$temp_5": 5,
    },
    "rows": [
        row("halt"),
        row("add", a=0, b=1, d=2),
        row("copy", a=2, d=3),
        row("branch", a=4, yes=4, no=7),
        row("sub", a=3, b=1, d=5),
        row("copy", a=5, d=3),
        row("jump", yes=7),
        row("request", a=3, d=0),
        row("request", d=63),
        row("halt"),
    ],
}


def run(program, value, condition):
    mem = [value, 1, 0, 0, condition, 0]
    pc = program["entry_pc"]["1"]
    packet = []
    for _ in range(30):
        r = program["rows"][pc]
        pc += 1
        if r["op"] == ops["halt"]:
            return mem[3], packet
        if r["op"] == ops["jump"]:
            pc = r["yes"]
        elif r["op"] == ops["branch"]:
            pc = r["yes"] if mem[r["a"]] else r["no"]
        elif r["op"] == ops["request"]:
            packet.append((r["d"], mem[r["a"]] if r["d"] != 63 else None))
        else:
            a, b = mem[r["a"]], mem[r["b"]]
            value = (
                a
                if r["op"] == ops["copy"]
                else a + b
                if r["op"] == ops["add"]
                else a - b
            )
            mem[r["d"]] = value & ((1 << r["width"]) - 1)
    raise AssertionError("control failed to halt")


new = copy.deepcopy(m)
compact(new)
assert new["control_compaction"]["fused_copies"] == 2
assert new["control_compaction"]["removed_fallthrough_jumps"] == 1
for value in (0, 1, 254, 255):
    for condition in (0, 1):
        assert run(m, value, condition) == run(new, value, condition)
for kind in ("narrow", "extra_use", "other_predecessor", "entry"):
    modified = copy.deepcopy(m)
    if kind == "narrow":
        modified["rows"][2]["width"] = 4
    elif kind == "extra_use":
        modified["rows"][7]["a"] = 2
    elif kind == "other_predecessor":
        modified["rows"][0] = row("jump", yes=2)
    else:
        modified["entry_pc"]["2"] = 2
    compact(modified)
    assert modified["control_compaction"]["fused_copies"] == 1
for kind in ("cycle", "unknown"):
    modified = copy.deepcopy(m)
    modified["rows"][6] = (
        row("jump", yes=1) if kind == "cycle" else {**row("copy"), "op": 99}
    )
    try:
        compact(modified)
    except AssertionError:
        pass
    else:
        raise AssertionError("accepted unsupported control")
print("CONTROL_COMPACTION_TYPED_PACKET_GUARDS_PASS 14", flush=True)

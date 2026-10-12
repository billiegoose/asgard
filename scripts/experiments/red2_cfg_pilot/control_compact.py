"""Fuse single-use typed expression copies and remove fall-through jumps."""


def compact(m):
    rows, ops = m["rows"], m["ops"]
    pure = {
        ops[n]
        for n in (
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
        )
        if n in ops
    }
    binary = pure - {ops["copy"], ops["not"]}
    known = pure | {ops[n] for n in ("branch", "jump", "request", "response", "halt")}
    temps = {v for k, v in m["slots"].items() if k.startswith("$temp_")}
    uses, definitions = {}, {}
    predecessors = [set() for _ in rows]
    for pc, row in enumerate(rows):
        op = row["op"]
        assert op in known, "unknown operation needs an effect analysis"
        operands = (
            [row["a"]]
            if op in pure | {ops["branch"]}
            or (op == ops["request"] and row["d"] != m.get("request_sentinel", 15))
            else []
        )
        if op in binary:
            operands.append(row["b"])
        for operand in operands:
            uses[operand] = uses.get(operand, 0) + 1
        if op in pure | {ops["response"]}:
            definitions[row["d"]] = definitions.get(row["d"], 0) + 1
        successors = (
            []
            if op == ops["halt"]
            else [row["yes"], row["no"]]
            if op == ops["branch"]
            else [row["yes"]]
            if op == ops["jump"]
            else [pc + 1]
        )
        for target in successors:
            assert pc < target < len(rows), "only acyclic source control is supported"
            predecessors[target].add(pc)
    entries = set(m["entry_pc"].values())
    removed, replacements = set(), {}
    fused = jumps = 0
    for pc, row in enumerate(rows):
        if pc in removed:
            continue
        if row["op"] == ops["jump"] and row["yes"] == pc + 1:
            removed.add(pc)
            jumps += 1
            continue
        if pc + 1 == len(rows):
            continue
        after = rows[pc + 1]
        if (
            row["op"] in pure
            and row["d"] in temps
            and definitions[row["d"]] == 1
            and uses.get(row["d"]) == 1
            and after["op"] == ops["copy"]
            and after["a"] == row["d"]
            and after["width"] == row["width"]
            and pc + 1 not in entries
            and predecessors[pc + 1] == {pc}
        ):
            replacements[pc] = {**row, "d": after["d"]}
            removed.add(pc + 1)
            fused += 1
    kept = [pc for pc in range(len(rows)) if pc not in removed]
    assert kept[-1] == len(rows) - 1 and rows[-1]["op"] == ops["halt"]
    remap = {}
    next_index = len(kept) - 1
    kept_index = {pc: index for index, pc in enumerate(kept)}
    for pc in range(len(rows) - 1, -1, -1):
        if pc in kept_index:
            next_index = kept_index[pc]
        remap[pc] = next_index
    result = []
    for pc in kept:
        row = replacements.get(pc, rows[pc]).copy()
        if row["op"] in {ops["branch"], ops["jump"]}:
            row["yes"] = remap[row["yes"]]
        if row["op"] == ops["branch"]:
            row["no"] = remap[row["no"]]
        result.append(row)
    before = len(rows)
    rows[:] = result
    m["entry_pc"] = {k: remap[v] for k, v in m["entry_pc"].items()}
    m["control_compaction"] = {
        "rows_before": before,
        "rows_after": len(rows),
        "fused_copies": fused,
        "removed_fallthrough_jumps": jumps,
        "proof": (
            "Same-width pure expression, unique temporary definition/use, "
            "sole copy predecessor; all packet/response effects retained"
        ),
    }

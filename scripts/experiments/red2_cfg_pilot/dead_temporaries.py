"""Drop only dead scratch writes in the acyclic transition CFG."""


def eliminate(m):
    rows, ops = m["rows"], m["ops"]
    pure = {
        "copy",
        "add",
        "sub",
        "mul",
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
        "response",
    }
    assert set(ops) <= pure | {"branch", "jump", "request", "halt"}, (
        "new opcode needs an explicit side-effect classification"
    )
    state = {
        i
        for name, i in m["slots"].items()
        if name.split(".")[0] in m["state_ownership"]
    }
    binary = {
        ops[n]
        for n in (
            "add",
            "sub",
            "mul",
            "and",
            "or",
            "eq",
            "ne",
            "bool_and",
            "bool_or",
            "shr",
            "shl",
            "ge",
        )
        if n in ops
    }
    effects = {ops[n] for n in ("branch", "jump", "request", "halt")}
    live = [set() for _ in rows]
    removed = set()
    for pc in reversed(range(len(rows))):
        r = rows[pc]
        op = r["op"]
        successors = (
            []
            if op == ops["halt"]
            else [r["yes"], r["no"]]
            if op == ops["branch"]
            else [r["yes"]]
            if op == ops["jump"]
            else [pc + 1]
        )
        assert all(pc < s < len(rows) for s in successors)
        after = set().union(*(live[s] for s in successors))
        if op not in effects and r["d"] not in state and r["d"] not in after:
            removed.add(pc)
            live[pc] = after
            continue
        uses = set()
        if op not in {ops[n] for n in ("jump", "response", "halt")} and not (
            op == ops["request"] and r["d"] == m.get("request_sentinel", 15)
        ):
            uses.add(r["a"])
        if op in binary:
            uses.add(r["b"])
        defined = set() if op in effects else {r["d"]}
        live[pc] = uses | (after - defined)
    kept = [i for i in range(len(rows)) if i not in removed]
    mapping = {old: new for new, old in enumerate(kept)}
    for old in reversed(range(len(rows))):
        if old in removed:
            mapping[old] = mapping[old + 1]
    for state_id, pc in m["entry_pc"].items():
        m["entry_pc"][state_id] = mapping[pc]
    for pc in kept:
        r = rows[pc]
        if r["op"] in {ops["branch"], ops["jump"]}:
            r["yes"] = mapping[r["yes"]]
        if r["op"] == ops["branch"]:
            r["no"] = mapping[r["no"]]
    m["dead_temporaries"] = {
        "removed_rows": len(removed),
        "original_rows": len(rows),
        "remaining_rows": len(kept),
        "rule": (
            "Preserve all state writes, requests, branches and halts; "
            "remove only dead temporary writes and their dead operand chains"
        ),
    }
    rows[:] = [rows[i] for i in kept]

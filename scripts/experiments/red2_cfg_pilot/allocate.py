"""Allocate temporary scratch by exact CFG liveness; retain distinct RED2 state."""


def allocate(m):
    rows, ops = m["rows"], m["ops"]
    # Architectural/family fields remain distinct and visible at handoffs.
    state = set(m["state_ownership"])
    fixed = [k for k in m["slots"] if k.split(".")[0] in state]
    constants = [k for k in m["slots"] if k.startswith("$constant_")]
    temporary = [k for k in m["slots"] if k not in fixed and k not in constants]
    temporary_ids = {m["slots"][k] for k in temporary}
    graph = {i: set() for i in temporary_ids}
    live = [set() for _ in rows]
    no_write = {ops[n] for n in ("branch", "jump", "request", "halt")}
    binary = {
        ops[n]
        for n in (
            "add",
            "sub",
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
    for pc in reversed(range(len(rows))):
        r = rows[pc]
        op = r["op"]
        successors = (
            []
            if op == ops["halt"]
            else (
                [r["yes"], r["no"]]
                if op == ops["branch"]
                else [r["yes"]]
                if op == ops["jump"]
                else [pc + 1]
            )
        )
        assert all(pc < s < len(rows) for s in successors)
        after = set().union(*(live[s] for s in successors))
        uses = set()
        if op not in {ops[n] for n in ("jump", "response", "halt")} and not (
            op == ops["request"] and r["d"] == m.get("request_sentinel", 15)
        ):
            uses.add(r["a"])
        if op in binary:
            uses.add(r["b"])
        defined = set() if op in no_write else {r["d"]}
        live[pc] = uses | (after - defined)
        # Sources must coexist; destinations may reuse a dying source because
        # both operands are latched before the single scratch write phase.
        active = live[pc] & temporary_ids
        for a in active:
            graph[a].update(active - {a})
        for d in defined & temporary_ids:
            graph[d].update((after & temporary_ids) - {d})
            for other in (after & temporary_ids) - {d}:
                graph[other].add(d)
    colors = {}
    for i in sorted(temporary_ids, key=lambda i: (-len(graph[i]), i)):
        unavailable = {colors[j] for j in graph[i] if j in colors}
        color = 0
        while color in unavailable:
            color += 1
        colors[i] = color
    color_count = max(colors.values(), default=-1) + 1
    remap = {m["slots"][k]: i for i, k in enumerate(fixed)}
    remap.update({i: len(fixed) + color for i, color in colors.items()})
    writable = len(fixed) + color_count
    remap.update({m["slots"][k]: writable + i for i, k in enumerate(constants)})
    # Check the complete live sets, including immutable operands and state.
    for values in live:
        assert len({remap[i] for i in values}) == len(values)
    for r in rows:
        r["a"] = remap[r["a"]]
        if r["op"] != ops["response"]:
            r["b"] = remap[r["b"]]
        if r["op"] not in no_write:
            r["d"] = remap[r["d"]]
    m["slots"] = {k: remap[i] for k, i in m["slots"].items()}
    m["initial"] = {remap[int(i)]: v for i, v in m["initial"].items()}
    m["writable_words"] = writable
    m["scratch_allocation"] = {
        "method": "CFG liveness, distinct persistent state and immutable constants",
        "original_words": len(remap),
        "allocated_words": writable + len(constants),
        "persistent_words": len(fixed),
        "temporary_colors": color_count,
        "constant_words": len(constants),
        "all_live_sets_disjoint": True,
    }

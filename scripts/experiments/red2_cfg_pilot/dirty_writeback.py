"""Track actual scratch writes and bypass constant shared-state transfers."""

import operator


def constant_writes(manifest):
    """Conservatively propagate immutable values through every entry's CFG.

    Mutable state and responses start unknown. A field qualifies only when
    every reachable write to it produces the same known value. Conditional
    paths that do not write it are handled by the runtime dirty bit.
    """
    slots, rows, ops = manifest["slots"], manifest["rows"], manifest["ops"]
    assert all(0 < row["width"] <= 64 for row in rows)
    roots = {
        slot: name
        for name, slot in slots.items()
        if name.split(".")[0] in manifest["state_ownership"]
    }
    assert len(roots) == sum(
        name.split(".")[0] in manifest["state_ownership"] for name in slots
    )
    initial = {int(slot): value for slot, value in manifest["initial"].items()}
    immutable = {
        slot: int(initial[slot])
        for name, slot in slots.items()
        if name.startswith("$constant_")
    }
    writes = {name: set() for name in roots.values()}
    names = {value: name for name, value in ops.items()}
    starts = sorted(manifest["entry_pc"].values())
    for start, end in zip(starts, [*starts[1:], len(rows)], strict=True):
        incoming = {start: immutable.copy()}
        for pc in range(start, end):
            known = incoming.pop(pc, None)
            if known is None:
                continue
            row = rows[pc]
            name = names[row["op"]]
            a, b = known.get(row["a"]), known.get(row["b"])
            successors = [pc + 1]
            if name == "halt":
                continue
            if name == "jump":
                successors = [row["yes"]]
            elif name == "branch":
                successors = (
                    [row["yes"], row["no"]]
                    if a is None
                    else [row["yes"] if a else row["no"]]
                )
            elif name != "request":
                value = None
                if name == "copy":
                    value = a
                elif name == "not" and a is not None:
                    value = int(not a)
                elif name != "response" and a is not None and b is not None:
                    if name in {"shr", "shl"}:
                        value = 0 if b >= 64 else (a >> b if name == "shr" else a << b)
                    else:
                        value = {
                            "add": operator.add,
                            "sub": operator.sub,
                            "and": operator.and_,
                            "or": operator.or_,
                            "eq": operator.eq,
                            "ne": operator.ne,
                            "ge": operator.ge,
                            "bool_and": lambda x, y: bool(x) and bool(y),
                            "bool_or": lambda x, y: bool(x) or bool(y),
                        }[name](a, b)
                if value is None:
                    known.pop(row["d"], None)
                else:
                    value = int(value) & ((1 << row["width"]) - 1)
                    known[row["d"]] = value
                if row["d"] in roots:
                    writes[roots[row["d"]]].add(value)
            for successor in set(successors):
                assert pc < successor < end
                if successor not in incoming:
                    incoming[successor] = known.copy()
                else:
                    previous = incoming[successor]
                    incoming[successor] = {
                        slot: value
                        for slot, value in previous.items()
                        if slot in known and known[slot] == value
                    }
    return {
        name: next(iter(values))
        for name, values in writes.items()
        if len(values) == 1 and None not in values
    }


def extend_emitter(text, manifest):
    changes = [
        (
            "addr_t = make_uint_t(",
            "scratch_word_t = make_uint_t(65)\naddr_t = make_uint_t(",
        ),
        (
            "scratch_ram, _ = make_ram(uint64_t,",
            "scratch_ram, _ = make_ram(scratch_word_t,",
        ),
        (
            "class output_t(NamedTuple):\n",
            "class output_t(NamedTuple):\n    setup_dirty: uint1_t\n",
        ),
        (
            "        sr.wr_data = result\n",
            "        scratch_result: scratch_word_t = result\n"
            "        scratch_result = scratch_result | 18446744073709551616\n"
            "        sr.wr_data = scratch_result\n",
        ),
        ("        a = so.p0.rd_data\n", "        a = so.p0.rd_data[63:0]\n"),
        ("        b = so.p0.rd_data\n", "        b = so.p0.rd_data[63:0]\n"),
        (
            "setup_data=so.p0.rd_data)",
            "setup_data=so.p0.rd_data[63:0], setup_dirty=so.p0.rd_data[64])",
        ),
    ]
    for old, new in changes:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    manifest["scratch_word_bits"] = 65
    manifest["dirty_writeback"] = {
        "method": "Scratch bit 64 marks actual writes; imports clear the tag",
        "constant_writes": constant_writes(manifest),
    }
    return text

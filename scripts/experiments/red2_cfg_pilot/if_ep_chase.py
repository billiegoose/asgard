"""Target valid and malformed IF pointer-chase paths in extracted controllers."""


def cases(hw):
    fixtures = [
        ("ep-zero", {"lo": 0}),
        ("ep-last-address", {"lo": hw.GRAPH_WORDS - 1}),
        ("ep-out-of-range", {"lo": hw.GRAPH_WORDS}),
        ("ep-negative", {"lo": 1 << 63}),
        ("ep-unsigned-kind", {"kind": hw.DATA_LITERAL_ID}),
        ("ep-float-kind", {"kind": hw.DATA_FLOAT64}),
        ("ep-hop-limit", {"hops": hw.GRAPH_WORDS - 1}),
        ("ep-before-hop-limit", {"hops": hw.GRAPH_WORDS - 2}),
        ("invalid-word", {"valid": 0}),
        ("invalid-current-target", {"target": hw.GRAPH_WORDS}),
        ("high-current-target", {"target": 1 << 63}),
        ("invalid-word-and-target", {"valid": 0, "target": hw.GRAPH_WORDS}),
    ]
    fixtures += [
        (
            "atomic-" + name.lower(),
            {"opcode": getattr(hw, "MOP_" + name), "lo": (1 << 64) - 1},
        )
        for name in ("INT", "FLOAT", "CHAR", "SYM")
    ]
    fixtures += [
        ("defined-symbol", {"opcode": hw.MOP_SYM, "definition_valid": 1}),
        ("closure", {"opcode": hw.MOP_CLOSURE}),
    ]
    fixtures += [
        ("closure-parent-" + str(parent), {"opcode": hw.MOP_CLOSURE, "parent": parent})
        for parent in (0, 1, 2, hw.GRAPH_WORDS - 1, hw.GRAPH_WORDS)
    ]
    fixtures += [
        ("unsupported-" + name.lower(), {"opcode": getattr(hw, "MOP_" + name)})
        for name in ("APP", "LAMBDA", "STRUCT", "UBV")
    ]
    return fixtures


def witness(hw, widths, keys, trial):
    fixtures = cases(hw)
    if trial >= len(fixtures):
        return None
    label, overrides = fixtures[trial]
    params = {
        "lo": 7,
        "opcode": hw.MOP_EP,
        "kind": hw.DATA_SIGNED,
        "valid": 1,
        "definition_valid": 0,
        "target": 4,
        "hops": 0,
        "parent": 20,
        **overrides,
    }
    values = {key: (1 << widths[key]) - 1 for key in keys}
    selected = {
        "microstate": hw.MICRO_JOIN_IF_EP_CHASE,
        "red2_fault": 0,
        "hw_fault": 0,
        "join_ep_chase_target": params["target"],
        "join_ep_hops": params["hops"],
        "join_parent_address": params["parent"],
    }
    assert selected.keys() <= values.keys()
    values.update(selected)
    response = [
        params["lo"],
        (params["valid"] << 26)
        | (params["opcode"] << 21)
        | (params["kind"] << 17)
        | (params["definition_valid"] << 16)
        | 0xBEEF,
        0,
        0,
        0,
    ]
    return values, response, label

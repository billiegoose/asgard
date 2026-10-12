"""Guard branch joins, state writes and observable packets during dead removal."""

import copy

from dead_temporaries import eliminate

ops = {
    n: i
    for i, n in enumerate(
        ("copy", "add", "branch", "jump", "request", "response", "halt")
    )
}


def row(op, a=0, b=0, d=0, yes=0, no=0):
    return dict(op=ops[op], a=a, b=b, d=d, yes=yes, no=no, width=8)


source = {
    "ops": ops,
    "state_ownership": {"result": {}, "condition": {}},
    "slots": {
        "result": 0,
        "condition": 1,
        "$constant_a": 2,
        "$constant_b": 3,
        "$temp_a": 4,
        "$temp_b": 5,
        "$response": 6,
        "$joined": 7,
    },
    "entry_pc": {1: 1},
    "rows": [
        row("halt"),
        row("copy", a=2, d=4),
        row("add", a=4, b=3, d=5),
        row("response", d=6),
        row("branch", a=1, yes=5, no=7),
        row("copy", a=2, d=7),
        row("jump", yes=8),
        row("copy", a=3, d=7),
        row("copy", a=7, d=0),
        row("request", a=0),
        row("request", d=15),
        row("halt"),
    ],
}
candidate = copy.deepcopy(source)
eliminate(candidate)
assert candidate["dead_temporaries"]["removed_rows"] == 3


def execute(m, condition, a, b):
    scratch = [0, condition, a, b, 0, 0, 0, 0]
    pc, requests = m["entry_pc"][1], []
    for _ in range(len(m["rows"])):
        r = m["rows"][pc]
        pc += 1
        op = r["op"]
        if op == ops["halt"]:
            return scratch[0], requests
        if op == ops["branch"]:
            pc = r["yes"] if scratch[r["a"]] else r["no"]
        elif op == ops["jump"]:
            pc = r["yes"]
        elif op == ops["request"]:
            requests.append("accept" if r["d"] == 15 else scratch[r["a"]])
        else:
            scratch[r["d"]] = (
                123
                if op == ops["response"]
                else (scratch[r["a"]] + (scratch[r["b"]] if op == ops["add"] else 0))
                & 255
            )
    raise AssertionError("did not halt")


for condition in (0, 1):
    for a, b in ((0, 255), (19, 71), (255, 255)):
        assert execute(source, condition, a, b) == execute(candidate, condition, a, b)
cyclic = copy.deepcopy(source)
cyclic["rows"][6]["yes"] = 4
try:
    eliminate(cyclic)
except AssertionError:
    pass
else:
    raise AssertionError("accepted a cyclic transition")
print("DEAD_TEMPORARIES_BRANCH_PACKET_PASS 7", flush=True)

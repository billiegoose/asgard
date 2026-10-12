"""Read-only literal metadata packets and source-ordered continuation launches."""

import ast
import copy
import hashlib

STATES = {
    "struct_selector_value_read",
    "struct_selector_result_meta_scan",
    "join_prim_meta_scan",
    "join_special_meta_scan",
}
READ_STATES = STATES - {"struct_selector_value_read"}
EVENTS = {
    "selector_copy_value_init_launch": "struct_selector_value_read",
    "equality_shared_init_launch": "join_prim_meta_scan",
}


def body_sha(bank):
    return hashlib.sha256(
        ast.unparse(ast.Module(body=bank.body, type_ignores=[])).encode()
    ).hexdigest()


def launch_banks(fn):
    records, tails = [], {state: [] for state in STATES}
    for event, state in EVENTS.items():
        handler = next(
            n
            for n in fn.body
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "clock_dispatch_enable and micro_is_" + state
        )
        default = next(
            n
            for n in fn.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == event
        )
        assert isinstance(default.value, ast.Constant) and default.value.value == 0
        writes = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Name)
            and isinstance(n.ctx, ast.Store)
            and n.id == event
        ]
        assert len(writes) == 2
        assert sum(n in list(ast.walk(handler)) for n in writes) == 1
        banks = [
            n
            for n in fn.body
            if isinstance(n, ast.If)
            and isinstance(n.test, ast.BoolOp)
            and isinstance(n.test.op, ast.Or)
            and any(isinstance(t, ast.Name) and t.id == event for t in n.test.values)
        ]
        readers = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == event
        ]
        assert len(banks) == (2 if event == "equality_shared_init_launch" else 1)
        assert len(readers) == len(banks)
        assert all(any(r in list(ast.walk(b.test)) for b in banks) for r in readers)
        for bank in banks:
            records.append(
                {
                    "event": event,
                    "writer_state": state,
                    "consumer_line": bank.lineno,
                    "body_sha256": body_sha(bank),
                }
            )
            tails[state].append(
                ast.copy_location(
                    ast.If(
                        test=ast.Name(id=event, ctx=ast.Load()),
                        body=copy.deepcopy(bank.body),
                        orelse=[],
                    ),
                    bank,
                )
            )
    return records, tails


def configure(tree, fn, types, structs, spec):
    factory = next(
        n.value
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Call)
        and any(
            isinstance(t, ast.Name) and t.id == "literal_meta_ram"
            for t in ast.walk(n.targets[0])
        )
    )
    assert [ast.unparse(a) for a in factory.args] == [
        "red2_literal_meta_t",
        "LITERAL_META_WORDS",
    ]
    assert {k.arg: ast.literal_eval(k.value) for k in factory.keywords} == {
        "ports": ("rw",),
        "read_latency": 1,
    }
    fields = structs["red2_literal_meta_t"]
    assert len(fields) == 9 and all(t.startswith("uint") for t in fields.values())
    types["literal_meta_req.addr"] = "uint6_t"
    types["literal_meta_out.p0.rd_data"] = "red2_literal_meta_t"
    spec = copy.deepcopy(spec)
    spec["banks"].append(("literal_meta", "red2_literal_meta_t"))
    spec["read_only_banks"] = ["literal_meta"]
    spec["requests"].append(
        {
            "name": "literal_meta_addr",
            "key": "literal_meta_req.addr",
            "type": "uint6_t",
            "width": 6,
            "bank": "literal_meta",
        }
    )
    for field, dtype in fields.items():
        spec["responses"].append(
            {
                "name": "literal_meta_read_" + field,
                "key": "literal_meta_out.p0.rd_data." + field,
                "type": dtype,
                "width": int(dtype[4:-2]),
                "bank": "literal_meta",
                "suffix": "." + field,
            }
        )
    source = next(
        n
        for n in fn.body
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "command.op == CMD_LOAD_LITERAL_META"
    )
    write_enables = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and ast.unparse(n.targets[0]) == "literal_meta_req.wr_en"
    ]
    assert len(write_enables) == 2
    assert any(
        n in fn.body and isinstance(n.value, ast.Constant) and n.value.value == 0
        for n in write_enables
    )
    assert len(source.body) == 1 and source.body[0] in write_enables
    assert ast.unparse(source.body[0].value) == "literal_meta_address_in_range"
    arm, requests = source, {}
    for _ in range(3):
        assert len(arm.orelse) == 1 and isinstance(arm.orelse[0], ast.If)
        arm = arm.orelse[0]
        state = ast.unparse(arm.test).removeprefix("micro_is_")
        assert state in READ_STATES and state not in requests
        assert len(arm.body) == 1 and isinstance(arm.body[0], ast.Assign)
        assert ast.unparse(arm.body[0].targets[0]) == "literal_meta_req.addr"
        requests[state] = copy.deepcopy(arm.body)
    assert not arm.orelse and set(requests) == READ_STATES
    records, tails = launch_banks(fn)
    defaults = ast.parse("literal_meta_req.addr = 0").body
    return spec, requests, defaults, records, tails


def remove_legacy(fn, records):
    source = next(
        n
        for n in fn.body
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "command.op == CMD_LOAD_LITERAL_META"
    )
    # Host loading retains its original enable/data; only selected scan-address
    # arms move. The accepted controller packet never drives a write enable.
    source.orelse = []
    for record in records:
        banks = [
            n
            for n in fn.body
            if isinstance(n, ast.If)
            and isinstance(n.test, ast.BoolOp)
            and any(
                isinstance(t, ast.Name) and t.id == record["event"]
                for t in n.test.values
            )
            and body_sha(n) == record["body_sha256"]
        ]
        assert len(banks) == 1
        bank = banks[0]
        bank.test.values = [
            t
            for t in bank.test.values
            if not (isinstance(t, ast.Name) and t.id == record["event"])
        ]

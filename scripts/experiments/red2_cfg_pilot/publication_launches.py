"""Connect publication launch writers and their uniquely triggered reset banks."""

import ast
import copy
import hashlib

STATES = {
    "join_tail_read",
    "join_ep_chase",
    "join_app_scan",
    "join_app_target_read",
    "join_multi_target_read",
}
EVENTS = {"selector_copy_join_init_launch", "promote_shared_init_launch"}


def describe(fn):
    handler = next(
        n
        for n in fn.body
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "clock_dispatch_enable and micro_is_join_tail_read"
    )
    records, statements = [], []
    for bank in fn.body:
        if (
            not isinstance(bank, ast.If)
            or not isinstance(bank.test, ast.BoolOp)
            or not isinstance(bank.test.op, ast.Or)
        ):
            continue
        found = [
            n.id for n in bank.test.values if isinstance(n, ast.Name) and n.id in EVENTS
        ]
        if not found:
            continue
        assert len(found) == 1
        event = found[0]
        writers = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Name)
            and isinstance(n.ctx, ast.Store)
            and n.id == event
        ]
        assert len(writers) == 2
        default = next(
            n
            for n in fn.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == event
        )
        assert isinstance(default.value, ast.Constant) and default.value.value == 0
        assert (
            sum(
                isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Store)
                and n.id == event
                for n in ast.walk(handler)
            )
            == 1
        )
        readers = [
            n
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == event
        ]
        assert len(readers) == 1 and readers[0] in list(ast.walk(bank.test))
        body = ast.unparse(ast.Module(body=bank.body, type_ignores=[]))
        records.append(
            {
                "event": event,
                "writer_state": "MICRO_JOIN_TAIL_READ",
                "consumer_line": bank.lineno,
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "proof": (
                    "One zero default, one selected assertion "
                    "and one source reset-bank reader"
                ),
            }
        )
        statements.append(
            ast.copy_location(
                ast.If(
                    test=ast.Name(id=event, ctx=ast.Load()),
                    body=copy.deepcopy(bank.body),
                    orelse=[],
                ),
                bank,
            )
        )
    assert {r["event"] for r in records} == EVENTS
    return records, [ast.fix_missing_locations(n) for n in statements]


def remove_legacy(fn, records):
    remaining = {r["event"]: r for r in records}
    for bank in fn.body:
        if not isinstance(bank, ast.If) or not isinstance(bank.test, ast.BoolOp):
            continue
        found = [
            n.id
            for n in bank.test.values
            if isinstance(n, ast.Name) and n.id in remaining
        ]
        for event in found:
            body = ast.unparse(ast.Module(body=bank.body, type_ignores=[]))
            assert (
                hashlib.sha256(body.encode()).hexdigest()
                == remaining[event]["body_sha256"]
            )
            bank.test.values = [
                n
                for n in bank.test.values
                if not (isinstance(n, ast.Name) and n.id == event)
            ]
            del remaining[event]
    assert not remaining

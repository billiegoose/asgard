"""Extract core continuations from the shared scalar entry, preserving priority.

The final arithmetic arm remains in legacy hardware. Selection uses the old
active flags, before any continuation clears them. Each admitted continuation
retains the original request packet and source order.
"""

import ast
import copy
import hashlib

STATE = "MICRO_JOIN_SCALAR_LEFT_READ"
FLAG = "micro_is_join_scalar_left_read"
ACTIVE = (
    "equality_continue_active",
    "equality_child_active",
    "equality_launch_active",
    "prim0_y_active",
)
PREDICATE = " or ".join(ACTIVE)


def split(body):
    """Split the pinned four-arm priority chain and its arithmetic fallback."""
    core = copy.deepcopy(body)
    chains = [
        n for n in core if isinstance(n, ast.If) and ast.unparse(n.test) == ACTIVE[0]
    ]
    assert len(chains) == 1
    node = chains[0]
    for flag in ACTIVE:
        assert ast.unparse(node.test) == flag
        if flag != ACTIVE[-1]:
            assert len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If)
            node = node.orelse[0]
    assert node.orelse
    fallback = copy.deepcopy(body)
    index = next(i for i, n in enumerate(fallback) if isinstance(n, ast.If))
    assert ast.unparse(fallback[index].test) == ACTIVE[0]
    fallback[index : index + 1] = copy.deepcopy(node.orelse)
    node.orelse = []
    return core, fallback


def describe(handler, request):
    core, _ = split(handler.body)
    req, _ = split(request)
    assert {
        ast.unparse(n.func)
        for s in core + req
        for n in ast.walk(s)
        if isinstance(n, ast.Call)
    } <= {"red2_word_t", "red2_control_t", "red2_u64_ge"}
    record = {
        "state": STATE,
        "predicate": PREDICATE,
        "priority": list(ACTIVE),
        "handler_sha256": hashlib.sha256(ast.unparse(handler).encode()).hexdigest(),
        "request_sha256": hashlib.sha256(
            ast.unparse(ast.Module(body=request, type_ignores=[])).encode()
        ).hexdigest(),
    }
    return record, req, core


def retain_legacy(fn, record, original_handler):
    assert (
        hashlib.sha256(ast.unparse(original_handler).encode()).hexdigest()
        == record["handler_sha256"]
    )
    _, fallback = split(original_handler.body)
    legacy = copy.deepcopy(original_handler)
    legacy.test = ast.parse(
        f"clock_dispatch_enable and {FLAG} and not ({PREDICATE})", mode="eval"
    ).body
    legacy.body = fallback
    # Original selected handler has been removed. Place the retained fallback
    # before the next dispatch handler, preserving all later reset-bank order.
    position = next(
        i
        for i, n in enumerate(fn.body)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "clock_dispatch_enable and micro_is_u64_div"
    )
    fn.body.insert(position, legacy)
    parents = [
        n
        for n in fn.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "command_is_clock"
    ]
    parent = next(
        n
        for n in parents
        if any(
            isinstance(c, ast.If) and ast.unparse(c.test) == "micro_is_execute"
            for c in n.body
        )
    )
    # Generic removal consumed the selected request arm. Rebuild only its
    # arithmetic fallback from the untouched source packet.
    return parent


def legacy_request(parent, request, record):
    assert (
        hashlib.sha256(
            ast.unparse(ast.Module(body=request, type_ignores=[])).encode()
        ).hexdigest()
        == record["request_sha256"]
    )
    _, fallback = split(request)
    position = next(
        (i for i, n in enumerate(parent.body) if n.lineno > request[0].lineno),
        len(parent.body),
    )
    parent.body.insert(
        position,
        ast.If(
            test=ast.parse(f"{FLAG} and not ({PREDICATE})", mode="eval").body,
            body=fallback,
            orelse=[],
        ),
    )


def retain_sync_fallback(fn):
    arms = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == FLAG
        and any(
            isinstance(x, ast.Name)
            and isinstance(x.ctx, ast.Store)
            and x.id == "scalar_sync_read"
            for x in ast.walk(n)
        )
    ]
    assert len(arms) == 1
    arms[0].test = ast.parse(f"{FLAG} and not ({PREDICATE})", mode="eval").body
    arms[0].body = ast.parse("scalar_sync_read = 1").body

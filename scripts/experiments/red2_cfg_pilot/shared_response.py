"""Share the stream bridge's stable response registers with its microengine.

This is an integrated-controller optimization. The standalone controller keeps
its pulse-response interface and its own capture registers. In the stream top,
the bridge retains the accepted packet until the next request; a second capture
bank in the engine is redundant.
"""

import ast
from collections import Counter

from packets import response_fields


def share(engine, manifest):
    fields = set(response_fields(manifest))
    declarations = {
        n.target.id: n
        for n in engine.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id in fields
    }
    assert set(declarations) == fields
    widths = {}
    for name, node in declarations.items():
        assert node.value is None
        annotation = ast.unparse(node.annotation)
        assert annotation.startswith("Reg[uint") and annotation.endswith("_t]")
        widths[name] = int(annotation.removeprefix("Reg[uint").removesuffix("_t]"))

    phase = next(
        n
        for n in ast.walk(engine)
        if isinstance(n, ast.If) and ast.unparse(n.test) == "incoming_phase == 7"
    )
    assert len(phase.body) == 1
    accept = phase.body[0]
    assert isinstance(accept, ast.If) and ast.unparse(accept.test) == "i.response_valid"
    captures = [
        n
        for n in accept.body
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id in fields
    ]
    assert Counter(n.targets[0].id for n in captures) == Counter(
        dict.fromkeys(fields, 1)
    )
    assert all(ast.unparse(n.value) == "i." + n.targets[0].id for n in captures)
    capture_ids = {id(n) for n in captures}
    accept.body = [n for n in accept.body if id(n) not in capture_ids]
    declaration_ids = {id(n) for n in declarations.values()}
    engine.body = [n for n in engine.body if id(n) not in declaration_ids]

    class Aliases(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in fields:
                assert isinstance(node.ctx, ast.Load), (
                    "unexpected response writer",
                    node.id,
                )
                return ast.copy_location(
                    ast.Attribute(
                        value=ast.Name(id="i", ctx=ast.Load()),
                        attr=node.id,
                        ctx=ast.Load(),
                    ),
                    node,
                )
            return node

    Aliases().visit(engine)
    return {
        "fields": sorted(fields),
        "removed_declared_register_bits": sum(widths.values()),
        "field_widths": widths,
        "scope": (
            "Integrated stream top only; bridge retains response until next request"
        ),
        "standalone_controller_unchanged": True,
    }


def validate_bridge(fn, manifest):
    """Reject adapters that overwrite a retained packet or wire another source."""
    fields = set(response_fields(manifest))
    writers = Counter()

    def inspect(node, guards=()):
        if isinstance(node, ast.If):
            for child in node.body:
                inspect(child, (*guards, ast.unparse(node.test)))
            for child in node.orelse:
                inspect(child, guards)
            return
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("cfg_read_"):
                    field = target.id.removeprefix("cfg_read_")
                    if field in fields:
                        assert "cfg_incoming_mem_phase == 1" in guards
                        writers[field] += 1
        for child in ast.iter_child_nodes(node):
            inspect(child, guards)

    inspect(fn)
    assert writers == Counter(dict.fromkeys(fields, 1)), writers
    packet = next(
        n.value
        for n in fn.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "cfg_i"
    )
    values = {k.arg: ast.unparse(k.value) for k in packet.keywords}
    assert all(values[name] == "cfg_read_" + name for name in fields)
    assert values["response_valid"] == "cfg_incoming_mem_phase == 2"
    assert values["enable"] == "cfg_clock"

    # Every response use must follow an accepted request on all control paths.
    rows, ops = manifest["rows"], manifest["ops"]
    for entry in manifest["entry_pc"].values():
        incoming = {entry: False}
        for pc in range(entry, len(rows)):
            if pc not in incoming:
                continue
            row = rows[pc]
            if row["op"] == ops["response"]:
                assert incoming[pc], ("response precedes request", entry, pc)
            after = incoming[pc] or (
                row["op"] == ops["request"]
                and row["d"] == manifest.get("request_sentinel", 15)
            )
            successors = (
                []
                if row["op"] == ops["halt"]
                else [row["yes"], row["no"]]
                if row["op"] == ops["branch"]
                else [row["yes"]]
                if row["op"] == ops["jump"]
                else [pc + 1]
            )
            for successor in successors:
                assert successor > pc
                incoming[successor] = incoming.get(successor, True) and after

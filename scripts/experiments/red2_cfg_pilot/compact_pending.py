"""Keep only lifecycle payloads in the stream bridge's queued-command bank."""

import ast


def compact(fn):
    lifecycle = next(
        n
        for n in fn.body
        if isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "cfg_lifecycle_input"
    )
    assert ast.unparse(lifecycle.value) == (
        "incoming_command.op == CMD_RESET or incoming_command.op == CMD_LOAD_STATE "
        "or incoming_command.op == CMD_START"
    )
    captures = []

    def inspect(node, guards=()):
        if isinstance(node, ast.If):
            for child in node.body:
                inspect(child, (*guards, ast.unparse(node.test)))
            for child in node.orelse:
                inspect(child, guards)
            return
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "cfg_pending_command"
            for t in node.targets
        ):
            assert len(node.targets) == 1
            assert ast.unparse(node.value) == "incoming_command"
            assert (
                "cfg_lifecycle_input and cfg_incoming_stage != 0 and (not cfg_pending)"
                in guards
            )
            captures.append(node)
        for child in ast.iter_child_nodes(node):
            inspect(child, guards)

    inspect(fn)
    assert len(captures) == 1
    captures[0].value = ast.parse(
        "red2_command_t(op=incoming_command.op, address=incoming_command.address, "
        "word=red2_word_t(lo=0, hi=0), "
        "control=red2_control_t(lo=0, hi=0, tag_hi=0), "
        "value=incoming_command.value, aux=0, state=incoming_command.state)",
        mode="eval",
    ).body
    return {
        "retained_fields": ["op", "address", "value", "state"],
        "zeroed_fields": ["word", "control", "aux"],
        "zeroed_payload_bits": 324,
        "scope": "Queued RESET/LOAD_STATE/START only; immediate commands unchanged",
    }

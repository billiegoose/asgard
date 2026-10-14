"""Preserve source order and shared state guards when extracting RAM requests."""

import ast
import copy

PREFIX = "micro_is_"


def state_alternatives(test):
    """Return state predicates in a pure OR guard, or None for other tests."""
    if isinstance(test, ast.Name) and test.id.startswith(PREFIX):
        return [test.id]
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
        parts = [state_alternatives(value) for value in test.values]
        if all(part is not None for part in parts):
            return list(dict.fromkeys(name for part in parts for name in part))
    return None


def state_name(predicate):
    return "MICRO_" + predicate.removeprefix(PREFIX).upper()


def extract(parent, selected, specialized=()):
    requests = {}
    for node in parent.body:
        if not isinstance(node, ast.If):
            continue
        predicates = state_alternatives(node.test)
        if predicates is None:
            mentioned = {
                state_name(item.id)
                for item in ast.walk(node.test)
                if isinstance(item, ast.Name) and item.id.startswith(PREFIX)
            }
            unsupported = (mentioned & set(selected)) - set(specialized)
            if unsupported:
                raise ValueError(
                    f"request guard needs explicit lowering: {ast.unparse(node.test)}"
                )
            continue
        if node.orelse:
            raise ValueError(
                "state request alternatives cannot silently omit an else arm"
            )
        for predicate in predicates:
            requests.setdefault(predicate.removeprefix(PREFIX), []).extend(
                copy.deepcopy(node.body)
            )
    return requests


def retain_unselected(node, selected):
    """Remove only selected alternatives from a source request guard."""
    if not isinstance(node, ast.If):
        return node
    predicates = state_alternatives(node.test)
    if predicates is None:
        return node
    remaining = [name for name in predicates if state_name(name) not in selected]
    if len(remaining) == len(predicates):
        return node
    if node.orelse:
        raise ValueError("cannot remove a state request with an else arm")
    if not remaining:
        return None
    node = copy.deepcopy(node)
    node.test = (
        ast.Name(id=remaining[0], ctx=ast.Load())
        if len(remaining) == 1
        else ast.BoolOp(
            op=ast.Or(),
            values=[ast.Name(id=name, ctx=ast.Load()) for name in remaining],
        )
    )
    return ast.fix_missing_locations(node)

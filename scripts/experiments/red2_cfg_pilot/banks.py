"""Discover RAM adapter dependencies, including requests outside handlers."""

import ast
from collections import defaultdict


def inspect(c):
    ram_names = {
        n.id
        for node in c.tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "make_ram"
        for n in ast.walk(node.targets[0])
        if isinstance(n, ast.Name) and n.id != "_"
    }
    requests, responses = set(), set()
    for n in c.fn.body:
        if (
            isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call)
            and isinstance(n.value.func, ast.Name)
            and n.value.func.id in ram_names
        ):
            responses |= {x.id for x in n.targets if isinstance(x, ast.Name)}
            requests |= {x.id for x in n.value.args if isinstance(x, ast.Name)}
    requests -= {"memory_req", "control_req"}
    responses -= {"memory_out", "control_out"}

    def flags(node, visited=None):
        visited = set() if visited is None else visited
        result = set()
        for n in ast.walk(node):
            if not isinstance(n, ast.Name):
                continue
            if n.id.startswith("micro_is_"):
                result.add("MICRO_" + n.id.removeprefix("micro_is_").upper())
            elif n.id.startswith("MICRO_"):
                result.add(n.id)
            elif n.id in c.aliases and n.id not in visited:
                visited.add(n.id)
                result |= flags(c.aliases[n.id].value, visited)
        return result

    effects = defaultdict(set)

    def visit(node, conditions):
        if isinstance(node, ast.If):
            conditions = conditions | flags(node.test)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr != "wr_en":
                    continue
                if isinstance(node.value, ast.Constant) and node.value.value == 0:
                    continue
                while isinstance(target, ast.Attribute):
                    target = target.value
                if isinstance(target, ast.Name) and target.id in requests:
                    active = conditions | (flags(node.value) if node.value else set())
                    for state in active:
                        effects[state].add(target.id)
        for child in ast.iter_child_nodes(node):
            visit(child, conditions)

    for n in c.fn.body:
        if isinstance(n, ast.If) and ast.unparse(n.test).startswith(
            "clock_dispatch_enable and micro_is_"
        ):
            continue
        visit(n, set())
    return requests | responses, dict(effects)

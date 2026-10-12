"""Reject extracted same-cycle events unless remaining reads have fresh locals."""

import ast


def unbridged(fn, earliest_write):
    """Each remaining top-level region must define a reused local before use.

    A global zero default is not a fresh definition in a later reset/launch
    region: extracting a handler could remove its event assertion. In contrast,
    reusing a temporary name in a different handler is safe when every read is
    dominated by that handler's own assignment. Reads earlier than every
    extracted write cannot observe an extracted same-cycle update.
    """
    bad = set()

    def uses(node, defined):
        if node is None:
            return
        for n in ast.walk(node):
            if (
                isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Load)
                and n.id in earliest_write
                and n.id not in defined
                and n.lineno >= earliest_write[n.id]
            ):
                bad.add((n.id, n.lineno))

    def block(statements, defined):
        defined = defined.copy()
        for n in statements:
            if isinstance(n, ast.If):
                uses(n.test, defined)
                defined = block(n.body, defined) & block(n.orelse, defined)
            elif isinstance(n, (ast.Assign, ast.AnnAssign)):
                uses(n.value, defined)
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for target in targets:
                    if isinstance(target, ast.Name) and n.value is not None:
                        defined.add(target.id)
                    elif isinstance(target, ast.Attribute):
                        uses(target, defined)
            else:
                uses(n, defined)
        return defined

    for statement in fn.body:
        block([statement], set())
    return sorted(bad)

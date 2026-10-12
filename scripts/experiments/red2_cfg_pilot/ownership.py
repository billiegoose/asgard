"""Prove persistent ownership and derive safe per-entry shared transfers."""

import ast
import copy

LIFECYCLE = {
    "command.op == CMD_RESET or command.op == CMD_LOAD_STATE": False,
    (
        "command.op == CMD_RESET or command.op == CMD_LOAD_STATE or "
        "(command.op == CMD_START and memory_address_in_range)"
    ): True,
}


def root_name(target):
    while isinstance(target, ast.Attribute):
        target = target.value
    return target.id if isinstance(target, ast.Name) else None


def zero(value):
    if isinstance(value, ast.Constant):
        return value.value == 0
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "red2_word_t"
        and not value.args
        and {k.arg for k in value.keywords} == {"lo", "hi"}
        and all(zero(k.value) for k in value.keywords)
    )


def prove_private(fn, m):
    """Only lifecycle-zero writes may remain after original handlers are removed.

    Return a new AST with these private declarations/initializers removed.
    Every other surviving access is a hard exclusion, including request aliases
    and nonselected shared launch/completion banks.
    """
    roots = set(m["state_ownership"])

    def is_zero(value):
        if "lifecycle_structs" not in m:
            return zero(value)
        if isinstance(value, ast.Name):
            return value.id in m["lifecycle_zero_constants"]
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            fields = m["lifecycle_structs"].get(value.func.id)
            return (
                fields is not None
                and not value.args
                and len(value.keywords) == len(fields)
                and {k.arg for k in value.keywords} == set(fields)
                and all(is_zero(k.value) for k in value.keywords)
            )
        return isinstance(value, ast.Constant) and value.value == 0

    allowed = {}
    for statement in fn.body:
        if isinstance(statement, ast.If) and ast.unparse(statement.test) in LIFECYCLE:
            for assignment in statement.body:
                if isinstance(assignment, ast.Assign) and len(assignment.targets) == 1:
                    target = assignment.targets[0]
                    name = root_name(target)
                    if (
                        name in roots
                        and isinstance(target, ast.Name)
                        and is_zero(assignment.value)
                    ):
                        allowed[id(assignment)] = (
                            name,
                            LIFECYCLE[ast.unparse(statement.test)],
                        )
    blocked = set()
    initializers = {}

    def inspect(node):
        if id(node) in allowed:
            name, on_start = allowed[id(node)]
            initializers.setdefault(name, []).append(on_start)
            return
        if isinstance(node, ast.AnnAssign) and ast.unparse(node.annotation).startswith(
            "Reg["
        ):
            if root_name(node.target) in roots:
                assert node.value is None, (
                    "initialized Reg requires explicit lifecycle analysis"
                )
                return
        if isinstance(node, ast.Name) and node.id in roots:
            blocked.add(node.id)
        for child in ast.iter_child_nodes(node):
            inspect(child)

    inspect(fn)
    private = set(initializers) - blocked
    assert private, "no proven private fields"
    # Typed-zero proofs admit duplicate initializers: all values are identical,
    # and START clears their union. Legacy configurations retain the old guard.
    if "lifecycle_structs" not in m:
        assert all(len(initializers[k]) == 1 for k in private)
    result = copy.deepcopy(fn)

    class RemovePrivate(ast.NodeTransformer):
        def visit_AnnAssign(self, node):
            if root_name(node.target) in private:
                assert ast.unparse(node.annotation).startswith("Reg[")
                return None
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if any(root_name(t) in private for t in node.targets):
                assert len(node.targets) == 1 and is_zero(node.value)
                return None
            return self.generic_visit(node)

        def visit_If(self, node):
            self.generic_visit(node)
            if not node.body:
                # Every removed write was proved to be an exact lifecycle-zero
                # initializer. Once its whole bank is private, BRAM lifecycle
                # initialization owns it and the empty pure guard can disappear.
                assert not node.orelse and ast.unparse(node.test) in LIFECYCLE
                return None
            return node

    result = RemovePrivate().visit(result)
    assert not any(
        isinstance(n, ast.Name) and n.id in private for n in ast.walk(result)
    )
    leaves = [k for k in m["slots"] if k.split(".")[0] in private]
    return result, {
        "private_roots": sorted(private),
        "private_fields": leaves,
        "private_bits": sum(m["widths"][k] for k in leaves),
        "initialize_on_start": [
            k for k in leaves if any(initializers[k.split(".")[0]])
        ],
        "proof": (
            "No remaining legacy AST reference after lifecycle-zero writes "
            "and Reg declarations removed"
        ),
    }


def schedules(m, private):
    """Import old values of conditional writes, as well as live-in reads."""
    rows, ops = m["rows"], m["ops"]
    fields = {
        v: k for k, v in m["slots"].items() if k.split(".")[0] in m["state_ownership"]
    }
    binary = {
        ops[n]
        for n in (
            "add",
            "sub",
            "and",
            "or",
            "eq",
            "ne",
            "bool_and",
            "bool_or",
            "shr",
            "shl",
            "ge",
        )
        if n in ops
    }
    no_write = {ops[n] for n in ("branch", "jump", "request", "halt")}
    result = {}
    for state, start in m["entry_pc"].items():
        incoming = {start: set()}
        reads, writes = set(), set()
        for pc in range(start, len(rows)):
            if pc not in incoming:
                continue
            row = rows[pc]
            op = row["op"]
            uses = set()
            if op not in {ops[n] for n in ("jump", "response", "halt")} and not (
                op == ops["request"] and row["d"] == m.get("request_sentinel", 15)
            ):
                uses.add(row["a"])
            if op in binary:
                uses.add(row["b"])
            reads |= (uses - incoming[pc]) & fields.keys()
            defined = set() if op in no_write else {row["d"]}
            writes |= defined & fields.keys()
            after = incoming[pc] | defined
            successors = (
                []
                if op == ops["halt"]
                else [row["yes"], row["no"]]
                if op == ops["branch"]
                else [row["yes"]]
                if op == ops["jump"]
                else [pc + 1]
            )
            for successor in successors:
                assert successor > pc
                incoming[successor] = (
                    incoming[successor] & after
                    if successor in incoming
                    else after.copy()
                )
        imported = {fields[i] for i in reads | writes} - set(private)
        exported = {fields[i] for i in writes} - set(private)
        assert exported <= imported
        result[state] = {
            "import": sorted(imported),
            "export": sorted(exported),
            "read_before_write": sorted(fields[i] for i in reads),
            "may_write": sorted(fields[i] for i in writes),
        }
    return result

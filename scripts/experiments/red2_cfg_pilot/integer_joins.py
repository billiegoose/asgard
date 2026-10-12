"""Specialize JOIN publication to the existing integer arithmetic profile.

Raw FLOAT transport and EVEN? applicability checks retain their original bit
semantics. Pure binary64 unpack/domain helpers inline from their source ASTs;
no floating arithmetic implementation or new numeric approximation is added.
"""

import ast
import copy
import hashlib
import os

STATES = {"join_publish", "join_ep_result_write"}
HELPERS = {"red2_float64_from_bits", "red2_float64_supported"}
FLOAT_FIELDS = {"sign": "uint1_t", "exp": "uint11_t", "man": "uint52_t"}


def inline(fn, argument):
    assert len(fn.args.args) == 1 and not fn.args.defaults
    bindings = {fn.args.args[0].arg: argument}

    class Substitute(ast.NodeTransformer):
        def visit_Name(self, node):
            return copy.deepcopy(bindings.get(node.id, node))

    for statement in fn.body[:-1]:
        assert isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        )
        assert statement.target.id not in bindings
        bindings[statement.target.id] = Substitute().visit(
            copy.deepcopy(statement.value)
        )
    assert isinstance(fn.body[-1], ast.Return)
    return Substitute().visit(copy.deepcopy(fn.body[-1].value))


def configure(tree, structs, floating_source):
    assert os.environ.get("RED2_SYN_FLOAT", "0") == "0"
    floating = ast.parse(floating_source)
    instance = next(
        n
        for n in floating.body
        if isinstance(n, ast.Assign)
        and len(n.targets) == 1
        and ast.unparse(n.targets[0]) == "float64_t"
    )
    assert ast.unparse(instance.value) == "make_float_t(11, 52)"
    factory = next(
        n
        for n in floating.body
        if isinstance(n, ast.FunctionDef) and n.name == "make_float_t"
    )
    aliases = {"uint1_t": "uint1_t"}
    for local, parameter, width in (
        ("exp_t", "exponent_width", 11),
        ("man_t", "mantissa_width", 52),
    ):
        definition = next(
            n
            for n in factory.body
            if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == local
        )
        assert ast.unparse(definition.value) == f"make_uint_t({parameter})"
        aliases[local] = f"uint{width}_t"
    f = next(
        n for n in factory.body if isinstance(n, ast.ClassDef) and n.name == "float_t"
    )
    fields = {
        n.target.id: aliases[ast.unparse(n.annotation)]
        for n in f.body
        if isinstance(n, ast.AnnAssign)
    }
    assert fields == FLOAT_FIELDS
    structs["float64_t"] = fields
    helpers = {
        n.name: n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in HELPERS
    }
    assert helpers.keys() == HELPERS
    for name, fn in helpers.items():
        assert all(
            not isinstance(n, (ast.NamedExpr, ast.Await, ast.Yield))
            for n in ast.walk(fn)
        )
        calls = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        assert calls <= ({"float64_t"} if name.endswith("from_bits") else set())
        # Validate the linear body even before an extraction needs this helper.
        inline(fn, ast.Name(id="argument", ctx=ast.Load()))
    record = {
        "RED2_SYN_FLOAT": 0,
        "states": sorted(STATES),
        "floating_type_source_sha256": hashlib.sha256(
            floating_source.encode()
        ).hexdigest(),
        "source_helpers_sha256": {
            name: hashlib.sha256(ast.unparse(fn).encode()).hexdigest()
            for name, fn in helpers.items()
        },
    }
    return helpers, record


def specialize(body, helpers):
    class Specialize(ast.NodeTransformer):
        def visit_If(self, node):
            if ast.unparse(node.test) == "RED2_SYN_FLOAT":
                return [self.visit(n) for n in node.orelse]
            return self.generic_visit(node)

        def visit_Call(self, node):
            node = self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in helpers:
                assert len(node.args) == 1 and not node.keywords
                return ast.copy_location(
                    inline(helpers[node.func.id], node.args[0]), node
                )
            return node

    result = Specialize().visit(ast.Module(body=copy.deepcopy(body), type_ignores=[]))
    assert not any(
        isinstance(n, ast.Name) and n.id == "RED2_SYN_FLOAT" for n in ast.walk(result)
    )
    assert {
        ast.unparse(n.func) for n in ast.walk(result) if isinstance(n, ast.Call)
    } <= {"float64_t", "red2_word_t"}
    return ast.fix_missing_locations(result).body

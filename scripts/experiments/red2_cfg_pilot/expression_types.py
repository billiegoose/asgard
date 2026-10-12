"""Unsigned expression widths using the pinned enhanced PipelineC type rules."""

import ast
import sys

from paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import pipelinec_toolchain as tc

tc.verify_enhanced_compiler(tc.configured_root())
sys.path.insert(0, str(tc.configured_root() / "src"))
from pypeline import arith_result_type, make_uint_t  # noqa: E402


class ExpressionTypes:
    def __init__(self, constants, leaves, key):
        self.constants = constants
        self.leaves = leaves
        self.key = key

    def infer(self, node):
        """Return (width, plain_constant); signed arithmetic is outside scope."""
        if isinstance(node, ast.Constant):
            assert isinstance(node.value, int) and node.value >= 0
            return max(1, node.value.bit_length()), True
        if isinstance(node, (ast.Name, ast.Attribute)):
            name = self.key(node)
            if name in self.constants:
                value = self.constants[name]
                assert value >= 0
                return max(1, value.bit_length()), True
            fields = self.leaves(name)
            assert len(fields) == 1
            return fields[0][1], False
        if isinstance(node, ast.Subscript):
            hi = (
                self.constant(node.slice.lower)
                if isinstance(node.slice, ast.Slice)
                else self.constant(node.slice)
            )
            lo = (
                self.constant(node.slice.upper)
                if isinstance(node.slice, ast.Slice)
                else hi
            )
            return hi - lo + 1, False
        if isinstance(node, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
            assert not isinstance(node, ast.UnaryOp) or isinstance(node.op, ast.Not)
            return 1, False
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Name) and node.func.id == "red2_u64_ge"
            return 1, False
        if isinstance(node, ast.BinOp):
            lw, lraw = self.infer(node.left)
            rw, rraw = self.infer(node.right)
            if lraw and rraw:
                value = self.constant(node)
                assert value >= 0, "negative constant expression needs signed support"
                return max(1, value.bit_length()), True
            if isinstance(node.op, (ast.Add, ast.Sub)):
                _, _, result = arith_result_type(
                    "add" if isinstance(node.op, ast.Add) else "sub",
                    make_uint_t(lw),
                    make_uint_t(rw),
                )
                name = result._ctype_name
                assert name.startswith("uint")
                return int(name[4:-2]), False
            if isinstance(node.op, (ast.BitAnd, ast.BitOr)):
                # Native reflected bitwise operations retain the typed side;
                # ordinary bitwise operations retain their left operand type.
                return (rw if lraw else lw), False
            if isinstance(node.op, (ast.LShift, ast.RShift)):
                assert not lraw, (
                    "variable shift of an untyped literal needs an explicit type"
                )
                return lw, False
        raise ValueError("Unsupported expression type: " + ast.unparse(node))

    def constant(self, node):
        return eval(
            compile(ast.Expression(node), "<constant>", "eval"),
            {"__builtins__": {}},
            self.constants,
        )

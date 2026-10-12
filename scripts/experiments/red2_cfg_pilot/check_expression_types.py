"""Regress native integer promotion at intermediate expression boundaries."""

import ast

from expression_types import ExpressionTypes
from pypeline import make_uint_t

widths = {"count": 17, "index": 17, "word": 64, "small": 8}


def key(node):
    assert isinstance(node, ast.Name)
    return node.id


types = ExpressionTypes({"GRAPH_WORDS": 256}, lambda k: [(k, widths[k])], key)
cases = {
    "count - 1": 17,
    "count + 1": 18,
    "count + index + 1": 19,
    "count - index": 17,
    "count[16:8]": 9,
    "word & 255": 64,
    "255 | small": 8,
    "word >> 63": 64,
    "GRAPH_WORDS - 1": 8,
    "index == count - 1": 1,
    "count - 1 + 1": 18,
}
for text, expected in cases.items():
    width, _ = types.infer(ast.parse(text, mode="eval").body)
    assert width == expected, (text, width, expected)
count = make_uint_t(17)(0)
index = make_uint_t(17)((1 << 17) - 1)
assert index == count - 1, "native narrow subtraction must wrap before comparison"
assert int(count - 1) == (1 << 17) - 1
assert int(count + index + 1) == 1 << 17
assert int(count - 1 + 1) == 1 << 17
for amount in (63, 64, 65):
    word = make_uint_t(64)(1)
    assert int(word << amount) == (1 << 63 if amount == 63 else 0)
    assert int(word >> amount) == 0
print("EXPRESSION_WIDTH_REGRESSION_PASS", len(cases), flush=True)

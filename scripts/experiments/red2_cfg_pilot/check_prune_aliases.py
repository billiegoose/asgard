"""Regress ownership pruning's side-effect and definition guards."""

import ast

from prune_aliases import prune

cases = [
    ("a: uint1_t = x == 1\nreturn x", {"a"}),
    ("a: uint1_t = x == 1\nb: uint1_t = a\nreturn x", {"a", "b"}),
    ("a: uint1_t = x == 1\nreturn a", set()),
    ("a: uint1_t = effect(x)\nreturn x", set()),
    ("a: uint1_t = x == 1\na = 0\nreturn x", set()),
    ("a: Reg[uint1_t]\nreturn x", set()),
    ("a: uint1_t = (b := x)\nreturn x", set()),
    ("a: uint8_t = x // 0\nreturn x", set()),
    ("a: values_t = [v for v in x]\nreturn x", set()),
]
for body, expected in cases:
    fn = ast.parse(
        "def hardware(x):\n" + "\n".join("    " + line for line in body.splitlines())
    ).body[0]
    assert set(prune(fn)) == expected, body
print("PURE_ALIAS_PRUNING_PASS", len(cases), flush=True)

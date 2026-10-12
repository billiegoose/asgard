"""Reject lost/ambiguous launch consumers and altered source-bank effects."""

import ast
import copy

from publication_launches import describe, remove_legacy

source = """def hardware():
    selector_copy_join_init_launch: uint1_t = 0
    promote_shared_init_launch: uint1_t = 0
    if clock_dispatch_enable and micro_is_join_tail_read:
        selector_copy_join_init_launch = 1
        promote_shared_init_launch = 1
    if reset or load or selector_copy_join_init_launch:
        selector_count = 0
    if reset or load or promote_shared_init_launch:
        promotion_count = 0
"""
fn = ast.parse(source).body[0]
records, banks = describe(fn)
assert [r["event"] for r in records] == [
    "selector_copy_join_init_launch",
    "promote_shared_init_launch",
]
assert [ast.unparse(b.body[0]) for b in banks] == [
    "selector_count = 0",
    "promotion_count = 0",
]
remaining = copy.deepcopy(fn)
remove_legacy(remaining, records)
assert [ast.unparse(n.test) for n in remaining.body[-2:]] == [
    "reset or load",
    "reset or load",
]
for altered in (
    source.replace("uint1_t = 0", "uint1_t = 1", 1),
    source + "    observer = selector_copy_join_init_launch\n",
    source + "    if other:\n        promote_shared_init_launch = 1\n",
    source.replace("        promote_shared_init_launch = 1\n", ""),
):
    try:
        describe(ast.parse(altered).body[0])
    except AssertionError:
        pass
    else:
        raise AssertionError("accepted ambiguous launch semantics")
altered = ast.parse(source.replace("promotion_count = 0", "promotion_count = 1")).body[
    0
]
try:
    remove_legacy(altered, records)
except AssertionError:
    pass
else:
    raise AssertionError("accepted an altered source bank")
print("PUBLICATION_LAUNCH_SOURCE_BANKS_PASS 6", flush=True)

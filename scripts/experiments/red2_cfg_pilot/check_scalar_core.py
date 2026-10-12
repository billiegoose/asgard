"""Check old-flag priority and exact fallback preservation at the split boundary."""

import ast
import itertools

from scalar_core import ACTIVE, split

source = """def original(equality_continue_active, equality_child_active,
             equality_launch_active, prim0_y_active):
    value = 7
    if equality_continue_active:
        value = 10
        equality_continue_active = 0
    elif equality_child_active:
        value = 20
        equality_child_active = 0
    elif equality_launch_active:
        value = 30
        equality_launch_active = 0
    elif prim0_y_active:
        value = 40
        prim0_y_active = 0
    else:
        value = 50
    value = value + 1
    return value
"""
fn = ast.parse(source).body[0]
core, fallback = split(fn.body)
namespace = {}
exec(compile(ast.parse(source), "<original>", "exec"), namespace)
for name, body in (("core", core), ("fallback", fallback)):
    tree = ast.parse(source)
    tree.body[0].name = name
    tree.body[0].body = body
    exec(compile(ast.fix_missing_locations(tree), "<split>", "exec"), namespace)
for flags in itertools.product((0, 1), repeat=4):
    run = namespace["core"] if any(flags) else namespace["fallback"]
    assert run(*flags) == namespace["original"](*flags), flags
for altered in (
    source.replace(ACTIVE[1] + ":", ACTIVE[2] + ":"),
    source.replace("    else:\n        value = 50\n", ""),
):
    try:
        split(ast.parse(altered).body[0].body)
    except AssertionError:
        pass
    else:
        raise AssertionError("accepted changed continuation partition")
print("SCALAR_CORE_PRIORITY_PARTITION_PASS 18", flush=True)

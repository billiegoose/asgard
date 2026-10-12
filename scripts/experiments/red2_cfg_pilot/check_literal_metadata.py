"""Guard multiple reset-bank consumers and preserve host metadata loading."""

import ast
import copy

from literal_metadata import launch_banks, remove_legacy

source = """def hardware():
    selector_copy_value_init_launch: uint1_t = 0
    equality_shared_init_launch: uint1_t = 0
    if clock_dispatch_enable and micro_is_struct_selector_value_read:
        selector_copy_value_init_launch = 1
    if clock_dispatch_enable and micro_is_join_prim_meta_scan:
        equality_shared_init_launch = 1
    if command.op == CMD_LOAD_LITERAL_META:
        literal_meta_req.wr_en = address_valid
    elif micro_is_join_prim_meta_scan:
        literal_meta_req.addr = prim_cursor
    elif micro_is_join_special_meta_scan:
        literal_meta_req.addr = special_cursor
    elif micro_is_struct_selector_result_meta_scan:
        literal_meta_req.addr = selector_cursor
    if reset or load or selector_copy_value_init_launch:
        copy_count = 0
    if reset or load or equality_shared_init_launch:
        phase = 0
    if reset or load or execute_launch or equality_shared_init_launch:
        literal_id = 0
"""
fn = ast.parse(source).body[0]
records, tails = launch_banks(fn)
assert len(records) == 3
assert [ast.unparse(n.body[0]) for n in tails["join_prim_meta_scan"]] == [
    "phase = 0",
    "literal_id = 0",
]
remaining = copy.deepcopy(fn)
remove_legacy(remaining, records)
host = next(
    n
    for n in remaining.body
    if isinstance(n, ast.If)
    and ast.unparse(n.test) == "command.op == CMD_LOAD_LITERAL_META"
)
assert not host.orelse
assert ast.unparse(host.body[0]) == "literal_meta_req.wr_en = address_valid"
assert [ast.unparse(n.test) for n in remaining.body[-3:]] == [
    "reset or load",
    "reset or load",
    "reset or load or execute_launch",
]
for altered in (
    source + "    observer = equality_shared_init_launch\n",
    source + "    if other:\n        equality_shared_init_launch = 1\n",
    source.replace("uint1_t = 0", "uint1_t = 1", 1),
    source.replace(
        " or equality_shared_init_launch:\n        phase = 0", ":\n        phase = 0"
    ),
):
    try:
        launch_banks(ast.parse(altered).body[0])
    except AssertionError:
        pass
    else:
        raise AssertionError("accepted changed metadata launch consumers")
try:
    remove_legacy(ast.parse(source.replace("phase = 0", "phase = 1")).body[0], records)
except AssertionError:
    pass
else:
    raise AssertionError("accepted changed metadata launch bank")
print("LITERAL_METADATA_SOURCE_BANKS_PASS 6", flush=True)

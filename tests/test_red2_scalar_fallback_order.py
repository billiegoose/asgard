import ast
import copy

import pytest
from scripts.experiments.red2_cfg_pilot.scalar_core import describe, retain_legacy

SOURCE = """def machine(clock_dispatch_enable, micro_is_join_scalar_left_read,
        micro_is_u64_div, micro_is_u64_div_finish, reset,
        equality_continue_active=0, equality_child_active=0,
        equality_launch_active=0, prim0_y_active=0):
    value = 0
    command_is_clock = True
    micro_is_execute = False
    if command_is_clock:
        if micro_is_execute:
            value = 99
    if clock_dispatch_enable and micro_is_join_scalar_left_read:
        if equality_continue_active:
            value = 10
        elif equality_child_active:
            value = 20
        elif equality_launch_active:
            value = 30
        elif prim0_y_active:
            value = 40
        else:
            value = 50
    if clock_dispatch_enable and micro_is_u64_div:
        value = 60
    if clock_dispatch_enable and micro_is_u64_div_finish:
        value = 70
    if reset:
        value = 0
    return value
"""


@pytest.mark.parametrize("divider_extracted", [False, True])
def test_retained_arithmetic_keeps_order_before_later_dispatch_and_reset(
    divider_extracted,
):
    tree = ast.parse(SOURCE)
    fn = tree.body[0]
    handler = next(
        n
        for n in fn.body
        if isinstance(n, ast.If)
        and "micro_is_join_scalar_left_read" in ast.unparse(n.test)
    )
    record, _, _ = describe(handler, handler.body)
    fn.body.remove(handler)
    if divider_extracted:
        fn.body = [
            n
            for n in fn.body
            if not (
                isinstance(n, ast.If)
                and ast.unparse(n.test) == "clock_dispatch_enable and micro_is_u64_div"
            )
        ]
    retain_legacy(fn, record, handler)
    namespace = {}
    exec(
        compile(ast.fix_missing_locations(tree), "<retained-fallback>", "exec"),
        namespace,
    )
    machine = namespace["machine"]
    assert machine(True, True, False, False, False) == 50
    assert machine(True, True, False, False, True) == 0
    assert machine(True, True, False, False, False, equality_child_active=1) == 0
    assert machine(False, True, False, False, False) == 0
    assert machine(True, False, False, True, False) == 70
    if not divider_extracted:
        assert machine(True, False, True, False, False) == 60


def test_changed_source_handler_is_rejected_before_reinsertion():
    tree = ast.parse(SOURCE)
    fn = tree.body[0]
    handler = next(
        n
        for n in fn.body
        if isinstance(n, ast.If)
        and "micro_is_join_scalar_left_read" in ast.unparse(n.test)
    )
    record, _, _ = describe(handler, handler.body)
    altered = copy.deepcopy(handler)
    assignment = next(
        n
        for n in ast.walk(altered)
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Constant)
        and n.value.value == 50
    )
    assignment.value = ast.Constant(77)
    with pytest.raises(AssertionError):
        retain_legacy(fn, record, altered)

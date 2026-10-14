"""RAM requests shared by several RED2 states must survive lowering."""

import ast
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "red2_request_arms", ROOT / "scripts/experiments/red2_cfg_pilot/request_arms.py"
)
arms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(arms)


class Bits(int):
    def __sub__(self, other):
        return Bits(int(self) - int(other))

    def __getitem__(self, item):
        return (int(self) >> item.stop) & ((1 << (item.start - item.stop + 1)) - 1)


def execute(body, **values):
    packet = SimpleNamespace(addr=0)
    env = {"control_req": packet, "uint17_t": Bits, **values}
    module = ast.fix_missing_locations(
        ast.Module(body=copy.deepcopy(body), type_ignores=[])
    )
    exec(compile(module, "<request>", "exec"), env)
    return packet.addr


@pytest.mark.parametrize("phase", ["preflight", "rewrite"])
@pytest.mark.parametrize(
    ("operation", "cursor"),
    [("scan", "cursor"), ("target", "target"), ("ep_chase", "ep_target")],
)
def test_structure_request_matches_original_source(phase, operation, cursor):
    source = ast.parse(
        (ROOT / "src/machines/synthesizable_red2_machine/machine.py").read_text()
    )
    predicates = {
        f"micro_is_join_struct_{kind}_{operation}" for kind in ("preflight", "rewrite")
    }
    original = next(
        node
        for node in ast.walk(source)
        if isinstance(node, ast.If)
        and set(arms.state_alternatives(node.test) or []) == predicates
    )
    extracted = arms.extract(ast.Module(body=[original], type_ignores=[]), set())
    inputs = {
        name: name == f"micro_is_join_struct_{phase}_{operation}" for name in predicates
    }
    inputs.update(
        memory_req=SimpleNamespace(addr=0),
        GRAPH_ADDR_BITS=8,
        **{f"join_struct_{cursor}": Bits(247)},
    )
    execute([original], **inputs)
    assert inputs["memory_req"].addr == 247
    inputs["memory_req"].addr = 0
    execute(extracted[f"join_struct_{phase}_{operation}"], **inputs)
    assert inputs["memory_req"].addr == 247


@pytest.mark.parametrize("state", ["true", "false"])
def test_equality_path_request_matches_original_source(state):
    source = ast.parse(
        (ROOT / "src/machines/synthesizable_red2_machine/machine.py").read_text()
    )
    predicates = {
        "micro_is_join_if_true_path_read",
        "micro_is_join_if_false_path_read",
    }
    original = next(
        node
        for node in ast.walk(source)
        if isinstance(node, ast.If)
        and set(arms.state_alternatives(node.test) or []) == predicates
    )
    parent = ast.Module(body=[original], type_ignores=[])
    selected = {"MICRO_JOIN_IF_TRUE_PATH_READ", "MICRO_JOIN_IF_FALSE_PATH_READ"}
    extracted = arms.extract(parent, selected)
    inputs = {
        name: name == f"micro_is_join_if_{state}_path_read" for name in predicates
    }
    inputs["join_if_path_cursor"] = Bits(5)
    inputs["CONTROL_ADDR_BITS"] = 8
    expected = execute([original], **inputs)
    assert expected == 4
    assert execute(extracted[f"join_if_{state}_path_read"], **inputs) == expected
    assert arms.retain_unselected(original, selected) is None


def test_extraction_preserves_multiple_request_blocks_in_source_order():
    parent = ast.parse(
        "if micro_is_a: control_req.addr = 1\n"
        "if micro_is_a or micro_is_b: control_req.addr += 3\n"
        "if micro_is_a: control_req.addr *= 2\n"
    )
    extracted = arms.extract(parent, {"MICRO_A", "MICRO_B"})
    assert (
        execute(extracted["a"])
        == execute(parent.body, micro_is_a=True, micro_is_b=False)
        == 8
    )
    assert (
        execute(extracted["b"])
        == execute(parent.body, micro_is_a=False, micro_is_b=True)
        == 3
    )


def test_partial_extraction_retains_other_state_request():
    original = ast.parse(
        "if micro_is_a or micro_is_b or micro_is_c: control_req.addr = 7"
    ).body[0]
    retained = arms.retain_unselected(original, {"MICRO_A"})
    assert arms.state_alternatives(retained.test) == ["micro_is_b", "micro_is_c"]
    assert execute([retained], micro_is_b=True, micro_is_c=False) == 7
    assert execute([retained], micro_is_b=False, micro_is_c=False) == 0
    assert len(arms.state_alternatives(original.test)) == 3


def test_selected_mixed_guard_requires_explicit_specialization():
    parent = ast.parse("if micro_is_a and phase == 3: control_req.addr = 7")
    with pytest.raises(ValueError, match="explicit lowering"):
        arms.extract(parent, {"MICRO_A"})
    assert arms.extract(parent, {"MICRO_A"}, specialized={"MICRO_A"}) == {}
    assert arms.extract(parent, {"MICRO_B"}) == {}


def test_request_else_cannot_be_silently_discarded():
    parent = ast.parse(
        "if micro_is_a: control_req.addr = 1\nelse: control_req.addr = 2"
    )
    with pytest.raises(ValueError, match="else arm"):
        arms.extract(parent, {"MICRO_A"})
    with pytest.raises(ValueError, match="else arm"):
        arms.retain_unselected(parent.body[0], {"MICRO_A"})

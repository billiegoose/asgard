import ast
import os
from pathlib import Path
import subprocess
import sys


def test_pypeline_stepper_artifact_has_expected_entry_points() -> None:
    source = Path("models/python/pypeline_red2/red2_stepper.py").read_text()
    assert "RED2_ABI_V1 = 1" in source
    assert "def pack_word" in source
    assert "def pack_control_entry" in source
    assert "def red2_step_word" in source
    assert "# PypelineC legacy exploration entry" in source


def test_synthesizable_abi_module_has_no_dynamic_python_state_containers() -> None:
    path = Path("models/python/pypeline_red2/red2_stepper.py")
    tree = ast.parse(path.read_text())
    forbidden = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
    offenders = [node for node in ast.walk(tree) if isinstance(node, forbidden)]
    assert offenders == []


def test_synthesizable_abi_module_does_not_import_python_object_helpers() -> None:
    tree = ast.parse(Path("models/python/pypeline_red2/red2_stepper.py").read_text())
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imports == set()
    assert imported_from == set()


def test_pypeline_readme_names_validation_path_and_fixed_width_contract() -> None:
    text = Path("models/python/pypeline_red2/README.md").read_text()
    assert "PipelineC" in text
    assert "RED2_ABI_V1" in text
    assert "16-bit physical RAM cell addresses" in text
    assert "17-bit environment/frontier path registers" in text
    assert "signed 64-bit integer" in text
    assert "uv run pytest tests/test_pipelinec_vectors.py" in text


def _red2_processor_class() -> ast.ClassDef:
    tree = ast.parse(Path("models/python/pypeline_red2/red2_processor.py").read_text())
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Red2Processor"
    )


def test_task4_publication_uses_fixed_bounded_scratch_not_dynamic_containers() -> None:
    processor = _red2_processor_class()
    required_methods = {
        "_task4_begin",
        "_task4_commit",
        "_task4_push",
        "_task4_mat_append",
        "_task4_start_publication",
        "_task4_copy_clock",
        "_task4_materialization_clock",
        "_task4_publication_clock",
        "_task4_join_clock",
        "_task4_join_restore_and_commit",
        "_task4_var_clock",
        "_task4_app_var_clock",
        "_task4_ep_clock",
        "_task4_if_clock",
        "_task4_fire_primitive",
        "_task4_fire_scalar_primitive",
        "_task4_push_saved_quantum",
        "_task4_pop_saved_quantum",
        "_execute_y",
        "_evaluate_scalar_primitive",
        "_scalar_op",
        "_struct_selector_tag",
        "_struct_selector_offset",
        "_bool_word",
        "_checked_int_result",
        "_is_symbol_value",
        "_task4_enter_subgraph",
        "_task4_clock",
        "_execute_join",
        "_execute_var",
        "_execute_app",
        "_execute_app_var",
        "_execute_ep",
        "_execute_rblock",
        "_execute_rup",
        "_execute_recp",
        "_execute_struct",
        "_task8_struct_clock",
        "_task8_validate_rec",
        "_task8_allocate_environment_word",
        "_task8_allocate_rec",
        "_task8_rblock_clock",
        "_task8_rup_clock",
        "_task8_recp_clock",
        "_task8_reconstruct_clock",
        "_task9_push_graph",
        "_task9_push_equality_frame",
        "_task9_pop_equality_frame",
        "_task9_constant_class",
        "_task9_constants_equal",
        "_task9_append_task_graph",
        "_task9_start_children",
        "_task9_build_child_task",
        "_task9_finish_child_result",
        "_task9_finish_equality",
        "_task9_equality_clock",
        "_task10_reserve_slot",
        "_task10_relinearize_clock",
        "_task10_quantum_clock",
        "_peek_control_path",
        "_subgraph_entry_fault",
        "_enter_subgraph",
    }
    methods = {
        method.name: method
        for method in processor.body
        if isinstance(method, ast.FunctionDef) and method.name in required_methods
    }
    assert methods.keys() == required_methods

    offenders: list[tuple[str, str, int]] = []
    for method in methods.values():
        for node in ast.walk(method):
            if isinstance(
                node,
                (
                    ast.List,
                    ast.Dict,
                    ast.Set,
                    ast.ListComp,
                    ast.DictComp,
                    ast.SetComp,
                    ast.GeneratorExp,
                ),
            ):
                offenders.append((method.name, type(node).__name__, node.lineno))
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"list", "dict", "set"}
            ):
                offenders.append((method.name, f"{node.func.id}()", node.lineno))
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"append", "extend"}
            ):
                offenders.append((method.name, node.func.attr, node.lineno))

    assert offenders == []


def test_task4_processor_has_no_recursive_runtime_graph_walkers() -> None:
    processor = _red2_processor_class()
    offenders: list[tuple[str, str, int]] = []

    for method in processor.body:
        if not isinstance(method, ast.FunctionDef) or method.name == "__init__":
            continue

        for node in ast.walk(method):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.func.attr == method.name
            ):
                offenders.append((method.name, "self-recursion", node.lineno))

        nested = [
            node
            for node in ast.walk(method)
            if isinstance(node, ast.FunctionDef) and node is not method
        ]
        for walker in nested:
            if any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == walker.name
                for node in ast.walk(walker)
            ):
                offenders.append((method.name, walker.name, walker.lineno))

    assert offenders == []


def test_task4_runtime_paths_have_no_data_dependent_python_while_walkers() -> None:
    processor = _red2_processor_class()
    task4_methods = {
        "_task4_copy_clock",
        "_task4_materialization_clock",
        "_task4_publication_clock",
        "_task4_join_clock",
        "_task4_join_restore_and_commit",
        "_task4_var_clock",
        "_task4_app_var_clock",
        "_task4_ep_clock",
        "_task4_if_clock",
        "_task4_fire_primitive",
        "_task4_fire_scalar_primitive",
        "_task4_push_saved_quantum",
        "_task4_pop_saved_quantum",
        "_execute_y",
        "_evaluate_scalar_primitive",
        "_scalar_op",
        "_struct_selector_tag",
        "_struct_selector_offset",
        "_bool_word",
        "_checked_int_result",
        "_is_symbol_value",
        "_task4_enter_subgraph",
        "_task4_clock",
        "_execute_join",
        "_execute_var",
        "_execute_app",
        "_execute_app_var",
        "_execute_ep",
        "_execute_rblock",
        "_execute_rup",
        "_execute_recp",
        "_execute_struct",
        "_task8_struct_clock",
        "_task8_validate_rec",
        "_task8_allocate_environment_word",
        "_task8_allocate_rec",
        "_task8_rblock_clock",
        "_task8_rup_clock",
        "_task8_recp_clock",
        "_task8_reconstruct_clock",
        "_task9_push_graph",
        "_task9_push_equality_frame",
        "_task9_pop_equality_frame",
        "_task9_constant_class",
        "_task9_constants_equal",
        "_task9_append_task_graph",
        "_task9_start_children",
        "_task9_build_child_task",
        "_task9_finish_child_result",
        "_task9_finish_equality",
        "_task9_equality_clock",
        "_task10_reserve_slot",
        "_task10_relinearize_clock",
        "_task10_quantum_clock",
        "_peek_control_path",
        "_subgraph_entry_fault",
        "_enter_subgraph",
    }
    methods = {
        method.name: method
        for method in processor.body
        if isinstance(method, ast.FunctionDef) and method.name in task4_methods
    }
    assert methods.keys() == task4_methods

    offenders = [
        (method.name, node.lineno)
        for method in methods.values()
        for node in ast.walk(method)
        if isinstance(node, ast.While)
    ]
    assert offenders == []


def test_task14_hardware_checker_pins_real_frontend_and_persistent_processor() -> None:
    text = Path("scripts/check_pypeline_red2.py").read_text()
    assert "171c52b3f1411f632a07ccfc3dbfb177efa901cd" in text
    assert 'PROCESSOR_SOURCE = Path("models/python/pypeline_red2/red2_pypeline.py")' in text
    assert "legacy red2_step_word" in text
    assert "--no_synth" in text
    assert "PY_TO_LOGIC.PARSE_FILE" not in text
    assert "TRIM_COLLAPSE_LOGIC" not in text
    assert "red2_processor_top_*.vhd" in text
    assert "--comb" in text
    assert "Skipping synthesis" in text
    assert "check_pypeline_red2_sim.py" in text
    assert "native Pypeline RED2 parity failed" in text


def test_task14_explicit_gate_hard_fails_when_frontend_is_hidden() -> None:
    env = os.environ.copy()
    env.pop("PIPELINEC_ROOT", None)
    env["PATH"] = ""
    result = subprocess.run(
        [sys.executable, "scripts/check_pypeline_red2.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "pypeline-red2-check: missing PipelineC/Pypeline frontend; "
        "set PIPELINEC_ROOT to a checkout at "
        "171c52b3f1411f632a07ccfc3dbfb177efa901cd or put pypelinec/pipelinec on PATH"
    )


def test_task14_mise_exposes_explicit_non_skipping_hardware_gate() -> None:
    text = Path(".mise.toml").read_text()
    assert "[tasks.pypeline-red2-check]" in text
    assert "scripts/check_pypeline_red2.py" in text
    assert "setuptools" in text
    assert "pyrtl==0.11.3" in text


def test_task14_real_pypeline_top_has_persistent_hardware_state_contract() -> None:
    source = Path("models/python/pypeline_red2/red2_pypeline.py").read_text()
    assert "@MAIN(25.0)" in source
    assert "def red2_processor_top" in source
    assert "make_ram(" in source
    assert "class red2_word_t(NamedTuple)" in source
    assert "class red2_control_t(NamedTuple)" in source
    assert "RED2_PYPELINE_SEMANTICS_COMPLETE = 0" in source
    assert "red2_step_word" not in source
    assert "Red2Processor(" not in source


def test_task14_microstate_dispatch_stays_flat_for_pipelinec() -> None:
    path = Path("models/python/pypeline_red2/red2_pypeline.py")
    tree = ast.parse(path.read_text())
    top = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "red2_processor_top"
    )

    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(top):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    long_dispatch_chains: list[tuple[int, int]] = []
    for node in ast.walk(top):
        if not isinstance(node, ast.If) or node.col_offset != 8:
            continue
        parent = parents.get(node)
        if (
            isinstance(parent, ast.If)
            and len(parent.orelse) == 1
            and parent.orelse[0] is node
        ):
            continue

        count = 1
        cursor = node
        while len(cursor.orelse) == 1 and isinstance(cursor.orelse[0], ast.If):
            cursor = cursor.orelse[0]
            count += 1
        if count >= 40:
            long_dispatch_chains.append((node.lineno, count))

    assert long_dispatch_chains == []
    source = path.read_text()
    assert "micro_is_commit_entry: uint1_t = microstate == MICRO_COMMIT" in source
    assert "clock_dispatch_handled: uint1_t = 0" in source
    assert source.count("clock_dispatch_handled = 1") == 117


def test_task14_closure_code_validation_keeps_mixed_width_predicates_split() -> None:
    """PipelineC 171c52b collides helper names for the compound mixed-width form."""

    text = Path("models/python/pypeline_red2/red2_pypeline.py").read_text()
    assert (
        "if not equality_child_left_code_valid or "
        "equality_child_left_code_opcode != MOP_NONE:"
    ) not in text
    assert (
        "if not equality_child_right_code_valid or "
        "equality_child_right_code_opcode != MOP_NONE:"
    ) not in text
    for side in ("left", "right"):
        assert (
            f"equality_child_{side}_code_is_none: uint1_t = "
            f"equality_child_{side}_code_opcode == MOP_NONE"
        ) in text
        assert (
            f"equality_child_{side}_code_bad: uint1_t = "
            f"equality_child_{side}_code_valid == 0"
        ) in text
        assert (
            f"equality_child_{side}_code_bad = equality_child_{side}_code_bad or "
            f"equality_child_{side}_code_is_none == 0"
        ) in text


def test_task14_recursive_lambda_metadata_checks_remain_split_for_pipelinec() -> None:
    """PipelineC 171c52b must not lower mixed-width != comparisons at one bool site."""

    text = Path("models/python/pypeline_red2/red2_pypeline.py").read_text()
    forbidden = (
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "join_true_literal_id != 0",
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "join_false_literal_id != 0",
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "join_equal_if_literal_id != 0",
    )
    for compound in forbidden:
        assert compound not in text

    for name, source in (
        ("star", "join_equal_star_literal_id"),
        ("true", "join_true_literal_id"),
        ("false", "join_false_literal_id"),
        ("if", "join_equal_if_literal_id"),
    ):
        assert (
            f"equality_child_lambda_has_{name}: uint1_t = {source} != 0"
        ) in text

    assert (
        "equality_child_lambda_meta_ok: uint1_t = "
        "equality_child_lambda_has_star and equality_child_lambda_has_true"
    ) in text
    assert (
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "equality_child_lambda_has_false"
    ) in text
    assert (
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "equality_child_lambda_has_if"
    ) in text

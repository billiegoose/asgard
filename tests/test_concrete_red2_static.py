import ast
from pathlib import Path


def test_concrete_red2_abi_has_expected_entry_points() -> None:
    source = Path("src/machines/concrete_red2_machine/abi.py").read_text()
    assert "RED2_ABI_V1 = 1" in source
    assert "def pack_word" in source
    assert "def pack_control_entry" in source
    assert "def red2_step_word" in source
    assert "# Legacy 32-bit word-level exploration entry" in source


def test_synthesizable_abi_module_has_no_dynamic_python_state_containers() -> None:
    path = Path("src/machines/concrete_red2_machine/abi.py")
    tree = ast.parse(path.read_text())
    forbidden = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
    offenders = [node for node in ast.walk(tree) if isinstance(node, forbidden)]
    assert offenders == []


def test_synthesizable_abi_module_does_not_import_python_object_helpers() -> None:
    tree = ast.parse(Path("src/machines/concrete_red2_machine/abi.py").read_text())
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


def test_concrete_red2_readme_names_validation_path_and_fixed_width_contract() -> None:
    text = Path("src/machines/concrete_red2_machine/README.md").read_text()
    assert "PipelineC" in text
    assert "RED2_ABI_V1" in text
    assert "16-bit physical RAM cell addresses" in text
    assert "17-bit environment/frontier path registers" in text
    assert "signed 64-bit integer" in text
    assert "uv run pytest tests/test_pipelinec_vectors.py" in text


def _red2_processor_class() -> ast.ClassDef:
    tree = ast.parse(Path("src/machines/concrete_red2_machine/machine.py").read_text())
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ConcreteRED2Machine"
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

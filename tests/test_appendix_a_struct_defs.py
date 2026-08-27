from thor_spec.golden import run_source


def test_tree_struct_definition_installs_appendix_a_helpers() -> None:
    source = """
    tree |= label subtrees
    tree-label == tree-label
    (tree-label (make-tree 7 []))
    """
    assert run_source(source, model="thor", quantum=80) == "7"
    assert run_source(source, model="red2", quantum=80) == "7"


def test_tree_subtrees_accessor_returns_lazy_list() -> None:
    source = """
    tree |= label subtrees
    (tree-subtrees (make-tree 1 [2 3]))
    """
    assert run_source(source, model="thor", quantum=80) == "[2 3]"
    assert run_source(source, model="red2", quantum=80) == "[2 3]"


def test_generated_struct_helpers_use_declared_case_only() -> None:
    canonical = """
    tree |= label subtrees
    (make-tree 1 [])
    """
    alternate = """
    tree |= label subtrees
    (MAKE-TREE 1 NIL)
    """

    assert run_source(canonical, model="thor", quantum=80) == "{tree 1 NIL}"
    assert run_source(canonical, model="red2", quantum=80) == "{tree 1 NIL}"
    assert run_source(alternate, model="thor", quantum=80) == "(MAKE-TREE 1 NIL)"
    assert run_source(alternate, model="red2", quantum=80) == "(MAKE-TREE 1 NIL)"

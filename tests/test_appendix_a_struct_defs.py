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

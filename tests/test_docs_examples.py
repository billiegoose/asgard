from pathlib import Path


def test_traceability_doc_names_models_and_thesis_chapters() -> None:
    text = Path("docs/thor-red2-prototype.md").read_text()
    assert "Chapter 3" in text
    assert "Chapter 4" in text
    assert "THOR interpreter" in text
    assert "RED2 machine" in text
    assert "PypelineC" in text
    assert "faithful research prototype" in text


def test_readme_mentions_both_models() -> None:
    text = Path("README.md").read_text()
    assert "--model thor" in text
    assert "--model red2" in text


def test_readme_links_primitive_reference() -> None:
    text = Path("README.md").read_text()
    assert "docs/thor-primitives.md" in text
    primitive_reference = Path("docs/thor-primitives.md").read_text()
    assert "Current Primitives" in primitive_reference
    assert "Future Primitive Candidates" in primitive_reference
    assert "Simulator IO Actions" in primitive_reference
    assert "UART-RX" in primitive_reference
    assert "UART-TX" in primitive_reference


def test_readme_links_red2_bytecode_reference() -> None:
    text = Path("README.md").read_text()
    assert "docs/red2-bytecode.md" in text
    bytecode_reference = Path("docs/red2-bytecode.md").read_text()
    assert "RED2 Bytecode Format" in bytecode_reference
    assert "Rust/WASM VM" in bytecode_reference
    assert "wasmtime --dir /tmp" in bytecode_reference


def test_top_level_examples_are_canonical() -> None:
    readme = Path("README.md").read_text()
    traceability = Path("docs/thor-red2-prototype.md").read_text()
    caesar = Path("examples/uart-caesar-plus4.thor").read_text()

    assert "examples/uart-caesar-plus4.thor" in readme
    assert "tools/vscode-thor" in traceability
    assert "vscode-thor/examples/uart-caesar-plus4.thor" not in readme
    assert "rot-upper ==" in caesar


def test_hangman_example_documents_utility_sections() -> None:
    readme = Path("README.md").read_text()
    hangman = Path("examples/hangman.thor").read_text()

    assert "examples/hangman.thor" in readme
    for section in [
        "; --- constants ---",
        "; --- UART text utilities ---",
        "; --- Hangman rendering ---",
        "; --- game loop ---",
    ]:
        assert section in hangman

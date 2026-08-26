import json
from pathlib import Path
from typing import Any, cast


def load_json(path: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(Path(path).read_text()))


def test_vscode_manifest_declares_thor_language_and_grammar() -> None:
    package = load_json("vscode-thor/package.json")
    contributes = package["contributes"]
    assert package["name"] == "thor-syntax"
    assert contributes["languages"][0]["id"] == "thor"
    assert ".thor" in contributes["languages"][0]["extensions"]
    assert contributes["grammars"][0]["scopeName"] == "source.thor"


def test_textmate_grammar_contains_core_patterns() -> None:
    grammar = load_json("vscode-thor/syntaxes/thor.tmLanguage.json")
    text = json.dumps(grammar)
    for token in [
        "comment.line.semicolon.thor",
        "keyword.control.thor",
        "constant.numeric.thor",
        "storage.type.function.thor",
        "entity.name.function.definition.thor",
    ]:
        assert token in text


def test_examples_cover_fibonacci_and_appendix_a_forms() -> None:
    fib = Path("vscode-thor/examples/fibonacci.thor").read_text()
    sample = Path("vscode-thor/examples/appendix-a-sample.thor").read_text()
    assert "fib ==" in fib
    assert "tree |= label subtrees" in sample
    assert "LETREC" in fib.upper()


def test_extension_docs_include_local_installation_and_release_notes() -> None:
    readme = Path("vscode-thor/README.md").read_text()
    changelog = Path("vscode-thor/CHANGELOG.md").read_text()
    assert "code --install-extension" in readme
    assert ".thor" in readme
    assert "TextMate" in readme
    assert "0.1.0" in changelog

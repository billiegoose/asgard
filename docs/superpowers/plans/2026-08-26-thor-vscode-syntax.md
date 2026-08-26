# THOR VS Code Syntax Highlighting Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local VS Code-compatible syntax highlighting extension for THOR `.thor` files.

**Architecture:** Create a standalone `vscode-thor/` extension folder with TextMate grammar JSON, language configuration, package metadata, sample THOR files, and static tests. Keep it independent from interpreter internals so it can evolve/publish separately later.

**Tech Stack:** VS Code extension manifest JSON, TextMate grammar JSON, pytest static validation, Python stdlib JSON parsing.

**Spec:** Current THOR source syntax in `src/thor_spec/parser.py`; examples in `tests/fixtures/appendix_a/*.thor`; VS Code TextMate grammar contribution conventions.

## Global Constraints

- Do not add Node/npm dependencies for default verification.
- Do not require VS Code to be installed for pytest validation.
- Keep extension local/unpublished; no marketplace publishing steps.
- Grammar must recognize `.thor` files and `source.thor` scope.
- Use examples copied or derived from existing THOR fixtures.

**Acceptance:** suite — static pytest validation of JSON manifests/grammar plus examples verifies this plan.

---

### Task 1: VS Code Extension Skeleton and Grammar

**Type:** implementation
**Depends-on:** none

**Files:**
- Create: `vscode-thor/package.json`
- Create: `vscode-thor/language-configuration.json`
- Create: `vscode-thor/syntaxes/thor.tmLanguage.json`
- Create: `vscode-thor/examples/fibonacci.thor`
- Create: `vscode-thor/examples/appendix-a-sample.thor`
- Create: `tests/test_vscode_thor_extension.py`
- Modify: `docs/thor-red2-prototype.md`

**Interfaces:**
- Consumes: `.thor` syntax conventions from parser and fixtures.
- Produces: VS Code language id `thor`, file extension `.thor`, TextMate scope `source.thor`.

- [ ] **Step 1: Write failing static tests**

Create `tests/test_vscode_thor_extension.py`:

```python
import json
from pathlib import Path


def load_json(path: str) -> dict[str, object]:
    return json.loads(Path(path).read_text())


def test_vscode_manifest_declares_thor_language_and_grammar() -> None:
    package = load_json("vscode-thor/package.json")
    contributes = package["contributes"]  # type: ignore[index]
    assert package["name"] == "thor-syntax"
    assert contributes["languages"][0]["id"] == "thor"  # type: ignore[index]
    assert ".thor" in contributes["languages"][0]["extensions"]  # type: ignore[index]
    assert contributes["grammars"][0]["scopeName"] == "source.thor"  # type: ignore[index]


def test_textmate_grammar_contains_core_patterns() -> None:
    grammar = load_json("vscode-thor/syntaxes/thor.tmLanguage.json")
    text = json.dumps(grammar)
    for token in ["comment.line.semicolon.thor", "keyword.control.thor", "constant.numeric.thor", "storage.type.function.thor", "entity.name.function.definition.thor"]:
        assert token in text


def test_examples_cover_fibonacci_and_appendix_a_forms() -> None:
    fib = Path("vscode-thor/examples/fibonacci.thor").read_text()
    sample = Path("vscode-thor/examples/appendix-a-sample.thor").read_text()
    assert "fib ==" in fib
    assert "tree |= label subtrees" in sample
    assert "LETREC" in fib.upper()
```

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_vscode_thor_extension.py -v`
Expected: FAIL because extension files do not exist.

- [ ] **Step 3: Create extension files**

Create:

- `package.json` with `engines.vscode`, `contributes.languages`, `contributes.grammars`, and no runtime activation.
- `language-configuration.json` with semicolon comments, bracket pairs for `()`, `{}`, `[]`, and auto-closing pairs.
- `thor.tmLanguage.json` patterns for semicolon comments, definitions `==`, struct defs `|=`, lambda/let/letrec/if/Y keywords, numeric constants, character constants `#\\x`, booleans/NIL, primitives, symbols, list/struct punctuation.
- Example files for Fibonacci and Appendix A tree/list sample.
- Docs note pointing to `vscode-thor/`.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_vscode_thor_extension.py -v`
Expected: PASS.

- [ ] **Step 5: Full static verification**

Run: `uv run pytest tests/test_vscode_thor_extension.py && uv run ruff check tests/test_vscode_thor_extension.py && uv run mypy tests/test_vscode_thor_extension.py`
Expected: PASS.

---

### Task 2: Extension Documentation and Packaging Smoke

**Type:** implementation
**Depends-on:** 1

**Files:**
- Create: `vscode-thor/README.md`
- Create: `vscode-thor/CHANGELOG.md`
- Modify: `tests/test_vscode_thor_extension.py`

**Interfaces:**
- Consumes: extension skeleton from Task 1.
- Produces: local installation instructions and optional packaging note.

- [ ] **Step 1: Add failing docs tests**

Extend `tests/test_vscode_thor_extension.py` to assert `vscode-thor/README.md` includes `code --install-extension`, `.thor`, and `TextMate`, and `CHANGELOG.md` includes `0.1.0`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_vscode_thor_extension.py -v`
Expected: FAIL before docs exist.

- [ ] **Step 3: Add README and changelog**

Document local development: open `vscode-thor/` in VS Code Extension Development Host or package with `vsce package` if `vsce` is installed. Make clear npm/vsce are optional and not part of default tests.

- [ ] **Step 4: Verify GREEN**

Run: `uv run pytest tests/test_vscode_thor_extension.py -v`
Expected: PASS.

---

### Task 3: Final Syntax Highlighter Gate

**Type:** gate
**Depends-on:** 1, 2

**Files:**
- Test: `vscode-thor/`
- Test: `tests/test_vscode_thor_extension.py`

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces: verified local VS Code syntax extension.

- [ ] **Step 1: Run extension tests**

Run: `uv run pytest tests/test_vscode_thor_extension.py -v`
Expected: PASS.

- [ ] **Step 2: Run repo checks**

Run: `uv run pytest && uv run ruff check . && uv run mypy src tests`
Expected: PASS.

---

## Operator smoke

- do: open `vscode-thor/` in VS Code and press F5 to launch an Extension Development Host.
- see: `.thor` examples open with THOR syntax highlighting.

- do: inspect `vscode-thor/syntaxes/thor.tmLanguage.json`.
- see: grammar scope is `source.thor` and package manifest maps `.thor` to language id `thor`.

import json
from pathlib import Path


def test_traceability_doc_names_models_and_thesis_chapters() -> None:
    text = Path("docs/thor-red2-prototype.md").read_text()
    assert "Chapter 3" in text
    assert "Chapter 4" in text
    assert "THOR interpreter" in text
    assert "RED2 machine" in text
    assert "PypelineC" in text
    assert "faithful research prototype" in text


def test_readme_mentions_direct_python_commands() -> None:
    text = Path("README.md").read_text()
    assert "uv run thor --expr" in text
    assert "uv run red2 --expr" in text
    assert "uv run compile --expr" in text
    assert "uv run thor-spec" not in text


def test_red2_bytecode_doc_mentions_direct_compile_command() -> None:
    text = Path("docs/red2-bytecode.md").read_text()
    assert "uv run compile --expr" in text
    assert "uv run thor-spec" not in text


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


def test_breakout_example_documents_terminal_game_sections() -> None:
    breakout = Path("examples/breakout.thor").read_text()

    for section in [
        "; --- constants ---",
        "; --- terminal rendering ---",
        "; --- input decoding ---",
        "; --- game physics ---",
        "; --- game loop ---",
    ]:
        assert section in breakout
    assert "CLOCK" in breakout
    assert "ESC [2J" in breakout
    assert "20x12" in breakout


def test_docs_describe_clock_and_breakout() -> None:
    readme = Path("README.md").read_text()
    primitives = Path("docs/thor-primitives.md").read_text()

    assert "mise run thor examples/breakout.thor --clock" in readme
    assert "mise run red2 examples/breakout.thor --clock" in readme
    assert "CLOCK" in primitives
    assert "Unix timestamp" in primitives
    assert "latest-value clock" in primitives


def test_docs_describe_rust_wasm_clock_and_breakout() -> None:
    readme = Path("README.md").read_text()
    primitives = Path("docs/thor-primitives.md").read_text()
    bytecode = Path("docs/red2-bytecode.md").read_text()
    examples = Path("examples/README.md").read_text()

    assert "mise run rust examples/breakout.thor --clock" in readme
    assert "mise run wasm examples/breakout.thor --clock" in readme
    assert "Rust/Wasm runners support `--clock <path>`" in primitives
    assert "--clock /tmp/asgard-clock" in bytecode
    assert "examples/media/breakout-wasm.cast" in examples


def test_wasm_breakout_cast_is_committed_asciicast_v2() -> None:
    cast = Path("examples/media/breakout-wasm.cast")
    header = json.loads(cast.read_text().splitlines()[0])

    assert header["version"] == 2
    assert header["title"] == "Asgard Breakout WASM"


def test_readme_embeds_latest_breakout_recording() -> None:
    readme = Path("README.md").read_text()
    embed = (
        "[![Asgard Breakout asciicast]"
        "(https://asciinema.org/a/oaQSOF9foLO34D6v.svg)]"
        "(https://asciinema.org/a/oaQSOF9foLO34D6v)"
    )

    assert embed in readme


def test_examples_readme_embeds_breakout_recording() -> None:
    readme = Path("examples/README.md").read_text()
    embed = (
        "[![Asgard Breakout asciicast]"
        "(https://asciinema.org/a/oaQSOF9foLO34D6v.svg)]"
        "(https://asciinema.org/a/oaQSOF9foLO34D6v)"
    )

    assert "mise run generate-video breakout" in readme
    assert "examples/media/breakout.cast" in readme
    assert embed in readme


def test_python_engine_benchmark_doc_describes_workloads_and_checksums() -> None:
    text = Path("docs/python-engine-benchmarks.md").read_text()
    for name, expected in (
        ("tak", "15"),
        ("list", "300"),
        ("struct", "300"),
        ("game", "8"),
    ):
        assert f"`{name}`" in text
        assert f"`{expected}`" in text
    assert "Recursive application" in text
    assert "PAIR/list allocation" in text
    assert "user-defined `STRUCT` allocation" in text
    assert "Appendix-A GAME" in text


def test_python_engine_benchmark_doc_states_methodology_contract() -> None:
    text = Path("docs/python-engine-benchmarks.md").read_text()
    assert "untimed parity preflight" in text
    assert "backend-specific setup happen outside the timed region" in text
    assert "translated before timing" in text
    assert "compiled and loaded before timing" in text
    assert "times only `MuredMachine.run()`" in text
    assert "Result reconstruction and `to_source` rendering happen after the timer stops" in text
    assert "Warmups" in text and "excluded from statistics" in text
    assert "median measured time" in text
    assert "no successful partial CSV" in text
    assert "benchmark-breakout" in text
    assert "subprocesses" in text

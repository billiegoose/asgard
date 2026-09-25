import json
from pathlib import Path


def _asciinema_embed(alt_text: str, url: str) -> str:
    return f"[![{alt_text}]({url}.svg)]({url})"


def test_traceability_doc_names_models_and_thesis_chapters() -> None:
    text = Path("docs/thor-red2-prototype.md").read_text()
    assert "Chapter 3" in text
    assert "Chapter 4" in text
    assert "THOR interpreter" in text
    assert "RED2 machine" in text
    assert "PipelineC/Pypeline" in text
    assert "faithful research prototype" in text


def test_readme_mentions_direct_python_commands() -> None:
    text = Path("README.md").read_text()
    assert "uv run thor --expr" in text
    assert "uv run abs --expr" in text
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


def test_pong_example_documents_terminal_game_sections() -> None:
    pong = Path("examples/pong.thor").read_text()

    for section in [
        "; --- constants ---",
        "; --- terminal rendering ---",
        "; --- input decoding ---",
        "; --- game physics ---",
        "; --- game loop ---",
    ]:
        assert section in pong
    assert "CLOCK" in pong
    assert "UART-RX" in pong
    assert "UART-TX-BYTES" in pong
    assert "20x12" in pong


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


def test_docs_describe_red2_owned_io_boundary() -> None:
    prototype = Path("docs/thor-red2-prototype.md").read_text()
    primitives = Path("docs/thor-primitives.md").read_text()

    assert "one persistent `AbstractRED2Machine`" in prototype
    assert "returns a `MuredHostCall`" in prototype
    assert "loading replacement machines" in prototype
    assert "every successful host dispatch resets the quantum" in prototype
    assert "1,048,576 graph/environment words" in prototype
    for action in ("UART-RX", "UART-TX", "UART-TX-BYTES", "CLOCK"):
        assert action in primitives
    assert "native `AbstractRED2Machine` suspension points" in primitives
    assert "same machine resumes without rebuilding" in primitives
    assert "`LEDS` and" in primitives
    assert "`TICKS` remain THOR-host" in primitives
    assert "stdout for simulated UART output" in primitives
    assert "`--verbose`" in primitives
    assert "Unix timestamp" in primitives
    assert "latest-value" in primitives
    assert "`quantum-exhausted` recharge event" in primitives


def test_docs_describe_clock_and_breakout() -> None:
    readme = Path("README.md").read_text()
    primitives = Path("docs/thor-primitives.md").read_text()

    assert "mise run thor examples/breakout.thor --clock" in readme
    assert "mise run abs examples/breakout.thor --clock" in readme
    assert "CLOCK" in primitives
    assert "Unix timestamp" in primitives
    assert "latest-value clock" in primitives


def test_readme_embeds_latest_breakout_recording() -> None:
    readme = Path("README.md").read_text()
    embed = _asciinema_embed(
        "Asgard Breakout asciicast",
        "https://asciinema.org/a/ZA2OrmB0Mc9aAdfq",
    )

    assert embed in readme


def test_examples_readme_embeds_latest_recordings() -> None:
    readme = Path("examples/README.md").read_text()
    breakout_embed = _asciinema_embed(
        "Asgard Breakout asciicast",
        "https://asciinema.org/a/ZA2OrmB0Mc9aAdfq",
    )
    pong_embed = _asciinema_embed(
        "Asgard Pong asciicast",
        "https://asciinema.org/a/4O27VEiw9i3E2gjy",
    )

    assert "mise run generate-video breakout" in readme
    assert "examples/media/breakout.cast" in readme
    assert breakout_embed in readme
    assert pong_embed in readme


def test_canonical_benchmark_doc_describes_workloads_and_checksums() -> None:
    text = Path("benchmarks.md").read_text()
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
    assert "user-defined STRUCT allocation" in text
    assert "Appendix-A GAME" in text


def test_canonical_benchmark_doc_states_methodology_contract() -> None:
    text = Path("benchmarks.md").read_text()
    assert "mise run benchmark" in text
    assert "untimed parity preflight" in text
    assert "backend-specific setup happen outside the timed region" in text
    assert "translated before timing" in text
    assert "compiled and loaded before timing" in text
    assert "times only `AbstractRED2Machine.run()`" in text
    assert (
        "Result reconstruction and `to_source` rendering happen after the timer stops"
        in text
    )
    assert "Warmups" in text and "excluded from statistics" in text
    assert "Median measured time" in text
    assert "not directly comparable instruction counts" in text
    assert "End-to-end Breakout backend benchmark" in text
    assert "subprocesses" in text
    assert "temporary `q = 0` states" in text
    assert "Default-capacity acceptance checks" in text
    assert "benchmark-python" in text
    assert "benchmark-breakout" in text


def test_superseded_benchmark_docs_are_removed() -> None:
    assert not Path("docs/python-engine-benchmarks.md").exists()
    assert not Path("docs/breakout-benchmarks.md").exists()

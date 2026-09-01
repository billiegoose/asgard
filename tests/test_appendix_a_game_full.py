from pathlib import Path

from thor_engine.golden import run_source


def fixture_source_without_benchmark() -> str:
    source = Path("tests/fixtures/appendix_a/game_full.thor").read_text()
    return source.rsplit("game-benchmark", maxsplit=1)[0]


def assert_parity(source: str, expected: str, quantum: int = 30000) -> None:
    assert run_source(source, model="thor", quantum=quantum) == expected
    assert run_source(source, model="red2", quantum=quantum) == expected


def test_game_full_fixture_matches_between_thor_and_red2() -> None:
    source = Path("tests/fixtures/appendix_a/game_full.thor").read_text()
    thor = run_source(source, model="thor", quantum=30000)
    red2 = run_source(source, model="red2", quantum=30000)
    assert thor == red2
    assert thor.lstrip("-").replace(".", "", 1).isdigit()


def test_game_full_move_generator_and_helpers_match_between_models() -> None:
    source = fixture_source_without_benchmark()
    assert_parity(
        f"{source}\n(moves empty-board)",
        "[[O E E E E E E E E] [E O E E E E E E E] "
        "[E E O E E E E E E] [E E E O E E E E E] "
        "[E E E E O E E E E] [E E E E E O E E E] "
        "[E E E E E E O E E] [E E E E E E E O E] "
        "[E E E E E E E E O]]",
    )
    assert_parity(f"{source}\n(reverse [1 2 3])", "[3 2 1]")


def test_game_full_tree_runtime_helpers_match_between_models() -> None:
    source = fixture_source_without_benchmark()
    assert_parity(
        f"{source}\n"
        "no-moves == (lambda (board) [])\n"
        "(tree-label (reptree no-moves empty-board))",
        "[E E E E E E E E E]",
    )
    assert_parity(
        f"{source}\n"
        "small-tree == (make-tree [E] [(make-tree [O] [])])\n"
        "(tree-label (maptree static (prune 0 small-tree)))",
        "1",
    )

import pytest
from pytest import CaptureFixture

from red2_engine.cli import main as red2_main


@pytest.mark.parametrize(
    ("source", "quantum", "expected"),
    [
        ("((LAMBDA (x) x) 42)", 10, "42\n"),
        ("1.5", 10, "1.5\n"),
        ("#\\a", 10, "#\\a\n"),
        ("FOO", 10, "FOO\n"),
        ("(+ 2 3)", 20, "5\n"),
        ("(AND)", 20, "TRUE\n"),
        ("(OR)", 20, "FALSE\n"),
        ("(AND TRUE FALSE (BAD BAD))", 20, "FALSE\n"),
        ("(OR FALSE TRUE (BAD BAD))", 20, "TRUE\n"),
        ("{PAIR 1 2}", 10, "[1 | 2]\n"),
        ("({PAIR 1 2} (LAMBDA (a b) a))", 10, "1\n"),
        ("(LETREC ((x 7)) x)", 1, "7\n"),
        (
            "(LETREC ((x [1 | y]) (y [2 | x])) x)",
            1,
            "[1 | (LETREC ((x [1 | y]) (y [2 | x])) y)]\n",
        ),
    ],
)
def test_red2_cli_runs_faithful_expression_corpus_by_default(
    source: str,
    quantum: int,
    expected: str,
    capsys: CaptureFixture[str],
) -> None:
    assert red2_main(["--quantum", str(quantum), "--expr", source]) == 0
    captured = capsys.readouterr()
    assert captured.out == expected
    assert captured.err == ""


def test_red2_cli_runs_top_level_definition(capsys: CaptureFixture[str]) -> None:
    source = "inc == (LAMBDA (x) (+ x 1))\n(inc 41)"

    assert red2_main(["--quantum", "20", "--expr", source]) == 0

    captured = capsys.readouterr()
    assert captured.out == "42\n"
    assert captured.err == ""


def test_red2_cli_runs_cross_definition_reference(capsys: CaptureFixture[str]) -> None:
    source = "one == 1\ninc == (LAMBDA (x) (+ x one))\n(inc 41)"

    assert red2_main(["--quantum", "20", "--expr", source]) == 0

    captured = capsys.readouterr()
    assert captured.out == "42\n"
    assert captured.err == ""


def test_red2_cli_projects_lazy_atomic_struct_field(
    capsys: CaptureFixture[str],
) -> None:
    source = "tree |= label subtrees\n(tree-label (make-tree (+ 3 4) []))"

    assert red2_main(["--quantum", "100", "--expr", source]) == 0

    captured = capsys.readouterr()
    assert captured.out == "7\n"
    assert captured.err == ""


def test_red2_cli_projects_lazy_structured_struct_field(
    capsys: CaptureFixture[str],
) -> None:
    source = (
        "tree |= label subtrees\n"
        "(tree-subtrees (make-tree 7 ((LAMBDA (z) [z 2]) 1)))"
    )

    assert red2_main(["--quantum", "100", "--expr", source]) == 0

    captured = capsys.readouterr()
    assert captured.out == "[1 2]\n"
    assert captured.err == ""


def test_red2_cli_user_definition_overrides_generated_bare_struct_accessor(
    capsys: CaptureFixture[str],
) -> None:
    source = (
        "tree |= label subtrees\n"
        "label == (LAMBDA (x) 99)\n"
        "(label (make-tree 7 []))"
    )

    assert red2_main(["--quantum", "100", "--expr", source]) == 0

    captured = capsys.readouterr()
    assert captured.out == "99\n"
    assert captured.err == ""

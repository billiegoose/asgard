from __future__ import annotations

from pathlib import Path

from thor_spec.golden import run_source
from thor_spec.lockstep import compare_prefixes


def test_golden_examples_match_between_thor_and_red2() -> None:
    source = Path("tests/golden/thor_examples.thor").read_text()
    cases = [
        line
        for line in source.splitlines()
        if line.strip() and not line.startswith("#")
    ]
    for case in cases:
        thor = run_source(case, model="thor", quantum=40)
        red2 = run_source(case, model="red2", quantum=40)
        assert red2 == thor, case


def test_simple_cases_match_at_every_prefix_quantum() -> None:
    for source in [
        "(+ 2 3)",
        "((LAMBDA (X) X) 42)",
        "(IF TRUE (+ 1 2) (BAD BAD))",
    ]:
        result = compare_prefixes(source, max_quantum=10)
        assert result.first_mismatch is None, source


def test_fibonacci_example_reports_first_prefix_mismatch() -> None:
    source = Path("vscode-thor/examples/fibonacci.thor").read_text()
    result = compare_prefixes(source, max_quantum=75)

    assert result.first_mismatch is not None
    assert result.first_mismatch.quantum == 3
    assert result.snapshots[75].thor == "(+ 3 (+ 2 (+ 1 2)))"
    assert result.snapshots[75].red2 == "(+ 3 (+ 2 (+ 1 2)))"

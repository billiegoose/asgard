from __future__ import annotations

from pathlib import Path

from thor_spec.golden import run_source


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

from thor_spec.golden import run_source


def both(source: str, quantum: int = 50) -> tuple[str, str]:
    return (
        run_source(source, model="thor", quantum=quantum),
        run_source(source, model="red2", quantum=quantum),
    )


def test_appendix_a_numeric_primitives_match() -> None:
    cases = {
        "(1+ 4)": "5",
        "(minus 5)": "-5",
        "(abs (minus 7))": "7",
        "(floor (/ 7 2))": "3",
        "(ceiling (/ 7 2))": "4",
        "(expt 2 5)": "32",
        "(max 3 9)": "9",
        "(min 3 9)": "3",
        "(even? 8)": "TRUE",
    }
    for source, expected in cases.items():
        assert both(source) == (expected, expected)

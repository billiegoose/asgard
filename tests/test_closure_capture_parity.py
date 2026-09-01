from thor_engine.golden import run_source


def assert_parity(source: str, expected: str, quantum: int = 1000) -> None:
    assert run_source(source, model="thor", quantum=quantum) == expected
    assert run_source(source, model="red2", quantum=quantum) == expected


def test_nested_lambda_keeps_outer_binding_in_both_models() -> None:
    source = """
    f == (lambda (a b c) (lambda (x) b))
    ((f 1 2 3) 9)
    """
    assert_parity(source, "2")


def test_local_letrec_keeps_surrounding_lambda_bindings_in_thor() -> None:
    source = """
    h == (lambda (n)
      (letrec ((term (lambda (i)
                       (if (= i n) i (term (1+ i))))))
        (term 0)))
    (h 2)
    """
    assert_parity(source, "2")

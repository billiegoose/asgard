from thor_spec.golden import run_source


def test_red2_partial_lambda_application_does_not_print_pnp() -> None:
    output = run_source("((LAMBDA (X) X) 42)", model="red2", quantum=0)
    assert "PNP" not in output
    assert "LAMBDA" in output
    assert "42" in output


def test_red2_partial_recursive_definition_does_not_print_pnp() -> None:
    source = """
    fib == (lambda (n)
      (if (< n 2)
          n
          (+ (fib (1- n)) (fib (1- (1- n))))))
    (fib 3)
    """
    output = run_source(source, model="red2", quantum=2)
    assert "PNP" not in output

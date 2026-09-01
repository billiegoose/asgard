from thor_engine.golden import run_source


def test_recursive_top_level_factorial_definition_matches_thor() -> None:
    source = """
    fact == (lambda (n) (if (= n 0) 1 (* n (fact (1- n)))))
    (fact 5)
    """
    assert run_source(source, model="thor", quantum=500) == "120"
    assert run_source(source, model="red2", quantum=500) == "120"


def test_recursive_top_level_fibonacci_definition_matches_thor() -> None:
    source = """
    fib == (lambda (n)
      (if (< n 2)
          n
          (+ (fib (1- n)) (fib (1- (1- n))))))
    (fib 7)
    """
    assert run_source(source, model="thor", quantum=2000) == "13"
    assert run_source(source, model="red2", quantum=2000) == "13"


def test_y_combinator_fibonacci_still_matches() -> None:
    source = """
    ((Y (lambda (fib n)
       (if (< n 2)
           n
           (+ (fib (1- n)) (fib (1- (1- n))))))) 6)
    """
    assert run_source(source, model="thor", quantum=2000) == "8"
    assert run_source(source, model="red2", quantum=2000) == "8"

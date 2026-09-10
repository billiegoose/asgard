import pytest

from thor_engine.golden import run_source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("(EQUAL? 1 1)", "TRUE"),
        ("(EQUAL? 1 2)", "FALSE"),
        ("(EQUAL? #\\a #\\a)", "TRUE"),
        ("(EQUAL? SAME SAME)", "TRUE"),
        ("(EQUAL? LEFT RIGHT)", "FALSE"),
    ],
)
def test_structural_equality_preserves_atomic_cases(source: str, expected: str) -> None:
    assert run_source(source, model="red2", quantum=20) == expected


def test_structural_equality_runs_after_strict_operand_reduction() -> None:
    source = "(EQUAL? ((LAMBDA (x) x) 1) ((LAMBDA (y) y) 1))"

    assert run_source(source, model="red2", quantum=3) == "TRUE"
    assert run_source(source, model="thor", quantum=3) == "TRUE"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("(EQUAL? (LAMBDA (x) x) (LAMBDA (y) y))", "TRUE"),
        ("(EQUAL? (LAMBDA (x) x) (LAMBDA (y) 1))", "FALSE"),
        ("(EQUAL? (LAMBDA (x y) x) (LAMBDA (a b) a))", "TRUE"),
        ("(EQUAL? (LAMBDA (x y) x) (LAMBDA (a b) b))", "FALSE"),
    ],
)
def test_structural_equality_compares_lambdas_alpha_equivalently(
    source: str,
    expected: str,
) -> None:
    assert run_source(source, model="thor", quantum=20) == expected
    assert run_source(source, model="red2", quantum=20) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            """pair |= left right
(EQUAL? (make-pair 1 2) (make-pair 1 2))""",
            "TRUE",
        ),
        (
            """pair |= left right
(EQUAL? (make-pair 1 2) (make-pair 1 3))""",
            "FALSE",
        ),
        (
            """pair |= left right
other |= value
(EQUAL? (make-pair 1 2) (make-other 1))""",
            "FALSE",
        ),
    ],
)
def test_structural_equality_compares_lazy_structures(
    source: str,
    expected: str,
) -> None:
    assert run_source(source, model="thor", quantum=20) == expected
    assert run_source(source, model="red2", quantum=20) == expected


def test_structural_equality_can_decide_before_demanding_later_lazy_field() -> None:
    source = """pair |= left right
(EQUAL? (make-pair 1 (BAD BAD)) (make-pair 2 (BAD BAD)))"""

    assert run_source(source, model="thor", quantum=20) == "FALSE"
    assert run_source(source, model="red2", quantum=20) == "FALSE"


@pytest.mark.parametrize(
    "source",
    [
        "(EQUAL? (LAMBDA (x) x) (LAMBDA (y) y))",
        """pair |= left right
(EQUAL? (make-pair 1 2) (make-pair 1 2))""",
    ],
)
def test_zero_quantum_structural_equality_is_public_equal_residual(source: str) -> None:
    expected = run_source(source, model="thor", quantum=0)

    assert expected.startswith("(EQUAL?")
    assert run_source(source, model="red2", quantum=0) == expected


@pytest.mark.parametrize("quantum", [0, 1, 8])
def test_structural_equality_under_unapplied_lambda_remains_publicly_stuck(
    quantum: int,
) -> None:
    source = "(LAMBDA (x) (EQUAL? x 1))"

    expected = run_source(source, model="thor", quantum=quantum)
    assert expected == "(LAMBDA (x) (EQUAL? x 1))"
    assert run_source(source, model="red2", quantum=quantum) == expected


def test_structural_equality_matches_shared_closure_identity() -> None:
    from red2_engine.mured import MuredMachine, MuredOpcode, Word, _EqualityTask

    machine = MuredMachine.load(
        (Word(MuredOpcode.INT, 0, True),), quantum=1, memory_words=32
    )
    state = machine.state
    state.memory[5] = Word(MuredOpcode.CLOSURE, 20, True)
    state.memory[6] = Word(None, 24)
    state.memory[7] = Word(MuredOpcode.CLOSURE, 20, True)
    state.memory[8] = Word(None, 24)
    state.memory[9] = Word(MuredOpcode.CLOSURE, 21, True)
    state.memory[10] = Word(None, 24)

    assert machine._equality_step(_EqualityTask(5, 7, 0, False)) == (True, ())
    assert machine._equality_step(_EqualityTask(5, 9, 0, False)) == (False, ())


def test_structural_equality_leaves_unequal_ubvs_stuck_like_repaired_c() -> None:
    from red2_engine.mured import MuredMachine, MuredOpcode, Word, _EqualityTask

    machine = MuredMachine.load(
        (Word(MuredOpcode.INT, 0, True),), quantum=1, memory_words=32
    )
    state = machine.state
    state.memory[5] = Word(MuredOpcode.UBV, 2, True)
    state.memory[6] = Word(MuredOpcode.UBV, 2, True)
    state.memory[7] = Word(MuredOpcode.UBV, 1, True)

    assert machine._equality_step(_EqualityTask(5, 6, 0, False)) == (True, ())
    assert machine._equality_step(_EqualityTask(5, 7, 0, False)) == (None, ())


def test_structural_equality_rejects_unsupported_internal_tags() -> None:
    from red2_engine.mured import (
        IllegalTransition,
        MuredMachine,
        MuredOpcode,
        Word,
        _EqualityTask,
    )

    machine = MuredMachine.load(
        (Word(MuredOpcode.INT, 0, True),), quantum=1, memory_words=32
    )
    machine.state.memory[5] = Word(MuredOpcode.STOP, None, True)
    machine.state.memory[6] = Word(MuredOpcode.STOP, None, True)

    with pytest.raises(IllegalTransition, match="unsupported EQUAL\\? node opcode"):
        machine._equality_step(_EqualityTask(5, 6, 0, False))


def test_structural_equality_result_compacts_before_enclosing_if() -> None:
    cases = [
        ("(IF (EQUAL? (F 1 2) (F 1 2)) 7 9)", "7"),
        ("(IF (EQUAL? (F 1 2) (F 1 3)) 7 9)", "9"),
    ]

    for source, expected in cases:
        assert run_source(source, model="thor", quantum=20) == expected
        assert run_source(source, model="red2", quantum=20) == expected


def test_structural_equality_rejects_application_arity_mismatch() -> None:
    source = "(EQUAL? (F 1) (F 1 2))"

    assert run_source(source, model="thor", quantum=20) == "FALSE"
    assert run_source(source, model="red2", quantum=20) == "FALSE"


def test_structural_equality_free_variable_tristate_matches_hilton() -> None:
    from red2_engine.mured import MuredMachine, MuredOpcode, Word, _EqualityTask

    machine = MuredMachine.load(
        (Word(MuredOpcode.INT, 0, True),), quantum=1, memory_words=32
    )
    state = machine.state
    state.memory[5] = Word(MuredOpcode.VAR, 3, True)
    state.memory[6] = Word(MuredOpcode.VAR, 3, True)
    state.memory[7] = Word(MuredOpcode.VAR, 4, True)
    state.memory[8] = Word(MuredOpcode.VAR, 0, True)

    assert machine._equality_step(_EqualityTask(5, 6, 2, False)) == (True, ())
    assert machine._equality_step(_EqualityTask(8, 5, 2, False)) == (False, ())
    assert machine._equality_step(_EqualityTask(5, 7, 2, False)) == (None, ())

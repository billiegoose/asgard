import pytest

from pypeline_red2.red2_processor import (
    PRIM0_ROLE_IF,
    PRIM0_ROLE_Y,
    SCALAR_OP_ADD,
    Red2Processor,
)
from red2_engine.mured import MuredMachine
from red2_engine.pipelinec_vectors import RED2ABICodec
from thor_compile.red2 import load_faithful_machine
from thor_lang.normalization import normalize_expr
from thor_lang.parser import parse_expr


def _processor(machine: MuredMachine, codec: RED2ABICodec) -> Red2Processor:
    encoded = codec.encode_state(machine.state)
    if_id = codec.literal_id("IF")
    y_id = codec.literal_id("Y")
    role_image = [0] * (max(if_id, y_id) + 1)
    role_image[if_id] = PRIM0_ROLE_IF
    role_image[y_id] = PRIM0_ROLE_Y

    selectors = dict(machine.struct_selectors)
    selectors["CAR"] = ("PAIR", 2)
    selectors["CDR"] = ("PAIR", 1)
    selector_ids = [codec.literal_id(name) for name in selectors]
    selector_limit = max(selector_ids, default=0)
    selector_tags = [0] * (selector_limit + 1)
    selector_offsets = [0] * (selector_limit + 1)
    for name, (tag, offset) in selectors.items():
        literal_id = codec.literal_id(name)
        selector_tags[literal_id] = codec.literal_id(tag)
        selector_offsets[literal_id] = offset

    add_id = codec.literal_id("+")
    scalar_ops = [0] * (add_id + 1)
    scalar_ops[add_id] = SCALAR_OP_ADD

    return Red2Processor(
        encoded,
        scalar_ops=tuple(scalar_ops),
        prim0_roles=tuple(role_image),
        true_literal_id=codec.literal_id("TRUE"),
        false_literal_id=codec.literal_id("FALSE"),
        nil_literal_id=codec.literal_id("NIL"),
        if_reconstruct_literal_id=codec.literal_id("__IF_RECONSTRUCT__"),
        struct_selector_tags=tuple(selector_tags),
        struct_selector_offsets=tuple(selector_offsets),
        struct_selector_result_literal_id=codec.literal_id("__STRUCT_SELECTOR_RESULT__"),
        cons_literal_id=codec.literal_id("CONS"),
        pair_literal_id=codec.literal_id("PAIR"),
        equality_literal_id=codec.literal_id("EQUAL?"),
        equal_star_literal_id=codec.literal_id("__EQUAL_STAR__"),
        equal_if_literal_id=codec.literal_id("__EQUAL_IF__"),
        equality_continue_literal_id=codec.literal_id("__EQUALITY_CONTINUE__"),
        equal_stuck_literal_id=codec.literal_id("__EQUAL_STUCK__"),
    )


def _assert_program_commits_match(source: str, quantum: int) -> None:
    expr = normalize_expr(parse_expr(source))
    machine = load_faithful_machine(
        expr,
        quantum=quantum,
        memory_words=128,
        control_words=32,
    )
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    commits = 0
    while not machine.state.halted:
        assert commits < 256, (source, quantum, "Python machine did not halt")
        machine.step()
        assert processor.run_to_commit(), (
            source,
            quantum,
            commits,
            processor.fault,
        )
        assert processor.checkpoint() == codec.encode_state(machine.state), (
            source,
            quantum,
            commits,
        )
        commits += 1

    assert processor.halted


@pytest.mark.parametrize(
    "source",
    [
        "(IF TRUE 7 (BAD BAD))",
        "(IF FALSE (BAD BAD) 9)",
        "(AND FALSE (BAD BAD))",
        "(OR TRUE (BAD BAD))",
        "(Y (LAMBDA (self) 7))",
    ],
)
@pytest.mark.parametrize("quantum", range(0, 7))
def test_lazy_program_q_prefix_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(CAR {PAIR (+ 2 3) (BAD BAD)})", 8),
        ("(CDR {PAIR (BAD BAD) (+ 3 4)})", 8),
        ("(CAR (CONS 1 [2 3]))", 12),
        ("(CDR (CONS 1 [2 3]))", 12),
        ("(CAR {PAIR {PAIR 1 2} (BAD BAD)})", 8),
        ("(CAR {PAIR (FOO {PAIR 1 2}) (BAD BAD)})", 8),
    ],
)
def test_struct_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(LETREC ((x 7)) x)", 1),
        ("(LETREC ((x 7)) x)", 0),
        ("(LETREC ((x y) (y 9)) x)", 2),
        ("(LETREC ((f (LAMBDA (n) n))) (f 1))", 2),
        ("(LETREC ((x [1 | y]) (y [2 | x])) x)", 1),
    ],
)
def test_recursive_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(EQUAL? 1 1)", 1),
        ("(EQUAL? 1 2)", 1),
        ("(EQUAL? #\\a #\\a)", 1),
        ("(EQUAL? SAME SAME)", 1),
        ("(EQUAL? LEFT RIGHT)", 1),
        ("(EQUAL? 1 1)", 0),
    ],
)
def test_equality_atomic_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)


@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(EQUAL? (LAMBDA (x) x) (LAMBDA (y) y))", 20),
        ("(EQUAL? (LAMBDA (x) x) (LAMBDA (y) 1))", 20),
        ("(EQUAL? (LAMBDA (x y) x) (LAMBDA (a b) a))", 20),
        ("(EQUAL? (LAMBDA (x y) x) (LAMBDA (a b) b))", 20),
        ("(EQUAL? (F 1 2) (F 1 2))", 20),
        ("(EQUAL? (F 1 2) (F 1 3))", 20),
        ("(EQUAL? (F 1) (F 1 2))", 20),
        ("(EQUAL? {PAIR 1 2} {PAIR 1 2})", 20),
        ("(EQUAL? {PAIR 1 2} {PAIR 1 3})", 20),
        ("(EQUAL? {PAIR 1 (BAD BAD)} {PAIR 2 (BAD BAD)})", 20),
    ],
)
def test_equality_compound_program_committed_checkpoints_match_python(
    source: str,
    quantum: int,
) -> None:
    _assert_program_commits_match(source, quantum)

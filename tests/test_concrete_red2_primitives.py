import pytest

from abstract_red2_machine.machine import (
    AbstractRED2Machine,
    AbstractRED2MachineState,
    Direction,
    MuredOpcode,
    Word,
    _SavedDefinitionPath,
)
from concrete_red2_machine import abi
from concrete_red2_machine.machine import (
    PRIM0_ROLE_IF,
    PRIM0_ROLE_IO_SEQUENCE,
    RED2_PRIM_SEQ_V1,
    RED2_SCALARS_V1,
    RED2_FLOAT_V1,
    SCALAR_OP_ABS,
    SCALAR_OP_ADD,
    SCALAR_OP_CEILING,
    SCALAR_OP_CHAR_P,
    SCALAR_OP_DEC,
    SCALAR_OP_DIV,
    SCALAR_OP_EQ,
    SCALAR_OP_EVEN,
    SCALAR_OP_EXPT,
    SCALAR_OP_FLOAT_P,
    SCALAR_OP_FLOOR,
    SCALAR_OP_GE,
    SCALAR_OP_GT,
    SCALAR_OP_INC,
    SCALAR_OP_INTEGER_P,
    SCALAR_OP_LE,
    SCALAR_OP_LT,
    SCALAR_OP_MAX,
    SCALAR_OP_MIN,
    SCALAR_OP_MOD,
    SCALAR_OP_MUL,
    SCALAR_OP_NEGATE,
    SCALAR_OP_NOT,
    SCALAR_OP_NULL,
    SCALAR_OP_SUB,
    SCALAR_OP_SYMBOL_P,
    ConcreteRED2Machine,
)
from concrete_red2_machine.pipelinec_vectors import RED2ABICodec


def _processor(
    machine: AbstractRED2Machine,
    codec: RED2ABICodec,
    *,
    prim0_role_name: str | None = None,
    prim0_role: int = 0,
    scalar_name: str | None = None,
    scalar_op: int = 0,
) -> ConcreteRED2Machine:
    encoded = codec.encode_state(machine.state)
    roles: tuple[int, ...] = ()
    if prim0_role_name is not None:
        literal_id = codec.literal_id(prim0_role_name)
        role_image = [0] * (literal_id + 1)
        role_image[literal_id] = prim0_role
        roles = tuple(role_image)
    scalar_ops: tuple[int, ...] = ()
    if scalar_name is not None:
        literal_id = codec.literal_id(scalar_name)
        scalar_image = [0] * (literal_id + 1)
        scalar_image[literal_id] = scalar_op
        scalar_ops = tuple(scalar_image)
    return ConcreteRED2Machine(
        encoded,
        prim0_roles=roles,
        scalar_ops=scalar_ops,
        true_literal_id=codec.literal_id("TRUE"),
        false_literal_id=codec.literal_id("FALSE"),
        nil_literal_id=codec.literal_id("NIL"),
    )


def _step_both(
    machine: AbstractRED2Machine,
    processor: ConcreteRED2Machine,
    codec: RED2ABICodec,
) -> None:
    machine.step()
    assert processor.run_to_commit()
    assert processor.checkpoint() == codec.encode_state(machine.state)


def test_red2_prim_seq_v1_is_explicit() -> None:
    assert RED2_PRIM_SEQ_V1 == 1


def test_defined_sym_reverse_preserves_active_primitive_exactly() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 16,
        control_stack=[None] * 8,
        pc=4,
        fsp=4,
        env=16,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=2,
        prim="=",
        fire=1,
    )
    state.memory[3] = Word(MuredOpcode.STOP)
    state.memory[4] = Word(MuredOpcode.SYM, "A", True, 12)
    state.memory[12] = Word(MuredOpcode.INT, 65, True)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


@pytest.mark.parametrize(
    ("opcode", "name", "arity"),
    [
        (MuredOpcode.PRIM_1, "NOT", 1),
        (MuredOpcode.PRIM_2, "+", 2),
    ],
)
def test_head_strict_primitive_arming_matches_oracle(
    opcode: MuredOpcode,
    name: str,
    arity: int,
) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=arity,
    )
    state.memory[0] = Word(opcode, name, True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


@pytest.mark.parametrize(("argcnt", "quantum"), [(1, 3), (2, 0)])
def test_binary_primitive_without_arity_or_quantum_matches_oracle(
    argcnt: int,
    quantum: int,
) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=quantum,
        phi=0,
        argcnt=argcnt,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_2, "+", True)
    state.memory[1] = Word(MuredOpcode.INT, 77, False)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


@pytest.mark.parametrize(
    ("opcode", "name", "argcnt", "role"),
    [
        (MuredOpcode.PRIM_1, "NOT", 1, 0),
        (MuredOpcode.PRIM_2, "+", 2, 0),
        (MuredOpcode.PRIM_0, "IF", 3, PRIM0_ROLE_IF),
        (MuredOpcode.PRIM_0, "IO-BIND", 2, PRIM0_ROLE_IO_SEQUENCE),
    ],
)
def test_every_task5_ready_primitive_class_is_passive_at_q_zero(
    opcode: MuredOpcode,
    name: str,
    argcnt: int,
    role: int,
) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=0,
        fsp=3,
        env=12,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=0,
        argcnt=argcnt,
    )
    state.memory[0] = Word(opcode, name, True)
    state.memory[3] = Word(MuredOpcode.STOP)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(
        machine,
        codec,
        prim0_role_name=name if opcode is MuredOpcode.PRIM_0 else None,
        prim0_role=role,
    )

    _step_both(machine, processor, codec)
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_non_head_strict_primitive_is_passive_exactly() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=2,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_2, "+", False)
    state.memory[1] = Word(MuredOpcode.INT, 1, True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


def test_head_if_arming_matches_oracle_with_load_time_role_image() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 12,
        control_stack=[None] * 4,
        pc=0,
        fsp=3,
        env=12,
        c=-1,
        direction=Direction.F,
        q=3,
        phi=0,
        argcnt=3,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[3] = Word(MuredOpcode.APP, 9, False)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(
        machine,
        codec,
        prim0_role_name="IF",
        prim0_role=PRIM0_ROLE_IF,
    )

    _step_both(machine, processor, codec)


@pytest.mark.parametrize(("argcnt", "quantum"), [(3, 0), (2, 3)])
def test_head_if_without_quantum_or_arity_is_passive_exactly(
    argcnt: int,
    quantum: int,
) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 10,
        control_stack=[None] * 4,
        pc=0,
        fsp=2,
        env=10,
        c=-1,
        direction=Direction.F,
        q=quantum,
        phi=0,
        argcnt=argcnt,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_0, "IF", True)
    state.memory[2] = Word(MuredOpcode.STOP)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(
        machine,
        codec,
        prim0_role_name="IF",
        prim0_role=PRIM0_ROLE_IF,
    )

    _step_both(machine, processor, codec)


def test_reverse_passive_value_advances_active_countdown_from_two_to_one() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=2,
        env=8,
        c=-1,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=2,
        prim="+",
        fire=2,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.INT, 7, False)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


def test_stop_discards_completed_definition_paths_exactly() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=2,
        env=8,
        c=1,
        direction=Direction.B,
        q=3,
        phi=0,
        argcnt=0,
    )
    state.memory[2] = Word(MuredOpcode.STOP)
    state.memory[3] = Word(MuredOpcode.INT, 0, False)
    state.control_stack[0] = _SavedDefinitionPath(7)
    state.control_stack[1] = _SavedDefinitionPath(6)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(machine, processor, codec)


@pytest.mark.parametrize(
    ("name", "scalar_op", "operand", "expected"),
    [
        ("1-", SCALAR_OP_DEC, Word(MuredOpcode.INT, 5), Word(MuredOpcode.INT, 4)),
        ("1+", SCALAR_OP_INC, Word(MuredOpcode.INT, 5), Word(MuredOpcode.INT, 6)),
        (
            "MINUS",
            SCALAR_OP_NEGATE,
            Word(MuredOpcode.INT, 5),
            Word(MuredOpcode.INT, -5),
        ),
        ("ABS", SCALAR_OP_ABS, Word(MuredOpcode.INT, -5), Word(MuredOpcode.INT, 5)),
        ("FLOOR", SCALAR_OP_FLOOR, Word(MuredOpcode.INT, 5), Word(MuredOpcode.INT, 5)),
        (
            "CEILING",
            SCALAR_OP_CEILING,
            Word(MuredOpcode.INT, 5),
            Word(MuredOpcode.INT, 5),
        ),
        (
            "EVEN?",
            SCALAR_OP_EVEN,
            Word(MuredOpcode.INT, 4),
            Word(MuredOpcode.SYM, "TRUE"),
        ),
        (
            "NULL?",
            SCALAR_OP_NULL,
            Word(MuredOpcode.SYM, "NIL"),
            Word(MuredOpcode.SYM, "TRUE"),
        ),
        (
            "NOT",
            SCALAR_OP_NOT,
            Word(MuredOpcode.SYM, "TRUE"),
            Word(MuredOpcode.SYM, "FALSE"),
        ),
        (
            "INTEGER?",
            SCALAR_OP_INTEGER_P,
            Word(MuredOpcode.INT, 9),
            Word(MuredOpcode.SYM, "TRUE"),
        ),
        (
            "FLOAT?",
            SCALAR_OP_FLOAT_P,
            Word(MuredOpcode.FLOAT, 1.5),
            Word(MuredOpcode.SYM, "TRUE"),
        ),
        (
            "CHAR?",
            SCALAR_OP_CHAR_P,
            Word(MuredOpcode.CHAR, "x"),
            Word(MuredOpcode.SYM, "TRUE"),
        ),
        (
            "SYMBOL?",
            SCALAR_OP_SYMBOL_P,
            Word(MuredOpcode.SYM, "X"),
            Word(MuredOpcode.SYM, "TRUE"),
        ),
    ],
)
def test_task6_unary_scalar_contractions_match_oracle_exactly(
    name: str,
    scalar_op: int,
    operand: Word,
    expected: Word,
) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=3,
        env=8,
        c=-1,
        direction=Direction.B,
        q=5,
        phi=0,
        argcnt=1,
        prim=name,
        fire=1,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = operand
    state.memory[3] = Word(MuredOpcode.STOP)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec, scalar_name=name, scalar_op=scalar_op)

    before_q = processor.q
    before_clocks = processor.clocks
    _step_both(machine, processor, codec)

    assert machine.state.memory[2] == Word(
        expected.opcode, expected.data, True, expected.definition
    )
    assert processor.q == before_q - 1
    assert processor.clocks - before_clocks == 3
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_task6_expt_rejects_huge_nontrivial_exponent_without_committing() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=3,
        env=8,
        c=-1,
        direction=Direction.B,
        q=5,
        phi=0,
        argcnt=2,
        prim="EXPT",
        fire=1,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.INT, 100_000_000)
    state.memory[3] = Word(MuredOpcode.INT, 2)
    codec = RED2ABICodec()
    processor = _processor(
        AbstractRED2Machine(state), codec, scalar_name="EXPT", scalar_op=SCALAR_OP_EXPT
    )
    before_q = processor.q

    assert processor.run_to_commit() is False
    assert processor.fault != 0
    assert processor.q == before_q
    assert processor.prim_id == codec.literal_id("EXPT")
    assert processor.fire == 0


def test_task6_expt_signed_64_bit_boundary_is_bounded() -> None:
    codec = RED2ABICodec()

    valid = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=3,
        env=8,
        c=-1,
        direction=Direction.B,
        q=5,
        phi=0,
        argcnt=2,
        prim="EXPT",
        fire=1,
    )
    valid.memory[1] = Word(MuredOpcode.STOP)
    valid.memory[2] = Word(MuredOpcode.INT, 63)
    valid.memory[3] = Word(MuredOpcode.INT, -2)
    valid_processor = _processor(
        AbstractRED2Machine(valid), codec, scalar_name="EXPT", scalar_op=SCALAR_OP_EXPT
    )
    assert valid_processor.run_to_commit()
    assert valid_processor.memory[2] == codec.encode_word(
        Word(MuredOpcode.INT, -(1 << 63), True)
    )

    overflow = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=3,
        env=8,
        c=-1,
        direction=Direction.B,
        q=5,
        phi=0,
        argcnt=2,
        prim="EXPT",
        fire=1,
    )
    overflow.memory[1] = Word(MuredOpcode.STOP)
    overflow.memory[2] = Word(MuredOpcode.INT, 63)
    overflow.memory[3] = Word(MuredOpcode.INT, 2)
    overflow_processor = _processor(
        AbstractRED2Machine(overflow), codec, scalar_name="EXPT", scalar_op=SCALAR_OP_EXPT
    )
    before_q = overflow_processor.q
    assert overflow_processor.run_to_commit() is False
    assert overflow_processor.fault != 0
    assert overflow_processor.q == before_q
    assert overflow_processor.prim_id == codec.literal_id("EXPT")
    assert overflow_processor.fire == 0


def test_task6_expt_trivial_bases_allow_large_exponents_boundedly() -> None:
    codec = RED2ABICodec()
    for base, exponent, expected in (
        (0, 100_000_000, 0),
        (1, 100_000_000, 1),
        (-1, 100_000_001, -1),
    ):
        state = AbstractRED2MachineState(
            memory=[None] * 8,
            control_stack=[None] * 4,
            pc=2,
            fsp=3,
            env=8,
            c=-1,
            direction=Direction.B,
            q=5,
            phi=0,
            argcnt=2,
            prim="EXPT",
            fire=1,
        )
        state.memory[1] = Word(MuredOpcode.STOP)
        state.memory[2] = Word(MuredOpcode.INT, exponent)
        state.memory[3] = Word(MuredOpcode.INT, base)
        processor = _processor(
            AbstractRED2Machine(state), codec, scalar_name="EXPT", scalar_op=SCALAR_OP_EXPT
        )
        assert processor.run_to_commit()
        assert processor.memory[2] == codec.encode_word(
            Word(MuredOpcode.INT, expected, True)
        )


@pytest.mark.parametrize(
    ("name", "scalar_op", "left", "right", "expected"),
    [
        ("+", SCALAR_OP_ADD, 7, 2, Word(MuredOpcode.INT, 9)),
        ("-", SCALAR_OP_SUB, 7, 2, Word(MuredOpcode.INT, 5)),
        ("*", SCALAR_OP_MUL, 7, 2, Word(MuredOpcode.INT, 14)),
        ("/", SCALAR_OP_DIV, 6, 2, Word(MuredOpcode.INT, 3)),
        ("<", SCALAR_OP_LT, 2, 7, Word(MuredOpcode.SYM, "TRUE")),
        (">", SCALAR_OP_GT, 7, 2, Word(MuredOpcode.SYM, "TRUE")),
        ("<=", SCALAR_OP_LE, 2, 2, Word(MuredOpcode.SYM, "TRUE")),
        (">=", SCALAR_OP_GE, 7, 2, Word(MuredOpcode.SYM, "TRUE")),
        ("=", SCALAR_OP_EQ, 7, 7, Word(MuredOpcode.SYM, "TRUE")),
        ("EXPT", SCALAR_OP_EXPT, 3, 4, Word(MuredOpcode.INT, 81)),
        ("MAX", SCALAR_OP_MAX, 7, 2, Word(MuredOpcode.INT, 7)),
        ("MIN", SCALAR_OP_MIN, 7, 2, Word(MuredOpcode.INT, 2)),
        ("MOD", SCALAR_OP_MOD, 7, 3, Word(MuredOpcode.INT, 1)),
    ],
)
def test_task6_binary_integer_contractions_match_oracle_exactly(
    name: str,
    scalar_op: int,
    left: int,
    right: int,
    expected: Word,
) -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=3,
        env=8,
        c=-1,
        direction=Direction.B,
        q=5,
        phi=0,
        argcnt=2,
        prim=name,
        fire=1,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.INT, right)
    state.memory[3] = Word(MuredOpcode.INT, left)
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec, scalar_name=name, scalar_op=scalar_op)

    before_q = processor.q
    before_clocks = processor.clocks
    _step_both(machine, processor, codec)

    assert machine.state.memory[2] == Word(
        expected.opcode, expected.data, True, expected.definition
    )
    assert processor.q == before_q - 1
    assert processor.clocks - before_clocks == 3
    assert processor.prim_id == 0
    assert processor.fire == 0


def test_red2_scalars_v1_is_explicit() -> None:
    assert RED2_SCALARS_V1 == 1


def test_red2_float_v1_is_explicit() -> None:
    assert RED2_FLOAT_V1 == 1


def _assert_scalar_fire_matches_oracle(
    name: str,
    scalar_op: int,
    operands: tuple[Word, ...],
) -> None:
    assert 1 <= len(operands) <= 2
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=2 + len(operands),
        env=8,
        c=-1,
        direction=Direction.B,
        q=5,
        phi=0,
        argcnt=len(operands),
        prim=name,
        fire=1,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    # RED2's reduced strict argument spine stores the right/last argument at pc.
    for offset, operand in enumerate(reversed(operands)):
        state.memory[2 + offset] = operand
    machine = AbstractRED2Machine(state)
    codec = RED2ABICodec()
    processor = _processor(
        machine,
        codec,
        scalar_name=name,
        scalar_op=scalar_op,
    )

    machine.step()
    assert processor.run_to_commit()
    assert processor.checkpoint() == codec.encode_state(machine.state)


@pytest.mark.parametrize(
    ("name", "scalar_op", "operands"),
    [
        ("1+", SCALAR_OP_INC, (Word(MuredOpcode.FLOAT, 1.5),)),
        ("MINUS", SCALAR_OP_NEGATE, (Word(MuredOpcode.FLOAT, 1.5),)),
        ("ABS", SCALAR_OP_ABS, (Word(MuredOpcode.FLOAT, -1.5),)),
        ("FLOOR", SCALAR_OP_FLOOR, (Word(MuredOpcode.FLOAT, -3.75),)),
        ("CEILING", SCALAR_OP_CEILING, (Word(MuredOpcode.FLOAT, -3.75),)),
        ("+", SCALAR_OP_ADD, (Word(MuredOpcode.FLOAT, 1.5), Word(MuredOpcode.FLOAT, 2.25))),
        ("+", SCALAR_OP_ADD, (Word(MuredOpcode.INT, 2), Word(MuredOpcode.FLOAT, 1.5))),
        ("-", SCALAR_OP_SUB, (Word(MuredOpcode.FLOAT, 5.5), Word(MuredOpcode.INT, 2))),
        ("*", SCALAR_OP_MUL, (Word(MuredOpcode.FLOAT, 1.5), Word(MuredOpcode.FLOAT, 2.5))),
        ("/", SCALAR_OP_DIV, (Word(MuredOpcode.INT, 7), Word(MuredOpcode.INT, 2))),
        ("/", SCALAR_OP_DIV, (Word(MuredOpcode.FLOAT, 7.0), Word(MuredOpcode.INT, 2))),
        ("<", SCALAR_OP_LT, (Word(MuredOpcode.INT, 2), Word(MuredOpcode.FLOAT, 2.5))),
        (">", SCALAR_OP_GT, (Word(MuredOpcode.FLOAT, 3.5), Word(MuredOpcode.INT, 2))),
        ("<=", SCALAR_OP_LE, (Word(MuredOpcode.FLOAT, 2.0), Word(MuredOpcode.INT, 2))),
        (">=", SCALAR_OP_GE, (Word(MuredOpcode.INT, 2), Word(MuredOpcode.FLOAT, 2.0))),
        ("=", SCALAR_OP_EQ, (Word(MuredOpcode.FLOAT, 2.0), Word(MuredOpcode.FLOAT, 2.0))),
        ("=", SCALAR_OP_EQ, (Word(MuredOpcode.INT, 2), Word(MuredOpcode.FLOAT, 2.0))),
        ("MAX", SCALAR_OP_MAX, (Word(MuredOpcode.FLOAT, 2.5), Word(MuredOpcode.INT, 2))),
        ("MIN", SCALAR_OP_MIN, (Word(MuredOpcode.FLOAT, 2.5), Word(MuredOpcode.INT, 2))),
        ("EXPT", SCALAR_OP_EXPT, (Word(MuredOpcode.INT, 2), Word(MuredOpcode.INT, -1))),
    ],
)
def test_red2_float_v1_common_case_primitives_match_abstract_exactly(
    name: str,
    scalar_op: int,
    operands: tuple[Word, ...],
) -> None:
    _assert_scalar_fire_matches_oracle(name, scalar_op, operands)


def test_chapter4_float_add_and_mixed_coercion_gap_is_closed() -> None:
    # Chapter 4 lines 1356-1360 (thesis p.78) explicitly require floating ADD
    # and implicit INT/FLOAT coercion. RED2_FLOAT_V1 now executes both paths
    # rather than treating them as a known Concrete semantic divergence.
    _assert_scalar_fire_matches_oracle(
        "+",
        SCALAR_OP_ADD,
        (Word(MuredOpcode.FLOAT, 1.5), Word(MuredOpcode.FLOAT, 2.25)),
    )
    _assert_scalar_fire_matches_oracle(
        "+",
        SCALAR_OP_ADD,
        (Word(MuredOpcode.INT, 2), Word(MuredOpcode.FLOAT, 1.5)),
    )


def test_signed_64_add_overflow_remains_an_atomic_bounded_refinement() -> None:
    state = AbstractRED2MachineState(
        memory=[None] * 8,
        control_stack=[None] * 4,
        pc=2,
        fsp=3,
        env=8,
        c=-1,
        direction=Direction.B,
        q=5,
        phi=0,
        argcnt=2,
        prim="+",
        fire=1,
    )
    state.memory[1] = Word(MuredOpcode.STOP)
    state.memory[2] = Word(MuredOpcode.INT, 1)
    state.memory[3] = Word(MuredOpcode.INT, abi.SIGNED_DATA_MAX)
    codec = RED2ABICodec()
    processor = _processor(
        AbstractRED2Machine(state),
        codec,
        scalar_name="+",
        scalar_op=SCALAR_OP_ADD,
    )
    before = processor.checkpoint()

    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_UNSUPPORTED_VALUE
    after = processor.checkpoint()
    # Primitive firing consumes the countdown latch before scalar evaluation;
    # the bounded overflow must not partially commit graph/traversal state.
    assert after.memory == before.memory
    assert after.control_stack == before.control_stack
    assert after.pc == before.pc
    assert after.fsp == before.fsp
    assert after.env == before.env
    assert after.free_space == before.free_space
    assert after.c == before.c
    assert after.direction == before.direction
    assert after.q == before.q
    assert after.phi == before.phi
    assert after.argcnt == before.argcnt
    assert after.prim_id == before.prim_id
    assert after.fire == 0

import math

import pytest

from abstract_red2_machine.instructions import Instruction, Opcode, encode_instruction
from abstract_red2_machine.machine import (
    AbstractRED2MachineState,
    Direction,
    MuredOpcode,
    Word,
    _EqualityFrame,
    _SavedDefinitionPath,
    _SavedFire,
    _SavedPrim,
    _SavedQuantum,
    _SubgraphFrame,
)
from concrete_red2_machine import abi
from concrete_red2_machine.pipelinec_vectors import RED2ABICodec, emit_stepper_vectors


def test_stepper_vectors_include_passive_int_and_stop() -> None:
    vectors = {v.name: v for v in emit_stepper_vectors()}
    assert vectors["int_head"].before == encode_instruction(
        Instruction(Opcode.INT, 42, head=True)
    )
    assert vectors["stop"].before == encode_instruction(
        Instruction(Opcode.STOP, 0, head=True)
    )


@pytest.mark.parametrize(
    "word",
    [
        Word(None, 17),
        Word(MuredOpcode.APP, abi.ADDRESS_MAX),
        Word(MuredOpcode.APP_VAR, 2, True),
        Word(MuredOpcode.CLOSURE, 3, False, 9, True),
        Word(MuredOpcode.EP, 4, True),
        Word(MuredOpcode.JOIN, 5, False, 1),
        Word(MuredOpcode.LAMBDA, "x", True),
        Word(MuredOpcode.STOP),
        Word(MuredOpcode.INT, abi.SIGNED_DATA_MIN, True),
        Word(MuredOpcode.INT, abi.SIGNED_DATA_MAX, False),
        Word(MuredOpcode.FLOAT, -12.5, True),
        Word(MuredOpcode.CHAR, "A"),
        Word(MuredOpcode.SYM, "TRUE", True, 42),
        Word(MuredOpcode.PRIM_0, "CLOCK", True),
        Word(MuredOpcode.PRIM_1, "ABS"),
        Word(MuredOpcode.PRIM_2, "+"),
        Word(MuredOpcode.STRUCT, "PAIR"),
        Word(MuredOpcode.RBLOCK, 2),
        Word(MuredOpcode.RUP, 1),
        Word(MuredOpcode.RECP, 3),
        Word(MuredOpcode.REC, 4),
        Word(MuredOpcode.UBV, 5),
        Word(MuredOpcode.VAR, 6),
        Word(MuredOpcode.PNP, abi.ADDRESS_MAX),
    ],
)
def test_red2_abi_word_round_trips_every_opcode_family(word: Word) -> None:
    codec = RED2ABICodec()
    decoded = codec.decode_word(codec.encode_word(word))
    assert decoded == word


def test_red2_abi_distinguishes_empty_ram_from_none_opcode_workspace_word() -> None:
    codec = RED2ABICodec()
    assert codec.encode_word(None) == 0
    packed_workspace = codec.encode_word(Word(None, 7))
    assert packed_workspace != 0
    assert codec.decode_word(packed_workspace) == Word(None, 7)


def test_red2_abi_preserves_float_bits() -> None:
    codec = RED2ABICodec()
    values = [0.0, -0.0, math.inf, -math.inf, 1.5]
    for value in values:
        decoded = codec.decode_word(codec.encode_word(Word(MuredOpcode.FLOAT, value)))
        assert decoded is not None
        assert decoded.opcode is MuredOpcode.FLOAT
        if value == 0.0:
            assert type(decoded.data) is float
            assert math.copysign(1.0, decoded.data) == math.copysign(1.0, value)
        else:
            assert decoded.data == value


def test_red2_abi_rejects_payloads_outside_explicit_widths() -> None:
    codec = RED2ABICodec()
    with pytest.raises(ValueError, match="64-bit"):
        codec.encode_word(Word(MuredOpcode.INT, abi.SIGNED_DATA_MAX + 1))
    with pytest.raises(ValueError, match="64-bit"):
        codec.encode_word(Word(MuredOpcode.INT, abi.SIGNED_DATA_MIN - 1))
    with pytest.raises(ValueError, match="fixed-width"):
        abi.require_address(abi.ADDRESS_MAX + 1)


def test_red2_abi_frontier_paths_allow_one_past_64k_ram() -> None:
    assert abi.require_address(65_535) == 65_535
    assert abi.require_frontier(65_536) == 65_536
    with pytest.raises(ValueError):
        abi.require_address(65_536)
    with pytest.raises(ValueError):
        abi.require_frontier(65_537)

    codec = RED2ABICodec()
    assert codec.decode_control_entry(codec.encode_control_entry(65_536)) == 65_536
    frame = _SubgraphFrame(env=65_536, free_space=65_536, prim=None, fire=0)
    assert codec.decode_control_entry(codec.encode_control_entry(frame)) == frame


def test_red2_abi_round_trips_typed_control_entries() -> None:
    codec = RED2ABICodec()
    entries = [
        None,
        12,
        _SavedPrim("+"),
        _SavedFire(2),
        _SavedQuantum(999),
        _SavedDefinitionPath(41),
        _SubgraphFrame(env=51, free_space=49, prim="IF", fire=3),
        _SubgraphFrame(env=51, free_space=49, prim=None, fire=0),
        _EqualityFrame(result_pc=13, live_fsp=27),
    ]
    decoded = [
        codec.decode_control_entry(codec.encode_control_entry(entry))
        for entry in entries
    ]
    assert decoded == entries


def test_red2_abi_round_trips_representative_architectural_state() -> None:
    codec = RED2ABICodec()
    memory: list[Word | None] = [None] * 64
    memory[3] = Word(MuredOpcode.PRIM_2, "+", True)
    memory[4] = Word(None, 51)
    memory[5] = Word(MuredOpcode.CLOSURE, 47, False, 7, True)
    memory[50] = Word(MuredOpcode.PNP, 60)
    control: list[
        int
        | _SavedPrim
        | _SavedFire
        | _SavedQuantum
        | _SavedDefinitionPath
        | _SubgraphFrame
        | _EqualityFrame
        | None
    ] = [None] * 8
    control[0] = 50
    control[1] = _SavedQuantum(17)
    control[2] = _SavedDefinitionPath(61)
    control[3] = _SubgraphFrame(50, 49, "IF", 2)
    control[4] = _EqualityFrame(5, 8)
    state = AbstractRED2MachineState(
        memory=memory,
        control_stack=control,
        pc=3,
        fsp=8,
        env=50,
        c=4,
        direction=Direction.B,
        q=1234,
        phi=9,
        free_space=49,
        argcnt=-1,
        prim="+",
        fire=2,
        s_a=6,
        s_d=None,
        halted=False,
        cycles=987654,
    )

    decoded = codec.decode_state(codec.encode_state(state))
    assert decoded.memory == state.memory
    assert decoded.control_stack == state.control_stack
    assert decoded.pc == state.pc
    assert decoded.fsp == state.fsp
    assert decoded.env == state.env
    assert decoded.c == state.c
    assert decoded.direction is state.direction
    assert decoded.q == state.q
    assert decoded.phi == state.phi
    assert decoded.free_space == state.free_space
    assert decoded.argcnt == state.argcnt
    assert decoded.prim == state.prim
    assert decoded.fire == state.fire
    assert decoded.s_a == state.s_a
    assert decoded.s_d == state.s_d
    assert decoded.halted == state.halted
    # cycles is deliberately diagnostic, not architectural RED2_ABI_V1 state.
    assert decoded.cycles == 0

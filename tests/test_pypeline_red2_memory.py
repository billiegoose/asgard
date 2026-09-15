from copy import deepcopy

import pytest

from pypeline_red2 import red2_stepper as hw
from red2_engine.mured import (
    ControlStackOverflow,
    ControlStackUnderflow,
    GraphEnvironmentCollision,
    MuredMachine,
    MuredOpcode,
    Word,
)
from red2_engine.pipelinec_vectors import RED2ABICodec


def _loaded_machine(*, memory_words: int = 32, control_words: int = 8) -> MuredMachine:
    return MuredMachine.load(
        [Word(MuredOpcode.INT, 0, True)],
        quantum=1,
        memory_words=memory_words,
        control_words=control_words,
    )


def _encoded_memory(codec: RED2ABICodec, machine: MuredMachine) -> list[int]:
    return [codec.encode_word(word) for word in machine.state.memory]


def test_red2_memory_v1_is_explicit() -> None:
    assert hw.RED2_MEMORY_V1 == 1


def test_graph_push_matches_oracle_and_first_collision_is_atomic() -> None:
    codec = RED2ABICodec()
    machine = _loaded_machine()
    state = machine.state
    state.fsp = 5
    state.free_space = 7
    state.env = 7
    packed = codec.encode_word(Word(MuredOpcode.INT, 41, False))
    memory = _encoded_memory(codec, machine)

    oracle_address = machine._push_graph(Word(MuredOpcode.INT, 41, False))
    fault, fsp, address = hw.red2_push_graph(memory, 5, 7, packed)

    assert fault == hw.FAULT_NONE
    assert address == fsp == oracle_address == state.fsp == 6
    assert memory == _encoded_memory(codec, machine)

    before = memory.copy()
    with pytest.raises(GraphEnvironmentCollision):
        machine._push_graph(Word(MuredOpcode.INT, 42, False))
    fault, failed_fsp, failed_address = hw.red2_push_graph(memory, fsp, 7, packed)
    assert fault == hw.FAULT_GRAPH_ENV_COLLISION
    assert failed_fsp == fsp
    assert failed_address == fsp
    assert memory == before


@pytest.mark.parametrize("words", [1, 3])
@pytest.mark.parametrize("adjacent", [True, False])
def test_environment_allocations_match_oracle_layout(
    words: int, adjacent: bool
) -> None:
    codec = RED2ABICodec()
    machine = _loaded_machine()
    state = machine.state
    state.free_space = 16
    state.env = 16 if adjacent else 24
    footprint = words + int(not adjacent)
    state.fsp = 16 - footprint - 1
    payload = [Word(MuredOpcode.INT, n, False) for n in range(words)]
    memory = _encoded_memory(codec, machine)
    packed = [codec.encode_word(word) for word in payload]

    if words == 1:
        oracle_address = machine._allocate_environment(payload[0])
        result = hw.red2_allocate_environment(
            memory, state.fsp, 16 if adjacent else 24, 16, packed[0]
        )
    else:
        oracle_address = machine._allocate_environment_block(payload)
        result = hw.red2_allocate_environment_block(
            memory, state.fsp, 16 if adjacent else 24, 16, packed
        )

    fault, address, env, free_space = result
    assert fault == hw.FAULT_NONE
    assert address == env == free_space == oracle_address
    assert memory == _encoded_memory(codec, machine)


@pytest.mark.parametrize("words", [1, 3])
@pytest.mark.parametrize("adjacent", [True, False])
def test_environment_collision_has_no_partial_bridge_or_block(
    words: int, adjacent: bool
) -> None:
    codec = RED2ABICodec()
    machine = _loaded_machine()
    state = machine.state
    state.free_space = 16
    state.env = 16 if adjacent else 24
    footprint = words + int(not adjacent)
    state.fsp = 16 - footprint
    payload = [Word(MuredOpcode.INT, n, False) for n in range(words)]
    memory = _encoded_memory(codec, machine)
    before = memory.copy()
    packed = [codec.encode_word(word) for word in payload]

    with pytest.raises(GraphEnvironmentCollision):
        if words == 1:
            machine._allocate_environment(payload[0])
        else:
            machine._allocate_environment_block(payload)

    if words == 1:
        result = hw.red2_allocate_environment(
            memory, state.fsp, 16 if adjacent else 24, 16, packed[0]
        )
    else:
        result = hw.red2_allocate_environment_block(
            memory, state.fsp, 16 if adjacent else 24, 16, packed
        )
    assert result[0] == hw.FAULT_GRAPH_ENV_COLLISION
    assert memory == before


def test_environment_allocation_uses_physical_frontier_after_logical_path_restore() -> (
    None
):
    codec = RED2ABICodec()
    machine = _loaded_machine()
    state = machine.state
    state.env = 30
    state.free_space = 30
    memory = _encoded_memory(codec, machine)
    first_word = Word(MuredOpcode.UBV, 1, False)
    second_word = Word(MuredOpcode.UBV, 2, False)

    first_oracle = machine._allocate_environment(first_word)
    fault, first, _, free_space = hw.red2_allocate_environment(
        memory, state.fsp, 30, 30, codec.encode_word(first_word)
    )
    assert fault == hw.FAULT_NONE
    assert first == first_oracle == 29

    state.env = 30
    second_oracle = machine._allocate_environment(second_word)
    fault, second, env, free_space = hw.red2_allocate_environment(
        memory, state.fsp, 30, free_space, codec.encode_word(second_word)
    )
    assert fault == hw.FAULT_NONE
    assert second == second_oracle == env == free_space == 27
    assert memory == _encoded_memory(codec, machine)


def test_environment_marker_matches_oracle_without_extra_bridge() -> None:
    codec = RED2ABICodec()
    machine = _loaded_machine()
    state = machine.state
    state.env = 30
    state.free_space = 30
    machine._allocate_environment(Word(MuredOpcode.UBV, 1, False))
    state.env = 30

    memory = _encoded_memory(codec, machine)
    oracle_marker = machine._push_environment_marker(26)
    fault, marker, env = hw.red2_push_environment_marker(memory, state.fsp, 29, 26)

    assert fault == hw.FAULT_NONE
    assert marker == env == oracle_marker == 28
    assert memory == _encoded_memory(codec, machine)


def test_control_storage_fill_drain_and_fault_boundaries_match_oracle() -> None:
    codec = RED2ABICodec()
    machine = _loaded_machine(control_words=2)
    control = [0, 0]
    c = -1
    entries = [12, 31]

    for entry in entries:
        machine._push_control_entry(entry)
        fault, c = hw.red2_control_push(control, c, codec.encode_control_entry(entry))
        assert fault == hw.FAULT_NONE
        assert c == machine.state.c

    before = deepcopy(control)
    with pytest.raises(ControlStackOverflow):
        machine._push_control_entry(44)
    fault, failed_c = hw.red2_control_push(control, c, codec.encode_control_entry(44))
    assert fault == hw.FAULT_CONTROL_OVERFLOW
    assert failed_c == c
    assert control == before

    for expected in reversed(entries):
        assert machine._pop_control_entry() == expected
        fault, c, packed = hw.red2_control_pop(control, c)
        assert fault == hw.FAULT_NONE
        assert codec.decode_control_entry(packed) == expected
        assert c == machine.state.c

    with pytest.raises(ControlStackUnderflow):
        machine._pop_control_entry()
    fault, failed_c, packed = hw.red2_control_pop(control, c)
    assert fault == hw.FAULT_CONTROL_UNDERFLOW
    assert failed_c == -1
    assert packed == 0
    assert control == [0, 0]


def test_control_storage_rejects_malformed_packed_width_without_mutation() -> None:
    control = [0, 0]

    for malformed in (-1, 1 << hw.CONTROL_WIDTH):
        before = list(control)
        fault, c = hw.red2_control_push(control, -1, malformed)
        assert fault == hw.FAULT_INVALID_ADDRESS
        assert c == -1
        assert control == before

        control[0] = malformed
        before = list(control)
        fault, c, packed = hw.red2_control_pop(control, 0)
        assert fault == hw.FAULT_INVALID_ADDRESS
        assert c == 0
        assert packed == 0
        assert control == before
        control[0] = 0


def test_64k_one_past_end_frontier_allocates_last_ram_cell() -> None:
    codec = RED2ABICodec()
    memory = [0] * 65_536
    word = codec.encode_word(Word(MuredOpcode.INT, 9, False))

    fault, address, env, free_space = hw.red2_allocate_environment(
        memory, 0, 65_536, 65_536, word
    )

    assert fault == hw.FAULT_NONE
    assert address == env == free_space == 65_535
    assert memory[65_535] == word

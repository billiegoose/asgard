from copy import deepcopy

import pytest

from pypeline_red2 import red2_stepper as abi
from pypeline_red2.red2_processor import (
    PRIM0_ROLE_DEFERRED,
    RED2_CORE_V1,
    Red2Processor,
)
from red2_engine.mured import (
    Direction,
    MuredMachine,
    MuredMachineState,
    MuredOpcode,
    Word,
)
from red2_engine.pipelinec_vectors import RED2ABICodec


def _loaded(words: list[Word], *, q: int = 8, memory_words: int = 64) -> MuredMachine:
    return MuredMachine.load(
        words, quantum=q, memory_words=memory_words, control_words=32
    )


def _processor(machine: MuredMachine, codec: RED2ABICodec) -> Red2Processor:
    return Red2Processor(codec.encode_state(machine.state))


def _assert_architecture_matches(
    processor: Red2Processor, machine: MuredMachine, codec: RED2ABICodec
) -> None:
    actual = processor.checkpoint()
    expected = codec.encode_state(machine.state)
    assert actual == expected


def _step_both(
    processor: Red2Processor, machine: MuredMachine, codec: RED2ABICodec
) -> None:
    machine.step()
    assert processor.run_to_commit()
    _assert_architecture_matches(processor, machine, codec)


def test_default_run_to_commit_budget_covers_task4_pairwise_visit_scan() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.INT, 3, True)], memory_words=64)
    processor = _processor(machine, codec)
    memory_words = len(processor.memory)

    budget = processor._default_run_to_commit_budget()

    assert budget >= memory_words * memory_words * 8
    assert budget > memory_words * 64


def test_red2_core_v1_is_explicit_and_commit_requires_multiple_clocks() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.INT, 3, True)])
    processor = _processor(machine, codec)

    assert RED2_CORE_V1 == 1
    assert processor.commits == 0
    assert processor.clock() is False
    assert processor.commits == 0
    assert processor.clock() is False
    assert processor.commits == 0
    assert processor.clock() is True
    assert processor.commits == 1


def test_forward_and_reverse_atomic_int_match_oracle() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.INT, 7, True)])
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)
    _step_both(processor, machine, codec)


def test_float_and_char_forward_transitions_match_oracle() -> None:
    codec = RED2ABICodec()
    for word in (Word(MuredOpcode.FLOAT, 2.5, True), Word(MuredOpcode.CHAR, "x", True)):
        machine = _loaded([word])
        processor = _processor(machine, codec)
        _step_both(processor, machine, codec)


def test_app_forward_matches_graph_and_control_delta() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.APP, 0, False), Word(MuredOpcode.INT, 1, True)])
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)


def test_ubv_forward_at_zero_quantum_matches_oracle() -> None:
    state = MuredMachineState(
        memory=[None] * 64,
        control_stack=[None] * 32,
        pc=0,
        fsp=1,
        env=64,
        c=-1,
        direction=Direction.F,
        q=0,
        phi=3,
        argcnt=0,
    )
    state.memory[0] = Word(MuredOpcode.UBV, 1, False)
    state.memory[1] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    codec = RED2ABICodec()
    processor = _processor(machine, codec)

    _step_both(processor, machine, codec)

    assert processor.q == 0
    assert processor.direction == abi.DIRECTION_REVERSE
    assert processor.argcnt == 1
    assert processor.memory[processor.fsp] == codec.encode_word(
        Word(MuredOpcode.VAR, 2, True)
    )


def test_app_var_forward_immediate_environment_value_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _loaded(
        [Word(MuredOpcode.APP_VAR, 0, False), Word(MuredOpcode.INT, 1, True)]
    )
    machine.state.env = 40
    machine.state.free_space = 40
    machine.state.memory[40] = Word(MuredOpcode.INT, 12, False)
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)


def test_app_var_reverse_is_a_plain_spine_step() -> None:
    codec = RED2ABICodec()
    machine = _loaded(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.APP_VAR, 0, False)]
    )
    machine.state.direction = Direction.B
    machine.state.pc = 1
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)


def test_lambda_reverse_matches_phi_and_pc_delta() -> None:
    codec = RED2ABICodec()
    machine = _loaded(
        [Word(MuredOpcode.INT, 0, False), Word(MuredOpcode.LAMBDA, "x", True)]
    )
    machine.state.direction = Direction.B
    machine.state.pc = 1
    machine.state.phi = 2
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)


def test_lambda_forward_q_zero_builds_ubv_environment_binding() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.LAMBDA, "x", True)], q=0)
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)


def test_lambda_consumes_immediate_argument_and_allocates_binding() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.LAMBDA, "x", True)])
    state = machine.state
    state.memory[state.fsp] = Word(MuredOpcode.INT, 99, True)
    state.argcnt = 1
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)


def test_var_immediate_environment_value_matches_oracle() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.VAR, 0, True)])
    machine.state.env = 40
    machine.state.free_space = 40
    machine.state.memory[40] = Word(MuredOpcode.INT, 22, False)
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)


def test_stop_is_an_architectural_backward_transition() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.INT, 1, True)])
    machine.state.pc = 1
    machine.state.direction = Direction.B
    # MuredMachine.step() validates pc again after _stop() increments it, so a
    # synthetic direct-STOP fixture needs a populated continuation cell.
    machine.state.memory[2] = Word(MuredOpcode.INT, 0, False)
    processor = _processor(machine, codec)
    _step_both(processor, machine, codec)
    assert processor.halted == 1


def test_processor_state_persists_across_many_commits_without_reinitialization() -> (
    None
):
    codec = RED2ABICodec()
    words = [Word(MuredOpcode.INT, n, False) for n in range(25)]
    words.append(Word(MuredOpcode.INT, 99, True))
    machine = _loaded(words, memory_words=128)
    processor = _processor(machine, codec)
    identity = id(processor)

    for _ in range(50):
        if machine.state.halted:
            break
        _step_both(processor, machine, codec)

    assert id(processor) == identity
    assert processor.commits >= 50


def test_differential_checkpoint_detects_perturbed_expected_state() -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.INT, 7, True)])
    processor = _processor(machine, codec)
    machine.step()
    assert processor.run_to_commit()
    expected = codec.encode_state(machine.state)
    perturbed = deepcopy(expected)
    object.__setattr__(perturbed, "pc", expected.pc + 1)
    assert processor.checkpoint() != perturbed


@pytest.mark.parametrize(
    "word",
    [
        Word(MuredOpcode.PRIM_0, "CLOCK", True),
    ],
)
def test_later_slice_transitions_fault_instead_of_being_approximated(
    word: Word,
) -> None:
    codec = RED2ABICodec()
    machine = _loaded([Word(MuredOpcode.INT, 0, True)])
    machine.state.memory[0] = word
    encoded = codec.encode_state(machine.state)
    literal_id = codec.literal_id("CLOCK")
    roles = [0] * (literal_id + 1)
    roles[literal_id] = PRIM0_ROLE_DEFERRED
    processor = Red2Processor(encoded, prim0_roles=tuple(roles))
    assert processor.run_to_commit() is False
    assert processor.fault == abi.FAULT_ILLEGAL_TRANSITION

"""Compiled-image loader and committed-transition lockstep oracle for Pypeline RED2."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace

from pypeline_red2 import red2_stepper as abi
from pypeline_red2.red2_processor import (
    PRIM0_ROLE_DEFERRED,
    PRIM0_ROLE_IF,
    PRIM0_ROLE_IO_BIND,
    PRIM0_ROLE_IO_RETURN,
    PRIM0_ROLE_IO_THEN,
    PRIM0_ROLE_Y,
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
    Red2Processor,
)
from red2_engine.mured import (
    ControlStackOverflow,
    ControlStackUnderflow,
    GraphEnvironmentCollision,
    IllegalTransition,
    InvalidAddress,
    MalformedClosure,
    MuredMachine,
    MuredOpcode,
    Word,
)
from red2_engine.pipelinec_vectors import (
    EncodedArchitecturalState,
    EncodedProgramImage,
    RED2ABICodec,
)
from thor_compile.red2 import FaithfulDefinitionCache, load_faithful_machine
from thor_lang.ast import Expr

RED2_LOCKSTEP_V1 = 1

_SCALAR_OPS = {
    "1-": SCALAR_OP_DEC,
    "1+": SCALAR_OP_INC,
    "MINUS": SCALAR_OP_NEGATE,
    "ABS": SCALAR_OP_ABS,
    "FLOOR": SCALAR_OP_FLOOR,
    "CEILING": SCALAR_OP_CEILING,
    "EVEN?": SCALAR_OP_EVEN,
    "NULL?": SCALAR_OP_NULL,
    "NOT": SCALAR_OP_NOT,
    "INTEGER?": SCALAR_OP_INTEGER_P,
    "FLOAT?": SCALAR_OP_FLOAT_P,
    "CHAR?": SCALAR_OP_CHAR_P,
    "SYMBOL?": SCALAR_OP_SYMBOL_P,
    "+": SCALAR_OP_ADD,
    "-": SCALAR_OP_SUB,
    "*": SCALAR_OP_MUL,
    "/": SCALAR_OP_DIV,
    "<": SCALAR_OP_LT,
    ">": SCALAR_OP_GT,
    "<=": SCALAR_OP_LE,
    ">=": SCALAR_OP_GE,
    "=": SCALAR_OP_EQ,
    "EXPT": SCALAR_OP_EXPT,
    "MAX": SCALAR_OP_MAX,
    "MIN": SCALAR_OP_MIN,
    "MOD": SCALAR_OP_MOD,
}

_PRIM0_ROLES = {
    "IF": PRIM0_ROLE_IF,
    "AND": PRIM0_ROLE_DEFERRED,
    "OR": PRIM0_ROLE_DEFERRED,
    "Y": PRIM0_ROLE_Y,
    "IO-BIND": PRIM0_ROLE_IO_BIND,
    "IO-THEN": PRIM0_ROLE_IO_THEN,
    "IO-RETURN": PRIM0_ROLE_IO_RETURN,
}

_HOST_OPS = {
    "CLOCK": abi.HOST_CLOCK,
    "UART-RX": abi.HOST_UART_RX,
    "UART-TX": abi.HOST_UART_TX,
    "UART-TX-BYTES": abi.HOST_UART_TX_BYTES,
}


@dataclass(frozen=True, slots=True)
class ArchitecturalDiff:
    field: str
    oracle: object
    processor: object
    index: int | None = None


@dataclass(frozen=True, slots=True)
class LockstepDivergence:
    transition: int
    oracle: EncodedArchitecturalState
    processor: EncodedArchitecturalState
    diffs: tuple[ArchitecturalDiff, ...]
    oracle_opcode: str | None
    processor_microstate: int

    def format(self) -> str:
        context = (
            f"transition {self.transition}: oracle_opcode={self.oracle_opcode} "
            f"processor_microstate={self.processor_microstate}"
        )
        details = []
        for diff in self.diffs:
            where = diff.field if diff.index is None else f"{diff.field}[{diff.index}]"
            details.append(f"  {where}: oracle={diff.oracle!r} processor={diff.processor!r}")
        return "\n".join((context, *details))


@dataclass(frozen=True, slots=True)
class LockstepResult:
    transitions: int
    status: int
    divergence: LockstepDivergence | None = None

    @property
    def matches(self) -> bool:
        return self.divergence is None


@dataclass(frozen=True, slots=True)
class LoadedLockstepProgram:
    """One canonical compiled/relocated oracle image and its Pypeline instance."""

    machine: MuredMachine
    codec: RED2ABICodec
    image: EncodedProgramImage
    processor: Red2Processor


def _dense_literal_image(codec: RED2ABICodec, mapping: dict[str, int], default: int = 0) -> tuple[int, ...]:
    ids = {codec.literal_id(name): value for name, value in mapping.items()}
    if not ids:
        return ()
    image = [default] * (max(ids) + 1)
    for literal_id, value in ids.items():
        image[literal_id] = value
    return tuple(image)


def build_processor(
    image: EncodedProgramImage,
    codec: RED2ABICodec,
) -> Red2Processor:
    """Instantiate the processor from the same encoded image used for comparison."""
    selector_limit = max((item.selector_id for item in image.struct_selectors), default=0)
    selector_tags = [0] * (selector_limit + 1)
    selector_offsets = [0] * (selector_limit + 1)
    for item in image.struct_selectors:
        selector_tags[item.selector_id] = item.tag_id
        selector_offsets[item.selector_id] = item.offset

    return Red2Processor(
        image.state,
        prim0_roles=_dense_literal_image(codec, _PRIM0_ROLES),
        scalar_ops=_dense_literal_image(codec, _SCALAR_OPS),
        host_ops=_dense_literal_image(codec, _HOST_OPS, abi.HOST_NONE),
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
        working_memory_limit=image.working_memory_limit,
    )


def load_processor(machine: MuredMachine, codec: RED2ABICodec | None = None) -> tuple[RED2ABICodec, EncodedProgramImage, Red2Processor]:
    codec = RED2ABICodec() if codec is None else codec
    image = codec.encode_program(machine)
    return codec, image, build_processor(image, codec)


def load_compiled_program(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | FaithfulDefinitionCache | None = None,
    memory_words: int = 1_048_576,
    control_words: int = 8_192,
) -> LoadedLockstepProgram:
    """Compile/relocate once with the faithful loader, then encode that exact image."""
    canonical_definitions = definitions
    if definitions is not None and not isinstance(definitions, FaithfulDefinitionCache):
        canonical_definitions = {
            name: definitions[name]
            for name in sorted(definitions)
        }
    machine = load_faithful_machine(
        expr,
        quantum=quantum,
        definitions=canonical_definitions,
        memory_words=memory_words,
        control_words=control_words,
    )
    codec, image, processor = load_processor(machine)
    return LoadedLockstepProgram(machine, codec, image, processor)


def oracle_fault(error: BaseException | None) -> int:
    """Normalize typed μRED machine failures to RED2_ABI_V1 fault identifiers."""
    if error is None:
        return abi.FAULT_NONE
    if isinstance(error, InvalidAddress):
        return abi.FAULT_INVALID_ADDRESS
    if isinstance(error, GraphEnvironmentCollision):
        return abi.FAULT_GRAPH_ENV_COLLISION
    if isinstance(error, ControlStackOverflow):
        return abi.FAULT_CONTROL_OVERFLOW
    if isinstance(error, ControlStackUnderflow):
        return abi.FAULT_CONTROL_UNDERFLOW
    if isinstance(error, (MalformedClosure, IllegalTransition)):
        return abi.FAULT_ILLEGAL_TRANSITION
    raise error


def oracle_resume_fault(error: BaseException | None) -> int:
    """Normalize failures specifically at the RED2_HOSTCALL_V1 resume boundary."""
    if error is None:
        return abi.FAULT_NONE
    if isinstance(error, IllegalTransition):
        return abi.FAULT_INVALID_RESUME
    return oracle_fault(error)


def oracle_status(machine: MuredMachine, error: BaseException | None = None) -> int:
    """Normalize the oracle scheduler state to RED2_ABI_V1 status values."""
    if error is not None:
        oracle_fault(error)
        return abi.STATUS_FAULT
    if machine.pending_host_call is not None:
        return abi.STATUS_HOST_CALL
    if machine.state.halted:
        return (
            abi.STATUS_QUANTUM_EXHAUSTED
            if machine.state.q == 0
            else abi.STATUS_COMPLETE
        )
    return abi.STATUS_RUNNING


def architectural_diffs(
    oracle: EncodedArchitecturalState,
    processor: EncodedArchitecturalState,
    *,
    oracle_status_value: int | None = None,
    processor_status_value: int | None = None,
    oracle_fault_value: int | None = None,
    processor_fault_value: int | None = None,
) -> tuple[ArchitecturalDiff, ...]:
    """Return all architectural differences, with memory/control localized by index."""
    diffs: list[ArchitecturalDiff] = []
    for field in fields(EncodedArchitecturalState):
        name = field.name
        left = getattr(oracle, name)
        right = getattr(processor, name)
        if left == right:
            continue
        if name in {"memory", "control_stack"}:
            limit = max(len(left), len(right))
            for index in range(limit):
                lvalue = left[index] if index < len(left) else None
                rvalue = right[index] if index < len(right) else None
                if lvalue != rvalue:
                    diffs.append(ArchitecturalDiff(name, lvalue, rvalue, index))
            continue
        diffs.append(ArchitecturalDiff(name, left, right))
    if (
        oracle_status_value is not None
        and processor_status_value is not None
        and oracle_status_value != processor_status_value
    ):
        diffs.append(
            ArchitecturalDiff(
                "status",
                oracle_status_value,
                processor_status_value,
            )
        )
    if (
        oracle_fault_value is not None
        and processor_fault_value is not None
        and oracle_fault_value != processor_fault_value
    ):
        diffs.append(
            ArchitecturalDiff(
                "fault",
                oracle_fault_value,
                processor_fault_value,
            )
        )
    return tuple(diffs)


def _oracle_opcode(machine: MuredMachine) -> str | None:
    pc = machine.state.pc
    if not 0 <= pc < len(machine.state.memory):
        return None
    word = machine.state.memory[pc]
    if word is None or word.opcode is None:
        return None
    return word.opcode.value


def compare_checkpoint(
    machine: MuredMachine,
    processor: Red2Processor,
    codec: RED2ABICodec,
    *,
    transition: int,
    oracle_opcode: str | None = None,
) -> LockstepDivergence | None:
    expected = codec.encode_state(machine.state, machine.pending_host_call)
    actual = processor.checkpoint()
    diffs = architectural_diffs(
        expected,
        actual,
        oracle_status_value=oracle_status(machine),
        processor_status_value=processor.status(),
        oracle_fault_value=abi.FAULT_NONE,
        processor_fault_value=processor.fault,
    )
    if not diffs:
        return None
    return LockstepDivergence(
        transition,
        expected,
        actual,
        diffs,
        oracle_opcode,
        processor.microstate,
    )


def run_lockstep(
    machine: MuredMachine,
    *,
    max_transitions: int = 10_000,
    host_service: Callable[[str, Word | None], Word] | None = None,
    recharge_quantum: int | None = None,
    codec: RED2ABICodec | None = None,
    processor: Red2Processor | None = None,
) -> LockstepResult:
    """Run matching committed transitions and return the first architectural divergence."""
    if processor is None:
        codec, _image, processor = load_processor(machine, codec)
    elif codec is None:
        raise ValueError("preloaded processor requires its RED2 ABI codec")
    initial = compare_checkpoint(machine, processor, codec, transition=0)
    if initial is not None:
        return LockstepResult(0, processor.status(), initial)

    transition = 0
    while transition < max_transitions:
        if machine.pending_host_call is not None:
            if host_service is None:
                return LockstepResult(transition, processor.status())
            call = machine.pending_host_call
            argument = (
                None
                if call.argument_address is None
                else machine.state.memory[call.argument_address]
            )
            result = host_service(call.name, argument)
            oracle_error: BaseException | None = None
            try:
                machine.resume_host_call(result)
            except (
                InvalidAddress,
                GraphEnvironmentCollision,
                ControlStackOverflow,
                ControlStackUnderflow,
                MalformedClosure,
                IllegalTransition,
            ) as error:
                oracle_error = error
            processor.resume_host_call(codec.encode_word(result))
            transition += 1
            if oracle_error is not None or processor.status() == abi.STATUS_FAULT:
                expected = codec.encode_state(machine.state, machine.pending_host_call)
                actual = processor.checkpoint()
                oracle_fault_value = oracle_resume_fault(oracle_error)
                oracle_status_value = (
                    abi.STATUS_FAULT
                    if oracle_error is not None
                    else oracle_status(machine)
                )
                diffs = architectural_diffs(
                    expected,
                    actual,
                    oracle_status_value=oracle_status_value,
                    processor_status_value=processor.status(),
                    oracle_fault_value=oracle_fault_value,
                    processor_fault_value=processor.fault,
                )
                if not diffs and oracle_error is not None:
                    return LockstepResult(transition, abi.STATUS_FAULT)
                if diffs:
                    return LockstepResult(
                        transition,
                        processor.status(),
                        LockstepDivergence(
                            transition,
                            expected,
                            actual,
                            diffs,
                            f"RESUME:{call.name}",
                            processor.microstate,
                        ),
                    )
            divergence = compare_checkpoint(
                machine,
                processor,
                codec,
                transition=transition,
                oracle_opcode=f"RESUME:{call.name}",
            )
            if divergence is not None:
                return LockstepResult(transition, processor.status(), divergence)
            continue

        if machine.state.halted:
            if machine.state.q == 0 and recharge_quantum is not None:
                machine.recharge_quantum(recharge_quantum)
                processor.recharge_quantum(recharge_quantum)
                transition += 1
                divergence = compare_checkpoint(
                    machine,
                    processor,
                    codec,
                    transition=transition,
                    oracle_opcode="RECHARGE",
                )
                if divergence is not None:
                    return LockstepResult(transition, processor.status(), divergence)
                continue
            return LockstepResult(transition, processor.status())

        opcode = _oracle_opcode(machine)
        oracle_error: BaseException | None = None
        try:
            machine.step()
        except (
            InvalidAddress,
            GraphEnvironmentCollision,
            ControlStackOverflow,
            ControlStackUnderflow,
            MalformedClosure,
            IllegalTransition,
        ) as error:
            oracle_error = error
        processor_committed = processor.run_to_commit()
        if oracle_error is not None or not processor_committed:
            expected = codec.encode_state(machine.state, machine.pending_host_call)
            actual = processor.checkpoint()
            oracle_status_value = oracle_status(machine, oracle_error)
            oracle_fault_value = oracle_fault(oracle_error)
            diffs = architectural_diffs(
                expected,
                actual,
                oracle_status_value=oracle_status_value,
                processor_status_value=processor.status(),
                oracle_fault_value=oracle_fault_value,
                processor_fault_value=processor.fault,
            )
            if not diffs and oracle_error is not None:
                return LockstepResult(transition + 1, abi.STATUS_FAULT)
            if not diffs:
                diffs = (
                    ArchitecturalDiff("status", oracle_status_value, processor.status()),
                )
            return LockstepResult(
                transition + 1,
                processor.status(),
                LockstepDivergence(
                    transition + 1,
                    expected,
                    actual,
                    diffs,
                    opcode,
                    processor.microstate,
                ),
            )
        transition += 1
        divergence = compare_checkpoint(
            machine,
            processor,
            codec,
            transition=transition,
            oracle_opcode=opcode,
        )
        if divergence is not None:
            return LockstepResult(transition, processor.status(), divergence)

    raise RuntimeError(f"RED2 lockstep transition limit reached: {max_transitions}")


def run_compiled_lockstep(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | FaithfulDefinitionCache | None = None,
    memory_words: int = 1_048_576,
    control_words: int = 8_192,
    max_transitions: int = 10_000,
    host_service: Callable[[str, Word | None], Word] | None = None,
    recharge_quantum: int | None = None,
) -> LockstepResult:
    """Compile/load both machines from one canonical image and run committed lockstep."""
    loaded = load_compiled_program(
        expr,
        quantum=quantum,
        definitions=definitions,
        memory_words=memory_words,
        control_words=control_words,
    )
    return run_lockstep(
        loaded.machine,
        max_transitions=max_transitions,
        host_service=host_service,
        recharge_quantum=recharge_quantum,
        codec=loaded.codec,
        processor=loaded.processor,
    )


def mutate_state(
    state: EncodedArchitecturalState,
    **changes: object,
) -> EncodedArchitecturalState:
    """Test helper for proving every architectural field participates in comparison."""
    return replace(state, **changes)

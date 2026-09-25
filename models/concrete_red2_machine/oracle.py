"""Compiled-image loader and committed-transition lockstep oracle for Concrete RED2."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields, replace

from abstract_red2_machine.machine import (
    AbstractRED2Machine,
    ControlStackOverflow,
    ControlStackUnderflow,
    GraphEnvironmentCollision,
    IllegalTransition,
    InvalidAddress,
    MalformedClosure,
    Word,
)
from concrete_red2_machine import abi
from concrete_red2_machine.machine import (
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
    ConcreteRED2Machine,
)
from concrete_red2_machine.pipelinec_vectors import (
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
    concrete: object
    index: int | None = None


@dataclass(frozen=True, slots=True)
class LockstepDivergence:
    transition: int
    oracle: EncodedArchitecturalState
    concrete: EncodedArchitecturalState
    diffs: tuple[ArchitecturalDiff, ...]
    oracle_opcode: str | None
    concrete_microstate: int

    def format(self) -> str:
        context = (
            f"transition {self.transition}: oracle_opcode={self.oracle_opcode} "
            f"concrete_microstate={self.concrete_microstate}"
        )
        details = []
        for diff in self.diffs:
            where = diff.field if diff.index is None else f"{diff.field}[{diff.index}]"
            details.append(
                f"  {where}: oracle={diff.oracle!r} concrete={diff.concrete!r}"
            )
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
    """One canonical compiled image and its abstract/concrete machines."""

    abstract: AbstractRED2Machine
    codec: RED2ABICodec
    image: EncodedProgramImage
    concrete: ConcreteRED2Machine

    @property
    def machine(self) -> AbstractRED2Machine:
        """Compatibility alias for the historical oracle field name."""
        return self.abstract

    @property
    def processor(self) -> ConcreteRED2Machine:
        """Compatibility alias for the historical concrete field name."""
        return self.concrete


def _dense_literal_image(
    codec: RED2ABICodec, mapping: dict[str, int], default: int = 0
) -> tuple[int, ...]:
    ids = {codec.literal_id(name): value for name, value in mapping.items()}
    if not ids:
        return ()
    image = [default] * (max(ids) + 1)
    for literal_id, value in ids.items():
        image[literal_id] = value
    return tuple(image)


def build_concrete_machine(
    image: EncodedProgramImage,
    codec: RED2ABICodec,
) -> ConcreteRED2Machine:
    """Instantiate the Concrete RED2 Machine from one encoded image."""
    selector_limit = max(
        (item.selector_id for item in image.struct_selectors), default=0
    )
    selector_tags = [0] * (selector_limit + 1)
    selector_offsets = [0] * (selector_limit + 1)
    for item in image.struct_selectors:
        selector_tags[item.selector_id] = item.tag_id
        selector_offsets[item.selector_id] = item.offset

    return ConcreteRED2Machine(
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


def load_concrete_machine(
    abstract: AbstractRED2Machine, codec: RED2ABICodec | None = None
) -> tuple[RED2ABICodec, EncodedProgramImage, ConcreteRED2Machine]:
    codec = RED2ABICodec() if codec is None else codec
    image = codec.encode_program(abstract)
    return codec, image, build_concrete_machine(image, codec)


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
    abstract = load_faithful_machine(
        expr,
        quantum=quantum,
        definitions=canonical_definitions,
        memory_words=memory_words,
        control_words=control_words,
    )
    codec, image, concrete = load_concrete_machine(abstract)
    return LoadedLockstepProgram(abstract, codec, image, concrete)



def build_processor(
    image: EncodedProgramImage, codec: RED2ABICodec
) -> ConcreteRED2Machine:
    """Compatibility wrapper for :func:`build_concrete_machine`."""
    return build_concrete_machine(image, codec)


def load_processor(
    machine: AbstractRED2Machine, codec: RED2ABICodec | None = None
) -> tuple[RED2ABICodec, EncodedProgramImage, ConcreteRED2Machine]:
    """Compatibility wrapper for :func:`load_concrete_machine`."""
    return load_concrete_machine(machine, codec)

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


def oracle_status(
    abstract: AbstractRED2Machine, error: BaseException | None = None
) -> int:
    """Normalize the oracle scheduler state to RED2_ABI_V1 status values."""
    if error is not None:
        oracle_fault(error)
        return abi.STATUS_FAULT
    if abstract.pending_host_call is not None:
        return abi.STATUS_HOST_CALL
    if abstract.state.halted:
        return (
            abi.STATUS_QUANTUM_EXHAUSTED
            if abstract.state.q == 0
            else abi.STATUS_COMPLETE
        )
    return abi.STATUS_RUNNING


def architectural_diffs(
    oracle: EncodedArchitecturalState,
    concrete: EncodedArchitecturalState,
    *,
    oracle_status_value: int | None = None,
    concrete_status_value: int | None = None,
    oracle_fault_value: int | None = None,
    concrete_fault_value: int | None = None,
) -> tuple[ArchitecturalDiff, ...]:
    """Return all architectural differences, with memory/control localized by index."""
    diffs: list[ArchitecturalDiff] = []
    for field in fields(EncodedArchitecturalState):
        name = field.name
        left = getattr(oracle, name)
        right = getattr(concrete, name)
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
        and concrete_status_value is not None
        and oracle_status_value != concrete_status_value
    ):
        diffs.append(
            ArchitecturalDiff(
                "status",
                oracle_status_value,
                concrete_status_value,
            )
        )
    if (
        oracle_fault_value is not None
        and concrete_fault_value is not None
        and oracle_fault_value != concrete_fault_value
    ):
        diffs.append(
            ArchitecturalDiff(
                "fault",
                oracle_fault_value,
                concrete_fault_value,
            )
        )
    return tuple(diffs)


def _oracle_opcode(abstract: AbstractRED2Machine) -> str | None:
    pc = abstract.state.pc
    if not 0 <= pc < len(abstract.state.memory):
        return None
    word = abstract.state.memory[pc]
    if word is None or word.opcode is None:
        return None
    return word.opcode.value


def compare_checkpoint(
    abstract: AbstractRED2Machine,
    concrete: ConcreteRED2Machine,
    codec: RED2ABICodec,
    *,
    transition: int,
    oracle_opcode: str | None = None,
) -> LockstepDivergence | None:
    expected = codec.encode_state(abstract.state, abstract.pending_host_call)
    actual = concrete.checkpoint()
    diffs = architectural_diffs(
        expected,
        actual,
        oracle_status_value=oracle_status(abstract),
        concrete_status_value=concrete.status(),
        oracle_fault_value=abi.FAULT_NONE,
        concrete_fault_value=concrete.fault,
    )
    if not diffs:
        return None
    return LockstepDivergence(
        transition,
        expected,
        actual,
        diffs,
        oracle_opcode,
        concrete.microstate,
    )


def run_lockstep(
    abstract: AbstractRED2Machine,
    *,
    max_transitions: int = 10_000,
    host_service: Callable[[str, Word | None], Word] | None = None,
    recharge_quantum: int | None = None,
    codec: RED2ABICodec | None = None,
    concrete: ConcreteRED2Machine | None = None,
) -> LockstepResult:
    """Run matching committed transitions and return the first divergence."""
    if concrete is None:
        codec, _image, concrete = load_concrete_machine(abstract, codec)
    elif codec is None:
        raise ValueError("preloaded concrete machine requires its RED2 ABI codec")
    initial = compare_checkpoint(abstract, concrete, codec, transition=0)
    if initial is not None:
        return LockstepResult(0, concrete.status(), initial)

    transition = 0
    while transition < max_transitions:
        if abstract.pending_host_call is not None:
            if host_service is None:
                return LockstepResult(transition, concrete.status())
            call = abstract.pending_host_call
            argument = (
                None
                if call.argument_address is None
                else abstract.state.memory[call.argument_address]
            )
            result = host_service(call.name, argument)
            oracle_error: BaseException | None = None
            try:
                abstract.resume_host_call(result)
            except (
                InvalidAddress,
                GraphEnvironmentCollision,
                ControlStackOverflow,
                ControlStackUnderflow,
                MalformedClosure,
                IllegalTransition,
            ) as error:
                oracle_error = error
            concrete.resume_host_call(codec.encode_word(result))
            transition += 1
            if oracle_error is not None or concrete.status() == abi.STATUS_FAULT:
                expected = codec.encode_state(
                    abstract.state, abstract.pending_host_call
                )
                actual = concrete.checkpoint()
                oracle_fault_value = oracle_resume_fault(oracle_error)
                oracle_status_value = (
                    abi.STATUS_FAULT
                    if oracle_error is not None
                    else oracle_status(abstract)
                )
                diffs = architectural_diffs(
                    expected,
                    actual,
                    oracle_status_value=oracle_status_value,
                    concrete_status_value=concrete.status(),
                    oracle_fault_value=oracle_fault_value,
                    concrete_fault_value=concrete.fault,
                )
                if not diffs and oracle_error is not None:
                    return LockstepResult(transition, abi.STATUS_FAULT)
                if diffs:
                    return LockstepResult(
                        transition,
                        concrete.status(),
                        LockstepDivergence(
                            transition,
                            expected,
                            actual,
                            diffs,
                            f"RESUME:{call.name}",
                            concrete.microstate,
                        ),
                    )
            divergence = compare_checkpoint(
                abstract,
                concrete,
                codec,
                transition=transition,
                oracle_opcode=f"RESUME:{call.name}",
            )
            if divergence is not None:
                return LockstepResult(transition, concrete.status(), divergence)
            continue

        if abstract.state.halted:
            if abstract.state.q == 0 and recharge_quantum is not None:
                abstract.recharge_quantum(recharge_quantum)
                concrete.recharge_quantum(recharge_quantum)
                transition += 1
                divergence = compare_checkpoint(
                    abstract,
                    concrete,
                    codec,
                    transition=transition,
                    oracle_opcode="RECHARGE",
                )
                if divergence is not None:
                    return LockstepResult(transition, concrete.status(), divergence)
                continue
            return LockstepResult(transition, concrete.status())

        opcode = _oracle_opcode(abstract)
        oracle_error: BaseException | None = None
        try:
            abstract.step()
        except (
            InvalidAddress,
            GraphEnvironmentCollision,
            ControlStackOverflow,
            ControlStackUnderflow,
            MalformedClosure,
            IllegalTransition,
        ) as error:
            oracle_error = error
        concrete_committed = concrete.run_to_commit()
        if oracle_error is not None or not concrete_committed:
            expected = codec.encode_state(abstract.state, abstract.pending_host_call)
            actual = concrete.checkpoint()
            oracle_status_value = oracle_status(abstract, oracle_error)
            oracle_fault_value = oracle_fault(oracle_error)
            diffs = architectural_diffs(
                expected,
                actual,
                oracle_status_value=oracle_status_value,
                concrete_status_value=concrete.status(),
                oracle_fault_value=oracle_fault_value,
                concrete_fault_value=concrete.fault,
            )
            if not diffs and oracle_error is not None:
                return LockstepResult(transition + 1, abi.STATUS_FAULT)
            if not diffs:
                diffs = (
                    ArchitecturalDiff(
                        "status", oracle_status_value, concrete.status()
                    ),
                )
            return LockstepResult(
                transition + 1,
                concrete.status(),
                LockstepDivergence(
                    transition + 1,
                    expected,
                    actual,
                    diffs,
                    opcode,
                    concrete.microstate,
                ),
            )
        transition += 1
        divergence = compare_checkpoint(
            abstract,
            concrete,
            codec,
            transition=transition,
            oracle_opcode=opcode,
        )
        if divergence is not None:
            return LockstepResult(transition, concrete.status(), divergence)

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
    """Compile/load both machines from one image and run committed lockstep."""
    loaded = load_compiled_program(
        expr,
        quantum=quantum,
        definitions=definitions,
        memory_words=memory_words,
        control_words=control_words,
    )
    return run_lockstep(
        loaded.abstract,
        max_transitions=max_transitions,
        host_service=host_service,
        recharge_quantum=recharge_quantum,
        codec=loaded.codec,
        concrete=loaded.concrete,
    )


def mutate_state(
    state: EncodedArchitecturalState,
    **changes: object,
) -> EncodedArchitecturalState:
    """Test helper for proving every architectural field participates in comparison."""
    return replace(state, **changes)

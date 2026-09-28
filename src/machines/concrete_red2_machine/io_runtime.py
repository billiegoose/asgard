"""Scheduler-side RED2 host dispatch for encoded Concrete/Synth states."""

from __future__ import annotations

from abstract_red2_machine.io_runtime import Red2IoHost, dispatch_red2_host_call
from abstract_red2_machine.machine import AbstractRED2Machine, MuredHostCall
from concrete_red2_machine import abi
from concrete_red2_machine.pipelinec_vectors import (
    EncodedArchitecturalState,
    RED2ABICodec,
)

HOST_NAMES = {
    abi.HOST_CLOCK: "CLOCK",
    abi.HOST_UART_RX: "UART-RX",
    abi.HOST_UART_TX: "UART-TX",
    abi.HOST_UART_TX_BYTES: "UART-TX-BYTES",
}


def encoded_host_call(state: EncodedArchitecturalState) -> MuredHostCall:
    """Decode the scheduler-visible pending host call from RED2_ABI_V1 state."""
    name = HOST_NAMES.get(state.pending_host_op)
    if name is None:
        raise ValueError(f"unknown RED2 host op: {state.pending_host_op}")
    argument_address = None
    if state.pending_host_argument:
        argument_address = abi.decode_optional_address(state.pending_host_argument)
    return MuredHostCall(name, argument_address)


def dispatch_encoded_host_call(
    codec: RED2ABICodec,
    state: EncodedArchitecturalState,
    host: Red2IoHost,
    *,
    working_memory_limit: int,
) -> int:
    """Dispatch one suspended host call without mutating reducer state."""
    decoded = codec.decode_state(state)
    view = AbstractRED2Machine(decoded, working_memory_limit=working_memory_limit)
    result = dispatch_red2_host_call(view, encoded_host_call(state), host)
    return codec.encode_word(result)

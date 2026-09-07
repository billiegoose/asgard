from __future__ import annotations

from collections.abc import Collection, Mapping
from enum import StrEnum
from typing import Protocol

from red2_engine.mured import (
    MuredHostCall,
    MuredMachine,
    MuredOpcode,
    MuredStopReason,
    Word,
)
from thor_lang.ast import Expr


class Red2IoRuntimeError(RuntimeError):
    """Raised when faithful RED2 cannot execute an IO action."""


class Red2RechargeEvent(StrEnum):
    HOST_DISPATCH = "host-dispatch"
    QUANTUM_EXHAUSTED = "quantum-exhausted"


DEFAULT_RED2_RECHARGE_EVENTS = frozenset({Red2RechargeEvent.HOST_DISPATCH})


class Red2IoHost(Protocol):
    def uart_rx(self) -> int | None: ...

    def uart_tx(self, data: bytes) -> None: ...

    def clock_ms(self) -> int: ...


def run_red2_io_action(
    action: Expr,
    *,
    definitions: Mapping[str, Expr],
    quantum: int,
    host: Red2IoHost,
    memory_words: int = 1_048_576,
    recharge_on: Collection[Red2RechargeEvent] = DEFAULT_RED2_RECHARGE_EVENTS,
) -> Expr:
    """Run one effectful THOR/RED2 program on exactly one faithful μRED machine."""
    if quantum <= 0:
        raise Red2IoRuntimeError("RED2 IO quantum must be positive")
    recharge_events = frozenset(recharge_on)

    from thor_compile.red2 import load_faithful_machine

    machine = load_faithful_machine(
        action,
        quantum=quantum,
        definitions=definitions,
        memory_words=memory_words,
    )

    while True:
        stop = machine.run_until_suspend(
            cycle_limit=machine.state.cycles + 2_000_000
        )
        if stop.reason is MuredStopReason.HOST_CALL:
            call = stop.host_call
            if call is None:
                raise Red2IoRuntimeError("host suspension is missing its host call")
            machine.resume_host_call(_dispatch_host_call(machine, call, host))
            if Red2RechargeEvent.HOST_DISPATCH in recharge_events:
                machine.refresh_quantum(quantum)
            continue
        if stop.reason is MuredStopReason.QUANTUM_EXHAUSTED:
            if Red2RechargeEvent.QUANTUM_EXHAUSTED in recharge_events:
                machine.recharge_quantum(quantum)
                continue
            raise Red2IoRuntimeError(
                "RED2 IO quantum exhausted before the next host dispatch"
            )
        if stop.reason is MuredStopReason.COMPLETE:
            return machine.result_expr()
        raise Red2IoRuntimeError(f"unknown faithful RED2 stop reason: {stop.reason}")


def _dispatch_host_call(
    machine: MuredMachine,
    call: MuredHostCall,
    host: Red2IoHost,
) -> Word:
    if call.name == "CLOCK":
        return Word(MuredOpcode.INT, host.clock_ms())
    if call.name == "UART-RX":
        byte = host.uart_rx()
        return (
            Word(MuredOpcode.SYM, "NIL")
            if byte is None
            else Word(MuredOpcode.INT, byte)
        )
    if call.name == "UART-TX":
        operand = _host_argument(machine, call)
        if operand.opcode is not MuredOpcode.INT or type(operand.data) is not int:
            raise Red2IoRuntimeError("UART-TX expects an integer byte")
        host.uart_tx(bytes((operand.data % 256,)))
        return Word(MuredOpcode.SYM, "NIL")
    if call.name == "UART-TX-BYTES":
        host.uart_tx(_byte_list(machine, call))
        return Word(MuredOpcode.SYM, "NIL")
    raise Red2IoRuntimeError(f"unknown RED2 host primitive: {call.name}")


def _memory_word(machine: MuredMachine, address: int) -> Word:
    memory = machine.state.memory
    if not 0 <= address < len(memory):
        raise Red2IoRuntimeError(f"invalid RED2 host argument address: {address}")
    word = memory[address]
    if word is None:
        raise Red2IoRuntimeError(f"missing RED2 host argument at address: {address}")
    return word


def _host_argument(machine: MuredMachine, call: MuredHostCall) -> Word:
    address = call.argument_address
    if address is None:
        raise Red2IoRuntimeError(f"{call.name} requires a host argument")
    return _memory_word(machine, address)


def _descriptor_value(
    machine: MuredMachine,
    descriptor: Word,
) -> tuple[Word, int | None]:
    if descriptor.opcode is not MuredOpcode.APP:
        return descriptor, None
    if type(descriptor.data) is not int or descriptor.data < 0:
        raise Red2IoRuntimeError("RED2 host value APP requires a graph address")
    return _memory_word(machine, descriptor.data), descriptor.data


def _byte_list(machine: MuredMachine, call: MuredHostCall) -> bytes:
    descriptor = _host_argument(machine, call)
    result = bytearray()
    visited: set[int] = set()

    while True:
        value, root_address = _descriptor_value(machine, descriptor)
        if value.opcode is MuredOpcode.SYM and value.data == "NIL":
            return bytes(result)
        if (
            value.opcode is not MuredOpcode.STRUCT
            or value.data != "PAIR"
            or root_address is None
        ):
            raise Red2IoRuntimeError("UART-TX-BYTES expects a byte list")
        if root_address in visited:
            raise Red2IoRuntimeError("UART-TX-BYTES encountered a cyclic byte list")
        visited.add(root_address)

        tail_descriptor = _memory_word(machine, root_address + 1)
        head_descriptor = _memory_word(machine, root_address + 2)
        head, _ = _descriptor_value(machine, head_descriptor)
        if head.opcode is not MuredOpcode.INT or type(head.data) is not int:
            raise Red2IoRuntimeError("UART-TX-BYTES expects integer bytes")
        result.append(head.data % 256)
        descriptor = tail_descriptor

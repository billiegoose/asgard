from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass, field

from red2_engine.io_runtime import Red2IoHost, run_red2_io_action
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import parse_program
from thor_lang.pretty import to_source
from thor_lang.primitives import install_struct_definition


@dataclass
class FakeHost(Red2IoHost):
    rx_values: list[int | None] = field(default_factory=list)
    clock_value: int = 1_700_000_000_789
    writes: list[bytes] = field(default_factory=list)

    def uart_rx(self) -> int | None:
        if not self.rx_values:
            return None
        return self.rx_values.pop(0)

    def uart_tx(self, data: bytes) -> None:
        self.writes.append(data)

    def clock_ms(self) -> int:
        return self.clock_value


def prepare(source: str) -> tuple[Expr, dict[str, Expr]]:
    program = normalize_program(parse_program(source))
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    definitions.pop("CAR", None)
    definitions.pop("CDR", None)
    action: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
        else:
            action = form
    assert action is not None
    return action, definitions


def run(
    source: str,
    host: FakeHost | None = None,
    *,
    quantum: int = 5000,
) -> tuple[str, FakeHost]:
    action, definitions = prepare(source)
    fake = host or FakeHost()
    result = run_red2_io_action(
        action,
        definitions=definitions,
        quantum=quantum,
        host=fake,
    )
    return to_source(result), fake


def test_uart_rx_returns_byte_or_nil() -> None:
    assert run("(UART-RX)", FakeHost(rx_values=[90]))[0] == "90"
    assert run("(UART-RX)", FakeHost(rx_values=[None]))[0] == "NIL"


def test_uart_tx_and_uart_tx_bytes_use_modulo_256() -> None:
    result, host = run("(UART-TX 321)")
    assert result == "NIL"
    assert host.writes == [b"A"]

    result, host = run("(UART-TX-BYTES [65 322 -189])")
    assert result == "NIL"
    assert host.writes == [b"ABC"]


def test_clock_uses_injected_host() -> None:
    result, host = run("(CLOCK)", FakeHost(clock_value=1_700_000_000_789))
    assert result == "1700000000789"
    assert host.writes == []


def test_io_return_bind_and_then() -> None:
    assert run("(IO-RETURN (+ 40 2))")[0] == "42"

    result, host = run(
        "(IO-BIND (UART-RX) (LAMBDA (b) (UART-TX b)))",
        FakeHost(rx_values=[65]),
    )
    assert result == "NIL"
    assert host.writes == [b"A"]

    result, host = run("(IO-THEN (UART-TX 72) (UART-TX 105))")
    assert result == "NIL"
    assert host.writes == [b"H", b"i"]


def test_y_defined_action_chain_is_iterative() -> None:
    source = """
    loop ==
      (Y
        (LAMBDA (self)
          (LAMBDA (n)
            (if (= n 250)
                (IO-RETURN n)
                (IO-THEN (UART-TX 46) (self (+ n 1)))))))
    (loop 0)
    """
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(80)
    try:
        result, host = run(source, quantum=20_000)
    finally:
        sys.setrecursionlimit(previous)
    assert result == "250"
    assert b"".join(host.writes) == b"." * 250


def test_action_exposure_does_not_leak_bound_vars_between_machines() -> None:
    result, host = run(
        "((LAMBDA (x) (IF (= x 1) (UART-TX x) (UART-TX 0))) 1)",
        quantum=20,
    )
    assert result == "NIL"
    assert host.writes == [bytes((1,))]


def test_definitions_and_arithmetic_are_reduced_by_faithful_machine() -> None:
    result, host = run(
        """
        emit == (LAMBDA (n) (UART-TX (+ n 64)))
        (IO-THEN (emit 1) (IO-THEN (emit 2) (emit 3)))
        """
    )
    assert result == "NIL"
    assert b"".join(host.writes) == b"ABC"


def test_red2_io_runtime_has_one_faithful_pure_reduction_seam() -> None:
    import red2_engine.io_runtime as runtime

    source = inspect.getsource(runtime)
    helper = inspect.getsource(runtime._reduce_pure)
    runner = inspect.getsource(runtime.run_red2_io_action)
    assert helper.count("load_faithful_machine(") == 1
    assert ".run(" in helper
    for forbidden in (
        "thor_engine.semantics",
        "ThorDefinitionCache",
        "reduce_expr",
        "_substitute",
    ):
        assert forbidden not in source
    assert "run_red2_io_action(" not in runner.split("def run_red2_io_action", 1)[1]

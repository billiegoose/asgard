from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass, field
from typing import Any

import pytest

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


def test_red2_io_compiles_static_definitions_once_per_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import red2_engine.mured as mured

    source = """
    emit == (LAMBDA (n) (UART-TX (+ n 64)))
    (IO-THEN (emit 1) (IO-THEN (emit 2) (emit 3)))
    """
    action, definitions = prepare(source)
    target = definitions["emit"]
    original = mured.compile_lambda
    compile_count = 0

    def counting_compile(expr: Expr, *args: Any, **kwargs: Any) -> Any:
        nonlocal compile_count
        if expr is target:
            compile_count += 1
        return original(expr, *args, **kwargs)

    monkeypatch.setattr(mured, "compile_lambda", counting_compile)
    host = FakeHost()
    result = run_red2_io_action(
        action,
        definitions=definitions,
        quantum=20_000,
        host=host,
    )

    assert to_source(result) == "NIL"
    assert b"".join(host.writes) == b"ABC"
    assert compile_count == 1


def test_red2_io_memoizes_identical_pure_reductions_within_one_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import thor_compile.red2 as red2_compile

    source = """
    emit == (LAMBDA (n) (UART-TX (+ n 64)))
    (IO-THEN (emit 1) (IO-THEN (emit 1) (emit 1)))
    """
    action, definitions = prepare(source)
    original = red2_compile.load_faithful_machine
    loads: dict[tuple[Expr, int], int] = {}

    def counting_load(
        expr: Expr,
        *,
        quantum: int,
        definitions: Any = None,
        memory_words: int = 65_536,
        control_words: int = 8_192,
    ) -> Any:
        key = (expr, quantum)
        loads[key] = loads.get(key, 0) + 1
        return original(
            expr,
            quantum=quantum,
            definitions=definitions,
            memory_words=memory_words,
            control_words=control_words,
        )

    monkeypatch.setattr(red2_compile, "load_faithful_machine", counting_load)
    host = FakeHost()
    result = run_red2_io_action(
        action,
        definitions=definitions,
        quantum=20_000,
        host=host,
    )

    assert to_source(result) == "NIL"
    assert b"".join(host.writes) == b"AAA"
    assert loads
    assert max(loads.values()) == 1


def test_red2_io_pure_result_cache_is_scoped_to_one_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import thor_compile.red2 as red2_compile

    source = "(IO-RETURN (+ 40 2))"
    action, definitions = prepare(source)
    original = red2_compile.load_faithful_machine
    load_count = 0

    def counting_load(
        expr: Expr,
        *,
        quantum: int,
        definitions: Any = None,
        memory_words: int = 65_536,
        control_words: int = 8_192,
    ) -> Any:
        nonlocal load_count
        load_count += 1
        return original(
            expr,
            quantum=quantum,
            definitions=definitions,
            memory_words=memory_words,
            control_words=control_words,
        )

    monkeypatch.setattr(red2_compile, "load_faithful_machine", counting_load)
    first = run_red2_io_action(
        action,
        definitions=definitions,
        quantum=20_000,
        host=FakeHost(),
    )
    first_count = load_count
    second = run_red2_io_action(
        action,
        definitions=definitions,
        quantum=20_000,
        host=FakeHost(),
    )

    assert to_source(first) == "42"
    assert to_source(second) == "42"
    assert first_count > 0
    assert load_count == first_count * 2

from thor_engine.golden import run_source


def test_red2_partial_lambda_application_does_not_print_pnp() -> None:
    output = run_source("((LAMBDA (X) X) 42)", model="red2", quantum=0)
    assert "PNP" not in output
    assert "LAMBDA" in output
    assert "42" in output


def test_red2_partial_recursive_definition_does_not_print_pnp() -> None:
    source = """
    fib == (lambda (n)
      (if (< n 2)
          n
          (+ (fib (1- n)) (fib (1- (1- n))))))
    (fib 3)
    """
    output = run_source(source, model="red2", quantum=2)
    assert "PNP" not in output


def test_structural_equality_private_symbols_are_machine_only() -> None:
    from thor_compile.red2 import compile_expr, load_faithful_machine
    from thor_lang.parser import parse_expr

    source = "(EQUAL? (F 1 2) (F 1 2))"
    image = compile_expr(parse_expr(source))
    symbol_data = {
        instruction.data
        for instruction in image.instructions
        if isinstance(instruction.data, str)
    }
    assert "EQUAL?" in symbol_data
    assert not any(name.startswith("__EQUAL") for name in symbol_data)

    machine = load_faithful_machine(
        parse_expr(source), quantum=1, memory_words=192, control_words=64
    )
    machine.run()
    live_private = [
        word.data
        for word in machine.state.memory[: machine.state.fsp + 1]
        if word is not None
        and isinstance(word.data, str)
        and word.data.startswith("__EQUAL")
    ]
    assert live_private == []
    assert machine.state.c == -1


def test_residual_forwarding_is_copy_local_and_leaves_no_machine_marker() -> None:
    from red2_engine.mured import (
        Direction,
        MuredMachine,
        MuredMachineState,
        MuredOpcode,
        Word,
    )

    state = MuredMachineState(
        memory=[None] * 24,
        control_stack=[None] * 8,
        pc=0,
        fsp=5,
        env=24,
        free_space=24,
        c=-1,
        direction=Direction.B,
        q=0,
        phi=0,
        halted=True,
    )
    state.memory[0] = Word(MuredOpcode.APP, 3, False)
    state.memory[1] = Word(MuredOpcode.APP, 3, False)
    state.memory[2] = Word(MuredOpcode.SYM, "F", True)
    state.memory[3] = Word(MuredOpcode.INT, 7, True)
    state.memory[4] = Word(MuredOpcode.SYM, "__UNREACHABLE__", True)
    state.memory[5] = Word(MuredOpcode.INT, 999, True)
    machine = MuredMachine(state)
    source_before = tuple(state.memory)

    compact = machine._relinearize_result_graph()

    # Unlike C copy_graph's temporary MARKER forwarding, Python forwarding is
    # copy-local and must not mutate the installed source arena at all.
    assert tuple(state.memory) == source_before
    assert compact == (
        Word(MuredOpcode.APP, 3, False),
        Word(MuredOpcode.APP, 3, False),
        Word(MuredOpcode.SYM, "F", True),
        Word(MuredOpcode.INT, 7, True),
    )

    machine.recharge_quantum(0)

    assert state.memory[0] == Word(MuredOpcode.APP, 3, False)
    assert state.memory[1] == Word(MuredOpcode.APP, 3, False)
    assert state.memory[3] == Word(MuredOpcode.INT, 7, True)
    assert all(
        word is None or word.data != "__UNREACHABLE__"
        for word in state.memory[: state.fsp + 1]
    )

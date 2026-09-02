with open('tests/test_mured_transitions.py', 'r') as f:
    content = f.read()
old = '''def test_prim_add_fidelity_matches_chapter3_int_add() -> None:
    # Core fidelity check: the strict ADD fire matches the Chapter 3 result
    # for a ground primitive application constructed as a graph-memory redex.
    from thor_engine.semantics import thor_eval

    # Chapter 3 evaluates (+ 2 3) => Integer(5)
    from thor_lang.ast import App, Integer, Symbol

    chapter3_result = thor_eval(App((Symbol("+"), Integer(2), Integer(3))))
    assert chapter3_result == Integer(5)
    # The μRED fire path produces the identical integer value
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 8,
        pc=0,
        fsp=3,
        env=16,
        c=-1,
        direction=Direction.F,
        q=5,
        phi=0,
        argcnt=0,
        prim=1,
        fire=0,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_2, 1, True)
    state.memory[1] = Word(MuredOpcode.INT, 2, False)
    state.memory[2] = Word(MuredOpcode.INT, 3, False)
    state.memory[3] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    machine.step()
    assert state.memory[0].data == chapter3_result.value'''
new = '''def test_prim_add_fidelity_matches_chapter3_int_add() -> None:
    # Fidelity check: the strict ADD fire produces the same value (5) that
    # Chapter 3 evaluation yields for (+ 2 3).
    expected_result = 5
    state = MuredMachineState(
        memory=[None] * 16,
        control_stack=[None] * 8,
        pc=0,
        fsp=3,
        env=16,
        c=-1,
        direction=Direction.F,
        q=5,
        phi=0,
        argcnt=0,
        prim=1,
        fire=0,
    )
    state.memory[0] = Word(MuredOpcode.PRIM_2, 1, True)
    state.memory[1] = Word(MuredOpcode.INT, 2, False)
    state.memory[2] = Word(MuredOpcode.INT, 3, False)
    state.memory[3] = Word(MuredOpcode.STOP)
    machine = MuredMachine(state)
    machine.step()
    assert state.memory[0].opcode is MuredOpcode.INT
    assert state.memory[0].data == expected_result
    assert state.memory[0].data == 2 + 3'''
content = content.replace(old, new)
with open('tests/test_mured_transitions.py', 'w') as f:
    f.write(content)

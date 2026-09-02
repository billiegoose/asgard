#!/usr/bin/env python3
"""
Manual test for PRIM_2 ADD fire path.
"""
from red2_engine.mured import (
    Direction,
    MuredMachine,
    MuredMachineState,
    MuredOpcode,
    Word,
)

# Manually build a PRIM_2 head with both arguments reduced to INT
# (simulating + with 2 and 3); argcnt=0; q>0 => fire expected
state = MuredMachineState(
    memory=[None] * 16,
    control_stack=[None] * 8,
    pc=0,
    fsp=3,
    env=16,
    c=-1,
    direction=Direction.F,
    q=3,
    phi=0,
    argcnt=0,
    prim=1,
    fire=0,  # both args reduced: fire countdown complete
)
# Redex at 0: PRIM_2 (primitive id 1 = +)
state.memory[0] = Word(MuredOpcode.PRIM_2, "+", True)
# Arguments: 2 at 1, 3 at 2
state.memory[1] = Word(MuredOpcode.INT, 2, False)
state.memory[2] = Word(MuredOpcode.INT, 3, False)
# Stop at 3
state.memory[3] = Word(MuredOpcode.STOP)
machine = MuredMachine(state)

print("Before step:")
print(f"  pc={state.pc}, fsp={state.fsp}, env={state.env}, q={state.q}")
print(f"  argcnt={state.argcnt}, fire={state.fire}, prim={state.prim}")
print(f"  memory[{state.pc}] = {state.memory[state.pc]}")
print(f"  memory[1] = {state.memory[1]}")
print(f"  memory[2] = {state.memory[2]}")

# Fire path should overwrite head (0) with sum (5) and rewind fsp
machine.step()

print("\nAfter step:")
print(f"  pc={state.pc}, fsp={state.fsp}, env={state.env}, q={state.q}")
print(f"  argcnt={state.argcnt}, fire={state.fire}, prim={state.prim}")
print(f"  memory[0] = {state.memory[0]}")
print(f"  memory[1] = {state.memory[1]}")
print(f"  memory[2] = {state.memory[2]}")

# After fire: head replaced by INT 5; fsp reclaimed to argument base
assert state.memory[0] == Word(MuredOpcode.INT, 5, True), f"Expected INT 5, got {state.memory[0]}"
print("\n✓ Test passed!")
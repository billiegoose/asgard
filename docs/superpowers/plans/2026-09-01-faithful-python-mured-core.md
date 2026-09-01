# Faithful Python μRED Core Implementation Plan

> **For agentic workers:** Parallel execution: use `ultrapowers:ultrapowers` (this plan carries ultraplan markers). Sequential fallback: superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an isolated Python μRED machine that executes the pure λ-calculus Chapter 4 instruction transitions directly over graph memory, environment memory, and a control stack.

**Architecture:** Create `red2_engine.mured` as a new executable machine specification, leaving the current evaluator-backed `Red2Machine` and all CLIs unchanged. Build the fixed memory/register model first, add literal instruction transitions and `LOOKUP`, then add pure-lambda compilation, halted-result decompilation, and manually derived cycle traces.

**Tech Stack:** Python 3.14, frozen/slotted dataclasses, pytest, Ruff, mypy

**Spec:** `docs/superpowers/specs/2026-09-01-faithful-python-mured-core-design.md`

**Acceptance:** suite — the committed instruction-transition, boundary, golden-trace, anti-shortcut, and semantic-comparison tests are the acceptance contract for this internal machine core.

## Global Constraints

- The implementation must execute Chapter 4 graph-memory instructions and register transfers directly.
- It must not decode the instruction graph into an AST or private term graph for evaluation.
- Shared memory is fixed-size, with graph memory growing upward and the environment growing downward.
- The control stack is fixed-size and separate from shared memory.
- `step()` executes exactly one fetched instruction transition; `run()` adds no semantics.
- AST conversion is allowed only before loading and after halt.
- Quantum changes only at contractions identified by the thesis rules.
- The existing `red2_engine.machine.Red2Machine`, CLIs, `.red2` format, and Rust crate remain unchanged.
- Python remains `>=3.14`; add no runtime dependencies.

---

### Task 1: Establish μRED words, machine state, loading, and bounded storage

**Type:** implementation
**Depends-on:** none

**Files:**
- Create: `models/python/red2_engine/mured.py`
- Create: `tests/test_mured_state.py`

**Interfaces:**
- Consumes: no new project interfaces
- Produces: `MuredOpcode`, `Direction`, `Word`, `MuredMachineState`, `MuredMachine.load(problem: Sequence[Word], *, quantum: int, memory_words: int = 256, control_words: int = 64) -> MuredMachine`, `MuredMachine.step() -> MuredMachineState`, `MuredMachine.run(*, cycle_limit: int = 100_000) -> MuredMachineState`, and the `MuredMachineError` hierarchy

This is intentionally the common contract for every later task. It is a good standalone boundary even without parallel execution because it fixes address, empty-stack, and region conventions before instruction semantics are introduced.

**Parallelization rationale:** Later transition and compiler work can rely on one explicit machine-state contract rather than inventing incompatible storage conventions.

- [ ] **Step 1: Add failing loader and boundary tests**

Create `tests/test_mured_state.py` with these exact contracts:

```python
import pytest

from red2_engine.mured import (
    Direction,
    GraphEnvironmentCollision,
    IllegalTransition,
    MuredMachine,
    MuredOpcode,
    Word,
)


def test_load_places_problem_stop_and_registers() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.LAMBDA, "x"), Word(MuredOpcode.VAR, 0)],
        quantum=7,
        memory_words=16,
        control_words=4,
    )

    state = machine.state
    assert state.memory[:3] == [
        Word(MuredOpcode.LAMBDA, "x"),
        Word(MuredOpcode.VAR, 0),
        Word(MuredOpcode.STOP),
    ]
    assert state.pc == 0
    assert state.fsp == 2
    assert state.env == 16
    assert state.c == -1
    assert state.direction is Direction.F
    assert state.q == 7
    assert state.phi == 0
    assert state.s_a is None
    assert state.s_d is None
    assert state.cycles == 0
    assert state.halted is False


def test_load_rejects_problem_that_meets_environment() -> None:
    with pytest.raises(GraphEnvironmentCollision, match="graph and environment collide"):
        MuredMachine.load(
            [Word(MuredOpcode.VAR, 0)] * 4,
            quantum=1,
            memory_words=4,
        )


def test_step_rejects_unsupported_transition_before_incrementing_cycle() -> None:
    machine = MuredMachine.load(
        [Word(MuredOpcode.VAR, 0)],
        quantum=1,
        memory_words=8,
    )

    with pytest.raises(
        IllegalTransition,
        match="VAR transition is not implemented",
    ):
        machine.step()
    assert machine.state.cycles == 0
```

- [ ] **Step 2: Run the tests and verify the module is absent**

Run:

```bash
uv run pytest tests/test_mured_state.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'red2_engine.mured'`.

- [ ] **Step 3: Implement the exact state contract and loader**

Create `models/python/red2_engine/mured.py` with:

```python
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum, auto


class MuredOpcode(StrEnum):
    APP = auto()
    CLOSURE = auto()
    JOIN = auto()
    LAMBDA = auto()
    STOP = auto()
    UBV = auto()
    VAR = auto()
    PNP = auto()


class Direction(StrEnum):
    F = auto()
    B = auto()


@dataclass(frozen=True, slots=True)
class Word:
    opcode: MuredOpcode | None
    data: int | str | None = None


class MuredMachineError(RuntimeError):
    pass


class InvalidAddress(MuredMachineError):
    pass


class GraphEnvironmentCollision(MuredMachineError):
    pass


class ControlStackOverflow(MuredMachineError):
    pass


class ControlStackUnderflow(MuredMachineError):
    pass


class MalformedClosure(MuredMachineError):
    pass


class IllegalTransition(MuredMachineError):
    pass


class CycleLimitExceeded(MuredMachineError):
    pass


@dataclass(slots=True)
class MuredMachineState:
    memory: list[Word | None]
    control_stack: list[int | None]
    pc: int
    fsp: int
    env: int
    c: int
    direction: Direction
    q: int
    phi: int
    s_a: int | None = None
    s_d: int | None = None
    halted: bool = False
    cycles: int = 0


class MuredMachine:
    def __init__(self, state: MuredMachineState) -> None:
        self.state = state

    @classmethod
    def load(
        cls,
        problem: Sequence[Word],
        *,
        quantum: int,
        memory_words: int = 256,
        control_words: int = 64,
    ) -> "MuredMachine":
        if quantum < 0:
            raise ValueError("quantum must be non-negative")
        if memory_words <= 0:
            raise ValueError("memory_words must be positive")
        if control_words <= 0:
            raise ValueError("control_words must be positive")
        if not problem:
            raise ValueError("problem graph must not be empty")
        allowed = {MuredOpcode.APP, MuredOpcode.LAMBDA, MuredOpcode.VAR}
        if any(word.opcode not in allowed for word in problem):
            raise ValueError("problem graph contains a non-μRED source instruction")
        stop_address = len(problem)
        if stop_address >= memory_words:
            raise GraphEnvironmentCollision("graph and environment collide")
        memory: list[Word | None] = [None] * memory_words
        memory[:stop_address] = problem
        memory[stop_address] = Word(MuredOpcode.STOP)
        return cls(
            MuredMachineState(
                memory=memory,
                control_stack=[None] * control_words,
                pc=0,
                fsp=stop_address,
                env=memory_words,
                c=-1,
                direction=Direction.F,
                q=quantum,
                phi=0,
            )
        )

    def step(self) -> MuredMachineState:
        state = self.state
        if state.halted:
            return state
        word = self._word(state.pc)
        name = word.opcode.name if word.opcode is not None else "pointer"
        raise IllegalTransition(f"{name} transition is not implemented")

    def run(self, *, cycle_limit: int = 100_000) -> MuredMachineState:
        if cycle_limit < 0:
            raise ValueError("cycle_limit must be non-negative")
        while not self.state.halted:
            if self.state.cycles >= cycle_limit:
                raise CycleLimitExceeded(
                    f"μRED cycle limit reached: {cycle_limit}"
                )
            self.step()
        return self.state

    def _word(self, address: int) -> Word:
        if not 0 <= address < len(self.state.memory):
            raise InvalidAddress(f"invalid μRED address: {address}")
        word = self.state.memory[address]
        if word is None:
            raise InvalidAddress(f"uninitialized μRED address: {address}")
        return word
```

Keep `Word.opcode` optional because the second closure word has a data field but no executable opcode in Chapter 4.

- [ ] **Step 4: Run focused tests and static checks**

Run:

```bash
uv run pytest tests/test_mured_state.py -q
uv run ruff check models/python/red2_engine/mured.py tests/test_mured_state.py
uv run mypy models/python/red2_engine/mured.py tests/test_mured_state.py
```

Expected: all commands pass.

- [ ] **Step 5: Commit the state foundation**

```bash
git add models/python/red2_engine/mured.py tests/test_mured_state.py
git commit -m "feat: add faithful mured machine state"
```

---

### Task 2: Implement Chapter 4 instruction transitions and LOOKUP

**Type:** implementation
**Depends-on:** 1
**Review:** adversarial

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Create: `tests/test_mured_transitions.py`
- Create: `docs/mured-thesis-notes.md`

**Interfaces:**
- Consumes: `MuredMachine`, `MuredMachineState`, `MuredOpcode`, `Direction`, `Word`, and machine errors from Task 1
- Produces: `MuredMachine.lookup(index: int) -> int`, complete `MuredMachine.step() -> MuredMachineState`, and literal `APP`, `CLOSURE`, `JOIN`, `LAMBDA`, `STOP`, `UBV`, `VAR`, and `PNP` behavior

This task is cohesive because instruction handlers share `pc`, `fsp`, `env`, and control-stack invariants; splitting them would make intermediate machine states unverifiable. Verify the printed source PDF pages 50–56 visually before coding. The transcription is a guide, not authority.

- [ ] **Step 1: Add exact single-transition and LOOKUP tests**

Create `tests/test_mured_transitions.py`. Include a local helper that loads a legal problem and then installs the explicit state needed by each one-cycle test:

```python
import pytest

from red2_engine.mured import (
    ControlStackUnderflow,
    Direction,
    IllegalTransition,
    MuredMachine,
    MuredOpcode,
    Word,
)


def base_machine() -> MuredMachine:
    return MuredMachine.load(
        [Word(MuredOpcode.LAMBDA, "x"), Word(MuredOpcode.VAR, 0)],
        quantum=3,
        memory_words=32,
        control_words=8,
    )


def test_app_forward_copies_word_saves_env_and_advances() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[0] = Word(MuredOpcode.APP, 9)

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP, 9)
    assert state.fsp == 3
    assert state.control_stack[0] == 32
    assert state.c == 0
    assert state.pc == 1
    assert state.direction is Direction.F
    assert state.cycles == 1


def test_app_reverse_creates_join_with_parent_pointer() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.memory[9] = Word(MuredOpcode.VAR, 0)
    state.pc = 3
    state.fsp = 3
    state.env = 20
    state.control_stack[0] = 27
    state.c = 0
    state.direction = Direction.B

    machine.step()

    assert state.env == 27
    assert state.c == -1
    assert state.memory[4] == Word(MuredOpcode.JOIN, 3)
    assert state.fsp == 4
    assert state.pc == 9
    assert state.direction is Direction.F


def test_lookup_skips_ubv_closure_and_follows_parent_pointer() -> None:
    machine = base_machine()
    state = machine.state
    state.env = 20
    state.memory[20] = Word(MuredOpcode.UBV, 3)
    state.memory[21] = Word(MuredOpcode.CLOSURE, 28)
    state.memory[22] = Word(None, 7)
    state.memory[23] = Word(MuredOpcode.PNP, 27)
    state.memory[27] = Word(MuredOpcode.UBV, 1)

    assert machine.lookup(0) == 20
    assert machine.lookup(1) == 21
    assert machine.lookup(2) == 27
    assert state.s_d == 0
    assert state.s_a == 27


def test_lambda_contracts_against_result_app() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.control_stack[0] = 32
    state.c = 0
    state.fsp = 3

    machine.step()

    assert state.q == 2
    assert state.fsp == 2
    assert state.c == -1
    assert state.env == 30
    assert state.memory[30] == Word(MuredOpcode.CLOSURE, 32)
    assert state.memory[31] == Word(None, 9)
    assert state.pc == 1


def test_lambda_without_redex_copies_and_allocates_ubv() -> None:
    machine = base_machine()
    state = machine.state

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.LAMBDA, "x")
    assert state.fsp == 3
    assert state.memory[31] == Word(MuredOpcode.UBV, 1)
    assert state.env == 31
    assert state.phi == 1
    assert state.pc == 1


def test_var_uses_lookup_and_executes_environment_value() -> None:
    machine = base_machine()
    state = machine.state
    state.pc = 1
    state.env = 31
    state.memory[31] = Word(MuredOpcode.UBV, 1)
    state.phi = 1

    machine.step()

    assert state.s_d == 0
    assert state.s_a == 31
    assert state.pc == 31


def test_ubv_emits_var_and_switches_to_reverse() -> None:
    machine = base_machine()
    state = machine.state
    state.pc = 31
    state.env = 31
    state.memory[31] = Word(MuredOpcode.UBV, 1)
    state.phi = 1
    state.fsp = 3

    machine.step()

    assert state.memory[4] == Word(MuredOpcode.VAR, 0)
    assert state.fsp == 4
    assert state.pc == 3
    assert state.direction is Direction.B


def test_join_inserts_argument_root_and_walks_parent_backward() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[4] = Word(MuredOpcode.JOIN, 3)
    state.memory[5] = Word(MuredOpcode.VAR, 0)
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.pc = 4
    state.fsp = 5
    state.direction = Direction.B

    machine.step()

    assert state.memory[3] == Word(MuredOpcode.APP, 5)
    assert state.s_a == 5
    assert state.pc == 2


def test_closure_adds_parent_path_and_jumps_to_code() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[20] = Word(MuredOpcode.CLOSURE, 27)
    state.memory[21] = Word(None, 9)
    state.memory[9] = Word(MuredOpcode.VAR, 0)
    state.pc = 20
    state.env = 20

    machine.step()

    assert state.env == 19
    assert state.memory[19] == Word(MuredOpcode.PNP, 27)
    assert state.pc == 9


def test_stop_is_reverse_only_and_points_pc_at_result_root() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.LAMBDA, "x")
    state.pc = 2
    state.fsp = 3
    state.direction = Direction.B

    machine.step()

    assert state.halted is True
    assert state.pc == 3
    assert state.cycles == 1


def test_reverse_app_requires_saved_environment() -> None:
    machine = base_machine()
    state = machine.state
    state.memory[3] = Word(MuredOpcode.APP, 9)
    state.pc = 3
    state.fsp = 3
    state.direction = Direction.B

    with pytest.raises(ControlStackUnderflow):
        machine.step()
    assert state.cycles == 0


def test_stop_rejects_forward_execution() -> None:
    machine = base_machine()
    state = machine.state
    state.pc = 2

    with pytest.raises(IllegalTransition, match="STOP requires backward execution"):
        machine.step()
```

- [ ] **Step 2: Run transition tests and verify that dispatch is missing**

Run:

```bash
uv run pytest tests/test_mured_transitions.py -q
```

Expected: tests fail because `lookup` is absent and `step()` still raises the Task 1 unsupported-transition error.

- [ ] **Step 3: Implement exact storage helpers and LOOKUP**

Add helpers with these signatures and effects:

```python
def _push_graph(self, word: Word) -> int:
    address = self.state.fsp + 1
    if address >= self.state.env:
        raise GraphEnvironmentCollision("graph and environment collide")
    self.state.memory[address] = word
    self.state.fsp = address
    return address


def _allocate_environment(self, word: Word) -> int:
    address = self.state.env - 1
    if address <= self.state.fsp:
        raise GraphEnvironmentCollision("graph and environment collide")
    self.state.memory[address] = word
    self.state.env = address
    return address


def _push_control(self, address: int) -> None:
    next_c = self.state.c + 1
    if next_c >= len(self.state.control_stack):
        raise ControlStackOverflow("μRED control stack overflow")
    self.state.control_stack[next_c] = address
    self.state.c = next_c


def _pop_control(self) -> int:
    if self.state.c < 0:
        raise ControlStackUnderflow("μRED control stack underflow")
    value = self.state.control_stack[self.state.c]
    self.state.control_stack[self.state.c] = None
    self.state.c -= 1
    if value is None:
        raise ControlStackUnderflow("μRED control stack entry is empty")
    return value


def lookup(self, index: int) -> int:
    if index < 0:
        raise InvalidAddress(f"negative μRED variable index: {index}")
    self.state.s_d = index
    address = self.state.env
    while True:
        word = self._word(address)
        if word.opcode is MuredOpcode.PNP:
            if not isinstance(word.data, int):
                raise InvalidAddress("PNP requires an address")
            address = word.data
            continue
        if self.state.s_d == 0:
            self.state.s_a = address
            return address
        self.state.s_d -= 1
        address += 1 if word.opcode is MuredOpcode.UBV else 2
```

Do not represent the environment as Python closures or tuples.

- [ ] **Step 4: Implement exact instruction dispatch and transitions**

Replace the unsupported `step()` body with explicit opcode dispatch. Every handler must validate its legal direction before mutating state. Increment `cycles` only after a successful transition.

```python
def step(self) -> MuredMachineState:
    state = self.state
    if state.halted:
        return state
    self._validate_state()
    word = self._word(state.pc)
    match word.opcode:
        case MuredOpcode.APP:
            self._app(word)
        case MuredOpcode.CLOSURE:
            self._closure(word)
        case MuredOpcode.JOIN:
            self._join(word)
        case MuredOpcode.LAMBDA:
            self._lambda(word)
        case MuredOpcode.STOP:
            self._stop()
        case MuredOpcode.UBV:
            self._ubv(word)
        case MuredOpcode.VAR:
            self._var(word)
        case MuredOpcode.PNP | None:
            raise IllegalTransition(f"{word.opcode} is environment data")
    self._validate_state()
    state.cycles += 1
    return state


def _validate_state(self) -> None:
    state = self.state
    size = len(state.memory)
    if not 0 <= state.fsp < state.env <= size:
        raise GraphEnvironmentCollision("graph and environment collide")
    if not -1 <= state.c < len(state.control_stack):
        raise InvalidAddress(f"invalid μRED control pointer: {state.c}")
    if state.q < 0 or state.phi < 0:
        raise IllegalTransition("μRED counters must be non-negative")
    self._word(state.pc)
```

Implement the register transfers exactly as follows:

```python
def _app(self, word: Word) -> None:
    state = self.state
    if state.direction is Direction.F:
        self._push_graph(word)
        self._push_control(state.env)
        state.pc += 1
        return
    if not isinstance(word.data, int):
        raise InvalidAddress("APP requires an argument address")
    parent_app = state.pc
    state.env = self._pop_control()
    self._push_graph(Word(MuredOpcode.JOIN, parent_app))
    state.pc = word.data
    state.direction = Direction.F


def _closure(self, word: Word) -> None:
    if self.state.direction is not Direction.F:
        raise IllegalTransition("CLOSURE requires forward execution")
    if not isinstance(word.data, int):
        raise MalformedClosure("CLOSURE requires an environment address")
    code = self._word(self.state.pc + 1)
    if code.opcode is not None or not isinstance(code.data, int):
        raise MalformedClosure("CLOSURE requires a following code pointer")
    self._allocate_environment(Word(MuredOpcode.PNP, word.data))
    self.state.pc = code.data


def _join(self, word: Word) -> None:
    if self.state.direction is not Direction.B:
        raise IllegalTransition("JOIN requires backward execution")
    if not isinstance(word.data, int):
        raise InvalidAddress("JOIN requires a parent APP address")
    self.state.s_a = self.state.pc + 1
    parent = self._word(word.data)
    if parent.opcode is not MuredOpcode.APP:
        raise IllegalTransition("JOIN parent must be APP")
    self.state.memory[word.data] = Word(MuredOpcode.APP, self.state.s_a)
    self.state.pc = word.data - 1


def _lambda(self, word: Word) -> None:
    state = self.state
    if state.direction is Direction.B:
        state.phi -= 1
        if state.phi < 0:
            raise IllegalTransition("LAMBDA reverse underflows phi")
        state.pc -= 1
        return
    result_head = self._word(state.fsp)
    if state.q == 0 or result_head.opcode is not MuredOpcode.APP:
        self._push_graph(word)
        state.phi += 1
        self._allocate_environment(Word(MuredOpcode.UBV, state.phi))
        state.pc += 1
        return
    if not isinstance(result_head.data, int):
        raise InvalidAddress("result APP requires an argument address")
    saved_path = self._pop_control()
    self._allocate_environment(Word(None, result_head.data))
    self._allocate_environment(Word(MuredOpcode.CLOSURE, saved_path))
    state.q -= 1
    state.fsp -= 1
    state.pc += 1


def _stop(self) -> None:
    if self.state.direction is not Direction.B:
        raise IllegalTransition("STOP requires backward execution")
    self.state.pc += 1
    self.state.halted = True


def _ubv(self, word: Word) -> None:
    if self.state.direction is not Direction.F:
        raise IllegalTransition("UBV requires forward execution")
    if not isinstance(word.data, int):
        raise InvalidAddress("UBV requires a binder depth")
    self._push_graph(Word(MuredOpcode.VAR, self.state.phi - word.data))
    self.state.pc = self.state.fsp - 1
    self.state.direction = Direction.B


def _var(self, word: Word) -> None:
    if self.state.direction is not Direction.F:
        raise IllegalTransition("VAR requires forward execution")
    if not isinstance(word.data, int):
        raise InvalidAddress("VAR requires a De Bruijn index")
    self.state.pc = self.lookup(word.data)
```

The dispatch must reject fetching `PNP` or an opcode-less pointer as executable instructions. The `APP` reverse handler deliberately writes `JOIN.data = parent_app`; Figure 4.9 and the `JOIN` procedure require this pointer although the printed APP pseudocode only shows assignment of the opcode. The non-contracting forward `LAMBDA` deliberately advances `pc`; otherwise Rule C1 loops forever. `STOP` deliberately advances `pc` to the first result word before halting, matching the prose that the halted `pc` points to the result root.

- [ ] **Step 5: Document the three source reconciliations**

Create `docs/mured-thesis-notes.md` with a section titled `## μRED source reconciliations` and record exactly:

1. Reverse `APP` creates `JOIN(parent_app)` because Figure 4.9 draws that pointer and `JOIN` later dereferences it, although the APP pseudocode only assigns the opcode.
2. A non-contracting forward `LAMBDA` advances `pc` after copying itself and allocating `UBV`; omission would repeat the same instruction forever.
3. Reverse `STOP` advances `pc` from the sentinel to the first result word before halt so the halted `pc` identifies the result root as the execution-model prose requires.

State that these are narrow reconciliations of internally incomplete pseudocode, not evaluator shortcuts.

- [ ] **Step 6: Run transition, state, lint, and type gates**

Run:

```bash
uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py -q
uv run ruff check models/python/red2_engine/mured.py tests/test_mured_state.py tests/test_mured_transitions.py
uv run mypy models/python/red2_engine/mured.py tests/test_mured_state.py tests/test_mured_transitions.py
```

Expected: all commands pass.

- [ ] **Step 7: Commit literal μRED execution**

```bash
git add models/python/red2_engine/mured.py tests/test_mured_transitions.py docs/mured-thesis-notes.md
git commit -m "feat: execute core mured transitions"
```

---

### Task 3: Add pure-lambda compilation and halted-result decompilation

**Type:** implementation
**Depends-on:** 2

**Files:**
- Modify: `models/python/red2_engine/mured.py`
- Create: `tests/test_mured_compile.py`

**Interfaces:**
- Consumes: completed `MuredMachine` transition loop from Task 2 and `thor_lang.ast.App`, `Lambda`, `Var`, `Expr`
- Produces: `compile_lambda(expr: Expr) -> tuple[Word, ...]`, `MuredMachine.from_expr(expr: Expr, *, quantum: int, memory_words: int = 256, control_words: int = 64) -> MuredMachine`, and `MuredMachine.result_expr() -> Expr`

Compilation and decompilation are kept in `mured.py` for this baby-step milestone so the complete executable specification remains inspectable in one file. Neither function may be called from `step()` or an instruction handler.

- [ ] **Step 1: Add failing compiler-shape tests**

Create `tests/test_mured_compile.py`:

```python
import pytest

from red2_engine.mured import MuredMachine, MuredOpcode, Word, compile_lambda
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def test_compile_lambda_uses_linear_body_and_operator_layout() -> None:
    assert compile_lambda(parse_expr("(LAMBDA (x) x)")) == (
        Word(MuredOpcode.LAMBDA, "x"),
        Word(MuredOpcode.VAR, 0),
    )
    assert compile_lambda(parse_expr("((LAMBDA (x) x) (LAMBDA (y) y))")) == (
        Word(MuredOpcode.APP, 3),
        Word(MuredOpcode.LAMBDA, "x"),
        Word(MuredOpcode.VAR, 0),
        Word(MuredOpcode.LAMBDA, "y"),
        Word(MuredOpcode.VAR, 0),
    )


def test_compile_lambda_rejects_non_lambda_calculus_values() -> None:
    with pytest.raises(TypeError, match="pure λ-calculus expression required"):
        compile_lambda(parse_expr("42"))


def test_identity_application_runs_and_decompiles_after_halt() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("((LAMBDA (x) x) (LAMBDA (y) y))"),
        quantum=10,
        memory_words=64,
    )
    machine.run()

    assert machine.state.halted is True
    assert machine.state.q == 9
    assert to_source(machine.result_expr()) == "(LAMBDA (y) y)"


def test_result_expr_requires_halt() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("(LAMBDA (x) x)"),
        quantum=10,
    )
    with pytest.raises(RuntimeError, match="result is available only after halt"):
        machine.result_expr()
```

- [ ] **Step 2: Run compiler tests and verify imports fail**

Run:

```bash
uv run pytest tests/test_mured_compile.py -q
```

Expected: collection fails because `compile_lambda` and `from_expr` do not exist.

- [ ] **Step 3: Implement deterministic pure-lambda compilation**

Implement `compile_lambda` with a private compiler that mirrors the Chapter 4 linear graph convention:

- `Var(index, name)` emits `Word(VAR, index)`.
- Compilation carries an explicit tuple of binder names. A `Symbol` found in that tuple emits `Word(VAR, scope.index(symbol.name))`; an unbound source `Symbol` raises `TypeError("free source symbols require explicit Var")`.
- Each lambda parameter emits one sequential `Word(LAMBDA, parameter_name)` before its body and prepends those parameters to the compiler scope.
- An application of operator plus N arguments emits N sequential `APP` words, then the operator, then each argument graph; patch each `APP.data` with its argument start address.
- An empty or one-item `App` is rejected as malformed pure λ-calculus input.
- Every other Thor AST type raises `TypeError(f"pure λ-calculus expression required, got {type(expr).__name__}")`.

Add:

```python
@classmethod
def from_expr(
    cls,
    expr: Expr,
    *,
    quantum: int,
    memory_words: int = 256,
    control_words: int = 64,
) -> "MuredMachine":
    return cls.load(
        compile_lambda(expr),
        quantum=quantum,
        memory_words=memory_words,
        control_words=control_words,
    )
```

- [ ] **Step 4: Implement post-halt result decompilation**

Implement a private graph parser that starts at halted `state.pc`, carries `scope: tuple[str, ...]`, and returns `(Expr, next_sequential_address)`. It must:

- parse consecutive `APP` words as a spine, parse the sequential operator, and parse each argument through its address;
- parse consecutive `LAMBDA` words as binders, prepend them to `scope`, and then parse one body graph;
- parse `VAR(index)` as `Var(index, scope[index])` when the index is in scope, or as `Var(index)` when it is genuinely free;
- reject environment-only words, `JOIN`, `STOP`, and opcode-less words in a result graph;
- detect pointer cycles with an address set and raise `MuredMachineError("cyclic μRED result graph")`.

Expose:

```python
def result_expr(self) -> Expr:
    if not self.state.halted:
        raise MuredMachineError("result is available only after halt")
    expr, _ = self._decompile(self.state.pc, (), frozenset())
    return expr
```

Do not call `result_expr`, `_decompile`, or any Thor evaluator from `step()` or `run()`.

- [ ] **Step 5: Run compiler and transition gates**

Run:

```bash
uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py tests/test_mured_compile.py -q
uv run ruff check models/python/red2_engine/mured.py tests/test_mured_*.py
uv run mypy models/python/red2_engine/mured.py tests/test_mured_*.py
```

Expected: all commands pass.

- [ ] **Step 6: Commit the input/output boundary**

```bash
git add models/python/red2_engine/mured.py tests/test_mured_compile.py
git commit -m "feat: compile and inspect pure lambda graphs"
```

---

### Task 4: Seal fidelity with a manual golden trace, semantic corpus, and anti-shortcut checks

**Type:** implementation
**Depends-on:** 3
**Review:** adversarial

**Files:**
- Create: `tests/test_mured_fidelity.py`
- Modify: `docs/thor-red2-prototype.md`
- Modify: `models/python/red2_engine/__init__.py`

**Interfaces:**
- Consumes: `MuredMachine.from_expr`, `MuredMachine.step`, `MuredMachine.result_expr`, and public μRED types from Tasks 1–3
- Produces: public package exports for `MuredMachine`, `MuredMachineState`, `MuredOpcode`, and `Word`; committed fidelity and anti-shortcut acceptance tests

This task does not alter machine semantics. It establishes evidence that the new path executes instruction cycles and clearly distinguishes it from the legacy evaluator-backed `Red2Machine`.

- [ ] **Step 1: Add the manually derived cycle trace**

Create `tests/test_mured_fidelity.py` with this trace for `(LAMBDA (x) x)`. Each tuple is captured immediately before the fetched instruction executes:

```python
from pathlib import Path

import pytest

from red2_engine.mured import Direction, MuredMachine, MuredOpcode
from thor_engine.semantics import reduce_expr
from thor_lang.parser import parse_expr
from thor_lang.pretty import to_source


def snapshot(machine: MuredMachine) -> tuple[object, ...]:
    state = machine.state
    word = state.memory[state.pc]
    assert word is not None
    return (
        state.cycles,
        word.opcode,
        state.direction,
        state.pc,
        state.fsp,
        state.env,
        state.c,
        state.q,
        state.phi,
    )


def test_closed_identity_matches_manual_chapter4_cycle_trace() -> None:
    machine = MuredMachine.from_expr(
        parse_expr("(LAMBDA (x) x)"),
        quantum=10,
        memory_words=32,
        control_words=8,
    )
    trace: list[tuple[object, ...]] = []
    while not machine.state.halted:
        trace.append(snapshot(machine))
        machine.step()

    assert trace == [
        (0, MuredOpcode.LAMBDA, Direction.F, 0, 2, 32, -1, 10, 0),
        (1, MuredOpcode.VAR, Direction.F, 1, 3, 31, -1, 10, 1),
        (2, MuredOpcode.UBV, Direction.F, 31, 3, 31, -1, 10, 1),
        (3, MuredOpcode.LAMBDA, Direction.B, 3, 4, 31, -1, 10, 1),
        (4, MuredOpcode.STOP, Direction.B, 2, 4, 31, -1, 10, 0),
    ]
    assert machine.state.pc == 3
    assert to_source(machine.result_expr()) == "(LAMBDA (x) x)"
```

This expected trace is the plan’s pinned manual derivation from `LAMBDA`, `VAR`, `UBV`, reverse `LAMBDA`, and `STOP`; do not regenerate it from another evaluator.

- [ ] **Step 2: Add semantic and exhausted-quantum comparisons**

Append exact parametrized cases:

```python
@pytest.mark.parametrize(
    ("source", "quantum"),
    [
        ("(LAMBDA (x) x)", 10),
        ("((LAMBDA (x) x) (LAMBDA (y) y))", 10),
        ("(LAMBDA (x) (LAMBDA (y) x))", 10),
        ("((LAMBDA (x) (LAMBDA (y) x)) (LAMBDA (z) z))", 20),
        ("((LAMBDA (x) (LAMBDA (y) x)) (LAMBDA (z) z))", 1),
        ("((LAMBDA (x) x) (LAMBDA (y) y))", 0),
    ],
)
def test_mured_result_matches_chapter3_for_small_pure_lambda_corpus(
    source: str,
    quantum: int,
) -> None:
    expr = parse_expr(source)
    machine = MuredMachine.from_expr(
        expr,
        quantum=quantum,
        memory_words=128,
    )
    machine.run()
    thor = reduce_expr(expr, quantum=quantum).expr

    assert to_source(machine.result_expr()) == to_source(thor)
```

- [ ] **Step 3: Add static anti-shortcut assertions**

Append:

```python
def test_mured_execution_does_not_depend_on_evaluator_term_graphs() -> None:
    source = Path("models/python/red2_engine/mured.py").read_text()

    assert "from red2_engine.machine" not in source
    assert "_ProgramParser" not in source
    assert "_Term" not in source
    assert "reduce_expr" not in source
    step_body = source[source.index("    def step(") : source.index("    def run(")]
    assert "result_expr" not in step_body
    assert "_decompile" not in step_body
```

- [ ] **Step 4: Run the fidelity test and correct only genuine machine discrepancies**

Run:

```bash
uv run pytest tests/test_mured_fidelity.py -q
```

Expected: PASS. If the manual trace fails, compare the first differing cycle against the printed Chapter 4 transition before changing either implementation or expected data. Do not normalize away a register or memory discrepancy merely to obtain final-result parity.

- [ ] **Step 5: Export the μRED core without replacing legacy APIs**

Modify `models/python/red2_engine/__init__.py` to import and add to `__all__`:

```python
from red2_engine.mured import MuredMachine, MuredMachineState, MuredOpcode, Word
```

Keep `Red2Machine`, `Red2ResourceLimits`, `Instruction`, `Opcode`, and `ProgramImage` exported unchanged.

- [ ] **Step 6: Correct the prototype documentation**

In `docs/thor-red2-prototype.md`:

- state explicitly that `red2_engine.machine.Red2Machine` is the existing evaluator-backed compatibility model and does not execute Chapter 4 register transfers directly;
- add `red2_engine.mured` as the faithful pure-λ μRED core;
- state that the new core is not yet full RED2 and is not wired to the CLI;
- link `docs/mured-thesis-notes.md` for the three source reconciliations;
- remove or narrow any sentence claiming the legacy Python or Rust evaluator is itself a faithful Chapter 4 machine.

Use the exact distinction “semantic parity is not machine fidelity.”

- [ ] **Step 7: Run focused and full verification**

Run:

```bash
uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py tests/test_mured_compile.py tests/test_mured_fidelity.py -q
uv run pytest -q
uv run ruff check .
uv run mypy models/python tests
cargo test -p red2-wasm
```

Expected: all commands pass. Existing Python and Rust evaluators remain behaviorally unchanged.

- [ ] **Step 8: Commit the fidelity boundary**

```bash
git add tests/test_mured_fidelity.py docs/thor-red2-prototype.md models/python/red2_engine/__init__.py
git commit -m "test: establish mured machine fidelity"
```

---

### Task 5: Final verification gate

**Type:** gate
**Depends-on:** 4

**Files:**
- Test: `tests/test_mured_state.py`
- Test: `tests/test_mured_transitions.py`
- Test: `tests/test_mured_compile.py`
- Test: `tests/test_mured_fidelity.py`

**Interfaces:**
- Consumes: the complete μRED core and acceptance tests from Tasks 1–4
- Produces: no code; verifies the integrated milestone

- [ ] **Step 1: Run the complete project gate**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy models/python tests
cargo test -p red2-wasm
```

Expected: every command exits zero.

- [ ] **Step 2: Confirm repository and scope hygiene**

```bash
git status --short
git diff --check "$(git merge-base HEAD main)"..HEAD
rg -n "from red2_engine\.machine|_ProgramParser|reduce_expr" models/python/red2_engine/mured.py || true
```

Expected: no uncommitted files, no whitespace errors, and no forbidden evaluator dependency matches in `mured.py`.

## Operator smoke

- do: `uv run pytest tests/test_mured_fidelity.py::test_closed_identity_matches_manual_chapter4_cycle_trace -q`
- see: the manually derived five-cycle Chapter 4 trace passes.
- do: `uv run pytest tests/test_mured_transitions.py -q`
- see: every individual μRED instruction transition and environment lookup check passes.
- do: `uv run pytest tests/test_mured_compile.py::test_identity_application_runs_and_decompiles_after_halt -q`
- see: a pure lambda application executes to a halted graph and decompiles to `(LAMBDA (y) y)`.

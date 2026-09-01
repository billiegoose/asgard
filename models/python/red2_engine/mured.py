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


class InvalidAddress(MuredMachineError):  # noqa: N818
    pass


class GraphEnvironmentCollision(MuredMachineError):  # noqa: N818
    pass


class ControlStackOverflow(MuredMachineError):  # noqa: N818
    pass


class ControlStackUnderflow(MuredMachineError):  # noqa: N818
    pass


class MalformedClosure(MuredMachineError):  # noqa: N818
    pass


class IllegalTransition(MuredMachineError):  # noqa: N818
    pass


class CycleLimitExceeded(MuredMachineError):  # noqa: N818
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
    ) -> MuredMachine:
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

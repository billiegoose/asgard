from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from abstract_red2_machine.machine import AbstractRED2Machine
from red2.compiler import _generated_struct_selector, compile_lambda
from red2.representation import MuredOpcode, Word
from thor.ast import Expr

@dataclass(frozen=True, slots=True)
class FaithfulDefinitionCache:
    """Precompiled static μRED definition environment reusable across machine loads."""

    memory_words: int
    definition_names: frozenset[str]
    selector_names: frozenset[str]
    struct_selectors: dict[str, tuple[str, int]]
    definition_addresses: dict[str, int]
    static_start: int
    static_words: tuple[tuple[int, Word], ...]


def _relocate_faithful_word(
    word: Word,
    *,
    graph_base: int,
    definition_addresses: Mapping[str, int],
) -> Word:
    """Relocate graph-owned pointers while keeping definition addresses absolute."""
    data = word.data
    if word.opcode in {MuredOpcode.APP, MuredOpcode.RBLOCK}:
        if not isinstance(data, int):
            raise ValueError(f"{word.opcode} requires an address")
        data += graph_base
    definition = word.definition
    if word.opcode is MuredOpcode.SYM and isinstance(word.data, str):
        definition = definition_addresses.get(word.data)
    return Word(word.opcode, data, word.head, definition)


def prepare_faithful_definitions(
    definitions: Mapping[str, Expr] | None,
    *,
    memory_words: int = 1_048_576,
) -> FaithfulDefinitionCache:
    """Compile and relocate the static μRED definition environment once."""
    definition_exprs = {} if definitions is None else dict(definitions)
    struct_selectors = {
        name: selector
        for name, definition in definition_exprs.items()
        if (selector := _generated_struct_selector(definition, definition_exprs))
        is not None
    }
    for name in struct_selectors:
        definition_exprs.pop(name)

    definition_names = frozenset(definition_exprs)
    selector_names = frozenset(struct_selectors)
    compiled_definitions = {
        name: compile_lambda(
            definition,
            definition_names=definition_names,
            unary_primitive_names=selector_names,
        )
        for name, definition in definition_exprs.items()
    }
    reserved_words = sum(len(words) + 1 for words in compiled_definitions.values())
    if reserved_words >= memory_words:
        raise ValueError("faithful definitions exceed μRED memory capacity")

    static_start = memory_words - reserved_words
    definition_addresses: dict[str, int] = {}
    cursor = static_start
    for name, words in compiled_definitions.items():
        definition_addresses[name] = cursor
        cursor += len(words) + 1

    static_words: list[tuple[int, Word]] = []
    cursor = static_start
    for words in compiled_definitions.values():
        base = cursor
        static_words.extend(
            (
                base + offset,
                _relocate_faithful_word(
                    word,
                    graph_base=base,
                    definition_addresses=definition_addresses,
                ),
            )
            for offset, word in enumerate(words)
        )
        static_words.append((base + len(words), Word(MuredOpcode.STOP)))
        cursor += len(words) + 1

    return FaithfulDefinitionCache(
        memory_words=memory_words,
        definition_names=definition_names,
        selector_names=selector_names,
        struct_selectors=struct_selectors,
        definition_addresses=definition_addresses,
        static_start=static_start,
        static_words=tuple(static_words),
    )


def load_faithful_machine(
    expr: Expr,
    *,
    quantum: int,
    definitions: Mapping[str, Expr] | FaithfulDefinitionCache | None = None,
    memory_words: int = 1_048_576,
    control_words: int = 8_192,
    memory_diagnostics: bool = False,
    poison_reclaimed_environment: bool = False,
) -> AbstractRED2Machine:
    """Load one expression plus visible top-level definitions into μRED memory."""
    prepared = (
        definitions
        if isinstance(definitions, FaithfulDefinitionCache)
        else prepare_faithful_definitions(definitions, memory_words=memory_words)
    )
    if prepared.memory_words != memory_words:
        raise ValueError("faithful definition cache memory size does not match machine")

    root_words = compile_lambda(
        expr,
        definition_names=prepared.definition_names,
        unary_primitive_names=prepared.selector_names,
    )
    machine = AbstractRED2Machine.load(
        root_words,
        quantum=quantum,
        memory_words=memory_words,
        control_words=control_words,
        memory_diagnostics=memory_diagnostics,
        poison_reclaimed_environment=poison_reclaimed_environment,
    )
    root_stop = len(root_words)
    if prepared.static_start <= root_stop:
        raise ValueError("faithful program leaves no μRED working memory")

    for address in range(root_stop):
        word = machine.state.memory[address]
        if word is None:
            raise ValueError("faithful root graph contains an uninitialized word")
        machine.state.memory[address] = _relocate_faithful_word(
            word,
            graph_base=0,
            definition_addresses=prepared.definition_addresses,
        )

    for address, word in prepared.static_words:
        machine.state.memory[address] = word

    machine.state.env = prepared.static_start
    machine.state.free_space = prepared.static_start
    machine.working_memory_limit = prepared.static_start
    machine.struct_selectors = prepared.struct_selectors
    return machine

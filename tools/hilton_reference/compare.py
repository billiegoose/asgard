"""Save paired archived HORSE and Asgard graph/lifetime observations."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tools.hilton_reference import program

from abstract_red2_machine.loader import load_faithful_machine
from concrete_red2_machine.cli import _prepare_program
from thor.pretty import to_source


def word_nodes(memory: list, first: int, last: int) -> list[dict]:
    return [
        {
            "address": address,
            "type": word.opcode.value.upper() if word.opcode is not None else None,
            "operand": word.data,
            "head": word.head,
            "definition": word.definition,
            "closure_slot": word.closure_slot,
        }
        for address in range(first, last + 1)
        if (word := memory[address]) is not None
    ]


def compare(
    directory: Path,
    *,
    hilton_source: str,
    asgard_source: str,
    memory_words: int = 256,
    quantum: int = 100_000,
    trace_limit: int = 1000,
) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    old_source = directory / "hilton.lam"
    old_source.write_text(hilton_source + "\n")
    (directory / "asgard.thor").write_text(asgard_source + "\n")
    binary = program.build(directory / "build")
    old = subprocess.run(
        [
            str(binary.resolve()),
            str(program.runner.ARCHIVE / "PRELUDE.LAM"),
            str(old_source.resolve()),
            str(quantum),
            str(memory_words),
            str((directory / "hilton-graphs.jsonl").resolve()),
            str((directory / "hilton-trace.jsonl").resolve()),
            str(trace_limit),
            "0",
            "1",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    (directory / "hilton.stdout").write_text(old.stdout)
    (directory / "hilton.stderr").write_text(old.stderr)
    action, definitions = _prepare_program(asgard_source)
    machine = load_faithful_machine(
        action,
        definitions=definitions,
        quantum=quantum,
        memory_words=memory_words,
        control_words=10_000,
        memory_diagnostics=True,
    )
    state = machine.state
    initial = {
        "stage": "compiled",
        "root": 0,
        "nodes": word_nodes(state.memory, 0, state.fsp - 1),
        "definitions": word_nodes(
            state.memory, machine.working_memory_limit, memory_words - 1
        ),
        "working_memory_limit": machine.working_memory_limit,
    }
    error = None
    result_text = None
    trace_count = 0
    peak_environment = 0
    with (directory / "asgard-trace.jsonl").open("w") as trace:
        try:
            while not state.halted:
                if machine.pending_host_call is not None:
                    raise ValueError("comparison supports pure expressions only")
                if state.cycles >= 2_000_000:
                    raise ValueError("comparison instruction limit reached")
                peak_environment = max(
                    peak_environment, machine.working_memory_limit - state.free_space
                )
                if trace_count < trace_limit:
                    snapshot = {
                        "step": state.cycles,
                        "pc": state.pc,
                        "fsp": state.fsp,
                        "free_space": state.free_space,
                        "env": state.env,
                        "direction": state.direction.value,
                        "stack": state.c,
                        "instruction": word_nodes(state.memory, state.pc, state.pc),
                        "graph": word_nodes(state.memory, 0, state.fsp),
                        "environment": word_nodes(
                            state.memory,
                            state.free_space,
                            machine.working_memory_limit - 1,
                        ),
                    }
                    trace.write(json.dumps(snapshot) + "\n")
                trace_count += 1
                machine.step()
            result_text = to_source(machine.result_expr())
        except (ValueError, RuntimeError) as exception:
            error = f"{type(exception).__name__}: {exception}"
        trace.write(
            json.dumps(
                {
                    "stage": "trace-end",
                    "observed_steps": trace_count,
                    "written_steps": min(trace_count, trace_limit),
                    "truncated": trace_count > trace_limit,
                }
            )
            + "\n"
        )
    final = {
        "stage": "fault" if error else "result",
        "root": state.pc,
        "nodes": word_nodes(state.memory, 0, state.fsp),
        "environment": word_nodes(
            state.memory, state.free_space, machine.working_memory_limit - 1
        ),
        "result_text": result_text,
        "error": error,
        "peak_environment_words": peak_environment,
    }
    (directory / "asgard-graphs.jsonl").write_text(
        json.dumps(initial) + "\n" + json.dumps(final) + "\n"
    )
    report = {
        "memory_words": memory_words,
        "quantum": quantum,
        "hilton": {"exit_code": old.returncode, "result_text": old.stdout.strip()},
        "asgard": {
            "error": error,
            "result_text": result_text,
            "peak_environment_words": peak_environment,
        },
        "printed_results_equal": (
            old.returncode == 0 and error is None and old.stdout.strip() == result_text
        ),
        "interpretation": (
            "HORSE and RED2 have different node layouts, static definitions, and "
            "instruction/quantum accounting. Graph addresses and trace steps are "
            "local to each machine; this report does not assert graph isomorphism."
        ),
    }
    (directory / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hilton-expr", required=True)
    parser.add_argument("--asgard-expr", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-words", type=int, default=256)
    parser.add_argument("--quantum", type=int, default=100_000)
    parser.add_argument("--trace-limit", type=int, default=1000)
    args = parser.parse_args()
    if not 256 <= args.memory_words <= 100_000:
        parser.error("memory-words must be between 256 and 100000")
    if not 0 <= args.quantum <= 2_147_483_647 or args.trace_limit < 0:
        parser.error("invalid quantum or trace-limit")
    print(
        json.dumps(
            compare(
                args.output,
                hilton_source=args.hilton_expr,
                asgard_source=args.asgard_expr,
                memory_words=args.memory_words,
                quantum=args.quantum,
                trace_limit=args.trace_limit,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

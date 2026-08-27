from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from thor_spec import __version__
from thor_spec.ast import Definition, Expr, StructDef
from thor_spec.golden import DEFAULT_QUANTUM, ModelName, run_source
from thor_spec.io_runtime import run_io_source
from thor_spec.lockstep import ParityResult, compare_prefixes
from thor_spec.normalization import normalize_program
from thor_spec.parser import ParseError, parse_program
from thor_spec.pretty import to_source
from thor_spec.red2.binary import decode_bundle, encode_bundle
from thor_spec.red2.compiler import compile_definitions, compile_expr
from thor_spec.red2.machine import Red2Machine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thor-spec",
        description="Executable specification tooling for Hilton's THOR.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--model",
        choices=("thor", "red2", "parity"),
        default="thor",
        help="execution model to run (default: thor)",
    )
    parser.add_argument(
        "--quantum",
        type=int,
        default=DEFAULT_QUANTUM,
        help=f"maximum contraction quantum (default: {DEFAULT_QUANTUM})",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--expr", help="THOR expression or program source to run")
    source_group.add_argument("--file", type=Path, help="path to THOR source to run")
    parser.add_argument(
        "--trace",
        action="store_true",
        help="write deterministic trace metadata to stderr",
    )
    parser.add_argument(
        "--io",
        action="store_true",
        help="run the final expression as a simulated IO action",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "compile-red2":
        return _compile_red2_command(argv[1:])
    if argv and argv[0] == "run-red2":
        return _run_red2_command(argv[1:])
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.expr is None and args.file is None:
        parser.print_help()
        return 0

    try:
        source = args.expr if args.expr is not None else args.file.read_text()
        if args.io:
            return _run_io(source, model_value=args.model, quantum=args.quantum)
        if args.model == "parity":
            return _run_parity(source, quantum=args.quantum)
        model = _model_name(args.model)
        output = run_source(source, model=model, quantum=args.quantum)
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"thor-spec: {error}", file=sys.stderr)
        return 2

    if args.trace:
        _write_trace(
            sys.stderr,
            model=model,
            quantum=args.quantum,
            source_kind="expr" if args.expr is not None else "file",
            output=output,
        )
    if output:
        print(output)
    return 0


def _compile_red2_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="thor-spec compile-red2",
        description="Compile THOR source to a .red2 bytecode image.",
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--expr", help="THOR expression or program source")
    source_group.add_argument("--file", type=Path, help="path to THOR source")
    parser.add_argument("--output", type=Path, required=True, help="output .red2 path")
    args = parser.parse_args(argv)
    try:
        source = args.expr if args.expr is not None else args.file.read_text()
        definitions, final = _split_program(source)
        args.output.write_bytes(
            encode_bundle(compile_expr(final), compile_definitions(definitions))
        )
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"thor-spec: {error}", file=sys.stderr)
        return 2
    print(f"wrote RED2 bytecode: {args.output}", file=sys.stderr)
    return 0


def _run_red2_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="thor-spec run-red2",
        description="Run a .red2 bytecode image with the Python RED2 machine.",
    )
    parser.add_argument("--bytecode", type=Path, required=True, help="input .red2 path")
    parser.add_argument(
        "--quantum",
        type=int,
        default=DEFAULT_QUANTUM,
        help=f"maximum contraction quantum (default: {DEFAULT_QUANTUM})",
    )
    args = parser.parse_args(argv)
    try:
        bundle = decode_bundle(args.bytecode.read_bytes())
        machine = Red2Machine(
            bundle.entry,
            quantum=args.quantum,
            definitions=bundle.definitions,
        )
        machine.run()
        output = to_source(machine.result_expr())
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"thor-spec: {error}", file=sys.stderr)
        return 2
    if output:
        print(output)
    return 0


def _final_expression(source: str) -> Expr:
    _definitions, final = _split_program(source)
    return final


def _split_program(source: str) -> tuple[dict[str, Expr], Expr]:
    program = normalize_program(parse_program(source))
    definitions: dict[str, Expr] = {}
    final: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
            continue
        if isinstance(form, StructDef):
            continue
        final = form
    if final is None:
        msg = "compile-red2 requires a final expression"
        raise ValueError(msg)
    return definitions, final


def _run_io(source: str, *, model_value: object, quantum: int) -> int:
    if model_value == "parity":
        print(
            "thor-spec: --io supports only --model thor or --model red2",
            file=sys.stderr,
        )
        return 2
    model = _model_name(model_value)
    result = run_io_source(
        source,
        model=model,
        quantum=quantum,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    print(f"io result: {result}", file=sys.stderr)
    return 0


def _run_parity(source: str, *, quantum: int) -> int:
    result = compare_prefixes(source, max_quantum=quantum)
    final = result.final_snapshot
    if result.first_mismatch is not None:
        _write_mismatch_report(result)
        if final is not None:
            status = "matched" if final.matches else "mismatched"
            print(
                f"parity final quantum {final.quantum} {status}",
                file=sys.stderr,
            )
        if final is not None and final.matches and final.thor:
            print(final.thor)
        return 0 if final is not None and final.matches else 1

    final_output = final.thor if final is not None else ""
    print(
        "parity ok: "
        f"{len(result.snapshots)} prefix snapshot(s) matched through quantum {quantum}",
        file=sys.stderr,
    )
    if final_output:
        print(final_output)
    return 0


def _write_mismatch_report(result: ParityResult) -> None:
    snapshots = {snapshot.quantum: snapshot for snapshot in result.snapshots}
    for start, end in result.mismatch_ranges:
        mismatch = snapshots[start]
        print(f"parity mismatch at quantum {start}", file=sys.stderr)
        print(f"thor: {mismatch.thor}", file=sys.stderr)
        print(f"red2: {mismatch.red2}", file=sys.stderr)
        reconverged = snapshots.get(end + 1)
        if reconverged is not None and reconverged.matches:
            print(
                f"parity reconverged at quantum {reconverged.quantum}",
                file=sys.stderr,
            )
        else:
            print(
                f"parity did not reconverge by quantum {result.max_quantum}",
                file=sys.stderr,
            )
        print(file=sys.stderr)

def _model_name(value: object) -> ModelName:
    if value == "thor" or value == "red2":
        return value
    msg = f"unknown execution model: {value!r}"
    raise ValueError(msg)


def _write_trace(
    stream: TextIO,
    *,
    model: ModelName,
    quantum: int,
    source_kind: str,
    output: str,
) -> None:
    result_count = len(output.splitlines()) if output else 0
    print(f"trace model={model} quantum={quantum} source={source_kind}", file=stream)
    print(f"trace results={result_count}", file=stream)

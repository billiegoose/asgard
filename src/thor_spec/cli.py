from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from thor_spec import __version__
from thor_spec.golden import DEFAULT_QUANTUM, ModelName, run_source
from thor_spec.lockstep import compare_prefixes
from thor_spec.parser import ParseError


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.expr is None and args.file is None:
        parser.print_help()
        return 0

    try:
        source = args.expr if args.expr is not None else args.file.read_text()
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


def _run_parity(source: str, *, quantum: int) -> int:
    result = compare_prefixes(source, max_quantum=quantum)
    mismatch = result.first_mismatch
    if mismatch is not None:
        print(f"parity mismatch at quantum {mismatch.quantum}", file=sys.stderr)
        print(f"thor: {mismatch.thor}", file=sys.stderr)
        print(f"red2: {mismatch.red2}", file=sys.stderr)
        return 1
    final = result.snapshots[-1].thor if result.snapshots else ""
    print(
        "parity ok: "
        f"{len(result.snapshots)} prefix snapshot(s) matched through quantum {quantum}",
        file=sys.stderr,
    )
    if final:
        print(final)
    return 0


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

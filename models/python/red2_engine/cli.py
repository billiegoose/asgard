from __future__ import annotations

import argparse
import sys
from pathlib import Path

from red2_engine.machine import (
    DEFAULT_HEAP_SIZE_IN_BYTES,
    DEFAULT_STACK_SIZE_IN_BYTES,
    Red2ResourceLimits,
)
from thor_engine.golden import DEFAULT_QUANTUM, run_source
from thor_engine.io_runtime import IoRuntimeError, LatestFileClockSource, run_io_source
from thor_lang.parser import ParseError
from thor_lang.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="red2",
        description="Run THOR source with the Python RED2 model.",
    )
    parser.add_argument("file", nargs="?", type=Path, help="path to THOR source")
    parser.add_argument("--expr", help="THOR expression or program source to run")
    parser.add_argument(
        "--quantum",
        type=int,
        default=DEFAULT_QUANTUM,
        help=f"maximum contraction quantum (default: {DEFAULT_QUANTUM})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="write diagnostics to stderr",
    )
    parser.add_argument(
        "--clock",
        type=Path,
        help=(
            "path to a latest-value clock source with newline-delimited "
            "millisecond timestamps"
        ),
    )
    parser.add_argument("--stack-size-in-bytes", type=int, default=None)
    parser.add_argument("--heap-size-in-bytes", type=int, default=None)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.expr is None and args.file is None:
        parser.print_help()
        return 0
    if args.expr is not None and args.file is not None:
        parser.error("--expr and file are mutually exclusive")

    try:
        source = args.expr if args.expr is not None else args.file.read_text()
        resource_limits = _resource_limits_from_args(args)
        return _run_expr_source(
            source,
            quantum=args.quantum,
            verbose=args.verbose,
            clock_path=args.clock,
            resource_limits=resource_limits,
        )
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"red2: {error}", file=sys.stderr)
        return 2


def _resource_limits_from_args(args: argparse.Namespace) -> Red2ResourceLimits:
    return Red2ResourceLimits(
        stack_size_in_bytes=args.stack_size_in_bytes
        if args.stack_size_in_bytes is not None
        else DEFAULT_STACK_SIZE_IN_BYTES,
        heap_size_in_bytes=args.heap_size_in_bytes
        if args.heap_size_in_bytes is not None
        else DEFAULT_HEAP_SIZE_IN_BYTES,
    )


def _run_expr_source(
    source: str,
    *,
    quantum: int,
    verbose: bool,
    clock_path: Path | None,
    resource_limits: Red2ResourceLimits,
) -> int:
    try:
        return _run_io_source(
            source,
            quantum=quantum,
            verbose=verbose,
            clock_path=clock_path,
            resource_limits=resource_limits,
        )
    except IoRuntimeError as error:
        message = str(error)
        if not (
            message.startswith("not an IO action:")
            or message.startswith("unknown IO action:")
        ):
            raise
    output = run_source(
        source,
        model="red2",
        quantum=quantum,
        resource_limits=resource_limits,
    )
    if output:
        print(output)
    return 0


def _run_io_source(
    source: str,
    *,
    quantum: int,
    verbose: bool,
    clock_path: Path | None,
    resource_limits: Red2ResourceLimits,
) -> int:
    clock = LatestFileClockSource(clock_path) if clock_path is not None else None
    result = run_io_source(
        source,
        model="red2",
        quantum=quantum,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        clock=clock,
        resource_limits=resource_limits,
    )
    if verbose:
        print(f"io result: {result}", file=sys.stderr)
    return 0

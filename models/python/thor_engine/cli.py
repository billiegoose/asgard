import argparse
import sys
from pathlib import Path

from thor_engine.golden import DEFAULT_QUANTUM, run_source
from thor_engine.io_runtime import IoRuntimeError, LatestFileClockSource, run_io_source
from thor_lang.parser import ParseError
from thor_lang.version import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thor",
        description="Run THOR source with the Python THOR model.",
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
        return _run_expr_source(
            source,
            quantum=args.quantum,
            verbose=args.verbose,
            clock_path=args.clock,
        )
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"thor: {error}", file=sys.stderr)
        return 2


def _run_expr_source(
    source: str,
    *,
    quantum: int,
    verbose: bool,
    clock_path: Path | None,
) -> int:
    try:
        return _run_io_source(
            source,
            quantum=quantum,
            verbose=verbose,
            clock_path=clock_path,
        )
    except IoRuntimeError as error:
        message = str(error)
        if not (
            message.startswith("not an IO action:")
            or message.startswith("unknown IO action:")
        ):
            raise
    output = run_source(source, model="thor", quantum=quantum)
    if output:
        print(output)
    return 0


def _run_io_source(
    source: str,
    *,
    quantum: int,
    verbose: bool,
    clock_path: Path | None,
) -> int:
    clock = LatestFileClockSource(clock_path) if clock_path is not None else None
    result = run_io_source(
        source,
        model="thor",
        quantum=quantum,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        clock=clock,
    )
    if verbose:
        print(f"io result: {result}", file=sys.stderr)
    return 0

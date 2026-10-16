import argparse
import sys
from pathlib import Path

from abstract_red2_machine.io_runtime import (
    DEFAULT_RED2_RECHARGE_EVENTS,
    Red2RechargeEvent,
)
from red2.supervisor import DEFAULT_SUPERVISOR_QUANTUM
from thor.parser import ParseError
from thor.version import __version__
from thor_interpreter.golden import DEFAULT_QUANTUM, run_source
from thor_interpreter.io_runtime import (
    IoRuntimeError,
    LatestFileClockSource,
    run_io_source,
)


def build_parser(*, prog: str = "abs") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Run THOR source with the Abstract RED2 Machine.",
    )
    parser.add_argument("file", nargs="?", type=Path, help="path to THOR source")
    parser.add_argument("--expr", help="THOR expression or program source to run")
    parser.add_argument(
        "--quantum",
        type=int,
        default=None,
        help=f"maximum contraction quantum (default: {DEFAULT_QUANTUM})",
    )
    parser.add_argument(
        "--supervise",
        action="store_true",
        help="restart reconstructed residuals (default quantum: 20)",
    )
    parser.add_argument("--max-quanta", type=int, help="supervised execution limit")
    parser.add_argument(
        "--memory-words",
        type=int,
        default=1_048_576,
        help="faithful RED2 memory arena in words (default: 1048576)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="write diagnostics to stderr",
    )
    parser.add_argument(
        "--recharge-on",
        action="append",
        choices=[event.value for event in Red2RechargeEvent],
        help=(
            "scheduler event that resets the IO quantum; repeat to enable multiple "
            "events (default: host-dispatch)"
        ),
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


def main(argv: list[str] | None = None, *, prog: str = "abs") -> int:
    parser = build_parser(prog=prog)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.expr is None and args.file is None:
        parser.print_help()
        return 0
    if args.expr is not None and args.file is not None:
        parser.error("--expr and file are mutually exclusive")
    if args.quantum is None:
        args.quantum = DEFAULT_SUPERVISOR_QUANTUM if args.supervise else DEFAULT_QUANTUM
    if args.supervise and args.recharge_on:
        parser.error("--supervise cannot be combined with --recharge-on")

    try:
        source = args.expr if args.expr is not None else args.file.read_text()
        return _run_expr_source(
            source,
            quantum=args.quantum,
            memory_words=args.memory_words,
            verbose=args.verbose,
            clock_path=args.clock,
            recharge_on=(
                DEFAULT_RED2_RECHARGE_EVENTS
                if args.recharge_on is None
                else frozenset(Red2RechargeEvent(value) for value in args.recharge_on)
            ),
            supervised=args.supervise,
            max_quanta=args.max_quanta,
        )
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"{prog}: {error}", file=sys.stderr)
        return 2


def _run_expr_source(
    source: str,
    *,
    quantum: int,
    memory_words: int,
    verbose: bool,
    clock_path: Path | None,
    recharge_on: frozenset[Red2RechargeEvent],
    supervised: bool = False,
    max_quanta: int | None = None,
) -> int:
    try:
        return _run_io_source(
            source,
            quantum=quantum,
            memory_words=memory_words,
            verbose=verbose,
            clock_path=clock_path,
            recharge_on=recharge_on,
            supervised=supervised,
            max_quanta=max_quanta,
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
        model="abs",
        quantum=quantum,
        supervised=supervised,
        memory_words=memory_words,
        max_quanta=max_quanta,
    )
    if output:
        print(output)
    return 0


def _run_io_source(
    source: str,
    *,
    quantum: int,
    memory_words: int,
    verbose: bool,
    clock_path: Path | None,
    recharge_on: frozenset[Red2RechargeEvent],
    supervised: bool = False,
    max_quanta: int | None = None,
) -> int:
    clock = LatestFileClockSource(clock_path) if clock_path is not None else None
    result = run_io_source(
        source,
        model="abs",
        quantum=quantum,
        red2_memory_words=memory_words,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        clock=clock,
        red2_recharge_on=recharge_on,
        red2_supervised=supervised,
        red2_max_quanta=max_quanta,
    )
    if verbose:
        print(f"io result: {result}", file=sys.stderr)
    return 0

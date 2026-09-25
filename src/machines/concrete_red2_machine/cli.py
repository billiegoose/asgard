"""CLI for the Concrete RED2 Machine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from abstract_red2_machine.machine import AbstractRED2Machine
from concrete_red2_machine import abi
from concrete_red2_machine.oracle import load_compiled_program
from thor.ast import Definition, Expr, StructDef
from thor.normalization import normalize_program
from thor.parser import ParseError, parse_program
from thor.pretty import to_source
from thor.primitives import install_struct_definition
from thor.version import __version__


def _prepare_program(source: str) -> tuple[Expr, dict[str, Expr]]:
    program = normalize_program(parse_program(source))
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    definitions.pop("CAR", None)
    definitions.pop("CDR", None)
    action: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
        else:
            action = form
    if action is None:
        raise ValueError("THOR program requires a final expression")
    return action, definitions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="con",
        description="Run THOR source on the Concrete RED2 Machine.",
    )
    parser.add_argument("file", nargs="?", type=Path, help="path to THOR source")
    parser.add_argument("--expr", help="THOR expression or program source to run")
    parser.add_argument("--quantum", type=int, default=2000)
    parser.add_argument("--memory-words", type=int, default=65_536)
    parser.add_argument("--control-words", type=int, default=8_192)
    parser.add_argument("--max-clocks", type=int, default=10_000_000)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
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
    if args.quantum < 0:
        parser.error("--quantum must be non-negative")

    try:
        source = args.expr if args.expr is not None else args.file.read_text()
        expr, definitions = _prepare_program(source)
        loaded = load_compiled_program(
            expr,
            quantum=args.quantum,
            definitions=definitions,
            memory_words=args.memory_words,
            control_words=args.control_words,
        )
        concrete = loaded.concrete
        status = concrete.run_until_suspend(args.max_clocks)

        if status == abi.STATUS_COMPLETE:
            decoded = loaded.codec.decode_state(concrete.checkpoint())
            result_view = AbstractRED2Machine(
                decoded,
                working_memory_limit=loaded.image.working_memory_limit,
            )
            print(to_source(result_view.result_expr()))
            if args.verbose:
                print(
                    "con: complete "
                    f"commits={concrete.commits} clocks={concrete.clocks}",
                    file=sys.stderr,
                )
            return 0

        if status == abi.STATUS_QUANTUM_EXHAUSTED:
            print(
                "con: quantum exhausted; rerun with a larger --quantum",
                file=sys.stderr,
            )
            return 3
        if status == abi.STATUS_HOST_CALL:
            print(
                "con: suspended on a host call; CLI host services are not wired yet",
                file=sys.stderr,
            )
            return 4
        if status == abi.STATUS_FAULT:
            print(
                f"con: RED2 fault={concrete.fault} micro={concrete.microstate} "
                f"commits={concrete.commits}",
                file=sys.stderr,
            )
            return 5
        raise RuntimeError(
            f"Concrete RED2 Machine remained running after {args.max_clocks} clocks"
        )
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"con: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

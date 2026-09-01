from __future__ import annotations

import argparse
import sys
from pathlib import Path

from red2_engine.binary import encode_bundle
from thor_compile.red2 import compile_definitions, compile_expr
from thor_lang.ast import Definition, Expr, StructDef
from thor_lang.normalization import normalize_program
from thor_lang.parser import ParseError, parse_program


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compile",
        description="Compile THOR source to a .red2 bytecode image.",
    )
    parser.add_argument("file", nargs="?", type=Path, help="path to THOR source")
    parser.add_argument("--expr", help="THOR expression or program source")
    parser.add_argument("--output", type=Path, required=True, help="output .red2 path")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.expr is None and args.file is None:
        parser.error("one of --expr or file is required")
    if args.expr is not None and args.file is not None:
        parser.error("--expr and file are mutually exclusive")

    try:
        source = args.expr if args.expr is not None else args.file.read_text()
        definitions, final = _split_program(source)
        args.output.write_bytes(
            encode_bundle(compile_expr(final), compile_definitions(definitions))
        )
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"compile: {error}", file=sys.stderr)
        return 2
    print(f"wrote RED2 bytecode: {args.output}", file=sys.stderr)
    return 0


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
        msg = "compile requires a final expression"
        raise ValueError(msg)
    return definitions, final

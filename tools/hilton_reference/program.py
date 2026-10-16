"""Build and run Hilton's archived THOR compiler and HORSE reducer headlessly."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.hilton_reference import runner

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FILES = (*runner.SOURCES, "COMPILER.C", "PRINTER.C", "PRELUDE.LAM")
MAIN_FUNCTIONS = {
    "rep_loop",
    "copy_graph",
    "shift_memory",
    "struct_def",
    "load_file",
    "sum_times",
}


def strip_includes(text: str) -> str:
    return re.sub(r"^#include[^\n]*", "", text, flags=re.M)


def translation_unit() -> str:
    main = runner._archive_text("MAIN.C")
    prefix = main[: main.index("main(argc, argv)")]
    chunks = [
        '#include "program_compat.h"',
        runner._archive_text("LRS.H"),
        strip_includes(prefix),
        "symbol *symbol_lookup(), *archive_symbol_lookup();",
        "node *red(), *copy_graph(), *shift_memory(), *struct_def();",
        "void repaired(const char *); void trace_step(void);",
        "void rep_loop(), sum_times(), print_stats(), handle_command();",
        "char *input_line_editor(), *print_expression();",
    ]
    for filename in ("COMPILER.C", "RED.C", "PRIMS.C", "ARITH.C", "PRINTER.C"):
        text = strip_includes(
            runner._apply_repairs(runner._archive_text(filename), filename)
        )
        if filename == "COMPILER.C":
            # Preserve the historical symbol algorithm, but give it writable input.
            text = text.replace(
                "symbol *symbol_lookup(word, type)",
                "symbol *archive_symbol_lookup(word, type)",
            )
            # PCYACC forms pointers one element before its stacks and permits
            # a write at the upper bound. Add sentinel storage and fix that guard.
            replacements = {
                "YYSTYPE yyv[YYMAXDEPTH];": (
                    "YYSTYPE yyv_storage[YYMAXDEPTH + 1];\n"
                    "#define yyv (yyv_storage + 1)"
                ),
                "int statestack[YYMAXDEPTH];": (
                    "int state_storage[YYMAXDEPTH + 1];\n"
                    "#define statestack (state_storage + 1)"
                ),
                "++yyps - &statestack[YYMAXDEPTH] > 0": (
                    "++yyps >= &statestack[YYMAXDEPTH]"
                ),
            }
            for original, replacement in replacements.items():
                if text.count(original) != 1:
                    raise runner.HiltonReferenceError("Stale PCYACC stack repair")
                text = text.replace(original, replacement)
        if filename == "RED.C":
            original = "   while (TRUE) {"
            if text.count(original) != 1:
                raise runner.HiltonReferenceError("Stale instruction trace site")
            text = text.replace(original, original + "\n      trace_step();")
        if filename == "PRINTER.C":
            original = "void sprint(va_alist)\nva_dcl"
            if text.count(original) != 1:
                raise runner.HiltonReferenceError("Stale printer varargs repair")
            text = text.replace(original, "void sprint(char *format, ...)")
            text = text.replace("   char *format;\n", "")
            text = text.replace(
                "   va_start(args);\n   format = va_arg(args, char *);",
                "   va_start(args, format);",
            )
            text = text.replace("void sprint();", "void sprint(char *format, ...);")
        # K&R forward references must have the correct pointer/void return types.
        voids = re.findall(r"^void\s+(\w+)\(", text, re.M)
        chunks.append(
            "\n".join(f"void {name}();" for name in voids if name != "sprint")
        )
        chunks.append(text)
    for name, start, end in runner._functions(main):
        if name in MAIN_FUNCTIONS:
            chunks.append(strip_includes(main[start:end]))
    chunks.append((HERE / "program.c").read_text())
    return "\n".join(chunks)


def build(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which(os.environ.get("CC", "cc"))
    if compiler is None:
        raise runner.HiltonReferenceError("Missing C compiler (CC or cc)")
    source = directory / "horse.c"
    source.write_text(translation_unit())
    shutil.copyfile(HERE / "program_compat.h", directory / "program_compat.h")
    binary = directory / "horse"
    command = [
        compiler,
        "-std=gnu89",
        "-Wno-implicit-function-declaration",
        "-Wno-int-conversion",
        "-Wno-deprecated-declarations",
        "-Wno-comment",
        "-Wno-return-type",
        "-Wno-unknown-escape-sequence",
        "-Wno-deprecated-non-prototype",
        str(source),
        "-lm",
        "-o",
        str(binary),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    (directory / "compiler.log").write_text(result.stdout + result.stderr)
    if result.returncode:
        raise runner.HiltonReferenceError(result.stderr)
    manifest = {
        "archive_sha256": {
            name: hashlib.sha256((runner.ARCHIVE / name).read_bytes()).hexdigest()
            for name in FILES
        },
        "translation_unit_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "port_sha256": {
            name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
            for name in ("program.py", "program.c", "program_compat.h", "runner.py")
        },
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "compiler": compiler,
        "command": command,
        "reducer_repairs": list(runner.REPAIRS),
        "port": [
            "headless terminal services",
            "ANSI printer varargs",
            "writable symbol lookup argument",
            "per-instruction observation hook",
            "PCYACC stack sentinel storage and upper-bound guard",
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return binary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--expr", help="historical THOR expression or definitions")
    source.add_argument("--file", type=Path, help="historical .LAM source")
    parser.add_argument(
        "--load",
        type=Path,
        action="append",
        default=[],
        help="load an archived definitions file before the main input (repeatable)",
    )
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build/hilton-horse")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--compile-only", action="store_true")
    parser.add_argument("--quantum", type=int, default=100_000)
    parser.add_argument(
        "--passes",
        type=int,
        default=1,
        help="restart the residual graph up to this many times with fresh quantum",
    )
    parser.add_argument("--memory-words", type=int, default=100_000)
    parser.add_argument("--graphs", type=Path, help="compiled/result graph JSONL")
    parser.add_argument("--trace", type=Path, help="per-instruction state/graph JSONL")
    parser.add_argument("--trace-limit", type=int, default=1000)
    args = parser.parse_args()
    if not 0 <= args.quantum <= 2_147_483_647:
        parser.error("quantum must fit a nonnegative C int")
    if not 256 <= args.memory_words <= 100_000:
        parser.error("memory-words must be between 256 and 100000")
    if args.trace_limit < 0:
        parser.error("trace-limit must be nonnegative")
    if args.passes < 1:
        parser.error("passes must be positive")
    binary = build(args.build_dir.resolve())
    if args.build_only:
        print(binary)
        return 0
    if args.expr is None and args.file is None:
        parser.error("specify --expr or --file (or --build-only)")
    for path in (args.graphs, args.trace):
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hilton-program-") as temporary:
        input_path = args.file
        if input_path is None or args.load:
            input_path = Path(temporary) / "input.lam"
            body = args.expr if args.expr is not None else args.file.read_text()
            input_path.write_text(
                "\n".join(path.read_text() for path in args.load) + "\n" + body + "\n"
            )
        command = [
            str(binary),
            str(runner.ARCHIVE / "PRELUDE.LAM"),
            str(input_path.resolve()),
            str(args.quantum),
            str(args.memory_words),
            str(args.graphs.resolve()) if args.graphs else "-",
            str(args.trace.resolve()) if args.trace else "-",
            str(args.trace_limit),
            str(int(args.compile_only)),
            str(args.passes),
        ]
        return subprocess.run(command, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

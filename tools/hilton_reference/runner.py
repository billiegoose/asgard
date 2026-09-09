"""Build an isolated headless executable from the archived functional THOR bodies."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "archives/THOR"
SOURCES = ("LRS.H", "RED.C", "PRIMS.C", "ARITH.C", "MAIN.C")
REQUIRED_TECHNIQUES = frozenset(
    {
        "environment-return",
        "closure-sharing",
        "atomic-join",
        "lambda-suffix",
        "rup-suffix",
        "primitive-suffix",
        "if-discard",
        "and-discard",
        "or-discard",
        "y-reconstruction",
        "rec-reconstruction",
        "equal-scratch",
        "equal-star-wrap",
        "copy-shift-forwarding",
        "reduce-reset",
        "equal-star-head-promotion",
        "ubv-index-equality",
    }
)


# Approved adapter-only repairs: exact original/replacement compatibility log.
REPAIRS = {
    "equal-star-head-promotion": (
        (
            "if (arg1->op.addr->class == HEAD) {",
            'repaired("equal-star-head-promotion");\n'
            "      if ((arg1->type == PTR) && (arg1->op.addr->class == HEAD)) {",
        ),
        (
            "if (arg2->op.addr->class == HEAD) {",
            "if ((arg2->type == PTR) && (arg2->op.addr->class == HEAD)) {",
        ),
    ),
    "ubv-index-equality": (
        (
            "case UBV:      return(((*arg1)->op.addr->op.index ==\n"
            "                             (*arg2)->op.addr->op.index));",
            'case UBV:      repaired("ubv-index-equality");\n'
            "                     return(((*arg1)->op.index == (*arg2)->op.index));",
        ),
    ),
    "nodes-equal-unsupported-tag": (
        (
            "                     else return(FALSE);\n\n   }\n}",
            "                     else return(FALSE);\n\n"
            '      default: repaired("nodes-equal-unsupported-tag");\n'
            '               fprintf(stderr, "reference: unsupported '
            'nodes_equal tag %d\\n",\n'
            "                       (*arg1)->type);\n"
            "               exit(72);\n   }\n}",
        ),
    ),
}


def _apply_repairs(text: str, path: str) -> str:
    if path == "PRIMS.C":
        for name, replacements in REPAIRS.items():
            for original, replacement in replacements:
                if text.count(original) != 1:
                    raise HiltonReferenceError(f"Stale adapter repair: {name}")
                text = text.replace(original, replacement)
    return text


class HiltonReferenceError(RuntimeError):
    """A reference proof failed; never a skipped differential success."""


def _archive_text(path: str) -> str:
    return (ARCHIVE / path).read_text()


def source_hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((ARCHIVE / name).read_bytes()).hexdigest()
        for name in SOURCES
    }


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = json.loads((HERE / "cases.json").read_text())
    validate_corpus(cases)
    return cases


def validate_corpus(cases: list[dict[str, Any]]) -> None:
    missing = REQUIRED_TECHNIQUES - {case["technique"] for case in cases}
    if missing:
        raise HiltonReferenceError(f"Missing corpus technique: {sorted(missing)}")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise HiltonReferenceError("Duplicate case id")
    for case in cases:
        for field in (
            "id",
            "technique",
            "expected_result",
            "expected_aliases",
            "expected_events",
            "required_functions",
            "derivation",
            "expected_repairs",
        ):
            if field not in case:
                raise HiltonReferenceError(f"Missing case field: {field}")
        if not case["expected_events"] or not case["required_functions"]:
            raise HiltonReferenceError("Missing runtime evidence")
        for event in case["expected_events"]:
            if set(event) != {"at", "ws", "fs"}:
                raise HiltonReferenceError("Both arena boundaries must be explicit")


def compare_case(case: dict[str, Any], actual: dict[str, Any]) -> None:
    for field in ("result", "aliases", "events"):
        if field not in actual or actual[field] != case[f"expected_{field}"]:
            raise HiltonReferenceError(
                f"{case['id']}: {field} mismatch: {actual.get(field)!r}"
            )
    authority = actual.get("authority", {})
    if authority.get("source_sha256") != source_hashes() or not set(
        case["required_functions"]
    ) <= set(authority.get("functions", [])):
        raise HiltonReferenceError(f"{case['id']}: missing archived-body authority")
    if (
        authority.get("repairs_applied") != list(REPAIRS)
        or authority.get("repairs_exercised") != case["expected_repairs"]
        or authority.get("execution")
        != ("repaired-C" if case["expected_repairs"] else "archived-C")
    ):
        raise HiltonReferenceError(f"{case['id']}: missing/incorrect repair evidence")


def _without_comments(text: str) -> str:
    # Preserve locations, including historical /*-prefixed lines within comments.
    return re.sub(
        r"/\*.*?\*/|//[^\n]*",
        lambda m: "".join("\n" if c == "\n" else " " for c in m[0]),
        text,
        flags=re.S,
    )


def _code(text: str) -> str:
    return re.sub(
        r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
        lambda m: "".join("\n" if c == "\n" else " " for c in m[0]),
        _without_comments(text),
    )


def _functions(text: str) -> list[tuple[str, int, int]]:
    """Extract top-level K&R definitions; braces in strings/comments are ignored."""
    clean = _code(text)
    found = []
    # Archived definitions put the opening and closing braces in column zero.
    for match in re.finditer(r"^\{\s*$", clean, re.M):
        prefix = clean[: match.start()]
        signatures = list(
            re.finditer(
                r"^(?:(?:void|int|node|symbol)\s+\*?\s*)?(\w+)\([^;{}]*\)\s*\n",
                prefix,
                re.M,
            )
        )
        if not signatures:
            raise HiltonReferenceError("Unrecognized archived function definition")
        signature = signatures[-1]
        depth = 1
        end = match.end()
        while depth and end < len(clean):
            depth += (clean[end] == "{") - (clean[end] == "}")
            end += 1
        if depth:
            raise HiltonReferenceError("Unbalanced archived function")
        found.append((signature[1], signature.start(), end))
    for match in re.finditer(r"^void\s+(\w+)\([^\n]*?\)\s*\{[^\n]*?\}", clean, re.M):
        found.append((match[1], match.start(), match.end()))
    return sorted(found, key=lambda entry: entry[1])


def _instrument(text: str, path: str) -> str:
    # Only add entry probes; archived statements remain byte-for-byte text.
    for symbol, start, end in reversed(_functions(text)):
        opening = text.index("{", start, end) + 1
        text = text[:opening] + f'\n   entered("{path}:{symbol}");' + text[opening:]
    return re.sub(r"^#include[^\n]*", "", text, flags=re.M)


def _translation_unit() -> str:
    chunks = [
        '#include "compat.h"',
        _archive_text("LRS.H"),
        "symbol *symbol_lookup();\nnode *red(), *copy_graph(), *shift_memory();",
        "void entered(const char *); void repaired(const char *);",
    ]
    for path in ("RED.C", "PRIMS.C", "ARITH.C"):
        text = _apply_repairs(_archive_text(path), path)
        # Installation is parser/prelude integration, not a reducer body.
        if path == "PRIMS.C":
            for name, start, end in reversed(_functions(text)):
                if name == "install_primitives":
                    text = text[:start] + text[end:]
        voids = re.findall(r"^void\s+(\w+)\(", text, re.M)
        chunks.append("\n".join(f"void {name}();" for name in voids))
        chunks.append(_instrument(text, path))
    main = _archive_text("MAIN.C")
    for name, start, end in _functions(main):
        if name in {"copy_graph", "shift_memory"}:
            chunks.append(_instrument(main[start:end], "MAIN.C"))
    chunks.append(_adapter_source())
    return "\n".join(chunks)


def _adapter_source() -> str:
    return (HERE / "adapter.c").read_text()


def run_case(case_id: str) -> dict[str, object]:
    if case_id not in {case["id"] for case in load_cases()}:
        raise HiltonReferenceError(f"Unknown case: {case_id}")
    compiler = shutil.which(os.environ.get("CC", "cc"))
    if compiler is None:
        raise HiltonReferenceError("Missing C compiler (CC or cc)")
    with tempfile.TemporaryDirectory(prefix="hilton-reference-") as temporary:
        build = Path(temporary)
        (build / "reference.c").write_text(_translation_unit())
        shutil.copyfile(HERE / "compat.h", build / "compat.h")
        command = [
            compiler,
            "-std=gnu89",
            "-Wno-implicit-function-declaration",
            "-Wno-int-conversion",
            "-Wno-deprecated-declarations",
            "-Wno-comment",
            "-Wno-return-type",
            "-Wno-unknown-escape-sequence",
            str(build / "reference.c"),
            "-lm",
            "-o",
            str(build / "reference"),
        ]
        try:
            compiled = subprocess.run(
                command, capture_output=True, text=True, timeout=60, cwd=build
            )
            if compiled.returncode:
                raise HiltonReferenceError(
                    f"C compilation failed ({compiled.returncode}):\n{compiled.stderr}"
                )
            executed = subprocess.run(
                [str(build / "reference"), case_id],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=build,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise HiltonReferenceError(
                f"C reference execution infrastructure failure: {error}"
            ) from error
        if executed.returncode:
            raise HiltonReferenceError(
                f"C runtime failed ({executed.returncode}): {executed.stderr}"
            )
        try:
            actual: dict[str, object] = json.loads(executed.stdout)
            repairs_exercised = actual.pop("repairs_exercised")
            actual["authority"] = {
                "functions": actual.pop("functions"),
                "source_sha256": source_hashes(),
                "repairs_applied": list(REPAIRS),
                "repairs_exercised": repairs_exercised,
                "execution": "repaired-C" if repairs_exercised else "archived-C",
            }
        except (ValueError, KeyError, TypeError) as error:
            raise HiltonReferenceError(
                f"Malformed C evidence: {executed.stdout}"
            ) from error
        return actual


# The inventory audits every ws/fs mutation, a strict superset of rewinds/resets.
MUTATION = re.compile(
    r"(?:\b(ws|fs)\s*(?:=(?!=)|[+\-]=|\+\+|--)|(?:\+\+|--)\s*(ws|fs)\b)"
)
VARIANTS = (
    "THOR",
    "STRICT",
    "DEC6",
    "WORK",
    "SNARL/SNARL",
    "SNARL/OPT",
    "SNARL/EXPERIME",
)


def audit_sites() -> set[tuple[str, str, str, int]]:
    sites = set()
    for variant in VARIANTS:
        for filename in ("RED.C", "PRIMS.C", "ARITH.C", "MAIN.C"):
            path = ROOT / "archives" / variant / filename
            if not path.exists():  # STRICT has no ARITH.C in the archive.
                continue
            text = path.read_text()
            clean = _code(text)
            functions = _functions(text)
            for match in MUTATION.finditer(clean):
                symbol = next(
                    (
                        name
                        for name, start, end in functions
                        if start <= match.start() < end
                    ),
                    None,
                )
                if symbol is None:
                    raise HiltonReferenceError(f"Unowned mutation: {path}:{match[0]}")
                sites.add(
                    (
                        str(path.relative_to(ROOT)),
                        symbol,
                        "graph" if (match[1] or match[2]) == "ws" else "environment",
                        clean.count("\n", 0, match.start()) + 1,
                    )
                )
    return sites


def validate_inventory(records: list[dict[str, Any]] | None = None) -> None:
    if records is None:
        records = json.loads((HERE / "reclamation-sites.json").read_text())
    actual = set()
    ids = {case["id"] for case in load_cases()}
    for record in records:
        if record["disposition"] not in {
            "parity",
            "representation-equivalent",
            "variant-out-of-scope",
        }:
            raise HiltonReferenceError("Invalid inventory disposition")
        if not set(record["case_ids"]) <= ids or not record["trigger"]:
            raise HiltonReferenceError("Invalid inventory case/trigger")
        path = ROOT / record["path"]
        text = path.read_text()
        lines = text.splitlines()
        ranges = [
            (name, text.count("\n", 0, start) + 1, text.count("\n", 0, end) + 1)
            for name, start, end in _functions(text)
        ]
        if not record["locations"]:
            raise HiltonReferenceError("Inventory record has no source location")
        for location in record["locations"]:
            line = location["line"]
            if (
                line < 1
                or line > len(lines)
                or lines[line - 1].strip() != location["text"]
            ):
                raise HiltonReferenceError(f"Stale inventory location: {path}:{line}")
            if not any(
                name == record["symbol"] and start <= line <= end
                for name, start, end in ranges
            ):
                raise HiltonReferenceError(f"Wrong inventory symbol: {path}:{line}")
            if record["arena"] in {"graph", "environment"}:
                key = (record["path"], record["symbol"], record["arena"], line)
                if key in actual:
                    raise HiltonReferenceError(f"Duplicate inventory location: {key}")
                actual.add(key)
    expected = audit_sites()
    if actual != expected:
        raise HiltonReferenceError(
            f"Inventory mismatch: missing={expected - actual}, "
            f"extra={actual - expected}"
        )

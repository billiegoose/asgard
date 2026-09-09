"""Executable THOR lifetime reference (not a RED2-derived oracle)."""

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "hilton_reference", ROOT / "tools/hilton_reference/runner.py"
)
assert SPEC is not None and SPEC.loader is not None
reference = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reference)
CASES = reference.load_cases()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_archived_case(case: dict[str, Any]) -> None:
    actual = reference.run_case(case["id"])
    reference.compare_case(case, actual)
    assert actual["authority"]["functions"]
    assert actual["authority"]["source_sha256"] == reference.source_hashes()
    assert set(case["required_functions"]) <= set(actual["authority"]["functions"])
    for field in ("result", "aliases", "events", "authority"):
        broken = dict(actual)
        del broken[field]
        with pytest.raises(reference.HiltonReferenceError):
            reference.compare_case(case, broken)
    for index, _event in enumerate(case["expected_events"]):
        for register in ("ws", "fs"):
            broken = json.loads(json.dumps(case))
            broken["expected_events"][index][register] += 1
            with pytest.raises(reference.HiltonReferenceError):
                reference.compare_case(broken, actual)


def test_corpus_requires_each_technique() -> None:
    reference.validate_corpus(CASES)
    for technique in reference.REQUIRED_TECHNIQUES:
        without = [case for case in CASES if case["technique"] != technique]
        with pytest.raises(reference.HiltonReferenceError, match="technique"):
            reference.validate_corpus(without)


def test_atomic_child_restores_saved_fs() -> None:
    actual = reference.run_case("atomic-child-return")
    assert actual["events"][0]["fs"] == actual["events"][-1]["fs"] == 200
    assert min(event["fs"] for event in actual["events"]) < 200


def test_y_reconstruction_retains_context_and_is_executable() -> None:
    actual = reference.run_case("y-reconstruct")
    result = actual["result"]
    assert result["reconstruction"] == {
        "argument_class": 1,
        "argument_type": 2,
        "argument_target": 20,
        "code": 30,
        "stack": 1,
        "saved_env": 200,
        "mode": 1,
        "argcount": 1,
    }
    # Complete Y (lambda x.42) code, independent of fixture observations.
    assert result["recursive_graph"] == [
        {"offset": 20, "class": 1, "type": 2, "operand": 30},
        {"offset": 21, "class": 2, "type": 6, "operand": "y"},
    ]
    assert result["function_graph"] == [
        {"offset": 30, "class": 0, "type": 1, "operand": "binder"},
        {"offset": 31, "class": 2, "type": 4, "operand": 42},
    ]
    assert result["resumed"] == {
        "type": 4,
        "value": 42,
        "stack": 0,
        "reductions": 2,
        "binding": 196,
        "binding_type": 9,
        "binding_target": 198,
        "marker_type": 13,
        "marker_target": 200,
        "closure_code": 20,
        "closure_env": 200,
    }
    assert result["traversed_argument"] == {
        "type": 4,
        "value": 42,
        "stack": 0,
        "reductions": 2,
        "limit": 2,
    }
    reference.compare_case(next(c for c in CASES if c["id"] == "y-reconstruct"), actual)


@pytest.mark.parametrize(
    "before",
    [
        "operator_node(21, PRIM_0, &symbols[6]);",
        "integer(31, HEAD, 42); /* f = lambda x.42: finite, complete code. */",
    ],
    ids=["missing-y-operator", "missing-lambda-body"],
)
def test_y_incomplete_code_fails_in_archived_dispatch(
    monkeypatch: pytest.MonkeyPatch, before: str
) -> None:
    original = reference._adapter_source

    def incomplete() -> str:
        text: str = original()
        assert text.count(before) == 1
        return text.replace(before, "")

    monkeypatch.setattr(reference, "_adapter_source", incomplete)
    with pytest.raises(
        reference.HiltonReferenceError,
        match=r"(?s)runtime failed \(70\):.*red: pc = .*unexpected type: archived bomb",
    ):
        reference.run_case("y-reconstruct")


def test_y_wrong_saved_context_fails_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = reference._adapter_source

    def wrong_context() -> str:
        text: str = original()
        before = "(++stack)->ptr = env; /* saved by the PTR20"
        assert text.count(before) == 1
        return text.replace(
            before, "(++stack)->ptr = arena + 190; /* saved by the PTR20"
        )

    monkeypatch.setattr(reference, "_adapter_source", wrong_context)
    actual = reference.run_case("y-reconstruct")
    assert actual["result"]["reconstruction"]["saved_env"] == 190
    assert actual["result"]["resumed"]["closure_env"] == 190
    with pytest.raises(reference.HiltonReferenceError, match="result mismatch"):
        reference.compare_case(
            next(c for c in CASES if c["id"] == "y-reconstruct"), actual
        )


def test_rec_q0_returns_complete_residual_and_traverses_binding() -> None:
    actual = reference.run_case("rec-q0")
    result = actual["result"]
    assert result["nodes"] == [
        {"offset": 11, "class": 0, "type": 25, "operand": 50},
        {"offset": 12, "class": 0, "type": 27, "operand": 1},
        {"offset": 13, "class": 2, "type": 3, "operand": 0},
    ]
    assert result["reconstruction"] == {
        "pc": 12,
        "mode": 2,
        "stack": 1,
        "saved_env": 198,
        "env": 198,
        "binding_offset": 1,
        "marker_target": 191,
    }
    assert result["binding_graph"] == [
        {"offset": 50, "class": 0, "type": 1, "operand": "binder"},
        {"offset": 51, "class": 2, "type": 4, "operand": 42},
    ]
    assert result["returned_nodes"] == [
        {"offset": 11, "class": 0, "type": 25, "operand": 15},
        {"offset": 12, "class": 0, "type": 27, "operand": 1},
        {"offset": 13, "class": 2, "type": 3, "operand": 0},
    ]
    assert result["returned_binding"] == [
        {"offset": 15, "class": 0, "type": 1, "operand": "binder"},
        {"offset": 16, "class": 2, "type": 4, "operand": 42},
    ]
    assert result["returned"] == {
        "root": 11,
        "stack": 0,
        "env": 198,
        "binding_offset": 0,
        "reductions": 0,
        "limit": 0,
        "minimum_fs": 197,
    }
    # The reconstructed letrec x=42 in x is finite. THOR's atomic binding
    # shortcut needs no counted contraction, but requires positive quantum.
    assert result["traversed"] == {
        "type": 4,
        "value": 42,
        "stack": 0,
        "reductions": 0,
        "limit": 1,
    }
    reference.compare_case(next(c for c in CASES if c["id"] == "rec-q0"), actual)


@pytest.mark.parametrize(
    "before",
    [
        "operator_node(50, LAMBDA, &symbols[7]);",
        "integer(51, HEAD, 42); /* complete binding: letrec x=42 in x */",
    ],
    ids=["missing-binding-header", "missing-binding-body"],
)
def test_rec_incomplete_binding_fails_in_archived_dispatch(
    monkeypatch: pytest.MonkeyPatch, before: str
) -> None:
    original = reference._adapter_source

    def incomplete() -> str:
        text: str = original()
        assert text.count(before) == 1
        return text.replace(before, "")

    monkeypatch.setattr(reference, "_adapter_source", incomplete)
    with pytest.raises(
        reference.HiltonReferenceError,
        match=r"(?s)runtime failed \(70\):.*red: pc = .*unexpected type: archived bomb",
    ):
        reference.run_case("rec-q0")


def test_strict_inventory_describes_deferred_comparisons_and_suspension() -> None:
    records = json.loads((reference.HERE / "reclamation-sites.json").read_text())
    equal = [
        r
        for r in records
        if r["path"] == "archives/STRICT/PRIMS.C" and r["symbol"] == "prim_equal"
    ]
    assert len(equal) == 2
    for record in equal:
        assert (
            "deferred structure comparisons in descending fs space" in record["trigger"]
        )
        assert "primitive/count scratch slots" not in record["trigger"]
        assert record["disposition"] == "variant-out-of-scope"
        if record["arena"] == "graph":
            assert "ws = res - 1" in record["trigger"]
            assert "Boolean results" in record["trigger"]
    suspend = next(
        r
        for r in records
        if r["path"] == "archives/STRICT/RED.C" and r["symbol"] == "inst_suspend"
    )
    assert "appends JOIN" in suspend["trigger"]
    assert "restores suspension code, context and binding offset" in suspend["trigger"]
    assert "typed primitive" not in suspend["trigger"]
    assert suspend["disposition"] == "variant-out-of-scope"


def test_strict_inventory_describes_allocation_not_thor_return() -> None:
    records = json.loads((reference.HERE / "reclamation-sites.json").read_text())
    strict = [r for r in records if r["path"] == "archives/STRICT/RED.C"]
    suspend = next(r for r in strict if r["symbol"] == "make_suspend")
    assert [location["text"] for location in suspend["locations"]] == [
        "(--fs)->type = CL_BN;  fs->op.intval = bn;",
        "(--fs)->type = CL_ENV; fs->op.addr = context;",
        "(--fs)->type = CL_PTR; fs->op.addr = code;",
    ]
    assert "three descending environment words" in suspend["trigger"]
    assert "resets ws" not in suspend["trigger"]
    for record in strict:
        if record["symbol"] == "reduce":
            assert len(record["locations"]) == 1  # entry initialization only
            assert "entry only" in record["trigger"]
            assert (
                "restore supplied freespace after red returns" not in record["trigger"]
            )


def test_unknown_case() -> None:
    with pytest.raises(reference.HiltonReferenceError, match="Unknown case"):
        reference.run_case("not-a-case")


def test_missing_compiler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CC", "hilton-nonexistent-compiler")
    with pytest.raises(reference.HiltonReferenceError, match="compiler"):
        reference.run_case(CASES[0]["id"])


def test_compilation_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    compiler = tmp_path / "bad-cc"
    compiler.write_text("#!/bin/sh\necho injected-compile-failure >&2\nexit 17\n")
    compiler.chmod(0o755)
    monkeypatch.setenv("CC", str(compiler))
    with pytest.raises(
        reference.HiltonReferenceError, match="injected-compile-failure"
    ):
        reference.run_case(CASES[0]["id"])


def test_abnormal_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    original = reference._adapter_source
    monkeypatch.setattr(
        reference,
        "_adapter_source",
        lambda: original().replace(
            "int main(int argc, char **argv) {",
            "int main(int argc, char **argv) { exit(23);",
        ),
    )
    with pytest.raises(reference.HiltonReferenceError, match=r"runtime.*23"):
        reference.run_case(CASES[0]["id"])


def test_actual_archived_body_is_observable(monkeypatch: pytest.MonkeyPatch) -> None:
    original = reference._archive_text

    def changed(path: str) -> str:
        text: str = original(path)
        if path == "RED.C":
            assert "fs = (stack--)->ptr;" in text
            return text.replace("fs = (stack--)->ptr;", "fs = (stack--)->ptr - 1;")
        return text

    monkeypatch.setattr(reference, "_archive_text", changed)
    actual = reference.run_case("atomic-child-return")
    assert actual["events"][-1]["fs"] == 199
    with pytest.raises(reference.HiltonReferenceError):
        reference.compare_case(CASES[0], actual)


def test_inventory_matches_complete_source_audit() -> None:
    reference.validate_inventory()


def test_selected_bodies_are_preserved_not_reimplemented() -> None:
    unit = reference._translation_unit()
    import re

    # Only the explicitly logged compatibility repairs may change body text.
    for replacements in reference.REPAIRS.values():
        for original, replacement in replacements:
            assert unit.count(replacement) == 1
            unit = unit.replace(replacement, original)
    unit_without_probes = re.sub(r'\n   entered\("[^"\n]+"\);', "", unit)
    for filename in ("RED.C", "PRIMS.C", "ARITH.C", "MAIN.C"):
        text = reference._archive_text(filename)
        for name, start, end in reference._functions(text):
            if name == "install_primitives":
                continue
            if filename == "MAIN.C" and name not in {"copy_graph", "shift_memory"}:
                continue
            assert text[start:end] in unit_without_probes, (filename, name)


def test_inventory_cannot_omit_or_mislocate_a_site() -> None:
    records = json.loads((reference.HERE / "reclamation-sites.json").read_text())
    missing = json.loads(json.dumps(records))
    del missing[0]["locations"][0]
    with pytest.raises(reference.HiltonReferenceError):
        reference.validate_inventory(missing)
    stale = json.loads(json.dumps(records))
    stale[0]["locations"][0]["line"] += 1
    with pytest.raises(reference.HiltonReferenceError, match="Stale"):
        reference.validate_inventory(stale)
    wrong_symbol = json.loads(json.dumps(records))
    wrong_symbol[0]["symbol"] = "not_a_function"
    with pytest.raises(reference.HiltonReferenceError, match="symbol"):
        reference.validate_inventory(wrong_symbol)


def test_source_audit_ignores_comment_and_diagnostic_assignments() -> None:
    sample = """void fixture() {
        /* ws = dead; --fs; */
        log("ws = %p, fs = %p", ws, fs);
        ws = result;
        fs = (stack--)->ptr;
        ws -= 2;
        (--fs)->type = MARKER;
    }"""
    matches = list(reference.MUTATION.finditer(reference._code(sample)))
    assert [match[0] for match in matches] == ["ws =", "fs =", "ws -=", "--fs"]


def test_thor_rewind_reset_locations_independent_of_inventory() -> None:
    # Hand-audited against BASE THOR, not generated from the inventory JSON.
    expected = {
        "RED.C": {92, 93, 119, 337, 338, 347, 403, 663},
        "PRIMS.C": {212, 218, 224, 379, 475, 512, 1064, 1079, 1094, 1108},
        "ARITH.C": {
            80,
            92,
            101,
            110,
            127,
            136,
            144,
            160,
            228,
            242,
            260,
            274,
            363,
            492,
            526,
        },
        "MAIN.C": {133, 134},
    }
    sites = reference.audit_sites()
    for filename, required_lines in expected.items():
        audited = {
            line
            for path, _symbol, _arena, line in sites
            if path == f"archives/THOR/{filename}"
        }
        assert required_lines <= audited
    # Negative authority distinctions are part of the inventory contract.
    records = json.loads((reference.HERE / "reclamation-sites.json").read_text())
    for path, symbol in [
        ("archives/STRICT/RED.C", "inst_join"),
        ("archives/DEC6/RED.C", "inst_join"),
        ("archives/WORK/RED.C", "inst_join"),
        ("archives/SNARL/EXPERIME/RED.C", "inst_rptr"),
        ("archives/SNARL/OPT/PRIMS.C", "prim_equal_star"),
    ]:
        found = [
            record
            for record in records
            if record["path"] == path and record["symbol"] == symbol
        ]
        assert found
        assert all(record["disposition"] == "variant-out-of-scope" for record in found)


def test_concurrent_cases_have_isolated_builds() -> None:
    from concurrent.futures import ThreadPoolExecutor

    ids = ("atomic-child-return", "copy-shift", "equal-scratch")
    with ThreadPoolExecutor(max_workers=3) as executor:
        actuals = list(executor.map(reference.run_case, ids))
    for case_id, actual in zip(ids, actuals, strict=True):
        case = next(case for case in CASES if case["id"] == case_id)
        reference.compare_case(case, actual)


@pytest.mark.parametrize(
    "case_id",
    [
        "promote-left-pointer",
        "promote-right-pointer",
        "ubv-equal",
        "ubv-unequal",
    ],
)
def test_original_hazard_is_failure_not_reference_success(
    monkeypatch: pytest.MonkeyPatch, case_id: str, sanitized_compiler: None
) -> None:
    monkeypatch.setattr(reference, "_apply_repairs", lambda text, _path: text)
    with pytest.raises(
        reference.HiltonReferenceError, match="runtime failed"
    ) as failure:
        reference.run_case(case_id)
    assert "runtime error:" in str(failure.value) or "AddressSanitizer" in str(
        failure.value
    )


def test_unhandled_equal_tag_fails_instead_of_falling_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = reference._adapter_source

    def unsupported() -> str:
        text: str = original()
        for offset in (190, 191):
            before = f"arena[{offset}].type = UBV;"
            assert text.count(before) == 1
            text = text.replace(before, f"arena[{offset}].type = NOOP;")
        return text

    monkeypatch.setattr(reference, "_adapter_source", unsupported)
    with pytest.raises(
        reference.HiltonReferenceError, match="unsupported nodes_equal tag 29"
    ):
        reference.run_case("ubv-equal")


def test_repair_evidence_is_required() -> None:
    case = next(case for case in CASES if case["id"] == "ubv-equal")
    actual = reference.run_case(case["id"])
    assert actual["authority"]["execution"] == "repaired-C"
    for field in ("repairs_exercised", "repairs_applied", "execution"):
        broken = json.loads(json.dumps(actual))
        del broken["authority"][field]
        with pytest.raises(reference.HiltonReferenceError, match="repair evidence"):
            reference.compare_case(case, broken)


@pytest.fixture
def sanitized_compiler(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import os
    import shlex
    import shutil

    compiler = shutil.which(os.environ.get("CC", "cc"))
    assert compiler is not None, "Missing C compiler for sanitizer proof"
    wrapper = tmp_path / "sanitized-cc"
    wrapper.write_text(
        f"#!/bin/sh\nexec {shlex.quote(compiler)} "
        '-fsanitize=address,undefined -fno-sanitize-recover=all "$@"\n'
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("CC", str(wrapper))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_case_sanitizer_clean(sanitized_compiler: None, case: dict[str, Any]) -> None:
    reference.compare_case(case, reference.run_case(case["id"]))

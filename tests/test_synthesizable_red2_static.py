import ast
import os
import subprocess
import sys
from pathlib import Path


def test_task14_hardware_checker_pins_real_frontend_and_persistent_processor() -> None:
    text = Path("scripts/check_syn.py").read_text()
    assert "171c52b3f1411f632a07ccfc3dbfb177efa901cd" in text
    assert 'PROCESSOR_SOURCE = Path("src/machines/synthesizable_red2_machine/machine.py")' in text
    assert "legacy red2_step_word" in text
    assert "--no_synth" in text
    assert "PY_TO_LOGIC.PARSE_FILE" not in text
    assert "TRIM_COLLAPSE_LOGIC" not in text
    assert "SynthesizableRED2Machine_*.vhd" in text
    assert "--comb" in text
    assert "Skipping synthesis" in text
    assert "check_syn_sim.py" in text
    assert "native Synthesizable RED2 parity failed" in text


def test_task14_explicit_gate_hard_fails_when_frontend_is_hidden() -> None:
    env = os.environ.copy()
    env.pop("PIPELINEC_ROOT", None)
    env["PATH"] = ""
    result = subprocess.run(
        [sys.executable, "scripts/check_syn.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.strip() == (
        "syn-check: missing PipelineC/Pypeline frontend; "
        "set PIPELINEC_ROOT to a checkout at "
        "171c52b3f1411f632a07ccfc3dbfb177efa901cd or put pypelinec/pipelinec on PATH"
    )


def test_task14_frontend_only_bypasses_synthesis_backend_preflight(tmp_path: Path) -> None:
    fake_frontend = tmp_path / "pypelinec"
    fake_frontend.write_text("#!/bin/sh\nexit 0\n")
    fake_frontend.chmod(0o755)

    env = os.environ.copy()
    env.pop("PIPELINEC_ROOT", None)
    env["PATH"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "scripts/check_syn.py", "--frontend-only"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 4
    assert "synthesis backend unavailable" not in result.stderr
    assert "did not emit SynthesizableRED2Machine VHDL" in result.stderr


def test_task14_full_gate_hard_fails_before_frontend_when_synthesis_backend_is_hidden(
    tmp_path: Path,
) -> None:
    fake_frontend = tmp_path / "pypelinec"
    fake_frontend.write_text("#!/bin/sh\nexit 99\n")
    fake_frontend.chmod(0o755)

    env = os.environ.copy()
    env.pop("PIPELINEC_ROOT", None)
    env["PATH"] = str(tmp_path)
    result = subprocess.run(
        [sys.executable, "scripts/check_syn.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 5
    assert result.stderr.strip() == (
        "syn-check: synthesis backend unavailable: the generic PyRTL flow "
        "requires Yosys plus a usable GHDL prefix; install the synthesis toolchain "
        "or use --frontend-only"
    )


def test_task14_mise_exposes_explicit_non_skipping_hardware_gate() -> None:
    text = Path(".mise.toml").read_text()
    assert "[tasks.syn-check]" in text
    assert "scripts/check_syn.py" in text
    assert "setuptools" in text
    assert "pyrtl==0.11.3" in text


def test_task14_synthesizable_red2_top_has_persistent_hardware_state_contract() -> None:
    source = Path("src/machines/synthesizable_red2_machine/machine.py").read_text()
    assert "@MAIN(25.0)" in source
    assert "def SynthesizableRED2Machine" in source
    assert "make_ram(" in source
    assert "class red2_word_t(NamedTuple)" in source
    assert "class red2_control_t(NamedTuple)" in source
    assert "RED2_SYNTH_SEMANTICS_COMPLETE = 0" in source
    assert "red2_step_word" not in source
    assert "ConcreteRED2Machine(" not in source


def test_task14_microstate_dispatch_stays_flat_for_pipelinec() -> None:
    path = Path("src/machines/synthesizable_red2_machine/machine.py")
    tree = ast.parse(path.read_text())
    top = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "SynthesizableRED2Machine"
    )

    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(top):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    long_dispatch_chains: list[tuple[int, int]] = []
    for node in ast.walk(top):
        if not isinstance(node, ast.If) or node.col_offset != 8:
            continue
        parent = parents.get(node)
        if (
            isinstance(parent, ast.If)
            and len(parent.orelse) == 1
            and parent.orelse[0] is node
        ):
            continue

        count = 1
        cursor = node
        while len(cursor.orelse) == 1 and isinstance(cursor.orelse[0], ast.If):
            cursor = cursor.orelse[0]
            count += 1
        if count >= 40:
            long_dispatch_chains.append((node.lineno, count))

    assert long_dispatch_chains == []
    source = path.read_text()
    assert "micro_is_commit_entry: uint1_t = microstate == MICRO_COMMIT" in source
    assert "clock_dispatch_handled: uint1_t = 0" in source
    assert source.count("clock_dispatch_handled = 1") == 128


def test_task14_closure_code_validation_keeps_mixed_width_predicates_split() -> None:
    """PipelineC 171c52b collides helper names for the compound mixed-width form."""

    text = Path("src/machines/synthesizable_red2_machine/machine.py").read_text()
    assert (
        "if not equality_child_left_code_valid or "
        "equality_child_left_code_opcode != MOP_NONE:"
    ) not in text
    assert (
        "if not equality_child_right_code_valid or "
        "equality_child_right_code_opcode != MOP_NONE:"
    ) not in text
    for side in ("left", "right"):
        assert (
            f"equality_child_{side}_code_is_none: uint1_t = "
            f"equality_child_{side}_code_opcode == MOP_NONE"
        ) in text
        assert (
            f"equality_child_{side}_code_bad: uint1_t = "
            f"equality_child_{side}_code_valid == 0"
        ) in text
        assert (
            f"equality_child_{side}_code_bad = equality_child_{side}_code_bad or "
            f"equality_child_{side}_code_is_none == 0"
        ) in text


def test_task14_recursive_lambda_metadata_checks_remain_split_for_pipelinec() -> None:
    """PipelineC 171c52b must not lower mixed-width != comparisons at one bool site."""

    text = Path("src/machines/synthesizable_red2_machine/machine.py").read_text()
    forbidden = (
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "join_true_literal_id != 0",
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "join_false_literal_id != 0",
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "join_equal_if_literal_id != 0",
    )
    for compound in forbidden:
        assert compound not in text

    for name, source in (
        ("star", "join_equal_star_literal_id"),
        ("true", "join_true_literal_id"),
        ("false", "join_false_literal_id"),
        ("if", "join_equal_if_literal_id"),
    ):
        assert (
            f"equality_child_lambda_has_{name}: uint1_t = {source} != 0"
        ) in text

    assert (
        "equality_child_lambda_meta_ok: uint1_t = "
        "equality_child_lambda_has_star and equality_child_lambda_has_true"
    ) in text
    assert (
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "equality_child_lambda_has_false"
    ) in text
    assert (
        "equality_child_lambda_meta_ok = equality_child_lambda_meta_ok and "
        "equality_child_lambda_has_if"
    ) in text

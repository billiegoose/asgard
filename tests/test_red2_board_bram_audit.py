"""Pin BRAM FASM checks to explicit configuration and initialization fixtures."""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "red2_board_bram_audit", ROOT / "scripts/boards/red2_basys3/audit_bram.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
TILE = "BRAM_L_X0Y0"


def fixture(tmp_path, *, is36=True, half=0, readonly=False):
    site = "RAMB36_X0Y0" if is36 else f"RAMB18_X0Y{half}"
    params = {
        "READ_WIDTH_A": format(9 if readonly else 72 if is36 else 36, "032b"),
        "WRITE_WIDTH_B": format(0 if readonly else 72 if is36 else 36, "032b"),
        "INIT_00": format(3, "0256b"),
        "INIT_01": format(1 << 255, "0256b"),
    }
    cell = {
        "type": "RAMB36E1_RAMB36E1" if is36 else "RAMB18E1_RAMB18E1",
        "attributes": {"NEXTPNR_BEL": site + ("/RAMB36E1" if is36 else "/RAMB18E1")},
        "parameters": params,
    }
    features = []
    for part in (0, 1) if is36 else (half,):
        prefix = f"{TILE}.RAMB18_Y{part}"
        markers = ["IN_USE", "ZINV_CLKARDCLK", "ZINV_CLKBWRCLK"]
        if readonly:
            markers += ["READ_WIDTH_A_4"]
        else:
            markers += [
                "READ_WIDTH_B_18",
                "WRITE_WIDTH_A_18",
                "WRITE_WIDTH_B_18",
                "SDP_READ_WIDTH_36",
                "SDP_WRITE_WIDTH_36",
            ]
            if is36 or half == 1:
                markers += ["READ_WIDTH_A_18"]
        features.extend(prefix + "." + marker for marker in markers)
        if is36:
            # Logical bits 0/1 go to lower/upper halves. Logical INIT_01 bit
            # 255 becomes bit 255 in the upper half's physical INIT_00.
            value = 1 if part == 0 else (1 << 255) | 1
            features += [prefix + f".INIT_00[255:0] = 256'b{value:0256b}"]
        else:
            features += [
                prefix + f".INIT_00[255:0] = 256'b{3:0256b}",
                prefix + f".INIT_01[255:0] = 256'b{1 << 255:0256b}",
            ]
    if readonly:
        features += [TILE + ".RAMB36.BRAM36_READ_WIDTH_A_1"]
    paths = (tmp_path / "routed.json", tmp_path / "board.fasm", tmp_path / "grid.json")
    paths[0].write_text(json.dumps({"modules": {"top": {"cells": {"ram": cell}}}}))
    paths[1].write_text("\n".join(features) + "\n")
    paths[2].write_text(json.dumps({TILE: {"sites": {site: "RAMBFIFO36E1"}}}))
    return paths


def test_sdp72_both_write_halves_and_split_initializers(tmp_path):
    result = module.audit(*fixture(tmp_path))
    assert result["passed"]
    assert result["BRAM18_halves"] == 2
    assert result["known_initialization_bits_checked"] == 2 * 72 * 256


def test_missing_sdp72_low_write_side_is_detected(tmp_path):
    paths = fixture(tmp_path)
    marker = TILE + ".RAMB18_Y0.WRITE_WIDTH_A_18\n"
    paths[1].write_text(paths[1].read_text().replace(marker, ""))
    result = module.audit(*paths)
    assert not result["passed"]
    error = next(e for e in result["mismatches"] if e.get("kind") == "width markers")
    assert set(error["expected"]) - set(error["actual"]) == {"WRITE_WIDTH_A_18"}


@pytest.mark.parametrize("half", [0, 1])
def test_sdp36_lower_and_upper_half_markers(tmp_path, half):
    assert module.audit(*fixture(tmp_path, is36=False, half=half))["passed"]


def test_wrong_initializer_half_is_detected(tmp_path):
    paths = fixture(tmp_path)
    original = f"256'b{(1 << 255) | 1:0256b}"
    paths[1].write_text(paths[1].read_text().replace(original, f"256'b{1:0256b}"))
    result = module.audit(*paths)
    assert not result["passed"]
    error = next(e for e in result["mismatches"] if e.get("kind") == "initialization")
    assert error["feature"] == TILE + ".RAMB18_Y1.INIT_00"


def test_odd_width_rom_pairing_flag_is_required(tmp_path):
    paths = fixture(tmp_path, readonly=True)
    assert module.audit(*paths)["passed"]
    paths[1].write_text(
        paths[1].read_text().replace(TILE + ".RAMB36.BRAM36_READ_WIDTH_A_1\n", "")
    )
    result = module.audit(*paths)
    assert not result["passed"]
    assert any("BRAM36_READ_WIDTH_A_1" in e["feature"] for e in result["mismatches"])


def test_registered_output_requires_matching_register_clock(tmp_path):
    paths = fixture(tmp_path)
    data = json.loads(paths[0].read_text())
    data["modules"]["top"]["cells"]["ram"]["parameters"]["DOA_REG"] = "1"
    paths[0].write_text(json.dumps(data))
    with paths[1].open("a") as output:
        for half in (0, 1):
            output.write(f"{TILE}.RAMB18_Y{half}.DOA_REG\n")
    result = module.audit(*paths)
    assert not result["passed"]
    assert sum("ZINV_REGCLKARDRCLK" in e["feature"] for e in result["mismatches"]) == 2
    with paths[1].open("a") as output:
        for half in (0, 1):
            output.write(f"{TILE}.RAMB18_Y{half}.ZINV_REGCLKARDRCLK\n")
    assert module.audit(*paths)["passed"]


def test_unknown_initializer_syntax_cannot_silently_read_as_zero(tmp_path):
    paths = fixture(tmp_path)
    with paths[1].open("a") as output:
        output.write(TILE + ".RAMB18_Y0.INIT_02[255:0] = 256'h1\n")
    with pytest.raises(ValueError, match="unsupported BRAM initializer syntax"):
        module.audit(*paths)

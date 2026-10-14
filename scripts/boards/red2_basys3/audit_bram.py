"""Check routed BRAM initialization and configuration against emitted FASM.

This checks the intended nextpnr configuration, including the existing SDP72
write-width fix. It does not establish routed connectivity, bitstream frame
conversion, timing, or physical behavior.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path


def number(cell, name):
    return int(cell["parameters"].get(name, "0"), 2)


def init_word(cell, name):
    bits = cell["parameters"].get(name, "0" * 256).lower()
    assert len(bits) == 256 and set(bits) <= set("01x"), (name, bits)
    return (
        int(bits.replace("x", "0"), 2),
        int("".join("0" if bit == "x" else "1" for bit in bits), 2),
    )


def half_word(value, half):
    return sum(((value >> (2 * bit + half)) & 1) << bit for bit in range(128))


def width_markers(cell, is36, half):
    result = set()
    for name in ("READ_WIDTH_A", "READ_WIDTH_B", "WRITE_WIDTH_A", "WRITE_WIDTH_B"):
        width = number(cell, name)
        if not width:
            if name == "READ_WIDTH_B" and number(cell, "READ_WIDTH_A") == (
                72 if is36 else 36
            ):
                result.add(name + "_18")
            if name == "WRITE_WIDTH_A" and number(cell, "WRITE_WIDTH_B") == (
                72 if is36 else 36
            ):
                # Both physical halves write the low side of SDP72. This is
                # the existing openxc7-sdp72-write-width.patch correction.
                result.add(name + "_18")
            continue
        actual = width if not is36 or width == 1 else width // 2
        if (
            (is36 and width == 72) or (half == 1 and actual == 36)
        ) and name == "READ_WIDTH_A":
            result.add(name + "_18")
        if actual == 36:
            result.add("SDP_" + name[:-2] + "_36")
            if name.startswith("WRITE_WIDTH") or name == "READ_WIDTH_B":
                result.add(name + "_18")
        else:
            paired = [number(cell, name[:-1] + port) for port in ("A", "B")]
            sdp = any(
                (value if not is36 or value in (0, 1) else value // 2) == 36
                for value in paired
            )
            if not (sdp and actual == 1):
                result.add(name + "_" + str(actual))
    return result


def read_fasm(path):
    features, initializers, widths = set(), {}, {}
    pattern = re.compile(
        r"(\S+\.RAMB18_Y[01])\.(INITP?_[0-9A-F]{2})"
        r"\[255:0\] = 256'b([01]{256})"
    )
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        match = pattern.fullmatch(line)
        if match:
            initializers[match[1] + "." + match[2]] = int(match[3], 2)
        elif ".RAMB18_Y" in line and (".INIT_" in line or ".INITP_" in line):
            raise ValueError("unsupported BRAM initializer syntax: " + line)
        if "=" not in line:
            features.add(line)
        if ".RAMB18_Y" in line and "=" not in line:
            prefix, marker = line.rsplit(".", 1)
            if marker.startswith(
                ("READ_WIDTH_", "WRITE_WIDTH_", "SDP_READ_WIDTH_", "SDP_WRITE_WIDTH_")
            ):
                widths.setdefault(prefix, set()).add(marker)
    return features, initializers, widths


def audit(netlist, fasm, tilegrid):
    module = json.loads(netlist.read_text())["modules"]["top"]
    grid = json.loads(tilegrid.read_text())
    sites = {site: tile for tile, data in grid.items() for site in data["sites"]}
    features, actual_init, actual_widths = read_fasm(fasm)
    errors, used, expected_keys = [], set(), set()
    cells = words = known_bits = flags = 0

    def flag(cell, prefix, name, wanted):
        nonlocal flags
        flags += 1
        actual = prefix + "." + name in features
        if actual != wanted:
            errors.append(
                {
                    "cell": cell,
                    "feature": prefix + "." + name,
                    "expected": wanted,
                    "actual": actual,
                }
            )

    for name, cell in module["cells"].items():
        if cell["type"] not in ("RAMB18E1_RAMB18E1", "RAMB36E1_RAMB36E1"):
            continue
        cells += 1
        is36 = cell["type"].startswith("RAMB36")
        site = cell["attributes"]["NEXTPNR_BEL"].split("/")[0]
        tile = sites[site]
        halves = (0, 1) if is36 else (int(re.search(r"Y(\d+)$", site)[1]) % 2,)
        for half in halves:
            prefix = f"{tile}.RAMB18_Y{half}"
            assert prefix not in used, ("overlapping BRAM placement", prefix)
            used.add(prefix)
            flag(name, prefix, "IN_USE", True)
            wanted = width_markers(cell, is36, half)
            actual = actual_widths.get(prefix, set())
            if wanted != actual:
                errors.append(
                    {
                        "cell": name,
                        "feature": prefix,
                        "kind": "width markers",
                        "expected": sorted(wanted),
                        "actual": sorted(actual),
                    }
                )
            for port, clock, regclock in (
                ("A", "CLKARDCLK", "REGCLKARDRCLK"),
                ("B", "CLKBWRCLK", "REGCLKB"),
            ):
                registered = bool(number(cell, "DO" + port + "_REG"))
                follows = not bool(number(cell, "IS_" + clock + "_INVERTED"))
                flag(name, prefix, "DO" + port + "_REG", registered)
                flag(name, prefix, "ZINV_" + clock, follows)
                flag(name, prefix, "ZINV_" + regclock, registered and follows)
                mode = cell["parameters"].get("WRITE_MODE_" + port, "WRITE_FIRST")
                assert mode in ("WRITE_FIRST", "READ_FIRST", "NO_CHANGE"), mode
                for option in ("READ_FIRST", "NO_CHANGE"):
                    flag(
                        name,
                        prefix,
                        "WRITE_MODE_" + port + "_" + option,
                        mode == option,
                    )
            for parity, amount in (("", 64), ("P", 8)):
                for index in range(amount):
                    key = prefix + f".INIT{parity}_{index:02X}"
                    expected_keys.add(key)
                    if is36:
                        lo, lomask = init_word(cell, f"INIT{parity}_{2 * index:02X}")
                        hi, himask = init_word(
                            cell, f"INIT{parity}_{2 * index + 1:02X}"
                        )
                        value = half_word(lo, half) | (half_word(hi, half) << 128)
                        mask = half_word(lomask, half) | (
                            half_word(himask, half) << 128
                        )
                    else:
                        value, mask = init_word(cell, f"INIT{parity}_{index:02X}")
                    actual = actual_init.get(key, 0)
                    if (actual ^ value) & mask:
                        errors.append(
                            {
                                "cell": name,
                                "feature": key,
                                "kind": "initialization",
                                "expected": hex(value),
                                "actual": hex(actual),
                                "known_mask": hex(mask),
                            }
                        )
                    words += 1
                    known_bits += mask.bit_count()
        if is36:
            for key in (
                "READ_WIDTH_A",
                "READ_WIDTH_B",
                "WRITE_WIDTH_A",
                "WRITE_WIDTH_B",
            ):
                flag(
                    name,
                    tile,
                    "RAMB36.BRAM36_" + key + "_1",
                    number(cell, key) in (1, 9),
                )
    extra = [
        key for key, value in actual_init.items() if key not in expected_keys and value
    ]
    if extra:
        errors.append(
            {"kind": "nonzero initialization outside mapped BRAM", "features": extra}
        )
    actual_used = {
        feature.removesuffix(".IN_USE")
        for feature in features
        if re.fullmatch(r".+\.RAMB18_Y[01]\.IN_USE", feature)
    }
    if actual_used != used:
        errors.append(
            {
                "kind": "BRAM occupancy",
                "expected": sorted(used),
                "actual": sorted(actual_used),
            }
        )
    return {
        "scope": "Routed BRAM known init bits and intended FASM configuration; "
        "not frame conversion, connectivity, timing, or physical behavior",
        "passed": not errors,
        "BRAM_cells": cells,
        "BRAM18_halves": len(used),
        "initialization_words_checked": words,
        "known_initialization_bits_checked": known_bits,
        "configuration_flags_checked": flags,
        "width_marker_sets_checked": len(used),
        "mismatch_count": len(errors),
        "mismatches": errors,
        "artifacts_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (netlist, fasm, tilegrid)
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("fasm", type=Path)
    parser.add_argument("tilegrid", type=Path)
    args = parser.parse_args()
    result = audit(args.netlist, args.fasm, args.tilegrid)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

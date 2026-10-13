"""Prepare a Basys 3 build from the exact RTL-validated, mapped RED2 candidate."""

import argparse
import hashlib
import json
import shlex
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/red2-basys3")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "docs/handoffs/synth-red2-cfg-scalar-core-results.json",
    )
    parser.add_argument("--variant", default="cfg-integer-joins-regfix")
    parser.add_argument(
        "--relocate-response-byte",
        action="store_true",
        help="Move only the final response-byte LUT/FF pairs after placement",
    )
    args = parser.parse_args()
    report_path = args.report.resolve()
    report = json.loads(report_path.read_text())
    candidate = report["variants"][args.variant]
    if not candidate["usable_fit_candidate"]:
        raise ValueError("the measured candidate has not passed its validation gate")
    source = Path(candidate["configuration"]["RED2_CFG_PILOT_OUT"])
    top_path = source / "integrated-stream"
    mapped_path = top_path / "baseline-area.json"
    if sha(mapped_path) != candidate["artifacts"][str(mapped_path)]:
        raise ValueError("mapped core differs from its measured artifact")
    if sha(top_path / "machine.py") != candidate["candidate_source_sha256"]:
        raise ValueError("candidate source differs from its validated artifact")
    # This wrapper is deliberately specific to the measured public ABI.
    packed_path = top_path / "rtl-netlist/wrapper.v"
    if sha(packed_path) != candidate["verilator_netlist_provenance"]["wrapper_sha256"]:
        raise ValueError("packed port adapter differs from the RTL replay adapter")
    packed = packed_path.read_text()
    if "input [721:0] incoming, output [625:0] result" not in packed:
        raise ValueError("unsupported packed public-port layout")
    mapped = json.loads(mapped_path.read_text())
    module = mapped["modules"].pop("top")
    buffers = [(n, c) for n, c in module["cells"].items() if c["type"] == "BUFG"]
    if len(buffers) != 1:
        raise ValueError("expected exactly one measured core clock buffer")
    clock_buffer_name, buffer = buffers[0]
    (clock_in,) = buffer["connections"]["I"]
    (clock_out,) = buffer["connections"]["O"]
    if module["ports"]["clk_25p0"]["bits"] != [clock_in]:
        raise ValueError("measured BUFG is not attached to the public core clock")
    # Move only the clock buffer to the board boundary, where BUFGCE can pause
    # every core register and RAM. Preserve every logic/memory cell verbatim.
    del module["cells"][clock_buffer_name]
    rewritten = 0
    for cell in module["cells"].values():
        for port, bits in cell["connections"].items():
            for index, bit in enumerate(bits):
                if bit == clock_out:
                    if cell["port_directions"][port] != "input":
                        raise ValueError("clock buffer output has another driver")
                    bits[index] = clock_in
                    rewritten += 1
    for net in module["netnames"].values():
        net["bits"] = [clock_in if bit == clock_out else bit for bit in net["bits"]]
    module["attributes"].pop("top", None)
    mapped["modules"]["red2_core"] = module
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / "core.json").write_text(json.dumps(mapped, separators=(",", ":")))
    packed = packed.replace("module replay_top(", "module red2_packed_core(", 1)
    packed = packed.replace("top dut(", "red2_core dut(", 1)
    (output / "packed.v").write_text(packed)
    for name in (
        "uart.v",
        "monitor.v",
        "board.v",
        "implement.sh",
        "audit.py",
        "clocks.py",
        "relocate_monitor.py",
    ):
        shutil.copy2(HERE / name, output / name)
    pins = {"clk_100p0": "W5", "RsRx": "B18", "RsTx": "A18"}
    pins.update(
        {
            f"LD[{i}]": pin
            for i, pin in enumerate(
                ["U16", "E19", "U19", "V19", "W18", "U15", "U14", "V14"]
            )
        }
    )
    xdc = "".join(
        f"set_property LOC {pin} [get_ports {{{port}}}]\n"
        f"set_property IOSTANDARD LVCMOS33 [get_ports {{{port}}}]\n"
        for port, pin in pins.items()
    )
    xdc += "create_clock -period 10 [get_ports clk_100p0]\n"
    xdc += "create_clock -period 100 [get_nets clock]\n"
    xdc += "create_clock -period 100 [get_nets core_clock]\n"
    (output / "board.xdc").write_text(xdc)
    # Saved placement JSON does not preserve native XDC clock constraints.
    # Generic SDC is loaded after JSON import, including a route-only resume.
    (output / "board.sdc").write_text(
        "create_clock -period 10 [get_ports clk_100p0]\n"
        "create_clock -period 100 [get_nets clock]\n"
        "create_clock -period 100 [get_nets core_clock]\n"
    )
    (output / "area.abc").write_text("strash\ndc2\nif -a\n")
    (output / "board-placement-options.json").write_text(
        json.dumps({"relocate_response_byte": args.relocate_response_byte}, indent=2)
        + "\n"
    )
    (output / "board.ys").write_text(
        "read_json core.json\n"
        "read_verilog uart.v monitor.v packed.v board.v\n"
        "synth_xilinx -arch xc7 -top red2_basys3 -flatten -run begin:map_luts\n"
        "abc -lut 6 -script area.abc\nclean\n"
        "techmap -map +/xilinx/ff_map.v\n"
        "techmap -map +/xilinx/lut_map.v -map +/xilinx/cells_map.v -D LUT_WIDTH=6\n"
        "xilinx_dffopt\nopt_lut_ins -tech xilinx\n"
        "synth_xilinx -arch xc7 -top red2_basys3 -run finalize:edif\n"
        "write_json board.json\n"
    )
    shutil.copy2(ROOT / "scripts/yosys_resources.py", output / "yosys_resources.py")
    image = report["container_image"]
    command = [
        "podman",
        "run",
        "--rm",
        "-v",
        "fpgatool-nix:/nix",
        "-v",
        f"{ROOT / 'tools/fpgatool'}:/toolchain:ro",
        "-v",
        f"{output}:/design",
        "-w",
        "/design",
        image,
        "nix",
        "--extra-experimental-features",
        "nix-command flakes",
        "develop",
        "path:/toolchain/toolchain",
        "--command",
        "bash",
        "implement.sh",
    ]
    (output / "build.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n" + shlex.join(command) + "\n"
    )
    preparation = {
        "candidate_source_sha256": candidate["candidate_source_sha256"],
        "compiler_manifest_sha256": candidate["compiler_manifest_sha256"],
        "validation_report_sha256": sha(report_path),
        "mapped_core_sha256": sha(mapped_path),
        "mapped_core_path": str(mapped_path),
        "original_core_resources": candidate["resources"],
        "core_transform": {
            "removed_cell": clock_buffer_name,
            "removed_type": "BUFG",
            "clock_connections_rebound": rewritten,
            "replacement": "board BUFGCE; no logic or memory cell changes",
        },
        "container_image": image,
        "fpgatool_commit": report.get("fpgatool_commit")
        or report["compiler_register_reannotation_fix"]["fpgatool_commit"],
        "core_clock_mhz": 10,
        "uart_baud": 115200,
        "input_width": 722,
        "output_width": 626,
        "files_sha256": {p.name: sha(p) for p in sorted(output.iterdir())},
        "status": "prepared; no board mapping, routing or programming result yet",
    }
    (output / "provenance.json").write_text(json.dumps(preparation, indent=2) + "\n")
    print("BOARD_BUILD_PREPARED", output, flush=True)


if __name__ == "__main__":
    main()

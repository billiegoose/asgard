"""Replay public-port vectors against the exact area-map frontend netlist."""

import hashlib
import json
import re
import shlex
import sys

from paths import INTEGRATED

root = INTEGRATED / "rtl-netlist"
coarse = INTEGRATED / "coarse.json"
netlist = root / "clean.v"
if "--conversion-only" in sys.argv:
    assert coarse.is_file()
    root.mkdir(exist_ok=True)
    (root / "convert.ys").write_text(
        "read_json /experiment/coarse.json\n"
        "rename -hide\nopt_clean -purge\nmemory_unpack\n"
        "write_verilog -noattr /experiment/rtl-netlist/clean.v\n"
    )
    print("PREPARED_VERILATOR_CONVERSION", root, flush=True)
    raise SystemExit(0)
assert netlist.is_file()
top = json.loads(coarse.read_text())["modules"]["top"]
ports = top["ports"]
pkg = (INTEGRATED / "hdl/c_structs_pkg.pkg.vhd").read_text()
top_vhdl = (INTEGRATED / "hdl/top/top.vhd").read_text()
connections = [".clk_25p0(clk_25p0)"]
seen = {"clk_25p0"}
sizes = {}
for suffix, direction, vector in (
    ("incoming_command", "in", "incoming"),
    ("return_output", "out", "result"),
):
    typ = re.search(rf"{suffix}\s*:\s*{direction} (\w+)", top_vhdl)[1]
    body = re.search(rf"type {typ} is record\s+(.*?)end record;", pkg, re.S)[1]
    fields = re.findall(r"(\w+)\s*:\s*(?:unsigned\(\d+ downto 0\)|\w+)\s*;", body)
    offset = 0
    for field in fields:
        port = f"SynthesizableRED2Machine_{suffix}[{field}]"
        width = len(ports[port]["bits"])
        connections.append(f".\\{port} ({vector}[{offset + width - 1}:{offset}])")
        seen.add(port)
        offset += width
    sizes[vector] = offset
assert seen == ports.keys()
incoming, outgoing = sizes["incoming"], sizes["result"]
wrapper = (
    f"module replay_top(input clk_25p0, input [{incoming - 1}:0] incoming, "
    f"output [{outgoing - 1}:0] result);\ntop dut(\n"
    + ",\n".join(connections)
    + "\n);\nendmodule\n"
)
(root / "wrapper.v").write_text(wrapper)
source = r"""#include "Vreplay_top.h"
#include "verilated.h"
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

static void unpack(const std::string& hex, WData* words, unsigned count) {
  for (unsigned i = 0; i < count; ++i) {
    unsigned end = hex.size() > 8*i ? hex.size() - 8*i : 0;
    unsigned begin = end > 8 ? end - 8 : 0;
    words[i] = end ? std::strtoul(hex.substr(begin, end-begin).c_str(), 0, 16) : 0;
  }
}
int main(int argc, char** argv) {
  if (argc != 3) return 2;
  Verilated::commandArgs(argc, argv);
  std::ifstream vectors(argv[1]);
  if (!vectors) return 2;
  Vreplay_top* top = new Vreplay_top;
  top->clk_25p0 = 0;
  for (unsigned i=0; i<INPUT_WORDS; ++i)
    top->incoming[i] = 0;
  top->eval();
  unsigned cycles = 0;
  std::string incoming, expected;
  while (vectors >> incoming >> expected) {
    unpack(incoming, top->incoming, INPUT_WORDS);
    top->eval();
    WData wanted[OUTPUT_WORDS];
    unpack(expected, wanted, OUTPUT_WORDS);
    for (unsigned i=0; i<OUTPUT_WORDS; ++i) {
      WData mask = i+1 == OUTPUT_WORDS ? LAST_MASK : 0xffffffffU;
      WData actual = top->result[i] & mask;
      if (actual != (wanted[i] & mask)) {
        std::cerr << "RTL mismatch cycle " << cycles << " output word " << i
          << " actual " << std::hex << actual << " expected " << wanted[i] << '\n';
        return 1;
      }
    }
    top->clk_25p0 = 1;
    top->eval();
    top->clk_25p0 = 0;
    top->eval();
    if (++cycles % 1000 == 0)
      std::cout << "INTEGRATED_VERILATOR_REPLAY_PROGRESS " << cycles << std::endl;
  }
  if (!vectors.eof() || cycles != std::strtoul(argv[2], 0, 10)) return 2;
  top->final();
  delete top;
  std::cout << "INTEGRATED_VERILATOR_REPLAY_PASS " << cycles << std::endl;
}
"""
source = (
    source.replace("INPUT_WORDS", str((incoming + 31) // 32))
    .replace("OUTPUT_WORDS", str((outgoing + 31) // 32))
    .replace("LAST_MASK", hex((1 << ((outgoing - 1) % 32 + 1)) - 1) + "U")
)
(root / "replay.cpp").write_text(source)
obj = root / "obj"
(root / "build.sh").write_text(
    "#!/usr/bin/env bash\nset -euo pipefail\n"
    f"verilator --version > {shlex.quote(str(root / 'simulator-versions.txt'))}\n"
    "verilator --cc --exe -Wno-fatal --top-module replay_top "
    f"--Mdir {shlex.quote(str(obj))} "
    f"{shlex.quote(str(netlist))} {shlex.quote(str(root / 'wrapper.v'))} "
    f"{shlex.quote(str(root / 'replay.cpp'))}\n"
    f"make -C {shlex.quote(str(obj))} -f Vreplay_top.mk -j 4\n"
)
metadata = {
    "coarse_json_sha256": hashlib.sha256(coarse.read_bytes()).hexdigest(),
    "coarse_verilog_sha256": hashlib.sha256(netlist.read_bytes()).hexdigest(),
    "candidate_sha256": hashlib.sha256(
        (INTEGRATED / "machine.py").read_bytes()
    ).hexdigest(),
    "replay_cpp_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "wrapper_sha256": hashlib.sha256(wrapper.encode()).hexdigest(),
    "conversion_passes": (
        "read_json; rename -hide; opt_clean -purge; memory_unpack; "
        "write_verilog -noattr"
    ),
    "input_width": incoming,
    "output_width": outgoing,
    "scope": "Optimized GHDL/Yosys area-map frontend RTL before technology mapping",
}
(root / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
print("PREPARED_VERILATOR_REPLAY", root, flush=True)

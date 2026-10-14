"""Link an interactive public-port driver to an already built Verilator model."""

import hashlib
import json
import re
import shutil
import subprocess

from paths import INTEGRATED


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


root = INTEGRATED / "rtl-netlist"
provenance = json.loads((root / "provenance.json").read_text())
inputs = {
    INTEGRATED / "machine.py": provenance["candidate_sha256"],
    INTEGRATED / "coarse.json": provenance["coarse_json_sha256"],
    root / "clean.v": provenance["coarse_verilog_sha256"],
    root / "wrapper.v": provenance["wrapper_sha256"],
}
frontend = json.loads((INTEGRATED / "provenance.json").read_text())
for name in ("c_structs_pkg.pkg.vhd", "top/top.vhd"):
    inputs[INTEGRATED / "hdl" / name] = frontend["hdl_files_sha256"][name]
for path, digest in inputs.items():
    assert sha(path) == digest, path
obj = root / "obj"
for name in ("Vreplay_top__ALL.a", "verilated.o", "Vreplay_top.h", "Vreplay_top.mk"):
    path = obj / name
    inputs[path] = sha(path)
kit = re.search(
    r"^VERILATOR_ROOT\s*=\s*(.+)$", (obj / "Vreplay_top.mk").read_text(), re.M
)[1]
incoming = provenance["input_width"]
outgoing = provenance["output_width"]
input_words = (incoming + 31) // 32
output_words = (outgoing + 31) // 32
destination = root / "interactive-driver"
destination.mkdir(exist_ok=False)
source = destination / "server.cpp"
source.write_text(
    r"""#include "Vreplay_top.h"
#include "verilated.h"
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>
int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  Vreplay_top top;
  top.clk_25p0 = 0;
  for (unsigned i=0; i<INPUT_WORDS; ++i) top.incoming[i] = 0;
  top.eval();
  std::string input;
  while (std::cin >> input) {
    if (input.size() > INPUT_HEX ||
        input.find_first_not_of("0123456789abcdefABCDEF") != std::string::npos)
      return 2;
    for (unsigned i=0; i<INPUT_WORDS; ++i) {
      unsigned end = input.size() > 8*i ? input.size() - 8*i : 0;
      unsigned begin = end > 8 ? end - 8 : 0;
      top.incoming[i] = end ?
        std::strtoul(input.substr(begin, end-begin).c_str(), nullptr, 16) : 0;
    }
    if (top.incoming[INPUT_WORDS-1] & ~INPUT_MASK) return 2;
    top.eval();
    // Same phase as replay.cpp: observe before advancing the rising edge.
    for (int i=OUTPUT_WORDS-1; i>=0; --i)
      std::cout << std::hex << std::setfill('0') << std::setw(8)
        << (top.result[i] & (i==OUTPUT_WORDS-1 ? OUTPUT_MASK : 0xffffffffU));
    std::cout << '\n' << std::flush;
    top.clk_25p0 = 1; top.eval();
    top.clk_25p0 = 0; top.eval();
  }
  if (!std::cin.eof()) return 2;
  top.final();
  return 0;
}
""".replace("INPUT_WORDS", str(input_words))
    .replace("OUTPUT_WORDS", str(output_words))
    .replace("INPUT_HEX", str((incoming + 3) // 4))
    .replace("INPUT_MASK", hex((1 << ((incoming - 1) % 32 + 1)) - 1) + "U")
    .replace("OUTPUT_MASK", hex((1 << ((outgoing - 1) % 32 + 1)) - 1) + "U")
)
compiler = shutil.which("g++")
assert compiler, "the compiler used to build the Verilator model is required"
inputs[source] = sha(source)
binary = destination / "server"
command = [
    compiler,
    "-O2",
    "-I",
    str(kit + "/include"),
    "-I",
    str(obj),
    str(source),
    str(obj / "verilated.o"),
    str(obj / "Vreplay_top__ALL.a"),
    "-o",
    str(binary),
    "-lm",
]
with (destination / "build.log").open("x") as log:
    subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
for path, digest in inputs.items():
    assert sha(path) == digest, path
manifest = {
    "scope": "Interactive testbench linked to the existing Verilator model archive",
    "candidate_source_sha256": provenance["candidate_sha256"],
    "input_width": incoming,
    "output_width": outgoing,
    "binary_sha256": sha(binary),
    "inputs_sha256": {str(path): digest for path, digest in inputs.items()},
    "server_cpp_sha256": sha(source),
    "command": command,
    "compiler_version": subprocess.check_output([compiler, "--version"], text=True),
}
(destination / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("INTERACTIVE_RTL_DRIVER_BUILT", binary, flush=True)

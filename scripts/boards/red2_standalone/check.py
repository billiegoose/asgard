"""Build/run autonomous-controller tests against the qualified engine's frontend RTL."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from scripts.boards.red2_standalone.image import compile_image  # noqa: E402

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
top = ROOT / "build/red2-request-guards/shared-multiply/integrated-stream/rtl-netlist"
command = [
    "perl",
    shutil.which("verilator"),
    "--cc",
    "--exe",
    "-Wno-fatal",
    "--top-module",
    "standalone_sim_top",
    "--Mdir",
    str(out / "obj"),
    "-I" + str(HERE),
    str(HERE / "sim.v"),
    str(HERE / "controller.v"),
    str(HERE.parent / "red2_basys3/uart.v"),
    str(top / "clean.v"),
    str(top / "wrapper.v"),
    str(HERE / "sim.cpp"),
]
(out / "build-command.json").write_text(json.dumps(command, indent=2) + "\n")
with (out / "build.log").open("w") as log:
    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
with (out / "make.log").open("w") as log:
    subprocess.run(
        ["make", "-C", str(out / "obj"), "-f", "Vstandalone_sim_top.mk", "-j", "4"],
        stdout=log,
        stderr=subprocess.STDOUT,
        check=True,
    )
prepared = ROOT / "build/red2-basys3-shared-multiplier"
cases = [
    ("clock-dots", (ROOT / "examples/clock-dots.thor").read_text(), "...", "stream"),
    ("uart-tx", "(UART-TX 65)", "A", "halt"),
    (
        "clock-payload",
        "(IO-BIND (CLOCK) (LAMBDA (t) (UART-TX 65)))",
        "A",
        "halt",
    ),
    ("uart-rx", "(IO-BIND (UART-RX) (LAMBDA (x) (UART-TX x)))", "Z", "rx"),
    ("uart-list", "(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))", "AB", "halt"),
]
results = []
for name, source, expected, mode in cases:
    data, record = compile_image(source, prepared)
    image = out / (name + ".bin")
    image.write_bytes(data)
    with (out / (name + ".log")).open("w") as log:
        result = subprocess.run(
            [str(out / "obj/Vstandalone_sim_top"), str(image), expected, mode],
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    result.stdout = (out / (name + ".log")).read_text()
    result.stderr = ""
    row = {
        "name": name,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "image": record,
    }
    results.append(row)
    (out / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(name, result.returncode, result.stdout, result.stderr, flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
# CRC corruption retains valid ABI commands but changes an unused graph payload byte.
data = bytearray(compile_image("(UART-TX 65)", prepared)[0])
data[64 + 3] ^= 1
bad = out / "corrupt.bin"
bad.write_bytes(data)
subprocess.run(
    [str(out / "obj/Vstandalone_sim_top"), str(bad), "", "corrupt"], check=True
)
print("STANDALONE FRONTEND RTL PASS", flush=True)

"""Build/run autonomous-controller tests against the qualified engine's frontend RTL."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from scripts.boards.red2_standalone.image import compile_simulation_image  # noqa: E402
from scripts.boards.red2_standalone.io_fixture import compile_inline_image  # noqa: E402

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--output", type=Path, required=True)
p.add_argument(
    "--core",
    type=Path,
    default=ROOT / "build/red2-finite-quantum/core-v6/integrated-stream",
)
p.add_argument("--reuse-model", type=Path)
p.add_argument("--case", action="append", help="Run only named cases")
a = p.parse_args()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
top = a.core.resolve() / "rtl-netlist"
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
    str(HERE / "restart.v"),
    str(HERE.parent / "red2_basys3/uart.v"),
    str(top / "clean.v"),
    str(top / "wrapper.v"),
    str(HERE / "sim.cpp"),
]
(out / "build-command.json").write_text(json.dumps(command, indent=2) + "\n")
inputs = {
    str(path): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in [
        HERE / name
        for name in ("sim.v", "controller.v", "restart.v", "layout.vh", "sim.cpp")
    ]
    + [HERE.parent / "red2_basys3/uart.v", top / "clean.v", top / "wrapper.v"]
}
if a.reuse_model:
    model = a.reuse_model.resolve()
    assert json.loads((model / "model-inputs.json").read_text()) == inputs
else:
    model = out
    with (out / "build.log").open("w") as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    with (out / "make.log").open("w") as log:
        subprocess.run(
            [
                "make",
                "-C",
                str(out / "obj"),
                "-f",
                "Vstandalone_sim_top.mk",
                "-j",
                "4",
                "OPT_FAST=-O3",
                "OPT_SLOW=-O3",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
(out / "model-inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
binary = model / "obj/Vstandalone_sim_top"
cases = [
    ("budget20", "(IO-BIND (CLOCK) (LAMBDA (x) (UART-TX 65)))", "A", "halt", 20),
    ("inline-io-then", "IO-THEN", "A", "halt", 3),
    ("inline-io-bind", "IO-BIND", "A", "halt", 3),
    ("uart-tx", "(UART-TX 65)", "A", "halt", 1),
    (
        "clock-payload",
        "(IO-BIND (CLOCK) (LAMBDA (t) (UART-TX 65)))",
        "A",
        "halt",
        5,
    ),
    ("uart-rx", "(IO-BIND (UART-RX) (LAMBDA (x) (UART-TX x)))", "Z", "rx", 5),
    ("uart-list", "(UART-TX-BYTES (CONS 65 (CONS 66 NIL)))", "AB", "halt", 5),
    (
        "if-capture",
        "(IO-BIND (CLOCK) (LAMBDA (x) (if (= x x) (UART-TX 65) (UART-TX 66))))",
        "A",
        "halt",
        2,
    ),
    (
        "if-capture-false",
        "(IO-BIND (CLOCK) (LAMBDA (x) (if (< x x) (UART-TX 65) (UART-TX 66))))",
        "B",
        "halt",
        2,
    ),
    (
        "clock-dots",
        (ROOT / "examples/clock-dots.thor").read_text(),
        "..",
        "stream",
        5,
    ),
]
results = []
for name, source, expected, mode, quantum in cases:
    if a.case and name not in a.case:
        continue
    if name.startswith("inline-io-"):
        data, record = compile_inline_image(a.core.resolve(), source)
    else:
        data, record = compile_simulation_image(
            source, a.core.resolve(), quantum=quantum
        )
    image = out / (name + ".bin")
    image.write_bytes(data)
    with (out / (name + ".log")).open("w") as log:
        result = subprocess.run(
            [str(binary), str(image), expected, mode],
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
data = bytearray(compile_simulation_image("(UART-TX 65)", a.core.resolve())[0])
data[64 + 3] ^= 1
bad = out / "corrupt.bin"
bad.write_bytes(data)
subprocess.run([str(binary), str(bad), "", "corrupt"], check=True)
print("STANDALONE FRONTEND RTL PASS", flush=True)

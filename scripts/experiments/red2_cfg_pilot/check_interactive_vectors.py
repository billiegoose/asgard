"""Check every exposed output bit against a complete same-source native trace."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from paths import INTEGRATED, ROOT
from rtl_interactive import RTLServer

sys.path.insert(0, str(ROOT / "scripts/boards/red2_basys3"))
from host import verify_vectors

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("vectors", type=Path)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
source_hash = hashlib.sha256((INTEGRATED / "machine.py").read_bytes()).hexdigest()
metadata = verify_vectors(args.vectors, source_hash)
server = RTLServer(INTEGRATED)
assert metadata["input_width"] == server.input_width
assert metadata["output_width"] == server.output_width
started = time.monotonic()
count = 0
try:
    with args.vectors.open() as vectors:
        for count, line in enumerate(vectors, start=1):
            incoming, expected = (int(value, 16) for value in line.split())
            actual = server.exchange(incoming)
            assert actual == expected, (
                "interactive RTL output mismatch",
                count - 1,
                "actual",
                hex(actual),
                "expected",
                hex(expected),
            )
    assert count == metadata["cycles"]
finally:
    server.close()
result = {
    "environment": "Interactive Verilator RTL versus native expected-output trace",
    "scope": "Every exposed output bit on every cycle of this complete trace",
    "passed": True,
    "candidate_source_sha256": source_hash,
    "compared_cycles": count,
    "output_bits_compared_each_cycle": server.output_width,
    "vectors_sha256": metadata["vectors_sha256"],
    "interactive_binary_sha256": hashlib.sha256(server.binary.read_bytes()).hexdigest(),
    "seconds": time.monotonic() - started,
}
with args.out.open("x") as output:
    json.dump(result, output, indent=2)
    output.write("\n")
print("INTERACTIVE_RTL_VECTOR_PARITY_PASS", count, server.output_width, flush=True)

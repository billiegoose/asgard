"""Area attribution only: replace one legacy scalar handler with a fault.

This is deliberately not a semantically equivalent candidate or a proposed
feature removal. Its whole-top delta includes scalar control/preflight as well
as computation; it is not an additive standalone arithmetic-unit estimate.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path

from paths import INTEGRATED

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source-top", required=True, type=Path)
args = parser.parse_args()
source = args.source_top.resolve()
assert source != INTEGRATED.resolve(), "diagnostic must use a distinct directory"
text = (source / "machine.py").read_text()
tree = ast.parse(text)
fn = next(
    n
    for n in tree.body
    if isinstance(n, ast.FunctionDef) and n.name == "SynthesizableRED2Machine"
)
handlers = [
    n
    for n in fn.body
    if isinstance(n, ast.If)
    and ast.unparse(n.test)
    == "clock_dispatch_enable and micro_is_join_scalar_left_read"
]
assert len(handlers) == 1
handler = handlers[0]
original = ast.unparse(ast.Module(body=handler.body, type_ignores=[]))
handler.body = ast.parse(
    "clock_dispatch_handled = 1\nhw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED\n"
    "microstate = MICRO_FAULT"
).body
ast.fix_missing_locations(tree)
INTEGRATED.mkdir(exist_ok=True)
(INTEGRATED / "machine.py").write_text(ast.unparse(tree) + "\n")
record = json.loads((source / "integration.json").read_text())
record.update(
    scope="Area attribution only; scalar entry faults; not semantically equivalent",
    diagnostic_excluded_handler="MICRO_JOIN_SCALAR_LEFT_READ",
    diagnostic_source_top=str(source),
    diagnostic_source_sha256=hashlib.sha256(text.encode()).hexdigest(),
    diagnostic_original_handler_sha256=hashlib.sha256(original.encode()).hexdigest(),
)
(INTEGRATED / "integration.json").write_text(json.dumps(record, indent=2) + "\n")
print("SCALAR_AREA_DIAGNOSTIC_GENERATED", INTEGRATED, flush=True)

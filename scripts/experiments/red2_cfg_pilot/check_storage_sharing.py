"""Exercise storage-sharing preconditions against the actual generated tops."""

import ast
import copy
import json
import sys
from pathlib import Path

from compact_pending import compact
from paths import INTEGRATED, OUT
from shared_response import share, validate_bridge


def function(path, name):
    return next(
        n
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )


def rejected(action):
    try:
        action()
    except AssertionError:
        return
    raise AssertionError("unsafe storage-sharing precondition was accepted")


manifest = json.loads((OUT / "control.json").read_text())
engine = function(OUT / "machine.py", "red2_app_lambda_cfg")
record = share(copy.deepcopy(engine), manifest)
top = function(INTEGRATED / "machine.py", "SynthesizableRED2Machine")
validate_bridge(top, manifest)
packet = next(
    n.value
    for n in top.body
    if isinstance(n, ast.AnnAssign)
    and isinstance(n.target, ast.Name)
    and n.target.id == "cfg_i"
)
for field in record["fields"]:
    wire = next(k for k in packet.keywords if k.arg == field)
    previous = wire.value
    wire.value = ast.Constant(value=0)
    rejected(lambda: validate_bridge(top, manifest))
    wire.value = previous
    rogue = ast.parse(f"cfg_read_{field} = 0").body[0]
    top.body.insert(0, rogue)
    rejected(lambda: validate_bridge(top, manifest))
    top.body.pop(0)
bad_engine = copy.deepcopy(engine)
bad_engine.body.insert(0, ast.parse("graph_lo = 0").body[0])
rejected(lambda: share(bad_engine, manifest))
entry = next(iter(manifest["entry_pc"].values()))
previous = manifest["rows"][entry]["op"]
manifest["rows"][entry]["op"] = manifest["ops"]["response"]
rejected(lambda: validate_bridge(top, manifest))
manifest["rows"][entry]["op"] = previous
validate_bridge(top, manifest)

baseline = function(Path(sys.argv[1]), "SynthesizableRED2Machine")
compact(copy.deepcopy(baseline))
bad = copy.deepcopy(baseline)
guard = next(
    n
    for n in bad.body
    if isinstance(n, ast.AnnAssign)
    and isinstance(n.target, ast.Name)
    and n.target.id == "cfg_lifecycle_input"
)
guard.value = ast.parse("incoming_command.op == CMD_LOAD_MEMORY", mode="eval").body
rejected(lambda: compact(bad))
print("STORAGE_SHARING_GUARDS_PASS", 2 * len(record["fields"]) + 3, flush=True)

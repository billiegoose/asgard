# ruff: noqa: E501 -- generated source templates preserve source line boundaries
"""Emit original combinational handlers behind the same addressed family interface."""

import ast
import json

import build as c

m = json.loads((c.OUT / "control.json").read_text())
regs = json.loads((c.OUT / "reference-regs.json").read_text())
header = (c.OUT / "machine.py").read_text().split("CONTROL_INIT =")[0]
header = header.replace(header.splitlines()[1], "from pypeline import *")
header += "\n".join(k + " = " + str(v) for k, v in c.constants.items()) + "\n"
header += (
    "\n".join(
        ast.unparse(x)
        for x in c.tree.body
        if isinstance(x, ast.ClassDef) and x.name in ("red2_word_t", "red2_control_t")
    )
    + "\n"
)
header += """
@struct
class red2_command_t(NamedTuple):
    word:red2_word_t
    control:red2_control_t
@struct
class graph_port_t(NamedTuple):
    addr:uint8_t
    wr_data:red2_word_t
    wr_en:uint1_t
@struct
class control_port_t(NamedTuple):
    addr:uint8_t
    wr_data:red2_control_t
    wr_en:uint1_t
"""

s = header + "\n@MAIN(1.0)\ndef red2_app_lambda_baseline(i:input_t)->output_t:\n"
s += "    phase: Reg[uint1_t]\n    admitted_state: Reg[uint8_t]\n    request: Reg[request_t]\n"
for reg in regs:
    s += "    " + reg + ": Reg[" + c.types[reg] + "]\n"
s += "    incoming_phase: uint1_t = phase\n    done:uint1_t = 0\n    memory_req: graph_ram.p0_in_t\n    control_req: control_ram.p0_in_t\n    command: red2_command_t\n    memory_out: graph_ram.out_t\n    control_out: control_ram.out_t\n    memory_out.p0.rd_data = red2_word_t(lo=i.graph_lo,hi=i.graph_hi)\n    control_out.p0.rd_data = red2_control_t(lo=i.control_lo,hi=i.control_hi,tag_hi=i.control_tag)\n    setup_data:uint64_t = 0\n"
for k, idx in m["slots"].items():
    if k.split(".")[0] not in regs:
        continue
    s += f"    if i.setup_addr == {idx}:\n        setup_data = {k}\n"
    s += f"        if incoming_phase == 0 and i.setup_write and not i.reset:\n            {k} = i.setup_data\n"
s += "    if incoming_phase == 0 and i.start and not i.setup_write and not i.reset:\n        admitted_state = i.state\n        phase = 1\n"
for name, p in c.programs.items():
    s += "        if i.state == " + str(c.constants[name]) + ":\n"
    b = p["defaults"] + p["setup"] + p["request"]
    s += (
        "\n".join(
            "            " + line
            for line in ast.unparse(ast.Module(body=b, type_ignores=[])).splitlines()
        )
        + "\n"
    )
    s += "            request = request_t(graph_addr=memory_req.addr,graph_lo=memory_req.wr_data.lo,graph_hi=memory_req.wr_data.hi,graph_write=memory_req.wr_en,control_addr=control_req.addr,control_lo=control_req.wr_data.lo,control_hi=control_req.wr_data.hi,control_tag=control_req.wr_data.tag_hi,control_write=control_req.wr_en)\n"
s += "    if incoming_phase == 1 and i.response_valid and not i.reset:\n        phase = 0\n        done = 1\n"
for name, p in c.programs.items():
    s += "        if admitted_state == " + str(c.constants[name]) + ":\n"
    b = p["setup"] + p["body"]
    s += (
        "\n".join(
            "            " + line
            for line in ast.unparse(ast.Module(body=b, type_ignores=[])).splitlines()
        )
        + "\n"
    )
s += "    if i.reset:\n        phase = 0\n        done = 0\n    ready:uint1_t = phase == 0 and not i.reset\n    request_valid:uint1_t = incoming_phase == 1 and not i.reset\n    return output_t(ready=ready,done=done,request_valid=request_valid,request=request,setup_data=setup_data)\n"
out = c.OUT / "baseline"
out.mkdir(exist_ok=True)
s = (
    s.replace("graph_ram.p0_in_t", "graph_port_t")
    .replace("control_ram.p0_in_t", "control_port_t")
    .replace("graph_ram.out_t", "red2_word_t")
    .replace("control_ram.out_t", "red2_control_t")
    .replace("memory_out.p0.rd_data", "memory_out")
    .replace("control_out.p0.rd_data", "control_out")
)
(out / "machine.py").write_text(s)
print("ORIGINAL_FAMILY_BASELINE", len(s), "bytes")

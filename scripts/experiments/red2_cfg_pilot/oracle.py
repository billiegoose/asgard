# ruff: noqa: E501 -- generated source templates preserve source line boundaries
"""Build native typed reference directly from original handler ASTs."""

import ast

import build as c

reg_names = sorted({n.split(".")[0] for n in c.slots if n.split(".")[0] in c.regs})
text = "from typing import NamedTuple\nfrom pypeline import *\nfrom synthesizable_red2_machine.machine import *\n\n@struct\nclass state_t(NamedTuple):\n"
for name in reg_names:
    text += "    " + name + ": " + c.types[name] + "\n"
text += "\n@struct\nclass result_t(NamedTuple):\n    state: state_t\n    graph_addr: uint8_t\n    graph_lo: uint64_t\n    graph_hi: uint64_t\n    graph_write: uint1_t\n    control_addr: uint8_t\n    control_lo: uint64_t\n    control_hi: uint64_t\n    control_tag: uint4_t\n    control_write: uint1_t\n"
for name, p in c.programs.items():
    text += (
        "\n@hw_func\ndef reference_"
        + name.lower()
        + "(i:state_t, memory_data:red2_word_t, control_data:red2_control_t)->result_t:\n"
    )
    for reg in reg_names:
        text += "    " + reg + ": " + c.types[reg] + " = i." + reg + "\n"
    text += "    memory_req: graph_ram.p0_in_t\n    control_req: control_ram.p0_in_t\n    command: red2_command_t\n    memory_out: graph_ram.out_t\n    control_out: control_ram.out_t\n    memory_out.p0.rd_data = memory_data\n    control_out.p0.rd_data = control_data\n"
    body = p["defaults"] + p["setup"] + p["request"] + p["body"]
    text += (
        "\n".join(
            "    " + line
            for line in ast.unparse(ast.Module(body=body, type_ignores=[])).splitlines()
        )
        + "\n"
    )
    text += (
        "    return result_t(state=state_t("
        + ",".join(r + "=" + r for r in reg_names)
        + "),graph_addr=memory_req.addr, graph_lo=memory_req.wr_data.lo,graph_hi=memory_req.wr_data.hi,graph_write=memory_req.wr_en,control_addr=control_req.addr,control_lo=control_req.wr_data.lo,control_hi=control_req.wr_data.hi,control_tag=control_req.wr_data.tag_hi,control_write=control_req.wr_en)\n"
    )
if c.publication_reads:
    from publication_reads import extend_oracle

    text = extend_oracle(text, c.publication_reads)
(c.OUT / "reference.py").write_text(text)
(c.OUT / "reference-regs.json").write_text(__import__("json").dumps(reg_names))
print("REFERENCE_FUNCTIONS", len(c.programs), "REG_FIELDS", len(reg_names))

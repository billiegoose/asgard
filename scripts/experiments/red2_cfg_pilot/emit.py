# ruff: noqa: E501 -- generated source templates preserve source line boundaries
"""Emit the fixed control-table experiment through the enhanced PipelineC frontend."""

import json
import os

from paths import OUT as P

m = json.loads((P / "control-unmapped.json").read_text())
rows = m["rows"]
slots = m["slots"]
ops = m["ops"]
scratch_bits = max(1, (len(slots) - 1).bit_length())
control_bits = max(1, (len(rows) - 1).bit_length())
m["scratch_words"] = 1 << scratch_bits
m["control_words"] = 1 << control_bits
# Group immutable constants after writable scratch so the setup port cannot alter them.
order = [k for k in slots if not k.startswith("$constant_")] + [
    k for k in slots if k.startswith("$constant_")
]
remap = {slots[k]: i for i, k in enumerate(order)}
m["slots"] = {k: i for i, k in enumerate(order)}
m["initial"] = {remap[int(k)]: v for k, v in m["initial"].items()}
m["writable_words"] = sum(not k.startswith("$constant_") for k in slots)
for r in rows:
    if r["op"] != ops["response"]:
        r["b"] = remap[r["b"]]
    r["a"] = remap[r["a"]]
    if r["op"] not in [ops[n] for n in ("branch", "jump", "request", "halt")]:
        r["d"] = remap[r["d"]]
compact = os.environ.get("RED2_CFG_PILOT_COMPACT", "0") == "1"
if os.environ.get("RED2_CFG_PILOT_DEAD_TEMPS", "0") == "1":
    assert compact
    from dead_temporaries import eliminate

    eliminate(m)
    control_bits = max(1, (len(rows) - 1).bit_length())
    m["control_words"] = 1 << control_bits
if compact:
    from allocate import allocate

    allocate(m)
    scratch_bits = max(1, max(m["slots"].values()).bit_length())
    m["scratch_words"] = 1 << scratch_bits
(P / "control.json").write_text(json.dumps(m, indent=2) + "\n")
text = """from typing import NamedTuple
from pypeline import MAIN, Reg, struct, make_uint_t, uint1_t, uint3_t, uint4_t, uint5_t, uint7_t, uint8_t, uint64_t
from ram import make_ram
addr_t = make_uint_t(10)
pc_t = make_uint_t(12)
@struct
class control_t(NamedTuple):
    op: uint5_t
    a: addr_t
    b: addr_t
    d: addr_t
    width: uint7_t
    yes: pc_t
    no: pc_t
@struct
class request_t(NamedTuple):
    graph_addr: uint8_t
    graph_lo: uint64_t
    graph_hi: uint64_t
    graph_write: uint1_t
    control_addr: uint8_t
    control_lo: uint64_t
    control_hi: uint64_t
    control_tag: uint4_t
    control_write: uint1_t
@struct
class input_t(NamedTuple):
    reset: uint1_t
    start: uint1_t
    state: uint8_t
    setup_addr: addr_t
    setup_write: uint1_t
    setup_data: uint64_t
    response_valid: uint1_t
    graph_lo: uint64_t
    graph_hi: uint64_t
    control_lo: uint64_t
    control_hi: uint64_t
    control_tag: uint4_t
@struct
class output_t(NamedTuple):
    ready: uint1_t
    done: uint1_t
    request_valid: uint1_t
    request: request_t
    setup_data: uint64_t
"""
text += (
    "CONTROL_INIT = [\n"
    + "".join(
        "    control_t(" + ", ".join(k + "=" + str(v) for k, v in r.items()) + "),\n"
        for r in rows
    )
    + "]\n"
)
text += 'control_rom, _ = make_ram(control_t,4096,ports=("r",),read_latency=1,init=CONTROL_INIT)\n'
text += (
    'dispatch_rom, _ = make_ram(pc_t,256,ports=("r",),read_latency=1,init='
    + repr({int(k): v for k, v in m["entry_pc"].items()})
    + ")\n"
)
text += (
    'scratch_ram, _ = make_ram(uint64_t,1024,ports=("rw",),read_latency=1,init='
    + repr(m["initial"])
    + ")\n"
)
text += """
@MAIN(1.0)
def red2_app_lambda_cfg(i: input_t) -> output_t:
    phase: Reg[uint3_t]
    pc: Reg[pc_t]
    row: Reg[control_t]
    a: Reg[uint64_t]
    b: Reg[uint64_t]
    request: Reg[request_t]
    graph_lo: Reg[uint64_t]
    graph_hi: Reg[uint64_t]
    control_lo: Reg[uint64_t]
    control_hi: Reg[uint64_t]
    control_tag: Reg[uint4_t]
    incoming_phase: uint3_t = phase
    done: uint1_t = 0
    dispatch_req: dispatch_rom.p0_in_t
    dispatch_req.addr = i.state
    dispatch_req.valid = 1
    dispatch_out = dispatch_rom(dispatch_req)
    rom_req: control_rom.p0_in_t
    rom_req.addr = pc
    rom_req.valid = 1
    rom_out = control_rom(rom_req)
    sr: scratch_ram.p0_in_t
    sr.addr = i.setup_addr
    sr.wr_en = 0
    sr.wr_data = i.setup_data
    sr.valid = 1
    if incoming_phase == 0 and i.setup_write:
        sr.wr_en = i.setup_addr < WRITABLE_WORDS
    if incoming_phase == 3:
        sr.addr = rom_out.p0.rd_data.a
    if incoming_phase == 4:
        sr.addr = row.b
    # One physical add/sub lane; every route reads addressed scratch.
    subtract: uint1_t = row.op == OP_sub
    add_b: uint64_t = b
    if subtract:
        add_b = ~b
    add_result: uint64_t = a + add_b + subtract
    result: uint64_t = a
    if row.op == OP_add or row.op == OP_sub:
        result = add_result
    elif row.op == OP_and:
        result = a & b
    elif row.op == OP_or:
        result = a | b
    elif row.op == OP_eq:
        result = a == b
    elif row.op == OP_ne:
        result = a != b
    elif row.op == OP_not:
        result = a == 0
    elif row.op == OP_bool_and:
        result = (a != 0) and (b != 0)
    elif row.op == OP_bool_or:
        result = (a != 0) or (b != 0)
    elif row.op == OP_shr:
        result = 0
        if b[63:6] == 0:
            result = a >> b[5:0]
    elif row.op == OP_shl:
        result = 0
        if b[63:6] == 0:
            result = a << b[5:0]
    elif row.op == OP_response:
        result = graph_lo
        if row.b == 1:
            result = graph_hi
        elif row.b == 2:
            result = control_lo
        elif row.b == 3:
            result = control_hi
        elif row.b == 4:
            result = control_tag
    result_mask: uint64_t = 18446744073709551615
"""
for w in sorted(set(r["width"] for r in rows)):
    if w != 64:
        text += f"    if row.width == {w}:\n        result_mask = {(1 << w) - 1}\n"
text += """    result = result & result_mask
    if incoming_phase == 6:
        sr.addr = row.d
        sr.wr_data = result
        sr.wr_en = row.op < OP_branch or row.op == OP_response
    if i.reset:
        sr.wr_en = 0
    so = scratch_ram(sr)
    if incoming_phase == 0:
        if i.start and not i.setup_write:
            phase = 1
    elif incoming_phase == 1:
        pc = dispatch_out.p0.rd_data
        phase = 2
    elif incoming_phase == 2:
        phase = 3
    elif incoming_phase == 3:
        row = rom_out.p0.rd_data
        phase = 4
    elif incoming_phase == 4:
        a = so.p0.rd_data
        phase = 5
    elif incoming_phase == 5:
        b = so.p0.rd_data
        phase = 6
    elif incoming_phase == 6:
        pc = pc + 1
        phase = 2
        if row.op == OP_branch:
            pc = row.no
            if a != 0:
                pc = row.yes
        elif row.op == OP_jump:
            pc = row.yes
        elif row.op == OP_halt:
            done = 1
            phase = 0
        elif row.op == OP_request:
"""
fields = [
    "graph_addr",
    "graph_lo",
    "graph_hi",
    "graph_write",
    "control_addr",
    "control_lo",
    "control_hi",
    "control_tag",
    "control_write",
]
for j, f in enumerate(fields):
    text += f"            if row.d == {j}:\n                request.{f} = a\n"
text += """            if row.d == 15:
                pc = pc - 1
                phase = 7
    elif incoming_phase == 7:
        if i.response_valid:
            graph_lo = i.graph_lo
            graph_hi = i.graph_hi
            control_lo = i.control_lo
            control_hi = i.control_hi
            control_tag = i.control_tag
            pc = pc + 1
            phase = 2
    if i.reset:
        phase = 0
        done = 0
    request_valid: uint1_t = incoming_phase == 7 and not i.reset
    ready: uint1_t = phase == 0 and not i.reset
    return output_t(ready=ready, done=done, request_valid=request_valid, request=request, setup_data=so.p0.rd_data)
"""
text = text.replace("WRITABLE_WORDS", str(m["writable_words"]))
if "ge" in ops:
    text = text.replace(
        "addr_t = make_uint_t(10)", "wide_t = make_uint_t(65)\naddr_t = make_uint_t(10)"
    )
    text = text.replace(
        "subtract: uint1_t = row.op == OP_sub",
        "subtract: uint1_t = row.op == OP_sub or row.op == OP_ge",
    )
    text = text.replace(
        "add_result: uint64_t = a + add_b + subtract",
        "add_wide: wide_t = a\n    wide_b: wide_t = add_b\n"
        "    add_wide = add_wide + wide_b + subtract\n"
        "    add_result: uint64_t = add_wide",
    )
    text = text.replace(
        "elif row.op == OP_and:",
        "elif row.op == OP_ge:\n        result = add_wide[64]\n"
        "    elif row.op == OP_and:",
    )
if compact:
    # Branch true targets are fall-through; only false targets need storage.
    # Control fields share packed bits because their uses are disjoint by op.
    width_values = sorted({r["width"] for r in rows})
    width_bits = max(1, (len(width_values) - 1).bit_length())
    word_bits = max(5 + 3 * scratch_bits + width_bits, 5 + scratch_bits + control_bits)
    packed = []
    for pc, r in enumerate(rows):
        value = r["op"]
        if r["op"] == ops["branch"]:
            assert r["yes"] == pc + 1
            value |= r["a"] << 5
            value |= r["no"] << (5 + scratch_bits)
        elif r["op"] == ops["jump"]:
            value |= r["yes"] << 5
        else:
            value |= r["a"] << 5
            value |= r["b"] << (5 + scratch_bits)
            value |= r["d"] << (5 + 2 * scratch_bits)
            value |= width_values.index(r["width"]) << (5 + 3 * scratch_bits)
        assert value < 1 << word_bits
        packed.append(value)
    start = text.index("CONTROL_INIT =")
    end = text.index("control_rom, _ =", start)
    text = (
        text[:start]
        + f"control_word_t = make_uint_t({word_bits})\n"
        + "CONTROL_INIT = "
        + repr(packed)
        + "\n"
        + text[end:]
    )
    text = text.replace("make_ram(control_t,", "make_ram(control_word_t,")
    decode = f"""    decoded: control_t
    decoded.op = rom_out.p0.rd_data[4:0]
    decoded.a = rom_out.p0.rd_data[{4 + scratch_bits}:5]
    decoded.b = rom_out.p0.rd_data[{4 + 2 * scratch_bits}:{5 + scratch_bits}]
    decoded.d = rom_out.p0.rd_data[{4 + 3 * scratch_bits}:{5 + 2 * scratch_bits}]
    decoded.width = {width_values[0]}
    decoded.yes = pc + 1
    decoded.no = rom_out.p0.rd_data[{4 + scratch_bits + control_bits}:{5 + scratch_bits}]
    if decoded.op == OP_jump:
        decoded.yes = rom_out.p0.rd_data[{4 + control_bits}:5]
"""
    for i, w in enumerate(width_values[1:], 1):
        decode += f"    if rom_out.p0.rd_data[{word_bits - 1}:{5 + 3 * scratch_bits}] == {i}:\n        decoded.width = {w}\n"
    text = text.replace(
        "    sr: scratch_ram.p0_in_t\n", decode + "    sr: scratch_ram.p0_in_t\n"
    )
    text = text.replace("rom_out.p0.rd_data.a", "decoded.a")
    text = text.replace("row = rom_out.p0.rd_data", "row = decoded")
    m["control_encoding"] = {
        "method": "Fixed packed control fields with opcode-dependent branch targets",
        "word_bits": word_bits,
        "scratch_address_bits": scratch_bits,
        "width_values": width_values,
        "branch_true_target": "fall-through",
    }
    (P / "control.json").write_text(json.dumps(m, indent=2) + "\n")
text = text.replace("make_uint_t(10)", f"make_uint_t({scratch_bits})")
text = text.replace("make_uint_t(12)", f"make_uint_t({control_bits})")
text = text.replace(
    "make_ram(control_t,4096,", f"make_ram(control_t,{m['control_words']},"
)
text = text.replace(
    "make_ram(control_word_t,4096,",
    f"make_ram(control_word_t,{m['control_words']},",
)
text = text.replace(
    "make_ram(uint64_t,1024,", f"make_ram(uint64_t,{m['scratch_words']},"
)
for name, value in ops.items():
    text = (
        text.replace("OP_" + name + "\n", str(value) + "\n")
        .replace("OP_" + name + ":", str(value) + ":")
        .replace("OP_" + name + " ", str(value) + " ")
    )
assert "OP_" not in text
if "publication_reads" in m:
    from publication_reads import extend_emitter

    text = extend_emitter(text, m)
if os.environ.get("RED2_CFG_PILOT_DICTIONARY", "0") == "1":
    assert compact, "dictionary encoding requires packed control words"
    from dictionary import encode

    text = encode(text, m)
    (P / "control.json").write_text(json.dumps(m, indent=2) + "\n")
(P / "machine.py").write_text(text)
print("GENERATED_HARDWARE", len(text), "bytes", m["writable_words"], "writable words")

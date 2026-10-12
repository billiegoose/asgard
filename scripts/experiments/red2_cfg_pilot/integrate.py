# ruff: noqa: E501 -- generated source templates preserve source line boundaries
"""Integrate the measured family controller with the original full RED2 top.

This emits an experimental top with explicit busy feedback. It keeps named
architectural registers and bridges them serially; production stays untouched.
"""

import ast
import copy
import json
import os

import build as c
from paths import INTEGRATED

m = json.loads((c.OUT / "control.json").read_text())
assert int(os.environ.get("RED2_SYN_GRAPH_WORDS", "256")) == 256, (
    "integration requires a 256-word graph"
)
assert m["include_lookup"], "the first integration includes lookup"
assert m["source_sha256"] == c.manifest["source_sha256"]
root = INTEGRATED
root.mkdir(exist_ok=True)

# Namespace the measured controller and turn it into a nested hardware module.
controller = ast.parse((c.OUT / "machine.py").read_text())
rename = {
    name: "cfg_" + name
    for name in (
        "addr_t",
        "pc_t",
        "control_t",
        "request_t",
        "input_t",
        "output_t",
        "CONTROL_INIT",
        "control_rom",
        "dispatch_rom",
        "scratch_ram",
        "control_word_t",
        "wide_t",
        "red2_app_lambda_cfg",
    )
}


class Namespace(ast.NodeTransformer):
    def visit_Name(self, node):
        if node.id in rename:
            node.id = rename[node.id]
        return node

    def visit_ClassDef(self, node):
        node.name = rename.get(node.name, node.name)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.name = rename.get(node.name, node.name)
        return self.generic_visit(node)


controller = Namespace().visit(controller)
controller.body = [
    n for n in controller.body if not isinstance(n, (ast.Import, ast.ImportFrom))
]
input_type = next(
    n
    for n in controller.body
    if isinstance(n, ast.ClassDef) and n.name == "cfg_input_t"
)
input_type.body += ast.parse("enable: uint1_t").body
engine = next(n for n in controller.body if isinstance(n, ast.FunctionDef))
engine.decorator_list = [ast.Name(id="hw_func", ctx=ast.Load())]
# Pause control/state writes on observational NOP cycles. RAM addresses may
# continue to settle, but a request is accepted only on an enabled clock.
for n in ast.walk(engine):
    if isinstance(n, ast.If) and ast.unparse(n.test).startswith("incoming_phase =="):
        n.test = ast.BoolOp(
            op=ast.And(), values=[ast.parse("i.enable", mode="eval").body, n.test]
        )
    if (
        isinstance(n, ast.AnnAssign)
        and isinstance(n.target, ast.Name)
        and n.target.id == "request_valid"
    ):
        n.value = ast.BoolOp(
            op=ast.And(), values=[ast.parse("i.enable", mode="eval").body, n.value]
        )
ram_call = next(
    i
    for i, n in enumerate(engine.body)
    if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "so"
)
engine.body[ram_call:ram_call] = ast.parse("""if not i.enable:
    sr.wr_en = 0
    # A paused consume phase must keep its previously issued read address.
    if incoming_phase == 4:
        sr.addr = row.a
    elif incoming_phase == 5:
        sr.addr = row.b
""").body

# The wrapper mirrors every typed family field. Fields that signal faults or
# dispatch are transferred last so no observer sees a fault before its state.
reg_leaves = [k for k in m["slots"] if k.split(".")[0] in c.regs]
last = [k for k in ("hw_fault", "red2_fault", "microstate") if k in reg_leaves]
reg_leaves = [k for k in reg_leaves if k not in last] + last
assert reg_leaves[-1] == "microstate"
count = len(reg_leaves)
index_bits = max(1, (count - 1).bit_length())
selected_names = set(c.selected)
selected_values = [c.constants[n] for n in sorted(selected_names)]
sync_names = set()
for node in ast.walk(c.fn):
    if isinstance(node, (ast.AnnAssign, ast.Assign)):
        targets = [node.target] if isinstance(node, ast.AnnAssign) else node.targets
        if any(isinstance(t, ast.Name) and t.id == "sync_read_state" for t in targets):
            sync_names.update(
                "MICRO_" + n.id.removeprefix("micro_is_").upper()
                for n in ast.walk(node.value)
                if isinstance(n, ast.Name) and n.id.startswith("micro_is_")
            )
selected_sync = selected_names & sync_names
# Independently pin the original family's admission states as a regression check.
assert selected_sync >= {
    "MICRO_LAMBDA_READ",
    "MICRO_LAMBDA_EP_CONTROL_READ",
    "MICRO_LAMBDA_APP_CONTROL_READ",
    "MICRO_APP_CONTROL_READ",
    "MICRO_LOOKUP_READ",
    "MICRO_LOOKUP_CLOSURE_CODE_READ",
    "MICRO_LOOKUP_VAR_EP_CHASE",
}
selected_expr = " or ".join(f"microstate == {v}" for v in selected_values)
sync_expr = " or ".join(f"microstate == {n}" for n in sorted(selected_sync))
entry_opcodes = m.get(
    "entry_opcodes", ["MOP_APP", "MOP_LAMBDA", "MOP_VAR", "MOP_APP_VAR"]
)
execute_expr = " or ".join("fetched_word.hi[25:21] == " + op for op in entry_opcodes)

source = copy.deepcopy(c.tree)
fn = next(
    n
    for n in source.body
    if isinstance(n, ast.FunctionDef) and n.name == "SynthesizableRED2Machine"
)
fn.args.args[0].arg = "incoming_command"
# Retain original source for every other family and all shared reset banks.
new_body = []
removed_handlers = []
for n in fn.body:
    if isinstance(n, ast.If):
        test = ast.unparse(n.test)
        if test.startswith("clock_dispatch_enable and micro_is_"):
            name = "MICRO_" + test.split("micro_is_", 1)[1].upper()
            if name in selected_names:
                removed_handlers.append(name)
                continue
        if test == "command_is_clock" and any(
            isinstance(x, ast.If) and ast.unparse(x.test) == "micro_is_lambda_read"
            for x in n.body
        ):
            n.body = [
                x
                for x in n.body
                if not (
                    isinstance(x, ast.If)
                    and "MICRO_" + ast.unparse(x.test).removeprefix("micro_is_").upper()
                    in selected_names
                )
            ]
            req_execute = next(
                x
                for x in n.body
                if isinstance(x, ast.If) and ast.unparse(x.test) == "micro_is_execute"
            )

            class OtherExecuteRequests(ast.NodeTransformer):
                def visit_Name(self, node):
                    if node.id in {
                        "opcode_is_" + op.removeprefix("MOP_").lower()
                        for op in entry_opcodes
                    }:
                        return ast.copy_location(ast.Constant(value=0), node)
                    return node

            OtherExecuteRequests().visit(req_execute)
        if test == "clock_dispatch_enable and micro_is_execute":
            kept = []
            for x in n.body:
                if isinstance(x, ast.If):
                    t = ast.unparse(x.test)
                    if t in {
                        "not fetched_invalid and opcode_is_" + op for op in c.entry_ops
                    }:
                        continue
                    if t.startswith("not fetched_invalid and (not ("):
                        # VAR and APP_VAR now use the controller; the remaining
                        # unsupported opcode branch retains its original fault.
                        x.body = ast.parse(
                            "hw_fault = HW_FAULT_EXECUTION_NOT_IMPLEMENTED\nmicrostate = MICRO_FAULT"
                        ).body
                kept.append(x)
            n.body = kept
    new_body.append(n)
fn.body = new_body
assert set(removed_handlers) == selected_names

if os.environ.get("RED2_CFG_PILOT_OWNED", "0") == "1":
    from owned import emit_owned

    emit_owned(
        source,
        fn,
        controller,
        m,
        root,
        c,
        removed_handlers,
        selected_sync,
        selected_expr,
        sync_expr,
        execute_expr,
    )
    raise SystemExit(0)

# Insert wrapper state/command admission before any original combinational work.
position = next(
    i
    for i, n in enumerate(fn.body)
    if isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == "committed"
)
admit = f"""
cfg_stage: Reg[uint3_t]
cfg_index: Reg[cfg_bridge_index_t]
cfg_mem_phase: Reg[uint2_t]
cfg_read_graph_lo: Reg[uint64_t]
cfg_read_graph_hi: Reg[uint64_t]
cfg_read_control_lo: Reg[uint64_t]
cfg_read_control_hi: Reg[uint64_t]
cfg_read_control_tag: Reg[uint4_t]
cfg_incoming_stage: uint3_t = cfg_stage
cfg_incoming_mem_phase: uint2_t = cfg_mem_phase
cfg_clock: uint1_t = incoming_command.op == CMD_CLOCK
cfg_cancel: uint1_t = incoming_command.op == CMD_RESET or incoming_command.op == CMD_LOAD_STATE or incoming_command.op == CMD_START
cfg_family: uint1_t = {selected_expr}
cfg_execute: uint1_t = microstate == MICRO_EXECUTE and ({execute_expr})
cfg_sync: uint1_t = {sync_expr}
cfg_admit: uint1_t = cfg_clock and cfg_incoming_stage == 0 and (cfg_family or cfg_execute)
cfg_admit = cfg_admit and red2_fault == FAULT_NONE and microstate != MICRO_FAULT
cfg_admit = cfg_admit and (not cfg_sync or sync_read_pending)
cfg_owns: uint1_t = (cfg_incoming_stage != 0 or cfg_admit) and not cfg_cancel
command: red2_command_t = incoming_command
if cfg_owns:
    command.op = CMD_NOP
"""
fn.body[position:position] = ast.parse(admit).body
# Address/read mux and controller invocation before the actual graph RAM call.
position = next(
    i
    for i, n in enumerate(fn.body)
    if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "memory_out"
)
bridge = "cfg_setup_addr: cfg_addr_t = 0\ncfg_setup_data: uint64_t = 0\n"
for idx, k in enumerate(reg_leaves):
    bridge += f"if cfg_index == {idx}:\n    cfg_setup_addr = {m['slots'][k]}\n    cfg_setup_data = {k}\n"
bridge += """
cfg_i: cfg_input_t = cfg_input_t(reset=cfg_cancel, start=cfg_incoming_stage == 2, state=microstate, setup_addr=cfg_setup_addr, setup_write=cfg_incoming_stage == 1, setup_data=cfg_setup_data, response_valid=cfg_incoming_mem_phase == 2, graph_lo=cfg_read_graph_lo, graph_hi=cfg_read_graph_hi, control_lo=cfg_read_control_lo, control_hi=cfg_read_control_hi, control_tag=cfg_read_control_tag, enable=cfg_clock)
cfg_o = cfg_red2_app_lambda_cfg(cfg_i)
cfg_issue: uint1_t = cfg_clock and cfg_incoming_stage == 3 and cfg_incoming_mem_phase == 0 and cfg_o.request_valid and not cfg_cancel
if cfg_issue:
    memory_req.addr = cfg_o.request.graph_addr
    memory_req.wr_data = red2_word_t(lo=cfg_o.request.graph_lo, hi=cfg_o.request.graph_hi)
    memory_req.wr_en = cfg_o.request.graph_write
    control_req.addr = cfg_o.request.control_addr
    control_req.wr_data = red2_control_t(lo=cfg_o.request.control_lo, hi=cfg_o.request.control_hi, tag_hi=cfg_o.request.control_tag)
    control_req.wr_en = cfg_o.request.control_write
"""
fn.body[position:position] = ast.parse(bridge).body
# Transfer outputs after all original scalar/reset banks, before status logic.
position = next(
    i
    for i, n in enumerate(fn.body)
    if isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == "status"
)
finish = f"""
if cfg_admit:
    cfg_stage = 1
    cfg_index = 0
    cfg_mem_phase = 0
    sync_read_pending = 0
    hw_fault = HW_FAULT_NONE
if cfg_incoming_stage != 0 and not cfg_cancel:
    if cfg_incoming_mem_phase == 1:
        cfg_read_graph_lo = memory_out.p0.rd_data.lo
        cfg_read_graph_hi = memory_out.p0.rd_data.hi
        cfg_read_control_lo = control_out.p0.rd_data.lo
        cfg_read_control_hi = control_out.p0.rd_data.hi
        cfg_read_control_tag = control_out.p0.rd_data.tag_hi
        cfg_mem_phase = 2
    if cfg_clock:
        if cfg_incoming_stage == 1:
            cfg_index = cfg_index + 1
            if cfg_index == {count}:
                cfg_index = 0
                cfg_stage = 2
        elif cfg_incoming_stage == 2:
            cfg_stage = 3
        elif cfg_incoming_stage == 3:
            if cfg_issue:
                cfg_mem_phase = 1
            elif cfg_incoming_mem_phase == 2:
                cfg_mem_phase = 3
            elif cfg_incoming_mem_phase == 3 and not cfg_o.request_valid:
                cfg_mem_phase = 0
            if cfg_o.done:
                cfg_stage = 4
                cfg_index = 0
        elif cfg_incoming_stage == 4:
            cfg_stage = 5
        elif cfg_incoming_stage == 5:
"""
for idx, k in enumerate(reg_leaves):
    finish += (
        f"            if cfg_index == {idx}:\n                {k} = cfg_o.setup_data\n"
    )
finish += f"""            cfg_index = cfg_index + 1
            cfg_stage = 4
            if cfg_index == {count}:
                cfg_index = 0
                cfg_stage = 0
if cfg_cancel:
    cfg_stage = 0
    cfg_index = 0
    cfg_mem_phase = 0
cfg_busy: uint1_t = cfg_stage != 0
"""
fn.body[position:position] = ast.parse(finish).body
ret = fn.body[-1]
assert isinstance(ret, ast.Return)
ret.value.keywords += [
    ast.keyword(arg="busy", value=ast.Name(id="cfg_busy", ctx=ast.Load()))
]
fn.body[-1:-1] = ast.parse(
    "if cfg_busy:\n    status = STATUS_RUNNING\n    committed = 0"
).body
status_type = next(
    n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "red2_status_t"
)
status_type.body += ast.parse("busy: uint1_t").body
idx = source.body.index(fn)
source.body[idx:idx] = (
    ast.parse(f"cfg_bridge_index_t = make_uint_t({index_bits})").body + controller.body
)
ast.fix_missing_locations(source)
(root / "machine.py").write_text(ast.unparse(source) + "\n")
(root / "integration.json").write_text(
    json.dumps(
        {
            "source_sha256": m["source_sha256"],
            "removed_handlers": sorted(removed_handlers),
            "synchronous_states": sorted(selected_sync),
            "bridge_fields": reg_leaves,
            "bridge_words": count,
            "protocol": "busy feedback; CMD_CLOCK advances, CMD_NOP observes/pauses; RESET/LOAD_STATE/START cancel; other commands admitted only when not busy",
            "scope": "Experimental complete top, named architectural state retained; selected families and opcodes follow control.json",
            "entry_opcodes": entry_opcodes,
            "include_graph": m.get("include_graph", False),
        },
        indent=2,
    )
    + "\n"
)
print(
    "INTEGRATED_TOP",
    root,
    count,
    "bridge words",
    len(removed_handlers),
    "removed handlers",
)

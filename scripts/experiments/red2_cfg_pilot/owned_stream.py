# ruff: noqa: E501 -- generated hardware templates
"""Short immutable transfer streams instead of full shared-state mask scans."""

import ast
import os

from owned import publish_owned
from publication_reads import bridge as publication_bridge


def emit_stream(
    source,
    fn,
    controller,
    m,
    root,
    c,
    removed,
    sync_states,
    selected,
    sync,
    execute,
    proof,
    shared,
    plans,
    visible,
    snapshot,
    capture,
):
    private = proof["private_fields"]
    slot_bits = max(1, max(m["slots"][k] for k in shared).bit_length())
    end = 1 << slot_bits
    words, starts = [], {}
    for state, plan in plans.items():
        import_pc = len(words)
        words += [m["slots"][k] for k in shared if k in plan["import"]] + [end]
        export_pc = len(words)
        words += [m["slots"][k] for k in shared if k in plan["export"]] + [end]
        starts[int(state)] = (import_pc, export_pc)
    pc_bits = max(1, (len(words) - 1).bit_length())
    depth = 1 << pc_bits
    dispatch = {state: a | (b << pc_bits) for state, (a, b) in starts.items()}
    index_bits = max(2, len(private).bit_length())
    admit = f"""
{snapshot}
cfg_stage: Reg[uint4_t]
cfg_index: Reg[cfg_bridge_index_t]
cfg_entry: Reg[uint8_t]
cfg_bridge_pc: Reg[cfg_bridge_pc_t]
cfg_export_pc: Reg[cfg_bridge_pc_t]
cfg_transfer_slot: Reg[cfg_transfer_addr_t]
cfg_transfer_mode: Reg[uint1_t]
cfg_init_start: Reg[uint1_t]
cfg_pending: Reg[uint1_t]
cfg_pending_command: Reg[red2_command_t]
cfg_mem_phase: Reg[uint2_t]
cfg_read_graph_lo: Reg[uint64_t]
cfg_read_graph_hi: Reg[uint64_t]
cfg_read_control_lo: Reg[uint64_t]
cfg_read_control_hi: Reg[uint64_t]
cfg_read_control_tag: Reg[uint4_t]
cfg_incoming_stage: uint4_t = cfg_stage
cfg_incoming_mem_phase: uint2_t = cfg_mem_phase
cfg_clock: uint1_t = incoming_command.op == CMD_CLOCK
cfg_lifecycle_input: uint1_t = incoming_command.op == CMD_RESET or incoming_command.op == CMD_LOAD_STATE or incoming_command.op == CMD_START
cfg_apply_pending: uint1_t = cfg_pending and cfg_incoming_stage == 0 and cfg_clock
command: red2_command_t = incoming_command
if cfg_incoming_stage != 0 or cfg_pending:
    command.op = CMD_NOP
if cfg_apply_pending:
    command = cfg_pending_command
cfg_family: uint1_t = {selected}
cfg_execute: uint1_t = microstate == MICRO_EXECUTE and ({execute})
cfg_sync: uint1_t = {sync}
cfg_admit: uint1_t = cfg_clock and cfg_incoming_stage == 0 and not cfg_pending and (cfg_family or cfg_execute)
cfg_admit = cfg_admit and red2_fault == FAULT_NONE and microstate != MICRO_FAULT
cfg_admit = cfg_admit and (not cfg_sync or sync_read_pending)
if cfg_admit:
    command.op = CMD_NOP
cfg_cancel: uint1_t = command.op == CMD_RESET or command.op == CMD_LOAD_STATE or command.op == CMD_START
cfg_initialize: uint1_t = command.op == CMD_RESET or command.op == CMD_LOAD_STATE or (command.op == CMD_START and command.address[15:8] == 0)
if cfg_admit or cfg_initialize:
{capture}
"""
    position = next(
        i
        for i, n in enumerate(fn.body)
        if isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == "committed"
    )
    fn.body[position:position] = ast.parse(publication_bridge(admit, m, "admit")).body
    bridge = "cfg_setup_addr: cfg_addr_t = cfg_transfer_slot\ncfg_setup_data: uint64_t = 0\ncfg_setup_write: uint1_t = cfg_incoming_stage == 3 and not cfg_transfer_mode\n"
    from import_mux import emit as emit_import_mux

    onehot_import = os.environ.get("RED2_CFG_PILOT_ONEHOT_IMPORT", "0") == "1"
    bridge += emit_import_mux([(m["slots"][k], k) for k in shared], onehot_import)
    bridge += (
        "if cfg_incoming_stage == 8:\n    cfg_setup_data = 0\n    cfg_setup_write = 0\n"
    )
    for i, k in enumerate(private):
        enabled = "1" if k in proof["initialize_on_start"] else "not cfg_init_start"
        bridge += f"    if cfg_index == {i}:\n        cfg_setup_addr = {m['slots'][k]}\n        cfg_setup_write = {enabled}\n"
    bridge += """
cfg_bridge_dispatch_req: cfg_bridge_dispatch_rom.p0_in_t
cfg_bridge_dispatch_req.addr = cfg_entry
cfg_bridge_dispatch_out = cfg_bridge_dispatch_rom(cfg_bridge_dispatch_req)
cfg_plan_req: cfg_plan_rom.p0_in_t
cfg_plan_req.addr = cfg_bridge_pc
cfg_plan_out = cfg_plan_rom(cfg_plan_req)
cfg_i: cfg_input_t = cfg_input_t(reset=cfg_cancel, start=cfg_incoming_stage == 5, state=cfg_entry, setup_addr=cfg_setup_addr, setup_write=cfg_setup_write, setup_data=cfg_setup_data, response_valid=cfg_incoming_mem_phase == 2, graph_lo=cfg_read_graph_lo, graph_hi=cfg_read_graph_hi, control_lo=cfg_read_control_lo, control_hi=cfg_read_control_hi, control_tag=cfg_read_control_tag, enable=cfg_clock)
cfg_o = cfg_red2_app_lambda_cfg(cfg_i)
cfg_issue: uint1_t = cfg_clock and cfg_incoming_stage == 6 and cfg_incoming_mem_phase == 0 and cfg_o.request_valid
if cfg_issue:
    memory_req.addr = cfg_o.request.graph_addr
    memory_req.wr_data = red2_word_t(lo=cfg_o.request.graph_lo, hi=cfg_o.request.graph_hi)
    memory_req.wr_en = cfg_o.request.graph_write
    control_req.addr = cfg_o.request.control_addr
    control_req.wr_data = red2_control_t(lo=cfg_o.request.control_lo, hi=cfg_o.request.control_hi, tag_hi=cfg_o.request.control_tag)
    control_req.wr_en = cfg_o.request.control_write
"""
    position = next(
        i
        for i, n in enumerate(fn.body)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "memory_out"
    )
    fn.body[position:position] = ast.parse(
        publication_bridge(bridge, m, "request")
    ).body
    finish = f"""
if cfg_admit:
    cfg_stage = 7
    cfg_entry = microstate
    cfg_index = 0
    cfg_mem_phase = 0
    cfg_transfer_mode = 0
    sync_read_pending = 0
    hw_fault = HW_FAULT_NONE
if cfg_incoming_stage != 0:
    if cfg_incoming_mem_phase == 1:
        cfg_read_graph_lo = memory_out.p0.rd_data.lo
        cfg_read_graph_hi = memory_out.p0.rd_data.hi
        cfg_read_control_lo = control_out.p0.rd_data.lo
        cfg_read_control_hi = control_out.p0.rd_data.hi
        cfg_read_control_tag = control_out.p0.rd_data.tag_hi
        cfg_mem_phase = 2
    if cfg_clock:
        if cfg_incoming_stage == 7:
            cfg_index = cfg_index + 1
            if cfg_index == 2:
                cfg_index = 0
                cfg_bridge_pc = cfg_bridge_dispatch_out.p0.rd_data[{pc_bits - 1}:0]
                cfg_export_pc = cfg_bridge_dispatch_out.p0.rd_data[{pc_bits * 2 - 1}:{pc_bits}]
                cfg_stage = 1
        elif cfg_incoming_stage == 1:
            cfg_stage = 2
        elif cfg_incoming_stage == 2:
            if cfg_plan_out.p0.rd_data[{slot_bits}]:
                if cfg_transfer_mode:
                    cfg_stage = 0
                else:
                    cfg_stage = 5
            else:
                cfg_transfer_slot = cfg_plan_out.p0.rd_data[{slot_bits - 1}:0]
                cfg_bridge_pc = cfg_bridge_pc + 1
                cfg_stage = 3
        elif cfg_incoming_stage == 3:
            if cfg_transfer_mode:
                cfg_stage = 4
            else:
                cfg_stage = 1
        elif cfg_incoming_stage == 4:
"""
    for k in shared:
        if any(k in plan["export"] for plan in plans.values()):
            finish += f"            if cfg_transfer_slot == {m['slots'][k]}:\n                {k} = cfg_o.setup_data\n"
    finish += f"""            cfg_stage = 1
        elif cfg_incoming_stage == 5:
            cfg_stage = 6
        elif cfg_incoming_stage == 6:
            if cfg_issue:
                cfg_mem_phase = 1
            elif cfg_incoming_mem_phase == 2:
                cfg_mem_phase = 3
            elif cfg_incoming_mem_phase == 3 and not cfg_o.request_valid:
                cfg_mem_phase = 0
            if cfg_o.done:
                cfg_transfer_mode = 1
                cfg_bridge_pc = cfg_export_pc
                cfg_stage = 1
        elif cfg_incoming_stage == 8:
            cfg_index = cfg_index + 1
            if cfg_index == {len(private)}:
                cfg_index = 0
                cfg_stage = 0
if cfg_lifecycle_input and cfg_incoming_stage != 0 and not cfg_pending:
    cfg_pending_command = incoming_command
    cfg_pending = 1
if cfg_apply_pending:
    cfg_pending = 0
if cfg_initialize:
    cfg_stage = 8
    cfg_index = 0
    cfg_mem_phase = 0
    cfg_init_start = command.op == CMD_START
cfg_busy: uint1_t = cfg_stage != 0 or cfg_pending
"""
    position = next(
        i
        for i, n in enumerate(fn.body)
        if isinstance(n, ast.AnnAssign) and ast.unparse(n.target) == "status"
    )
    fn.body[position:position] = ast.parse(publication_bridge(finish, m, "finish")).body
    definitions = f"""
cfg_bridge_index_t = make_uint_t({index_bits})
cfg_bridge_pc_t = make_uint_t({pc_bits})
cfg_transfer_addr_t = make_uint_t({slot_bits})
cfg_plan_word_t = make_uint_t({slot_bits + 1})
cfg_bridge_dispatch_t = make_uint_t({pc_bits * 2})
cfg_plan_rom, _ = make_ram(cfg_plan_word_t, {depth}, ports=('r',), read_latency=1, init={words!r})
cfg_bridge_dispatch_rom, _ = make_ram(cfg_bridge_dispatch_t, 256, ports=('r',), read_latency=1, init={dispatch!r})
"""
    extra = {
        "bridge_kind": "stream",
        "bridge_stream_words": len(words),
        "bridge_stream_depth": depth,
        "bridge_stream_word_bits": slot_bits + 1,
        "bridge_dispatch_word_bits": pc_bits * 2,
        "pause_registers": ["cfg_bridge_pc", "cfg_transfer_slot", "cfg_transfer_mode"],
        "export_capture_stage": 4,
        "scope": "Experimental persistent private BRAM ownership; short per-entry transfer streams; coherent scalar observation; graph256 only",
    }
    if onehot_import:
        extra["import_mux"] = "One-hot gated typed fields, balanced bitwise OR"
    publish_owned(
        source,
        fn,
        controller,
        m,
        root,
        c,
        removed,
        sync_states,
        proof,
        shared,
        plans,
        visible,
        definitions,
        extra,
    )

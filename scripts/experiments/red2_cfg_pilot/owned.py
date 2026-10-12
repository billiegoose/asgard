# ruff: noqa: E501 -- generated hardware templates
"""Experimental persistent BRAM ownership with safe lifecycle/publication boundaries."""

import ast
import json
import os

from ownership import prove_private, schedules


def emit_owned(
    source, fn, controller, m, root, c, removed, sync_states, selected, sync, execute
):
    original_fn = fn
    fn, proof = prove_private(fn, m)
    source.body[source.body.index(original_fn)] = fn
    private = proof["private_fields"]
    plans = schedules(m, private)
    shared = [k for k in m["slots"] if k.split(".")[0] in c.regs and k not in private]
    last = [k for k in ("hw_fault", "red2_fault", "microstate") if k in shared]
    shared = [k for k in shared if k not in last] + last
    count = len(shared)
    bits = max(1, (max(count, len(private)) - 1).bit_length())
    masks = {}
    for state, plan in plans.items():
        masks[int(state)] = sum(
            1 << i for i, k in enumerate(shared) if k in plan["import"]
        ) | sum(1 << (count + i) for i, k in enumerate(shared) if k in plan["export"])
    ret = fn.body[-1]
    assert isinstance(ret, ast.Return)
    # Preserve coherent scalar observations while transfers/initialization run.
    visible = [
        k.arg
        for k in ret.value.keywords
        if isinstance(k.value, ast.Name) and k.value.id in c.regs
    ]
    snapshot = "".join(f"cfg_visible_{k}: Reg[{c.typ(k)}]\n" for k in visible)
    capture = "".join(f"    cfg_visible_{k} = {k}\n" for k in visible)
    if os.environ.get("RED2_CFG_PILOT_STREAM_BRIDGE", "0") == "1":
        from owned_stream import emit_stream

        return emit_stream(
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
        )
    admit = f"""
{snapshot}
cfg_stage: Reg[uint3_t]
cfg_index: Reg[cfg_bridge_index_t]
cfg_entry: Reg[uint8_t]
cfg_mask: Reg[cfg_mask_t]
cfg_init_start: Reg[uint1_t]
cfg_pending: Reg[uint1_t]
cfg_pending_command: Reg[red2_command_t]
cfg_mem_phase: Reg[uint2_t]
cfg_read_graph_lo: Reg[uint64_t]
cfg_read_graph_hi: Reg[uint64_t]
cfg_read_control_lo: Reg[uint64_t]
cfg_read_control_hi: Reg[uint64_t]
cfg_read_control_tag: Reg[uint4_t]
cfg_incoming_stage: uint3_t = cfg_stage
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
    fn.body[position:position] = ast.parse(admit).body
    bridge = "cfg_setup_addr: cfg_addr_t = 0\ncfg_setup_data: uint64_t = 0\ncfg_setup_write: uint1_t = 0\n"
    for i, k in enumerate(shared):
        bridge += f"if cfg_index == {i}:\n    cfg_setup_addr = {m['slots'][k]}\n    cfg_setup_data = {k}\n    cfg_setup_write = cfg_incoming_stage == 1 and cfg_mask[{i}]\n"
    bridge += "if cfg_incoming_stage == 6:\n    cfg_setup_data = 0\n"
    for i, k in enumerate(private):
        enabled = "1" if k in proof["initialize_on_start"] else "not cfg_init_start"
        bridge += f"    if cfg_index == {i}:\n        cfg_setup_addr = {m['slots'][k]}\n        cfg_setup_write = {enabled}\n"
    bridge += """
cfg_plan_req: cfg_plan_rom.p0_in_t
cfg_plan_req.addr = cfg_entry
cfg_plan_out = cfg_plan_rom(cfg_plan_req)
cfg_i: cfg_input_t = cfg_input_t(reset=cfg_cancel, start=cfg_incoming_stage == 2, state=cfg_entry, setup_addr=cfg_setup_addr, setup_write=cfg_setup_write, setup_data=cfg_setup_data, response_valid=cfg_incoming_mem_phase == 2, graph_lo=cfg_read_graph_lo, graph_hi=cfg_read_graph_hi, control_lo=cfg_read_control_lo, control_hi=cfg_read_control_hi, control_tag=cfg_read_control_tag, enable=cfg_clock)
cfg_o = cfg_red2_app_lambda_cfg(cfg_i)
cfg_issue: uint1_t = cfg_clock and cfg_incoming_stage == 3 and cfg_incoming_mem_phase == 0 and cfg_o.request_valid
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
    fn.body[position:position] = ast.parse(bridge).body
    finish = f"""
if cfg_admit:
    cfg_stage = 7
    cfg_entry = microstate
    cfg_index = 0
    cfg_mem_phase = 0
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
                cfg_mask = cfg_plan_out.p0.rd_data
                cfg_stage = 1
        elif cfg_incoming_stage == 1:
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
    for i, k in enumerate(shared):
        if any(k in p["export"] for p in plans.values()):
            finish += f"            if cfg_index == {i} and cfg_mask[{count + i}]:\n                {k} = cfg_o.setup_data\n"
    finish += f"""            cfg_index = cfg_index + 1
            cfg_stage = 4
            if cfg_index == {count}:
                cfg_index = 0
                cfg_stage = 0
        elif cfg_incoming_stage == 6:
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
    cfg_stage = 6
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
    fn.body[position:position] = ast.parse(finish).body
    global_definitions = f"cfg_bridge_index_t = make_uint_t({bits})\ncfg_mask_t = make_uint_t({count * 2})\ncfg_plan_rom, _ = make_ram(cfg_mask_t, 256, ports=('r',), read_latency=1, init={masks!r})"
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
        global_definitions,
    )


def publish_owned(
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
    global_definitions,
    extra=None,
):
    ret = fn.body[-1]
    count = len(shared)
    private = proof["private_fields"]
    # Returned snapshot must not write back into architectural Reg state.
    # Bind combinational output aliases, leaving legacy registers untouched.
    for k in visible:
        fn.body[-1:-1] = ast.parse(
            f"cfg_output_{k}: {c.typ(k)} = {k}\nif cfg_busy:\n    cfg_output_{k} = cfg_visible_{k}"
        ).body
    fn.body[-1:-1] = ast.parse(
        "if cfg_busy:\n    status = STATUS_RUNNING\n    committed = 0"
    ).body
    for keyword in ret.value.keywords:
        if keyword.arg in visible:
            keyword.value = ast.Name(id="cfg_output_" + keyword.arg, ctx=ast.Load())
    ret.value.keywords.append(
        ast.keyword(arg="busy", value=ast.Name(id="cfg_busy", ctx=ast.Load()))
    )
    status_type = next(
        n
        for n in source.body
        if isinstance(n, ast.ClassDef) and n.name == "red2_status_t"
    )
    status_type.body += ast.parse("busy: uint1_t").body
    idx = source.body.index(fn)
    source.body[idx:idx] = ast.parse(global_definitions).body + controller.body
    ast.fix_missing_locations(source)
    (root / "machine.py").write_text(ast.unparse(source) + "\n")
    record = {
        **proof,
        "source_sha256": m["source_sha256"],
        "removed_handlers": sorted(removed),
        "synchronous_states": sorted(sync_states),
        "bridge_fields": shared,
        "bridge_words": count,
        "entry_schedules": plans,
        "visible_snapshot_fields": visible,
        "protocol": "CLOCK advances, NOP pauses. One busy lifecycle command is queued and applied after logical completion; wait for busy=0 before another command. Private lifecycle writes are serialized with exact original masks.",
        "scope": "Experimental persistent private BRAM ownership; per-entry shared masks; coherent scalar observation; graph256 only",
    }
    record.update(extra or {})
    (root / "integration.json").write_text(json.dumps(record, indent=2) + "\n")
    print(
        "OWNED_INTEGRATED_TOP",
        root,
        len(private),
        "private words",
        count,
        "shared words",
        flush=True,
    )

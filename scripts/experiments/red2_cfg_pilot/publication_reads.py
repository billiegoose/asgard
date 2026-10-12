"""Explicit read-only sidecars for the source publication execution handler."""

import ast
import copy

BANKS = (
    ("pub_root", "red2_pub_root_t"),
    ("pub_patch", "red2_pub_patch_t"),
)


def extend_oracle(text, spec):
    if spec.get("read_only") is False:
        from publication_transactions import extend_oracle as full

        return full(text, spec)
    marker = "    control_write: uint1_t\n"
    assert text.count(marker) == 1
    text = text.replace(
        marker, marker + "".join(f"    {name}_addr: uint8_t\n" for name, _ in BANKS)
    )
    marker = "control_data:red2_control_t)->result_t:"
    text = text.replace(
        marker,
        "control_data:red2_control_t"
        + "".join(f", {name}_data:{dtype}" for name, dtype in BANKS)
        + ")->result_t:",
    )
    marker = "    memory_out.p0.rd_data = memory_data\n"
    text = text.replace(
        marker,
        "".join(
            f"    {name}_req: {name}_ram.p0_in_t\n"
            f"    {name}_out: {name}_ram.out_t\n"
            f"    {name}_out.p0.rd_data = {name}_data\n"
            for name, _ in BANKS
        )
        + marker,
    )
    marker = "control_write=control_req.wr_en)\n"
    return text.replace(
        marker,
        "control_write=control_req.wr_en"
        + "".join(f",{name}_addr={name}_req.addr" for name, _ in BANKS)
        + ")\n",
    )


def configure(tree, fn, types, structs):
    fields = []
    for name, dtype in BANKS:
        factory = next(
            n.value
            for n in tree.body
            if isinstance(n, ast.Assign)
            and isinstance(n.value, ast.Call)
            and any(
                isinstance(t, ast.Name) and t.id == name + "_ram"
                for t in ast.walk(n.targets[0])
            )
        )
        assert ast.unparse(factory.args[0]) == dtype
        assert ast.unparse(factory.args[1]) == "GRAPH_WORDS"
        options = {k.arg: ast.literal_eval(k.value) for k in factory.keywords}
        assert options["ports"] == ("rw",) and options["read_latency"] == 1
        types[name + "_req.addr"] = "uint8_t"
        types[name + "_out.p0.rd_data"] = dtype

        def flatten(typ, suffix="", name=name):
            if typ in structs:
                for field, child in structs[typ].items():
                    flatten(child, suffix + "." + field)
            else:
                assert typ.startswith("uint") and typ.endswith("_t")
                fields.append(
                    {
                        "name": name + "_read" + suffix.replace(".", "_"),
                        "key": name + "_out.p0.rd_data" + suffix,
                        "type": typ,
                        "width": int(typ[4:-2]),
                        "bank": name,
                        "suffix": suffix,
                    }
                )

        flatten(dtype)
    extra = []
    for n in fn.body:
        if isinstance(n, ast.If) and ast.unparse(n.test) == "command_is_clock":
            for arm in n.body:
                if (
                    not isinstance(arm, ast.If)
                    or ast.unparse(arm.test) != "micro_is_pub_exec"
                ):
                    continue
                targets = [
                    t
                    for x in ast.walk(arm)
                    if isinstance(x, ast.Assign)
                    for t in x.targets
                ]
                names = {ast.unparse(t) for t in targets}
                if names & {name + "_req.addr" for name, _ in BANKS}:
                    assert names <= {name + "_req.addr" for name, _ in BANKS}
                    extra += copy.deepcopy(arm.body)
    assert extra, "publication metadata request arm missing"
    return {"banks": list(BANKS), "responses": fields}, extra


def extend_emitter(text, m):
    if m["publication_reads"].get("read_only") is False:
        from publication_transactions import extend_emitter as full

        return full(text, m)
    spec = m["publication_reads"]
    response_fields = spec["responses"]
    declarations = "".join(f"    {f['name']}: {f['type']}\n" for f in response_fields)
    # input_t's control_tag is followed by output_t; request_t has control_write.
    marker = "    control_tag: uint4_t\n@struct\nclass output_t"
    assert text.count(marker) == 1
    text = text.replace(
        marker, "    control_tag: uint4_t\n" + declarations + "@struct\nclass output_t"
    )
    marker = "    control_write: uint1_t\n@struct\nclass input_t"
    additions = "".join(f"    {name}_addr: uint8_t\n" for name, _ in BANKS)
    assert text.count(marker) == 1
    text = text.replace(
        marker, "    control_write: uint1_t\n" + additions + "@struct\nclass input_t"
    )
    text = text.replace(
        "uint8_t, uint64_t\n", "uint8_t, uint17_t, uint32_t, uint2_t, uint64_t\n"
    )
    marker = "    control_tag: Reg[uint4_t]\n"
    assert text.count(marker) == 1
    text = text.replace(
        marker,
        marker
        + "".join(f"    {f['name']}: Reg[{f['type']}]\n" for f in response_fields),
    )
    marker = "    result_mask: uint64_t ="
    assignments = "".join(
        f"        if row.b == {i}:\n            result = {f['name']}\n"
        for i, f in enumerate(response_fields, 5)
    )
    assert text.count(marker) == 1
    text = text.replace(marker, assignments + marker)
    marker = "            if row.d == 15:\n"
    assignments = "".join(
        f"            if row.d == {i}:\n                request.{name}_addr = a\n"
        for i, (name, _) in enumerate(BANKS, 9)
    )
    assert text.count(marker) == 1
    text = text.replace(marker, assignments + marker)
    marker = "            control_tag = i.control_tag\n"
    text = text.replace(
        marker,
        marker
        + "".join(
            f"            {f['name']} = i.{f['name']}\n" for f in response_fields
        ),
    )
    return text


def bridge(text, m, part):
    spec = m.get("publication_reads")
    if not spec:
        return text
    if spec.get("read_only") is False:
        from publication_transactions import bridge as full

        return full(text, m, part)
    fields = spec["responses"]
    if part == "admit":
        marker = "cfg_read_control_tag: Reg[uint4_t]\n"
        assert text.count(marker) == 1
        return text.replace(
            marker,
            marker
            + "".join(f"cfg_read_{f['name']}: Reg[{f['type']}]\n" for f in fields),
        )
    if part == "request":
        marker = ", enable=cfg_clock)"
        assert text.count(marker) == 1
        text = text.replace(
            marker,
            "".join(f", {f['name']}=cfg_read_{f['name']}" for f in fields) + marker,
        )
        return text + "".join(
            f"    {name}_req.addr = cfg_o.request.{name}_addr\n" for name, _ in BANKS
        )
    assert part == "finish"
    marker = "        cfg_read_control_tag = control_out.p0.rd_data.tag_hi\n"
    assert text.count(marker) == 1
    return text.replace(
        marker,
        marker
        + "".join(f"        cfg_read_{f['name']} = {f['key']}\n" for f in fields),
    )

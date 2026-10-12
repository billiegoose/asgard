"""Source-derived publication packets; retain synchronous read-first semantics."""

import ast
import copy

BANKS = (
    ("pub_task", "red2_pub_task_t", "PUB_TASK_WORDS", 10),
    ("pub_root", "red2_pub_root_t", "GRAPH_WORDS", 8),
    ("pub_patch", "red2_pub_patch_t", "GRAPH_WORDS", 8),
    ("pub_patch_addr", "uint17_t", "GRAPH_WORDS", 8),
    ("pub_mat", "red2_pub_mat_t", "GRAPH_WORDS", 8),
)
STATES = {"micro_is_pub_exec", "micro_is_pub_stack"}
EVENT = "pub_completion_shared_init_launch"


def flag(arm):
    """Accept only a selected positive flag, possibly conjoined with a phase."""
    if not isinstance(arm, ast.If):
        return None
    terms = (
        arm.test.values
        if isinstance(arm.test, ast.BoolOp) and isinstance(arm.test.op, ast.And)
        else [arm.test]
    )
    found = [t.id for t in terms if isinstance(t, ast.Name) and t.id in STATES]
    assert len(found) <= 1
    return found[0] if found else None


def configure(tree, fn, types, structs):
    req, resp = [], []

    def leaves(dtype, suffix=""):
        if dtype in structs:
            return [
                leaf
                for k, child in structs[dtype].items()
                for leaf in leaves(child, suffix + "." + k)
            ]
        assert dtype.startswith("uint") and dtype.endswith("_t")
        return [(suffix, dtype, int(dtype[4:-2]))]

    for name, dtype, depth, width in BANKS:
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
        assert (
            ast.unparse(factory.args[0]) == dtype
            and ast.unparse(factory.args[1]) == depth
        )
        opts = {k.arg: ast.literal_eval(k.value) for k in factory.keywords}
        assert opts["ports"] == ("rw",) and opts["read_latency"] == 1
        types[name + "_req.addr"] = f"uint{width}_t"
        types[name + "_req.wr_en"] = "uint1_t"
        types[name + "_req.wr_data"] = dtype
        types[name + "_out.p0.rd_data"] = dtype
        fields = [("_addr", ".addr", f"uint{width}_t", width)]
        fields += [
            ("_write" + s.replace(".", "_"), ".wr_data" + s, t, w)
            for s, t, w in leaves(dtype)
        ]
        fields += [("_write_enable", ".wr_en", "uint1_t", 1)]
        req += [
            {
                "name": name + s,
                "key": name + "_req" + k,
                "type": t,
                "width": w,
                "bank": name,
            }
            for s, k, t, w in fields
        ]
        resp += [
            {
                "name": name + "_read" + s.replace(".", "_"),
                "key": name + "_out.p0.rd_data" + s,
                "type": t,
                "width": w,
                "bank": name,
                "suffix": s,
            }
            for s, t, w in leaves(dtype)
        ]
    requests = {s.removeprefix("micro_is_"): [] for s in STATES}
    for parent in fn.body:
        if (
            isinstance(parent, ast.If)
            and ast.unparse(parent.test) == "command_is_clock"
        ):
            for arm in parent.body:
                state = flag(arm)
                if state:
                    copied = copy.deepcopy(arm)

                    class Admit(ast.NodeTransformer):
                        def visit_Name(self, n, state=state):
                            return (
                                ast.copy_location(ast.Constant(value=1), n)
                                if n.id == state
                                else n
                            )

                    requests[state.removeprefix("micro_is_")].append(
                        Admit().visit(copied)
                    )
    assert len(requests["pub_stack"]) == 3 and len(requests["pub_exec"]) == 2
    defaults = []
    names = {n + "_req" for n, *_ in BANKS}
    for n in fn.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            t = n.targets[0]
            if (
                isinstance(t, ast.Attribute)
                and isinstance(t.value, ast.Name)
                and t.value.id in names
                and t.attr in {"addr", "wr_data", "wr_en"}
            ):
                defaults.append(copy.deepcopy(n))
    assert len(defaults) == 15
    return (
        {
            "banks": [(n, t) for n, t, *_ in BANKS],
            "requests": req,
            "responses": resp,
            "read_only": False,
        },
        requests,
        defaults,
    )


def completion_bank(fn):
    bank = next(
        n
        for n in fn.body
        if isinstance(n, ast.If)
        and isinstance(n.test, ast.BoolOp)
        and any(isinstance(t, ast.Name) and t.id == EVENT for t in n.test.values)
    )
    writers = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == EVENT
    ]
    assert len(writers) == 2  # zero default and one stack assertion
    stack = next(
        n
        for n in fn.body
        if isinstance(n, ast.If)
        and ast.unparse(n.test) == "clock_dispatch_enable and micro_is_pub_stack"
    )
    assert any(
        isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == EVENT
        for n in ast.walk(stack)
    )
    return ast.If(
        test=ast.Name(id=EVENT, ctx=ast.Load()),
        body=copy.deepcopy(bank.body),
        orelse=[],
    )


def remove_legacy(fn):
    for parent in fn.body:
        if (
            isinstance(parent, ast.If)
            and ast.unparse(parent.test) == "command_is_clock"
        ):
            parent.body = [arm for arm in parent.body if not flag(arm)]
        if isinstance(parent, ast.If) and isinstance(parent.test, ast.BoolOp):
            parent.test.values = [
                t
                for t in parent.test.values
                if not (isinstance(t, ast.Name) and t.id == EVENT)
            ]
    fn.body = [n for n in fn.body if not (isinstance(n, ast.If) and not n.body)]
    ast.fix_missing_locations(fn)


def extend_oracle(text, spec):
    marker = "    control_write: uint1_t\n"
    assert text.count(marker) == 1
    text = text.replace(
        marker,
        marker + "".join(f"    {f['name']}: {f['type']}\n" for f in spec["requests"]),
    )
    text = text.replace(
        "control_data:red2_control_t)->result_t:",
        "control_data:red2_control_t"
        + "".join(f", {n}_data:{t}" for n, t in spec["banks"])
        + ")->result_t:",
    )
    marker = "    memory_out.p0.rd_data = memory_data\n"
    text = text.replace(
        marker,
        "".join(
            f"    {n}_req: {n}_ram.p0_in_t\n    {n}_out: {n}_ram.out_t\n"
            f"    {n}_out.p0.rd_data = {n}_data\n"
            for n, _ in spec["banks"]
        )
        + marker,
    )
    return text.replace(
        "control_write=control_req.wr_en)\n",
        "control_write=control_req.wr_en"
        + "".join(f",{f['name']}={f['key']}" for f in spec["requests"])
        + ")\n",
    )


def extend_emitter(text, m):
    spec = m["publication_reads"]
    marker = "    control_tag: uint4_t\n@struct\nclass output_t"
    assert text.count(marker) == 1
    text = text.replace(
        marker,
        "    control_tag: uint4_t\n"
        + "".join(f"    {f['name']}: {f['type']}\n" for f in spec["responses"])
        + "@struct\nclass output_t",
    )
    marker = "    control_write: uint1_t\n@struct\nclass input_t"
    assert text.count(marker) == 1
    text = text.replace(
        marker,
        "    control_write: uint1_t\n"
        + "".join(f"    {f['name']}: {f['type']}\n" for f in spec["requests"])
        + "@struct\nclass input_t",
    )
    widths = sorted(
        {f["width"] for f in spec["requests"] + spec["responses"]} - {1, 4, 8, 64}
    )
    text = text.replace(
        "addr_t = make_uint_t(",
        "".join(f"uint{w}_t = make_uint_t({w})\n" for w in widths)
        + "addr_t = make_uint_t(",
        1,
    )
    marker = "    control_tag: Reg[uint4_t]\n"
    assert text.count(marker) == 1
    text = text.replace(
        marker,
        marker
        + "".join(f"    {f['name']}: Reg[{f['type']}]\n" for f in spec["responses"]),
    )
    text = text.replace(
        "    result_mask: uint64_t =",
        "".join(
            f"        if row.b == {i}:\n            result = {f['name']}\n"
            for i, f in enumerate(spec["responses"], 5)
        )
        + "    result_mask: uint64_t =",
    )
    marker = "            if row.d == 15:\n"
    assert text.count(marker) == 1
    text = text.replace(
        marker,
        "".join(
            f"            if row.d == {i}:\n                request.{f['name']} = a\n"
            for i, f in enumerate(spec["requests"], 9)
        )
        + f"            if row.d == {m['request_sentinel']}:\n",
    )
    marker = "            control_tag = i.control_tag\n"
    text = text.replace(
        marker,
        marker
        + "".join(
            f"            {f['name']} = i.{f['name']}\n" for f in spec["responses"]
        ),
    )
    if m.get("sparse_publication"):
        marker = "        if i.start and not i.setup_write:\n            phase = 1\n"
        assert text.count(marker) == 1
        text = text.replace(
            marker,
            marker
            + "".join(
                f"            request.{f['name']} = 0\n" for f in spec["requests"]
            ),
        )
    return text


def bridge(text, m, part):
    spec = m["publication_reads"]
    if part == "admit":
        marker = "cfg_read_control_tag: Reg[uint4_t]\n"
        assert text.count(marker) == 1
        return text.replace(
            marker,
            marker
            + "".join(
                f"cfg_read_{f['name']}: Reg[{f['type']}]\n" for f in spec["responses"]
            ),
        )
    if part == "request":
        marker = ", enable=cfg_clock)"
        assert text.count(marker) == 1
        text = text.replace(
            marker,
            "".join(f", {f['name']}=cfg_read_{f['name']}" for f in spec["responses"])
            + marker,
        )
        # Field assignments include every original write-data leaf and enable.
        return text + "".join(
            f"    {f['key']} = cfg_o.request.{f['name']}\n" for f in spec["requests"]
        )
    assert part == "finish"
    marker = "        cfg_read_control_tag = control_out.p0.rd_data.tag_hi\n"
    assert text.count(marker) == 1
    return text.replace(
        marker,
        marker
        + "".join(
            f"        cfg_read_{f['name']} = {f['key']}\n" for f in spec["responses"]
        ),
    )

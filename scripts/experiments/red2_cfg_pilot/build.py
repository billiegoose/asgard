"""Experimental immutable APP/LAMBDA control-table lowering, before SSA."""

import ast
import copy
import hashlib
import json

from expression_types import ExpressionTypes
from paths import EXTRA_STATES, INCLUDE_GRAPH, INCLUDE_LOOKUP, OUT, ROOT

SOURCE = ROOT / "src/machines/synthesizable_red2_machine/machine.py"
source = SOURCE.read_text()
tree = ast.parse(source)
fn = next(
    x
    for x in tree.body
    if isinstance(x, ast.FunctionDef) and x.name == "SynthesizableRED2Machine"
)
constants = {
    "GRAPH_WORDS": 256,
    "GRAPH_ADDR_BITS": 8,
    "CONTROL_WORDS": 256,
    "CONTROL_ADDR_BITS": 8,
}
for x in tree.body:
    if (
        isinstance(x, ast.Assign)
        and len(x.targets) == 1
        and isinstance(x.targets[0], ast.Name)
        and isinstance(x.value, ast.Constant)
        and isinstance(x.value.value, int)
    ):
        constants[x.targets[0].id] = x.value.value
structs = {
    x.name: {
        a.target.id: ast.unparse(a.annotation)
        for a in x.body
        if isinstance(a, ast.AnnAssign)
    }
    for x in tree.body
    if isinstance(x, ast.ClassDef)
}
types = {}
regs = set()
aliases = {}
for x in ast.walk(fn):
    if isinstance(x, ast.AnnAssign) and isinstance(x.target, ast.Name):
        typ = ast.unparse(x.annotation)
        if typ.startswith("Reg["):
            typ = typ[4:-1]
            regs.add(x.target.id)
        types[x.target.id] = typ
for x in fn.body:
    if (
        isinstance(x, ast.AnnAssign)
        and x.value is not None
        and isinstance(x.target, ast.Name)
    ):
        aliases[x.target.id] = x
# RAM port bundles are flattened explicitly. No generic type guessing.
for prefix, fields in {
    "memory_req": {"addr": 8, "wr_en": 1, "wr_data.lo": 64, "wr_data.hi": 64},
    "control_req": {
        "addr": 8,
        "wr_en": 1,
        "wr_data.lo": 64,
        "wr_data.hi": 64,
        "wr_data.tag_hi": 4,
    },
    "memory_out.p0.rd_data": {"lo": 64, "hi": 64},
    "control_out.p0.rd_data": {"lo": 64, "hi": 64, "tag_hi": 4},
}.items():
    for field, width in fields.items():
        types[prefix + "." + field] = "uint" + str(width) + "_t"
types["memory_req.wr_data"] = "red2_word_t"
types["control_req.wr_data"] = "red2_control_t"
types["command.word"] = "red2_word_t"
types["command.control"] = "red2_control_t"


def key(x):
    if isinstance(x, ast.Name):
        return x.id
    if isinstance(x, ast.Attribute):
        return key(x.value) + "." + x.attr
    raise ValueError(ast.dump(x))


def typ(name):
    if name in types:
        return types[name]
    parent, field = name.rsplit(".", 1)
    return structs[typ(parent)][field]


def leaves(name):
    t = typ(name)
    if t in structs:
        return [(leaf, w) for f in structs[t] for leaf, w in leaves(name + "." + f)]
    assert t.startswith("uint") and t.endswith("_t"), (name, t)
    return [(name, int(t[4:-2]))]


selected = {}
for x in fn.body:
    if isinstance(x, ast.If) and ast.unparse(x.test).startswith(
        "clock_dispatch_enable and micro_is_"
    ):
        name = ast.unparse(x.test).split("micro_is_", 1)[1]
        if (
            "MICRO_" + name.upper() in EXTRA_STATES
            or name.startswith(("app_", "lambda_"))
            or (INCLUDE_LOOKUP and name.startswith("lookup_"))
            or (
                INCLUDE_GRAPH
                and name.startswith(("ep_", "closure_", "rup_", "recp_"))
                and name != "ep_reverse_control_read"
            )
        ):
            selected["MICRO_" + name.upper()] = (x, constants["MICRO_" + name.upper()])
assert set(EXTRA_STATES) <= set(selected), "unknown additional microstate"
if not INCLUDE_GRAPH and not EXTRA_STATES:
    assert len(selected) == (24 if INCLUDE_LOOKUP else 20)
request_parent = next(
    x
    for x in fn.body
    if isinstance(x, ast.If)
    and ast.unparse(x.test) == "command_is_clock"
    and any(
        isinstance(c, ast.If) and ast.unparse(c.test) == "micro_is_lambda_read"
        for c in x.body
    )
)
requests = {
    ast.unparse(x.test).removeprefix("micro_is_"): x.body
    for x in request_parent.body
    if isinstance(x, ast.If)
}
execute = next(
    x
    for x in fn.body
    if isinstance(x, ast.If)
    and ast.unparse(x.test) == "clock_dispatch_enable and micro_is_execute"
)
for x in execute.body:
    if (
        isinstance(x, ast.AnnAssign)
        and x.value is not None
        and isinstance(x.target, ast.Name)
    ):
        aliases[x.target.id] = x
entry_ops = ["lambda", "app"]
if INCLUDE_GRAPH:
    entry_ops += ["ep", "closure", "rup", "recp"]
entry = [
    x
    for x in execute.body
    if isinstance(x, ast.If)
    and ast.unparse(x.test)
    in {"not fetched_invalid and opcode_is_" + op for op in entry_ops}
]
assert len(entry) == len(entry_ops)
if INCLUDE_LOOKUP:
    entry.append(
        next(
            x
            for x in execute.body
            if isinstance(x, ast.If)
            and ast.unparse(x.test).startswith("not fetched_invalid and (not (")
        )
    )
# Include exactly the common error priority for these execute opcodes.
entry_setup = ast.parse("""fetched_invalid: uint1_t = fetched_valid == 0
if fetched_invalid:
    red2_fault = FAULT_INVALID_ADDRESS
    microstate = MICRO_FAULT
""").body
# Requests are the original execute request arm. Unrelated opcode arms are inert
# for APP/LAMBDA, but keep it intact so common validation is not hand-pruned.
family = {
    name: (requests.get(name.removeprefix("MICRO_").lower(), []), node.body)
    for name, (node, _) in selected.items()
}
family["MICRO_EXECUTE"] = (requests["execute"], entry_setup + entry)

OP_NAMES = [
    "copy",
    "add",
    "sub",
    "and",
    "or",
    "eq",
    "ne",
    "not",
    "bool_and",
    "bool_or",
    "shr",
    "shl",
    "branch",
    "jump",
    "request",
    "response",
    "halt",
]
if INCLUDE_GRAPH:
    OP_NAMES.insert(OP_NAMES.index("branch"), "ge")
OP = {n: i for i, n in enumerate(OP_NAMES)}
rows = []
slots = {}
widths = {}
initial = {}
entry_pc = {}
programs = {}


def slot(name, width=64):
    if name not in slots:
        slots[name] = len(slots)
        widths[name] = width
    else:
        assert widths[name] == width, (name, width, widths[name])
    return slots[name]


def const(value):
    assert 0 <= value < (1 << 64), ("constant needs wider scratch", value)
    value &= (1 << 64) - 1
    n = "$constant_" + str(value)
    i = slot(n)
    initial[i] = value
    return i


def emit(op, a=0, b=0, d=0, width=64, yes=0, no=0):
    i = len(rows)
    rows.append(dict(op=OP[op], a=a, b=b, d=d, width=width, yes=yes, no=no))
    return i


def temp():
    return slot("$temp_" + str(len(slots)))


def ceval(x):
    return eval(
        compile(ast.Expression(x), "<constant>", "eval"),
        {"__builtins__": {}},
        constants,
    )


expression_types = ExpressionTypes(constants, leaves, key)


def expr(x, cap=None):
    if isinstance(x, ast.Constant):
        return const(x.value)
    if isinstance(x, (ast.Name, ast.Attribute)):
        n = key(x)
        if n in constants:
            return const(constants[n])
        w = leaves(n)
        assert len(w) == 1, (n, w)
        return slot(n, w[0][1])
    if isinstance(x, ast.Subscript):
        a = expr(x.value)
        if isinstance(x.slice, ast.Slice):
            hi = ceval(x.slice.lower)
            lo = ceval(x.slice.upper)
        else:
            hi = lo = ceval(x.slice)
        d = temp()
        emit("shr", a, const(lo), d, hi - lo + 1)
        return d
    if isinstance(x, ast.UnaryOp) and isinstance(x.op, ast.Not):
        d = temp()
        emit("not", expr(x.operand), 0, d, 1)
        return d
    if isinstance(x, ast.BoolOp):
        a = expr(x.values[0])
        for v in x.values[1:]:
            b = expr(v)
            d = temp()
            emit("bool_and" if isinstance(x.op, ast.And) else "bool_or", a, b, d, 1)
            a = d
        return a
    if isinstance(x, ast.BinOp):
        op = {
            ast.Add: "add",
            ast.Sub: "sub",
            ast.BitAnd: "and",
            ast.BitOr: "or",
            ast.LShift: "shl",
            ast.RShift: "shr",
        }[type(x.op)]
        width, raw = expression_types.infer(x)
        if raw:
            return const(ceval(x))
        if cap is not None:
            width = min(width, cap)
        assert width <= 64, ("expression needs wider scratch", ast.unparse(x), width)
        # Low-bit arithmetic/bitwise/shl results do not require higher input
        # bits. Right shifts and comparisons must retain their full operands.
        child_cap = (
            width
            if isinstance(x.op, (ast.Add, ast.Sub, ast.BitAnd, ast.BitOr, ast.LShift))
            else None
        )
        a = expr(x.left, child_cap)
        b = expr(
            x.right,
            child_cap
            if isinstance(x.op, (ast.Add, ast.Sub, ast.BitAnd, ast.BitOr))
            else None,
        )
        d = temp()
        emit(op, a, b, d, width)
        return d
    if isinstance(x, ast.Compare) and len(x.ops) == 1:
        op = {ast.Eq: "eq", ast.NotEq: "ne"}[type(x.ops[0])]
        a = expr(x.left)
        b = expr(x.comparators[0])
        d = temp()
        emit(op, a, b, d, 1)
        return d
    if (
        INCLUDE_GRAPH
        and isinstance(x, ast.Call)
        and isinstance(x.func, ast.Name)
        and x.func.id == "red2_u64_ge"
    ):
        assert len(x.args) == 2 and not x.keywords
        a, b = (expr(arg) for arg in x.args)
        d = temp()
        emit("ge", a, b, d, 1)
        return d
    raise ValueError("Unsupported expression: " + ast.unparse(x))


def field_value(value, field):
    if isinstance(value, ast.Call):
        assert value.func.id in structs
        return next(k.value for k in value.keywords if k.arg == field)
    return ast.Attribute(value=copy.deepcopy(value), attr=field, ctx=ast.Load())


def assign(name, value):
    t = typ(name)
    if t in structs:
        for f in structs[t]:
            assign(name + "." + f, field_value(value, f))
    else:
        w = leaves(name)[0][1]
        a = expr(value, cap=w)
        emit("copy", a, 0, slot(name, w), w)


def statements(body):
    for x in body:
        if isinstance(x, ast.AnnAssign):
            if x.value is not None:
                assign(key(x.target), x.value)
        elif isinstance(x, ast.Assign):
            assert len(x.targets) == 1
            assign(key(x.targets[0]), x.value)
        elif isinstance(x, ast.If):
            a = expr(x.test)
            branch = emit("branch", a)
            rows[branch]["yes"] = len(rows)
            statements(x.body)
            j = emit("jump")
            rows[branch]["no"] = len(rows)
            statements(x.orelse)
            rows[j]["yes"] = len(rows)
        else:
            raise ValueError("Unsupported statement: " + ast.unparse(x))


REQUEST_KEYS = [
    "memory_req.addr",
    "memory_req.wr_data.lo",
    "memory_req.wr_data.hi",
    "memory_req.wr_en",
    "control_req.addr",
    "control_req.wr_data.lo",
    "control_req.wr_data.hi",
    "control_req.wr_data.tag_hi",
    "control_req.wr_en",
]
RESPONSE_KEYS = [
    "memory_out.p0.rd_data.lo",
    "memory_out.p0.rd_data.hi",
    "control_out.p0.rd_data.lo",
    "control_out.p0.rd_data.hi",
    "control_out.p0.rd_data.tag_hi",
]
# Constant rows are not writable from the setup/debug port.
emit("halt")
for name, (req, body) in family.items():
    roots = {
        n.id
        for x in req + body
        for n in ast.walk(x)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    needed = set()

    def need(n, needed=needed):
        if n in needed or n not in aliases:
            return
        needed.add(n)
        for d in ast.walk(aliases[n].value):
            if isinstance(d, ast.Name):
                need(d.id)

    for n in roots:
        need(n)
    setup = [
        x
        for x in list(fn.body) + execute.body
        if isinstance(x, ast.AnnAssign)
        and isinstance(x.target, ast.Name)
        and x.target.id in needed
    ]
    # Original RAM defaults, with zero disabled data. command payload is not
    # used by CLOCK except as the unobservable disabled write-data default.
    defaults = ast.parse("""memory_req.addr = 0
memory_req.wr_en = 0
control_req.addr = 0
control_req.wr_en = 0
command.word = red2_word_t(lo=0,hi=0)
command.control = red2_control_t(lo=0,hi=0,tag_hi=0)
clock_memory_req_data: red2_word_t = red2_word_t(lo=0,hi=0)
clock_control_req_data: red2_control_t = red2_control_t(lo=0,hi=0,tag_hi=0)
""").body
    finish_req = ast.parse("""memory_req.wr_data = clock_memory_req_data
control_req.wr_data = clock_control_req_data
""").body
    entry_pc[constants[name]] = len(rows)
    statements(defaults + setup + req + finish_req)
    for j, k in enumerate(REQUEST_KEYS):
        emit("request", expr(ast.parse(k, mode="eval").body), d=j)
    emit("request", d=15)
    for j, k in enumerate(RESPONSE_KEYS):
        emit("response", d=slot(k, leaves(k)[0][1]), b=j, width=leaves(k)[0][1])
    statements(body)
    emit("halt")
    programs[name] = {
        "setup": setup,
        "defaults": defaults,
        "request": req + finish_req,
        "body": body,
    }
manifest = {
    "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
    "scope": list(family),
    "entry_pc": entry_pc,
    "rows": rows,
    "slots": slots,
    "widths": widths,
    "initial": initial,
    "request_keys": REQUEST_KEYS,
    "response_keys": RESPONSE_KEYS,
    "ops": OP,
    "include_lookup": INCLUDE_LOOKUP,
    "include_graph": INCLUDE_GRAPH,
    "extra_states": list(EXTRA_STATES),
    "entry_opcodes": ["MOP_APP", "MOP_LAMBDA"]
    + ["MOP_" + op.upper() for op in entry_ops[2:]]
    + (["MOP_VAR", "MOP_APP_VAR"] if INCLUDE_LOOKUP else []),
    "graph_words": 256,
    "admission": (
        "One already-admitted logical transition. MICRO_EXECUTE accepts "
        "the entry_opcodes listed above (graph scope adds EP/CLOSURE/RUP/RECP). "
        "Outer command/fault/synchronous-read arbitration remains "
        "outside this pilot."
    ),
}
# The source CFG is acyclic within one admitted logical transition. Prove that
# every semantic operand is initialized on every path, rather than treating
# zeroed simulation scratch as a substitute for an assignment.
inputs = {
    i
    for name, i in slots.items()
    if name.startswith("$constant_") or name.split(".")[0] in regs
}
starts = sorted(entry_pc.values())
for start, end in zip(starts, [*starts[1:], len(rows)], strict=True):
    incoming = {start: set(inputs)}
    for pc in range(start, end):
        if pc not in incoming:
            continue
        r = rows[pc]
        defined = incoming[pc].copy()
        op = r["op"]
        reads = []
        if op not in {OP[n] for n in ("jump", "response", "halt")} and not (
            op == OP["request"] and r["d"] == 15
        ):
            reads.append(r["a"])
        if op in {
            OP[n]
            for n in (
                "add",
                "sub",
                "and",
                "or",
                "eq",
                "ne",
                "bool_and",
                "bool_or",
                "shr",
                "shl",
                "ge",
            )
            if n in OP
        }:
            reads.append(r["b"])
        assert set(reads) <= defined, (start, pc, set(reads) - defined)
        if op not in {OP[n] for n in ("branch", "jump", "request", "halt")}:
            defined.add(r["d"])
        successors = (
            []
            if op == OP["halt"]
            else (
                [r["yes"], r["no"]]
                if op == OP["branch"]
                else [r["yes"]]
                if op == OP["jump"]
                else [pc + 1]
            )
        )
        for successor in successors:
            assert pc < successor < end, (pc, successor, end)
            if successor in incoming:
                incoming[successor] &= defined
            else:
                incoming[successor] = defined.copy()
manifest["all_paths_operands_initialized"] = True
covered_lines = set()
for req, body in family.values():
    for statement in req + body:
        covered_lines.update(range(statement.lineno, statement.end_lineno + 1))
state_names = sorted({name.split(".")[0] for name in slots} & regs)
ownership = {}
for name in state_names:
    reads, writes = set(), set()
    for statement in ast.walk(fn):
        if getattr(statement, "lineno", 0) in covered_lines:
            continue
        if isinstance(statement, ast.Name) and statement.id == name:
            if isinstance(statement.ctx, ast.Load):
                reads.add(statement.lineno)
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            if (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.annotation, ast.Subscript)
                and ast.unparse(statement.annotation.value) == "Reg"
            ):
                continue
            targets = (
                statement.targets
                if isinstance(statement, ast.Assign)
                else [statement.target]
            )
            for target in targets:
                if (
                    isinstance(target, (ast.Name, ast.Attribute))
                    and key(target).split(".")[0] == name
                ):
                    writes.add(statement.lineno)
    ownership[name] = {"outside_reads": sorted(reads), "outside_writes": sorted(writes)}
manifest["state_ownership"] = ownership
manifest["handoffs"] = sorted(
    {
        node.id
        for _, body in family.values()
        for statement in body
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and node.id.startswith("MICRO_")
    }
    - set(family)
)
(OUT / "control-unmapped.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(
    "CFG_TABLE",
    len(family),
    "entries",
    len(rows),
    "rows",
    len(slots),
    "scratch words",
    flush=True,
)

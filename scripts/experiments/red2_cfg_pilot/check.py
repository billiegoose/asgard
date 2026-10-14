# isort: skip_file
import importlib.util
import json
import operator
import random
import sys
from paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import run_syn  # noqa: F401 -- verifies and bootstraps enhanced PipelineC
import pypeline
from native_runtime import cache_scalar_types

from pypeline import sim_call
from paths import OUT as P
from packets import construct, request_fields, sidecars

cache_scalar_types(pypeline)

m = json.loads((P / "control.json").read_text())
ops = m["ops"]
rows = m["rows"]
slots = m["slots"]
widths = m["widths"]
constant_exports = {
    slots[name]: value
    for name, value in m.get("dirty_writeback", {}).get("constant_writes", {}).items()
}
spec = importlib.util.spec_from_file_location("cfg_reference", P / "reference.py")
ref = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ref
spec.loader.exec_module(ref)
assert ref.GRAPH_WORDS == m["graph_words"] == 256
regs = json.loads((P / "reference-regs.json").read_text())
mask64 = (1 << 64) - 1


def nested_get(obj, name):
    for p in name.split(".")[1:]:
        obj = getattr(obj, p)
    return int(obj)


def typed_state(values):
    return ref.state_t(
        **{
            reg: construct(ref.state_t.__annotations__[reg], reg, values)
            for reg in regs
        }
    )


def model(values, state, response):
    mem = [0] * m["scratch_words"]
    for k, v in m["initial"].items():
        mem[int(k)] = v
    for k, v in values.items():
        mem[slots[k]] = v
    pc = m["entry_pc"][str(state)]
    request = [0] * len(request_fields(m))
    requests = 0
    trace = set()
    for _ in range(20000):
        r = rows[pc]
        op = r["op"]
        a = mem[r["a"]]
        b = mem[r["b"]]
        pc += 1
        trace.add(pc - 1)
        if op == ops["halt"]:
            break
        if op == ops["branch"]:
            pc = r["yes"] if a else r["no"]
            continue
        if op == ops["jump"]:
            pc = r["yes"]
            continue
        if op == ops["request"]:
            if r["d"] == m.get("request_sentinel", 15):
                requests += 1
            else:
                request[r["d"]] = a
            continue
        if op == ops["response"]:
            v = response[r["b"]]
        else:
            name = next(name for name, value in ops.items() if value == op)
            if name == "copy":
                v = a
            elif name == "not":
                v = not a
            elif name == "bool_and":
                v = bool(a) and bool(b)
            elif name == "bool_or":
                v = bool(a) or bool(b)
            elif name == "shr":
                v = a >> b if b < 64 else 0
            elif name == "shl":
                v = a << b if b < 64 else 0
            else:
                v = {
                    "add": operator.add,
                    "sub": operator.sub,
                    "mul": operator.mul,
                    "and": operator.and_,
                    "or": operator.or_,
                    "eq": operator.eq,
                    "ne": operator.ne,
                    "ge": operator.ge,
                }[name](a, b)
        mem[r["d"]] = int(v) & ((1 << r["width"]) - 1)
        if r["d"] in constant_exports:
            assert mem[r["d"]] == constant_exports[r["d"]], (
                "constant-write proof",
                state,
                pc - 1,
                r["d"],
            )
    else:
        raise AssertionError("control table did not halt")
    assert requests == 1
    return mem, request, len(trace), trace


rng = random.Random(203708309)
state_keys = [k for k in slots if k.split(".")[0] in regs]
cases = []
coverage = {}
typed_comparisons = 0
integer_corners = []
multiply_corners = {}
if "--shared-multiply-corners" in sys.argv:
    assert "mul" in ops
    products = [
        (0, 0),
        (0, mask64),
        (1, mask64),
        (1 << 63, 1),
        ((1 << 32) + 1, (1 << 32) + 1),
        (mask64, mask64),
        (7, 3),
    ]
    multiply_corners[ref.MICRO_U64_DIV_FINISH] = [
        {
            "u64_div_resume_kind": ref.U64_DIV_RESUME_SCALAR_MUL,
            "u64_div_aux": a,
            "u64_div_divisor": b,
            "u64_div_quotient": mask64,
            "u64_div_flags": flags,
            "join_scalar_return_ep": ep,
        }
        for a, b in products
        for flags in range(4)
        for ep in (0, 1)
    ]
    multiply_corners[ref.MICRO_JOIN_SCALAR_INT_POW] = [
        {
            "join_scalar_int_pow_magnitude": a,
            "join_scalar_int_pow_base": b,
            "join_scalar_int_pow_bound": mask64,
            "join_scalar_int_pow_remaining": remaining,
            "join_scalar_int_pow_negative": negative,
            "join_scalar_return_ep": ep,
        }
        for a, b in products
        for remaining in (1, 2)
        for negative in (0, 1)
        for ep in (0, 1)
    ]
    assert {str(state) for state in multiply_corners} <= set(m["entry_pc"])
if "--integer-corners" in sys.argv:
    assert "integer_joins" in m
    for op in ("DEC", "INC", "NEGATE", "ABS", "FLOOR", "CEILING"):
        for payload in (0, 1, 2, (1 << 63) - 1, 1 << 63, (1 << 63) + 1, mask64):
            integer_corners.append(
                (getattr(ref, "SCALAR_OP_" + op), ref.MOP_INT, ref.DATA_SIGNED, payload)
            )
    for payload in (0, 1, 1 << 63, mask64):
        integer_corners.append(
            (ref.SCALAR_OP_EVEN, ref.MOP_INT, ref.DATA_SIGNED, payload)
        )
    for sign in (0, 1):
        for exponent, mantissa in ((0, 0), (0, 1), (1023, 0), (2047, 0), (2047, 1)):
            integer_corners.append(
                (
                    ref.SCALAR_OP_EVEN,
                    ref.MOP_FLOAT,
                    ref.DATA_FLOAT64,
                    (sign << 63) | (exponent << 52) | mantissa,
                )
            )
    for op in ("INTEGER_P", "FLOAT_P", "CHAR_P", "SYMBOL_P"):
        for opcode, kind in (
            (ref.MOP_INT, ref.DATA_SIGNED),
            (ref.MOP_FLOAT, ref.DATA_FLOAT64),
            (ref.MOP_CHAR, ref.DATA_SIGNED),
            (ref.MOP_SYM, ref.DATA_LITERAL_ID),
            (ref.MOP_APP, ref.DATA_SIGNED),
        ):
            integer_corners.append((getattr(ref, "SCALAR_OP_" + op), opcode, kind, 7))
for state in m["entry_pc"]:
    candidates = []
    corners = (
        integer_corners
        if int(state) in {ref.MICRO_JOIN_PUBLISH, ref.MICRO_JOIN_EP_RESULT_WRITE}
        else []
    )
    products = multiply_corners.get(int(state), [])
    for trial in range(120 + len(corners) + len(products)):
        values = {}
        for key in state_keys:
            w = widths[key]
            choices = [0, 1, 2, 254, 255, 256, 257, (1 << w) - 1, rng.getrandbits(w)]
            values[key] = rng.choice(choices) & ((1 << w) - 1)
        values["microstate"] = int(state)
        values["red2_fault"] = 0
        values["hw_fault"] = 0
        if trial % 3:
            valid_context = {
                "fsp": rng.randrange(64),
                "pc": rng.randrange(1, 64),
                "free_space": 256,
                "env": rng.choice([200, 256]),
                "control_top": rng.randrange(9),
                "q": rng.randrange(4),
                "phi": rng.randrange(5),
                "argcnt": rng.randrange(4),
                "app_entry_env": 200,
                "app_parent_env": 256,
            }
            values.update({k: v for k, v in valid_context.items() if k in values})
            for k in values:
                if widths[k] == 1:
                    values[k] = rng.randrange(2)
        if int(state) == ref.MICRO_EXECUTE:
            entry_ops = [getattr(ref, n) for n in m["entry_opcodes"]]
            values["fetched_word.hi"] = (
                (rng.choice(entry_ops) << 21)
                | (rng.choice([0, 1, 1, 1, 1]) << 26)
                | (rng.randrange(4) << 17)
                | (rng.randrange(2) << 16)
                | rng.getrandbits(16)
            )
        response = [
            rng.choice([0, 1, 255, 256, 257, mask64]),
            (rng.choice([0, 1, 1, 1, 1]) << 26)
            | (
                rng.choice(
                    [
                        ref.MOP_STOP,
                        ref.MOP_APP,
                        ref.MOP_EP,
                        ref.MOP_APP_VAR,
                        ref.MOP_LAMBDA,
                        ref.MOP_INT,
                        ref.MOP_UBV,
                        ref.MOP_REC,
                        ref.MOP_CLOSURE,
                        ref.MOP_PNP,
                        ref.MOP_NONE,
                    ]
                )
                << 21
            )
            | (rng.choice([0, 1, 1, 1, 2, 3]) << 17)
            | rng.getrandbits(17),
            rng.choice([0, 1, 255, 256, 257, mask64]),
            rng.choice([0, 1, mask64]),
            rng.choice([0, 1, 1, 1, 5, 6, 15]),
        ]
        for f in m.get("publication_reads", {}).get("responses", []):
            w = f["width"]
            response.append(
                rng.choice([0, 1, 2, 255, 256, (1 << w) - 1, rng.getrandbits(w)])
                & ((1 << w) - 1)
            )
        if "publication_reads" in m and int(state) == ref.MICRO_PUB_EXEC:
            task_kinds = [
                value
                for name, value in vars(ref).items()
                if name.startswith("PUB_TASK_")
                and isinstance(value, int)
                and name not in {"PUB_TASK_WORDS", "PUB_TASK_ADDR_BITS"}
            ]
            values["pub_current_task.kind"] = task_kinds[trial % len(task_kinds)]
            if trial % 3:
                values["pub_current_valid"] = 1
                values["pub_sp"] = 1
                values["pub_current_task.a"] = rng.randrange(1, 64)
                for j, f in enumerate(m["publication_reads"]["responses"], 5):
                    if f["suffix"] == ".generation":
                        response[j] = values["pub_generation"]
        if (
            m.get("publication_reads", {}).get("read_only") is False
            and int(state) == ref.MICRO_PUB_STACK
        ):
            values["pub_stack_phase"] = trial % 16
        launch_witness = None
        reverse_control_witness = None
        if (
            "reverse_control_launch_events" in m
            and int(state) == ref.MICRO_EP_REVERSE_CONTROL_READ
        ):
            from reverse_control import witness

            selected_reverse = witness(ref, widths, state_keys, trial)
            if selected_reverse is not None:
                values, response_base = selected_reverse
                response[:5] = response_base
                reverse_control_witness = trial
        metadata_launch_witness = None
        integer_corner_witness = None
        if 120 <= trial < 120 + len(corners):
            op, opcode, kind, payload = corners[trial - 120]
            values = {k: 0 for k in state_keys}
            values.update(
                microstate=int(state),
                fsp=64,
                pc=32,
                env=256,
                free_space=256,
                control_top=1,
                join_parent_address=10,
                join_result_address=12,
                join_scalar_active=1,
                join_prim_scalar_op=op,
                join_true_literal_id=8,
                join_false_literal_id=9,
            )
            values["join_publish_word.lo"] = payload
            values["join_publish_word.hi"] = (1 << 26) | (opcode << 21) | (kind << 17)
            integer_corner_witness = trial - 120
        if "literal_metadata" in m:
            for j, field in enumerate(m["publication_reads"]["responses"], 5):
                if field["bank"] != "literal_meta":
                    continue
                if field["suffix"] == ".literal_id" and trial % 3:
                    response[j] = values.get("join_frame_prim_id", 0)
                elif field["suffix"] == ".special_flags" and trial % 3:
                    response[j] = 1 << (trial % 16)
            if trial == 0 and int(state) in {
                ref.MICRO_JOIN_PRIM_META_SCAN,
                ref.MICRO_STRUCT_SELECTOR_VALUE_READ,
            }:
                values = {k: (1 << widths[k]) - 1 for k in state_keys}
                values.update(microstate=int(state), red2_fault=0, hw_fault=0)
                if int(state) == ref.MICRO_JOIN_PRIM_META_SCAN:
                    values.update(
                        prim0_meta_active=0,
                        direct_scalar_active=0,
                        ep_scalar_active=0,
                        q=1,
                    )
                    for j, field in enumerate(m["publication_reads"]["responses"], 5):
                        if field["bank"] == "literal_meta":
                            response[j] = {
                                ".valid": 1,
                                ".literal_id": values["join_frame_prim_id"],
                                ".special_flags": 1 << 6,
                            }.get(field["suffix"], 0)
                else:
                    response[0] = 7
                    response[1] = (1 << 26) | (ref.MOP_STRUCT << 21) | (1 << 20)
                metadata_launch_witness = int(state)
        if "scalar_core" in m and int(state) == ref.MICRO_JOIN_SCALAR_LEFT_READ:
            flags = m["scalar_core"]["priority"]
            selected = trial // 32
            # Each selected arm also sees lower-priority flags, exercising the
            # source priority when a continuation clears its own active bit.
            for j, flag in enumerate(flags):
                values[flag] = int(j >= selected)
            for phase in (
                "equality_continue_phase",
                "equality_child_phase",
                "equality_launch_phase",
            ):
                values[phase] = (trial % 32) & ((1 << widths[phase]) - 1)
        if (
            "publication_launch_events" in m
            and int(state) == ref.MICRO_JOIN_TAIL_READ
            and trial < 6
        ):
            # Force both reset-bank launches from nonzero old state. Random
            # opcode sampling alone rarely reaches these selector continuations.
            values = {k: (1 << widths[k]) - 1 for k in state_keys}
            values.update(
                microstate=int(state),
                red2_fault=0,
                hw_fault=0,
                join_io_active=0,
                join_host_active=0,
                join_io_return_active=0,
                struct_selector_result_active=1,
                join_result_address=32,
                join_parent_address=12,
                fsp=35,
                promote_generation=0 if trial % 2 == 0 else (1 << 32) - 1,
            )
            opcode = [ref.MOP_STRUCT, ref.MOP_APP, ref.MOP_LAMBDA][trial // 2]
            response[0] = 700 if opcode == ref.MOP_STRUCT else 20
            kind = ref.DATA_LITERAL_ID if opcode == ref.MOP_STRUCT else ref.DATA_SIGNED
            response[1] = (1 << 26) | (opcode << 21) | (1 << 20) | (kind << 17)
            launch_witness = trial
        multiply_corner_witness = None
        if trial >= 120 + len(corners):
            multiply_corner_witness = trial - 120 - len(corners)
            values = {key: 0 for key in state_keys}
            values["microstate"] = int(state)
            values.update(products[multiply_corner_witness])
        if_ep_chase_witness = None
        if int(state) == ref.MICRO_JOIN_IF_EP_CHASE:
            from if_ep_chase import witness as if_ep_witness

            targeted = if_ep_witness(ref, widths, state_keys, trial)
            if targeted is not None:
                values, graph_response, if_ep_chase_witness = targeted
                response[:5] = graph_response
        original = sim_call(
            getattr(
                ref,
                "reference_"
                + next(
                    name.lower()
                    for name in m["scope"]
                    if getattr(ref, name) == int(state)
                ),
            ),
            typed_state(values),
            ref.red2_word_t(lo=response[0], hi=response[1]),
            ref.red2_control_t(lo=response[2], hi=response[3], tag_hi=response[4]),
            *sidecars(ref, m, response),
        )
        mem, request, cycles, trace = model(values, int(state), response)
        for key in state_keys:
            got = mem[slots[key]]
            wanted = nested_get(getattr(original.state, key.split(".")[0]), key)
            assert got == wanted, (state, trial, key, got, wanted)
        expect = [int(getattr(original, k)) for k in request_fields(m)]
        assert request == expect, (state, trial, "request", request, expect)
        candidates.append(
            {
                "values": values,
                "state": int(state),
                "response": response,
                "expected": {k: mem[slots[k]] for k in state_keys},
                "request": request,
                "rows_executed": cycles,
                "trace": trace,
            }
        )
        if launch_witness is not None:
            candidates[-1]["launch_witness"] = launch_witness
        if reverse_control_witness is not None:
            candidates[-1]["reverse_control_witness"] = reverse_control_witness
        if metadata_launch_witness is not None:
            candidates[-1]["metadata_launch_witness"] = metadata_launch_witness
        if integer_corner_witness is not None:
            candidates[-1]["integer_corner_witness"] = integer_corner_witness
        if multiply_corner_witness is not None:
            candidates[-1]["multiply_corner_witness"] = multiply_corner_witness
        if if_ep_chase_witness is not None:
            candidates[-1]["if_ep_chase_witness"] = if_ep_chase_witness
        typed_comparisons += 1
    covered = set()
    witnesses = []
    publication = "publication_reads" in m and (
        int(state) == ref.MICRO_PUB_EXEC
        or (
            m["publication_reads"].get("read_only") is False
            and int(state) == ref.MICRO_PUB_STACK
        )
    )
    core = "scalar_core" in m and int(state) == ref.MICRO_JOIN_SCALAR_LEFT_READ
    for _ in range(120 if publication or core else 6):
        best = max(candidates, key=lambda c: len(c["trace"] - covered))
        if best["trace"] <= covered:
            break
        covered |= best["trace"]
        selected = best.copy()
        selected.pop("trace")
        witnesses.append(selected)
    if publication and int(state) == ref.MICRO_PUB_EXEC:
        for kind in sorted({c["values"]["pub_current_task.kind"] for c in candidates}):
            if any(c["values"]["pub_current_task.kind"] == kind for c in witnesses):
                continue
            best = max(
                (c for c in candidates if c["values"]["pub_current_task.kind"] == kind),
                key=lambda c: (c["expected"]["red2_fault"] == 0, len(c["trace"])),
            )
            covered |= best["trace"]
            selected = best.copy()
            selected.pop("trace")
            witnesses.append(selected)
    if publication and m["publication_reads"].get("read_only") is False:
        # Branch coverage alone can choose a zero enable for an unconditional
        # packet assignment. Retain a positive witness for every observed bank
        # write, so read-first/lifecycle checks cannot silently lose that case.
        fields = request_fields(m)
        for bank, _ in m["publication_reads"]["banks"]:
            field = bank + "_write_enable"
            if field not in fields:
                continue
            index = fields.index(field)
            writes = [c for c in candidates if c["request"][index]]
            if writes and not any(w["request"][index] for w in witnesses):
                best = max(writes, key=lambda c: len(c["trace"]))
                covered |= best["trace"]
                selected = best.copy()
                selected.pop("trace")
                witnesses.append(selected)
    for candidate in candidates:
        if "if_ep_chase_witness" in candidate and not any(
            witness.get("if_ep_chase_witness") == candidate["if_ep_chase_witness"]
            for witness in witnesses
        ):
            covered |= candidate["trace"]
            selected = candidate.copy()
            selected.pop("trace")
            witnesses.append(selected)
        if "multiply_corner_witness" in candidate and not any(
            witness.get("multiply_corner_witness")
            == candidate["multiply_corner_witness"]
            for witness in witnesses
        ):
            covered |= candidate["trace"]
            selected = candidate.copy()
            selected.pop("trace")
            witnesses.append(selected)
        if "reverse_control_witness" in candidate:
            selected = candidate.copy()
            selected.pop("trace")
            if not any(
                w.get("reverse_control_witness") == selected["reverse_control_witness"]
                for w in witnesses
            ):
                covered |= candidate["trace"]
                witnesses.append(selected)
        if "integer_corner_witness" in candidate and not any(
            w.get("integer_corner_witness") == candidate["integer_corner_witness"]
            for w in witnesses
        ):
            covered |= candidate["trace"]
            selected = candidate.copy()
            selected.pop("trace")
            witnesses.append(selected)
        if "launch_witness" in candidate and not any(
            w.get("launch_witness") == candidate["launch_witness"] for w in witnesses
        ):
            covered |= candidate["trace"]
            selected = candidate.copy()
            selected.pop("trace")
            witnesses.append(selected)
        if "metadata_launch_witness" in candidate and not any(
            w.get("metadata_launch_witness") == candidate["metadata_launch_witness"]
            for w in witnesses
        ):
            covered |= candidate["trace"]
            selected = candidate.copy()
            selected.pop("trace")
            witnesses.append(selected)
    cases += witnesses
    coverage[state] = {
        "observed_rows": len(set().union(*(c["trace"] for c in candidates))),
        "hardware_witness_rows": len(covered),
        "hardware_witnesses": len(witnesses),
        "all_task_kinds_witnessed": publication,
    }
    print("CFG_TYPED_REFERENCE_PASS", state, flush=True)
if m.get("publication_reads", {}).get("read_only") is False:
    fields = request_fields(m)
    for bank, _ in m["publication_reads"]["banks"]:
        field = bank + "_write_enable"
        if field in fields:
            assert any(c["request"][fields.index(field)] for c in cases), field
(P / "native-cases.json").write_text(json.dumps(cases))
(P / "native-coverage.json").write_text(json.dumps(coverage, indent=2) + "\n")
print("CFG_TYPED_REFERENCE_ALL_PASS", typed_comparisons, flush=True)

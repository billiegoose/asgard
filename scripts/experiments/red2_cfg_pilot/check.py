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
                    "and": operator.and_,
                    "or": operator.or_,
                    "eq": operator.eq,
                    "ne": operator.ne,
                    "ge": operator.ge,
                }[name](a, b)
        mem[r["d"]] = int(v) & ((1 << r["width"]) - 1)
    else:
        raise AssertionError("control table did not halt")
    assert requests == 1
    return mem, request, len(trace), trace


rng = random.Random(203708309)
state_keys = [k for k in slots if k.split(".")[0] in regs]
cases = []
coverage = {}
for state in m["entry_pc"]:
    candidates = []
    for trial in range(120):
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
    covered = set()
    witnesses = []
    publication = "publication_reads" in m and (
        int(state) == ref.MICRO_PUB_EXEC
        or (
            m["publication_reads"].get("read_only") is False
            and int(state) == ref.MICRO_PUB_STACK
        )
    )
    for _ in range(120 if publication else 6):
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
    cases += witnesses
    coverage[state] = {
        "observed_rows": len(set().union(*(c["trace"] for c in candidates))),
        "hardware_witness_rows": len(covered),
        "hardware_witnesses": len(witnesses),
        "all_task_kinds_witnessed": publication,
    }
    print("CFG_TYPED_REFERENCE_PASS", state, flush=True)
(P / "native-cases.json").write_text(json.dumps(cases))
(P / "native-coverage.json").write_text(json.dumps(coverage, indent=2) + "\n")
print("CFG_TYPED_REFERENCE_ALL_PASS", len(m["entry_pc"]) * 120, flush=True)

"""Conservatively catalogue extra handlers usable with the graph/control adapter.

This is a discovery aid, not a correctness proof: generation, event/ownership
checks, typed and native parity and complete mapping are still required.
"""

import ast
import json
from collections import defaultdict

import build as c
from banks import inspect

allowed_calls = {"red2_word_t", "red2_control_t", "red2_u64_ge"}

ports, external_bank_effects = inspect(c)
reads = defaultdict(set)
for n in ast.walk(c.fn):
    if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
        reads[n.id].add(n.lineno)
records = []
for handler in c.fn.body:
    if not isinstance(handler, ast.If):
        continue
    test = ast.unparse(handler.test)
    if not test.startswith("clock_dispatch_enable and micro_is_"):
        continue
    short = test.split("micro_is_", 1)[1]
    name = "MICRO_" + short.upper()
    if name in c.selected or not short.startswith(("struct_", "join_")):
        continue
    req = c.requests.get(short, [])
    code = req + handler.body
    dependencies = set()
    visited = set()

    def need(alias, visited=visited, dependencies=dependencies):
        if alias not in c.aliases or alias in visited:
            return
        visited.add(alias)
        dependencies.add(alias)
        for n in ast.walk(c.aliases[alias].value):
            if isinstance(n, ast.Name):
                need(n.id)

    for statement in code:
        for n in ast.walk(statement):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                need(n.id)
    code += [c.aliases[k] for k in sorted(dependencies)]
    nodes = [n for statement in code for n in ast.walk(statement)]
    used_ports = sorted({n.id for n in nodes if isinstance(n, ast.Name)} & ports)
    used_ports = sorted(set(used_ports) | external_bank_effects.get(name, set()))
    calls = sorted(
        {
            ast.unparse(n.func)
            for n in nodes
            if isinstance(n, ast.Call) and ast.unparse(n.func) not in allowed_calls
        }
    )
    events = set()
    for n in ast.walk(handler):
        if (
            isinstance(n, ast.Name)
            and isinstance(n.ctx, ast.Store)
            and n.id not in c.regs
            and n.id != "clock_dispatch_handled"
            and n.id in c.aliases
            and isinstance(c.aliases[n.id].value, ast.Constant)
            and c.aliases[n.id].value.value == 0
            and any(line > handler.end_lineno for line in reads[n.id])
        ):
            events.add(n.id)
    late_requests = set()
    for n in ast.walk(handler):
        if isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for target in targets:
                while isinstance(target, ast.Attribute):
                    target = target.value
                if isinstance(target, ast.Name) and target.id in {
                    "memory_req",
                    "control_req",
                }:
                    late_requests.add(target.id)
    arithmetic = short.startswith("join_scalar_")
    records.append(
        {
            "state": name,
            "source_line": handler.lineno,
            "source_lines": handler.end_lineno - handler.lineno + 1,
            "additional_banks": used_ports,
            "unsupported_calls": calls,
            "external_events": sorted(events),
            "optional_arithmetic": arithmetic,
            "post_response_requests": sorted(late_requests),
            "candidate": not (
                used_ports or calls or events or arithmetic or late_requests
            ),
        }
    )
(c.OUT / "extension-catalogue.json").write_text(json.dumps(records, indent=2) + "\n")
print("EXTRA_STATE_CANDIDATES", sum(r["candidate"] for r in records), flush=True)
print(
    ",".join(r["state"] for r in records if r["candidate"]),
    flush=True,
)

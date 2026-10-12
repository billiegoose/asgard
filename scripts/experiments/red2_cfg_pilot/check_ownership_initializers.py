"""Check exact typed-zero proofs and lifecycle masks for private state."""

import ast

from ownership import prove_private


def proof(value, extra="", fields=None, constants=None):
    fn = ast.parse(
        "def hardware(command):\n"
        "    held: Reg[uint8_t]\n"
        "    task: Reg[task_t]\n"
        "    if command.op == CMD_RESET or command.op == CMD_LOAD_STATE:\n"
        "        held = 0\n"
        f"        task = {value}\n" + extra + "    return 0\n"
    ).body[0]
    m = {
        "state_ownership": {"held": {}, "task": {}},
        "slots": {"held": 0, "task.kind": 1, "task.address": 2},
        "widths": {"held": 8, "task.kind": 6, "task.address": 17},
        "lifecycle_structs": {
            "task_t": fields or {"kind": "uint6_t", "address": "uint17_t"}
        },
        "lifecycle_zero_constants": constants or ["NONE"],
    }
    return prove_private(fn, m)[1]


p = proof("task_t(kind=NONE, address=0)")
assert p["private_roots"] == ["held", "task"] and p["private_bits"] == 31
assert not p["initialize_on_start"]
extra = (
    "    if command.op == CMD_RESET or command.op == CMD_LOAD_STATE or "
    "(command.op == CMD_START and memory_address_in_range):\n"
    "        task = task_t(kind=0, address=0)\n"
)
p = proof("task_t(kind=NONE, address=0)", extra)
assert p["initialize_on_start"] == ["task.kind", "task.address"]
for value in (
    "task_t(kind=1, address=0)",
    "task_t(kind=UNKNOWN, address=0)",
    "task_t(kind=0)",
    "task_t(kind=0, address=0, extra=0)",
    "task_t(0, 0)",
    "other_t(kind=0, address=0)",
):
    assert proof(value)["private_roots"] == ["held"], value
assert proof("task_t(kind=0, address=0)", "    other = task\n")["private_roots"] == [
    "held"
]
fn = ast.parse("""def hardware(command):
    held: Reg[uint8_t]
    if command.op == CMD_RESET or command.op == CMD_LOAD_STATE:
        held = 0
    return 0
""").body[0]
pruned, _ = prove_private(
    fn, {"state_ownership": {"held": {}}, "slots": {"held": 0}, "widths": {"held": 8}}
)
assert not any(isinstance(n, (ast.If, ast.Pass)) for n in ast.walk(pruned))
print("OWNERSHIP_TYPED_INITIALIZERS_PASS 10", flush=True)

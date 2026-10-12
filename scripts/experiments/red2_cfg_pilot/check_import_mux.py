"""Exhaust selector codes across varied typed widths and nonzero payloads."""

import random

from import_mux import emit

rng = random.Random(784311)
for count in (0, 1, 7, 16, 162):
    slots = rng.sample(range(1024), count)
    fields = [(slot, f"v_{i}") for i, slot in enumerate(slots)]
    values = [rng.getrandbits(rng.randint(1, 64)) for _ in fields]
    functions = []
    for onehot in (False, True):
        namespace = {}
        text = (
            "def select(cfg_transfer_slot"
            + "".join(", " + name for _, name in fields)
            + "):\n"
        )
        text += "    cfg_setup_data = 0\n" + "".join(
            "    " + line + "\n" for line in emit(fields, onehot).splitlines()
        )
        text += "    return cfg_setup_data\n"
        exec(compile(text, "<typed import selector>", "exec"), namespace)
        functions.append(namespace["select"])
    for address in range(1024):
        wanted = values[slots.index(address)] if address in slots else 0
        assert all(f(address, *values) == wanted for f in functions)
try:
    emit([(1, "a"), (1, "b")], True)
except AssertionError:
    pass
else:
    raise AssertionError("accepted duplicate import selectors")
print("IMPORT_MUX_EXHAUSTIVE_CODES_PASS 5120", flush=True)

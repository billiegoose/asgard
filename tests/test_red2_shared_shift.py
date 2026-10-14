"""Check generated shared-shift expressions against independent integer shifts."""

import random
from textwrap import dedent
from types import SimpleNamespace

from scripts.experiments.red2_cfg_pilot.shared_shift import datapath


def test_shared_shift_all_distances_and_unsigned_boundaries():
    # Execute exactly the emitted expressions. A small uint64-like operand
    # supplies PipelineC's inclusive bit-slice syntax; arithmetic uses Python ints.
    class Bits(int):
        def __getitem__(self, key):
            return (int(self) >> key.stop) & ((1 << (key.start - key.stop + 1)) - 1)

    code = compile(dedent(datapath()), "shared_shift_datapath", "exec")
    mask = (1 << 64) - 1
    rng = random.Random(210183735787)
    values = [0, 1, mask, 1 << 63, (1 << 63) - 1]
    values += [rng.getrandbits(64) for _ in range(32)]
    distances = [*range(128), 1 << 32, 1 << 63, mask]
    for left in (False, True):
        for value in values:
            for distance in distances:
                scope = {
                    "a": Bits(value),
                    "b": Bits(distance),
                    "row": SimpleNamespace(op=int(left)),
                    "OP_shl": 1,
                    "uint64_t": int,
                }
                exec(code, scope)
                expected = (
                    ((value << distance) & mask if left else value >> distance)
                    if distance < 64
                    else 0
                )
                assert scope["shift_result"] == expected, (left, value, distance)

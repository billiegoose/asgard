# isort: skip_file
"""Compare source-inlined FLOAT bit/domain helpers with the pinned native types."""

import ast
import sys
from paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import run_syn  # noqa: F401 -- compiler/runtime bootstrap
import pipelinec_toolchain as tc
import pypeline as py
from synthesizable_red2_machine import machine as hw
from integer_joins import configure, inline, specialize

tree = ast.parse(
    (ROOT / "src/machines/synthesizable_red2_machine/machine.py").read_text()
)
floating = (tc.configured_root() / "include/pypeline/floating_point.py").read_text()
helpers, record = configure(tree, {}, floating)
unpack = compile(
    ast.fix_missing_locations(
        ast.Expression(
            inline(
                helpers["red2_float64_from_bits"],
                ast.Name(id="payload", ctx=ast.Load()),
            )
        )
    ),
    "<unpack>",
    "eval",
)
domain = compile(
    ast.fix_missing_locations(
        ast.Expression(
            inline(
                helpers["red2_float64_supported"], ast.Name(id="value", ctx=ast.Load())
            )
        )
    ),
    "<domain>",
    "eval",
)
count = 0
for sign in (0, 1):
    for exponent in (0, 1, 1023, 2046, 2047):
        for mantissa in (0, 1, (1 << 52) - 1):
            payload = hw.uint64_t((sign << 63) | (exponent << 52) | mantissa)
            value = eval(unpack, {"float64_t": hw.float64_t, "payload": payload})
            original = py.sim_call(hw.red2_float64_from_bits, payload)
            assert value == original
            assert bool(eval(domain, {"value": value})) == bool(
                py.sim_call(hw.red2_float64_supported, original)
            )
            count += 1
for body in (
    "if RED2_SYN_FLOAT:\n    forbidden_numeric_operation()\nelse:\n    result = 1\n",
    "value: float64_t = red2_float64_from_bits(bits)\n"
    "result = red2_float64_supported(value)\n",
):
    result = specialize(ast.parse(body).body, helpers)
    assert not any(
        isinstance(n, ast.Name) and n.id in set(helpers) | {"RED2_SYN_FLOAT"}
        for s in result
        for n in ast.walk(s)
    )
try:
    specialize(ast.parse("if RED2_SYN_FLOAT and flag:\n    value = 1\n").body, helpers)
except AssertionError:
    pass
else:
    raise AssertionError("accepted an unproved profile predicate")
print("INTEGER_JOIN_SOURCE_HELPERS_NATIVE_PASS", count, flush=True)

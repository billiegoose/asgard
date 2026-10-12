"""Regress lost launch assertions versus independently reused local names."""

import ast

from events import unbridged


def analyze(source, earliest):
    return unbridged(ast.parse(source), earliest)


assert analyze("flag = 0\nif flag:\n    result = 1\n", {"flag": 2})
assert not analyze("if other:\n    temp = data\n    result = temp\n", {"temp": 1})
assert analyze(
    "if other:\n    if condition:\n        temp = data\n    result = temp\n",
    {"temp": 1},
)
assert not analyze("result = flag\n", {"flag": 2})
assert not analyze(
    "if other:\n    if condition:\n        temp = a\n"
    "    else:\n        temp = b\n    result = temp\n",
    {"temp": 1},
)
print("LEGACY_EVENT_GUARD_PASS", 5, flush=True)

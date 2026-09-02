# RED2 Primitive-Register Scaffold and Passive Primitive Opcodes — Task 3

**Status:** Implemented — `argcnt`, `prim`, `fire` registers; `PRIM_0/1/2` opcodes; `_prim()` passive method; state/transition tests green.

**Plan:** `remaining-red2-slices-draft.md` (Task 3, depends on Task 2)

**Files modified:**
- `models/python/red2_engine/mured.py` (opcodes, state, load, step, _prim)
- `tests/test_mured_state.py` (register assertions)
- `tests/test_mured_transitions.py` (passive PRIM forward/reverse)

**Acceptance:** `uv run pytest tests/test_mured_state.py tests/test_mured_transitions.py -k prim` passes.

**Constraints:** Passive only (q=0/no-fire cases per chapter 4); no strict firing yet (Task 4).

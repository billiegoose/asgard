# A3 slice 3 — transactional closure materialization

## Status

Accepted for the A3 slice-3 scope.

The generic publication walker now supports the first allocation-producing publication case: narrow `CLOSURE` materialization. Closure code is materialized entirely into generation-tagged private scratch, validated as a complete allocation, and only then committed to graph memory. Existing-address patch-journal writes still commit before allocation rows, so the combined transaction remains failure-atomic.

## Implemented behavior

- `EP -> CLOSURE` inside the reclaim interval enters generic `PUB_TASK_CLOSURE` / `PUB_TASK_EP_RESULT` publication.
- Ordinary one-target JOIN `EP -> CLOSURE` is rerouted through the same generic publisher rather than the older direct closure copier, so direct, mixed, shared, overlap, and capacity cases use one allocation path.
- Closure memo rows use the existing generation-tagged root memo RAM:
  - `PUB_ROOT_RESERVED` marks an in-progress closure allocation and records its scratch base.
  - `PUB_ROOT_DONE` memoizes the allocated destination so repeated references allocate once.
  - Re-entering a same-generation reserved closure faults as an illegal cycle.
- The implemented narrow closure source format is:
  - valid `CLOSURE` with signed environment pointer;
  - following valid `NONE` code slot with signed code address;
  - one or more contiguous `LAMBDA` words;
  - a headed signed nonnegative `VAR` body.
- Lambda words are detached into private material scratch with head cleared.
- A local body `VAR` is copied into scratch and reheaded.
- A captured body `VAR` walks the closure environment and resolves only shareable atomics (`INT`, `FLOAT`, `CHAR`, undefined `SYM`).
- Environment walking follows `PNP` with the hardware graph-size hop bound and applies RED2 width stepping while skipping captures:
  - `REC`: +3 words;
  - `CLOSURE` or closure-slot marker: +2 words;
  - otherwise: +1 word.
- Material scratch rows are generation-tagged. Before any architectural allocation write, validation proves:
  - destination and final row are in graph range;
  - final row is strictly below `free_space`;
  - every expected scratch row belongs to the current generation and contains a valid word;
  - material `APP` pointers, when present, are nonnegative relative indices below the material count and relocate to an in-range absolute address.
- Commit ordering is transactional:
  1. validate the complete publication/materialization;
  2. complete JOIN continuation/scalar preflight;
  3. commit staged existing-address patch-journal rows;
  4. commit material allocation rows, relocating relative `APP` pointers at write time;
  5. advance `fsp` to the final allocated row;
  6. resume ordinary JOIN publication/restore.
- Because all source reads finish before material graph writes begin, source/destination overlap is safe.
- A destination whose last row is exactly `free_space - 1` succeeds; consuming `free_space` faults `FAULT_GRAPH_ENV_COLLISION` before graph/control mutation.

## Focused parity coverage

`scripts/check_syn_sim.py --generic-closure-materialization-only` covers:

1. Direct one-target closure allocation through the normal JOIN path.
2. Source/destination overlap with two lambdas (`20..22` materialized to `22..24`).
3. Exact-frontier success.
4. One-word overflow with failure-atomic graph/control state.
5. Two distinct EP roots sharing one closure target, forced through the generic multi-target walker, proving one allocation via closure memoization.

The existing full native parity suite additionally covers:

- captured integer closure body;
- local variable body;
- captured character plus lambda definition metadata;
- farther captured variable with environment stepping;
- PNP environment redirection;
- malformed/missing environment fault atomicity;
- malformed code-slot fault atomicity;
- PNP cycle reaching the exact 256-word hop bound;
- mixed transparent APP prefix plus closure allocation/retargeting;
- shared APP closure publication.

## Integration findings

No closure semantic defect was found after the generic reroute.

The first full-suite failures were stale test clock budgets inherited from the older direct closure copier. A captured closure now commits at clock 54 through the serialized generic task/scratch pipeline, beyond the helper's former 32-clock default. The self-referential PNP cycle reaches the expected `FAULT_ILLEGAL_TRANSITION` at clock 799, with graph and control state unchanged.

Only closure-bearing regression calls had their explicit bounds raised. The global `_run_encoded_to_same_commit` / `_run_encoded_to_same_fault` defaults remain unchanged, preserving tight bounds for unrelated tests.

A sampled full-suite run also showed steady forward progress through unrelated PRIM/FLOAT tests rather than a loop; the combined working tree simply exceeds the earlier 180-second wall-clock harness limit. With a realistic outer timeout, the complete native suite passes.

## Validation

Pinned PipelineC/Pypeline revision:

`171c52b3f1411f632a07ccfc3dbfb177efa901cd`

Validated gates:

- `python -m py_compile scripts/check_syn_sim.py src/machines/synthesizable_red2_machine/machine.py` -> PASS.
- `git diff --check -- scripts/check_syn_sim.py src/machines/synthesizable_red2_machine/machine.py` -> PASS.
- `.venv/bin/python -m pytest tests/test_synthesizable_red2_static.py -q` -> `9 passed`.
- Focused slice 2 native parity -> `PipelineC native RED2 generic EP patch-journal parity: PASS`.
- Focused slice 3 native parity -> `PipelineC native RED2 generic closure materialization parity: PASS`.
- Complete pinned native parity -> `PipelineC native RED2 first-slice parity: PASS`.

Final file hashes at acceptance:

- `src/machines/synthesizable_red2_machine/machine.py`: `4f86932af405ca4957083e54892d4892c1915b7df7840deebca3e0b1180fa0f8`
- `scripts/check_syn_sim.py`: `2c26560d32fe6b129671886d038898332db3f95af1faca9982460139344064ed`

Frontend/VHDL elaboration was not rerun specifically for slice 3 in this acceptance pass; do not infer a new frontend result from the native gates above. Slice 2's A3-only frontend evidence remains documented separately.

## Remaining generic-publication gaps

This slice intentionally implements only the existing narrow closure materializer as the first generic allocation producer. It does not yet provide the fully general material graph traversal planned for A4.

Notably:

- generic `EP -> REC` remains an explicit `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` gap;
- unsupported closure bodies beyond the narrow lambda-spine/VAR form remain explicit gaps;
- general allocation-producing graph publication belongs to A4 rather than expanding this slice ad hoc.

## Working-tree caution

Do not discard unrelated modifications in `src/machines/synthesizable_red2_machine/machine.py` or `scripts/check_syn_sim.py`; both files contain substantial work outside A3, especially `RED2_FLOAT_V1`. Other modified Concrete/test files are also unrelated working-tree state. No commit was made as part of this slice.

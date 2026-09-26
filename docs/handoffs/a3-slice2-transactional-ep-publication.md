# A3 slice 2 — transactional generic EP publication

## Status

Accepted for the A3 slice-2 scope.

The generic publication walker now supports transactional EP rewrites, including embedded EP descriptors reached through STRUCT publication. Existing-address rewrites are staged in a generation-tagged patch journal and are not written to architectural graph memory until generic publication and the later JOIN scalar preflight have both completed without fault.

## Implemented behavior

- Generic `PUB_TASK_EP_CHASE` follows EP chains with the hardware graph-size hop bound.
- Terminals outside the reclaim interval leave the descriptor untouched.
- Shareable atomic terminals rewrite the EP descriptor by cloning the terminal while preserving descriptor head metadata.
- UBV terminals rewrite to `VAR` for root EPs and `APP_VAR` for embedded EPs, using the captured launch `phi`.
- APP publication rewrites are journaled instead of written directly.
- Patch journal rows are generation-tagged and an address list records first writes per address.
- Journal commit occurs only after generic publication completes and JOIN continuation/scalar preflight is safe.
- Late faults therefore leave architectural graph and control state unchanged.
- Generic `STRUCT_SCAN` walks contiguous descriptors through signed `VAR 0`, reusing `PUB_GRAPH`, `APP_REWRITE`, and embedded `EP_CHASE` tasks.
- STRUCT task ordering is depth-first: target publication/chase runs before the continuation scan, matching Concrete RED2.

## Focused parity coverage

`scripts/check_syn_sim.py --generic-ep-patch-journal-only` covers:

1. EP -> shareable atomic rewrite.
2. EP -> UBV root rewrite.
3. Embedded STRUCT EP -> UBV rewrite to `APP_VAR`.
4. Outside-interval EP remains untouched.
5. Multiple APP descriptors sharing one EP descriptor.
6. Late invalid EP after an earlier staged patch, proving rollback/no publication leak.
7. EP cycle at the exact 256-word hardware hop bound.
8. Nested APP containing an EP target.

The focused native parity gate passes against Concrete RED2 using the pinned Pypeline checkout.

## Validation

Pinned PipelineC/Pypeline revision:

`171c52b3f1411f632a07ccfc3dbfb177efa901cd`

Validated gates:

- `python3 -m py_compile src/machines/synthesizable_red2_machine/machine.py scripts/check_syn_sim.py`
- `git diff --check -- src/machines/synthesizable_red2_machine/machine.py scripts/check_syn_sim.py`
- `uv run pytest -q tests/test_synthesizable_red2_static.py` -> 9 passed.
- Focused pinned native parity -> `PipelineC native RED2 generic EP patch-journal parity: PASS`.
- A3-only pinned frontend/VHDL elaboration -> PASS, emitted `SynthesizableRED2Machine_0CLK_80e55a1b.vhd`, 57,968,201 bytes.

### Frontend isolation note

The current working tree also contains a large unrelated `RED2_FLOAT_V1` implementation in the same machine file. Running the repository-wide `scripts/check_syn.py --frontend-only` on the combined tree first exposed two PipelineC synthetic-instance naming collisions in A3 compound comparisons; both were fixed by splitting those comparisons into typed intermediates, with focused native parity remaining green. After those fixes, full combined-tree frontend elaboration ran beyond the harness's 600-second limit without emitting VHDL.

To distinguish A3 correctness from unrelated FLOAT elaboration cost, an A3-only temporary source snapshot was constructed from `HEAD` plus only the generic-publication hunks, with FLOAT hunks excluded. That snapshot elaborated successfully on the exact pinned revision and emitted the VHDL top above. The repository itself was not replaced by or modified from that temporary snapshot.

## Remaining generic-publication gaps

This slice intentionally still leaves allocation-requiring EP terminals (`CLOSURE` / `REC`, and the corresponding `EP_RESULT` path) as explicit `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` gaps. Those belong to the next publication/allocation slice rather than this transactional existing-address rewrite slice.

## Working-tree caution

Do not discard unrelated modifications in `src/machines/synthesizable_red2_machine/machine.py` or `scripts/check_syn_sim.py`; both files contain work outside A3, especially `RED2_FLOAT_V1`. No commit was made as part of this slice.

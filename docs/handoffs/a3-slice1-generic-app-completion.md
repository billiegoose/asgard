# A3 slice 1 — generic APP publisher completion handoff

## Status

A3 slice 1 is implemented and validated on the current working tree.

The allocation-free generic publication walker now handles arbitrary APP target multiplicity and nested APP graphs using fixed scratch state, generation-tagged root memoization, and a serialized fixed task stack. It is entered only from the three reviewed reverse-JOIN fallback seams; existing specialized EP/closure/REC/STRUCT paths remain intact.

## Implemented substrate

`src/machines/synthesizable_red2_machine/machine.py` now contains:

- `MICRO_PUB_EXEC = 126` and `MICRO_PUB_STACK = 127`;
- the frozen future-compatible `red2_pub_task_t` and `red2_pub_root_t` rows;
- `PUB_TASK_GRAPH`, `ROOT_DONE`, `APP_SCAN`, `APP_REWRITE`, and `APP_OPERATOR_DONE`;
- one fixed 1024-entry task-stack RAM (`GRAPH_WORDS * 4`);
- one generation-tagged 256-entry root-memo RAM;
- a registered current task so architectural graph request routing does not depend combinationally on scratch-RAM output;
- serialized memo/task writes through the two-state publisher envelope;
- generation-zero reservation and explicit unsupported behavior on generation wrap;
- exactly three generic launch sites:
  1. third distinct APP target;
  2. one-target nested APP root;
  3. two-target nested APP root;
- success handoff back into the existing no-fail `MICRO_JOIN_PUBLISH` / control-clear tail.

The flat PipelineC dispatch remains flat; the static expected handled count is now 128.

## Architectural atomicity

While the generic walker runs it does not write architectural graph or control RAM and does not mutate the RED2 architectural transition state (`pc/fsp/env/control_top/q/phi/free_space/argcnt/prim_id/fire/s_a/s_d`). Scratch task/memo state may change freely and is invalidated by generation on the next launch.

`APP_REWRITE` remains deliberately allocation-free: if a child publication would return a different root, slice 1 stops at `HW_FAULT_EXECUTION_NOT_IMPLEMENTED` before architectural mutation. Descriptor patch journaling is the next A3 slice.

## Retired frozen gaps

The former A1 red witnesses for:

- three distinct APP targets; and
- nested APP target publication

are now ordinary Concrete parity regressions and pass through a committed JOIN transition.

The EP -> REC witness remains intentionally red at `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`; closure allocation/materialization remains later work.

## Slice-1 proof legs now covered

Native parity/regression coverage includes:

1. three distinct stable APP targets;
2. five distinct stable APP targets;
3. duplicate/shared root behavior through memoization;
4. nested APP with a child reusing an already-completed target;
5. one-target nested APP fallback specifically;
6. APP_VAR and non-head inline transparent-prefix entries on the generic path;
7. direct APP recursion -> `FAULT_ILLEGAL_TRANSITION` with graph/control unchanged;
8. late malformed target -> `FAULT_INVALID_ADDRESS` with graph/control unchanged;
9. the original nested/two-target fallback witness;
10. allocating closure targets remain explicit unsupported boundaries with no mutation.

The review requested a private task-stack overflow witness. For slice 1 this is structurally unreachable for a valid 256-word architectural graph: a conservative DFS bound is `3 * GRAPH_WORDS + 1 = 769` live tasks, below the fixed `4 * GRAPH_WORDS = 1024` task-stack capacity. The hardware overflow guard remains present and returns `FAULT_CONTROL_OVERFLOW`; later task families may make the guard reachable and should add a direct witness then.

## Validation evidence

Validated after the slice-1 implementation and regression expansion:

- native PipelineC/PyRTL RED2 parity: `PipelineC native RED2 first-slice parity: PASS`;
- focused Python/static suite: 145 tests pass;
- `python -m py_compile` for Synth machine and native parity script;
- `git diff --check` clean for the targeted files;
- pinned PipelineC revision: `171c52b3f1411f632a07ccfc3dbfb177efa901cd`;
- pinned PipelineC frontend + HDL: PASS;
- emitted VHDL: `SynthesizableRED2Machine_0CLK_e2daebc8.vhd`, 55,909,488 bytes;
- flat dispatch handled count: 128.

## Next planned slice

A3 slice 2 should add transactional existing-address rewrites before any allocation work:

- task IDs 6/7: `PUB_TASK_LAMBDA_SCAN`, `PUB_TASK_LAMBDA_DONE`;
- task IDs 8/9: `PUB_TASK_EP_CHASE`, `PUB_TASK_EP_RESULT`;
- generation-tagged descriptor patch scratch;
- a deterministic no-fail patch commit phase before the existing JOIN parent/control commit tail;
- APP descriptor retargeting when child publication changes root;
- EP -> shareable atomic;
- EP -> UBV (`VAR`/`APP_VAR` according to embedded mode);
- outside-publication-interval EP preservation;
- EP hop-limit/cycle fault parity;
- nested APP containing EP and repeated/shared EP descriptors;
- late EP failure after staged patches proving architectural atomicity.

Do not fold closure materialization or REC publication into that first transactional-journal slice. Closure materialization is A4 / the subsequent materialized-output slice; REC/RBLOCK rewriting is A5.

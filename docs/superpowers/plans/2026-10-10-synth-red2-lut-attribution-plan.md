# Synth RED2 LUT Attribution Plan

Goal: explain the remaining ~572k-LUT combinational footprint before attempting further optimization, and identify the smallest source-level regions responsible for it.

## Working hypothesis

V13–V20 removed or serialized several expensive arithmetic structures and reduced carry/DSP usage substantially, but LUT usage remains far above the Basys 3 XC7A35T budget. The next step is attribution, not another speculative rewrite. The leading hypothesis is that a large fraction of the remaining LUTs may be mux/decode/writeback fabric around the ~145-state microcoded machine rather than arithmetic itself.

## Phase 1 — hierarchy-preserved resource attribution

Run a diagnostic Xilinx synthesis of the current exact V20 machine without flattening hierarchy where possible. Produce hierarchy-aware cell/resource statistics so we can rank generated entities/functions by mapped cost.

Questions to answer:
- Is most mapped logic concentrated in the top RED2 machine entity?
- Which helper entities remain individually expensive?
- Are any supposedly shared helpers still replicated unexpectedly?

Desired outputs:
- hierarchy-preserved Yosys `stat -hierarchy` / Xilinx-oriented statistics
- machine-readable JSON where practical
- ranked entity/resource summary

## Phase 2 — pre-LUT coarse-cell composition

Inspect the design before final LUT mapping and aggregate RTLIL/Yosys cell kinds, especially:
- `$mux` / `$pmux`
- equality/comparison cells
- add/subtract
- multiply/divide-related cells
- reductions/boolean logic
- flip-flops
- memories

For muxes, measure not just count but approximate width × fan-in / total selected data bits. A small number of very wide, very high-fan-in muxes can dominate LUT usage.

Questions to answer:
- Is the remaining footprint primarily mux fabric or arithmetic?
- Which signals/structures have the largest selection networks?
- Does the ~145-way microstate dispatch produce giant next-state/writeback mux trees?

## Phase 3 — mapped-cell provenance

Use preserved hierarchy, cell names, and `src` attributes where available to aggregate mapped LUT/carry cells back to generated HDL locations and then to Pypeline source/state families.

Desired output:
- ranked list of source locations / generated entities by LUT contribution
- enough provenance to point at a small number of Python expressions or microstate families

## Phase 4 — diagnostic family bisection

Only after Phases 1–3, make temporary non-semantic diagnostic builds that cheaply stub whole families (publisher, equality, scalar math, STRUCT/selector, JOIN/dispatch, etc.) and compare mapped LUT deltas. These builds are a resource microscope, not candidate production changes.

Use binary-style narrowing until most of the footprint is attributable to a few source regions.

## Decision point

If arithmetic still dominates, continue extracting pure combinational islands and evaluate `AUTO_FSM` as an automated sharing/serialization mechanism.

If mux/decode/writeback fabric dominates, focus instead on FSM/control representation: localizing state, splitting sub-FSMs, reducing global register writeback fan-in, or changing how Pypeline lowers the machine.

## Guardrails

- Do not alter RED2 semantics during attribution.
- Preserve current dirty worktrees outside Asgard.
- Do not commit or push without explicit authorization.
- Keep V20 + framed scalar JOIN FSP fix as the baseline.
- Prefer reproducible machine-readable reports over eyeballing generated HDL.

## 2026-10-10 LUT-attribution findings

The V20+FSP-fix hierarchical `synth_xilinx -abc9 -arch xc7 -noiopad` netlist already exists at:

`../fpgatool/build/basys3/red2_probe_32_archsync_wait_v20floorfspfix_frontend/top/top_v20floorfspfix_noflat_hierarchical.json`

Measured mapped resources:

- 572,195 LUTs total
- 536,863 LUT3
- 26,594 LUT2
- 4,223 LUT4
- 1,083 LUT5
- 3,432 LUT6
- 12,766 FF
- 6,796 CARRY4
- 44 DSP48
- 18 RAMB18 + 7 RAMB36 = 16 BRAM36-equivalent

The dominant cause is now identified: **conditional mux fabric**.

- 19,493 generated `MUX_*` instances account for 521,818 LUTs, about 91.2% of all LUTs.
- Largest aggregate mux families:
  - `red2_word_t` (128-bit): 193,408 LUTs across 1,511 instances
  - `uint64_t`: 106,880 LUTs across 1,670 instances
  - `uint32_t`: 49,600 LUTs across 1,550 instances
  - `uint17_t`: 43,129 LUTs across 2,537 instances
  - `uint16_t`: 43,072 LUTs across 2,692 instances
  - `red2_pub_task_t`: 30,276 LUTs across 261 instances
- Arithmetic helpers are comparatively small. For example, the largest individual floating-point helper is only a few thousand LUTs. The previous V12-V20 helper serialization work was real but is no longer the dominant opportunity.

The important structural observation is that Pypeline appears to merge a very large live variable environment at each Python `if`/`elif`, not just values actually assigned by that branch. Examples:

- line 3110, `if command.op == CMD_RESET:` -> 309 muxes / 9,695 LUTs
- lines 3424/3429/3434/3439 command `elif` arms -> each ~309 muxes / 9,695 LUTs
- line 3996, `elif command.op == CMD_CLOCK:` -> 307 muxes / 9,615 LUTs
- line 4175, `if not clock_dispatch_handled and micro_is_execute:` -> 119 muxes / 2,951 LUTs
- line 8024, JOIN tail dispatch -> 81 muxes / 2,243 LUTs
- line 9639, scalar/equality dispatch -> 91 muxes / 2,702 LUTs

Instance names prove unrelated state is selected at outer conditionals. For example, the RESET branch produces muxes for `ep_publish_word`, equality scratch words, JOIN scratch words, publication scratch words, float-divider state, and many other values even though RESET does not semantically update all of them. Nested conditionals repeat the same pattern with the live environment applicable at that point.

Working hypothesis: this is primarily a Pypeline conditional/SSA branch-merge issue. If branch merging can be restricted to values actually modified in either arm (plus values whose dataflow genuinely differs), most of the 521,818 mux LUTs may disappear without changing RED2 semantics. This is potentially a much larger win than further hand-serializing arithmetic.

Next step: inspect Pypeline's `ast.If` elaboration / branch environment merge implementation, identify why untouched variables receive MUXes, and test a minimal reproducer before changing RED2 source structure.

## 2026-10-10 compiler-control-flow findings

### Root cause confirmed
Hierarchy-preserved mapped synthesis showed the V20+FSP-fix design at 572,195 LUTs, of which 521,818 LUTs (~91.2%) were generated `MUX_*` child modules. Arithmetic serialization was no longer the dominant lever.

Pypeline lowers Python `elif` as recursively nested binary `if`s. For distinct destinations this creates triangular re-selection: an N-arm chain produces N(N+1)/2 data muxes because every outer merge re-muxes values written by later arms. Minimal reproducer: N=16 distinct-register `elif` = 136 muxes; independent `if`s = 16.

### Equality-only experiment
An isolated `/tmp/pipelinec-red2-elif-opt` compiler recognized proven mutually-exclusive `selector == constant` chains and emitted independent arms. Safety guards reject equal-valued aliases and selector mutation; final-else support uses unique generated AST locations.

Real RED2 frontend:
- machine VHDL: 102,316,592 -> 67,840,876 bytes (-33.70%)
- generated MUX instances: 19,503 -> 17,773 (-8.87%)

Mapped synthesis:
- LUT: 572,195 -> 515,208 (-56,987, -9.96%)
- mux LUT: 521,818 -> 464,686
- DSP/BRAM essentially unchanged.

### General priority-elif experiment
A second isolated compiler `/tmp/pipelinec-red2-general-elif` flattens multi-arm runtime `if/elif[/else]` chains whose conditions are conservatively side-effect-free. It preserves Python priority with residual clock-enable wires, elaborates every branch from the same pre-chain value snapshot, unions driven reference paths using the existing struct/array coverage reducer, and merges each destination only across branches that actually write it.

Mixed-condition minimal reproducer, distinct destinations:
- N=16 no else: 136 -> 47 total muxes (includes ~2 one-bit CE muxes/condition)
- N=16 with else: 152 -> 49
Growth is linear instead of triangular. Call-containing tests conservatively fall back to the original lowering.

Real RED2 frontend:
- generated machine VHDL: 102,316,592 -> 54,897,358 bytes
- MUX instances: 19,503 -> 13,824 (-29.12%)

Hierarchy-preserved mapped synthesis, same `synth_xilinx -abc9 -arch xc7 -noiopad` flow:
- LUT: 572,195 -> 322,935 (-249,260, -43.56%)
- mux LUT: 521,818 -> 272,207 (-249,611)
- LUT3: 536,863 -> 287,603
- FF: 12,766 -> 11,419
- CARRY4: 6,796 -> 6,796
- DSP48E1: 44 -> 44
- RAMB18E1: 18 -> 18
- RAMB36E1: 7 -> 7
- estimated LCs: 296,341
- still ~15.53x the Basys 3's ~20.8k LUT budget.

Representative formerly-triangular chains collapse strongly in generated HDL: line 4181 118->4 mux instances; 8069 78->4; 9641 90->21; 9750 32->6; 14011 20->4.

This establishes compiler-level control-flow lowering, not arithmetic helpers or Yosys flattening, as the major area lever. Global Yosys flattening remains impractical: the earlier flat experiment exposed ~1.16M AND gates to ABC9 and timed out.

### Current safety gate before further area work
Do not merge this compiler experiment into the real PipelineC checkout yet. First validate semantic parity through Pypeline simulation / RED2 lockstep and relevant PipelineC regression tests, especially priority behavior, branch-body state writes, partial struct/array writes, final else, and fallback for stateful condition expressions.

## 2026-10-11 clock-dispatch continuation

Continued the isolated experiment in `/tmp/asgard-fourway/clock-dispatch`.
The exact incoming source is the earlier `idiomatic-last/inputs/scalar/machine.py`
candidate (SHA-256 `e1bdf1e94ee4fe931bed9a9b5021d7fa655c469e1733de1fb1b6af70d03f2bd6`).
Its mapped baseline is `../fpgatool/build/asgard-idiomatic-last/scalar/`.

The applied source moves the individual microstate handlers outside the outer
`CMD_CLOCK` conditional. Their shared dispatch enable defaults to zero, then is
enabled only by a clock command after fault and synchronous-read arbitration.
The commit predicate also defaults to zero, and the shared promotion completion
and illegal-transition fallback have explicit clock guards. This removes a
second selection of nearly every persistent register at the outer clock boundary.

Same isolated `patched_control` compiler and hierarchy-preserving
`synth_xilinx -abc9 -arch xc7 -noiopad` recipe:

| Measurement | Incoming source | Clock unwrap |
| --- | ---: | ---: |
| Hierarchical LUTs | 278,039 | 268,129 |
| Mapped mux LUTs | 240,887 | 230,968 |
| Machine VHDL mux instances | 11,165 | 10,854 |
| Machine VHDL bytes | 47,807,319 | 46,809,223 |
| Outer clock conditional mux LUTs | 9,934 | 15 |

Net reduction: **9,910 LUTs (3.56%)**. The remaining largest machine-source
boundary is the combined RESET/LOAD_STATE/START initializer at line 3112
(6,378 mux LUTs), followed by scalar dispatch (2,702). Helper source line
numbers in generated module names belong to their helper files; they must not
be interpreted as RED2 machine source lines.

Applied source SHA-256:
`885b757199b5759dfa5e5ead959ad29f519bacf9797585307eaef83fcd3b9a81`.
Mapped output: `../fpgatool/build/asgard-clock-dispatch/clock_unwrap/`.
Detailed source attribution: `/tmp/asgard-fourway/clock-dispatch/results/mux-source-lines.json`.
The diagnostic uses 11,419 FF, 44 DSP48, 6,773 CARRY4 and 18 RAMB18 + 7 RAMB36
(16 BRAM36-equivalent). An earlier report incorrectly expanded primitive
simulation blackboxes and reported zero FF/BRAM; `scripts/yosys_resources.py`
corrects that accounting. Distributed RAM adds 330 LUTs to the 268,129 logic
LUTs, for 268,459 total. These are capacity measurements, not a complete routed
FPGA implementation or a claim that the design fits the Basys 3.

Validation:

- Frontend emitted all 320 VHDL files; mapped synthesis reported zero problems.
- Structural reconstruction matches the entire incoming AST, including all 237
  clock-body statements, after undoing only the intended declaration/guard moves.
  Script: `/tmp/asgard-fourway/clock-dispatch/check_clock_ast.py`.
- 5,220 native non-clock traces match byte-for-byte across all defined
  microstates plus invalid state 255, both synchronous-read-pending values, both
  clear/latched fault states, and all nine non-clock commands. Each trace records
  the response and every processor register. Both trace files have SHA-256
  `a1d5f94df828ec3e664ef0e500d2cac4f50c4ab3ca4f03ad8d76d24b21574aa2`.
  Script: `/tmp/asgard-fourway/clock-dispatch/check_command_parity.py`.
- Ordinary suite: 1,209 passed, 3 deselected, with one static failure caused by
  expecting the moved commit snapshot to remain an annotated assignment. The
  static check now accepts declarations and assignments separately and checks
  for long dispatch chains at every indentation depth. All 11 static tests pass
  against the final source. The prior three test exclusions remain unchanged.
- Native generic EP patch-journal, generic closure materialization, and framed
  FLOOR/CEILING FSP regression checks pass.
- The full native first-slice gate remains blocked by pre-existing exact
  three-clock commit assertions: both incoming and candidate source fail at
  `check_syn_sim.py:297` via the same call at line 1368. A temporary run using
  the existing bounded-commit helper proceeds further, then encounters another
  exact-three-clock assertion at line 1444. No full native-gate success is claimed.

No compiler checkout was modified, and no commit or push was made.


## Basys 3 continuation and architecture boundary (2026-10-11)

The user confirmed dedicated RED2 hardware, with latency traded for area. A CPU
running a RED2 firmware interpreter is excluded. Application, graph creation,
and graph access belong in the reducer. Arithmetic and devices (including the
language's UART/CLOCK services) should become optional hardware modules. The
FPGA clock and reducer step command remain part of the hardware protocol.

The intended module boundary is an operation request and response with explicit
valid/ready handshakes. The core resolves arguments, owns graph/control RAM and
architectural state, and publishes a contraction only after the module returns a
checked result. A busy module stalls the same RED2 transition; it must not cause
an extra architectural commit. Unsupported optional operations report an
explicit fault. Device effects continue through the existing suspend/resume
boundary. This is a design target, not an implemented interface in this change.

### Compiler identity

Experiments explicitly select `/tmp/asgard-fourway/compilers/patched_control`.
It contains the priority/branch-merge enhancement absent from the older pinned
checkout. Its `pypeline.py`, `AUTO_FSM.py`, `AUTO.py`, and `AUTO_PIPELINE.py` match
`../PipelineC`; `PY_TO_LOGIC.py` additionally contains the isolated branch patch.
The measured compiler was installed as `build/pipelinec-enhanced` in both simulation and the
explicit lowering gate. `python scripts/setup_pipelinec.py` exports base revision
`d991e1f931a2303e3daa4f6256755f3ab47dd9c3` from the sibling PipelineC Git database
and applies `pypeline-boolop-instance-names.patch` followed by
`pypeline-red2-enhancements.patch` from the pinned
`tools/fpgatool/toolchain/patches/` submodule directory. This split reproduces the
former combined patch exactly. Nine compiler
and operator files are fingerprinted in `tools/pipelinec/manifest.json`, including
the software comparison replacement. These are the same production compiler
files used by the isolated experiments. The working sibling checkout is not
modified. An older or mismatched `PIPELINEC_ROOT` fails explicitly. The gate no
longer discovers arbitrary frontend executables on PATH.

The default compiler was subsequently upgraded to upstream
`2fe880d19852b8df0df1aae00f469c8be6fe8ce1` with the ported patch pair at fpgatool
`8356f4c`. Its installation path is `build/pipelinec-enhanced-<manifest-hash>` so
upgrades preserve the previous compiler. The new compiler emits the full RED2
top and passes a 31-row native/VHDL trace comparison covering priority, enables,
aggregate writes, BoolOp naming, and signed/mixed-width software comparisons.
The measured manifest is retained in the resource handoff JSON. Historical
counts below retain their original compiler and source provenance; the current
compiler remeasurement is recorded at the end of this document.
Upgrade validation completed: the monolithic native parity suite passed, as did
1,213 ordinary tests (the same three environment-dependent exclusions), focused
RECP/Fibonacci/selector checks, and analysis of all 320 emitted VHDL files by NVC.
Removing generated BoolOp instance tagging reproduced the regression's expected
duplicate `BIN_OP_NEQ` instance error.

### Experiments and accounting

Artifacts are isolated in `/tmp/asgard-lut-fit`. Primitive blackboxes must be
counted as leaves, and LUT RAM must be included. The hierarchy-preserved pre-repair
source uses 268,459 total LUTs (268,129 logic + 330 RAM), 11,419 FF, 44 DSP48,
6,773 CARRY4, and 16 BRAM36-equivalent. Basys 3 limits are 20,800 LUT, 41,600 FF,
90 DSP48, 5,200 CARRY4 and 50 BRAM36-equivalent. These are resource capacities;
fit still requires the board wrapper, routing and timing.

Flattening is essential for fair area estimates. The whole flattened design's
ABC-only fast pass has 82,623 LUT nodes; `strash; dc2; if -a -K 6` reduces that
to 53,892 before final LUT/FF cleanup. These are not final board resource totals.
The initial long ABC9 run exited 137 without a result. The full classic default
ABC run was stopped after its slow mapping stage; saved input BLIF permits the
fixed, faster area recipe above. No successful result is inferred from either
unfinished run.

A RAM-free whole-transition AUTO_FSM probe found 17,746 operations, 180 shared
units, 3,342 states, and 39,235 internal register bits before adding the existing
machine state. This plain greedy schedule is a diagnostic; it has neither a RAM
adapter nor an implemented replacement core and is not a fit candidate.

A conservative state-implication experiment packed 263 microstate mux chains
(32,594 mux bits). Independent Yosys SAT, with all stored values exposed as
unconstrained inputs, proved all proposed selector groups mutually exclusive:
5,645 cells, 79,205 variables, 180,656 clauses, SUCCESS. The fast completed map
uses 94,228 total LUT, 9,193 FF, 32 DSP48, 3,772 CARRY4 and 15.5 BRAM36-equivalent.
It does not fit, and is not adopted. An area-oriented map is also being compared.
A broader phase experiment packs 530 groups / 45,260 mux bits; that variant is
not yet mapped or formally checked and must not be described as validated.

Floating-point helper roots account for 21,975 logic LUT and 12 DSP in the
hierarchy-preserved netlist, with nested helper costs counted only once. This
excludes float state/control costs and does not predict the flattened savings.
`float-attribution.json` and `helper-attribution.json` contain the breakdown.

`core-equality-probe/` is a scalar-family bisection, not a production core. It
retains application, structure creation/access, structural equality, and the
serial divider's RECP resume path. The latter divides a reconstruction offset by
three and cannot be deleted merely because language-level DIV is optional.
Both normal and EP scalar preflight retain the structural-EQUAL launch. Other
scalar arithmetic is replaced by an explicit unsupported-value fault. This
measurement is intended to separate optional arithmetic from core area before
committing to a hardware interface implementation.


### Completed flattened area maps and RECP isolation

The original fixed area recipe is complete: the pre-repair source used **50,287 total
LUTs** (49,969 logic + 318 RAM), 9,193 FF, 32 DSP48, 3,780 CARRY4 and 15.5
BRAM36-equivalent. This is a synthesis estimate, not placement/routing or a board
bitstream. It remains 29,487 LUTs over capacity. The hierarchy-preserved 268,459
number above is a different mapping recipe and must not be presented as the same
measurement or as an architectural area reduction.

The scalar-family bisection maps to **38,117 total LUTs**, 8,345 FF, zero DSP48,
2,855 CARRY4 and 15.5 BRAM36-equivalent under the same flattened area recipe.
Arithmetic accounts for 12,170 LUTs in this diagnostic comparison; removing it
alone does not fit the core. Its unsupported-operation faults are diagnostic,
not a completed pluggable arithmetic implementation. The SAT-proven microstate
mux packing maps to 65,113 total LUTs under the area recipe, worse than the
50,287 production baseline, so it remains rejected.

RECP reconstruction divides a selected arena offset by three. A staged variant
replaces its general 64-cycle division launch with a bounded constant circuit:
`GRAPH_ADDR_BITS + 2` input bits, 3-bit partial remainder, explicit high-bit
rejection, then the existing count/remainder checks. Context, wrapped-address,
RUP-count, and fault-priority guards remain before this step. All 1,024 inputs
at the default arena size match Python divmod; both the baseline and candidate
pass the existing 132 RECP witness statements and checkpoint assertions. The
variant is still staged pending area comparison. It has not replaced production
hardware or established Basys 3 fit.

The native parity checker now has a reproducible `--recp-only` entry point.
Its witness extraction was checked AST-identical; the full suite still calls
it. Older exact/short cycle budgets have been replaced where they prevented
existing serialized RAM scans/division from reaching their checked outcomes.
Bounds remain finite and failure to commit/fault remains a test failure.
Fourteen static/resource tests pass; the full native suite is still running and
must not be reported as passed until its final result appears.


### Compiler default and native semantic repair

The reproducible enhanced compiler setup is installed and its default runtime
origin was checked. The older pinned checkout is rejected by file fingerprint.
The ordinary test run completed with 1,213 passes; the three environment/interactive
cases excluded in the earlier run remain excluded. Fourteen static/resource
checks also pass after the hardware repair below.

The native suite reached a selector scan's obsolete 160-clock limit. The corrected
bounded scan uses the configured arena and metadata sizes. Focused execution of
all remaining selector/RBLOCK witnesses (265 statements) then exposed a real
semantic defect: the shared promotion reset included validation completion and
cleared `promote_mat_count`. Publication consequently advanced past the valid
materialized rows and faulted. Validation completion now only resets its write
index and validate flag, preserving the count. The complete selector/RBLOCK tail
passes with its source assertions and actual finite budgets. The two shared-APP
and reset-generation cases also have an AST-identical standalone entry point,
`python scripts/check_syn_sim.py --selector-shared-app-only`, and pass.

`--fibonacci-only` likewise retains the existing milestone's four statements and
passes, including per-commit graph/control mutation checks and full final RAM
comparison. RECP's standalone check also passes. The subsequent compiler upgrade
validation also passed a full post-repair monolithic native parity invocation.
The corrected production source is staged in `validation-fixed/`; its frontend
completed using the verified default compiler. Earlier area numbers above refer
to the snapshot before this repair, not a mapped result of the corrected source.

The constant RECP divider maps to 50,452 total LUTs, 165 more than its matching
50,287 baseline. It is not adopted as an area optimization; decoupling RECP from
the optional general arithmetic unit remains a useful module-design direction.

An exclusive-dispatch candidate groups the **143** incoming-state handlers into
one elif chain, using the enhanced compiler's branch merging. It moves only the
promotion default-zero flag and shared completion around that chain. Handler
bodies are AST-identical; all 256 state encodings select at most one handler.
Baseline and candidate produce identical full register/response traces for 1,024
clock cases (every encoding, pending-read 0/1, fault 0/illegal), SHA256
`25f9d19eeca2b32101f501d9b11ab434f5587a5bd7c4aa8c372d5b7bcc74b78f`.
The completed area map uses 50,933 total LUTs, 646 more than the matching
50,287 baseline, despite reducing CARRY4 from 3,780 to 2,959 and FF from 9,193 to
9,160. It is rejected as an area optimization. This pair predates the validation-
reset repair; no area of the corrected production source is inferred from it.

The whole-transition area sweep and both aggressive Yosys-sharing probes were
stopped without completed resource results when the dispatch experiment was
prioritized. No successful area reduction is inferred from these unfinished jobs.
An additional endpoint-cone attribution accounts for all 49,969 mapped logic
LUTs with no unobserved LUTs; 29,657 feed multiple endpoint groups. Its exclusive
cone counts are attribution, not predicted removal savings, and RAM endpoint-name
classification needs inspection before making per-bank claims.


All experiments started in this phase have completed or were explicitly stopped.
Dedicated RED2 hardware remains the required architecture, and fitting it on
Basys 3 remains unfinished.

### Current compiler and corrected-source remeasurement (2026-10-11)

The current source (`236db38a5d4ded9356845e3bce80b2909fa0de6299b265b9d9c819d8ef4106fe`)
was mapped with upstream PipelineC `2fe880d` plus the enhanced patch pair pinned
by fpgatool `8356f4c`. The validated 320-file HDL emission was reused after compiler
fingerprint verification. Source and HDL hashes remained unchanged during mapping.
The run reused the previous Yosys 0.67 and GHDL plugin store paths, flattening
passes, Xilinx mapping script and `strash; dc2; if -a` ABC script.

| Resource | Historical baseline | Current source/compiler | Basys 3 capacity |
| --- | ---: | ---: | ---: |
| Logic LUTs | 49,969 | 50,035 | Shared LUT capacity |
| LUT RAM | 318 | 318 | Shared LUT capacity |
| Total LUTs | 50,287 | **50,353** | 20,800 |
| Flip-flops | 9,193 | 9,193 | 41,600 |
| BRAM36 equivalent | 15.5 | 15.5 | 50 |
| DSP48 | 32 | 32 | 90 |
| CARRY4 | 3,780 | 3,780 | 5,200 |

The total increased by 66 LUTs (0.13%). Both the promotion validation-reset repair
and compiler pin changed, so this is not a compiler-only comparison. The current
design remains **29,553 LUTs over capacity**, requiring a 58.69% reduction from
this total. LUT capacity is the only exceeded resource limit. Yosys structural
checks reported zero problems, and all primitives are accounted for. Independent
counts of top-level logic LUT and LUT RAM instances match the resource counter.
These are synthesis estimates for the RED2 top, without the board wrapper;
placement, routing and timing have not been verified.

Full resources and reproducible provenance are in
`docs/handoffs/synth-red2-upstream-lut-results.json`; intermediate netlists, input
snapshots and scripts are in `/tmp/asgard-pipelinec-remeasure`. The baseline
handoff retains the historical experiments and links the current measurement.

### Optional floating arithmetic and shared multiplier experiments

Further experiments use the 50,353-LUT full-arithmetic map above as their
baseline. The source still contained floating arithmetic hardware. The user had
already accepted omitting it, so it is now an explicit compile-time option:
hardware defaults to `RED2_SYN_FLOAT=0`; `RED2_SYN_FLOAT=1` restores the original
full arithmetic implementation. The native `syn` CLI and direct full parity
suite retain their previous floating-point mode by default. The synthesis gate
selects the profile-specific native checks.

| Measurement | Full arithmetic | Shared serial integer MUL | Floating arithmetic omitted |
| --- | ---: | ---: | ---: |
| Total LUTs | 50,353 | 50,709 | **41,705** |
| Logic LUTs | 50,035 | 50,391 | 41,387 |
| LUT RAM | 318 | 318 | 318 |
| Flip-flops | 9,193 | 9,193 | 8,676 |
| DSP48 | 32 | 12 | 20 |
| CARRY4 | 3,780 | 3,758 | 3,185 |
| BRAM36 equivalent | 15.5 | 15.5 | 15.5 |

The serial multiplier reuses the divider scratch bank for 64 shift/add clocks,
with two new microstates and no new persistent registers. It replaces both
integer multiplication sites, including exponentiation, while retaining the
existing overflow preflight. The full native parity suite passed with finite
arithmetic clock budgets increased for the additional latency. It saves 20 DSPs
but costs **356 more LUTs**, so it is rejected. The parallel multipliers were
already efficient DSP implementations; extra sequencing and muxes outweigh the
LUT savings. The isolated candidate and its validation wrapper remain available
under `/tmp/asgard-area-next/serial-mul/`.

Omitting floating arithmetic saves **8,648 LUTs (17.2%)**. This profile preserves
integer operations, raw FLOAT transport through graph operations, type predicates,
structural equality and scalar FLOAT `=`. Requests requiring the omitted module
fault explicitly with `FAULT_UNSUPPORTED_VALUE`, including inexact integer DIV
and the negative-EXPT reciprocal path. It does not approximate those results.
Existing EVEN?/MOD applicability behavior on FLOAT operands remains intact.
Graph construction/access, application, publication and the architectural
command/status protocol are unchanged.

Production source regeneration emitted **211 VHDL files byte-identical** to the
mapped candidate. The candidate was explicitly built with FLOAT=0; production
now defaults to that value. Removing only the static feature guards recovers the
baseline processor body AST exactly, retaining the enabled module's implementation.
Validation passed 15 program lockstep cases, five unsupported-operation cases
with complete architectural and graph/control RAM preservation, RECP, shared-APP
selector promotion, generic publication journal, closure materialization and
Fibonacci. The production runner repeats these checks. Floating-enabled framed
FLOOR/CEILING regression checks also pass. Ordinary validation reports 1,213
passed with the same three environment-dependent exclusions, plus three new
profile-selection tests. Both mapped designs reported zero structural problems;
independent logic LUT/LUT RAM counts match the resource counter.

The hardware default remains **20,905 LUTs over capacity**, about 2.005 times the
Basys 3 limit. No routing or timing result is claimed. The smaller profile still
contains 371 coarse 17/18-bit add/sub operators (6,520 output bits before Xilinx
cleanup). These counts are not predicted LUT savings. The next core candidate
is a shared graph-address ALU with BRAM-backed scratch storage and RED2-specific
sequencing, starting with address/request/writeback logic. The multiplier result
shows why its operand mux and sequencing costs must be measured as part of the
candidate. This remains a dedicated RED2 hardware engine, without a separate CPU.

Resources, compiler/source hashes, build flags, production HDL comparison and
validation records are in `docs/handoffs/synth-red2-area-next-results.json`.
Experiment netlists, scripts and snapshots are in `/tmp/asgard-area-next/`.


### Graph/control RAM write-data selection (2026-10-12)

The next accepted change combines enabled graph/control write-data contributions
from mutually exclusive incoming microstates. Address selection, write enables,
intra-handler priority and non-clock loader/resume writes retain their original
arbitration. Disabled RAM write data becomes zero. Every graph/control data bit,
including reserved upper bits, is retained; no arithmetic operation or RED2 rule
is removed, and no latency is added.

The same flattened backend maps this source to **41,170 total LUTs** (40,852 logic
plus 318 RAM), saving **535 LUTs (1.28%)** from the 41,705-LUT hardware default.
FF remain 8,676, DSP 20, CARRY4 3,185, and BRAM36-equivalent 15.5. Only LUT capacity
is exceeded: the core remains 20,370 LUTs above Basys 3 capacity. This is a
synthesis estimate, without a board wrapper or routing/timing verification.

Validation passed the complete floating-enabled native parity suite, the complete
integer-profile gate (15 lockstep programs, five failure-atomic unsupported
programs, RECP, shared-APP selector, publication journal, closure materialization
and Fibonacci), and 48 targeted repository tests. Reversing only the write-data
transform restores the entire original processor AST exactly. All 55 request
groups are disjoint for every microstate and publication phase: 8,192 cases over
the two ports. Every clock write-enable belongs to a checked group. All 212 HDL
file hashes match the mapped inputs, and production source matches the candidate.
Independent primitive counts agree with the resource counter; synthesis reports
zero structural problems.

The record is `docs/handoffs/synth-red2-bus-area-results.json`; raw artifacts,
transformation/proof scripts and the patch are in
`/tmp/asgard-area-next/onehot-ram-write/`. Further isolated experiments test
entry-state register snapshots and bounded SAT-based sharing of 17/18-bit address
operators. Most automatic sharing candidates form combinational loops and roll
back; this is evidence of false dependencies between inactive state handlers,
not evidence of an area saving. The snapshot trial targets those dependencies
while preserving the original independent handler guards and bodies. Its
integer-profile gate passes. The completed measurements follow below.

### Sharing and storage follow-up (2026-10-12)

The maintained source remains commit `93cce5e`, **41,170 total LUTs**. Three
isolated experiments completed against that exact source:

| Experiment | Total LUTs | Change | Decision |
| --- | ---: | ---: | --- |
| Entry snapshots plus accepted RAM bus | 43,017 | +1,847 | Reject |
| 16 bounded address add/sub merges | 41,151 | -19 | Keep diagnostic only |
| Weighted LUT1..8 cut library | 42,861 | +1,691 | Reject |

The snapshot candidate passes full native parity, the integer-profile suite,
and reversal of its AST transform. It removes 151 coarse add/sub cells and 989
muxes, and saves 826 CARRY4s, but increases mapped LUTs. Arithmetic/operator
counts alone are therefore insufficient evidence of an area improvement.

The installed Yosys `share` pass has a merge-limit bug: its loop tests the
unchanged `config.limit` while successful merges decrement local `limit`. An
isolated plugin fixes only that condition and changes the pass name. Across
limits 0/1/2/3, the four-adder regression retains 4/3/2/1 adders with the fix;
stock retains 4/1/1/1. All eight equivalence checks pass. The real bounded run
completes 16 merges after 138 loop rollbacks, saving only 19 LUTs. Neither the
plugin nor its mapping recipe is installed in the production toolchain.

The current coarse netlist contains 8,309 mux cells with 185,613 output bits,
compared with 554 add/sub cells with 14,846 output bits. These are structural
attribution counts, not removable LUT estimates. Both independent reviewers
recommend moving operand selection, private scratch, RAM requests, and state
writeback together behind a shared RED2 datapath. They initially differed on
the first family; after comparing interfaces, the agreed order is APP/LAMBDA,
lookup as the incremental scaling test, then publication as the transaction
stress test. Publication must retain preparation, external JOIN/scalar preflight,
and explicit commit authorization as separate boundaries.

The APP/LAMBDA pilot covers all 20 named handlers, matching graph/control
requests, and their execute-entry paths and validation. It lowers active source
control flow into immutable RED2 control tables with synchronous BRAM scratch,
bounded operand registers, and registered request ports. It must preserve exact
widths, malformed address detection, incoming-state guards, source-order scalar
updates and faults. Its setup/debug port addresses state only; it cannot load
controller programs. A logical clock may require many physical clocks, with one
acceptance and completion. A committed RED2 reduction remains a separate event.

First compare complete standalone old/new family implementations behind the
same addressed state and graph/control interfaces. Require real BRAM inference
and include controller, reset, arbitration and adapter costs. Then remove the
legacy handlers/requests and measure the integrated machine, including any
bridges for fields used by other families. Lookup must reuse the same datapath;
proportional growth in operand muxes would reject the approach. The full-core
engineering budget is 18,000 LUTs before board integration, an acceptance target
rather than a prediction.

A whole-tail AUTO_FSM diagnostic schedules 17,019 operations onto 154 units in
3,088 states, with 59,845 scheduled register bits. It excludes RAM requests and
has a 521-field input / 313-field state output; it is not an integrated compact
RED2 engine. Its scheduled HDL re-elaboration was stopped without generated
scheduled HDL. A separate ABC9 mapping was stopped after 31 minutes of wall
time, including about 24.5 minutes of ABC CPU time. Neither produced an area
result. Detailed hashes and measurements are in
`docs/handoffs/synth-red2-sharing-results.json`.

## Validated control-flow/storage pilot

The reproducible generator and checks now live in
`scripts/experiments/red2_cfg_pilot/`. All variants use the pinned enhanced
PipelineC compiler and the maintained core's classic flattened LUT6 mapping
recipe. The original-family comparison has the same addressed state and
registered graph/control handshake interface as the shared controller.

| Isolated scope | Original LUTs | Shared LUTs | Shared BRAM36 equivalents |
| --- | ---: | ---: | ---: |
| APP/LAMBDA | 3,977 | 1,481 | 9.5 |
| APP/LAMBDA and lookup | 6,254 | 1,377 | 12.0 |

Lookup increases the immutable control rows from 2,311 to 3,240 and scratch
depth from 1,024 to 2,048 64-bit words. It reuses the physical datapath. The
small LUT decrease between candidates is mapping variation, not a prediction
that additional rules always reduce area. Static all-path analysis proves
operand initialization within each admitted transition; generation rejects
unsupported AST constructs and types.

The independent typed reference passes 2,520 and 3,000 cases respectively.
Greedy path witnesses pass 67 and 89 cases against both original-family and
physical-controller native simulation, checking all family state fields and
request bits. Protocol checks cover delayed responses, input changes after
admission, busy-start/setup rejection, retained scratch across transitions,
reset cancellation and protected constants. The latest emitted HDL is byte
identical to all four mapped inputs; maps report zero structural problems and
no unaccounted primitives. These checks do not establish integrated program
parity or RTL-level simulation.

The next step is to integrate APP/LAMBDA and lookup, remove the old handlers
and request generation, and measure the complete core with shared-field bridges
and command/reset arbitration included. State ownership and handoffs are
recorded in each generated manifest. Then extend the same datapath to other
graph rule families, retaining publication's prepare/preflight/authorized-commit
boundaries. Compact scratch lifetimes and control tables as needed: moving
logic into BRAM must stay within the board's 50 BRAM36-equivalent capacity.

The maintained production core remains 41,170 LUTs; isolated savings are not
subtracted from that figure. Full-core acceptance remains 18,000 LUTs before
board integration, full native program parity and complete primitive accounting,
followed by routing and timing checks. Detailed source, HDL, mapping and
validation hashes are in `docs/handoffs/synth-red2-cfg-pilot-results.json`.

### Integration and persistent ownership follow-up (2026-10-12)

Temporary liveness allocation and packed control reduce the lookup controller
from 12 BRAM36 equivalents to five, at 1,459 LUT (82 more than the uncompressed
controller). Default noncompact lookup generation is byte-identical to the
previously mapped source. The broader graph configuration covers 56 entries,
6,229 rows and 218 used scratch cells; 6,720 typed cases and 159 physical path
witnesses pass. EP_REVERSE_CONTROL_READ remains external because its shared
initialization launch is consumed by other original logic.

The first full lookup integration mapped to 40,826 LUT, but is rejected:
a paused operand-consume phase allowed a synchronous scratch address to drift.
Corrected address hold passes all 25 lookup and 56 graph entry boundaries,
including RAM payload, pause and reset checks. The corrected graph complete top
is mapped separately. No production change or Basys 3 fit is claimed.

The two-reviewer diagnosis separates two effects: the standalone original
baseline contains debug/setup selection absent from production, and the serial
integration adds FF mirrors and writeback selection. The nominal isolated
saving is not additive, and coarse bridge mux-bit counts are not mapped LUT
attribution. Freeze the 56-entry graph scope before expanding again.

The next owned integration removes 26 lifecycle-only Reg roots (29 leaves,
923 typed bits), retaining their BRAM cells across transitions. Ownership must
be proved against the transformed remaining AST, with no surviving runtime
legacy reference. Use entry-specific shared import=(read-before-write union
may-write) minus private and export=may-write minus private. Stage only the
observable scalar bank for coherent publication; do not snapshot private state.
Queue a busy lifecycle command until logical completion so an accepted graph
write cannot be paired with an incomplete scalar transition. Extract exact
RESET/LOAD_STATE/valid START initializer masks; invalid START must preserve
private state. Include this entire boundary in the next full-core measurement.

Then migrate connected JOIN/selector/equality/publication state into the same
persistent backend, preserving preparation, external preflight and explicit
commit authorization. Acceptance still requires full native parity, complete
primitive accounting and 18k LUT engineering headroom before board routing.

Completed full-core comparison with the same graph scope and pinned mapper:

| Candidate | Total LUTs | FF | BRAM36 equivalents |
| --- | ---: | ---: | ---: |
| Maintained production | 41,170 | 8,676 | 15.5 |
| Corrected graph serial mirror | 38,908 | 9,731 | 24.5 |
| Persistent private ownership | 38,417 | 9,959 | 26.0 |

Both experimental maps have zero structural problems and no unaccounted
primitives. Ownership saves 491 LUTs against the same-scope mirror, including
its coherent observation bank, per-entry mask ROM and queued lifecycle logic.
It saves 2,753 LUTs against production but is still 17,617 above board capacity.
The added observation/queue registers mean FF count increases despite removing
private mirrors; no claim that ownership alone solves area is supported.

All 159 integrated path witnesses pass against the typed source results,
including all family leaves, graph/control payloads, pauses, nonzero private
lifecycle masks and queued invalid START after accepted writes/during export.
Application and list construction/access pass concrete lockstep (46,448
physical clocks), and existing RECP parity passes (70,844). Existing closure
materialization compatibility passes, but that particular suite exercises only
legacy transitions plus lifecycle initialization. Full-program parity for all
supported programs, RTL simulation and board implementation remain outstanding.
A new generator guard rejects dropped non-Reg events still read by legacy code;
it regenerates byte-identical hardware for the measured scope. Evidence and
hashes are in `docs/handoffs/synth-red2-cfg-integration-results.json`.

### Connected selector/JOIN extension in progress

After measuring ownership at fixed graph scope, add 52 selector/JOIN handlers
on the same datapath. Keep optional scalar arithmetic outside this extraction.
The resulting 108-entry controller has 11,709 rows, a 16,384x37-bit control ROM,
and 389 allocated scratch words in 512 locations. Its 12,960 typed reference
cases and 339 physical witnesses pass, including reset and constants. The
integrated candidate owns 60 private words and has 144 shared bridge words.
All 339 full-top path witnesses pass, including pauses, coherent observations,
nonzero private lifecycle masks and queued invalid START. Application/list
program lockstep also passes. RECP parity and mapping are ongoing; no new LUT
total is claimed until that exact source finishes the mapped flow.

The larger domain caught a 17-bit subtraction used before comparison: unsigned
intermediate wrap must follow enhanced PipelineC type rules. Lowering now uses
its public arithmetic result-type helper and preserves typed intermediate
widths. Native regression covers narrow underflow and widened addition. A
second rejected candidate included a handler that forms a post-response RAM
write; it needs another explicit request phase and stays in legacy hardware.
Record both failed experiments rather than treating them as successful lowerings.

Discovery and integration guards cover metadata writes outside handler bodies,
post-response requests and non-Reg launch events. Reused temporary names in
different legacy handlers are safe only with fresh dominating assignments;
zero defaults before extraction do not discharge launch-event obligations.
Evidence is in `docs/handoffs/synth-red2-cfg-connected-results.json`.

At this expanded scope, fixed scans visit 144 shared words although the average
entry imports 7.49 and exports 4.94. A second complete-top variant uses immutable
short transfer lists (1,558 nine-bit words) instead of the wide masks. Measure
both at identical scope. The transfer-list prototype passes initial boundary,
pause and lifecycle checks; full path/program checks and mapping remain
pending. Its emitter refactor reproduces the fixed-mask source byte for byte.

The expanded fixed-mask map completes at **34,183 total LUTs**, 9,272 FF, 20 DSP,
1,766 CARRY4 and 37 BRAM36 equivalents. That is 4,234 LUTs below the old
56-entry owned experiment and 6,987 below maintained production. All primitives
are accounted for and structural checks report zero problems. RECP parity
passes (112,644 physical clocks). Short-list application/list parity passes at
61,168 physical clocks versus 83,490 for fixed scans; its area map is pending.

Control storage will constrain further extraction: the current ROM has 11,709
logical rows but only 2,945 distinct packed words. An opt-in immutable index-ROM
plus word-ROM encoding adds one synchronous fetch cycle. Its reconstruction is
checked exactly and the physical controller is being revalidated. Measure its
whole-top BRAM and LUT usage before claiming headroom for publication; the
existing encoding remains the default and regenerates byte-identically.

The short-list map completes at **33,449 total LUTs**, 9,062 FF, 20 DSP,
1,753 CARRY4 and 33.5 BRAM36 equivalents. It saves 734 LUTs and 3.5 BRAM36
equivalents against the same-scope fixed-mask top. All 339 integrated boundary
witnesses, nonzero lifecycle checks and queued invalid START pass. HDL inputs
are verified against the recorded hashes; no structural problems or unaccounted
primitives remain. The gap to board capacity is still 12,649 LUTs. Continue
with control-store headroom and explicit metadata/publication adapters, rather
than treating the standalone family saving as an additive full-core estimate.

The indexed control-store full top finishes at **33,601 LUTs**, 9,064 FF,
20 DSP, 1,769 CARRY4 and 27 BRAM36 equivalents. Its 152-LUT cost frees 6.5
BRAM36 equivalents for further extraction. All 339 integrated witnesses,
lifecycle checks and application/list parity pass. Full source/HDL hashes and
primitive accounting are recorded in the dictionary results file. The direct
short-list store remains the lowest measured LUT count; retain both experiments.

Next extract only MICRO_PUB_EXEC with two explicit read-only metadata sidecars.
The legacy publication stack keeps all staged/authorized writes and completion
banks. This isolates the large pure publication computation without weakening
prepare/preflight/commit boundaries. The new configuration has 109 entries,
14,634 rows, 3,901 unique words and 482 allocated scratch words. Typed parity
passes 13,080 cases. The 370 physical witnesses pass, including 31 publication
cases covering all 1,048 observed CFG rows and all sampled task kinds. Complete
integration checks and mapped measurement are now running.
The earlier indexed scope regenerates byte-identically with sidecars disabled.

Indexed-store RECP parity passes at 79,540 physical clocks. Publication quick
full-top pause/lifecycle checks pass. Stronger validation and mapping use byte-
identical complete-top sources, with exact hashes recorded separately.

### Publication read result and next ownership boundary

The read-sidecar complete top maps to **33,299 LUTs**, 9,615 FF, 20 DSP,
1,643 CARRY4 and 27.5 BRAM36 equivalents. All primitives are accounted for,
HDL hashes match and structural checks report zero problems. This saves only
302 LUTs against the matching indexed-store top. Private ownership stays at
60 words while shared transfers grow from 144 to 205 words; computation-only
extraction does not establish a large area win. All 31 publication boundary
witnesses pass, including read-only metadata assertions, pauses and lifecycle
checks. Full 370-case boundary and existing publication parity checks continue.

A diagnostic pass removes 56 unused, single-definition, call-free aliases before
ownership analysis. It finds zero additional private words at this scope. Do
not infer LUT savings or map this diagnostic as a new optimization. The surviving
publication stack and launch writers really keep the state shared.

The next useful boundary is the connected publication stack and its state:

- Adapt all five original publication RAM packets, including typed write data
  and write enables; issue each packet once using the original incoming phase.
- Collect compound graph request arms such as `micro_is_pub_stack and phase ==
  COMMIT_GRAPH`, not only exact microstate-name arms. Retain source order and
  remove the same extracted arms from legacy logic.
- Attach the uniquely owned publication-completion bank to the stack handler;
  keep its lifecycle predicates in legacy arbitration. Preserve explicit
  preparation, external preflight and authorized commit phases.
- Prove zero struct initializers using exact original struct fields/constants,
  prune unused pure aliases, and move only state with no surviving legacy use
  into persistent BRAM. Connect the remaining launch writers before declaring
  their publication state private; retain generation/epoch behavior exactly.

Use a distinct opt-in configuration and source-derived typed oracle. Metadata
writes need exact request/payload and read-first RAM checks, accepted-write
lifecycle tests, and full native publication parity before adoption.

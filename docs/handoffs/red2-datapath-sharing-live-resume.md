# RED2 datapath-sharing pass — live checkpoint

## Latest continuation: failed wrapper and next area pass (2026-10-14)

This section supersedes running-job, build and current-board statuses below.
All four optional source `89c7712c...` complete native/Concrete list programs
have now **finished and passed** (4,044,528 simulated clocks). Driver PID 5299 /
child 75941 are terminal. Native unequal-list, equal-nested and unequal-nested
traces are byte-identical to their earlier validated RTL observations; their
separate origin metadata remain unchanged. Legacy native metadata is verified
against the completed native checker logs. This is additional corroboration,
not a relabeling of existing physical replay receipts. See
`red2-native-list-corroboration-results.json`.
The qualified source `89c7712c...` / SRAM bitstream `a0ef3f44...` remains the
working baseline. It was freshly restored at **09:56:37 UTC** after paired RAM
diagnostics; no program has run since that restoration. No flash writes occurred.

Shared-shifter source `60da0147...` now passes **15 same-source complete RTL /
Concrete programs: 4,568,145 simulated clocks**. All final graph/control RAM
checks pass. The actual RTL trace bytes match the earlier reference traces;
source/origin metadata remain separate. Both trace-recording drivers are terminal.

Its shift-register board **builds and routes**, at **16,321 physical LUT sites**
(4,479 spare) and 12.58/12.67 MHz estimated core/monitor maxima, passing 10 MHz.
The 288 mapped-LUT reduction produces **47 fewer physical LUT sites**; these
are different resource measures. BRAM and 20,319 LUT truth-table audits pass.
However bitstream `f8b7069c...` **fails physical application setup readback at
engine-clock endpoint 461**, before START. Only `memory_read` differs there.
The failed image also fails 34/131 walking-bit RAM words; the qualified image
passes the identical diagnostic. Byte lanes 0 and 5 repeatedly lose bits.
The cause is unresolved; this does not establish shifter arithmetic failure.
See `red2-shared-shift-physical-results.json` and the updated board report.
Do not retry the old supervisor or claim that candidate is physically qualified.

A controlled wrapper variant uses the existing **immutable indexed snapshot**
serializer with the same exact RED2 core. Full UART/CRC/recovery and burst RTL
tests pass, including TX stalls and counts through 1,048,575. Thirty-eight
focused pytest cases and Ruff pass. Added `--snapshot-response` test CLI flags
exercise this combination directly. It maps at **16,108 board LUTs**, saving
another 356; exact core identity passes. Placement is running at
`build/red2-basys3-shared-shift-snapshot`, driver PID **1819**, exec **57133**,
container `red2-shift-snapshot-place`. Supervisor PID **2001**, exec **3719**,
waits for actual build completion, then LUT audit and a **131-word physical RAM
pattern pass before program qualification**. It restores qualified `a0` on
failure. Revalidate the processes before waiting; never start a second UART
client while the supervisor is performing physical tests.
See `red2-shared-shift-snapshot-board-results.json`.

Separately, the remaining **IF EP-chase graph handler** is extracted using only
`MICRO_JOIN_IF_EP_CHASE` added to the previous configuration. Source
`7d965e66...` maps at **15,181 core LUTs / 6,090 FFs**, saving **334 LUTs and
80 FFs** with identical mapping scripts/backend/compiler and unchanged BRAM/DSP.
It adds 88 control rows (15,248 total), keeps 1,024 scratch words and covers
128 entries. All 88 new rows are covered by **27 targeted emitted-controller
native witnesses**, including malformed addresses, EP hop limits, atomic words,
closure continuation and unsupported forms. Reset and constant protection pass.
Full native/product/lifecycle/metadata/poison qualification runs in exec **90523**,
driver PID **3379**, `full-boundary-progress.json`. The same-source RTL replay
model is built; all **26 saved-IF RTL/Concrete fixtures pass** (exec 70543
terminal PASS, 1,342,196 simulated clocks / 2,754 admissions). Full same-source
complete-program RTL/Concrete checks are now live: short corpus exec **59311**,
driver PID **6684**, `direct-rtl-short-progress.json`; four list programs exec
**54246**, driver PID **6700**, `direct-rtl-lists-progress.json`. These do not
record expected-output vectors. Source `7d...` changes some transition latencies
(application 10,690 simulated clocks, structure 124,267), so do not relabel or
replay earlier-source clock-aligned goldens as this source's own observations.
Revalidate actual processes before waiting. No board preparation or physical
qualification is claimed for this separate extraction. See
`red2-if-ep-sharing-results.json`.

## Current qualified board: corrected shared multiplier (2026-10-14)

This section supersedes historical running-job statuses below. Dedicated RED2,
floating arithmetic omitted, division retained, enhanced compiler unchanged.

- Corrected shared-divider reference `1375f430...`: **16,809 LUTs**, 6,200 FFs,
  34.5 BRAM36 equivalents, 20 DSPs, 700 CARRY4. It passes 15,152 typed comparisons,
  the reachable equality checkpoint and four direct RTL arithmetic programs.
- Corrected shared product/finish/power candidate `89c7712c...`: **15,803 LUTs**,
  6,170 FFs, 34.5 BRAM36 equivalents, ten DSPs, 534 CARRY4. With the same semantics
  and byte-identical mapper scripts/backend, this saves 1,006 LUTs, 30 FFs and
  ten DSPs. Attribution verifies two ten-DSP multipliers become one; register
  alias groups are not functional LUT budgets.
- All **820 native boundaries plus lifecycle/metadata/poison checks pass**.
  All 15 direct RTL/Concrete programs and 26 saved-IF fixtures pass. Application,
  lifecycle, equality checkpoint and signed multiply pass every-bit native
  expected-output replay in frontend RTL and Xilinx primitives. The first full
  native equal-list program also passes 811,553-cycle every-626-bit RTL replay.
  Native unequal-list also passes 642,136-cycle every-bit frontend RTL replay.
  Its new RTL observation trace is byte-identical to native. Native equal-nested now passes 1,380,140 cycles; its trace is byte-identical
  to the completed RTL observation. Duplicate native unequal-nested remains
  running as optional corroboration.

The immutable preparation gate is
`docs/handoffs/synth-red2-shared-multiplier-results.json` (variant
`shared-multiply`). Do not edit it: board provenance pins its hash. It explicitly
uses direct generated-RTL/Concrete program semantics plus the native boundary
and bitwise/mapped gates; it does not claim the slow duplicate native corpus
has completed. Physical qualification is a separate requirement.

The complete burst board is prepared at `build/red2-basys3-shared-multiplier`.
It maps at **16,752 LUTs**, 8,370 FFs, 34.5 BRAM36 equivalents and ten DSPs; the
wrapper adds exactly 949 LUTs and 2,200 FFs. Exact backward-cone identity matches
23,061 original core primitives, all parameters, 30,767 bijective nets and all
32 packed public fields after only cutting the core clock/command boundary.

Mapping, placement, routing and bitstream generation have **completed**. The
board uses **16,368 physical LUT sites**, leaving **4,432 spare**. Both domains
pass the 10 MHz requirement: core 12.82 MHz, monitor 12.76 MHz estimated maximum.
All 29,914 cell placements are preserved. It uses the existing pinned backend
`e9fd42e7...`, chipdb alias, seed 1, four-thread analytical placement, eight
serializer-pair relocation and router2 hold-fix=8. LUT INIT audit passes 20,428
truth tables; the BRAM audit also passes.

The new image `a0ef3f44...` is loaded in **volatile SRAM** on Basys 3 serial
`210183735787`. Physical application replay passes **10,688 executed clocks /
1,354 compared packet endpoints**, lifecycle passes **1,043 / 21**, signed
multiply passes **46,855 / 1,375**, and the equality checkpoint passes
**61,871 / 828**. Each endpoint compares all 626 public output bits with the
native hardware-source trace. No every-cycle observation is claimed for burst
replay. Each case starts from a fresh SRAM load; no UART retry/resume occurs.
Full equal-list physical replay also **passes: 811,553 / 1,631**. Exec **6556**
completed successfully, with `native-corpus-qualification.json` terminal PASS.
The older f97 image `5e88122c...` remains preserved. The initial qualification
drivers would restore it on failure; none of these runs failed. For future
candidate bring-up, prefer restoring the newly qualified `a0ef3f44...` image.

Validated RTL observation recording now retains a distinct expected-output
origin, same-source binary/manifest hashes and completed Concrete RED2 semantic
gate. Application observations exactly match all 10,688 native trace rows.
Twenty-three focused regressions and Ruff pass. The wider observation corpus
is **complete** (exec **14079**), `rtl-observation-corpus-progress.json` terminal
PASS for all twelve additional programs. These are RTL observations rather than
native expected-output traces. Application and unequal-list observation traces
are byte-identical to native (10,688 and 642,136 cycles respectively). See
`red2-rtl-observation-trace-results.json`.

Physical replay against those validated observations also **completes** (exec
**84822**), `observed-corpus-qualification.json` terminal PASS. This adds
structure, add, signed-add, negative EVEN?, divide, modulo, exponent,
signed-minimum multiply, high-magnitude divide, unequal-list, equal-nested and
unequal-nested. Overall the FPGA passes **15 complete programs plus lifecycle
and the equality checkpoint: 4,631,059 executed engine clocks / 22,878 compared
packet endpoints**, all 626 public output bits at each endpoint. Each case
uses a fresh SRAM load. The final load/replay leaves `a0ef3f44...` on the board.
UART replay is complete; no transport process should remain active.

The new optional `attribute_resources.py --lut-cones` report partitions all
15,477 combinational LUTs by conservative endpoint reachability. The largest
exclusive sets feed remaining core state (3,501) and scratch-memory inputs
(2,979). These are not removable-area estimates. Five regressions pass; storage
and DSP attribution remain unchanged. See `red2-lut-endpoint-attribution-results.json`.
The optional shared left/right shifter experiment `60da0147...` at
`build/red2-shared-shift/shared-shift` maps to **15,515 LUTs**, saving **288**
against the corrected same-recipe 15,803-LUT reference. FFs (6,170), BRAM36
equivalents (34.5) and DSPs (ten) are unchanged; CARRY4 increases from 534 to 550.
Mapping scripts, backend versions and enhanced compiler manifest are identical.
All 15,160 control rows, dispatch tables and scratch allocation are unchanged;
the flag adds no controller cycles. Native checks pass 15,504 typed comparisons
and 123 selected emitted-controller witnesses, reset cancellation and constant
protection. Exactly emitted shift expressions additionally pass 3,406 typed
native checks and 9,694 independent arithmetic comparisons. An isolated
enhanced-PipelineC/GHDL SAT miter proves both shifts for all 129 input bits.
An initial formal harness used a packed record port where GHDL exposed separate
field ports; that failed harness receipt is preserved, and the corrected actual
RTL proof passes. Default-off generation stays byte-identical to the baseline.

The candidate's full RTL replay model is built (exec **92380** terminal PASS),
binary SHA `af7ce7c4...`. Cross-source regression **passes** (exec **1119**),
`check-reference-traces.py`, progress `reference-rtl-replay-progress.json`.
It intentionally compares new candidate RTL against the earlier-source native
and validated RTL observation traces, preserving both source IDs and each
expected-output origin. It checks every one of 626 bits on every cycle for all
17 cases: **4,631,059 simulated clocks**, terminal PASS. This candidate has not yet been routed, loaded or physically qualified.
The current board remains the qualified shared-multiplier image.
See `red2-shared-shift-results.json`. The flag remains optional/default-off.

The same-source complete-top native gate is **complete**: 820 boundary
witnesses, reset/private/queued lifecycle, five accepted metadata banks and
poisoned payload checks all pass. Four Xilinx mapped primitive replays pass
all 626 bits on each of 120,457 simulated clocks. All 26 same-source frontend
RTL/Concrete saved-IF fixtures also pass (1,340,406 simulated clocks).
The immutable preparation gate is
`docs/handoffs/synth-red2-shared-shift-results.json`; do not edit it.

The new complete board is prepared at `build/red2-basys3-shared-shift`.
It maps at **16,464 LUTs**, 8,370 FFs, 34.5 BRAM36 equivalents and ten DSPs,
saving 288 mapped board LUTs. The wrapper still adds 949 LUTs and 2,200 FFs.
Exact identity checks pass for 22,789 core primitives, their parameters,
30,607 bijective nets and all 32 packed public fields. Placement is running
in `red2-shift-place`, driver PID 86470 (exec 88740); revalidate the actual
process/container before waiting. Routing, timing, bitstream generation and
physical qualification are pending. See `red2-shared-shift-board-results.json`.

Additional same-source RTL/Concrete complete-program observation recording is
running for the candidate. All eleven shorter programs **pass** (523,617
simulated clocks); their actual RTL traces have completed independent semantic
checks and retain distinct same-source metadata. Equal-list also passes (811,553 simulated clocks). The other three list
programs are running under driver PID 89691 (exec 64092), progress
`board-rtl-traces-lists-progress.json`; revalidate that process before waiting.
Prepared `build/red2-basys3-shared-shift/qualify-rtl-corpus.py` will use these
same-source observations, fresh SRAM per program, all 626 bits per packet
endpoint and restoration of qualified `a0ef3f44...` on failure. It has not run;
board timing and bitstream generation must pass first. A supervisor is live
in exec 58124, PID 94228, `qualify-when-built.py`; it verifies the actual build
process and starts the physical driver only after successful audited build
completion. `qualification-supervisor.json` records that state. Revalidate this
process/session before waiting; do not launch a duplicate UART client.

Live execution is now implemented in `scripts/boards/red2_basys3/run.py`.
It compiles THOR on the host, loads fresh volatile SRAM, sends public-port
commands and clock bursts, and decodes graph data read back from the FPGA.
No prerecorded vectors or host RED2 reducer are used. CLOCK/UART effects are
handled by the existing host I/O adapter at FPGA suspension/resume boundaries.
Native reducer/RAM APIs are disabled during the RTL runner checks.

Eight fresh physical programs pass: `((LAMBDA (x) (+ x 2)) 40)` -> 42,
`(CAR (CONS 12 (CONS 34 NIL)))` -> 12, `(/ -84 2)` -> -42, UART transmit,
UART receive, injected CLOCK, real system CLOCK (64-bit timestamp) and
`examples/fibonacci.thor` (`fib 6` -> 8). Their final architectural fields and all 256 graph /
256 control RAM words match separate RTL public-port executions. The FPGA
remains on `a0ef3f44...`, most recently halted after Fibonacci -> 8.
All live UART processes have completed; no flash writes occurred. Detailed
receipts and transcripts are in `build/red2-basys3-live-run`, with compact
evidence in `red2-basys3-live-run-results.json`.
Post-execution transcript comparison also matches every command and all 626
response bits at all **10,305 packet endpoints** across these eight programs.
These are live-execution endpoint checks, not comparisons at each internal
burst cycle. Fibonacci used 1,376,256 delivered run clocks, including the final burst's
HALT tail; this is not exact cycles-to-halt. The pre-profile-guard runner source was reconstructed and hash
verified against its physical receipts, then preserved as
`build/red2-basys3-live-run/run.before-profile-guard.py`.

The `fpga` dependency group explicitly pins setuptools 84.0.0 (the same version
previously borrowed from Python 3.13's site-packages). `uv sync --group fpga`
makes the live runner work from the project venv without that PYTHONPATH.
`uv lock --check`, Ruff and 40 focused tests pass. Runtime rejects cached ABI
types from a mismatched memory/float profile before loading hardware.
Live `delivered_run_clocks` includes any idle tail in the final 65,536-clock
burst, excludes setup/readback, and is not an exact cycles-to-halt benchmark.
The receipt requires COMPLETE/HALTED/no pending host op; budget/transport
errors, hardware faults and quantum exhaustion cannot produce success.

`audit_bram.py` is now copied and run after routing before frame generation.
Eight regressions and a real preparation smoke pass. Both saved working/failed
boards pass all 45 BRAMs' known INIT data and intended width/clock/write settings
(69 halves, 4,968 words, 962,048 known bits and 855 flags). The first temporary
audit mistakenly used pre-SDP72 width expectations and flagged 14 intentional
bits; its failed receipt is retained and the pinned patch is now included.
This has not identified the prior physical failure. The xc7a35t-to-xc7a50t alias
also matches upstream [nextpnr](https://raw.githubusercontent.com/YosysHQ/nextpnr/main/himbaechel/uarch/xilinx/xilinx.cc)
and [prjxray](https://raw.githubusercontent.com/f4pga/prjxray/master/settings/artix7/devices.yaml);
no device-map change was made.

Records: `red2-corrected-arithmetic-sharing-results.json`,
`red2-shared-request-guards-results.json`, and
`red2-shared-multiplier-board-results.json`. Recent pushed commits include
`7c204c7` (trace origins), `2d2400f` (LUT endpoint attribution), `2156958`
(physical checkpoint), `ebef101` (explicit clock/endpoint labels) and `370c822`
(optional shared shifter with isolated RTL equivalence evidence).

## Latest checkpoint: shared multiplier and request extraction (2026-10-14)

This section supersedes the historical process and board-load statuses below.
The last confirmed FPGA load is the qualified f97 burst image, bitstream
`5e88122cefd085717d63258192d5fd60f3b9ab10e2ed8bc0e71d5c088b8a8df5`.
The divider-only board routes at 17,826 physical LUT sites and passes 10 MHz
timing, but physical application replay fails. The earlier image was restored.
Flattened mapped-board application simulation, exact mapped-core identity and
22,653 LUT truth-table checks pass; the downstream physical fault is unresolved.
See [the physical failure record](red2-shared-divider-physical-results.json).

The optional shared multiplier plus extracted finish/power handlers maps the
combined semantic core from 17,003 to 15,830 LUTs and from 20 to ten DSPs.
This frozen `e718bd5a...` source passes 15,504 typed comparisons, 123 selected
native controller witnesses, 820 native boundary/lifecycle witnesses and 11
native/concrete programs with 523,584 RTL cycles, all 626 output bits compared
per cycle. No new FPGA qualification follows from those simulation results.
See [the multiplier record](red2-shared-multiplier-results.json).

An independent list-equality checkpoint fails in both the combined baseline
`202f7182...` and multiplier candidate. The maintained source passes the same
checkpoint. Root cause: RAM request extraction keyed a shared `or` predicate
as one state name, omitting the IF path request. It read stack slot 0 (saved
quantum) instead of slot 4 (address). Shared structure request guards were also
affected. `request_arms.py` now expands shared alternatives, merges request
blocks in source order and preserves unselected alternatives in integration.
Source-based pytest regressions cover both IF paths, six structure paths,
ordered blocks, residual guards and rejection of unsupported mixed/else guards.

The corrected shared-multiplier source is frozen separately at
`build/red2-request-guards/shared-multiply`, SHA256
`89c7712cb728b61872c7823e119b0c4e8c6548f2dcccd92b2504c8f5d10f4f94`.
Its generation, checkpoint and map receipts live there; do not reuse the old
15,830-LUT measurement as a measurement of this fix. The durable focused gate
is `check_integrated.py --equality-checkpoint`; full programs, exact-source RTL
replay, boundary/lifecycle and physical qualification remain required.
The corrected checkpoint now passes: 61,871 native simulated cycles including
setup/readback, with next-commit architecture and all graph/control words
matching Concrete RED2. Corrected typed validation passes 15,504 comparisons.
See [the request-fix evidence](red2-shared-request-guards-results.json).
The corrected enhanced core map is complete at **15,803 LUTs**, 6,170 FFs,
34.5 BRAM36 equivalents, ten DSPs and 534 CARRY4 cells. HDL and mapping-script
hashes verify; synthesis reports zero structural problems. The 123 selected
native product-controller witnesses, reset cancellation and constant protection
also pass. Complete native boundaries and four equality programs are running;
the exact-source RTL replay model is built. No new physical load has occurred.

Focused equality checkpoint replay now passes all 626 output bits on every one
of its 61,871 cycles in Verilator. An interactive RTL testbench links a small
host port driver to the existing compiled model archive; it does not change
the FPGA netlist. `build_interactive_rtl.py` records and verifies model/layout
inputs. `check_interactive_vectors.py` verifies complete same-source native
traces; it passes the same 61,871 cycles against the interactive driver.
Set `RED2_CFG_PILOT_RTL_INTERACTIVE=1` for `check_integrated.py --program`,
`--equality-checkpoint` or `--saved-if-fixtures`. Results have a distinct RTL
environment/marker and cannot be recorded as native expected-output vectors.
Twenty-one focused pytest cases pass, including nested port layout and trace
format checks. Direct RTL prototypes pass complete application and equal/unequal
one-element list programs; these compare architecture and expected mutations at
commits and all RAM at termination, rather than every bit with native per cycle.
Durable direct RTL corpus/nested/26 saved-IF gates are separate jobs below the
corrected output root. Their terminal progress files must be checked before
claiming completion. The original native full-program/boundary jobs continue.
Completed additions: all 11 original programs pass direct RTL/Concrete parity
(523,617 simulated cycles); the equal two-element nested list passes 1,380,140
cycles; all 26 saved-IF fixtures pass architectural and full-RAM parity in RTL;
and public queued lifecycle passes native assertions plus every-bit RTL replay
for 1,043 cycles. The direct corpus is also replaying the two simple equality
programs, while the nested job is running the unequal case. Xilinx mapped
primitive replay for lifecycle/equality-checkpoint/signed multiply is now running
under `mapped-check-progress.json`; the native product trace is recorded by
that driver. Do not infer completion from file existence.

The older failed divider board also passes a BRAM known-initialization-bit and
output-register-setting audit against FASM: 45 cells, 69 halves, 4,968 words,
962,048 known bits, zero mismatches. This does not check frame conversion,
widths, clock polarity, routed wires or physical behavior. No board was loaded.

Terminal direct RTL results now supersede the preceding running-list statuses:
all 13 original/simple-equality corpus programs and both nested-list programs
pass (15 total, 4,568,145 simulated cycles). All 26 saved-IF fixtures pass too.
The host checker changed only to add the saved-IF entrypoint while the batches
ran; deleting that import/function/mode exactly reconstructs the batches'
initial checker hash, so existing program checking/transport code is verified
unchanged. Candidate source and model manifest were checked before each case.
Native signed multiply passes every-bit ordinary RTL replay for 46,855 cycles.
Mapped Xilinx lifecycle passes all 626 bits for 1,043 cycles; the mapped driver
continues with equality-checkpoint and signed multiply. Native boundary and
native full equality traces remain live and must be verified independently.
A corrected shared-divider-only reference profile (shared multiplier disabled,
finish/power left in legacy logic) is generating/being mapped separately under
`build/red2-request-guards/shared-divider` for a controlled area comparison.

Compiler launchers now bootstrap installed setuptools' `distutils` compatibility
instead of depending on `/tmp/red2-python-shims`, which disappeared during an
earlier corpus run. The pinned enhanced compiler is unchanged. That bootstrap
failure ran no hardware clocks; the remaining four corpus cases subsequently
passed. Native gate output now explicitly labels simulated clocks and the
environment. Cycles include setup/observation and do not count RED2 reductions.

The user explicitly redirected effort from physical RAM staging to a substantial
source-level datapath-sharing pass. Continue this pass through validation,
measurement, commit and push. Do not resume the old blanket RAM-stage route.
Dedicated RED2 only; enhanced PipelineC required; more cycles are acceptable;
preserve current integer-profile semantics. No instruction was dropped here.

## Physical checkpoint

The one-hour watchdog stopped `ram-phase-isolation-route5` at iteration 2 with
37,394 overused routing resources. There was no new bitstream/load/replay.
`build/red2-basys3/ram-phase-isolation-route5/route-time-limit.json` records it.
The narrowed scratch/graph RAM prototype `ram-working-phase` passed all 10,703
mapped-simulation commands, adds 404 used FFs and no LUTs, but was NOT placed or
routed after the user redirected effort. Last known board image remains
`normal-monitor-fullroute/red2_basys3.bit`, failing physical replay at 7,506.

## New measured candidates

All roots are under `build/red2-datapath-sharing/`. The frozen starting source
is `/tmp/asgard-area-next/cfg-integer-joins-regfix` (19,172 LUTs, 8,095 FFs).
`baseline-reproduction/integrated-stream/machine.py` regenerated byte-identically:
SHA256 `f229a2755c11376093f876e46e9b175148c98727e6e638f179f5e5e53258da68`.

| Variant | LUTs including LUT RAM | FFs | BRAM36 equivalents | DSPs |
| --- | ---: | ---: | ---: | ---: |
| Frozen baseline | 19,172 | 8,095 | 34.5 | 20 |
| shared-response | 19,101 | 7,188 | 34.5 | 20 |
| shared-storage | 18,985 | 6,901 | 34.5 | 20 |
| reverse-control | 18,767 | 7,018 | 34.5 | 20 |
| **dirty-writeback** | **17,266** | **6,345** | **34.5** | **20** |

The last candidate saves 1,906 LUTs (9.94%) and 1,750 FFs. These are CORE mapping
results, not a mapped/routed/working board result. Old wrapper delta was 878
LUTs; do not label an estimated new board count as measured.

`dirty-writeback/integrated-stream/machine.py` SHA256:
`f97b169a1610f0235fed2bf3f701d3989e1567daa97ce668a36cc2e5403195e8`.
Every completed area map reports zero structural problems and no unaccounted
primitives. The enhanced compiler manifest remains `9834e480170b...`.

## Implementation

All flags are optional and default off:

- `RED2_CFG_PILOT_SHARED_RESPONSE=1`: integrated microengine reads the bridge's
  retained response registers instead of duplicating 907 bits. Standalone
  controller retains pulse-response capture. Checks enforce packet wiring,
  capture writers and response-use domination by accepted request.
- `RED2_CFG_PILOT_COMPACT_PENDING=1`: queued RESET/LOAD_STATE/START retain op,
  address, value and architectural state; word/control/aux are zero. This drops
  287 mapped FFs, not the full 324 declared payload bits.
- `RED2_CFG_PILOT_REVERSE_CONTROL=1`: moves EP reverse control handling onto the
  shared engine, preserving its source scalar-launch reset bank. The generic
  `publication_launches.describe` now accepts a writer/event set; defaults
  reproduce the old behavior. Thirty mandatory nonzero witnesses cover atomic,
  UBV, closure, launch and fault paths. 123 entries, 14,846 compact rows, 5,791
  dictionary words, 621 allocated scratch words, 200 private/175 shared words.
- `RED2_CFG_PILOT_DIRTY_WRITEBACK=1`: scratch word is 65 bits. Imports/setup clear
  tag bit 64; actual microinstruction writes set it. Export only tagged values.
  All fields remain in the same transfer schedules, so tags are reset before
  every possible export. Initial-read analysis removes 63 fields from the
  import data selector (they receive a clear-only setup write). An independent
  CFG constant-value analysis identifies constant actual writes; 56 shared
  fields/1,391 bits bypass the export data bus. The removed selector inputs total
  1,780 bits relative to the reverse-control variant. No extra BRAM was needed.

Code changes are in `scripts/experiments/red2_cfg_pilot/`: shared_response.py,
compact_pending.py, dirty_writeback.py, reverse_control.py and generator hooks.
The production machine and compiler source/pins are unchanged by this pass.

## Validation completed

The final candidate passes all 701 complete-top native boundary cases, including
152 integer corners and 30 mandatory reverse-control witnesses. The interrupted
serial prefix was combined with six disjoint completed ranges; the partition
record verifies exact coverage. Lifecycle, five-bank accepted-write and nonzero
queued LOAD_STATE/START checks pass. All 14,912 typed comparisons pass with
concrete assertions checking the constant-write proofs.

Five new native/concrete program traces pass every one of 626 public output bits
in Verilator: application 10,683 clocks; addition 26,226; structure creation/access
123,200; signed-boundary addition 26,226; EVEN? -2 44,655. Total: 230,990 clocks.
The public queued-lifecycle trace passes another 1,018 clocks. Do not reuse the
old candidate's traces: latency changed.

Mapped simulation using Xilinx RAM primitive models passes application (10,683
clocks) and public lifecycle (1,018). The 65-bit scratch RAM therefore has both
RTL and mapped primitive checks. All 69 mutation/precondition checks, 18 scalar
partition checks, six launch checks, 13 focused board pytest cases and Ruff pass.
Fresh full regeneration reproduces both the default baseline and candidate
byte-for-byte; final-reproduction.json records it. All area maps are complete.

The hashed result record is synth-red2-datapath-sharing-results.json. It records
candidate/source/HDL/mapped artifacts, every trace identity and validation scope.
No new physical-board application result exists yet.

## Tools and reproducibility

`build/red2-datapath-sharing/run-candidate.py VARIANT SCRIPT [ARGS]` orchestrates
exact frozen configuration plus the variant's flags. It copies frozen inputs
only if absent. The dirty root was initialized from reverse-control so its
oracle/cases include the new state. It uses `.venv/bin/python` (3.14.7), with
`PYTHONPATH` containing project scripts, `/tmp/red2-python-shims` (distutils
copy_tree shim) and `/usr/local/lib/python3.13/site-packages` (pycparser 2.22 and
other pure compiler dependencies). Initial clean-venv attempts failed for missing
distutils; preserved logs are not semantic failures. Enhanced compiler is
`build/pipelinec-enhanced-9834e480170b` and verify_enhanced_compiler passed.

Frozen Podman Nix volume/tool paths match the physical checkpoint. Area run
scripts generated by prepare_map.py use Yosys 0.67/GHDL and the SAME ABC script
as baseline. Do not invoke a full new Nix develop/chipdb rebuild. Native host has
12 CPUs/32 GiB; tests were parallelized. Host free disk was about 1.5 GiB; watch
space, losslessly compress completed diagnostics if needed (never active files).

## Board continuation

The validated candidate is prepared in build/red2-basys3-datapath using:

```sh
python3 scripts/boards/red2_basys3/prepare.py \
  --report docs/handoffs/synth-red2-datapath-sharing-results.json \
  --variant dirty-writeback --output build/red2-basys3-datapath
```

Preparation now accepts explicit report/variant arguments; defaults retain the
old candidate. host.py already validates the selected prepared provenance.
clocks.py derives the actual packed monitor/core net names before resuming
routing; a backend probe verified both 10 MHz constraints, including the
core.clk_25p0 alias. No nextpnr patch was added by this pass.

Whole-board mapping is complete: 18,144 LUTs, 8,525 FFs, 34.5 BRAM36 equivalents,
20 DSPs. All primitives are accounted for and structural checks report zero
problems. synth-red2-datapath-board-map-results.json records the hashes.
The source pass is committed/pushed as 83d4124. run-physical.py in the prepared
root is running the cached backend: 30-minute placement budget, one-hour routing
budget, then fit/timing-gated bitstream generation. physical-progress.json and
physical-driver.log record progress; exec session 97695. The initial raw-backend invocation omitted --device and
exited before placement; its logs are preserved under initial-missing-device-*.
The corrected invocation selects xc7a35tcpg236 and uses the established
-o hold-fix=8 / -o fasm options. This driver does not
load SRAM automatically. Placement/routing, bitstream and SRAM replay remain.
 Use the pinned cached tools, a new result log, and the new application
trace. Do not claim that core fit proves physical operation. Keep the historical
failed physical images and reports intact.


## Physical result — 2026-10-13

Cached build completed: placement 15m17s, routing 14m15s, bitstream generated.
17,992 physical LUT sites, 2,808 spare. All 33,095 cell placements preserved;
core 10.14 MHz and monitor 10.62 MHz pass the 10 MHz requirement. No hold
violations were reported. Bitstream SHA256:
297a9589e2f5910523ac8a397c230e3291cfef729bb1ed516a9f7f4365d6f97f.

SRAM load succeeded. Application replay matched clocks 0–255 then failed at 256:
only busy bit 625 expected one, actual zero. A fresh reload and independent
300-command prefix diagnostic reproduces it; clocks 257–299 also differ at
memory_read bit 449. The diagnostic continues after mismatches and is explicitly
NOT a passing replay. Framing/sequence/CRC checks passed. Do not label it a UART
sequence-wrap bug without evidence. LUT INIT audit checks all 23,246 logic LUTs
against emitted FASM and reports zero mismatches. This does not prove routing,
RAM configuration, or gate timing correct.

synth-red2-datapath-board-results.json records build/load/replay hashes and scope.
The board currently contains this new SRAM image after the 300-command prefix.
No serial client or build job remains running. Root cause is still unresolved;
next work is physical data/control delivery diagnosis. Preserve the new mismatch
logs and the earlier image's clock-7506 failure separately. The older continuation
instructions above are historical; placement/routing and SRAM load are complete.


## Serializer diagnosis — latest continuation

The previous goal turn made progress: fit/timing/SRAM/replay evidence was recorded.
This turn further narrows the physical mismatch. A clock-only diagnostic changes
six frame bits (MMCM divide100 ->120), producing 8.333 MHz and 96000 baud. It
fails identically at clock256. Both bitstreams and every load/result are retained.

After a fresh SRAM load, the 131-word physical graph diagnostic (zero, all ones,
mixed and 128 walking ones) reports 50 mismatches. Critically, every graph error
maps to response-byte lanes 1,2,7 after adding the memory_read offset364. Across
all 393 commands, no returned status bit in these three byte lanes is ever one.
Framing/sequence/CRC checks pass, including sequence wrap. The all-ones graph
word comes back as repeated 0x97, exactly the global output-byte missing lanes
translated through that four-bit field alignment. This strongly points at the
response serialization paths. It does NOT prove that all RED2 internal execution
is correct or establish the exact failing cells. Do not treat busy625 and
memory_read449 as unrelated core faults without further evidence.

Reusable scripts/boards/red2_basys3/diagnose_memory.py reproduces the exact 50
errors after a separate fresh SRAM reload. Five analysis tests plus transport,
clock and audit tests pass (15 total), and Ruff passes. It verifies the selected
image against the successful SRAM-load record and preserves raw status words.

The earlier monitor-capture-move route was explicitly stopped and cancelled.json
records why. No bitstream came from it. The NEW serializer-byte-move experiment
moves only the eight final response-byte LUT/FF pairs, keeping all logic and core
placements unchanged. It is routing in Podman red2-datapath-serializer-move;
exec session4183, a one-hour watchdog, then physical-fit and 10 MHz timing gates
before bitstream generation. Inspect actual live state before waiting/restarting.
Its run.py/progress.json/driver.log and board-route.log are in that root. It does
not load SRAM automatically. When complete, verify the build manifest, load its
image with the established SRAM-only program.py helper, then run diagnose_memory
at115200 baud with the parent prepared root. Full application trace remains the
same 10683-clock candidate trace, and requires a separate fresh SRAM reload.

The board currently contains the SLOW diagnostic image after the 131-word memory
test; there is no serial client running. Use baud96000 for this image, and115200
for the normal10MHz/relocated images. Do not silently reuse the wrong host baud.
The source/generator/compiler pins are unchanged. Completed pre-ABC IL dumps were
losslessly gzip-compressed to recover disk space; measurement hashes/artifacts
are otherwise retained. red2-serializer-diagnosis-results.json records this
checkpoint and raw evidence hashes.


## First physical RED2 application pass — latest checkpoint

The previous goal turn made progress through physical byte-lane diagnosis and a
reusable checked memory probe. This continuation completed the serializer reroute
and the first real RED2 application pass. No compiler/core logic was changed.

The monitor-only FPGA fixture (878 LUTs, 2,130 FFs; no RED2 engine) passes all 759
physical commands: all 626 response walking bits, ignored high input bits,
random patterns, accepted-edge count and multiple sequence wraps. Its files are
in build/red2-monitor-selftest. This is a transport diagnostic, not RED2 proof.
The original full-board packed-origin audit also matches all 135,083 retained
LUT/FF logical ports before/after packing, with zero unresolved aliases. A
mapped-monitor simulation export was prepared but NOT simulated; do not claim it.

serializer-byte-move completed normally. The 16 moved monitor cells preserve
all core logic and core placements. Rerouting uses 17,997 physical LUT sites,
2,803 spare; core 10.05 MHz and monitor 10.51 MHz pass 10 MHz. Bitstream SHA256:
dd259c97f70e3edfe084d7e48dd2a541174ae36bd3681c5be26e50853f5f5e37.
Fresh SRAM loads and the reusable memory probe now pass all 131 patterns.

The complete RED2 function-application trace passes all 10,683 clocks and all 626
output bits on hardware (239.802 seconds). After another fresh SRAM load, the
public queued-lifecycle trace also passes all 1,018 clocks (24.114 seconds).
These are 11,701 complete RED2 physical trace clocks, separate from the fixture
and partial-field memory diagnostic. synth-red2-basys3-working-application-results.json
records completed evidence and hashes. Older failures are preserved separately.

The existing relocate_monitor.py CLI with --first-bit 0 --count 8 reproduces the
selected placement byte-for-byte. prepare.py now accepts --relocate-response-byte;
implement.sh applies that recipe after placement, retains both placements,
records the selected path/hash and audits the selected copy. It uses the same
hold-fix=8 setting as the verified cached route. A flagged fresh preparation has
been hash-checked, shell syntax/Ruff pass, and all 15 focused tests pass. A fresh
full build through this flag has NOT yet been physically replayed; exact selected
placement reproduction is proven, not a universal backend fix.

The remaining physical suite is LIVE: exec session94061, local Python
serializer-byte-move/run-program-suite.py. It checks the existing application
pass, then freshly loads SRAM for lifecycle, structure, addition, signed-add and
EVEN? -2. Lifecycle is complete. Structure (123,200 clocks) is currently running,
then arithmetic follows. Each trace checks every output bit and source/vector
hash; every load/result/log is exclusive, and any error stops the suite without
UART retry. program-suite-progress.json / program-suite-driver.log and the active
<label>-board-replay.log are authoritative. Recheck the actual process/handle
before waiting or changing anything. Do NOT start another serial client while
this suite is running. It is using the normal 10 MHz / 115200-baud working image.

The objective remains active. Broader physical program parity and the existing
unsupported list-equality path still require work; do not equate one successful
application with exhaustive architectural correctness.


## Snapshot serializer and detached physical runners — latest checkpoint

The previous goal turn made progress: dedicated RED2 application and queued
lifecycle passed on the FPGA, with source/evidence committed as 5e06454.
This turn adds a smaller optional UART serializer and preserves/restarts an
interrupted long physical replay. The objective remains active.

The original physical suite exec94061 ended with exit1; both Python processes
were absent, the structure result file remained empty and the last positive log
marker was 30,100 matched clocks. No exception/mismatch/final result was recorded;
the cause is unknown. All evidence is preserved, and
serializer-byte-move/original-suite-interruption.json records it. Do not count
that prefix as a full structure pass or silently resume uncertain UART delivery.

A fresh SRAM retry now runs detached: PID 6443, script
serializer-byte-move/run-program-suite-retry1.py. Its launch/progress/driver files
are program-suite-retry1-*. It skips the already passed lifecycle case and runs
structure, then addition, signed-add and EVEN? -2. Each case gets a fresh SRAM
load and unique *-retry1 filenames; errors stop the suite with no implicit UART
retry. It has passed 54,000 structure clocks at this checkpoint. Revalidate PID
and command identity plus actual log growth; do not infer live state from a
stale progress JSON. No tool session handle owns this detached process.

The optional --snapshot-response serializer captures status once, selects bytes
by index and uses the selected byte for CRC. It removes the wide shift update.
The controlled complete-board map is 17,786 LUTs, saving 358 from 18,144. FF 8,525,
BRAM 34.5 and DSP 20 are unchanged. Enhanced-compiler/core artifacts are byte
identical. UART waveform, CRC/padding/recovery/sequence-wrap and full 10,683-clock
application monitor simulation pass; 23 focused tests and Ruff pass. The strict
snapshot_monitor.py transform guards ABI, frame bounds and both original response
writers. Default monitor.v is unchanged; --snapshot-response and the existing
--relocate-response-byte mode are mutually exclusive. This is an experimental
opt-in; no snapshot image has been physically replayed yet.

Measured prototype: build/red2-monitor-snapshot. Prepared snapshot build:
build/red2-basys3-snapshot-prepared. Every design input hash matches the prototype,
so its completed map was reused via APFS clones. Preparation manifest hashes were
verified. Detached build PID 10833 runs run-physical.py in the prepared root, with
physical-launch.json / physical-progress.json / physical-driver.log. Placement
passed (estimated core 11.71 MHz, monitor 12.14 MHz), and routing is live in Podman
red2-snapshot-route. The cached backend is still e9fd42e7..., --freq 10, explicit
clock names, hold-fix=8, router bounds 12/congestion 1.2. Fit/timing gates precede
bitstream generation. This build NEVER loads SRAM; leave the working image and
serial suite uninterrupted. Verify actual PID/container state before waiting or
restarting. Only load the new image after the serial suite has finished or been
explicitly stopped and its evidence saved.

red2-snapshot-serializer-results.json records area/simulation/preparation and
completed placement evidence. Routing results and new physical replay remain to
be recorded. Original program/trace/generator/compiler semantics are unchanged.
Unused cancelled/reproduced placement copies and an unused simulation export /
old mapped-sim binary were losslessly gzip-compressed; no active image manifest
input was changed. VM fstrim reclaimed free backing blocks; host free space was
about 743 MiB, so avoid needless large copies. Completed/gzipped diagnostics can
be decompressed if re-running those historical checks.


## Physical structure pass and atomic checkpoints — latest checkpoint

The previous goal turn made progress: optional snapshot serialization saved 358
mapped LUTs, tests/simulation passed, and the interrupted physical suite was
preserved and restarted from fresh SRAM with a detached runner. Commit 8a1bbc0.

The fresh physical structure replay now PASSES all 123,200 clocks and every one
of 626 public output bits for (CAR (CONS 7 (CONS 8 NIL))). Elapsed 3,069.994 seconds.
Its result/log are structure-retry1-board-result.json / structure-retry1-board-replay.log
under serializer-byte-move; load-structure-retry1-result.json records a fresh
successful SRAM load of dd259c97... first. The older interrupted prefix remains
separate and is NOT counted. Combined complete application, structure and queued
lifecycle traces total 134,901 physical clocks. red2-physical-structure-results.json
records completed evidence/hashes and scope.

Trace-input analysis also verifies that all graph writes are in bootstrap
(clocks 0–255), the initial state is loaded once at 256, literal metadata ends at
507, and every later structure input is only CLOCK or observational NOP. Graph
updates and reduction run in the dedicated FPGA engine, not in host commands.
The input pattern record is build/red2-basys3-datapath/trace-input-patterns.json.

The detached suite PID 6443 is still LIVE and has advanced to addition; signed
addition and EVEN? -2 follow. Each has a fresh SRAM load and unique *-retry1 files.
Do not interrupt or start another serial client. Revalidate the actual PID/command
and current case log rather than treating this note as proof of liveness.

host.py now creates an exclusive atomic .progress.json sidecar every 100 confirmed
clocks and at termination. It contains PID, trace identities, elapsed time,
running/passed/failed state and compared_clocks. Temp-file writes/fsync/rename keep
the prior valid checkpoint on an interrupted or failed update. It is a lower bound
and explicitly NOT a UART resume token. A hard-kill test waits for an explicit
CHECKPOINT_READY marker, then kills the child and verifies its count survives;
other tests cover exclusive reservation, failed writes and mismatch accounting.
All 27 focused tests and Ruff pass. Structure started with the older host process;
the current arithmetic process uses the new host and already publishes valid
add-retry1-board-result.progress.json checkpoints. FPGA commands/comparisons are
unchanged. The interrupted old run's empty final record motivated this change.

Snapshot build PID 10833 / Podman red2-snapshot-route is still routing the separate
17,786-LUT experimental image. Its last recorded iteration 2 has 24,836 overused
resources; the one-hour route watchdog remains in force. Do not restart merely
because logs are quiet. Check actual PID/container status; no snapshot bitstream
has been loaded. Route/timing/physical replay are still unproven for this variant.
The objective remains active; arithmetic and snapshot physical checks remain.

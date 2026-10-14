# RED2 current hardware checkpoint

The objective remains active: improve dedicated RED2 hardware while preserving
its semantics. More cycles and fixed hardware control ROMs are acceptable; a
general-purpose CPU running RED2 firmware is not. Use enhanced PipelineC.

## Qualified hardware

The core source remains
`f97b169a1610f0235fed2bf3f701d3989e1567daa97ce668a36cc2e5403195e8`.
The new optional burst-clock image is built, routed, physically qualified and
**loaded on the Basys 3**. Bitstream SHA256:
`5e88122cefd085717d63258192d5fd60f3b9ab10e2ed8bc0e71d5c088b8a8df5`.

It uses 17,932 physical LUT sites (2,868 spare). Routed timing passes the 10 MHz
target at 10.45 MHz core and 10.67 MHz monitor, with no hold violations. Mapping
is 18,215 LUTs, 8,545 FF, 34.5 BRAM36 equivalents and 20 DSPs. The frontend adds
71 mapped LUTs and 20 FF; the routed site count also reflects packing/placement.
All 33,222 cell placements survive routing.

All five programs plus queued lifecycle passed after a fresh SRAM load per case:
232,008 executed clocks, comparing all 626 bits at 6,927 packet endpoints. The
last load is `load-even-negative-result.json`. Host replay elapsed was 159.554
seconds total versus 5,689.291 seconds for the earlier per-clock checks. This is
a sampling/transport improvement; the configured kernel clock remains 10 MHz.
The independent prior image compared every output on every clock for this same
corpus. Do not claim burst endpoints establish intermediate-output comparison.

Everything is in `build/red2-basys3-burst-prepared`. Build driver PID 74444 and
qualification watcher PID 84024 have **finished**. Their progress, driver logs,
build manifest, final timing/fit audit and all six physical result/load/replay
records confirm success. No serial replay client remains from this suite.
`red2-burst-clock-results.json` records verified artifacts and result scopes.

The default Basys recipe selects the qualified shared datapath with the guarded
eight-pair response-byte relocation. Burst delivery remains optional. Default
preparation reproduces eight hardware inputs from the prior single-clock image
byte-for-byte; see `red2-basys3-default-recipe-results.json`. The maintained
production machine source remains a separate reference. A fresh default full
build is not claimed; the complete optional burst build is now qualified.

Use `/dev/cu.usbserial-2101837357871`, board serial `210183735787`. SRAM only,
never flash. Before any new hardware work, inspect current processes and image
load records; do not infer external board state solely from this checkpoint.

## Arithmetic sharing experiment

An isolated compare/subtract fusion proved equivalent for all 128 input bits
using Yosys SAT. It saved one LUT and 15 CARRY4 blocks. This is not a substantial
LUT reduction; no qualified source changed. See
`red2-divider-subtract-probe-results.json` and its preserved RTL/log artifacts.

The larger candidate is `build/red2-arithmetic-sharing/div-loop`, with
`MICRO_U64_DIV` appended to the existing extra-state configuration. It moves the
divider iteration onto the existing shared hardware engine, preserving source
operations and accepting additional physical cycles. Oracle and controller
generation passed. Initial integration failed because `scalar_core.py` used the
removed divider handler as an insertion anchor. The helper now locates the next
retained source-ordered dispatch handler. Three regression tests and the existing
18 partition checks pass. Regeneration of the normal configuration reproduces
**exactly** the qualified f97 source; see `default-identity/integrated-stream`.

The new divider candidate successfully integrates with 124 entries, 14,893
compact rows, 1,024 scratch words and 16,384 control-index words. The prior
configuration has 123 entries and 14,846 rows with the same capacities. Both have
200 private and 175 shared words.

Complete core synthesis **finished**: 16,870 LUTs including LUT RAM, 6,343 FF,
34.5 BRAM36 equivalents, 20 DSPs and 702 CARRY4. Against the qualified core this
saves **396 LUTs**, two FF and 34 CARRY4. Enhanced compiler manifest, mapping
scripts and Yosys/GHDL versions match; all generated HDL hashes were checked.
This is a core result; no new board mapping or routing is established.

Native validation driver 5183 **finished successfully**. It passed 15,032 typed
comparisons with all 152 mandatory integer corners, 699 selected complete-top
boundary witnesses across all 124 entries, lifecycle/accepted-metadata and
poisoned queued-payload checks, then multiply/divide/modulo/exponent program
parity. Selected witnesses do not establish exhaustive ISA coverage.

The RTL model is built from the exact measured frontend. Driver PID 30841
**finished successfully**: all 11 fresh native/concrete checked public-port
program traces pass Verilator replay, **518,097 simulated clocks with every
626-bit output compared on every clock**. The public lifecycle trace adds
1,018 clocks with the same comparison scope.

Mapped-primitive driver PID 42732 **finished successfully**: lifecycle,
application, division, modulo and large-magnitude division all pass, comparing
all 626 output bits on every recorded clock. Board watcher PID 43260 verified
all exact-source receipts and wrote the immutable, provenance-pinned
`synth-red2-shared-divider-results.json`. Do not edit that report while its build
is running: preparation and build pin its SHA256.

The fresh optional burst build is in `build/red2-basys3-shared-divider`. Board
build driver PID 61335 (`run-physical.py`) maps the complete board to **17,819
LUTs**, 8,543 FF, 34.5 BRAM36 equivalents and 20 DSPs. That saves 396 mapped LUTs
and two FF versus the qualified burst image. Placement is running with the same
pinned backend and response-byte relocation. Routing/timing and physical replay
remain unproven. Inspect `physical-progress.json`, `build-driver.log`, backend
logs and actual process/container state. The watcher/build does **not** program
the board. SRAM replay remains authorized after successful fit/timing gates.

See `red2-arithmetic-sharing-integration-results.json` and
`red2-shared-divider-resource-attribution.json`. Generation's first
`progress.json` describes the preserved failed anchor attempt; successful
integration is in `integration-retry.log`. No new routed or physical result is
established for this candidate yet. Keep the qualified image available.

## Saved equality semantics

The original instrumented probe finished without localizing its fault. The
unmodified qualified-core state probe (driver 40245, child 40246) has now also
**finished** and captured the exact state: shared entry 60
(`MICRO_JOIN_PRIM_META_SCAN`), halted engine PC 4447, scratch slot 68 value 49
(`__EQUAL_IF__`), metadata cursor 42, dirty hw_fault/microstate payloads both 3.
The unchanged production-source probe independently captured the same primitive
in microstate 60 immediately before the fault at architectural commit 41.
The cause is missing saved-JOIN dispatch for special bit 4. See
`red2-list-equality-diagnostic-results.json`.

The maintained source is now
`75ccb12f1bb8669e54c28f21ffdf3d2fa41c94da3bf49400afac3acaafebb651`.
It shares ordinary IF handling for saved private equality IF, stages inline and
terminal EP RAM writes through new microstate 144, and preserves live argcnt on
equality completion. The dedicated gate `scripts/check_syn_equality_if.py`
passes 26 saved-IF fixtures and four full list-equality programs. All graph and
control RAM words are compared for every fixture; full programs compare every
architectural commit and expected changed RAM words. Fourteen focused static/
scalar-fallback tests and Ruff pass. `red2-equality-if-results.json` pins evidence.

These are **native** semantic results; no RTL, area or board qualification exists
for the maintained-source revision. Direct/EP private primitive firing remains
separate and unsupported. The f97 loaded image and frozen e6 divider candidate
still retain the earlier equality gap. Do not merge their resource/physical
receipts with this semantic revision.

The combined candidate is in `build/red2-equality-integrated/shared-divider`.
Its configuration starts with shared-divider flags and also extracts
`MICRO_JOIN_IF_INLINE_WRITE` onto the fixed hardware engine. Generation/typed
driver PID 60899 **finished successfully**: 125 entries, 14,982 compact rows,
1,024 scratch words, 200 private and 176 shared words; **15,152 typed comparisons
with mandatory integer corners pass**. Combined source SHA256:
`202f71828d84269d7f491dab383753473fa0bc0de89ee796bc073de9c3dda68b`.
See `red2-equality-shared-divider-integration-results.json`.

Two exact-source gates are running via `run-next-gates.py`: enhanced RTL frontend
driver PID 62772 (mode `frontend`) and complete-top native driver PID 62773 (mode
`native`). The latter runs all boundary/lifecycle witnesses, then records fresh
public-port native/concrete traces for equal/unequal simple and nested lists.
Inspect `frontend-progress.json`, `native-progress.json`, driver/stage logs and
actual process identity before waiting or retrying. Program traces require a
successful exact-source frontend. No new RTL replay, area map or board result is
claimed for this combined source. It still needs appropriate arithmetic/public
lifecycle traces, RTL/mapped replay, complete map and physical qualification.

## Artifact storage

Completed simulation binaries were losslessly compressed with original/archive
hashes in `build/red2-burst-corpus-check/simulation-archives.json`. Historical
nonselected ablation JSON intermediates were also archived;
`red2-ablation-archives.json` pins original/archive hashes and restore commands.
Qualified dirty-writeback and board inputs were untouched. The JSON archive
saved 333,412,535 logical bytes. Guest cache references initially held reclaimed
space; `podman machine ssh sudo sysctl -w vm.drop_caches=3` released unused
references without restarting active workers. No historical IL archive completed.
Keep qualified inputs intact and verify archive hashes before restoration.

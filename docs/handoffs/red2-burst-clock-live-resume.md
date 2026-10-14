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
200 private and 175 shared words. No complete-core LUT saving or RTL/physical
parity is established for the new candidate yet.

The initial typed run passed 14,880 comparisons. The full run with mandatory
integer corners now passes 15,032 comparisons and retains all 152 corner
witnesses. Validation driver PID 5183 (`run-validation.py`) is running all
boundary witnesses and poisoned lifecycle next, then multiply, exact divide,
modulo and exponent programs.
Its authoritative files are `validation-progress.json`, `validation-driver.log`
and stage-specific logs. **Revalidate process identity and actual logs** before
waiting or restarting. The earlier PID 2300 typed checker has finished.

See `red2-arithmetic-sharing-integration-results.json`. Generation's first
`progress.json` describes the preserved failed anchor attempt; the successful
retry is in `integration-retry.log`. No area/RTL/physical claim is made for this
candidate. Require enhanced-compiler RTL, complete-core mapping and appropriate
replay before promotion. The qualified FPGA image must remain available.

## List-equality gap

The native-only diagnostic PID 79880 has **finished**. It reproduced the fault
before architectural commit 41: red2=0, hw=3, microstate=3, PC=62, direction=1.
Its extra diagnostic register stayed zero, so it did not locate the retained
legacy assignment that emitted the fault. The shared-control path needs further
location work. See `red2-list-equality-diagnostic-results.json`.

The instrumented copy and `probe-site.log` are in
`build/red2-list-equality-diagnostic`. It was never synthesized or loaded; its
extra register/status field is diagnostic only. The earlier dynamic-print
attempt was rejected during native pipeline elaboration and is not a semantic
reproduction. The unqualified expression is
`(EQUAL? (CONS 7 NIL) (CONS 7 NIL))`. Passing other programs does not close this gap.

Disk space remains tight. Completed simulation binaries were losslessly
compressed with original/archive hashes recorded in
`build/red2-burst-corpus-check/simulation-archives.json`. Keep all qualified build
inputs intact; preserve historical intermediate artifacts through verified
lossless archives when more space is needed.

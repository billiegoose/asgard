# Live Basys 3 bring-up checkpoint

User authorization: load dedicated RED2 hardware into volatile SRAM on this Mac,
run physical replay, commit and push. No CPU emulation, no flash write.
Permissions work. Board serial `210183735787`, JTAG ID `0x0362d093`, UART
`/dev/cu.usbserial-2101837357871`. **SRAM loading works; the full application has not passed on hardware yet.**

## Current attempt

Routing completed in `route-timing-10mhz`: core 10.39 MHz and monitor 10.35 MHz,
both PASS at 10 MHz. It uses 19,984 physical LUT sites and preserves all 37,015
placements. Base bitstream SHA256:
`f8a97bd2508b4d7cd959bc4e6785bb01751e8fabe2526d8627c3fe796f869e7f`.
The base SRAM load succeeded, but replay failed at clock 257 on graph memory.

A confirmed backend bug omitted WRITE_WIDTH_A_18 on both RAMB18 halves of
RAMB36E1 WRITE_WIDTH_B=72 / WRITE_WIDTH_A=0. Adding exactly 14 configuration bits
for seven affected memories changed the 131-word physical graph-memory test
from 74 failures to zero. The corrected image is
`build/red2-basys3/bram72-width-fix/red2_basys3.bit`, SHA256
`160b9d3e1e978c9695589adbd1cf7c54143f73e9de74762b0f39d836f0c9b704`.
It preserves all routing. The matching source fix and regression are pushed in
fpgatool `f8da9ea`. Raw rebuilt backend:
`/nix/store/0apsy55ndakz03k2vzf1snhfwnbr6b0b-nextpnr-1.0.0/bin/nextpnr-himbaechel`,
SHA256 `e9fd42e7b779424725302bd79bbc1632ca8d87526dd0fac50daac44a8b4212fc`.
Old backend fails specifically on missing A-width markers; patched width test
and both saved-placement routing regressions pass.

The corrected physical application matches 3,999 clocks, then reports microstate
5 instead of 13 (only bit 3 differs initially). A reload/followthrough probe
repeats this failure; subsequent busy/dispatch behavior diverges too. Preserve
`bram72-width-fix/application-board-result.json` and `followthrough-result.json`.
The corrected 10 MHz image is still diagnostic, not an application pass.

The exact mapped core **passes all 10,703 clocks** with Yosys logic models and
Xilinx RAMB18E1/RAMB36E1 models. Sources, a lean gate-level export, simulation
bench and logs live in `mapped-sim/`; `replay.log` ends MAPPED_REPLAY_PASS 10703.
The full original export was 299 MB; `rename -hide; clean -purge` reduced names
and unused aliases to 5.7 MB without changing the circuit. The simulation took
about three minutes. This separates source/logic mapping from the remaining
packing/configuration/routing/physical issue.

The core cone extracted from the final mapped board netlist also **passes all
10,703 clocks**, with the same vendor RAM models. It cuts only the 722 command
register outputs and core clock, then retains the backward cone of all 626
results, including state inputs. It contains 28,839 cells and 8,095 FFs.
`mapped-board-sim/replay.log` ends MAPPED_REPLAY_PASS 10703. This rules out a
functional change introduced by mapping the core inside the UART board for
this trace; packing/configuration/routing/physical behavior remains to diagnose.

The 8.333 MHz clock probe completed and repeats exactly the same clock-3999
failure. It changes only six MMCM bits (divide 100 -> 120); UART is 96000.
Reducing frequency did not cure the fault. Hold timing remains a hypothesis,
not a demonstrated cause.

The passing mapped simulation reads scratch constant address 449 as 13 at clock
3970, writes 13 to scratch address 4 at clock 3973, and reads 13 back during the
bridge export at clocks 3996..4002. These intermediate values are simulation
observations only. Hardware has so far exposed the final microstate 5.

Two diagnostic images clone scratch RAM initialization into the graph monitor's
RAM in the same TDP36 read mode. Together, the valid probes read all 512 source
words 0..511 without a mismatch, including address 449 = 13. Each raw probe
attempted 512 host addresses, but only 0..255 are valid: the graph address is
eight bits and larger addresses alias. Preserve the raw reports, interpreting
only their first 256 rows. This validates initialization encoding in another
RAM location, not the live scratch write/read path.

The earlier `scratch-observer/red2_basys3.bit` diagnostic image has SHA256
`2fe79a9e9fbf374de7aa8fe7ad6ceb400b8a629855f4f61b782cbc1b81e2878c`.
It replaces thirteen graph readback bits (status 364..376) with scratch DI3,
DO3, ten address bits, and write-enable. Thirteen monitor LUT/FF pairs moved
into compatible control sets; no core cell placement or logic changed.

This image **passes all 4,050 scratch observations and all other output bits**.
At clock 3999, the physical microstate is now correctly 13. Hardware observes
the expected constant read, bit 3 at the scratch write, and bit 3 on readback.
`application-result.json` has null first_debug_mismatch and
first_output_mismatch. This is a diagnostic pass, not a full 626-bit application
pass, because thirteen graph readback bits were replaced.

The observer uses 19,991 physical LUT sites, preserves all 37,015 placements
from its modified placement input, and passes 10 MHz timing (core 10.68,
monitor 10.45 MHz). The model reports no hold violations. All 25,378 logic LUT
truth tables match the emitted FASM. All 5,835 RAMB18 configuration/INIT feature
lines exactly match the old corrected image; no additional RAM settings changed.

**Current board SRAM contains `normal-monitor-fullroute/red2_basys3.bit`**,
SHA256 `00bc146d22f16b0819bc0a1a0e6b6d30eae58bd184980e2c967c9d8923a88194`.
This restores all thirteen normal graph readback bits and routes afresh from
the observer's saved placement. Core and monitor placements stay as in the
passing observer. It uses 19,991 physical LUT sites, passes 10 MHz timing (core
10.57 MHz, monitor 10.45 MHz), and passes all 25,378 logic LUT truth-table checks.

Physical replay compares all 626 bits successfully for 7,506 commands, then
fails at clock 7,506: graph readback is zero instead of
`0x462000000000000000000f7`, with status 4 instead of 0, fault 1 instead of 0,
and microstate 3 instead of 1. A fresh SRAM reload and replay repeats the exact
failure. Preserve `application-board-result.json` and `confirm-board-result.json`.
Both runners have stopped. This is progress past clock 3,999, not a full
application pass or proof of a specific routing defect.

`scripts/boards/red2_basys3/relocate_monitor.py` reproduces the thirteen monitor
LUT/FF moves from `route-bounded/board-placed.json` without changing any logic.
Its guarded output has exactly the same 37,015 cell dictionaries as
`normal-monitor-fullroute/normal-placed.json`; Ruff passes. The default build
does not use this experimental placement recipe.

**Active experiment:** `ram-phase-isolation/` inserts negative-edge registers
on variable synchronous BRAM inputs and outputs, clocked by the free-running
monitor clock. RAMs retain the gated core clock. This tests RAM boundary timing;
unmodeled hold timing is a hypothesis, not an established cause. It requires
enough monitor edges between commands for both register layers to settle, as
the UART monitor provides. It is not a drop-in change for a continuously
clocked core. It also changes placement and MMCM settings, so a hardware pass
would not by itself identify the precise cause.

The experiment **passes all 10,703 commands and all 626 output bits** in mapped
simulation with Xilinx RAM models. Dead-code cleanup leaves 2,217 extra FFs:
12,492 FFs total, the same 20,050 mapped LUTs, 20 DSPs and 34.5 BRAM36 equivalents.
The MMCM uses multiplier 6 and output divider 120: 5 MHz and UART 57600 baud.
Placement is running in container `red2-phase-place-valid`; inspect
`ram-phase-isolation/place.log` and `place-driver.log`. The `complete.sh` runner
(tool session 18636) waits for placement, then routes, gates physical LUT fit,
5 MHz routed timing and LUT truth tables, builds, loads SRAM and replays all
626 bits. Inspect `complete-driver.log`, `route.log`, then
`application-board-replay.log` and its result JSON. It stops on failure and
does not retry UART commands. Do not start another serial client while this
runner is active. No new hardware image has been built or loaded from this
experiment yet. Its `replay-board.py` sets the standard termios 57600 baud rate
before the first exchange; the maintained host default remains 115200.

Routed-JSON resume experiments (`route-restored-hold/` and
`restored-monitor-route/`) were stopped before completing an iteration. They
were not accepted as route results. Re-import needs native BEL/site-wire names,
removal of unused LUT pins added during final physical legalization, and
clearing already-bound clock routes; it may still have other issues. Use the
known-good saved placement for current work. Normal route outputs now go to
container /tmp and are copied out only when complete, avoiding slow per-line
Mac shared-filesystem exports.

The diagnostic fast FASM reader (`fast-fasm2frames.py`) retains the pinned
Project X-Ray frame assembler and rejects unsupported syntax. On the original
710k-line FASM it produced byte-for-byte identical board.frames; validation log
ends FAST_FASM_BASELINE_EXACT_MATCH. The observer and normal restoration use
this verified reader for faster frame generation. Original models/logs and
failed attempts are preserved; some bulky diagnostic files were losslessly
compressed to recover disk space. VM fstrim recovered additional host space.

The initial autonomous runner is stopped after the comparison failure. Its
`complete-bringup.log` records the initial load and failure. Later probes use
fresh load/replay paths; no implicit UART retries or flash writes. Build hashes
are checked before each SRAM load. Original inputs and failures remain intact.
New maintained builds automatically use the BRAM fix through fpgatool.

Asgard `7c5b290` already contains resource attribution, SDC reload, physical BEL
normalization, and 9 focused tests. Additional handoff evidence and the fpgatool
pin were committed in Asgard `279beb0`. The native XDC clocks are
lost across saved JSON import, so the route reloads SDC. A small two-test probe
confirmed the resumed 10 MHz target with the delay model enabled and disabled.
Do not import final routed JSON directly: its normalized site names are not
round-trip safe; use the original saved placement.

The prepared root `build/red2-basys3/` preserves all original mapped inputs and
hashes. Its mapped board uses 20,050 LUTs including LUT RAM. Actual placement
uses **19,984 physical LUT sites**, leaving 816 spare. The alternate spread
placement uses 20,228 sites, leaving 572 spare. These count distinct physical
LUTs after merging O5/O6 halves within the same tile/slice/letter. The final
routed design is audited again before bit generation, including any new buffers.
The shared 50T database's larger capacity is not the nominal Basys 3 budget.

## Diagnosed backend issues and verified fix

- Preserve the package-bearing `xc7a35tcpg236.bin` alias; resolving its symlink
  selected a die without the package and asserted before placement.
- nextpnr aligns shorter clock names with whitespace; timing parsing needs
  `clock\s+`, and must require both final clock results.
- Imported JSON settings overwrite matching CLI settings. A saved
  `router=default` silently overrides `--router router1`. Router-only retries
  must deliberately set/remove that saved setting if changing algorithms.
- **Important:** the Xilinx backend builds its measured delay model in
  `prePlace()` only. A saved-placement `--no-pack --no-place` retry skipped it,
  falling back to a different delay formula and badly regressing congestion.
  fpgatool commit **f5d6dba** restores the model/options in the resumed
  `preRoute()` path. The old counter regression fails for exactly this missing
  model; the patched backend passes both model-on and explicit-off cases.

The backend fix and tests are pushed on fpgatool's existing
`codex/pypeline-register-reannotations` branch. PipelineC lowering and the RED2
circuit were not changed by this backend fix.

Patched executable:
`/nix/store/7anbqfygsd5dx69naa368sln2430nhsn-nextpnr-1.0.0/bin/nextpnr-himbaechel`
SHA-256: `df4a16a9a3a6341a0cb61c842f4d976207243cffed8dd3b21f72656107625a59`.
Reuse the existing DB at
`/nix/store/v2764cclyfrslx741fg1b906rfnnpmix-fpgatool-basys3-himbaechel-chipdb-1.0.0/xc7a35tcpg236.bin`.
Its format/data are unchanged. Build used only `#nextpnr-patched`, avoiding DB
regeneration. `original-fpgatool/toolchain/` inside the prepared root is an
export of f8b237d, used for the unchanged bit-generation tools and Yosys tests.
**Use that frozen shell for finishing; developing the updated full flake would
regenerate the chip database and needs more disk space.**

Regression logs: `resume-regression-driver.log`, `resume-regression-old.log`,
`resume-regression-new.log`, `resume-regression-toolchains.sha256` in the
prepared root. Old failure reproduced; new 2 tests pass. Ruff passes.

Stopped attempts are preserved: original unbounded route diverged after
bottoming near 100 conflicts; both model-less bounded retries plateaued around
10,000+ conflicts. SA failed relative-chain placement. The correctly selected
router1 trial was stopped without its measured model. An initialization-only
fixed-BEL workaround rebuilt the matrix but failed partial carry placement;
it never produced a bitstream. No functional RED2 failure is established by
these backend attempts. The previous runner stopped when its jobs were halted;
its log is `complete-bringup-before-resume-fix.log`.

## Completion and validation

Require the corrected route's normal completion marker, zero router overuse,
final timing PASS at 10 MHz for both `clock` and `core_clock`, and final
physical LUT count <= 20,800. `finish-selected.sh route-resume-fixed` additionally
checks that original cells retain their saved BEL locations, then records
artifact hashes in `build-result.json`. Use the frozen original-fpgatool shell.
`program.py` verifies those hashes and writes exclusive `load.log` and
`load-result.json`.

The runner then executes:

```sh
/usr/local/bin/python3 -u scripts/boards/red2_basys3/host.py \
  --port /dev/cu.usbserial-2101837357871 --prepared build/red2-basys3 \
  --log build/red2-basys3/application-board-result.json \
  build/red2-basys3/application-vectors.txt \
  > build/red2-basys3/application-board-replay.log 2>&1
```

Require `BOARD_REPLAY_PASS 10703` and completed_pass=true. This compares all 626
output bits each clock for `((LAMBDA (x) x) 7)`. If delivery is uncertain, reload
before a retry and use fresh result paths. After success, update the handoff
JSON and READMEs with actual timing/load/replay results and hashes. Put the
successful reproducible two-stage placement/routing flow into maintained
`implement.sh`, then commit and push Asgard. Stop any redundant jobs.

Earlier validation: 7 focused pytest cases, UART digital simulation including
CRC/padding/framing/timeout/sequence checks, and 10,703-clock real optimized RED2
monitor RTL replay. Core validation previously passed 232,090 clocks across
five programs. Existing list-equality gap remains open. This is a dedicated
hardware processor monitor; an interactive THOR host adapter remains future work.

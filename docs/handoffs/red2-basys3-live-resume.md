# Live Basys 3 bring-up checkpoint

User authorization: load dedicated RED2 hardware into volatile SRAM on this Mac,
run physical replay, commit and push. No CPU emulation, no flash write.
Permissions work. Board serial `210183735787`, JTAG ID `0x0362d093`, UART
`/dev/cu.usbserial-2101837357871`. **No bitstream has been loaded yet.**

## Current attempt

`red2-basys3-route-timing-10mhz` is running. Host launcher:
`build/red2-basys3/route-timing-10mhz/route.sh`; exec session 74508.
It routes the unchanged saved default-density placement with the patched backend,
bounded expansion 12 and congestion increment 1.2, and explicit `--sdc board.sdc`.
Outputs are written inside the container then copied as completed files to avoid
hundreds of thousands of tiny writes across the Mac/VM filesystem boundary.

The earlier corrected route completed legally and preserved all 37,015 cell
placements, using 19,984 physical LUT sites. It reported 10.39 MHz core and
10.35 MHz monitor fmax, but FAIL at the unintended 12 MHz default: native XDC
clock constraints are lost across saved JSON import. The new attempt reloads
SDC after import to check the intended 10 MHz constraint directly. Original
logs/FASM/routed JSON remain in `route-resume-fixed`. A probe importing final
routed JSON crashed because its normalized site names are not round-trip safe;
use the original placed JSON. Do not load the earlier route on inferred timing.

The autonomous runner `build/red2-basys3/complete-bringup.py` is exec session
82044. Its log is `build/red2-basys3/complete-bringup.log`. It waits for the
explicitly constrained route, then runs `finish-selected.sh`, checks physical
fit/preserved placements and both routed 10 MHz clocks, generates the bitstream,
verifies build hashes, loads SRAM using `program.py`, and replays the application.
It stops on any failure. Do not run a second load/replay concurrently. It does
not automatically update docs, source, or Git results. Earlier runner failures
are preserved in `complete-bringup-before-*.log`.

The physical audit now uses `audit.py` plus the exact `tilegrid.json` to translate
generic tile-relative BELs to exported Xilinx site/BEL names, including typed
RAM/IOB BEL suffixes. It passed against the full completed route; focused tests
also exercise shared LUT halves, relative site coordinates and moved-cell
rejection. Maintained `implement.sh` now has two-stage placement/routing, SDC
reload and the corrected final audit. Prepared original source snapshots remain
unchanged; finishing records hashes of its new helper and scripts separately.

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

# Live Basys 3 bring-up checkpoint

The user authorized loading the dedicated RED2 hardware into volatile SRAM on
this Mac, replaying it, and committing/pushing results. Permissions now work.
The board is Digilent serial `210183735787`, JTAG ID `0x0362d093`, UART
`/dev/cu.usbserial-2101837357871`. No bitstream has been loaded yet.

Spread placement now passed its physical-site audit: **20,228 LUT sites**,
572 spare; 12.17/12.32 MHz placement estimates. Routing is active.
`finish-selected.sh` now independently audits the final routed physical sites
before bit generation, and records that audit in the build hashes.

The prepared, hash-verified build is `build/red2-basys3/`. Its complete mapped
board is 20,050 LUTs including LUT RAM. **Also check physical LUT-site occupancy
from saved placement before claiming final fit or programming.** nextpnr adds
carry helper LUT1 cells and counts O5/O6 half-sites separately. The nominal
Basys 3 limit is 20,800 physical LUT sites. The shared 50T database's larger
capacity is not the nominal Basys 3 budget.

Live Podman containers (independent output directories):

- `red2-basys3-route-spread`: most promising; alpha 1.0, beta 0.7,
  parallel refinement with 4 threads; analytical placement finished in 612s.
- `red2-basys3-route-bounded`: default-density placement, parallel refinement.
- `red2-basys3-route-sa`: slower independent SA placement fallback.

Both new attempts save `board-placed.json` before routing, then use
`--no-pack --no-place --router2-bb-expand-max 12 --router2-cong-mult 1.2`.
Their drivers and logs are under `route-spread/` and `route-bounded/` inside the
prepared build. Their exact scripts are `route.sh`; do not mutate active inputs.
Saved placement supports further router-only retries if needed.

The first heap attempt was stopped after unbounded router divergence: overuse
fell near 100 then rose to 349 at iteration 136. Its preserved log is
`board-route-package.log`. Placement timing estimates passed at 12.07/12.19 MHz,
but **these are not routed timing**. The initial earlier package assertion was
fixed by preserving the `xc7a35tcpg236.bin` symlink name instead of resolving it.
The timing parser also needs `clock\s+` because nextpnr aligns shorter names.
The maintained `implement.sh` has both fixes.

After one bounded/spread route succeeds:

1. Inspect saved physical placement and gate unique physical LUT-site count.
   Parse actual BEL names before normalizing O5/O6 aliases; do not count every
   SLICE_LUTX half-site as a separate 6-input LUT.
2. Require final routed timing PASS for **both** `clock` and `core_clock` at
   10 MHz, zero routing overuse, and normal backend completion. If routing
   fails, retain evidence and retry from `board-placed.json` with separate outputs.
3. `finish-selected.sh route-spread` (or `route-bounded`) in the pinned fpgatool
   Nix environment verifies original inputs and legal routed result, checks
   both clocks, produces canonical `red2_basys3.bit`, and hashes artifacts into
   `build-result.json`. This helper is in the prepared build directory; it also
   audits final routed physical LUT sites against the 20,800-site limit.
   Use the same Podman image/volume/mounts as `resume-package-host.sh`, mount the
   prepared root read-write as `/design`, and invoke the finishing helper there.
4. On the Mac, `python3 build/red2-basys3/program.py` verifies the build hashes
   and loads SRAM using the explicit serial. It writes exclusive `load.log` and
   `load-result.json`. No flash write. Do not rerun with occupied result paths.
5. Physical replay (input trace snapshot already validated and preserved):

   ```sh
   /usr/local/bin/python3 -u scripts/boards/red2_basys3/host.py \
     --port /dev/cu.usbserial-2101837357871 \
     --prepared build/red2-basys3 \
     --log build/red2-basys3/application-board-result.json \
     build/red2-basys3/application-vectors.txt \
     > build/red2-basys3/application-board-replay.log 2>&1
   ```

   Require `BOARD_REPLAY_PASS 10703` and completed_pass=true. This checks all
   626 output bits on every clock for `((LAMBDA (x) x) 7)`. If command delivery
   is uncertain, reload before retrying and use fresh result paths.
6. Stop redundant jobs after success. Update the handoff JSON and READMEs with
   actual routed/loaded/replayed results and hashes; commit and push. If a new
   routing configuration wins, put its reproducible settings and placement
   checkpoint stage into maintained `implement.sh` before the final commit.

Local validation already passed: 7 focused pytest cases; actual UART digital
simulation including CRC/padding/framing/timeout/sequence checks; 10,703-clock
real optimized RED2 monitor RTL replay. Earlier corrected core validation passed
232,090 clocks across five programs. Existing list-equality gap remains open.
This board interface is a dedicated hardware processor monitor, not an
interactive THOR host adapter. No CPU emulation is involved.

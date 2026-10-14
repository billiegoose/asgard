# RED2 on Basys 3

The first board target exposes the RTL-validated dedicated RED2 core through
115200-baud USB UART. It uses a 100 MHz to 10 MHz MMCM and a BUFGCE at the core
boundary. In default mode the core, including its synchronous RAMs, receives
exactly one rising edge per accepted command. Between packets it receives no
edges. This preserves
the public-port trace contract; continuously issuing CMD_NOP would still clock
synchronous RAM reads and would not reproduce the same trace.

The current dedicated core maps to **15,803 LUTs**, 6,170 flip-flops, 34.5
BRAM36 equivalents and ten DSPs. The complete burst board maps to **16,752
LUTs** and 8,370 flip-flops. Routing uses **16,368 physical LUT sites**, leaving
**4,432 spare**. Both domains pass the 10 MHz requirement: estimated maximum
12.82 MHz core and 12.76 MHz monitor.

The new image has passed physical function application, lifecycle handling,
signed multiplication, the equality checkpoint, full one-element list equality,
and graph construction/access. The wider arithmetic/nested-list corpus is still
being qualified. Every case starts with a fresh volatile SRAM load. Burst
replay compares all 626 public output bits at packet endpoints; intermediate
cycles are not individually observed. Expected-output origin and exact counts
are recorded in [the current board evidence](../../../docs/handoffs/red2-shared-multiplier-board-results.json).

The frozen [preparation gate](../../../docs/handoffs/synth-red2-shared-multiplier-results.json)
records 820 native boundary/lifecycle witnesses, 15 complete RTL/Concrete
programs, 26 saved-IF fixtures and four every-bit native-expected RTL/primitive
replays. Full duplicate native list traces remain independently tracked. The
current image uses corrected shared RAM requests and shared product hardware.

The earlier f97 image remains a preserved fallback: its single-clock board uses
17,997 physical LUT sites, and its burst board uses 17,932. It passed five
programs plus lifecycle handling. See [the earlier hardware evidence](../../../docs/handoffs/red2-complete-physical-corpus-results.json).
The final eight response-byte LUT/register pairs still use the verified
placement adjustment; earlier failures and their diagnostics remain preserved.

This is a processor monitor for bring-up. It does not execute RED2 in host
software, and it does not yet provide an interactive THOR CLI on the board.
Floating arithmetic is omitted and division is retained. Saved-JOIN list
equality is supported; direct/EP private primitive firing remains outside that
support. Finite graph/control memory and the other recorded profile limits
still apply.

New builds run `audit_bram.py` after routing and before frame generation. The
audit compares mapped known initialization bits, RAMB36 even/odd splitting,
width/SDP markers, clock polarity, output-register modes, write modes and
odd-width pairing flags with emitted FASM. It includes the existing SDP72
write-width correction. Eight regression cases and both the working burst
image and failed divider image pass this check. It does not establish routed
connectivity, frame conversion, timing or physical behavior. The build record
fingerprints the auditor and its result.

## Prepare and build

The recommended preparation uses the validated mapped candidate referenced by
`docs/handoffs/synth-red2-datapath-sharing-results.json`. It verifies the measured
netlist, candidate source and RTL replay adapter hashes before preparing a new
output directory. The netlist is already lowered by the enhanced PipelineC
compiler. Preparation moves its single BUFG to the board boundary as a BUFGCE;
all logic and memory cells are preserved. It does not rerun a different compiler.

```sh
python3 scripts/boards/red2_basys3/prepare.py \
  --output build/red2-basys3-next
bash build/red2-basys3-next/build.sh > build/red2-basys3-next/build-driver.log 2>&1
```

Defaults select the validated `dirty-writeback` candidate and the eight-bit
response-byte relocation recipe. `--report` and `--variant` select another
measured candidate; `--no-relocate-response-byte` explicitly disables the
adjustment. `--snapshot-response` selects the experimental snapshot serializer
and disables relocation. Burst delivery remains off by default.

Relocation moves only the eight final response-byte LUT/FF pairs after
placement, preserves the original placement, records every move and routes and
audits the selected copy. All resource, placement-preservation and timing gates
still apply. Default preparation reproduces the verified image's eight hardware
inputs byte-for-byte; the selected-placement recipe has separately reproduced
the verified placement byte-for-byte. A fresh full build through this recipe
still needs its own completed routing and hardware replay. The input-identity
check is recorded in [the default-recipe evidence](../../../docs/handoffs/red2-basys3-default-recipe-results.json).

Choose a fresh `--output` directory for each attempt; output directories are
not overwritten. The generated build runs the pinned fpgatool
Nix/OpenXC7 environment through Podman. It maps the wrapper, checks all board
resources, places/routes the pin-constrained design and requires passing routed
timing for both 10 MHz clock domains before generating a bitstream. Mapping and
routing are necessary: the measured 17,266 LUTs cover the core, not this wrapper.
`build-result.json` records the final artifact hashes after a successful build.

Placement is saved separately, then routing resumes with measured delays from
the patched nextpnr backend. Clock constraints are explicitly reloaded from
SDC using the actual packed clock-net names after importing the saved placement;
native XDC constraints are not retained in that JSON. The final audit checks physical LUT sites and unchanged cell
locations, accounting for nextpnr's different placed/routed BEL name formats.

Earlier diagnosis used `relocate_monitor.py` for thirteen graph-readback LUT/FF
pair moves in the previous normal-monitor route. It accepts an unrouted saved
placement, preserves logic and core cell locations, and writes a new placement
and move/hash report. It verifies the selected monitor load muxes and compatible
flip-flop control sets. This is a diagnostic recipe, not a general placement
fix or part of the default build. That earlier image failed at clock 7,506.
For the preserved local artifacts:

```sh
python3 scripts/boards/red2_basys3/relocate_monitor.py \
  build/red2-basys3/route-bounded/board-placed.json \
  --output /tmp/red2-monitor-placed.json --report /tmp/red2-monitor-moves.json
```

The prepared `core.json` is a snapshot; the generated build no longer depends
on the original `/tmp` netlist. Preserve the prepared directory if restarting
the Mac. The source measurement record retains the configuration needed to
regenerate the original experiment if those temporary artifacts are lost.

## Load and check the hardware

Load into volatile FPGA SRAM after a successful build:

```sh
openFPGALoader --board basys3 --ftdi-serial 210183735787 --write-sram \
  --bitstream build/red2-basys3-datapath/serializer-byte-move/red2_basys3.bit
```

The legacy `build/red2-basys3` image preserves an earlier wide-write error; new
builds and the working image above use the corrected fpgatool backend. Preserve
those historical diagnostics separately. No persistent flash write is involved.
Use the USB-UART channel, normally the
serial device ending in `1`, rather than the JTAG channel ending in `0`. On the
development Mac the observed UART path is `/dev/cu.usbserial-2101837357871`.

```sh
python3 scripts/boards/red2_basys3/host.py \
  --port /dev/cu.usbserial-2101837357871 \
  --prepared build/red2-basys3-datapath \
  --log build/red2-basys3-datapath/serializer-byte-move/new-application-board-result.json \
  build/red2-datapath-sharing/dirty-writeback/rtl-application/vectors.txt
```

The new application trace has 10,683 clocks and took about four minutes over
UART on this Mac. The host validates trace identity, hash, widths and row count
before sending the first command. Every 626-bit response must match. A sequence
or CRC mismatch, timeout or output mismatch aborts without retrying a command.
Reload the bitstream before restarting a replay if command delivery was
uncertain. A new result path is required, preserving earlier evidence. New runs also reserve
an atomic `.progress.json` sidecar, updated every 100 confirmed clocks and on
completion/failure. It records trace identity, PID and the last confirmed clock
count; a mismatch is never counted. After abrupt termination this is a lower
bound, not a resume token: fresh SRAM is still required for another replay.

Trace metadata also records where the expected outputs came from. Native
hardware-source traces and validated Verilator observations remain separately
labeled. RTL observations require a completed same-source Concrete RED2 program
gate and HALTED termination, plus model binary/manifest fingerprints. The host
rejects missing or inconsistent RTL validation metadata and preserves the origin
and semantic scope in the physical result. In burst mode the reported executed
clocks include intermediate cycles, while comparisons occur only at packet
endpoints; `compared_samples` gives that smaller count.

LD0 indicates MMCM lock, LD1 monitor readiness, LD2 core busy, LD3 core halted,
LD4 a hardware/RED2 fault, LD5 a sticky transport error, LD6 an active response,
and LD7 toggles for each executed command. Busy/halted/fault describe the core's
current public output; initial or intermediate states need not indicate a fault
in the transport.

## Local validation

```sh
python3 scripts/boards/red2_basys3/check.py \
  --output /tmp/red2-board-check-new \
  --core-top build/red2-datapath-sharing/dirty-writeback/integrated-stream \
  --vectors build/red2-datapath-sharing/dirty-writeback/rtl-application/vectors.txt
```

Icarus first exercises actual UART start/data/stop bits against an independent
core model: CRC rejection, abandoned-frame recovery, framing errors, sequence
wrap, full-width payloads and exactly one edge per valid frame. It then checks
the complete RED2 application trace through the monitor's byte interface and a
falling-edge clock-enable latch model. This second check uses the same optimized
GHDL/Yosys frontend RTL as the earlier independent Icarus replay. These are
digital simulation checks; they do not establish routed timing, analog MMCM
behavior or a physical-board pass.

## Wire format

Request: `a5 5a`, one sequence byte, 91 command bytes, two CRC bytes.
Response: `5a a5`, the same sequence byte, 79 status bytes, two CRC bytes.
Payloads and CRC bytes are little-endian. CRC16-CCITT uses polynomial `0x1021`
and initial value `0xffff`, covering sequence plus payload. Padding beyond the
722 input or 626 output bits must be zero. The status is sampled immediately
before the accepted command's core edge, matching the validated trace format.
An invalid request does not clock the core and receives no response. The host
waits for a complete response before sending the next command; there is no
packet queue or automatic retry.


## Physical memory and serializer diagnosis

After a fresh SRAM load into the initial idle state, run the walking-bit probe:

```sh
python3 scripts/boards/red2_basys3/diagnose_memory.py \
  --port /dev/cu.usbserial-2101837357871 \
  --prepared build/red2-basys3-datapath \
  --image build/red2-basys3-datapath/red2_basys3.bit \
  --load-result build/red2-basys3-datapath/load-result.json \
  --log build/red2-basys3-datapath/new-memory-diagnostic.json
```

This overwrites graph addresses 0–130 with zero, all ones, a mixed pattern and 128
walking ones. Two NOP/address commands settle each synchronous read. It records
every returned status, validates UART framing/sequence/CRC, and reports errors
both as graph bits and response-byte lanes. The image hash must match the
successful SRAM-load record, and the result file must be new. Reload SRAM before
independent application replay. This diagnostic does not prove RED2 reduction.

A clock-only 8.333 MHz probe, using `--baud 96000` on macOS, reproduces the new
image's clock 256 application mismatch. Its physical memory probe reveals three
response-byte lanes (1,2,7) always low across 393 responses; all 50 mismatching graph
words map to these lanes. This points to response serialization and changes the
next investigation from individual core outputs to the shared byte paths. See
[the diagnosis record](../../../docs/handoffs/red2-serializer-diagnosis-results.json).
That reroute now passes all 131 memory patterns and the complete physical
application and queued lifecycle traces. Its core logic and placement are
unchanged; the exact underlying backend failure remains unidentified.


## Experimental snapshot serializer

`prepare.py --snapshot-response` captures the 626-bit status once per command and
selects each payload byte by index. It preserves the request/response format,
CRC, padding and one core edge per accepted command. The legacy monitor source
and verified `--relocate-response-byte` recipe remain available; the two options
are mutually exclusive. The snapshot transform checks its ABI, frame bounds and
response writers before changing the prepared source.

The complete snapshot board maps to **17,786 LUTs**, saving **358 LUTs**, with the
same 8,525 flip-flops, 34.5 BRAM36 equivalents and 20 DSPs. UART waveform/CRC/
recovery/sequence-wrap simulation and the full 10,683-clock application monitor
simulation pass. All 23 focused tests pass. Its placement passes the 10 MHz gate;
routing hit its one-hour limit with 4,338 overused wires and produced no bitstream.
Physical replay remains unproven. This is experimental, not the currently
verified FPGA image. See [the measured record](../../../docs/handoffs/red2-snapshot-serializer-results.json).

```sh
python3 scripts/boards/red2_basys3/prepare.py \
  --report docs/handoffs/synth-red2-datapath-sharing-results.json \
  --variant dirty-writeback --snapshot-response \
  --output build/red2-basys3-snapshot-next
```


The completed physical structure result and unchanged dedicated-core identity
are recorded in [the structure evidence](../../../docs/handoffs/red2-physical-structure-results.json).
After bootstrap, its host trace supplies only CLOCK/NOP commands; graph reduction
and updates occur in the FPGA engine. The earlier interrupted attempt is retained
separately and is not counted as a complete pass.


## Complete physical corpus

The verified shift-serializer image passes all five programs (application,
structure creation/access, addition, signed addition and negative EVEN?) plus
queued lifecycle handling: **232,008 physical clocks**, with all 626 output bits
compared on every clock and a fresh SRAM load for each case. The image occupies
17,997 physical LUT sites and passes the 10 MHz routed timing gate. See
[the complete evidence](../../../docs/handoffs/red2-complete-physical-corpus-results.json).
This qualifies the recorded integer/256-word graph profile and these traces;
it does not establish exhaustive ISA coverage. The existing list-equality
execution gap remains.

## Counted CLOCK delivery (optional)

`prepare.py --burst-clock` adds a counted-clock controller to the UART frontend.
The dedicated RED2 core is unchanged. Wire opcode 10 carries a 20-bit count in
the 32-bit command value field (bits 311:280); valid counts are 1 through
1,048,575. The frontend forwards exactly that many consecutive copies of core
CLOCK (opcode 7, value zero), then returns the last **pre-edge** status, matching
the existing trace convention. Zero counts and counts with nonzero upper bits
are rejected without a reply or core edge. Normal requests retain their existing
one-edge behavior. The option is off by default and can accompany the verified
response-byte relocation recipe.

The host's matching `--burst-clock` option requires a provenance-checked prepared
image advertising this capability. It groups only adjacent identical, zero-value
CLOCK commands; NOP observations, other commands and differing fields retain
their individual transactions. Native opcode 10 is rejected before serial access
on burst-capable images. Burst result files record `executed_clocks` and
`compared_samples` separately: **only packet endpoints are compared**, unlike the
complete per-clock physical corpus above. Interrupted replay still requires a
fresh SRAM load; checkpoints cannot resume execution.

```sh
python3 scripts/boards/red2_basys3/check_burst.py \
  --output build/red2-burst-check-next
python3 scripts/boards/red2_basys3/check.py --burst-clock \
  --output build/red2-burst-application-next \
  --core-top build/red2-datapath-sharing/dirty-writeback/integrated-stream \
  --vectors build/red2-datapath-sharing/dirty-writeback/rtl-application/vectors.txt
python3 scripts/boards/red2_basys3/prepare.py \
  --report docs/handoffs/synth-red2-datapath-sharing-results.json \
  --variant dirty-writeback --relocate-response-byte --burst-clock \
  --output build/red2-basys3-burst-next
```

Exact-count simulation checks the minimum, maximum and intermediate counts,
contiguous core edges, the complete status payload and CRC, transmit stalls,
and invalid-count recovery. A physical counter/echo fixture also passes these
counts; that fixture contains no RED2 core. The complete burst-enabled RED2 image
now also passes all five programs and queued lifecycle on the Basys 3:
**232,008 executed clocks and 6,927 compared endpoints**, with all 626 bits checked
at each endpoint and a fresh SRAM load per case. The core receives consecutive
10 MHz edges within each burst.

This image uses **17,932 physical LUT sites** (2,868 spare) and passes the 10 MHz
routed timing gate at **10.45 MHz core / 10.67 MHz monitor**, with no hold
violations. Mapping is 18,215 LUTs, 8,545 FF, 34.5 BRAM36 equivalents and 20 DSPs.
The mapped frontend adds 71 LUTs and 20 FF; the physical site count also reflects
packing and placement. Its bitstream SHA256 is
`5e88122cefd085717d63258192d5fd60f3b9ab10e2ed8bc0e71d5c088b8a8df5`.
The recorded host replays took 159.554 seconds total, versus 5,689.291 seconds
for the separate per-clock checks: about 35.66 times less host elapsed time.
That comparison changes the sampling scope; the RED2 kernel and its configured
clock frequency are unchanged. See
[the burst evidence](../../../docs/handoffs/red2-burst-clock-results.json).

Load this specific image before using the burst host option:

```sh
openFPGALoader --board basys3 --ftdi-serial 210183735787 --write-sram \
  --bitstream build/red2-basys3-burst-prepared/red2_basys3.bit
python3 scripts/boards/red2_basys3/host.py --burst-clock \
  --port /dev/cu.usbserial-2101837357871 \
  --prepared build/red2-basys3-burst-prepared \
  --log build/red2-basys3-burst-prepared/application-next-result.json \
  build/red2-datapath-sharing/dirty-writeback/rtl-application/vectors.txt
```

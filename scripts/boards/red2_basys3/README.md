# RED2 on Basys 3

The first board target exposes the RTL-validated dedicated RED2 core through
115200-baud USB UART. It uses a 100 MHz to 10 MHz MMCM and a BUFGCE at the core
boundary. The core, including its synchronous RAMs, receives exactly one rising
edge per accepted command. Between packets it receives no edges. This preserves
the public-port trace contract; continuously issuing CMD_NOP would still clock
synchronous RAM reads and would not reproduce the same trace.

The dedicated core maps to **17,266 LUTs**; the complete board maps to
**18,144 LUTs**, with 8,525 flip-flops, 34.5 BRAM36 equivalents and 20 DSPs.
The working image uses **17,997 physical LUT sites**, leaving **2,803 spare**.
Both domains pass the 10 MHz gate: core 10.05 MHz and monitor 10.51 MHz.

The FPGA now passes all **10,683 clocks and 626 output bits** of the dedicated
RED2 function-application trace `((LAMBDA (x) x) 7)`, plus 1,018 queued public
lifecycle clocks and 131 graph-memory patterns. A controlled move of the final
eight response-byte LUT/register pairs removes the three missing serializer
lanes seen in the original placement. All core logic and placements are
unchanged. The exact backend cause is unresolved; the opt-in build recipe
reproduces the selected placement byte-for-byte. Broader physical structure and
arithmetic checks continue. See
[the working-image record](../../../docs/handoffs/synth-red2-basys3-working-application-results.json).
Earlier failed images and diagnostics remain preserved in their dated reports.

This is a processor monitor for bring-up. It does not execute RED2 in host
software, and it does not yet provide an interactive THOR CLI on the board.
The host sends previously compiled command vectors and compares every output
bit. The existing supported-profile limitations still apply, including the
recorded list-equality execution gap.

## Prepare and build

The recommended preparation uses the validated mapped candidate referenced by
`docs/handoffs/synth-red2-datapath-sharing-results.json`. It verifies the measured
netlist, candidate source and RTL replay adapter hashes before preparing a new
output directory. The netlist is already lowered by the enhanced PipelineC
compiler. Preparation moves its single BUFG to the board boundary as a BUFGCE;
all logic and memory cells are preserved. It does not rerun a different compiler.

```sh
python3 scripts/boards/red2_basys3/prepare.py \
  --report docs/handoffs/synth-red2-datapath-sharing-results.json \
  --variant dirty-writeback --relocate-response-byte \
  --output build/red2-basys3-next
bash build/red2-basys3-next/build.sh > build/red2-basys3-next/build-driver.log 2>&1
```

Defaults still select the older scalar-core record; use the explicit report,
variant and placement flag above for the recorded working recipe. The flag
moves only the eight final response-byte LUT/FF pairs after placement, preserves
the original placement, records every move and routes/audits the selected copy.
All ordinary resource, placement-preservation and timing gates still apply.
A fresh full build through this flag has not yet been physically replayed.

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
uncertain. A new result path is required, preserving earlier evidence.

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

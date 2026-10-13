# RED2 on Basys 3

The first board target exposes the RTL-validated dedicated RED2 core through
115200-baud USB UART. It uses a 100 MHz to 10 MHz MMCM and a BUFGCE at the core
boundary. The core, including its synchronous RAMs, receives exactly one rising
edge per accepted command. Between packets it receives no edges. This preserves
the public-port trace contract; continuously issuing CMD_NOP would still clock
synchronous RAM reads and would not reproduce the same trace.

The latest dedicated core maps to **17,266 LUTs**, saving 1,906 from the previous
candidate. It passes all 701 boundary cases and 230,990 RTL program clocks plus
1,018 public lifecycle clocks. Its complete board maps to **18,144 LUTs**,
leaving **2,656 spare** (12.8%). It uses 8,525 flip-flops, 34.5 BRAM36 equivalents
and 20 DSPs. Placement and routing complete in about 15 and 14 minutes.
The routed design uses **17,992 physical LUT sites**, leaving 2,808, and passes
10 MHz timing (core 10.14 MHz, monitor 10.62 MHz). The bitstream loads into SRAM,
but application replay first differs at clock 256 (`busy` expected high, actual
low); a fresh reload reproduces it. A 300-command diagnostic also sees graph-read
bit 449 differ. LUT INIT audit passes all 23,246 logic LUTs. Root cause remains
unresolved; see [the physical result](../../../docs/handoffs/synth-red2-datapath-board-results.json)
and
[the board mapping record](../../../docs/handoffs/synth-red2-datapath-board-map-results.json).

The previous candidate's complete board maps to **20,050 LUTs** including LUT RAM, leaving 750 of
the Basys 3's 20,800 LUTs spare. It uses 10,275 flip-flops, 20 DSPs and 34.5
BRAM36 equivalents. The latest normal-monitor route uses **19,991 physical LUT
sites**, leaving 809; both domains pass the 10 MHz requirement (core 10.57 MHz,
monitor 10.45 MHz).
SRAM loading and physical UART work. A nextpnr wide-write configuration fix
makes all 131 graph-memory diagnostic words pass. Full application replay
now matches 7,506 clocks before a repeatable graph-memory/fault mismatch;
diagnosis continues.
The mapped core also passes all 10,703 clocks with Xilinx RAM simulation models.
The [resource overview](../../../docs/handoffs/red2-basys3-resource-overview.md)
details memory, register and arithmetic ownership and further sharing options.

This is a processor monitor for bring-up. It does not execute RED2 in host
software, and it does not yet provide an interactive THOR CLI on the board.
The host sends previously compiled command vectors and compares every output
bit. The existing supported-profile limitations still apply, including the
recorded list-equality execution gap.

## Prepare and build

The initial preparation uses the frozen mapped artifact referenced by
`docs/handoffs/synth-red2-cfg-scalar-core-results.json`. It verifies the measured
netlist, candidate source and RTL replay adapter hashes before preparing a new
output directory. The netlist is already lowered by the enhanced PipelineC
compiler. Preparation moves its single BUFG to the board boundary as a BUFGCE;
all logic and memory cells are preserved. It does not rerun a different compiler.

```sh
python3 scripts/boards/red2_basys3/prepare.py
bash build/red2-basys3/build.sh > build/red2-basys3/build-driver.log 2>&1
```

Prepare the new datapath-sharing candidate with:

```sh
python3 scripts/boards/red2_basys3/prepare.py \
  --report docs/handoffs/synth-red2-datapath-sharing-results.json \
  --variant dirty-writeback --output build/red2-basys3-datapath
```

Use `prepare.py --output build/red2-basys3-attempt2` for another attempt. Output
directories are not overwritten. The generated build runs the pinned fpgatool
Nix/OpenXC7 environment through Podman. It maps the wrapper, checks all board
resources, places/routes the pin-constrained design and requires passing routed
timing for both 10 MHz clock domains before generating a bitstream. Mapping and
routing are necessary: the measured 19,172 LUTs cover the core, not this wrapper.
`build-result.json` records the final artifact hashes after a successful build.

Placement is saved separately, then routing resumes with measured delays from
the patched nextpnr backend. Clock constraints are explicitly reloaded from
SDC using the actual packed clock-net names after importing the saved placement;
native XDC constraints are not retained
in that JSON. The final audit checks physical LUT sites and unchanged cell
locations, accounting for nextpnr's different placed/routed BEL name formats.

`relocate_monitor.py` reproduces the experimental thirteen monitor LUT/FF pair
moves used by the latest normal-monitor route. It accepts an unrouted saved
placement, preserves logic and core cell locations, and writes a new placement
and move/hash report. It verifies the selected monitor load muxes and compatible
flip-flop control sets. This is a diagnostic recipe, not a general placement
fix or part of the default build. The resulting hardware still fails at clock
7,506. For the preserved local artifacts:

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
  --bitstream build/red2-basys3/red2_basys3.bit
```

The original prepared bitstream preserves the failing wide-write configuration;
the corrected diagnostic image is in `build/red2-basys3/bram72-width-fix/`.
New builds use the fixed fpgatool backend. See the handoff result JSON for exact
image hashes and the current replay limitation. No persistent flash write is
involved. Use the USB-UART channel, normally the
serial device ending in `1`, rather than the JTAG channel ending in `0`. On the
development Mac the observed UART path is `/dev/cu.usbserial-2101837357871`.

```sh
python3 scripts/boards/red2_basys3/host.py \
  --port /dev/cu.usbserial-2101837357871 \
  --prepared build/red2-basys3 \
  --log build/red2-basys3/application-board-result.json \
  /tmp/asgard-area-next/cfg-integer-joins-regfix/rtl-application/vectors.txt
```

The application trace has 10,703 clocks. UART transport takes approximately
three minutes. The host validates trace identity, hash, widths and row count
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
  --core-top /tmp/asgard-area-next/cfg-integer-joins-regfix/integrated-stream \
  --vectors /tmp/asgard-area-next/cfg-integer-joins-regfix/rtl-application/vectors.txt
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

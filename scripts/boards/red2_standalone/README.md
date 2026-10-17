# Standalone RED2 on Basys 3

This board integration replaces the debug monitor with a flash loader and
hardware devices around the existing qualified dedicated RED2 engine. The host
compiles THOR before deployment; it does not execute reductions or service I/O
while the program runs.

The corrected finite-quantum image passed physical resource, memory and routed
timing checks at 10 MHz. It produced thirty physical UART dots from SRAM,
thirty after programming configuration flash, and thirty after a separate
configuration reset from flash. The observer sent no UART commands.
The implementation uses 18,467 physical LUT sites,
39.5 block-RAM equivalents and 12 DSPs.

The earlier four-dot fault was a control-stack underflow when reconstructed
IO-THEN began with an inline value. Its correction passed source, frontend
RTL and the sustained physical checks recorded below.
The earlier once-dot board qualification remains in
`docs/handoffs/red2-standalone-results.json`.

Finite-quantum validation and board qualification are recorded separately in
`docs/handoffs/red2-finite-quantum-results.json`. The frontend RTL checks produce
two clock-dots outputs across five hardware restarts, with a peak compacted
residual of 84 words, and preserve elapsed CLOCK across every restart.

- The program image is read from configuration flash at **0x220000**. The loader
  uses ordinary 03h SPI reads on the board's QSPI NOR, without changing flash
  modes or enabling writes.
- `CLOCK` returns a 64-bit integer count of milliseconds since successful program
  loading. At the first program run, the counter starts at zero; it keeps counting
  during UART waits and quantum reconstruction/restart. The 10 MHz board clock
  has 10,000 cycles per millisecond.
- `UART-TX` emits the integer argument modulo 256 on the physical USB UART at
  115200 baud, 8N1. `UART-RX` waits for an actual received byte, with a 16-byte
  receive FIFO. An empty UART is not EOF.
- `UART-TX-BYTES` validates a finite PAIR/NIL byte list before emitting its bytes.
  It follows the existing adapter's one-APP descriptor rule, rejects cyclic or
  malformed lists, and buffers up to 256 bytes, matching this board's graph size.
- Accepted device operations resume the same hardware engine with an encoded
  integer or NIL. They consume the current contraction budget without refreshing it.
- At quantum exhaustion the reducer continues its ordinary q=0 reconstruction
  until evaluation halts. A dedicated RTL supervisor then snapshots graph
  memory, copies reachable executable spines into a second RAM buffer, relocates
  APP/RBLOCK links, installs a STOP, and restarts at address zero with a fresh
  budget. Definition storage above the working arena keeps its original addresses.
  This controller has no CPU, firmware or host service loop.
- Restart resets architectural environment/control pointers and private transient
  state through LOAD_STATE. Unreachable graph/control words need no physical
  clearing. Internal publication generation counters survive LOAD_STATE, so stale
  scratch records cannot become valid again merely because the graph moved.

The flash image selects the budget; its default is 20. Graph/control/literal
capacities remain 256/256/64. A smaller budget may be required to finish
reconstruction within the working arena reserved by a particular program.
Use **5 for clock-dots**: a budget of 20 still reaches a graph/environment
collision in this small arena. With 5, the native hardware model produced repeated
dots with a peak compacted residual of 86 words.
Floating arithmetic is omitted; integer division remains. Capacity exhaustion or
an invalid residual raises an explicit fault. The Python models' additional
closed-scalar sharing policy is not part of this hardware change.

The capacity experiment in `docs/handoffs/red2-graph-capacity-results.json`
projects 42.5 block-RAM equivalents for 512 graph words, compared with 39.5
for 256. This is an isolated-memory estimate, not a larger-board qualification.
The 512-word native model produced ten dots with six restarts at quantum 20
and two restarts at quantum 50; the present 256-word model needs 26 at quantum 5.
With CLOCK advancing only every fourth call, the corresponding counts are
21 and eight restarts for 512 words, compared with 84 for 256 words.
The standalone controller and loader still require wider graph addresses before
that capacity can be used on the board. A direct 1024-word expansion projects
62 block-RAM equivalents and exceeds the device capacity.

The hardware IF exhaustion path restores both captured branch environments and
reconstructs both branches before restarting. This is necessary even when the
condition has already become a Boolean: exhaustion prevents IF contraction but
must not leave environment-dependent branches in the residual graph.

## Publication fix checkpoint

The v8 source fixes the EP-parent, APP-operator and flat-scan publication gaps.
Both full UART examples pass typed-source checks (alphanumerics at quantum 20,
Caesar at 5), and lowered RTL passes the original failing paths. The complete
board maps to 18,663 LUTs. Placement, routing, sustained RTL and physical
qualification are still pending; v6 remains installed and the default prepared
build has deliberately not switched. The updated source will fail the old
build's source-identity check until a compatible build is selected.
See `docs/handoffs/red2-uart-publication-fix-checkpoint.md` for the continuation.

## Build and deploy

Once the standalone hardware is installed, replace just its THOR program with:

```sh
mise run fpga examples/clock-dots.thor
mise run fpga examples/clock-dots.thor --quantum 5 --compile-only
```

The task compiles and checks the image against the qualified board build, uses
the pinned `tools/fpgatool` submodule's `program-data` command to write and verify
it at `0x220000`, then resets configuration to load it. Both compilation and image
checks finish before any flash write. The installed hardware configuration stays
in flash, and the new program persists across power cycles. No hardware synthesis
or host runtime is involved. Attach only one Basys 3 when programming.

The task selects budgets from `programs.toml`: **20 for alphanumerics**, **5 for
clock-dots and Caesar**, and 5 for unlisted programs. Override with `--quantum N`.
Either increasing or decreasing the budget can increase peak graph memory,
depending on deferred work. The new profiles await v8 physical qualification.
`--compile-only` saves and validates the image without accessing hardware.
Images, compiler metadata and programming receipts are kept in unique directories
under `build/red2-standalone/programs/`. Programming success means the flash was
verified and configuration reset succeeded; program behavior is checked separately
by observing its UART or status LEDs.

By default the task uses `build/red2-basys3-standalone-quantum-v6-seed2`; pass
`--prepared PATH` for another qualified, compatible standalone build. Its build
artifacts and mapped core must be available locally. The task assumes the matching
hardware is already installed; use the full deployment below to install hardware.

### Current program compatibility

`clock-dots` has passed sustained physical execution. The simple UART send/receive
fixtures also pass frontend RTL tests, but the full `uart-alphanumerics.thor` and
`uart-caesar-plus4.thor` examples currently fault in the installed v6 reducer.
Successful flash programming does not establish that a program will execute.
Check LD6 when a program produces no UART output.

Both full examples expose missing graph-publication cases during exhausted-quantum
reconstruction, reported as `HW_FAULT_EXECUTION_NOT_IMPLEMENTED`. Alphanumerics
first fails when a multiword result is returned through an EP parent; Caesar first
fails in `MICRO_JOIN_FLAT_SCAN` after receiving input. These are reducer coverage
gaps, not serial-terminal settings. Increasing quantum delays the alphanumerics
failure but does not fix it. The investigation and reproduction commands are in
`docs/handoffs/red2-uart-examples-diagnosis.md`.

To exercise these currently unqualified programs in frontend RTL simulation:

```sh
.venv/bin/python scripts/boards/red2_standalone/check.py \
  --output build/red2-uart-alphanumerics --case uart-alphanumerics
.venv/bin/python scripts/boards/red2_standalone/check.py \
  --output build/red2-uart-caesar --reuse-model build/red2-uart-alphanumerics \
  --case uart-caesar-plus4
```

These checks require the actual expected output and normal termination; they fail
on the current reducer. The Caesar test injects real serial bits for `Az09!` and
ESC, expecting `Ed09!` followed by halt. `--uart-examples` includes both programs
alongside the existing smoke cases. Ordinary smoke qualification keeps its
previous cases and adds a two-byte receive/echo check; this must not be
interpreted as full-program coverage.

### Installing hardware

Prepare and build the board from the recorded, validated core, then compile its
program:

```sh
.venv/bin/python scripts/boards/red2_standalone/prepare.py \
  --seed 2 --output build/red2-basys3-standalone-quantum-v6-seed2
bash build/red2-basys3-standalone-quantum-v6-seed2/build.sh
.venv/bin/python scripts/boards/red2_standalone/image.py \
  --prepared build/red2-basys3-standalone-quantum-v6-seed2 \
  --file examples/clock-dots.thor --quantum 5 \
  --output build/red2-standalone/clock-dots-quantum-v6.bin
```

Preparation preserves the qualified mapped engine and verifies its packed ABI.
The build uses the qualified image's cached, hash-pinned nextpnr backend and chip
database, with network access disabled. Changes to the core are lowered with the
verified enhanced PipelineC compiler; the board wrapper reuses that mapped core.
Placement and routing trials can set `--seed`, `--router2-bb-expand-max` and
`--router2-cong-mult` during preparation. These options change implementation
choices and are recorded in provenance; they do not change RED2 logic.
No chip database regeneration is needed. Mapping, physical resource checks,
routed timing and BRAM initialization audits must pass before a bitstream is
produced.

The compatibility exporter also configures static BUFG route-throughs used by
the router for data signals. The pinned native exporter omitted these settings,
which left 13 routed buffers disabled and aliased a graph-RAM address bit.
Completing their configuration fixed physical execution without changing HDL,
placement or routing. The build records every added feature and rejects
unqualified buffer modes. Resource and routed timing audits still apply.

For an exporter-only correction, `reuse_route.py --source OLD --prepared NEW`
can reuse a completed route after verifying identical HDL, synthesis recipes,
constraints and backend. Run `NEW/finish-reused-route-build.sh` afterward. The
qualified v4 image used this path; its configuration payload matches the
physically tested diagnostic repair exactly.

After a successful build:

```sh
.venv/bin/python scripts/boards/red2_standalone/deploy.py \
  --prepared build/red2-basys3-standalone-quantum-v6-seed2 \
  --image build/red2-standalone/clock-dots-quantum-v6.bin \
  --log build/red2-standalone/quantum-v6-deployment.json \
  --expected ".............................." --observe-seconds 900 --persistent
```

Deployment uses the sibling fpgatool's `program-data` command to program and
verify the reserved data area. It first loads the new hardware into volatile
SRAM and waits for the requested raw output without sending UART commands. After that
check does `--persistent` program and verify the FPGA configuration flash and test
startup and a separate reset from flash. Power removal/reconnection is a further
physical check; a JTAG-triggered configuration reset is not a power-cycle test.
On failure the script restores the qualified debug image in SRAM; the receipt
records which flash operations had already completed.

A serial terminal is optional for observing program output; the program does not
need one attached. Default board serial is `210183735787`, with UART device
`/dev/cu.usbserial-2101837357871`. Supply UART input after LD4 lights; bytes sent
during initial flash loading are discarded. Flash configuration itself takes
several seconds before program execution starts.

LEDs: LD0 UART transmit request, LD1 clock lock, LD2 board ready, LD3 elapsed-time
bit 9, LD4 program running, LD5 halted, LD6 adapter fault, LD7 command activity.

## Flash image

`RED2FLSH` version 1 has a 64-byte little-endian header:

| Offset | Size | Meaning |
| --- | --- | --- |
| 0 | 8 | ASCII `RED2FLSH` |
| 8 | 4 | Format version, 1 |
| 12 | 4 | Number of load commands, 1..1024 |
| 16 | 4 | Nonzero contraction quantum |
| 20 | 4 | Graph capacity, 256 |
| 24 | 16 | ABI-encoded NIL word |
| 40 | 4 | Payload length, command count times 91 |
| 44 | 4 | IEEE CRC32 of payload |
| 48 | 4 | PAIR literal ID |
| 52 | 12 | Reserved, zero |

The payload contains 91-byte little-endian packed commands using the qualified
722-bit public ABI, with six zero padding bits. Only LOAD_MEMORY, LOAD_CONTROL and
LOAD_LITERAL_META are accepted before one final LOAD_STATE. The loader performs
RESET and waits for initialization independently. Header/opcode/address/CRC
validation must finish before execution starts. The image's JSON sidecar retains
source, literal IDs, hashes and compiler/core identity.

## Validation

```sh
.venv/bin/python scripts/boards/red2_standalone/check.py \
  --core build/red2-finite-quantum/core-v6/integrated-stream \
  --output build/red2-standalone/check-new
```

This test combines the actual qualified engine's frontend RTL with the new
controller and a physical UART transmitter/receiver model. It checks clock-dots,
byte output, real-waveform byte input/echo, list output, inline IO sequencing, captured-variable IF,
repeated quantum restart, elapsed-time behavior and
corrupt-image rejection. Its test clock uses 100 cycles per millisecond to bound
simulation cost; hardware uses 10,000. Success terminates when expected output
appears, rather than treating a timeout as success. It does not replace physical
qualification or claim that the newly mapped/routed hardware has passed.

`restart_tb.v` exercises residual relocation, shared links, overlapping suffixes,
cycles, recursive bindings, static definition targets, metadata preservation,
restart registers and faults:

```sh
iverilog -g2012 -I scripts/boards/red2_standalone -s restart_tb \
  -o build/red2-standalone/restart-test \
  scripts/boards/red2_standalone/restart.v \
  scripts/boards/red2_standalone/restart_tb.v
vvp build/red2-standalone/restart-test
.venv/bin/python scripts/boards/red2_standalone/check_if_quantum.py
.venv/bin/python scripts/boards/red2_standalone/check_io_quantum.py
```

`flash_check.sv` separately checks the read command/address, every image byte and
backpressure against a serial flash model. Example:

```sh
iverilog -g2012 -s flash_check -o build/red2-standalone/flash-check.vvp \
  scripts/boards/red2_standalone/flash.v \
  scripts/boards/red2_standalone/flash_check.sv
vvp build/red2-standalone/flash-check.vvp \
  +image=build/red2-standalone/clock-dots.hex +length=28092
```

The `.hex` file contains one hexadecimal byte per line from the compiled binary.

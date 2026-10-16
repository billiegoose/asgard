# Standalone RED2 on Basys 3

This board integration replaces the debug monitor with a flash loader and
hardware devices around the existing qualified dedicated RED2 engine. The host
compiles THOR before deployment; it does not execute reductions or service I/O
while the program runs.

The first finite-quantum image passed physical resource, memory and routed timing
checks at 10 MHz, then faulted after four physical UART dots. The source model
reproduced a control-stack underflow when IO-THEN's first value was already
inline after reconstruction. The correction has passed ten dots and 26 restarts
in the source model; the updated physical build is being qualified.
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

The hardware IF exhaustion path restores both captured branch environments and
reconstructs both branches before restarting. This is necessary even when the
condition has already become a Boolean: exhaustion prevents IF contraction but
must not leave environment-dependent branches in the residual graph.

## Build and deploy

Prepare and build the board from the recorded, validated core, then compile its
program:

```sh
.venv/bin/python scripts/boards/red2_standalone/prepare.py \
  --output build/red2-basys3-standalone-quantum
bash build/red2-basys3-standalone-quantum/build.sh
.venv/bin/python scripts/boards/red2_standalone/image.py \
  --prepared build/red2-basys3-standalone-quantum \
  --file examples/clock-dots.thor --quantum 5 \
  --output build/red2-standalone/clock-dots-quantum.bin
```

Preparation preserves the qualified mapped engine and verifies its packed ABI.
The build uses the qualified image's cached, hash-pinned nextpnr backend and chip
database, with network access disabled. Changes to the core are lowered with the
verified enhanced PipelineC compiler; the board wrapper reuses that mapped core.
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
  --prepared build/red2-basys3-standalone-quantum \
  --image build/red2-standalone/clock-dots-quantum.bin \
  --log build/red2-standalone/deployment.json \
  --expected ".............................." --observe-seconds 120 --persistent
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

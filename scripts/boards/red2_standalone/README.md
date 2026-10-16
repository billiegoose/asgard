# Standalone RED2 on Basys 3

This board integration replaces the debug monitor with a flash loader and
hardware devices around the existing qualified dedicated RED2 engine. The host
compiles THOR before deployment; it does not execute reductions or service I/O
while the program runs.

- The program image is read from configuration flash at **0x220000**. The loader
  uses ordinary 03h SPI reads on the board's QSPI NOR, without changing flash
  modes or enabling writes.
- `CLOCK` returns a 64-bit integer count of milliseconds since successful program
  loading. At the first program run, the counter starts at zero; it keeps counting
  during UART waits. The 10 MHz board clock has 10,000 cycles per millisecond.
- `UART-TX` emits the integer argument modulo 256 on the physical USB UART at
  115200 baud, 8N1. `UART-RX` waits for an actual received byte, with a 16-byte
  receive FIFO. An empty UART is not EOF.
- `UART-TX-BYTES` validates a finite PAIR/NIL byte list before emitting its bytes.
  It follows the existing adapter's one-APP descriptor rule, rejects cyclic or
  malformed lists, and buffers up to 256 bytes, matching this board's graph size.
- Accepted device operations resume the same hardware engine with an encoded
  integer or NIL, then recharge its contraction quantum. No host reconstruction,
  graph compaction, or checkpoint readback occurs during execution.

Finite graph/control/literal capacities remain 256/256/64. Floating arithmetic
is omitted; integer division remains. Memory faults and quantum exhaustion stop
execution explicitly. This integration does not claim unlimited program lifetime.

## Build and deploy

Compile a program and prepare a fresh board build:

```sh
.venv/bin/python scripts/boards/red2_standalone/image.py \
  --file examples/clock-dots.thor --output build/red2-standalone/clock-dots.bin
.venv/bin/python scripts/boards/red2_standalone/prepare.py \
  --output build/red2-basys3-standalone-next
bash build/red2-basys3-standalone-next/build.sh
```

Preparation preserves the qualified mapped engine and verifies its packed ABI.
The build uses the qualified image's cached, hash-pinned nextpnr backend and chip
database, with network access disabled. There is no new PipelineC lowering or
chip database regeneration. Mapping, physical resource checks, routed timing and
BRAM initialization audits must pass before a bitstream is produced.

After a successful build:

```sh
.venv/bin/python scripts/boards/red2_standalone/deploy.py \
  --prepared build/red2-basys3-standalone-next \
  --image build/red2-standalone/clock-dots.bin \
  --log build/red2-standalone/deployment.json --persistent
```

Deployment uses the sibling fpgatool's `program-data` command to program and
verify the reserved data area. It first loads the new hardware into volatile
SRAM and waits for three raw dots without sending UART commands. Only after that
check does `--persistent` program and verify the FPGA configuration flash and test
startup and a separate reset from flash. Power removal/reconnection is a further
physical check; a JTAG-triggered configuration reset is not a power-cycle test.
On failure the script restores the qualified debug image in SRAM; the receipt
records which flash operations had already completed.

A serial terminal is optional for observing program output; the program does not
need one attached. Default board serial is `210183735787`, with UART device
`/dev/cu.usbserial-2101837357871`.

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
  --output build/red2-standalone/check-new
```

This test combines the actual qualified engine's frontend RTL with the new
controller and a physical UART transmitter/receiver model. It checks clock-dots,
byte output, real-waveform byte input/echo, list output, elapsed-time behavior and
corrupt-image rejection. Its test clock uses 100 cycles per millisecond to bound
simulation cost; hardware uses 10,000. Success terminates when expected output
appears, rather than treating a timeout as success. It does not replace physical
qualification or claim that the newly mapped/routed hardware has passed.

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

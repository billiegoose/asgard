# UART publication fix checkpoint — before v8 deployment

**Completed:** v8 subsequently passed full physical UART tests and persistent
clock-dots startup/reset checks. The default build now selects v8. See the
[qualification record](red2-uart-publication-fix-results.json). The remainder
preserves the earlier checkpoint and continuation instructions as history.


User requested saving and committing while placement was running. The automatic
physical deployment worker was stopped. Build, RTL and native diagnostic workers
continue in the background; they do not program the board. The qualified,
persistent **v6 clock-dots** image remains installed. No v7/v8 image was deployed.
Default `image.py` prepared build and `check.py` core intentionally remain v6
until v8 is physically qualified. Existing source-identity guards therefore
reject newly compiled programs against that old build; do not weaken the guards.

## Implemented and verified

Three previously unsupported composite JOIN paths now enter the existing
transactional generic publication walker: multiword EP-parent returns,
non-inline APP operators and non-inline flat-scan terms. Specialized IO-return
and private selector-result dispatch retain priority. A first unqualified v7
attempt violated selector priority; it was rejected and never deployed.

Final machine SHA-256:
`aad93dd1b6d249a4510ba496180b35ffc584e9ab4caaa40f0310192f9e77be72`.

- Four native architectural regression groups pass, including selector priority,
  generic EP/exhausted JOIN memory/control parity, closure materialization,
  sharing, and failure atomicity.
- Full unchanged alphanumerics passes: 63 bytes then halt, quantum 20,
  120,214 logical clocks, 31 restarts, peak compacted residual 41 words.
- Full unchanged Caesar passes: `Az09!` + ESC -> `Ed09!` then halt, quantum 5,
  51,271 logical clocks, 24 restarts, peak residual 49 words.
- Lowered RTL failure-path regressions pass at quantum 5: alphanumerics `01`
  across three restarts; Caesar `E` across four, using real UART input waveforms.
  These are prefix checks, not full-program RTL qualification.
- First ten finite RTL smoke cases pass. The eleventh, clock-dots, had emitted
  one dot and crossed four restarts at this checkpoint; two dots are required.
- 29 focused pytest tests pass. Small changed Python files pass Ruff; changed
  lines add no diagnostics in the two legacy files with existing lint issues.
- Enhanced PipelineC lowering and area mapping pass. Complete board maps to
  **18,663 LUTs, 9,567 FFs, 39.5 BRAM36 equivalents, 12 DSPs**. Placement is
  running with seed 2; routing/timing/physical-site audits remain pending.

`programs.toml` selects alphanumerics quantum 20, clock-dots/Caesar 5, unlisted
programs 5; explicit `--quantum` wins. An earlier v7 alphanumerics run at 5
printed the digits then hit graph/environment collision. The final v8 quantum-5
capacity recheck is still running; inspect it before making final capacity claims.
The source checker models the standalone supervisor's FIFO relocation; actual
controller behavior is independently checked in RTL and on the board.

Machine-readable checkpoint: [results](red2-uart-publication-fix-checkpoint.json).

## Continue locally

Keep these ignored build directories until qualification completes:

- `build/red2-uart-fix/`: logs, native/RTL results and continuation scripts.
- `build/red2-finite-quantum/core-v8/integrated-stream`: mapped new core,
  provenance, enhanced compiler identity, generated RTL and area report.
- `build/red2-basys3-standalone-quantum-v8-seed2`: active board implementation.
- Qualified v6 core/board/program artifacts: required for rollback.

Inspect `board-v8.log`, `rtl-v8.log`, `rtl-prefix-v8.log`,
`native-alphanumerics-q5-v8.log`, and their `result(s).json` files inside
`build/red2-uart-fix`. Board detail is in `board-place.log`, `board-route.log`,
`board-timing.json` and final `build-result.json` in the prepared directory.
Running build worker `start-board-v8.py` finishes implementation; do not launch a
duplicate writer into the same output directory. `rtl-v8.py` handles smoke RTL;
`rtl-prefix-v8.py` already completed both prefix checks.

When all source/RTL/build checks pass, restart the stopped qualification worker:

```sh
.venv/bin/python -u build/red2-uart-fix/qualify-board-v8.py \
  > build/red2-uart-fix/qualification-v8.log 2>&1
```

It verifies all gates/source identities and checks that the serial port is free.
It programs unique images, checks both full UART examples plus normal halt, tests
ten SRAM clock-dots, then programs/verifies configuration flash and checks thirty
dots plus ten after separate reset. On failure it restores v6 data/configuration.
It writes `qualified-board-v8.json` only on success. The board is serial
`210183735787`; port `/dev/cu.usbserial-2101837357871`, 115200 baud 8N1. User had
closed tio; check ownership before use. Do not claim physical power-cycle testing
from a JTAG reset. No host CLOCK service or debug runtime commands are involved.

Only after physical PASS:

1. Run `build/red2-uart-fix/record-v8.py` once to save full qualification and update
   canonical finite-quantum build selection. It embeds the previous result; avoid
   repeated nesting if rerunning.
2. Run `build/red2-uart-fix/finalize-docs-v8.py` to switch the default prepared
   build/core and update guides. Review its generated prose, especially the
   quantum-5 capacity statement, against the final capacity recheck. It expects
   v6 defaults and untouched old guide sections; this checkpoint added prose,
   so remove/adjust the interim checkpoint notice afterward.
3. Run `build/red2-uart-fix/check-mise-v8.py`. It tests the exact original bare
   `mise run fpga examples/...` commands with automatic budgets, complete UART
   outputs/halts, then restores persistent clock-dots and leaves the port free.
   Save its receipt into the qualification report. It flushes stale output after
   each reset before checking the new program.
4. Re-run focused tests and lint, verify provenance/files, commit and push.

Focused tests:

```sh
uv run --group fpga python -m pytest -q \
  tests/test_red2_standalone_run.py tests/test_red2_board_run.py \
  tests/test_synthesizable_red2_static.py tests/test_syn_arithmetic_profile.py
```

The background native and RTL processes use bounded failure limits; successful
long-running tests stop on expected output, never by treating timeout as success.

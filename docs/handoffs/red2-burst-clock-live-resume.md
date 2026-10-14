# RED2 current hardware checkpoint

The objective remains active: improve the dedicated RED2 implementation while
preserving RED2 semantics. Extra cycles and a fixed hardware control ROM are
acceptable; another CPU running RED2 firmware is not. Use the enhanced PipelineC
compiler. Do not confuse endpoint sampling with complete per-clock comparison.

The verified integer/256-word graph core source SHA256 is
`f97b169a1610f0235fed2bf3f701d3989e1567daa97ce668a36cc2e5403195e8`.
Its working FPGA image SHA256 is
`dd259c97f70e3edfe084d7e48dd2a541174ae36bd3681c5be26e50853f5f5e37`.
It uses 17,997 physical LUT sites, leaving 2,803 spare, and passes routed 10 MHz
timing. All five programs and queued lifecycle pass on the Basys 3: 232,008
physical clocks, comparing every 626-bit output, fresh SRAM per case. See
`red2-complete-physical-corpus-results.json`. The existing list-equality gap is
not qualified by those passing programs.

The standard Basys preparation now defaults to the measured `dirty-writeback`
core and the guarded eight-pair response-byte relocation recipe. Eight hardware
inputs reproduce the verified preparation byte-for-byte. `--no-relocate-response-byte`
disables relocation; snapshot response selects its alternative serializer;
burst CLOCK remains optional. See `red2-basys3-default-recipe-results.json`.
The maintained production machine source remains a separate reference. A fresh
full default build is not claimed; the verified image used the recorded cached
route and reproduced placement recipe.

Optional `--burst-clock` adds a UART frontend counter, keeping the core unchanged.
Wire opcode 10 repeats core CLOCK/value zero 1 through 1,048,575 times, returning
the last pre-edge status. The host groups only adjacent identical zero-value
CLOCK commands, rejects native opcode 10 before serial access on this image,
and records executed clocks and compared endpoint samples separately. Invalid
counts, contiguous edges, TX stalls, complete payload and CRC pass simulation.
A counter/echo FPGA fixture also passes; it contains no RED2 engine. The verified
RED2 image was restored afterward. All five RED2 programs plus lifecycle pass
burst monitor simulation: 232,008 clocks and 6,927 endpoint samples. There are
57 passing focused tests. Source and evidence were pushed in `017c5bd`;
default-recipe adoption was pushed in `2ae0a20`.

The complete burst image is in `build/red2-basys3-burst-prepared`. It maps to
18,215 LUTs (+71), 8,545 FF (+20), unchanged 34.5 BRAM36 equivalents and 20 DSPs.
Placement and its guarded eight-pair relocation passed; estimated clocks are
12.30 MHz core and 12.51 MHz monitor. Selected placement SHA256 is
`631d624920ead748b3df86e6f175c8d76ef605a1af978ed39b941b733c1b9060`.
Routing is running in Podman `red2-burst-route`, supervised by local PID 74444
(`run-physical.py`). **Revalidate process identity, container and actual logs**
before waiting, restarting or declaring completion. A timeout in observation is
not a failed build. The existing stage has a one-hour route bound and unchanged
fit, placement-preservation and 10 MHz timing gates before bitstream generation.
Do not load an ungated or incomplete image.

A separate qualification runner, PID 84024 (`qualify-after-build.py`), waits for
that exact existing builder to end. It never restarts the build. Only after a
completed gated build and an unused UART does it run `run-physical-suite.py`.
The suite independently verifies every build artifact, copies host/helper source
into immutable replay-tools, freshly loads SRAM for each of the six cases, and
compares all 626 bits at each packet endpoint. It aborts on the first error,
without UART retries, and restores the known working SRAM image on failure.
The normal board UART is `/dev/cu.usbserial-2101837357871`, serial
`210183735787`; SRAM writes only, never persistent flash. Do not start a second
serial client while qualification is running.

Authoritative files in that build directory:

- `physical-progress.json`, `physical-driver.log`, `board-route.log`;
- `qualification-progress.json`, `qualification-driver.log`;
- after replay begins: `physical-suite-progress.json`,
  `physical-suite-driver.log`, individual load/results/replay logs;
- `build-result.json` exists only after the build gates complete.

`red2-burst-clock-results.json` records completed mapping, simulation, fixture and
placement evidence plus the armed qualification runner. Routed timing and actual
RED2 burst hardware replay remain unproven at this checkpoint. The earlier
snapshot serializer saved 358 mapped LUTs but hit its one-hour route limit;
no bitstream was generated and it did not replace the verified image.

A native-only list-equality diagnostic is also running, PID 79880, in
`build/red2-list-equality-diagnostic/probe.py`. It loads a separate copy of the
frozen candidate, adding a 16-bit diagnostic register/output that records the
original generated-source line when a legacy unsupported-execution assignment
fires. This copy is never synthesized or loaded on the FPGA; production,
compiler and qualified core sources are unchanged. `probe-site.log` is the live
result. The initial attempt to insert dynamic print calls was rejected during
native pipeline elaboration and is retained in `probe.log`; it did not reproduce
the semantic fault. The typed-register probe is still advancing and has not yet
reported a fault location. Its test expression is
`(EQUAL? (CONS 7 NIL) (CONS 7 NIL))`, historically faulting at commit 41 on both
the old candidate and maintained production. Revalidate that process and inspect
its final result before drawing a new conclusion.

Disk space is tight. Completed burst simulation binaries were losslessly
compressed after explicit success; their original/archive hashes are recorded
in `build/red2-burst-corpus-check/simulation-archives.json`. No active build
inputs or qualification artifacts were removed. Podman free-block trimming
also recovered space. Keep the verified image and all gate inputs intact.

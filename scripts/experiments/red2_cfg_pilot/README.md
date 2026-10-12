# RED2 control-flow/storage experiment

This is an isolated hardware experiment, not the production top or a completed
Basys 3 implementation. It mechanically lowers the original typed RED2 handlers
before SSA into an immutable synchronous control ROM, synchronous BRAM scratch,
one 64-bit add/sub lane, Boolean/bit operations, and registered graph/control
ports. There is no CPU core, loadable firmware, or writable control-store port.

The first configuration covers all 16 LAMBDA and four APP handlers, their RAM
requests, and APP/LAMBDA entry paths in EXECUTE. Enabling lookup adds its four
handlers, requests, and VAR/APP_VAR entry paths on the same datapath. Full-width
graph/control payloads, typed truncation, malformed addresses, sentinels, ordered
scalar updates, faults, and handoffs come from the original source. Unsupported
AST operations fail generation. A static all-path check rejects uninitialized
operands. `control.json` records source identity, types, state ownership and
handoffs; state addresses are generated, not a stable external ABI.

One start admits one logical transition; physical latency varies with the active
branch. Start state is sampled once. Setup writes and new starts are ignored
while busy. Graph/control requests remain stable until `response_valid`, which
accepts the pair exactly once and latches both read responses. The external RAM
adapter must return read-first data for simultaneous reads/writes. A completion
is not itself a committed RED2 reduction. The addressed setup/debug port reads
and writes typed state words; valid state locations and widths are in the
manifest. It cannot modify constants or controller rows. Unused setup locations
and unsupported start states are outside this pilot's interface contract.

The original family baseline uses the same state locations, request/response
interface and admission domain, with the source handlers and named FF state.
Both models leave outer command arbitration, initial fault checks and the
original synchronous-read admission bubble to the caller. Controller reset
cancels internal activity and suppresses new requests/writes; it does not
implement architectural RESET/LOAD_STATE or undo an already accepted RAM write.

Generate and validate, with Python 3.14 and the native PipelineC dependencies
used by `scripts/check_syn_sim.py`:

```sh
export RED2_CFG_PILOT_OUT="$PWD/build/red2-cfg-pilot"
python3 scripts/experiments/red2_cfg_pilot/oracle.py
python3 scripts/experiments/red2_cfg_pilot/emit.py
python3 scripts/experiments/red2_cfg_pilot/baseline.py
python3 scripts/experiments/red2_cfg_pilot/check.py
python3 scripts/experiments/red2_cfg_pilot/check_hardware.py
python3 scripts/experiments/red2_cfg_pilot/check_hardware.py --baseline
python3 scripts/experiments/red2_cfg_pilot/frontend.py
python3 scripts/experiments/red2_cfg_pilot/frontend.py --baseline
```

Use a separate output directory and `RED2_CFG_PILOT_LOOKUP=1` for the second
configuration. Generation uses a 256-word graph. The typed oracle is extracted
directly from the original AST and runs through PipelineC's native simulator;
it is not synthesized into the candidate. Deterministic boundary/random cases
compare every family state field and every request bit. A greedy path selection
chooses physical-controller cases, including successful/failing paths. Physical
tests also delay RAM responses, vary inputs after acceptance, attempt busy
starts/setup writes, retain scratch between transitions, cancel with reset, and
check constant protection. Finite iteration budgets require actual completion.

For the recorded Nix/Podman backend, `prepare_map.py` (and `--baseline`) verifies
the enhanced compiler, emits GHDL/Yosys scripts and fingerprints every HDL input.
Run each generated `run.sh` inside the pinned Nix container with `fpgatool-nix`
mounted at `/nix` and that configuration directory at `/experiment`. Count the
result with `scripts/yosys_resources.py <directory>/baseline-area.json --top top`.
The mapper recipe matches the maintained core's flattened classic LUT6 area
flow. This helper assumes the exact Nix store paths recorded in the area report;
it does not install or change tools. Netlists and generated sources stay outside
Git, while the generator and measurement record are committed.

APP/LAMBDA alone maps from 3,977 to 1,481 LUTs; including lookup maps from 6,254
to 1,377 LUTs, with 12 BRAM36 equivalents in the latter candidate. These are
standalone comparisons. Integration must remove legacy handlers/requests and
account for all bridges to the remaining machine. In particular, several state
fields are shared with RBLOCK, definition cleanup, selector and reconstruction
paths. Publication remains a later test and must preserve preparation, external
JOIN/scalar preflight, and explicit commit authorization. Neither isolated result
establishes whole-core fit, routing, timing, or complete-program parity.

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

`RED2_CFG_PILOT_COMPACT=1` enables CFG-liveness allocation of temporary words
and opcode-specific control packing. Architectural cells and immutable constants
never alias. For lookup this reduces 1,438 scratch words to 146 (256-word RAM)
and the control word to 33 bits: measured storage falls from 12 to five BRAM36
at 1,459 LUT. The interference proof checks every complete live set, including
branch successors; destination reuse is safe because both operands are latched.

`RED2_CFG_PILOT_GRAPH=1` adds EP, CLOSURE, RUP and RECP entry/handler paths on
the same datapath. EP_REVERSE_CONTROL_READ stays in legacy logic because its
shared-initialization launch event is consumed outside the extracted handlers.
This scope has 56 entries, 6,229 rows, 218 allocated words and a packed 34-bit,
8,192-row control ROM. A shared 65-bit add/sub carry implements unsigned GE.
The source-derived oracle passed 6,720 cases and the physical controller passed
159 path witnesses plus reset and constant protection.

The experimental complete top is generated by `integrate.py`, then elaborated
or mapped with `frontend.py --integrated` / `prepare_map.py --integrated`.
`RED2_CFG_PILOT_INTEGRATED_NAME` selects a separate variant directory (default
`integrated`). It currently mirrors the family FF fields through serial BRAM
transfers. Its extra status bit `busy` is part of the experimental contract:
CMD_CLOCK advances a transition; CMD_NOP pauses/observes; RESET, LOAD_STATE and
START cancel; other commands are admitted when idle. Scalar observations during
busy are not a completed architectural snapshot. Accepted RAM writes cannot be
rolled back. The graph must remain 256 words. No production caller is switched.

`check_boundary.py --entries` seeds original internal states only through the
pinned simulator fixture, then drives the complete hardware top through normal
commands. It checks all selected entry states, every family leaf, RAM write
payloads and one paired request, pauses, and cancellation at different phases.
The corrected `integrated-v2` passed all 25 lookup and all 56 graph entries.
A pause in operand-consume phases originally let RAM read addresses drift;
address hold in phases four/five fixes the state-22 counterexample. The first
lookup integration's 40,826-LUT map is **rejected diagnostic evidence**, because
it predates this fix. The corrected graph full-core map is recorded separately.
`check_integrated.py` adapts the existing complete-program native suite by
waiting for actual `busy` completion, with finite failure bounds. A suite that
is still running or was interrupted is not a pass.

The standalone original family includes addressed debug/setup multiplexers that
the production core does not have. Its isolated saving is not an additive
whole-core estimate. The integrated bridge also adds selection and FF state.
Next, freeze the graph scope and make lifecycle-only private state authoritative
in BRAM, use per-entry shared transfers, and publish coherent architectural
outputs. Lifecycle initialization must preserve the difference between RESET,
LOAD_STATE, valid START and invalid START; do not clear all private cells alike.
Measure that complete top before extending connected JOIN/publication families.

`RED2_CFG_PILOT_OWNED=1` selects the next integration experiment. Generation
proves private ownership against the remaining legacy AST after extraction;
it removes 26 Reg roots (29 leaves, 923 typed bits), including their lifecycle
FF assignments. No runtime legacy reference may survive. Private scratch is
retained across owned transitions. A synchronous per-entry mask ROM enables
imports of shared read-before-write or potentially written fields, and exports
only potentially written fields. Potential conditional writes import their old
values too, so an untaken write cannot export stale scratch. The first version
still scans shared indices; masks suppress transfers, not every scan cycle.

The owned variant snapshots only observable architectural/status scalar fields,
then exposes the completed scalar result together when busy drops. This avoids
partial serial-export observations without duplicating private storage. One
lifecycle command received while busy is latched and applied after the current
logical transition completes, including already accepted RAM writes. Callers
must wait for busy to clear before sending another command. RESET/LOAD_STATE
initialize all proven private fields; valid START initializes its exact subset;
invalid START changes the original fault state without initializing private
cells. These masks are extracted from exact original lifecycle predicates and
zero initializers; new/unsupported patterns remain shared or fail generation.

The boundary checker supports `--lifecycle` to test nonzero private sentinels
against all four lifecycle cases, and queued invalid START after an accepted
RAM write and during scalar export. `--entries` also checks coherent scalar
observations on every busy cycle. `check_integrated.py --application` runs
application/lookup and list construction/access in lockstep with the concrete
RED2 reference. All integration variants remain experiments until full parity,
complete mapped resources, and board implementation satisfy acceptance.

The corrected graph mirror maps to 38,908 total LUTs; persistent ownership maps
to 38,417, including its mask ROM, scalar observation bank and queued lifecycle
logic. The latter uses 9,959 FF and 26 BRAM36 equivalents. Both maps account for
all primitives and report zero structural problems. All 159 owned integration
path witnesses, nonzero lifecycle masks, queued invalid START, application/list
lockstep and RECP parity checks pass. This is still above the 20,800-LUT board
capacity; production remains at 41,170 LUT. The event audit regenerates identical
hardware and rejects extraction of non-Reg events still consumed by legacy code.
See `docs/handoffs/synth-red2-cfg-integration-results.json` for exact provenance.

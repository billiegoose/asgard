#!/usr/bin/env python3
"""Run compiled THOR source on the Synthesizable RED2 Machine simulator."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PIPELINEC_ROOT = REPO_ROOT.parent / "PipelineC-pypeline-red2-pinned"
LIB_ROOT = REPO_ROOT / "src" / "lib"
MACHINES_ROOT = REPO_ROOT / "src" / "machines"


def _bootstrap_import_paths() -> None:
    """Make Asgard and the configured PipelineC checkout importable in-process."""
    for source_root in (LIB_ROOT, MACHINES_ROOT):
        source = str(source_root)
        if source not in sys.path:
            sys.path.insert(0, source)

    configured = os.environ.get("PIPELINEC_ROOT")
    root = (
        Path(configured).expanduser().resolve()
        if configured
        else DEFAULT_PIPELINEC_ROOT
    )
    if root.is_dir():
        checkout_paths = [
            str(root / "src"),
            str(root / "include"),
            str(root / "include" / "pypeline"),
        ]
        sys.path[:0] = [value for value in checkout_paths if value not in sys.path]
        return

    try:
        __import__("pypeline")
    except ImportError as error:
        raise RuntimeError(
            "native Pypeline simulator unavailable; set PIPELINEC_ROOT to a PipelineC "
            f"checkout (tested checkout: {DEFAULT_PIPELINEC_ROOT})"
        ) from error


_bootstrap_import_paths()

import pypeline as _pypeline  # noqa: E402
from pypeline import sim_call, sim_reset  # noqa: E402

from abstract_red2_machine.machine import AbstractRED2Machine  # noqa: E402
from concrete_red2_machine import abi  # noqa: E402
from concrete_red2_machine.pipelinec_vectors import (  # noqa: E402
    EncodedArchitecturalState,
    RED2ABICodec,
)
import synthesizable_red2_machine.machine as _syn_machine  # noqa: E402
from synthesizable_red2_machine.machine import (  # noqa: E402
    CMD_CLOCK,
    CMD_LOAD_CONTROL,
    CMD_LOAD_LITERAL_META,
    CMD_LOAD_MEMORY,
    CMD_LOAD_STATE,
    CMD_NOP,
    CMD_RESET,
    CONTROL_WORDS,
    GRAPH_WORDS,
    LITERAL_META_WORDS,
    LITERAL_SPECIAL_EQUAL_IF,
    LITERAL_SPECIAL_EQUAL_STAR,
    LITERAL_SPECIAL_EQUAL_STUCK,
    LITERAL_SPECIAL_EQUALITY,
    LITERAL_SPECIAL_EQUALITY_CONTINUE,
    LITERAL_SPECIAL_FALSE,
    LITERAL_SPECIAL_NIL,
    LITERAL_SPECIAL_TRUE,
    PRIM0_ROLE_DEFERRED,
    PRIM0_ROLE_IF,
    PRIM0_ROLE_IO_BIND,
    PRIM0_ROLE_IO_RETURN,
    PRIM0_ROLE_IO_THEN,
    PRIM0_ROLE_Y,
    SCALAR_OP_ABS,
    SCALAR_OP_ADD,
    SCALAR_OP_CEILING,
    SCALAR_OP_CHAR_P,
    SCALAR_OP_DEC,
    SCALAR_OP_DIV,
    SCALAR_OP_EQ,
    SCALAR_OP_EVEN,
    SCALAR_OP_EXPT,
    SCALAR_OP_FLOAT_P,
    SCALAR_OP_FLOOR,
    SCALAR_OP_GE,
    SCALAR_OP_GT,
    SCALAR_OP_INC,
    SCALAR_OP_INTEGER_P,
    SCALAR_OP_LE,
    SCALAR_OP_LT,
    SCALAR_OP_MAX,
    SCALAR_OP_MIN,
    SCALAR_OP_MOD,
    SCALAR_OP_MUL,
    SCALAR_OP_NEGATE,
    SCALAR_OP_NOT,
    SCALAR_OP_NULL,
    SCALAR_OP_SUB,
    SCALAR_OP_SYMBOL_P,
    STATUS_COMPLETE,
    STATUS_FAULT,
    STATUS_HOST_CALL,
    STATUS_QUANTUM_EXHAUSTED,
    STATUS_RUNNING,
    STRUCT_ROLE_SELECTOR,
    STRUCT_ROLE_SELECTOR_RESULT,
    SynthesizableRED2Machine,
    red2_arch_state_t,
    red2_command_t,
    red2_control_t,
    red2_literal_meta_t,
    red2_word_t,
)
from abstract_red2_machine.loader import load_faithful_machine  # noqa: E402
from thor.ast import Definition, Expr, StructDef  # noqa: E402
from thor.normalization import normalize_program  # noqa: E402
from thor.parser import ParseError, parse_program  # noqa: E402
from thor.pretty import to_source  # noqa: E402
from thor.primitives import install_struct_definition  # noqa: E402

MASK64 = (1 << 64) - 1
ZERO_WORD = red2_word_t(lo=0, hi=0)
ZERO_CONTROL = red2_control_t(lo=0, hi=0, tag_hi=0)
ZERO_STATE = red2_arch_state_t(
    pc=0,
    fsp=0,
    env=0,
    control_top=0,
    direction=0,
    q=0,
    phi=0,
    free_space=0,
    argcnt=0,
    prim_id=0,
    fire=0,
    s_a=0,
    s_d=0,
    halted=0,
    pending_host_op=0,
    pending_host_argument=0,
)

_SCALAR_OPS = {
    "1-": SCALAR_OP_DEC,
    "1+": SCALAR_OP_INC,
    "MINUS": SCALAR_OP_NEGATE,
    "ABS": SCALAR_OP_ABS,
    "FLOOR": SCALAR_OP_FLOOR,
    "CEILING": SCALAR_OP_CEILING,
    "EVEN?": SCALAR_OP_EVEN,
    "NULL?": SCALAR_OP_NULL,
    "NOT": SCALAR_OP_NOT,
    "INTEGER?": SCALAR_OP_INTEGER_P,
    "FLOAT?": SCALAR_OP_FLOAT_P,
    "CHAR?": SCALAR_OP_CHAR_P,
    "SYMBOL?": SCALAR_OP_SYMBOL_P,
    "+": SCALAR_OP_ADD,
    "-": SCALAR_OP_SUB,
    "*": SCALAR_OP_MUL,
    "/": SCALAR_OP_DIV,
    "<": SCALAR_OP_LT,
    ">": SCALAR_OP_GT,
    "<=": SCALAR_OP_LE,
    ">=": SCALAR_OP_GE,
    "=": SCALAR_OP_EQ,
    "EXPT": SCALAR_OP_EXPT,
    "MAX": SCALAR_OP_MAX,
    "MIN": SCALAR_OP_MIN,
    "MOD": SCALAR_OP_MOD,
}

_PRIM0_ROLES = {
    "IF": PRIM0_ROLE_IF,
    "AND": PRIM0_ROLE_DEFERRED,
    "OR": PRIM0_ROLE_DEFERRED,
    "Y": PRIM0_ROLE_Y,
    "IO-BIND": PRIM0_ROLE_IO_BIND,
    "IO-THEN": PRIM0_ROLE_IO_THEN,
    "IO-RETURN": PRIM0_ROLE_IO_RETURN,
}

_HOST_OPS = {
    "CLOCK": abi.HOST_CLOCK,
    "UART-RX": abi.HOST_UART_RX,
    "UART-TX": abi.HOST_UART_TX,
    "UART-TX-BYTES": abi.HOST_UART_TX_BYTES,
}

_SPECIALS = {
    "TRUE": LITERAL_SPECIAL_TRUE,
    "FALSE": LITERAL_SPECIAL_FALSE,
    "NIL": LITERAL_SPECIAL_NIL,
    "EQUAL?": LITERAL_SPECIAL_EQUALITY,
    "__EQUAL_STAR__": LITERAL_SPECIAL_EQUAL_STAR,
    "__EQUAL_IF__": LITERAL_SPECIAL_EQUAL_IF,
    "__EQUALITY_CONTINUE__": LITERAL_SPECIAL_EQUALITY_CONTINUE,
    "__EQUAL_STUCK__": LITERAL_SPECIAL_EQUAL_STUCK,
}

_HOST_NAMES = {
    abi.HOST_CLOCK: "CLOCK",
    abi.HOST_UART_RX: "UART-RX",
    abi.HOST_UART_TX: "UART-TX",
    abi.HOST_UART_TX_BYTES: "UART-TX-BYTES",
}

_FAST_RAM_NAMES = (
    "graph_ram",
    "control_ram",
    "literal_meta_ram",
    "promote_mat_ram",
    "promote_forward_ram",
    "pub_task_ram",
    "pub_root_ram",
    "pub_patch_ram",
    "pub_patch_addr_ram",
    "pub_mat_ram",
)


def _identity(value):
    return value


def _install_fast_native_ram_simulation() -> None:
    """Specialize Pypeline's generic RAM simulation for RED2's CLI runner.

    ``run_syn`` performs exactly one top-level ``sim_call`` per modeled clock and
    does not run a wire-convergence loop.  The generic Pypeline RAM model therefore
    pays for convergence safety that this runner cannot use: it deep-copies model
    state on every RAM invocation and deep-copies immutable RED2 struct payloads
    on every read/write bundle.  Keep the same read-first edge semantics by
    applying writes staged by the previous call before evaluating the next call,
    but retain RAM state in place and share immutable payload values directly.

    Every RED2 RAM target is a distinct single hardware instance, so model call-site
    capture carries no disambiguating information here.  Replacing it with one
    stable location avoids frame/line lookup overhead without merging instances.
    Hardware elaboration is unaffected; this changes only native Python simulation.
    """

    _pypeline._sim_capture_call_loc = lambda caller_f: ("<red2-ram>", 0, None, None)

    for name in _FAST_RAM_NAMES:
        ram = getattr(_syn_machine, name)
        cell = getattr(ram, "_sim_model_cell", None)
        if cell is None or cell[0] is None:
            raise RuntimeError(f"{name} has no Pypeline RAM simulation model")
        model_class, kind, _copy_state = cell[0]
        if kind != "class":
            raise RuntimeError(f"{name} uses unexpected simulation model kind {kind!r}")

        if not getattr(model_class, "_red2_fast_native_sim", False):
            original_call = model_class.__call__
            closure = dict(
                zip(original_call.__code__.co_freevars, original_call.__closure__ or ())
            )
            for owner_name in ("own", "write_value"):
                owner_cell = closure.get(owner_name)
                if owner_cell is None:
                    raise RuntimeError(
                        f"{name} RAM model is missing expected {owner_name!r} closure"
                    )
                owner_cell.cell_contents = _identity

            def fast_call(self, *args, __original_call=original_call, **kwargs):
                _commit_native_ram_pending(self)
                return __original_call(self, *args, **kwargs)

            model_class.__call__ = fast_call
            model_class._red2_fast_native_sim = True

        # Plain run_syn has one evaluation per clock, so mutating the committed RAM
        # model in place is equivalent to Pypeline's deepcopy/buffer path once the
        # previous call's staged writes are applied above.
        cell[0] = (model_class, kind, False)


_install_fast_native_ram_simulation()


def _native_ram_model(name: str):
    """Return the committed native-simulation model for one RED2 RAM instance."""
    ram = getattr(_syn_machine, name)
    qualname = ram.__qualname__
    for path, state in _pypeline._sim_reg_state.items():
        if path and path[-1][0] == qualname:
            model = state.get("__sim_model__")
            if model is not None:
                return model
    raise RuntimeError(f"native RAM model {name!r} is not instantiated")


def _commit_native_ram_pending(model) -> None:
    """Apply writes staged by the preceding native-simulation clock."""
    if not model.pending:
        return
    memory = model.mem
    for address, value, mask in model.pending:
        if mask is not None:
            raise RuntimeError("RED2 fast RAM simulation does not support byte masks")
        memory[address] = value
    model.pending = []


def _word_struct(packed: int) -> red2_word_t:
    return red2_word_t(lo=packed & MASK64, hi=(packed >> 64) & MASK64)


def _control_struct(packed: int) -> red2_control_t:
    return red2_control_t(
        lo=packed & MASK64,
        hi=(packed >> 64) & MASK64,
        tag_hi=(packed >> 128) & 0xF,
    )


def _packed_word(word: red2_word_t) -> int:
    return int(word.lo) | (int(word.hi) << 64)


def _packed_control(control: red2_control_t) -> int:
    return int(control.lo) | (int(control.hi) << 64) | (int(control.tag_hi) << 128)


def _state_struct(state: EncodedArchitecturalState) -> red2_arch_state_t:
    return red2_arch_state_t(
        pc=state.pc,
        fsp=state.fsp,
        env=state.env,
        control_top=state.c,
        direction=state.direction,
        q=state.q,
        phi=state.phi,
        free_space=state.free_space,
        argcnt=state.argcnt,
        prim_id=state.prim_id,
        fire=state.fire,
        s_a=state.s_a,
        s_d=state.s_d,
        halted=state.halted,
        pending_host_op=state.pending_host_op,
        pending_host_argument=state.pending_host_argument,
    )


def _command(
    op: int,
    *,
    address: int = 0,
    word: red2_word_t = ZERO_WORD,
    control: red2_control_t = ZERO_CONTROL,
    value: int = 0,
    aux: int = 0,
    state: red2_arch_state_t = ZERO_STATE,
) -> red2_command_t:
    return red2_command_t(
        op=op,
        address=address,
        word=word,
        control=control,
        value=value,
        aux=aux,
        state=state,
    )


def _prepare_program(source: str) -> tuple[Expr, dict[str, Expr]]:
    program = normalize_program(parse_program(source))
    definitions: dict[str, Expr] = {}
    install_struct_definition("PAIR", ("CAR", "CDR"), definitions)
    definitions.pop("CAR", None)
    definitions.pop("CDR", None)
    action: Expr | None = None
    for form in program.forms:
        if isinstance(form, Definition):
            definitions[form.name] = form.expr
        elif isinstance(form, StructDef):
            install_struct_definition(form.tag, form.accessors, definitions)
        else:
            action = form
    if action is None:
        raise ValueError("THOR program requires a final expression")
    return action, definitions


def _literal_metadata(codec: RED2ABICodec, selectors) -> list[dict[str, int]]:
    entries: dict[int, dict[str, int]] = {}

    def entry(name: str) -> dict[str, int]:
        literal_id = codec.literal_id(name)
        return entries.setdefault(
            literal_id,
            {
                "literal_id": literal_id,
                "scalar_op": 0,
                "prim0_role": 0,
                "host_op": 0,
                "special_flags": 0,
                "struct_role": 0,
                "struct_tag_id": 0,
                "struct_offset": 0,
            },
        )

    for name, value in _SCALAR_OPS.items():
        entry(name)["scalar_op"] = value
    for name, value in _PRIM0_ROLES.items():
        entry(name)["prim0_role"] = value
    for name, value in _HOST_OPS.items():
        entry(name)["host_op"] = value
    for name, value in _SPECIALS.items():
        entry(name)["special_flags"] |= value

    # Allocate the hidden semantic ids through this program's codec so words
    # synthesized by the reducer use the same finite-id namespace as the image.
    for hidden in ("__IF_RECONSTRUCT__", "CONS", "PAIR"):
        codec.literal_id(hidden)

    result = entry("__STRUCT_SELECTOR_RESULT__")
    result["struct_role"] = STRUCT_ROLE_SELECTOR_RESULT
    for selector in selectors:
        item = entries.setdefault(
            selector.selector_id,
            {
                "literal_id": selector.selector_id,
                "scalar_op": 0,
                "prim0_role": 0,
                "host_op": 0,
                "special_flags": 0,
                "struct_role": 0,
                "struct_tag_id": 0,
                "struct_offset": 0,
            },
        )
        item["struct_role"] = STRUCT_ROLE_SELECTOR
        item["struct_tag_id"] = selector.tag_id
        item["struct_offset"] = selector.offset

    values = list(entries.values())
    if len(values) > LITERAL_META_WORDS:
        raise ValueError(
            f"program requires {len(values)} semantic literal metadata entries; "
            f"hardware table holds {LITERAL_META_WORDS}"
        )
    return values


def _literal_meta_struct(meta: dict[str, int]) -> red2_literal_meta_t:
    return red2_literal_meta_t(
        literal_id=meta["literal_id"],
        scalar_op=meta["scalar_op"],
        prim0_role=meta["prim0_role"],
        host_op=meta["host_op"],
        special_flags=meta["special_flags"],
        struct_role=meta["struct_role"],
        struct_tag_id=meta["struct_tag_id"],
        struct_offset=meta["struct_offset"],
        valid=1 if meta["literal_id"] else 0,
    )


def _load_literal_meta(slot: int, meta: dict[str, int]) -> None:
    aux = (
        meta["scalar_op"]
        | (meta["prim0_role"] << 5)
        | (meta["host_op"] << 8)
        | (meta["special_flags"] << 11)
    )
    struct_meta = (
        (meta["struct_tag_id"] & 0xFFFFFFFF)
        | ((meta["struct_offset"] & 0xFFFFFFFF) << 32)
        | ((meta["struct_role"] & 0x3) << 64)
    )
    sim_call(
        SynthesizableRED2Machine,
        _command(
            CMD_LOAD_LITERAL_META,
            address=slot,
            value=meta["literal_id"],
            aux=aux,
            word=_word_struct(struct_meta),
        ),
    )


def _load_hardware(
    state: EncodedArchitecturalState, metadata: list[dict[str, int]]
) -> None:
    sim_reset()
    # One RESET call creates and resets every RAM/register instance. Program-image
    # loading is host setup rather than RED2 execution, so populate the native RAM
    # backing stores directly instead of spending one full simulated hardware clock
    # per graph/control/meta word.
    sim_call(SynthesizableRED2Machine, _command(CMD_RESET))

    graph = _native_ram_model("graph_ram")
    control = _native_ram_model("control_ram")
    literal_meta = _native_ram_model("literal_meta_ram")
    graph.mem[:] = [_word_struct(packed) for packed in state.memory]
    control.mem[:] = [_control_struct(packed) for packed in state.control_stack]
    for slot, meta in enumerate(metadata):
        literal_meta.mem[slot] = _literal_meta_struct(meta)

    sim_call(
        SynthesizableRED2Machine,
        _command(CMD_LOAD_STATE, state=_state_struct(state)),
    )


def _checkpoint(result) -> EncodedArchitecturalState:
    graph = _native_ram_model("graph_ram")
    control_ram_model = _native_ram_model("control_ram")
    # The terminating CMD_CLOCK may have staged an architectural RAM write. A
    # normal following sim_call would commit it at the next edge; checkpointing
    # must expose that same committed post-clock state before reading the backing
    # stores directly.
    _commit_native_ram_pending(graph)
    _commit_native_ram_pending(control_ram_model)
    memory = tuple(_packed_word(word) for word in graph.mem)
    control = tuple(_packed_control(word) for word in control_ram_model.mem)
    return EncodedArchitecturalState(
        memory=memory,
        control_stack=control,
        pc=int(result.pc),
        fsp=int(result.fsp),
        env=int(result.env),
        c=int(result.control_top),
        direction=int(result.direction),
        q=int(result.q),
        phi=int(result.phi),
        free_space=int(result.free_space),
        argcnt=int(result.argcnt),
        prim_id=int(result.prim_id),
        fire=int(result.fire),
        s_a=int(result.s_a),
        s_d=int(result.s_d),
        halted=int(result.halted),
        pending_host_op=int(result.pending_host_op),
        pending_host_argument=int(result.pending_host_argument),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="syn",
        description="Run THOR source on the Synthesizable RED2 Machine simulator.",
    )
    parser.add_argument("file", nargs="?", type=Path, help="path to THOR source")
    parser.add_argument("--expr", help="THOR expression or program source to run")
    parser.add_argument("--quantum", type=int, default=2000)
    parser.add_argument(
        "--clock", type=Path, help="reserved for hardware host-call support"
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--max-clocks", type=int, default=100_000_000, help=argparse.SUPPRESS
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.expr is None and args.file is None:
        parser.print_help()
        return 0
    if args.expr is not None and args.file is not None:
        parser.error("--expr and file are mutually exclusive")
    if args.quantum < 0:
        parser.error("--quantum must be non-negative")

    try:
        source = args.expr if args.expr is not None else args.file.read_text()
        action, definitions = _prepare_program(source)
        machine = load_faithful_machine(
            action,
            quantum=args.quantum,
            definitions=definitions,
            memory_words=GRAPH_WORDS,
            control_words=CONTROL_WORDS,
        )
        codec = RED2ABICodec()
        image = codec.encode_program(machine)
        metadata = _literal_metadata(codec, image.struct_selectors)
        _load_hardware(image.state, metadata)

        commits = 0
        result = sim_call(SynthesizableRED2Machine, _command(CMD_NOP))
        for clock in range(args.max_clocks + 1):
            status = int(result.status)
            if status != STATUS_RUNNING:
                break
            if clock == args.max_clocks:
                raise RuntimeError(
                    f"native simulator remained RUNNING after {args.max_clocks} clocks"
                )
            result = sim_call(SynthesizableRED2Machine, _command(CMD_CLOCK))
            commits += int(result.committed)
        else:  # pragma: no cover - loop has an explicit bound above
            raise RuntimeError("native simulator clock bound exhausted")

        status = int(result.status)
        if status == STATUS_COMPLETE:
            final_state = _checkpoint(result)
            decoded = codec.decode_state(final_state)
            result_view = AbstractRED2Machine(
                decoded,
                working_memory_limit=image.working_memory_limit,
            )
            print(to_source(result_view.result_expr()))
            if args.verbose:
                print(
                    f"syn: complete commits={commits} clocks={clock} "
                    f"graph_words={GRAPH_WORDS} control_words={CONTROL_WORDS}",
                    file=sys.stderr,
                )
            return 0

        if status == STATUS_QUANTUM_EXHAUSTED:
            print(
                "syn: quantum exhausted; native halted-residual recharge/"
                "relinearization is not implemented yet; rerun with a larger --quantum",
                file=sys.stderr,
            )
            return 3

        if status == STATUS_HOST_CALL:
            host_op = int(result.pending_host_op)
            host_name = _HOST_NAMES.get(host_op, f"host-op-{host_op}")
            clock_note = (
                ""
                if args.clock is None
                else f" (clock source {args.clock} was not consumed)"
            )
            print(
                f"syn: suspended on {host_name}; native CMD_RESUME is not "
                f"implemented yet{clock_note}",
                file=sys.stderr,
            )
            return 4

        if status == STATUS_FAULT:
            red2_fault = int(result.red2_fault)
            hw_fault = int(result.hw_fault)
            microstate = int(result.microstate)
            detail = ""
            if hw_fault == 3:
                detail = " (native reducer path not implemented yet)"
            print(
                "syn: hardware fault: "
                f"red2={red2_fault} hw={hw_fault} micro={microstate} "
                f"commits={commits}{detail}",
                file=sys.stderr,
            )
            return 5

        raise RuntimeError(f"unknown native simulator status: {status}")
    except (OSError, ParseError, ValueError, RuntimeError, TypeError) as error:
        print(f"syn: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

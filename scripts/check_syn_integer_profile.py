#!/usr/bin/env python3
"""Native parity and omission checks for RED2 without floating arithmetic hardware."""

import check_syn_sim as c
from run_syn import _SCALAR_OPS
from synthesizable_red2_machine.machine import RED2_SYN_FLOAT


CLOCK_BUDGET = 8192


def check_unsupported(source: str) -> None:
    """Omitted arithmetic must fault before changing the contracting checkpoint."""
    action, definitions = c._prepare_thor_program(source)
    machine = c.load_faithful_machine(
        action,
        quantum=2000,
        definitions=definitions,
        memory_words=256,
        control_words=256,
    )
    codec = c.RED2ABICodec()
    image = codec.encode_program(machine)
    metadata = c._program_literal_metadata(codec, image.struct_selectors)
    processor = c.ConcreteRED2Machine(
        image.state, **c._program_concrete_kwargs(codec, image, metadata)
    )
    c._load_program_hardware(image.state, metadata)
    for _ in range(128):
        before = processor.checkpoint()
        # The full oracle supports the omitted operation. Earlier contractions
        # must still agree; at the first unsupported request the hardware must
        # retain the checkpoint from immediately before that contraction.
        assert processor.run_to_commit(), source
        expected = processor.checkpoint()
        for _ in range(CLOCK_BUDGET):
            result = c.sim_call(c.SynthesizableRED2Machine, c._command(c.CMD_CLOCK))
            if int(result.status) == c.STATUS_FAULT:
                assert int(result.red2_fault) == c.abi.FAULT_UNSUPPORTED_VALUE, source
                assert int(result.hw_fault) == c.HW_FAULT_NONE, source
                c._assert_scalar_checkpoint(result, before)
                for address, word in enumerate(before.memory):
                    read = c.sim_call(
                        c.SynthesizableRED2Machine,
                        c._command(c.CMD_NOP, address=address),
                    )
                    assert c._packed_memory_read(read) == word, (
                        source,
                        "graph",
                        address,
                    )
                for address, word in enumerate(before.control_stack):
                    read = c.sim_call(
                        c.SynthesizableRED2Machine,
                        c._command(c.CMD_NOP, address=address),
                    )
                    assert c._packed_control_read(read) == word, (
                        source,
                        "control",
                        address,
                    )
                print("FAILURE_ATOMIC_UNSUPPORTED_PASS", source, flush=True)
                return
            if int(result.committed):
                c._assert_scalar_checkpoint(result, expected)
                break
        else:
            raise AssertionError("No bounded commit/fault: " + source)
    raise AssertionError("Expected unsupported arithmetic: " + source)


def check() -> None:
    assert RED2_SYN_FLOAT == 0, "run this gate with RED2_SYN_FLOAT=0"
    cases = (
        "(+ 7 2)",
        "(- 2 7)",
        "(* -7 9)",
        "(* -9223372036854775808 1)",
        "(* 0 -9223372036854775808)",
        "(EXPT -2 5)",
        "(EXPT 2 12)",
        "(/ -18 3)",
        "(MOD -19 3)",
        "(FLOAT? 1.5)",
        "(EQUAL? 1.5 1.5)",
        "(EQUAL? 0.0 -0.0)",
        "(= 1.5 1.5)",
        "(EVEN? 1.5)",
        "(MOD 1.5 2)",
    )
    for source in cases:
        assert source[1:].split()[0] in _SCALAR_OPS or source.startswith("(EQUAL? "), (
            source
        )
        c._run_program_lockstep(source, max_clocks_per_commit=CLOCK_BUDGET)
        print("LOCKSTEP_PASS", source, flush=True)
    for source in (
        "(+ 1.5 2.5)",
        "(1+ 1.5)",
        "(FLOOR 1.5)",
        "(/ 1 2)",
        "(EXPT 2 -1)",
    ):
        check_unsupported(source)
    for label, checker in (
        ("RECP", c.check_recp),
        ("SELECTOR_PROMOTION", c.check_selector_shared_app_promotion),
        ("PUBLICATION_PATCH_JOURNAL", c.check_generic_ep_patch_journal),
        ("CLOSURE_MATERIALIZATION", c.check_generic_closure_materialization),
        ("FIBONACCI", c.check_fibonacci),
    ):
        checker()
        print(label + "_PASS", flush=True)
    print("INTEGER_PROFILE_NATIVE_PASS", flush=True)


if __name__ == "__main__":
    check()

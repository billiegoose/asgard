"""Compile THOR to the standalone board's checked flash command image."""

import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.boards.red2_basys3.run import (  # noqa: E402
    compile_program,
    runtime,
    verify_preparation,
)

MAGIC = b"RED2FLSH"
HEADER = struct.Struct("<8sIIII16sIII12s")
COMMAND_BYTES = 91
FLASH_OFFSET = 0x220000
DEFAULT_PREPARED = ROOT / "build/red2-basys3-standalone-quantum-v8-seed2"


def compile_image(source, prepared, quantum=20):
    hw = runtime()
    provenance, layout = verify_preparation(prepared, hw, allow_standalone=True)
    return encode_image(
        source, hw, layout, quantum, provenance["candidate_source_sha256"]
    )


def compile_simulation_image(source, core, quantum=20):
    """Use a source-checked core ABI before its physical board qualification."""
    from scripts.experiments.red2_cfg_pilot.rtl_trace import PortLayout

    hw = runtime()
    provenance = json.loads((core / "provenance.json").read_text())

    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    if digest(Path(hw._syn_machine.__file__)) != provenance["original_source_sha256"]:
        raise ValueError("simulation core differs from the host ABI source")
    if digest(core / "machine.py") != provenance["candidate_source_sha256"]:
        raise ValueError("simulation candidate source changed")
    return encode_image(
        source, hw, PortLayout(core), quantum, provenance["candidate_source_sha256"]
    )


def encode_image(source, hw, layout, quantum, source_sha256):
    if not 0 < quantum < 1 << 32:
        raise ValueError("standalone quantum must be positive and fit 32 bits")
    codec, image, metadata = compile_program(hw, source, quantum)
    commands = []

    def add(op, **fields):
        bits, width = layout.pack(layout.input_type, hw._command(op, **fields))
        assert width == 722
        commands.append(bits.to_bytes(COMMAND_BYTES, "little"))

    for address, word in enumerate(image.state.memory):
        add(
            hw._syn_machine.CMD_LOAD_MEMORY, address=address, word=hw._word_struct(word)
        )
    for address, control in enumerate(image.state.control_stack):
        if control:
            add(
                hw._syn_machine.CMD_LOAD_CONTROL,
                address=address,
                control=hw._control_struct(control),
            )
    for slot, meta in enumerate(metadata):
        aux = meta["scalar_op"] | meta["prim0_role"] << 5 | meta["host_op"] << 8
        aux |= meta["special_flags"] << 11
        value = (
            meta["struct_tag_id"]
            | meta["struct_offset"] << 32
            | meta["struct_role"] << 64
        )
        add(
            hw.CMD_LOAD_LITERAL_META,
            address=slot,
            value=meta["literal_id"],
            aux=aux,
            word=hw._word_struct(value),
        )
    add(hw.CMD_LOAD_STATE, state=hw._state_struct(image.state))
    payload = b"".join(commands)
    from red2.representation import MuredOpcode, Word

    nil = codec.encode_word(Word(MuredOpcode.SYM, "NIL"))
    pair_id = codec.literal_id("PAIR")
    header = HEADER.pack(
        MAGIC,
        1,
        len(commands),
        quantum,
        256,
        nil.to_bytes(16, "little"),
        len(payload),
        zlib.crc32(payload),
        pair_id,
        bytes(12),
    )
    assert len(header) == 64
    result = header + payload
    assert len(result) <= 0x400000 - FLASH_OFFSET
    return result, {
        "source": source,
        "quantum": quantum,
        "command_count": len(commands),
        "flash_offset": FLASH_OFFSET,
        "literal_ids": codec._literal_to_id,
        "core_source_sha256": source_sha256,
        "format": "RED2FLSH v1; 64-byte header, 91-byte little-endian ABI commands",
        "sha256": hashlib.sha256(result).hexdigest(),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", type=Path, required=True)
    p.add_argument(
        "--prepared",
        type=Path,
        default=DEFAULT_PREPARED,
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--quantum", type=int, default=20)
    a = p.parse_args()
    data, record = compile_image(a.file.read_text(), a.prepared, a.quantum)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("xb") as f:
        f.write(data)
    a.output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"Compiled {a.file}: {len(data)} bytes, {record['command_count']} commands")


if __name__ == "__main__":
    main()

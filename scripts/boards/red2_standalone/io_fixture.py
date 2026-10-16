"""Public-ABI fixtures for inline values produced by residual reconstruction."""

import hashlib
import zlib


def inline_words(role, word, opcode):
    if role == "IO-THEN":
        value = word(opcode.SYM, "NIL")
        body = [word(opcode.INT, 65), word(opcode.PRIM_1, "UART-TX", True)]
    elif role == "IO-BIND":
        value = word(opcode.INT, 65)
        body = [
            word(opcode.LAMBDA, 1),
            word(opcode.APP_VAR, 0),
            word(opcode.PRIM_1, "UART-TX", True),
        ]
    else:
        raise ValueError(role)
    return [
        word(opcode.APP, 3),
        value,
        word(opcode.PRIM_0, role, True),
        *body,
        word(opcode.STOP),
    ]


def compile_inline_image(core, role):
    from scripts.boards.red2_standalone.image import (
        COMMAND_BYTES,
        HEADER,
        compile_simulation_image,
        runtime,
    )
    from scripts.experiments.red2_cfg_pilot.rtl_trace import PortLayout

    source = (
        "(IO-THEN NIL (UART-TX 65))"
        if role == "IO-THEN"
        else "(IO-BIND 65 (LAMBDA (x) (UART-TX x)))"
    )
    data, record = compile_simulation_image(source, core, quantum=3)
    from red2.representation import MuredOpcode, Word

    hw = runtime()
    codec = hw.RED2ABICodec()
    for literal, expected in sorted(record["literal_ids"].items(), key=lambda p: p[1]):
        assert codec.literal_id(literal) == expected
    words = [codec.encode_word(w) for w in inline_words(role, Word, MuredOpcode)]
    layout = PortLayout(core)
    commands = []
    for start in range(HEADER.size, len(data), COMMAND_BYTES):
        command = layout.unpack(
            layout.input_type,
            int.from_bytes(data[start : start + COMMAND_BYTES], "little"),
        )
        if command.op == hw._syn_machine.CMD_LOAD_MEMORY and command.address < len(
            words
        ):
            command = command._replace(word=hw._word_struct(words[command.address]))
        elif command.op == hw._syn_machine.CMD_LOAD_STATE:
            command = command._replace(state=command.state._replace(fsp=len(words) - 1))
        bits, width = layout.pack(layout.input_type, command)
        assert width == 722
        commands.append(bits.to_bytes(COMMAND_BYTES, "little"))
    payload = b"".join(commands)
    header = list(HEADER.unpack(data[: HEADER.size]))
    header[7] = zlib.crc32(payload)
    data = HEADER.pack(*header) + payload
    record["fixture"] = f"{role} with an inline first value and no child JOIN frame"
    record["sha256"] = hashlib.sha256(data).hexdigest()
    return data, record

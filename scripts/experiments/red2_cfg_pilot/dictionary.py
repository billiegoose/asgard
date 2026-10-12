"""Deduplicate immutable control words with one extra synchronous ROM phase."""

import ast


def encode(text, manifest):
    tree = ast.parse(text)
    node = next(
        n
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "CONTROL_INIT" for t in n.targets)
    )
    words = ast.literal_eval(node.value)
    unique = list(dict.fromkeys(words))
    indices = {word: i for i, word in enumerate(unique)}
    pointers = [indices[word] for word in words]
    assert [unique[p] for p in pointers] == words
    bits = max(1, (len(unique) - 1).bit_length())
    depth = 1 << bits
    start = text.index("CONTROL_INIT =")
    end = text.index("dispatch_rom, _ =", start)
    definitions = (
        f"control_index_t = make_uint_t({bits})\n"
        f"CONTROL_INIT = {unique!r}\n"
        f"control_rom, _ = make_ram(control_word_t, {depth}, ports=('r',), "
        "read_latency=1, init=CONTROL_INIT)\n"
        "control_index_rom, _ = make_ram(control_index_t, "
        f"{manifest['control_words']}, "
        f"ports=('r',), read_latency=1, init={pointers!r})\n"
    )
    text = text[:start] + definitions + text[end:]
    old = """    rom_req: control_rom.p0_in_t
    rom_req.addr = pc
    rom_req.valid = 1
    rom_out = control_rom(rom_req)
"""
    new = """    control_index_req: control_index_rom.p0_in_t
    control_index_req.addr = pc
    control_index_req.valid = 1
    control_index_out = control_index_rom(control_index_req)
    rom_req: control_rom.p0_in_t
    rom_req.addr = control_index_out.p0.rd_data
    rom_req.valid = 1
    rom_out = control_rom(rom_req)
"""
    assert text.count(old) == 1
    text = text.replace(old, new)
    old = """    elif incoming_phase == 2:
        phase = 3
"""
    new = """    elif incoming_phase == 2:
        phase = 8
    elif incoming_phase == 8:
        phase = 3
"""
    assert text.count(old) == 1
    text = text.replace(old, new)
    text = text.replace("phase: Reg[uint3_t]", "phase: Reg[uint4_t]")
    text = text.replace("incoming_phase: uint3_t", "incoming_phase: uint4_t")
    manifest["control_dictionary"] = {
        "method": "Immutable instruction index ROM and deduplicated word ROM",
        "logical_rows": len(words),
        "unique_words": len(unique),
        "index_bits": bits,
        "dictionary_depth": depth,
        "reconstruction_exact": True,
        "extra_fetch_cycles": 1,
    }
    return text

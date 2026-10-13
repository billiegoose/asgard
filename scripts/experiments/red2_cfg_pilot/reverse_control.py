"""Nonzero state witnesses for EP reverse control and its scalar launch bank."""


def witness(hw, widths, keys, trial):
    opcodes = [
        hw.MOP_INT,
        hw.MOP_FLOAT,
        hw.MOP_CHAR,
        hw.MOP_SYM,
        hw.MOP_PRIM_0,
        hw.MOP_PRIM_1,
        hw.MOP_PRIM_2,
        hw.MOP_UBV,
        hw.MOP_CLOSURE,
    ]
    if trial >= 30:
        return None
    opcode = opcodes[trial // 2] if trial < 18 else hw.MOP_INT
    kind = hw.DATA_FLOAT64 if opcode == hw.MOP_FLOAT else hw.DATA_SIGNED
    values = {k: (1 << widths[k]) - 1 for k in keys}
    selected = {
        "microstate": hw.MICRO_EP_REVERSE_CONTROL_READ,
        "red2_fault": 0,
        "hw_fault": 0,
        "pc": 20,
        "fsp": 32,
        "env": 200,
        "free_space": 240,
        "control_top": 1,
        "q": trial % 2,
        "phi": 12,
        "fire": 1,
        "prim_id": 3,
        "ep_target": 4,
        "ep_terminal_word.lo": 7,
        "ep_terminal_word.hi": (1 << 26) | (opcode << 21) | (kind << 17),
    }
    response = [0, 0, 200 + trial % 2, 0, hw.CONTROL_ADDRESS]
    if trial == 18:
        selected["control_top"] = 257
    elif trial == 19:
        selected["control_top"] = 0
    elif trial == 20:
        response[2:] = [0, 0, 0]
    elif trial == 21:
        response[4] = 15
    elif trial == 22:
        selected["prim_id"] = 0
    elif trial == 23:
        response[2] = 257
    elif trial == 24:
        selected["fsp"] = 256
        response[2] = 201
    elif trial == 25:
        selected["free_space"] = 32
        response[2] = 201
    elif trial in {26, 27, 28}:
        selected["ep_terminal_word.hi"] = (
            (1 << 26)
            | (hw.MOP_UBV << 21)
            | ((hw.DATA_SIGNED if trial != 27 else hw.DATA_FLOAT64) << 17)
        )
        if trial == 26:
            selected["ep_terminal_word.lo"] = 1 << 63
        elif trial == 28:
            selected["phi"] = 0
    elif trial == 29:
        selected["ep_terminal_word.hi"] = (1 << 26) | (hw.MOP_CLOSURE << 21)
        selected["free_space"] = 33
    values.update({k: v for k, v in selected.items() if k in values})
    return values, response

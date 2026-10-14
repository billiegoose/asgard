"""Share logical left/right variable shifts using fixed bit-reversal wiring."""

OLD_SHIFTS = """    elif row.op == OP_shr:
        result = 0
        if b[63:6] == 0:
            result = a >> b[5:0]
    elif row.op == OP_shl:
        result = 0
        if b[63:6] == 0:
            result = a << b[5:0]
"""


def reverse_lines(target, source):
    lines = [f"    {target}: uint64_t = {source}\n"]
    for distance in (1, 2, 4, 8, 16, 32):
        mask = sum(
            ((1 << distance) - 1) << offset
            for offset in range(0, 64, distance * 2)
        )
        lines.append(
            f"    {target} = (({target} & {mask}) << {distance}) "
            f"| (({target} >> {distance}) & {mask})\n"
        )
    return "".join(lines)


def datapath():
    return (
        reverse_lines("shift_reverse_input", "a")
        + "    shift_input: uint64_t = a\n"
        "    if row.op == OP_shl:\n"
        "        shift_input = shift_reverse_input\n"
        "    shift_right: uint64_t = shift_input >> b[5:0]\n"
        + reverse_lines("shift_reverse_output", "shift_right")
        + "    shift_result: uint64_t = shift_right\n"
        "    if row.op == OP_shl:\n"
        "        shift_result = shift_reverse_output\n"
        "    if b[63:6] != 0:\n"
        "        shift_result = 0\n"
    )


def share(text):
    anchor = "    result: uint64_t = a\n"
    if text.count(anchor) != 1 or text.count(OLD_SHIFTS) != 1:
        raise ValueError("unexpected shared-shift emitter template")
    text = text.replace(anchor, datapath() + anchor)
    return text.replace(
        OLD_SHIFTS,
        "    elif row.op == OP_shr or row.op == OP_shl:\n"
        "        result = shift_result\n",
    )

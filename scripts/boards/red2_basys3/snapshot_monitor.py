"""Prepare an optional status-snapshot implementation of the UART serializer."""


def snapshot_response(source):
    replacements = (
        (
            "    reg [631:0] response = 0;",
            "    reg [631:0] response = 0;\n"
            "    wire [6:0] payload_index = index - 7'd3;\n"
            "    wire [9:0] payload_offset = {payload_index, 3'b0};\n"
            "    wire [7:0] payload_byte = response[payload_offset +: 8];",
        ),
        ("default: tx_data = response[7:0];", "default: tx_data = payload_byte;"),
        (
            "crc <= update_crc(crc, response[7:0]);",
            "crc <= update_crc(crc, payload_byte);",
        ),
        ("                        response <= {8'b0, response[631:8]};\n", ""),
    )
    # The byte index and padding are specific to the checked 626-bit public ABI.
    # Fail on a changed frame layout or new response writer instead of applying
    # a stale transformation to a revised monitor.
    guards = (
        "input [625:0] result",
        "reg [6:0] index = 0;",
        "response <= {6'b0, result};",
        "if (index >= 3 && index <= 81) begin",
        *(before for before, _ in replacements),
    )
    for fragment in guards:
        if source.count(fragment) != 1:
            raise ValueError(f"Unexpected monitor serializer shape: {fragment.strip()}")
    if source.count("response <=") != 2:
        raise ValueError("Unexpected response writer outside capture and shift")
    for before, after in replacements:
        source = source.replace(before, after)
    return source

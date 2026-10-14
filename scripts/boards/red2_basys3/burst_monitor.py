# ruff: noqa: E501 -- preserve the hardware-tested Verilog replacement text exactly
"""Optional counted CLOCK delivery in the UART frontend; core ABI is unchanged."""

MAX_CLOCK_BURST = (1 << 20) - 1


def clock_burst_command(command: int, count: int) -> int:
    """Encode repeated identical zero-value CLOCKs for a burst-capable image."""
    if not 0 <= command < 1 << 722:
        raise ValueError("command exceeds the hardware input width")
    if command & 15 != 7 or (command >> 280) & 0xFFFFFFFF:
        raise ValueError("bursts require a CLOCK command with value zero")
    if not 1 <= count <= MAX_CLOCK_BURST:
        raise ValueError("burst count must be between 1 and 1048575")
    return (command & ~15) | 10 | (count << 280)


def burst_trace(rows):
    """Yield (wire command, last pre-edge status, edge count) per packet.

    Only adjacent identical CLOCKs with zero value are combined. Returned
    statuses sample endpoints; intermediate statuses are not compared.
    """
    pending = None
    expected = count = 0
    for command, status in rows:
        if command & 15 == 10:
            raise ValueError("native opcode 10 is reserved by the burst frontend")
        eligible = command & 15 == 7 and not ((command >> 280) & 0xFFFFFFFF)
        if pending is not None and (
            command != pending or not eligible or count == MAX_CLOCK_BURST
        ):
            yield (
                clock_burst_command(pending, count) if count > 1 else pending,
                expected,
                count,
            )
            pending = None
        if pending is None:
            pending, count = command, 0
        expected, count = status, count + 1
    if pending is not None:
        yield (
            clock_burst_command(pending, count) if count > 1 else pending,
            expected,
            count,
        )


def burst_clock(source):
    guards = (
        "input [625:0] result",
        "output reg [721:0] command",
        "reg [3:0] state = IDLE;",
        "reg [727:0] request = 0;",
        "core_ce <= 0;",
        "request[727:722] == 0",
    )
    for fragment in guards:
        if source.count(fragment) != 1:
            raise ValueError("Unexpected burst monitor ABI: " + fragment)
    replacements = [
        (
            "SAMPLE=6, EXECUTE=7, SETUP_TX=8, SEND=9, DRAIN=10;",
            "SAMPLE=6, EXECUTE=7, SETUP_TX=8, SEND=9, DRAIN=10,\n               BURST_SETUP=11, BURST_RUN=12;",
        ),
        (
            "    reg [631:0] response = 0;",
            "    reg [631:0] response = 0;\n    reg [19:0] burst_remaining = 0;",
        ),
        (
            """                            command <= request[721:0];
                            state <= SAMPLE;""",
            """                            if (request[3:0] == 4'd10) begin
                                if (request[311:300] == 0 && request[299:280] != 0) begin
                                    command <= {request[721:312], 32'b0, request[279:4], 4'd7};
                                    burst_remaining <= request[299:280];
                                    state <= BURST_SETUP;
                                end else begin error <= 1; state <= IDLE; end
                            end else begin
                                command <= request[721:0];
                                state <= SAMPLE;
                            end""",
        ),
        (
            """                SETUP_TX: begin index <= 0; crc <= 16'hffff; state <= SEND; end""",
            """                BURST_SETUP: if (!reset) begin
                    core_ce <= 1;
                    state <= BURST_RUN;
                end
                BURST_RUN: if (!reset) begin
                    if (burst_remaining == 20'd1) begin
                        response <= {6'b0, result};
                        burst_remaining <= 0;
                        activity <= ~activity;
                        state <= SETUP_TX;
                    end else begin
                        core_ce <= 1;
                        burst_remaining <= burst_remaining - 20'd1;
                    end
                end
                SETUP_TX: begin index <= 0; crc <= 16'hffff; state <= SEND; end""",
        ),
    ]
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError("Unexpected burst monitor shape: " + before)
        source = source.replace(before, after)
    return source

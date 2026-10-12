module red2_basys3 (
    input clk_100p0, input RsRx, output RsTx,
    output [7:0] LD
);
    wire raw_clock, feedback, feedback_global, clock, locked;
    // 100 MHz input -> 1 GHz VCO -> 10 MHz. Match fpgatool's tested primitives.
    MMCME2_ADV #(
        .BANDWIDTH("OPTIMIZED"), .CLKIN1_PERIOD("10.0"),
        .CLKFBOUT_MULT_F("10.0"), .DIVCLK_DIVIDE(1),
        .CLKOUT0_DIVIDE_F("100.0"), .COMPENSATION("ZHOLD"),
        .STARTUP_WAIT("FALSE")
    ) mmcm (
        .CLKIN1(clk_100p0), .CLKIN2(1'b0), .CLKINSEL(1'b1),
        .CLKFBIN(feedback_global), .CLKFBOUT(feedback), .CLKOUT0(raw_clock),
        .LOCKED(locked), .RST(1'b0), .PWRDWN(1'b0),
        .DADDR(7'b0), .DI(16'b0), .DCLK(1'b0), .DEN(1'b0), .DWE(1'b0),
        .PSCLK(1'b0), .PSEN(1'b0), .PSINCDEC(1'b0)
    );
    BUFG feedback_buffer (.I(feedback), .O(feedback_global));
    BUFG monitor_buffer (.I(raw_clock), .O(clock));
    (* ASYNC_REG = "TRUE" *) reg ready_meta = 0, ready = 0;
    always @(posedge clock or negedge locked) begin
        if (!locked) begin ready_meta <= 0; ready <= 0; end
        else begin ready_meta <= 1; ready <= ready_meta; end
    end
    wire [7:0] rx_data, tx_data;
    wire rx_valid, tx_valid, tx_ready, framing_error, core_ce, core_clock;
    wire active, error, activity;
    wire [721:0] command;
    wire [625:0] result;
    red2_uart uart (
        .clk(clock), .reset(!ready), .rx(RsRx), .tx(RsTx),
        .rx_data(rx_data), .rx_valid(rx_valid), .framing_error(framing_error),
        .tx_data(tx_data), .tx_valid(tx_valid), .tx_ready(tx_ready)
    );
    red2_monitor monitor (
        .clk(clock), .reset(!ready), .rx_data(rx_data), .rx_valid(rx_valid),
        .framing_error(framing_error), .tx_data(tx_data), .tx_valid(tx_valid),
        .tx_ready(tx_ready), .command(command), .result(result),
        .core_ce(core_ce), .active(active), .error(error), .activity(activity)
    );
    // Stop the whole core between commands, including synchronous RAM reads.
    // A logic-gated clock or CMD_NOP idle loop would not preserve trace timing.
    BUFGCE core_buffer (.I(raw_clock), .CE(core_ce && ready), .O(core_clock));
    red2_packed_core core (.clk_25p0(core_clock), .incoming(command), .result(result));
    assign LD = {activity, active, error, |result[8:3], result[296],
                 result[625], ready, locked};
endmodule

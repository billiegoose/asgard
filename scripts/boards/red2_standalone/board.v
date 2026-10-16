module red2_basys3 (
    input clk_100p0, input RsRx, output RsTx,
    output QspiDQ0, input QspiDQ1, output QspiDQ2, output QspiDQ3,
    output QspiCSn, output [7:0] LD
);
    wire raw_clock, feedback, feedback_global, clock, locked;
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
    (* ASYNC_REG="TRUE" *) reg ready_meta=0,ready=0;
    always @(posedge clock or negedge locked) begin
        if(!locked) begin ready_meta<=0;ready<=0;end
        else begin ready_meta<=1;ready<=ready_meta;end
    end
    wire [7:0] rx_data,tx_data,flash_data,fault;
    wire rx_valid,tx_valid,tx_ready,framing_error,core_ce,core_clock;
    wire flash_start,flash_take,flash_stop,flash_valid,flash_clock;
    wire running,halted,activity;
    wire [63:0] milliseconds;
    wire [721:0] command;
    wire [625:0] result;
    red2_uart uart (
        .clk(clock),.reset(!ready),.rx(RsRx),.tx(RsTx),
        .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error),
        .tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready)
    );
    red2_flash_stream flash (
        .clk(clock),.reset(!ready),.start(flash_start),.take(flash_take),.stop(flash_stop),
        .data(flash_data),.valid(flash_valid),.miso(QspiDQ1),
        .mosi(QspiDQ0),.sck(flash_clock),.cs_n(QspiCSn)
    );
    assign QspiDQ2=1'b1;
    assign QspiDQ3=1'b1;
    STARTUPE2 startup (
        .CLK(1'b0),.GSR(1'b0),.GTS(1'b0),.KEYCLEARB(1'b1),.PACK(1'b0),
        .USRCCLKO(flash_clock),.USRCCLKTS(1'b0),.USRDONEO(1'b1),.USRDONETS(1'b1)
    );
    red2_standalone_controller controller (
        .clk(clock),.reset(!ready),.flash_start(flash_start),.flash_take(flash_take),
        .flash_stop(flash_stop),.flash_data(flash_data),.flash_valid(flash_valid),
        .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error),
        .tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready),
        .command(command),.result(result),.core_ce(core_ce),
        .running(running),.halted(halted),.fault(fault),.activity(activity),
        .milliseconds(milliseconds)
    );
    BUFGCE core_buffer (.I(raw_clock),.CE(core_ce && ready),.O(core_clock));
    red2_packed_core core (.clk_25p0(core_clock),.incoming(command),.result(result));
    assign LD={activity,|fault,halted,running,milliseconds[9],ready,locked,tx_valid};
endmodule

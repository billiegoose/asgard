module standalone_sim_top (
    input clk, input reset, input [7:0] flash_data, input flash_valid,
    output flash_start, output flash_take, output flash_stop,
    input rx, output tx, output [7:0] observed_data, output observed_valid,
    output running, output halted, output [7:0] fault,
    output [63:0] milliseconds, output resume_valid,
    output [2:0] host_op, output [63:0] resume_data,
    output [15:0] pc, output [15:0] fsp, output [7:0] microstate,
    output [5:0] adapter_state, output [2:0] status, output [2:0] red2_fault,
    output [2:0] hw_fault,
    output [31:0] restarts, output [8:0] residual_words
);
    wire [7:0] rx_data,tx_data;
    wire rx_valid,framing_error,tx_valid,tx_ready,core_ce,activity;
    wire [721:0] command;
    wire [625:0] result;
    red2_standalone_controller #(.CYCLES_PER_MS(100)) controller (
        .clk(clk),.reset(reset),.flash_start(flash_start),.flash_take(flash_take),
        .flash_stop(flash_stop),.flash_data(flash_data),.flash_valid(flash_valid),
        .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error),
        .tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready),
        .command(command),.result(result),.core_ce(core_ce),
        .running(running),.halted(halted),.fault(fault),.activity(activity),
        .milliseconds(milliseconds)
    );
    red2_uart #(.DIV(4)) uart (.clk(clk),.reset(reset),.rx(rx),.tx(tx),
        .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error),
        .tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready));
    red2_uart #(.DIV(4)) observer (.clk(clk),.reset(reset),.rx(tx),
        .rx_data(observed_data),.rx_valid(observed_valid),.framing_error(),
        .tx_data(8'b0),.tx_valid(1'b0),.tx_ready(),.tx());
    reg admitted_ce=0;
    always @(negedge clk) admitted_ce<=core_ce;
    replay_top core (.clk_25p0(clk & admitted_ce),.incoming(command),.result(result));
    assign adapter_state=controller.state;assign status=controller.response[2:0];
    assign resume_valid=core_ce && command[3:0]==6;
    assign resume_data=command[83:20];
    assign host_op=controller.response[299:297];
    assign pc=result[33:18];assign fsp=result[49:34];
    assign microstate=result[16:9];assign red2_fault=result[5:3];
    assign restarts=controller.quantum_restarts;
    assign residual_words=controller.residual_words;
    assign hw_fault=controller.response[8:6];
endmodule

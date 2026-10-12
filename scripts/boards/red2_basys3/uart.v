// Board-independent 8-N-1 UART. DIV=87 at 10 MHz gives 114943 baud.
module red2_uart #(
    parameter DIV = 87
) (
    input clk, input reset, input rx,
    output reg [7:0] rx_data = 0, output reg rx_valid = 0,
    output reg framing_error = 0,
    input [7:0] tx_data, input tx_valid, output tx_ready,
    output tx
);
    (* ASYNC_REG = "TRUE" *) reg rx_meta = 1, rx_sync = 1;
    always @(posedge clk) begin
        rx_meta <= rx;
        rx_sync <= rx_meta;
    end
    reg [1:0] rx_state = 0;
    reg [15:0] rx_timer = 0;
    reg [2:0] rx_bit = 0;
    reg [7:0] rx_shift = 0;
    always @(posedge clk) begin
        rx_valid <= 0;
        framing_error <= 0;
        if (reset) begin
            rx_state <= 0;
            rx_timer <= 0;
        end else case (rx_state)
            0: if (!rx_sync) begin rx_state <= 1; rx_timer <= 0; end
            1: if (rx_timer == DIV/2-1) begin
                rx_timer <= 0;
                if (!rx_sync) begin rx_state <= 2; rx_bit <= 0; end
                else rx_state <= 0;
            end else rx_timer <= rx_timer + 1;
            2: if (rx_timer == DIV-1) begin
                rx_timer <= 0;
                rx_shift <= {rx_sync, rx_shift[7:1]};
                if (rx_bit == 7) rx_state <= 3;
                else rx_bit <= rx_bit + 1;
            end else rx_timer <= rx_timer + 1;
            3: if (rx_timer == DIV-1) begin
                rx_timer <= 0;
                rx_state <= 0;
                if (rx_sync) begin rx_data <= rx_shift; rx_valid <= 1; end
                else framing_error <= 1;
            end else rx_timer <= rx_timer + 1;
        endcase
    end
    reg [9:0] tx_shift = 10'h3ff;
    reg [3:0] tx_left = 0;
    reg [15:0] tx_timer = 0;
    assign tx_ready = tx_left == 0;
    assign tx = tx_left == 0 ? 1'b1 : tx_shift[0];
    always @(posedge clk) begin
        if (reset) begin
            tx_left <= 0;
            tx_timer <= 0;
            tx_shift <= 10'h3ff;
        end else if (tx_ready) begin
            if (tx_valid) begin
                tx_shift <= {1'b1, tx_data, 1'b0};
                tx_left <= 10;
                tx_timer <= 0;
            end
        end else if (tx_timer == DIV-1) begin
            tx_timer <= 0;
            tx_left <= tx_left - 1;
            tx_shift <= {1'b1, tx_shift[9:1]};
        end else tx_timer <= tx_timer + 1;
    end
endmodule

// Fixed frames, little-endian payloads, CRC16-CCITT (init ffff, poly 1021).
// Request:  a5 5a sequence command[91 bytes] crc[2 bytes, low first].
// Response: 5a a5 sequence status[79 bytes]  crc[2 bytes, low first].
// CRC covers sequence and payload. Invalid frames never clock the RED2 core.
module red2_monitor #(parameter TIMEOUT_BITS = 24) (
    input clk, input reset,
    input [7:0] rx_data, input rx_valid, input framing_error,
    output reg [7:0] tx_data, output tx_valid, input tx_ready,
    output reg [721:0] command = 0, input [625:0] result,
    output reg core_ce = 0,
    output active, output reg error = 0, output reg activity = 0
);
    localparam IDLE=0, MAGIC=1, SEQ=2, BODY=3, CRC_LO=4, CRC_HI=5,
               SAMPLE=6, EXECUTE=7, SETUP_TX=8, SEND=9, DRAIN=10;
    reg [3:0] state = IDLE;
    reg [7:0] sequence_id = 0;
    reg [6:0] index = 0;
    reg [727:0] request = 0;
    reg [631:0] response = 0;
    reg [15:0] crc = 16'hffff;
    reg [7:0] crc_low = 0;
    reg [TIMEOUT_BITS-1:0] silence = 0;
    function [15:0] update_crc;
        input [15:0] initial_crc;
        input [7:0] data;
        reg [15:0] work;
        integer bit_index;
        begin
            work = initial_crc ^ {data, 8'b0};
            for (bit_index=0; bit_index<8; bit_index=bit_index+1)
                work = work[15] ? (work << 1) ^ 16'h1021 : work << 1;
            update_crc = work;
        end
    endfunction
    assign active = state >= SAMPLE;
    assign tx_valid = state == SEND;
    always @* begin
        case (index)
            0: tx_data = 8'h5a;
            1: tx_data = 8'ha5;
            2: tx_data = sequence_id;
            82: tx_data = crc[7:0];
            83: tx_data = crc[15:8];
            default: tx_data = response[7:0];
        endcase
    end
    always @(posedge clk) begin
        core_ce <= 0;
        if (reset) begin
            state <= IDLE;
            command <= 0;
            error <= 0;
            silence <= 0;
            activity <= 0;
        end else begin
            if (framing_error) error <= 1;
            // Recover an abandoned partial packet after ~1.68 seconds.
            if (state > IDLE && state <= CRC_HI) silence <= silence + 1;
            else silence <= 0;
            if (rx_valid && state <= CRC_HI) begin
                silence <= 0;
                case (state)
                    IDLE: if (rx_data == 8'ha5) state <= MAGIC;
                    MAGIC: if (rx_data == 8'h5a) state <= SEQ;
                           else if (rx_data != 8'ha5) state <= IDLE;
                    SEQ: begin
                        sequence_id <= rx_data;
                        crc <= update_crc(16'hffff, rx_data);
                        index <= 0;
                        state <= BODY;
                    end
                    BODY: begin
                        request <= {rx_data, request[727:8]};
                        crc <= update_crc(crc, rx_data);
                        if (index == 90) state <= CRC_LO;
                        else index <= index + 1;
                    end
                    CRC_LO: begin crc_low <= rx_data; state <= CRC_HI; end
                    CRC_HI: begin
                        if ({rx_data, crc_low} == crc && request[727:722] == 0) begin
                            command <= request[721:0];
                            state <= SAMPLE;
                        end else begin error <= 1; state <= IDLE; end
                    end
                endcase
            end else if (&silence && state > IDLE && state <= CRC_HI) begin
                state <= IDLE;
                error <= 1;
            end
            case (state)
                SAMPLE: begin
                    // Observe before the one core rising edge, as in RTL traces.
                    response <= {6'b0, result};
                    core_ce <= 1;
                    state <= EXECUTE;
                end
                EXECUTE: begin
                    // BUFGCE sampled CE while the source clock was low.
                    // This edge executes exactly the accepted command.
                    activity <= ~activity;
                    state <= SETUP_TX;
                end
                SETUP_TX: begin index <= 0; crc <= 16'hffff; state <= SEND; end
                SEND: if (tx_ready) begin
                    if (index == 2) crc <= update_crc(crc, sequence_id);
                    if (index >= 3 && index <= 81) begin
                        crc <= update_crc(crc, response[7:0]);
                        response <= {8'b0, response[631:8]};
                    end
                    if (index == 83) state <= DRAIN;
                    else index <= index + 1;
                end
                DRAIN: if (tx_ready) state <= IDLE;
            endcase
        end
    end
endmodule

// Read the QSPI NOR in its power-on-compatible single-bit 03h read mode.
// No flash writes, mode changes, or quad-enable register changes in user logic.
module red2_flash_stream #(parameter BASE=24'h220000) (
    input clk, input reset, input start, input take, input stop,
    output reg [7:0] data=0, output reg valid=0,
    input miso, output mosi, output reg sck=0, output reg cs_n=1
);
    localparam IDLE=0, PRIME=1, ADDRESS=2, READ=3, HOLD=4;
    reg [2:0] state=IDLE;
    reg divider=0;
    reg [5:0] count=0;
    reg [31:0] send=0;
    reg [7:0] shift=0;
    assign mosi=send[31];
    always @(posedge clk) begin
        if(reset || stop) begin
            state<=IDLE; cs_n<=1; sck<=0; valid<=0; divider<=0;
        end else begin
            divider<=~divider;
            case(state)
                IDLE: if(start) begin
                    state<=PRIME;count<=0;divider<=0;cs_n<=1;sck<=0;
                end
                // STARTUPE2 needs priming clocks before selecting the flash.
                PRIME: if(divider) begin
                    sck<=~sck;
                    if(sck) begin
                        if(count==7) begin
                            cs_n<=0;send<={8'h03,BASE};count<=0;state<=ADDRESS;
                        end else count<=count+1;
                    end
                end
                ADDRESS: if(divider) begin
                    sck<=~sck;
                    if(sck) begin
                        send<={send[30:0],1'b0};
                        if(count==31) begin count<=0;state<=READ;end
                        else count<=count+1;
                    end
                end
                READ: if(divider) begin
                    sck<=~sck;
                    if(!sck) shift<={shift[6:0],miso};
                    else if(count==7) begin
                        data<=shift;valid<=1;state<=HOLD;count<=0;
                    end else count<=count+1;
                end
                HOLD: if(take) begin valid<=0;state<=READ;divider<=0;end
            endcase
        end
    end
endmodule

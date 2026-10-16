`include "layout.vh"
// Autonomous board adapter. Commands use the unchanged qualified RED2 ABI.
module red2_standalone_controller #(parameter CYCLES_PER_MS=10000) (
    input clk, input reset,
    output reg flash_start=0, output flash_take, output reg flash_stop=0,
    input [7:0] flash_data, input flash_valid,
    input [7:0] rx_data, input rx_valid, input framing_error,
    output reg [7:0] tx_data=0, output tx_valid, input tx_ready,
    output reg [721:0] command=0, input [625:0] result,
    output reg core_ce=0,
    output reg running=0, output reg halted=0,
    output reg [7:0] fault=0, output reg activity=0,
    output reg [63:0] milliseconds=0
);
    localparam BOOT_RESET=0, RESET_WAIT=1, HEADER=2, HEADER_CHECK=3,
        BODY=4, BODY_CHECK=5, BOOT_NEXT=6, BOOT_DONE=7, RUN=8,
        PULSE=9, SETTLE=10, RESUME=11, RECHARGE=12,
        READ_FIRST=13, READ_SECOND=14, READ_DONE=15,
        TX_BYTE=16, TX_DRAIN=17, RX_WAIT=18,
        LIST_DESC=19, LIST_VALUE=20, LIST_TAIL=21, LIST_HEAD=22,
        LIST_HEAD_VALUE=23, LIST_SEND=24, LIST_SEND_DRAIN=25, STOPPED=26;
    reg [5:0] state=BOOT_RESET, after_edge=0, after_read=0;
    reg [625:0] response=0;
    reg [511:0] header=0;
    reg [727:0] load_command=0;
    reg [6:0] byte_index=0;
    reg [15:0] commands_left=0, reset_steps=0;
    reg [31:0] crc=32'hffffffff, quantum=0;
    reg [127:0] nil_word=0;
    reg [31:0] pair_id=0;
    reg [31:0] ms_divider=0;
    reg [127:0] resume_word=0, read_word=0, descriptor=0, tail_descriptor=0;
    reg [7:0] read_address=0, list_root=0;
    reg root_valid=0;
    reg [255:0] visited=0;
    reg [7:0] bytes [0:255];
    reg [8:0] byte_count=0, byte_cursor=0;
    reg [7:0] rx_fifo [0:15];
    reg [3:0] rx_write=0, rx_read=0;
    reg [4:0] rx_count=0;
    wire rx_pop=state==RX_WAIT && rx_count!=0;
    wire [127:0] int_prefix=(128'd1<<90)|(128'd8<<85)|(128'd1<<81);
    assign flash_take=(state==HEADER || state==BODY) && flash_valid;
    assign tx_valid=state==TX_BYTE || state==LIST_SEND;
    function [31:0] crc_byte;
        input [31:0] old_crc;
        input [7:0] data;
        reg [31:0] work;
        integer i;
        begin
            work=old_crc^{24'b0,data};
            for(i=0;i<8;i=i+1) work=work[0] ? (work>>1)^32'hedb88320 : work>>1;
            crc_byte=work;
        end
    endfunction
    function is_int;
        input [127:0] word;
        begin is_int=word[90] && word[89:85]==8 && word[82:81]==1;end
    endfunction
    function is_app;
        input [127:0] word;
        begin is_app=word[90] && word[89:85]==1 && word[82:81]==1;end
    endfunction
    task issue;
        input [721:0] value;
        input [5:0] next_state;
        begin command<=value;core_ce<=1;after_edge<=next_state;state<=PULSE;end
    endtask
    task read_memory;
        input [7:0] address;
        input [5:0] next_state;
        begin read_address<=address;after_read<=next_state;state<=READ_FIRST;end
    endtask
    task fail;
        input [7:0] code;
        begin fault<=code;state<=STOPPED;running<=0;core_ce<=0;flash_stop<=1;end
    endtask
    reg [721:0] work;
    always @(posedge clk) begin
        core_ce<=0;flash_start<=0;
        if(reset) begin
            state<=BOOT_RESET;command<=0;core_ce<=0;fault<=0;running<=0;
            halted<=0;milliseconds<=0;ms_divider<=0;flash_stop<=0;
            byte_index<=0;header<=0;crc<=32'hffffffff;rx_count<=0;
            rx_write<=0;rx_read<=0;reset_steps<=0;activity<=0;
        end else begin
            if(running) begin
                if(ms_divider==CYCLES_PER_MS-1) begin
                    ms_divider<=0;milliseconds<=milliseconds+1;
                end else ms_divider<=ms_divider+1;
            end
            // Bytes arriving before the program starts are deliberately ignored.
            if(running) begin
                case({rx_valid,rx_pop})
                    2'b10: if(rx_count!=16) rx_count<=rx_count+1;
                    2'b01: rx_count<=rx_count-1;
                endcase
                if(rx_valid && (rx_count!=16 || rx_pop)) begin
                    rx_fifo[rx_write]<=rx_data;rx_write<=rx_write+1;
                end
                if(rx_pop) rx_read<=rx_read+1;
            end
            case(state)
                BOOT_RESET: issue(722'd1,RESET_WAIT);
                RESET_WAIT: if(response[`OUT_BUSY]) begin
                    if(reset_steps==65535) fail(8'h80);
                    else begin reset_steps<=reset_steps+1;issue(722'd7,RESET_WAIT);end
                end else begin flash_start<=1;state<=HEADER;end
                HEADER: if(flash_valid) begin
                    header<={flash_data,header[511:8]};
                    if(byte_index==63) begin byte_index<=0;state<=HEADER_CHECK;end
                    else byte_index<=byte_index+1;
                end
                HEADER_CHECK: begin
                    if(header[63:0]!=64'h48534c4632444552 || header[95:64]!=1 ||
                       header[127:96]<1 || header[127:96]>1024 ||
                       header[159:128]==0 || header[191:160]!=256 ||
                       header[351:320]!=header[127:96]*91 ||
                       header[511:416]!=0 || !header[282] || header[281:277]!=11 ||
                       header[274:273]!=3 || header[415:384]==0) fail(8'h81);
                    else begin
                        commands_left<=header[111:96];quantum<=header[159:128];
                        nil_word<=header[319:192];pair_id<=header[415:384];state<=BODY;
                    end
                end
                BODY: if(flash_valid) begin
                    load_command<={flash_data,load_command[727:8]};
                    crc<=crc_byte(crc,flash_data);
                    if(byte_index==90) begin byte_index<=0;state<=BODY_CHECK;end
                    else byte_index<=byte_index+1;
                end
                BODY_CHECK: begin
                    if(load_command[727:722]!=0 ||
                       (commands_left==1 && load_command[3:0]!=8) ||
                       (commands_left!=1 && load_command[3:0]!=2 &&
                         load_command[3:0]!=3 && load_command[3:0]!=9) ||
                       ((load_command[3:0]==2 || load_command[3:0]==3) && load_command[19:4]>=256) ||
                       (load_command[3:0]==9 && load_command[19:4]>=64)) fail(8'h82);
                    else issue(load_command[721:0],BOOT_NEXT);
                end
                BOOT_NEXT: if(response[`OUT_HW_FAULT]!=0 || response[`OUT_RED2_FAULT]!=0) fail(8'h83);
                    else if(commands_left==1) state<=BOOT_DONE;
                    else begin commands_left<=commands_left-1;state<=BODY;end
                BOOT_DONE: begin
                    flash_stop<=1;
                    if((~crc)!=header[383:352]) fail(8'h84);
                    else begin running<=1;milliseconds<=0;ms_divider<=0;state<=RUN;end
                end
                // Sample the command result before its one admitted core edge, exactly
                // as the qualified monitor does. The core exposes next-state outputs.
                PULSE: begin response<=result;state<=SETTLE;activity<=~activity;end
                SETTLE: state<=after_edge;
                RUN: begin
                    case(response[`OUT_STATUS])
                        0: issue(722'd7,RUN);
                        1: begin halted<=1;running<=0;state<=STOPPED;end
                        2: fail(8'h85);
                        3: case(response[`OUT_PENDING_HOST_OP])
                            1: begin resume_word<=int_prefix|milliseconds;state<=RESUME;end
                            2: state<=RX_WAIT;
                            3,4: begin
                                if(response[`OUT_PENDING_HOST_ARGUMENT]==0 ||
                                   response[`OUT_PENDING_HOST_ARGUMENT]>256) fail(8'h86);
                                else begin
                                    byte_count<=0;visited<=0;
                                    read_memory(response[307:300]-1,LIST_DESC);
                                end
                            end
                            default: fail(8'h87);
                        endcase
                        default: fail(8'h88);
                    endcase
                end
                READ_FIRST: begin
                    work=0;work[`IN_ADDRESS]={8'b0,read_address};issue(work,READ_SECOND);
                end
                READ_SECOND: issue(command,READ_DONE);
                READ_DONE: begin read_word<=response[`OUT_MEMORY_READ];state<=after_read;end
                LIST_DESC: if(response[`OUT_PENDING_HOST_OP]==3) begin
                    if(!is_int(read_word)) fail(8'h89);
                    else begin tx_data<=read_word[7:0];state<=TX_BYTE;end
                end else begin descriptor<=read_word;state<=LIST_VALUE;end
                LIST_VALUE: begin
                    if(is_app(descriptor)) begin
                        if(descriptor[63:0]>=256) fail(8'h8a);
                        else begin
                            list_root<=descriptor[7:0];root_valid<=1;
                            read_memory(descriptor[7:0],LIST_TAIL);
                        end
                    end else begin root_valid<=0;read_word<=descriptor;state<=LIST_TAIL;end
                end
                LIST_TAIL: begin
                    if(read_word[90] && read_word[89:85]==11 &&
                       read_word[82:81]==3 && read_word[63:0]==nil_word[63:0]) begin
                        if(byte_count==0) begin resume_word<=nil_word;state<=RESUME;end
                        else begin byte_cursor<=0;tx_data<=bytes[0];state<=LIST_SEND;end
                    end else if(!root_valid || !read_word[90] || read_word[89:85]!=15 ||
                        read_word[82:81]!=3 || read_word[63:0]!={32'b0,pair_id} ||
                        list_root>253 || visited[list_root] || byte_count==256) fail(8'h8b);
                    else begin
                        visited[list_root]<=1;read_memory(list_root+1,LIST_HEAD);
                    end
                end
                LIST_HEAD: begin tail_descriptor<=read_word;read_memory(list_root+2,LIST_HEAD_VALUE);end
                LIST_HEAD_VALUE: begin
                    if(is_app(read_word)) begin
                        if(read_word[63:0]>=256) fail(8'h8c);
                        else read_memory(read_word[7:0],LIST_HEAD_VALUE);
                        // _descriptor_value follows exactly one APP, not a chain.
                        // A second APP is rejected using root_valid as a one-hop flag.
                        if(!root_valid) fail(8'h8c);
                        root_valid<=0;
                    end else if(!is_int(read_word)) fail(8'h8d);
                    else begin
                        bytes[byte_count[7:0]]<=read_word[7:0];byte_count<=byte_count+1;
                        descriptor<=tail_descriptor;state<=LIST_VALUE;
                    end
                end
                TX_BYTE: if(tx_ready) state<=TX_DRAIN;
                TX_DRAIN: if(tx_ready) begin resume_word<=nil_word;state<=RESUME;end
                RX_WAIT: if(rx_count!=0) begin
                    resume_word<=int_prefix|{120'b0,rx_fifo[rx_read]};state<=RESUME;
                end
                LIST_SEND: if(tx_ready) state<=LIST_SEND_DRAIN;
                LIST_SEND_DRAIN: if(tx_ready) begin
                    if(byte_cursor+1==byte_count) begin resume_word<=nil_word;state<=RESUME;end
                    else begin byte_cursor<=byte_cursor+1;tx_data<=bytes[byte_cursor+1];state<=LIST_SEND;end
                end
                RESUME: begin work=0;work[`IN_OP]=6;work[`IN_WORD]=resume_word;issue(work,RECHARGE);end
                RECHARGE: if(response[`OUT_STATUS]==4) fail(8'h8e);
                    else begin work=0;work[`IN_OP]=5;work[`IN_VALUE]=quantum;issue(work,RUN);end
                STOPPED: begin end
                default: fail(8'h8f);
            endcase
            if(running && framing_error) fail(8'h90);
            if(running && rx_valid && rx_count==16 && !rx_pop) fail(8'h91);
        end
    end
endmodule

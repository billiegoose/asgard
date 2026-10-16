`include "layout.vh"
module restart_tb;
    reg clk=0; always #5 clk=~clk;
    reg reset=1,start=0;
    reg [15:0] root=70;
    reg [8:0] limit=212;
    reg [31:0] quantum=20;
    wire [721:0] command;
    wire ce,done;
    wire [7:0] fault;
    wire [8:0] residual;
    reg [625:0] result=0;
    reg [127:0] memory[0:255];
    reg [127:0] read_data=0;
    reg [345:0] loaded_state=0;
    integer i,cycles;
    red2_residual_restart dut(clk,reset,start,root,limit,quantum,result,command,ce,done,fault,residual);
    always @* begin result=0;result[`OUT_MEMORY_READ]=read_data;end
    always @(posedge clk) if(ce) begin
        read_data<=memory[command[`IN_ADDRESS]];
        if(command[`IN_OP]==2) memory[command[`IN_ADDRESS]]<=command[`IN_WORD];
        if(command[`IN_OP]==8) loaded_state<=command[`IN_STATE];
    end
    function [127:0] w;
        input [4:0] op;input head;input [63:0] value;
        begin w=(128'd1<<90)|({123'b0,op}<<85)|({127'b0,head}<<84)|(128'd1<<81)|value;end
    endfunction
    task run;
        input [7:0] expected_fault;
        begin
            @(negedge clk);start=1;
            @(negedge clk);start=0;cycles=0;
            while(!done && cycles<30000) begin @(negedge clk);cycles=cycles+1;end
            if(!done || fault!==expected_fault) $fatal(1,"restart fault %h expected %h cycles %d",fault,expected_fault,cycles);
            @(negedge clk);
        end
    endtask
    initial begin
        for(i=0;i<256;i=i+1) memory[i]=0;
        repeat(3) @(negedge clk);reset=0;
        memory[70]=w(1,0,90);memory[71]=w(1,0,90);
        memory[72]=w(14,1,7)|(128'd1<<80)|(128'd199<<64);
        memory[90]=w(8,1,42);memory[220]=w(8,1,99);
        run(0);
        if(residual!=4 || memory[0]!==w(1,0,3) || memory[1]!==w(1,0,3) ||
           memory[2] !== (w(14,1,7)|(128'd1<<80)|(128'd199<<64)) ||
           memory[3]!==w(8,1,42) || memory[4]!==((128'd1<<90)|(128'd7<<85)) ||
           memory[220]!==w(8,1,99)) $fatal(1,"shared graph, metadata or static definition changed");
        if(loaded_state[31:16]!=4 || loaded_state[48:32]!=212 ||
           loaded_state[98:67]!=20 || loaded_state[147:131]!=212 ||
           loaded_state[179:148]!=1 || loaded_state[15:0]!=0) $fatal(1,"restart registers");
        // A second restart must discard the first forwarding map. A recursive
        // binding includes an inline name and a variable terminator without a head bit.
        memory[70]=w(16,0,50);memory[71]=w(17,0,1);memory[72]=w(21,0,0);
        memory[50]=w(11,0,100);memory[51]=w(6,0,1);memory[52]=w(21,0,0);
        run(0);
        if(residual!=6 || memory[0]!==w(16,0,3) || memory[3]!==w(11,0,100) ||
           memory[4]!==w(6,0,1) || memory[5]!==w(21,0,0)) $fatal(1,"recursive binding relocation");
        // Explicit links into definition storage are copied into the new arena;
        // definition metadata and the original static storage stay unchanged.
        memory[70]=w(1,0,220);memory[71]=w(13,1,7);
        run(0);
        if(residual!=3 || memory[0]!==w(1,0,2) || memory[2]!==w(8,1,99) ||
           memory[220]!==w(8,1,99)) $fatal(1,"static target relocation");
        // A later spine may copy an earlier root as its suffix. Links must use
        // the final forwarding address while both complete copies stay valid.
        memory[70]=w(1,0,81);memory[71]=w(1,0,80);memory[72]=w(14,1,7);
        memory[80]=w(8,0,1);memory[81]=w(8,1,42);
        run(0);
        if(residual!=6 || memory[0]!==w(1,0,5) || memory[1]!==w(1,0,4) ||
           memory[3]!==w(8,1,42) || memory[4]!==w(8,0,1) ||
           memory[5]!==w(8,1,42)) $fatal(1,"overlapping suffix relocation");
        memory[70]=w(1,0,70);memory[71]=w(21,0,0);
        run(0);
        if(residual!=2 || memory[0]!==w(1,0,0) || memory[1]!==w(21,0,0))
            $fatal(1,"cyclic root relocation");
        memory[70]=w(3,1,50);run(8'ha2);
        memory[70]=w(1,0,256);memory[71]=w(8,1,0);run(8'ha4);
        root=0;limit=8;
        for(i=0;i<7;i=i+1) memory[i]=w(8,0,i);
        memory[7]=w(8,1,7);run(8'ha3);
        $display("PASS residual relocation: sharing, metadata, RBLOCK/VAR, overlapping suffixes, cycles, repeated restart, bounds, register reset");
        $finish;
    end
endmodule

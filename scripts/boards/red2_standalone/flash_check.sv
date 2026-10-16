`timescale 1ns/1ps
module flash_check;
    reg clk=0,reset=1,start=0,take=0,stop=0,miso=1;
    wire [7:0] data;wire valid,mosi,sck,cs_n;
    reg [7:0] memory[0:65535];
    reg [31:0] command=0;
    integer bits=0,position=0,output_bit=7,received=0,cycles=0,length=0;
    reg [1023:0] image;
    red2_flash_stream dut(.*);
    always #5 clk=~clk;
    always @(negedge cs_n) begin bits=0;command=0;position=0;output_bit=7;end
    always @(posedge sck) if(!cs_n) begin
        if(bits<32) begin
            command={command[30:0],mosi};bits=bits+1;
            if(bits==32 && command!==32'h03220000) $fatal(1,"wrong flash command/address %h",command);
        end else begin
            if(output_bit==0) begin output_bit=7;position=position+1;end
            else output_bit=output_bit-1;
        end
    end
    always @(negedge sck) if(!cs_n && bits>=32) miso=memory[position][output_bit];
    always @(negedge clk) begin
        take=valid && (cycles%7==0);
        if(take) begin
            if(data!==memory[received]) $fatal(1,"flash byte %0d mismatch %h %h",received,data,memory[received]);
            received=received+1;
            if(received==length) begin
                $display("FLASH SPI PASS %0d bytes with backpressure",received);$finish;
            end
        end
        cycles=cycles+1;
        if(cycles>20000000) $fatal(1,"flash finite cycle bound reached");
    end
    initial begin
        if(!$value$plusargs("image=%s",image) || !$value$plusargs("length=%d",length)) $fatal;
        $readmemh(image,memory,0,length-1);
        repeat(5) @(negedge clk);reset=0;start=1;
        @(negedge clk);start=0;
    end
endmodule

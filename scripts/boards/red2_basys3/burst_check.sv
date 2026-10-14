module test;
reg clk=0; always #5 clk=~clk;
reg reset=1,rx_valid=0,tx_ready=1; reg [7:0] rx_data=0;
wire [7:0] tx_data; wire tx_valid,core_ce,active,error,activity;
wire [721:0] command; wire [625:0] result;
red2_monitor monitor(.clk(clk),.reset(reset),.rx_data(rx_data),.rx_valid(rx_valid),
 .framing_error(1'b0),.tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready),
 .command(command),.result(result),.core_ce(core_ce),.active(active),.error(error),.activity(activity));
reg enabled=0; always @(negedge clk) enabled<=core_ce&&!reset;
wire core_clock=clk&enabled;
integer ticks=0,base=0; time first_edge=0,last_edge=0;
always @(posedge core_clock) begin
 if(ticks==base) first_edge=$time;
 last_edge=$time;
 ticks<=ticks+1;
end
assign result=command[625:0]^ticks;
reg [7:0] requests[0:1055],responses[0:671];
integer counts[0:4]; integer frame,i,j; reg [7:0] actual;
task send_byte(input [7:0] value);
 begin @(negedge clk);rx_data=value;rx_valid=1;@(negedge clk);rx_valid=0;end
endtask
task response_frame(input integer number);
 integer byte_index;
 begin
  for(byte_index=0;byte_index<84;byte_index=byte_index+1) begin
   while(!tx_valid) @(negedge clk);
   actual=tx_data;
   if(actual!==responses[number*84+byte_index])
    $fatal(1,"response mismatch frame %d byte %d got %h expected %h",number,byte_index,actual,responses[number*84+byte_index]);
   @(negedge clk);
  end
 end
endtask
initial begin
 $readmemh("__REQUESTS__",requests);
 $readmemh("__RESPONSES__",responses);
 counts[0]=1;counts[1]=2;counts[2]=257;counts[3]=65537;counts[4]=1048575;
 repeat(6) @(negedge clk);reset=0;
 for(frame=0;frame<5;frame=frame+1) begin
  base=ticks;
  tx_ready=0;
  fork
   begin for(i=0;i<96;i=i+1)send_byte(requests[frame*96+i]);end
   begin
    while(!tx_valid) @(negedge clk);
    if(ticks-base!==counts[frame]) $fatal(1,"wrong count before response");
    repeat(16) begin
     @(negedge clk);
     if(core_ce || enabled || ticks-base!==counts[frame]) $fatal(1,"clock continued under TX stall");
    end
    tx_ready=1;
    response_frame(frame);
   end
  join
  repeat(4) @(negedge clk);
  if(ticks-base!==counts[frame])$fatal(1,"wrong tick count %d expected %d",ticks-base,counts[frame]);
  if(last_edge-first_edge!==10*(counts[frame]-1))$fatal(1,"burst clock gap");
  if(core_ce || enabled || active || error)$fatal(1,"monitor failed to stop");
  $display("BURST_CLOCK_COUNT_PASS %d",counts[frame]);
 end
 for(frame=0;frame<3;frame=frame+1) begin
  base=ticks;
  fork
   begin for(i=0;i<192;i=i+1)send_byte(requests[480+frame*192+i]);end
   response_frame(5+frame);
  join
  repeat(4) @(negedge clk);
  if(ticks-base!==1 || !error || core_ce || enabled || active)$fatal(1,"invalid count caused an edge or reply");
  $display("BURST_INVALID_COUNT_PASS %d",frame);
 end
 $display("BOARD_MONITOR_PASS counted clocks, contiguous edges, last pre-edge output, CRC, full payload");
 $finish;
end
initial begin repeat(1300000) @(posedge clk);$fatal(1,"burst check did not complete");end
endmodule

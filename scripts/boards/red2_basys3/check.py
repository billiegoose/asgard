"""Exercise physical UART framing and replay a validated trace through the monitor."""

import argparse
import binascii
import hashlib
import json
import random
import subprocess
from pathlib import Path

from host import INPUT_BITS, OUTPUT_BITS, request_frame, verify_vectors

HERE = Path(__file__).resolve().parent


def run(output, name, sources, bench):
    path = output / (name + ".sv")
    path.write_text(bench)
    binary = output / (name + ".vvp")
    subprocess.run(
        [
            "iverilog",
            "-g2012",
            "-s",
            "test",
            "-o",
            str(binary),
            *[str(p) for p in sources],
            str(path),
        ],
        check=True,
    )
    log = output / (name + ".log")
    with log.open("x") as stream:
        subprocess.run(
            ["vvp", str(binary)], stdout=stream, stderr=subprocess.STDOUT, check=True
        )
    if "BOARD_MONITOR_PASS" not in log.read_text():
        raise ValueError(f"simulation did not reach explicit success: {log}")
    print(log.read_text(), end="", flush=True)


CRC = """
function [15:0] crc_byte(input [15:0] initial_crc, input [7:0] data);
    reg [15:0] work; integer k;
    begin
        work = initial_crc ^ {data, 8'b0};
        for(k=0;k<8;k=k+1) work = work[15] ? (work<<1)^16'h1021 : work<<1;
        crc_byte = work;
    end
endfunction
"""

GATE = """
reg enabled = 0;
always @(negedge clk) enabled <= core_ce;
wire core_clock = clk & enabled;
integer core_ticks = 0;
always @(posedge core_clock) core_ticks <= core_ticks + 1;
"""


def uart_check(output, monitor=None):
    randomizer = random.Random(0x52454432)
    commands = [
        1,
        randomizer.getrandbits(INPUT_BITS),
        randomizer.getrandbits(INPUT_BITS),
        7,
    ]
    sequences = [0, 255, 0, 1]
    pattern = randomizer.getrandbits(OUTPUT_BITS)
    requests, responses = [], []
    for ticks, (command, sequence) in enumerate(zip(commands, sequences, strict=True)):
        requests.extend(request_frame(command, sequence))
        result = (
            (command & ((1 << OUTPUT_BITS) - 1))
            ^ (command >> OUTPUT_BITS)
            ^ pattern
            ^ ticks
        )
        body = bytes([sequence]) + result.to_bytes(79, "little")
        responses.extend(
            b"\x5a\xa5" + body + binascii.crc_hqx(body, 0xFFFF).to_bytes(2, "little")
        )
    bad_padding = bytearray(requests[:96])
    bad_padding[93] |= 4
    bad_padding[-2:] = binascii.crc_hqx(bad_padding[2:-2], 0xFFFF).to_bytes(2, "little")
    requests.extend(bad_padding)
    (output / "requests.hex").write_text("".join(f"{b:02x}\n" for b in requests))
    (output / "responses.hex").write_text("".join(f"{b:02x}\n" for b in responses))
    bench = f"""
module test;
reg clk=0; always #5 clk=~clk;
reg reset=1, rx=1;
wire tx; wire [7:0] rx_data, tx_data;
wire rx_valid, framing_error, tx_valid, tx_ready, core_ce, active, error, activity;
wire [721:0] command;
wire [625:0] result;
red2_uart #(.DIV(8)) uart(.clk(clk),.reset(reset),.rx(rx),.tx(tx),
  .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error),
  .tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready));
red2_monitor #(.TIMEOUT_BITS(12)) monitor(.clk(clk),.reset(reset),
  .rx_data(rx_data),.rx_valid(rx_valid),.framing_error(framing_error),
  .tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(tx_ready),
  .command(command),.result(result),.core_ce(core_ce),.active(active),
  .error(error),.activity(activity));
{GATE}
assign result = command[625:0] ^ command[721:626] ^ 626'h{pattern:X} ^ core_ticks;
reg [7:0] requests[0:479], responses[0:335];
integer framing_events=0;
always @(posedge clk) if(framing_error) framing_events <= framing_events+1;
task send_byte(input [7:0] data, input bad_stop);
  integer bit_index;
  begin
    @(negedge clk); rx=0; repeat(8) @(negedge clk);
    for(bit_index=0;bit_index<8;bit_index=bit_index+1) begin
      rx=data[bit_index]; repeat(8) @(negedge clk);
    end
    rx=!bad_stop; repeat(8) @(negedge clk);
    rx=1;
  end
endtask
task receive_byte(output [7:0] data);
  integer bit_index;
  begin
    @(negedge tx); repeat(12) @(posedge clk); #1;
    for(bit_index=0;bit_index<8;bit_index=bit_index+1) begin
      data[bit_index]=tx;
      repeat(8) @(posedge clk); #1;
    end
    if(tx!==1) $fatal(1,"bad response stop bit");
  end
endtask
task frame(input integer number);
  integer i,j; reg [7:0] actual;
  begin
    fork
      begin for(i=0;i<96;i=i+1) send_byte(requests[number*96+i],0); end
      begin
        for(j=0;j<84;j=j+1) begin
          receive_byte(actual);
          if(actual!==responses[number*84+j])
            $fatal(1,"response mismatch frame %d byte %d actual %h expected %h",
                   number,j,actual,responses[number*84+j]);
        end
      end
    join
    repeat(20) @(posedge clk); #1;
    if(core_ticks!==number+1) $fatal(1,"wrong core edge count %d",core_ticks);
  end
endtask
integer i;
initial begin
  $readmemh("{output / "requests.hex"}",requests);
  $readmemh("{output / "responses.hex"}",responses);
  repeat(6) @(negedge clk); reset=0;
  frame(0);
  // Corrupt CRC: no execution and no response.
  for(i=0;i<96;i=i+1) send_byte(i==95 ? requests[i]^8'h80 : requests[i],0);
  repeat(100) @(posedge clk); #1;
  if(core_ticks!==1 || !error || tx!==1) $fatal(1,"CRC failure executed a command");
  // Nonzero input padding with a valid CRC must also be rejected.
  for(i=0;i<96;i=i+1) send_byte(requests[384+i],0);
  repeat(100) @(posedge clk); #1;
  if(core_ticks!==1 || tx!==1) $fatal(1,"nonzero padding executed a command");
  // Abandoned packet must recover without executing it.
  for(i=0;i<8;i=i+1) send_byte(requests[i],0);
  repeat(4200) @(posedge clk);
  frame(1);
  // A framing error while idle must not create a command.
  send_byte(8'h33,1); repeat(100) @(posedge clk);
  frame(2); frame(3);
  repeat(100) @(posedge clk); #1;
  if(core_ticks!==4 || !error) $fatal(1,"extra core clock or missing error flag");
  if(framing_events!==1) $fatal(1,"wrong framing error count %d",framing_events);
  $display("BOARD_MONITOR_PASS UART, CRC, recovery, sequence wrap, 4 core edges");
  $finish;
end
initial begin repeat(200000) @(posedge clk); $fatal(1,"test did not finish"); end
endmodule
"""
    run(output, "uart", [HERE / "uart.v", monitor or HERE / "monitor.v"], bench)


def core_check(output, top, vectors, burst=False, monitor=None):
    metadata = json.loads(vectors.with_suffix(".json").read_text())
    verify_vectors(
        vectors, hashlib.sha256((top / "machine.py").read_bytes()).hexdigest()
    )
    scan_format = "%h %h\\n"
    scan_args = "incoming,expected"
    scan_fields = 2
    advance = "count=count+1; samples=samples+1;"
    simulation_vectors = vectors
    if burst:
        from burst_monitor import burst_trace

        rows = [
            tuple(int(word, 16) for word in line.split())
            for line in vectors.read_text().splitlines()
        ]
        packets = list(burst_trace(rows))
        simulation_vectors = output / "burst-vectors.txt"
        simulation_vectors.write_text(
            "".join(
                f"{command:X} {expected:X} {edges:X}\n"
                for command, expected, edges in packets
            )
        )
        scan_format = "%h %h %h\\n"
        scan_args = "incoming,expected,edges"
        scan_fields = 3
        advance = "count=count+edges; samples=samples+1;"
    wrapper = (top / "rtl-netlist/wrapper.v").read_text()
    (output / "packed.v").write_text(wrapper)
    bench = f"""
module test;
reg clk=0; always #5 clk=~clk;
reg reset=1; reg [7:0] rx_data=0; reg rx_valid=0;
wire [7:0] tx_data; wire tx_valid,core_ce,active,error,activity;
wire [721:0] command; wire [625:0] result;
red2_monitor monitor(.clk(clk),.reset(reset),.rx_data(rx_data),.rx_valid(rx_valid),
  .framing_error(1'b0),.tx_data(tx_data),.tx_valid(tx_valid),.tx_ready(1'b1),
  .command(command),.result(result),.core_ce(core_ce),.active(active),
  .error(error),.activity(activity));
{GATE}
replay_top core(.clk_25p0(core_clock),.incoming(command),.result(result));
{CRC}
task send_byte(input [7:0] data);
  begin @(negedge clk); rx_data=data; rx_valid=1; end
endtask
integer fd,matched,count=0,j,edges=1,samples=0; reg [727:0] incoming;
reg [631:0] expected; reg [7:0] sequence_id, wanted;
reg [15:0] request_crc, response_crc;
initial begin
  repeat(6) @(negedge clk); reset=0;
  fd=$fopen("{simulation_vectors}","r");
  if(!fd) $fatal(1,"vectors missing");
  while(!$feof(fd)) begin
    matched=$fscanf(fd,"{scan_format}",{scan_args});
    if(matched!=={scan_fields}) $fatal(1,"bad trace row");
    sequence_id=count; request_crc=crc_byte(16'hffff,sequence_id);
    send_byte(8'ha5); send_byte(8'h5a); send_byte(sequence_id);
    for(j=0;j<91;j=j+1) begin
      send_byte(incoming[j*8+:8]);
      request_crc=crc_byte(request_crc,incoming[j*8+:8]);
    end
    send_byte(request_crc[7:0]); send_byte(request_crc[15:8]);
    @(negedge clk); rx_valid=0;
    response_crc=crc_byte(16'hffff,sequence_id);
    for(j=0;j<84;j=j+1) begin
      @(posedge clk);
      while(!tx_valid) @(posedge clk);
      case(j)
        0: wanted=8'h5a;
        1: wanted=8'ha5;
        2: wanted=sequence_id;
        82: wanted=response_crc[7:0];
        83: wanted=response_crc[15:8];
        default: begin
          wanted=expected[(j-3)*8+:8];
          response_crc=crc_byte(response_crc,wanted);
        end
      endcase
      if(tx_data!==wanted) $fatal(1,"clock %d response byte %d actual %h expected %h",
                                  count,j,tx_data,wanted);
    end
    {advance}
    repeat(4) @(negedge clk);
    if(core_ticks!==count || error) $fatal(1,"core gating or protocol fault");
    if(count%1000==0) $display("BOARD_CORE_REPLAY_PROGRESS %d",count);
  end
  if(count!={metadata["cycles"]}) $fatal(1,"wrong trace count");
  $display("BOARD_MONITOR_PASS RED2 clocks=%d burst={burst} samples=%d",
           count,samples);
  $finish;
end
initial begin repeat({metadata["cycles"] * 220 + 1000}) @(posedge clk);
  $fatal(1,"test did not finish"); end
endmodule
"""
    run(
        output,
        "core",
        [
            top / "rtl-netlist/clean.v",
            output / "packed.v",
            monitor or HERE / "monitor.v",
        ],
        bench,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--core-top", type=Path)
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--burst-clock", action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    if bool(args.core_top) != bool(args.vectors):
        parser.error("core-top and vectors must be provided together")
    monitor = None
    if args.burst_clock:
        from burst_monitor import burst_clock

        monitor = args.output / "monitor.v"
        monitor.write_text(burst_clock((HERE / "monitor.v").read_text()))
    uart_check(args.output, monitor)
    if args.core_top:
        core_check(
            args.output,
            args.core_top.resolve(),
            args.vectors.resolve(),
            args.burst_clock,
            monitor,
        )


if __name__ == "__main__":
    main()

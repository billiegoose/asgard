`include "layout.vh"
// Serial, bounded residual compactor. The reducer must have halted at q=0.
// Snapshot graph memory and copy executable spines into the working arena;
// relocate APP/RBLOCK links after all roots are placed. Definition metadata
// retains its original addresses above arena_limit.
module red2_residual_restart (
    input clk, input reset, input start,
    input [15:0] root, input [8:0] arena_limit, input [31:0] quantum,
    input [625:0] result,
    output reg [721:0] command=0, output reg core_ce=0,
    output reg done=0, output reg [7:0] fault=0,
    output reg [8:0] residual_words=0
);
    localparam IDLE=0, SNAP_READ=1, SNAP_SECOND=2, SNAP_STORE=3,
        NEXT_ROOT=4, ROOT_READY=5, WALK_READ=6, WALK_COPY=7,
        PATCH_READ=8, PATCH_WORD=9, PATCH_TARGET=10, PATCH_WRITE=11,
        STORE_READ=12, STORE_WORD=13, STORE_NEXT=14, STORE_STOP=15,
        START_STATE=16, FINISH=17, SAMPLE=18, PULSE=19, SETTLE=20,
        WALK_LATCH=21, PATCH_LATCH=22, STORE_LATCH=23,
        CLEAR_METADATA=24, ROOT_DECIDE=25;
    reg [4:0] state=IDLE, after_edge=0;
    reg [625:0] response=0;
    (* ram_style="block" *) reg [127:0] source [0:255];
    (* ram_style="block" *) reg [127:0] compact [0:255];
    (* ram_style="block" *) reg [8:0] forwarding [0:255];
    (* ram_style="block" *) reg [7:0] queue [0:255];
    reg [8:0] cursor=0, head=0, count=0, used=0, walk=0;
    reg [7:0] queued_root;
    reg [8:0] forwarding_read;
    wire [7:0] forwarding_address=(state==ROOT_READY || state==ROOT_DECIDE) ? queued_root : word[7:0];
    reg [127:0] source_read,compact_read;
    reg [127:0] word=0;
    reg [721:0] work;
    wire [4:0] opcode=word[89:85];
    wire pointer_word=opcode==1 || opcode==16;
    wire scalar_word=opcode>=8 && opcode<=14;
    wire allowed=pointer_word || opcode==2 || opcode==6 || scalar_word ||
                 opcode==15 || opcode==17 || opcode==21;
    // RUP=17 and VAR=21 in the frozen public ABI. RECP is not executable
    // residual data: it still depends on the environment being discarded.
    wire terminal=(scalar_word && word[84]) || opcode==21;
    task issue;
        input [721:0] value;
        input [4:0] next_state;
        begin command<=value;after_edge<=next_state;state<=SAMPLE;end
    endtask
    task fail;
        input [7:0] code;
        begin fault<=code;done<=1;state<=IDLE;core_ce<=0;end
    endtask
    // Dedicated synchronous read registers allow both 128-bit buffers to map
    // into BRAM. The shared word register is one stage after these RAM outputs.
    always @(posedge clk) begin
        source_read<=source[walk[7:0]];
        compact_read<=compact[cursor[7:0]];
        forwarding_read<=forwarding[forwarding_address];
    end
    always @(posedge clk) begin
        core_ce<=0;done<=0;
        if(reset) begin
            state<=IDLE;command<=0;fault<=0;
        end else case(state)
            IDLE: if(start) begin
                fault<=0;cursor<=0;head<=0;count<=1;used<=0;
                queue[0]<=root[7:0];
                if(root>=arena_limit || arena_limit==0) fail(8'ha0);
                else state<=CLEAR_METADATA;
            end
            CLEAR_METADATA: begin
                forwarding[cursor[7:0]]<=0;
                if(cursor==255) begin cursor<=0;state<=SNAP_READ;end
                else cursor<=cursor+1;
            end
            SAMPLE: begin response<=result;core_ce<=1;state<=PULSE;end
            PULSE: state<=SETTLE;
            SETTLE: begin
                if(response[`OUT_RED2_FAULT]!=0 || response[`OUT_HW_FAULT]!=0)
                    fail(8'ha1);
                else state<=after_edge;
            end
            SNAP_READ: begin
                work=0;work[`IN_ADDRESS]={7'b0,cursor};issue(work,SNAP_SECOND);
            end
            SNAP_SECOND: issue(command,SNAP_STORE);
            SNAP_STORE: begin
                source[cursor[7:0]]<=response[`OUT_MEMORY_READ];
                if(cursor==255) state<=NEXT_ROOT;
                else begin cursor<=cursor+1;state<=SNAP_READ;end
            end
            NEXT_ROOT: if(head==count) begin cursor<=0;state<=PATCH_READ;end
                else begin queued_root<=queue[head[7:0]];head<=head+1;state<=ROOT_READY;end
            ROOT_READY: state<=ROOT_DECIDE;
            ROOT_DECIDE: if(forwarding_read[8]) state<=NEXT_ROOT;
                else begin walk<={1'b0,queued_root};state<=WALK_READ;end
            WALK_READ: state<=WALK_LATCH;
            WALK_LATCH: begin word<=source_read;state<=WALK_COPY;end
            WALK_COPY: begin
                if(walk>=256 || !word[90] || !allowed) fail(8'ha2);
                else if(used+1>=arena_limit) fail(8'ha3);
                else if(pointer_word && word[63:0]>=256) fail(8'ha4);
                else if(pointer_word && word[82:81]!=1) fail(8'ha4);
                else if(pointer_word && count==256) fail(8'ha5);
                else begin
                    compact[used[7:0]]<=word;
                    forwarding[walk[7:0]]<={1'b1,used[7:0]};
                    // Duplicate roots are cheap: ROOT_DECIDE skips copied roots.
                    // At most one root is queued per copied word, so the bounded
                    // output arena also bounds this queue, including cycles.
                    if(pointer_word) begin
                        queue[count[7:0]]<=word[7:0];count<=count+1;
                    end
                    used<=used+1;
                    if(terminal) state<=NEXT_ROOT;
                    else begin walk<=walk+1;state<=WALK_READ;end
                end
            end
            PATCH_READ: if(cursor==used) begin cursor<=0;state<=STORE_READ;end
                else state<=PATCH_LATCH;
            PATCH_LATCH: begin word<=compact_read;state<=PATCH_WORD;end
            PATCH_WORD: if(pointer_word) begin
                    state<=PATCH_TARGET;
                end else begin cursor<=cursor+1;state<=PATCH_READ;end
            PATCH_TARGET: if(!forwarding_read[8]) fail(8'ha6);
                else begin word[63:0]<={56'b0,forwarding_read[7:0]};state<=PATCH_WRITE;end
            PATCH_WRITE: begin compact[cursor[7:0]]<=word;cursor<=cursor+1;state<=PATCH_READ;end
            STORE_READ: if(cursor==used) state<=STORE_STOP;
                else state<=STORE_LATCH;
            STORE_LATCH: begin word<=compact_read;state<=STORE_WORD;end
            STORE_WORD: begin
                work=0;work[`IN_OP]=2;work[`IN_ADDRESS]={7'b0,cursor};
                work[`IN_WORD]=word;issue(work,STORE_NEXT);
            end
            STORE_NEXT: begin cursor<=cursor+1;state<=STORE_READ;end
            STORE_STOP: begin
                work=0;work[`IN_OP]=2;work[`IN_ADDRESS]={7'b0,used};
                work[`IN_WORD]=(128'd1<<90)|(128'd7<<85);
                issue(work,START_STATE);
            end
            START_STATE: begin
                // Public state layout is the OUT_PC..OUT_PENDING_HOST_ARGUMENT
                // field sequence, shifted to IN_STATE. Verify during preparation.
                work=0;work[`IN_OP]=8;
                work[`IN_STATE_FSP]={7'b0,used};       // fsp
                work[`IN_STATE_ENV]={8'b0,arena_limit}; // env
                work[`IN_STATE_Q]=quantum;          // q
                work[`IN_STATE_FREE_SPACE]={8'b0,arena_limit}; // free_space
                work[`IN_STATE_ARGCNT]=1;                // encoded argcnt = internal + 1
                residual_words<=used;issue(work,FINISH);
            end
            FINISH: begin command<=0;done<=1;state<=IDLE;end
            default: fail(8'haf);
        endcase
    end
endmodule

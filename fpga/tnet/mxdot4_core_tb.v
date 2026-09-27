`timescale 1ns/1ps
`default_nettype none
//=============================================================================
// mxdot4_core_tb -- mxdot4_core against every request of the spec, one per clock.
//
//   python3 conformance/mxdot4_board_vectors.py --write /tmp/mxdot4_vectors.hex
//   iverilog -g2012 -P mxdot4_core_tb.FORMATS=3 -o /tmp/mxdot4_core_tb \
//       fpga/tnet/mxdot4_board_params.v fpga/tnet/mxdot4_core.v fpga/tnet/mxdot4_core_tb.v
//   vvp /tmp/mxdot4_core_tb +vectors=/tmp/mxdot4_vectors.hex +n=251616
//
// Each line is {op, sa, sb, A[127:0], B[127:0], expected[23:0]}. With FORMATS 1
// or 2 the other format's requests must come back as BADOP with a zero word.
// After the file, ops 0, 3 and 255 must come back as BADOP whatever FORMATS is.
//=============================================================================
module mxdot4_core_tb;
    parameter integer FORMATS = 3;
    localparam integer LB = 8 + 8 + 8 + 128 + 128 + 24;
    localparam integer W  = `MXDOT4_WORD_BITS;
    localparam integer MAXN = 262144;
    localparam integer NBAD = 3;

    reg clk = 1'b0, rst = 1'b1;
    always #5 clk = ~clk;

    reg          in_valid = 1'b0;
    reg [7:0]    in_op = 8'd0, in_sa = 8'd0, in_sb = 8'd0;
    reg [127:0]  in_a = 128'd0, in_b = 128'd0;
    wire         out_valid, out_badop;
    wire [W-1:0] out_y;

    mxdot4_core #(.FORMATS(FORMATS)) dut (
        .clk(clk), .rst(rst), .in_valid(in_valid), .in_op(in_op), .in_sa(in_sa), .in_sb(in_sb),
        .in_a(in_a), .in_b(in_b), .out_valid(out_valid), .out_badop(out_badop), .out_y(out_y));

    reg [LB-1:0] mem [0:MAXN-1];
    reg [7:0]    bad_ops [0:NBAD-1];
    integer n, sent, got, fails, computed, refused;
    reg [1023:0] path;

    function has(input [7:0] op);
        has = (op == `MXDOT4_OP_MXFP4 && FORMATS[0]) || (op == `MXDOT4_OP_TNF4 && FORMATS[1]);
    endfunction

    // Checker: results come back in request order.
    reg [7:0]   want_op;
    reg [W-1:0] want_y;
    always @(posedge clk) begin
        if (out_valid) begin
            if (got < n) begin
                want_op = mem[got][LB-1 -: 8];
                want_y  = mem[got][W-1:0];
            end else begin
                want_op = bad_ops[got - n];
                want_y  = {W{1'b0}};
            end
            if (has(want_op)) begin
                computed = computed + 1;
                if (out_badop || out_y !== want_y) begin
                    fails = fails + 1;
                    if (fails <= 10) $display("FAIL #%0d op %0d: got %06h badop %b, want %06h", got, want_op, out_y, out_badop, want_y);
                end
            end else begin
                refused = refused + 1;
                if (!out_badop || out_y !== {W{1'b0}}) begin
                    fails = fails + 1;
                    if (fails <= 10) $display("FAIL #%0d op %0d: got %06h badop %b, want BADOP", got, want_op, out_y, out_badop);
                end
            end
            got = got + 1;
        end
    end

    initial begin
        bad_ops[0] = 8'd0; bad_ops[1] = 8'd3; bad_ops[2] = 8'd255;
        if (!$value$plusargs("vectors=%s", path)) begin $display("need +vectors=FILE"); $finish; end
        if (!$value$plusargs("n=%d", n)) n = 0;
        if (n <= 0 || n > MAXN) begin $display("need +n=1..%0d", MAXN); $finish; end
        $readmemh(path, mem, 0, n - 1);
        sent = 0; got = 0; fails = 0; computed = 0; refused = 0;
        repeat (3) @(posedge clk);
        rst <= 1'b0;
        @(posedge clk);
        while (sent < n + NBAD) begin
            in_valid <= 1'b1;
            if (sent < n) begin
                {in_op, in_sa, in_sb, in_a, in_b} <= mem[sent][LB-1:W];
            end else begin
                in_op <= bad_ops[sent - n]; in_sa <= 8'd127; in_sb <= 8'd127;
                in_a <= {128{1'b1}}; in_b <= {128{1'b1}};
            end
            sent = sent + 1;
            @(posedge clk);
        end
        in_valid <= 1'b0;
        repeat (`MXDOT4_CORE_STAGES + 4) @(posedge clk);
        $display("# FORMATS=%0d: %0d requests, %0d computed, %0d refused as BADOP, %0d answered", FORMATS, n + NBAD, computed, refused, got);
        if (got != n + NBAD) begin
            $display("MXDOT4 SIM FAIL: %0d sent, %0d answered", n + NBAD, got);
        end else if (FORMATS == 3) begin
            $display("MXDOT4 SIM: %0d/%0d bit-exact (fails=%0d)", n - fails, n, fails);
        end else begin
            $display("MXDOT4 SIM FORMATS=%0d: %0d/%0d as specified (fails=%0d)", FORMATS, n + NBAD - fails, n + NBAD, fails);
        end
        $finish;
    end
endmodule
`default_nettype wire

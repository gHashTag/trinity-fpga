`timescale 1ns/1ps
`default_nettype none
//=============================================================================
// tnf16_core_tb -- every board request through tnf16_core, in order.
//
//   python3 conformance/tnf16_board_vectors.py --write /tmp/tnf16_vectors.hex
//   iverilog -g2005 -o /tmp/tnf16_core_tb fpga/tnet/tnf16_board_params.v \
//       fpga/tnet/tnf16_core.v fpga/tnet/tnf16_core_tb.v
//   vvp /tmp/tnf16_core_tb +vectors=/tmp/tnf16_vectors.hex
//
// Requests arrive with pseudo-random gaps, and while in_valid is low the inputs
// carry junk. Every output is matched to its request in order, its latency is
// measured against `TNF16_CORE_STAGES, and one unknown opcode is sent after every
// BADOP_EVERY requests; those must come back flagged, with a zero word.
//=============================================================================
module tnf16_core_tb;
    localparam integer W = `TNF16_WORD_BITS;
    localparam integer BADOP_EVERY = 99991;

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg          rst = 1'b1;
    reg          in_valid = 1'b0;
    reg  [7:0]   in_op = 8'd0;
    reg  [W-1:0] in_a = {W{1'b0}}, in_b = {W{1'b0}};
    wire         out_valid, out_badop;
    wire [W-1:0] out_y;

    tnf16_core dut (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_op(in_op), .in_a(in_a), .in_b(in_b),
        .out_valid(out_valid), .out_badop(out_badop), .out_y(out_y)
    );

    // In-flight requests, oldest first.
    reg [W-1:0] q_want [0:63];
    reg         q_bad  [0:63];
    reg [7:0]   q_op   [0:63];
    reg [W-1:0] q_a    [0:63], q_b [0:63];
    integer     q_t    [0:63];
    integer     q_n    [0:63];
    integer wr = 0, rd = 0;

    integer cycle = 0;
    always @(posedge clk) cycle <= cycle + 1;

    integer ok = 0, fails = 0, bad_ok = 0, bad_fails = 0, extra = 0, lat_bad = 0, lat_seen = -1;
    integer lat;
    always @(posedge clk) begin
        if (!rst && out_valid !== 1'b0) begin
            if (out_valid !== 1'b1 || rd == wr) begin
                extra = extra + 1;
                if (extra <= 5) $display("EXTRA output at cycle %0d: valid %b y %05h", cycle, out_valid, out_y);
            end else begin
                lat = cycle - q_t[rd % 64];
                if (lat_seen < 0) lat_seen = lat;
                if (lat != `TNF16_CORE_STAGES) begin
                    lat_bad = lat_bad + 1;
                    if (lat_bad <= 5) $display("LATENCY %0d != %0d on request %0d", lat, `TNF16_CORE_STAGES, q_n[rd % 64]);
                end
                if (q_bad[rd % 64]) begin
                    if (out_badop === 1'b1 && out_y === {W{1'b0}}) bad_ok = bad_ok + 1;
                    else begin
                        bad_fails = bad_fails + 1;
                        $display("BADOP op %02h: badop %b y %05h", q_op[rd % 64], out_badop, out_y);
                    end
                end else if (out_badop === 1'b0 && out_y === q_want[rd % 64]) begin
                    ok = ok + 1;
                end else begin
                    fails = fails + 1;
                    if (fails <= 20)
                        $display("MISMATCH request %0d op %0d a %05h b %05h: rtl %05h badop %b, reference %05h",
                                 q_n[rd % 64], q_op[rd % 64], q_a[rd % 64], q_b[rd % 64],
                                 out_y, out_badop, q_want[rd % 64]);
                end
                rd = rd + 1;
            end
        end
    end

    reg [15:0] lfsr = 16'hACE1;
    task step_lfsr;
        lfsr = {lfsr[14:0], lfsr[15] ^ lfsr[13] ^ lfsr[12] ^ lfsr[10]};
    endtask

    task push(input [7:0] op, input [W-1:0] a, input [W-1:0] b, input [W-1:0] want,
              input isbad, input integer n);
        begin
            // Idle clocks carry junk on the inputs.
            step_lfsr;
            while (lfsr[1:0] == 2'b00) begin
                in_valid = 1'b0;
                in_op = lfsr[7:0]; in_a = {lfsr[2:0], lfsr}; in_b = ~{lfsr, lfsr[2:0]};
                @(negedge clk);
                step_lfsr;
            end
            in_valid = 1'b1; in_op = op; in_a = a; in_b = b;
            q_want[wr % 64] = want; q_bad[wr % 64] = isbad; q_op[wr % 64] = op;
            q_a[wr % 64] = a; q_b[wr % 64] = b; q_t[wr % 64] = cycle; q_n[wr % 64] = n;
            wr = wr + 1;
            @(negedge clk);
            in_valid = 1'b0;
        end
    endtask

    reg [1023:0] path;
    integer fd, got, n = 0, bad_sent = 0;
    reg [7:0]   f_op;
    reg [W-1:0] f_a, f_b, f_want;
    initial begin
        if (!$value$plusargs("vectors=%s", path)) begin
            $display("usage: vvp tnf16_core_tb +vectors=FILE");
            $finish;
        end
        fd = $fopen(path, "r");
        if (fd == 0) begin
            $display("cannot open %0s", path);
            $finish;
        end
        // Requests offered during reset must vanish.
        @(negedge clk);
        in_valid = 1'b1; in_op = `TNF16_OP_ADD; in_a = 19'h14000; in_b = 19'h14000;
        repeat (10) @(negedge clk);
        in_valid = 1'b0;
        rst = 1'b0;
        repeat (3) @(negedge clk);

        got = $fscanf(fd, "%h %h %h %h\n", f_op, f_a, f_b, f_want);
        while (got == 4) begin
            push(f_op, f_a, f_b, f_want, 1'b0, n);
            n = n + 1;
            if (n % BADOP_EVERY == 0) begin
                push({bad_sent[0], 7'd3} + bad_sent[7:0], f_a, f_b, {W{1'b0}}, 1'b1, -1);
                bad_sent = bad_sent + 1;
            end
            got = $fscanf(fd, "%h %h %h %h\n", f_op, f_a, f_b, f_want);
        end
        $fclose(fd);
        repeat (`TNF16_CORE_STAGES + 20) @(negedge clk);

        if (rd != wr) $display("LOST %0d requests never answered", wr - rd);
        $display("TNF16 SIM latency: %0d cycles (spec %0d), %0d requests off it", lat_seen, `TNF16_CORE_STAGES, lat_bad);
        $display("TNF16 SIM badop: %0d/%0d flagged with a zero word", bad_ok, bad_sent);
        $display("TNF16 SIM extra outputs: %0d", extra);
        $display("TNF16 SIM: %0d/%0d bit-exact (fails=%0d)", ok, n, fails);
        if (ok == n && fails == 0 && rd == wr && lat_bad == 0 && lat_seen == `TNF16_CORE_STAGES
            && bad_ok == bad_sent && bad_fails == 0 && extra == 0)
            $display("TNF16 SIM PASS");
        else
            $display("TNF16 SIM FAIL");
        $finish;
    end
endmodule
`default_nettype wire

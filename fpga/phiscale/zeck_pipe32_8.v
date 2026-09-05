// Zeckendorf normaliser, 8-stage pipeline (6 compare-subtracts per stage).
//
// The combinational version answers the corollary but invites the obvious
// objection: 46 dependent stages in one cycle is the worst configuration
// for frequency, and pipelining trades that depth for registers and
// latency. This measures the trade instead of asserting it.
`default_nettype none
module zeck_pipe32_8 (
    input  wire            clk,
    input  wire [31:0]  x,
    output wire [45:0]  z
);
    reg  [31:0] r [0:8];
    reg  [45:0] d [0:8];
    wire [31:0] rw [0:46];
    wire [45:0] dw;
    integer i;
    always @(posedge clk) r[0] <= x;
    always @(posedge clk) d[0] <= 0;
    // --- pipeline stage 0: Fibonacci indices 45 down to 40 ---
    wire [31:0] s0_r [0:6];
    wire [45:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[45] = (s0_r[0] >= 32'd2971215073);
    assign s0_r[1] = s0_d[45] ? (s0_r[0] - 32'd2971215073) : s0_r[0];
    assign s0_d[44] = (s0_r[1] >= 32'd1836311903);
    assign s0_r[2] = s0_d[44] ? (s0_r[1] - 32'd1836311903) : s0_r[1];
    assign s0_d[43] = (s0_r[2] >= 32'd1134903170);
    assign s0_r[3] = s0_d[43] ? (s0_r[2] - 32'd1134903170) : s0_r[2];
    assign s0_d[42] = (s0_r[3] >= 32'd701408733);
    assign s0_r[4] = s0_d[42] ? (s0_r[3] - 32'd701408733) : s0_r[3];
    assign s0_d[41] = (s0_r[4] >= 32'd433494437);
    assign s0_r[5] = s0_d[41] ? (s0_r[4] - 32'd433494437) : s0_r[4];
    assign s0_d[40] = (s0_r[5] >= 32'd267914296);
    assign s0_r[6] = s0_d[40] ? (s0_r[5] - 32'd267914296) : s0_r[5];
    always @(posedge clk) begin
      r[1] <= s0_r[6];
      d[1] <= d[0] | ({46{1'b0}} | (s0_d[45] << 45)) | ({46{1'b0}} | (s0_d[44] << 44)) | ({46{1'b0}} | (s0_d[43] << 43)) | ({46{1'b0}} | (s0_d[42] << 42)) | ({46{1'b0}} | (s0_d[41] << 41)) | ({46{1'b0}} | (s0_d[40] << 40));
    end
    // --- pipeline stage 1: Fibonacci indices 39 down to 34 ---
    wire [31:0] s1_r [0:6];
    wire [45:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[39] = (s1_r[0] >= 32'd165580141);
    assign s1_r[1] = s1_d[39] ? (s1_r[0] - 32'd165580141) : s1_r[0];
    assign s1_d[38] = (s1_r[1] >= 32'd102334155);
    assign s1_r[2] = s1_d[38] ? (s1_r[1] - 32'd102334155) : s1_r[1];
    assign s1_d[37] = (s1_r[2] >= 32'd63245986);
    assign s1_r[3] = s1_d[37] ? (s1_r[2] - 32'd63245986) : s1_r[2];
    assign s1_d[36] = (s1_r[3] >= 32'd39088169);
    assign s1_r[4] = s1_d[36] ? (s1_r[3] - 32'd39088169) : s1_r[3];
    assign s1_d[35] = (s1_r[4] >= 32'd24157817);
    assign s1_r[5] = s1_d[35] ? (s1_r[4] - 32'd24157817) : s1_r[4];
    assign s1_d[34] = (s1_r[5] >= 32'd14930352);
    assign s1_r[6] = s1_d[34] ? (s1_r[5] - 32'd14930352) : s1_r[5];
    always @(posedge clk) begin
      r[2] <= s1_r[6];
      d[2] <= d[1] | ({46{1'b0}} | (s1_d[39] << 39)) | ({46{1'b0}} | (s1_d[38] << 38)) | ({46{1'b0}} | (s1_d[37] << 37)) | ({46{1'b0}} | (s1_d[36] << 36)) | ({46{1'b0}} | (s1_d[35] << 35)) | ({46{1'b0}} | (s1_d[34] << 34));
    end
    // --- pipeline stage 2: Fibonacci indices 33 down to 28 ---
    wire [31:0] s2_r [0:6];
    wire [45:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[33] = (s2_r[0] >= 32'd9227465);
    assign s2_r[1] = s2_d[33] ? (s2_r[0] - 32'd9227465) : s2_r[0];
    assign s2_d[32] = (s2_r[1] >= 32'd5702887);
    assign s2_r[2] = s2_d[32] ? (s2_r[1] - 32'd5702887) : s2_r[1];
    assign s2_d[31] = (s2_r[2] >= 32'd3524578);
    assign s2_r[3] = s2_d[31] ? (s2_r[2] - 32'd3524578) : s2_r[2];
    assign s2_d[30] = (s2_r[3] >= 32'd2178309);
    assign s2_r[4] = s2_d[30] ? (s2_r[3] - 32'd2178309) : s2_r[3];
    assign s2_d[29] = (s2_r[4] >= 32'd1346269);
    assign s2_r[5] = s2_d[29] ? (s2_r[4] - 32'd1346269) : s2_r[4];
    assign s2_d[28] = (s2_r[5] >= 32'd832040);
    assign s2_r[6] = s2_d[28] ? (s2_r[5] - 32'd832040) : s2_r[5];
    always @(posedge clk) begin
      r[3] <= s2_r[6];
      d[3] <= d[2] | ({46{1'b0}} | (s2_d[33] << 33)) | ({46{1'b0}} | (s2_d[32] << 32)) | ({46{1'b0}} | (s2_d[31] << 31)) | ({46{1'b0}} | (s2_d[30] << 30)) | ({46{1'b0}} | (s2_d[29] << 29)) | ({46{1'b0}} | (s2_d[28] << 28));
    end
    // --- pipeline stage 3: Fibonacci indices 27 down to 22 ---
    wire [31:0] s3_r [0:6];
    wire [45:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[27] = (s3_r[0] >= 32'd514229);
    assign s3_r[1] = s3_d[27] ? (s3_r[0] - 32'd514229) : s3_r[0];
    assign s3_d[26] = (s3_r[1] >= 32'd317811);
    assign s3_r[2] = s3_d[26] ? (s3_r[1] - 32'd317811) : s3_r[1];
    assign s3_d[25] = (s3_r[2] >= 32'd196418);
    assign s3_r[3] = s3_d[25] ? (s3_r[2] - 32'd196418) : s3_r[2];
    assign s3_d[24] = (s3_r[3] >= 32'd121393);
    assign s3_r[4] = s3_d[24] ? (s3_r[3] - 32'd121393) : s3_r[3];
    assign s3_d[23] = (s3_r[4] >= 32'd75025);
    assign s3_r[5] = s3_d[23] ? (s3_r[4] - 32'd75025) : s3_r[4];
    assign s3_d[22] = (s3_r[5] >= 32'd46368);
    assign s3_r[6] = s3_d[22] ? (s3_r[5] - 32'd46368) : s3_r[5];
    always @(posedge clk) begin
      r[4] <= s3_r[6];
      d[4] <= d[3] | ({46{1'b0}} | (s3_d[27] << 27)) | ({46{1'b0}} | (s3_d[26] << 26)) | ({46{1'b0}} | (s3_d[25] << 25)) | ({46{1'b0}} | (s3_d[24] << 24)) | ({46{1'b0}} | (s3_d[23] << 23)) | ({46{1'b0}} | (s3_d[22] << 22));
    end
    // --- pipeline stage 4: Fibonacci indices 21 down to 16 ---
    wire [31:0] s4_r [0:6];
    wire [45:0] s4_d;
    assign s4_r[0] = r[4];
    assign s4_d[21] = (s4_r[0] >= 32'd28657);
    assign s4_r[1] = s4_d[21] ? (s4_r[0] - 32'd28657) : s4_r[0];
    assign s4_d[20] = (s4_r[1] >= 32'd17711);
    assign s4_r[2] = s4_d[20] ? (s4_r[1] - 32'd17711) : s4_r[1];
    assign s4_d[19] = (s4_r[2] >= 32'd10946);
    assign s4_r[3] = s4_d[19] ? (s4_r[2] - 32'd10946) : s4_r[2];
    assign s4_d[18] = (s4_r[3] >= 32'd6765);
    assign s4_r[4] = s4_d[18] ? (s4_r[3] - 32'd6765) : s4_r[3];
    assign s4_d[17] = (s4_r[4] >= 32'd4181);
    assign s4_r[5] = s4_d[17] ? (s4_r[4] - 32'd4181) : s4_r[4];
    assign s4_d[16] = (s4_r[5] >= 32'd2584);
    assign s4_r[6] = s4_d[16] ? (s4_r[5] - 32'd2584) : s4_r[5];
    always @(posedge clk) begin
      r[5] <= s4_r[6];
      d[5] <= d[4] | ({46{1'b0}} | (s4_d[21] << 21)) | ({46{1'b0}} | (s4_d[20] << 20)) | ({46{1'b0}} | (s4_d[19] << 19)) | ({46{1'b0}} | (s4_d[18] << 18)) | ({46{1'b0}} | (s4_d[17] << 17)) | ({46{1'b0}} | (s4_d[16] << 16));
    end
    // --- pipeline stage 5: Fibonacci indices 15 down to 10 ---
    wire [31:0] s5_r [0:6];
    wire [45:0] s5_d;
    assign s5_r[0] = r[5];
    assign s5_d[15] = (s5_r[0] >= 32'd1597);
    assign s5_r[1] = s5_d[15] ? (s5_r[0] - 32'd1597) : s5_r[0];
    assign s5_d[14] = (s5_r[1] >= 32'd987);
    assign s5_r[2] = s5_d[14] ? (s5_r[1] - 32'd987) : s5_r[1];
    assign s5_d[13] = (s5_r[2] >= 32'd610);
    assign s5_r[3] = s5_d[13] ? (s5_r[2] - 32'd610) : s5_r[2];
    assign s5_d[12] = (s5_r[3] >= 32'd377);
    assign s5_r[4] = s5_d[12] ? (s5_r[3] - 32'd377) : s5_r[3];
    assign s5_d[11] = (s5_r[4] >= 32'd233);
    assign s5_r[5] = s5_d[11] ? (s5_r[4] - 32'd233) : s5_r[4];
    assign s5_d[10] = (s5_r[5] >= 32'd144);
    assign s5_r[6] = s5_d[10] ? (s5_r[5] - 32'd144) : s5_r[5];
    always @(posedge clk) begin
      r[6] <= s5_r[6];
      d[6] <= d[5] | ({46{1'b0}} | (s5_d[15] << 15)) | ({46{1'b0}} | (s5_d[14] << 14)) | ({46{1'b0}} | (s5_d[13] << 13)) | ({46{1'b0}} | (s5_d[12] << 12)) | ({46{1'b0}} | (s5_d[11] << 11)) | ({46{1'b0}} | (s5_d[10] << 10));
    end
    // --- pipeline stage 6: Fibonacci indices 9 down to 4 ---
    wire [31:0] s6_r [0:6];
    wire [45:0] s6_d;
    assign s6_r[0] = r[6];
    assign s6_d[9] = (s6_r[0] >= 32'd89);
    assign s6_r[1] = s6_d[9] ? (s6_r[0] - 32'd89) : s6_r[0];
    assign s6_d[8] = (s6_r[1] >= 32'd55);
    assign s6_r[2] = s6_d[8] ? (s6_r[1] - 32'd55) : s6_r[1];
    assign s6_d[7] = (s6_r[2] >= 32'd34);
    assign s6_r[3] = s6_d[7] ? (s6_r[2] - 32'd34) : s6_r[2];
    assign s6_d[6] = (s6_r[3] >= 32'd21);
    assign s6_r[4] = s6_d[6] ? (s6_r[3] - 32'd21) : s6_r[3];
    assign s6_d[5] = (s6_r[4] >= 32'd13);
    assign s6_r[5] = s6_d[5] ? (s6_r[4] - 32'd13) : s6_r[4];
    assign s6_d[4] = (s6_r[5] >= 32'd8);
    assign s6_r[6] = s6_d[4] ? (s6_r[5] - 32'd8) : s6_r[5];
    always @(posedge clk) begin
      r[7] <= s6_r[6];
      d[7] <= d[6] | ({46{1'b0}} | (s6_d[9] << 9)) | ({46{1'b0}} | (s6_d[8] << 8)) | ({46{1'b0}} | (s6_d[7] << 7)) | ({46{1'b0}} | (s6_d[6] << 6)) | ({46{1'b0}} | (s6_d[5] << 5)) | ({46{1'b0}} | (s6_d[4] << 4));
    end
    // --- pipeline stage 7: Fibonacci indices 3 down to 0 ---
    wire [31:0] s7_r [0:4];
    wire [45:0] s7_d;
    assign s7_r[0] = r[7];
    assign s7_d[3] = (s7_r[0] >= 32'd5);
    assign s7_r[1] = s7_d[3] ? (s7_r[0] - 32'd5) : s7_r[0];
    assign s7_d[2] = (s7_r[1] >= 32'd3);
    assign s7_r[2] = s7_d[2] ? (s7_r[1] - 32'd3) : s7_r[1];
    assign s7_d[1] = (s7_r[2] >= 32'd2);
    assign s7_r[3] = s7_d[1] ? (s7_r[2] - 32'd2) : s7_r[2];
    assign s7_d[0] = (s7_r[3] >= 32'd1);
    assign s7_r[4] = s7_d[0] ? (s7_r[3] - 32'd1) : s7_r[3];
    always @(posedge clk) begin
      r[8] <= s7_r[4];
      d[8] <= d[7] | ({46{1'b0}} | (s7_d[3] << 3)) | ({46{1'b0}} | (s7_d[2] << 2)) | ({46{1'b0}} | (s7_d[1] << 1)) | ({46{1'b0}} | (s7_d[0] << 0));
    end
    assign z = d[8];
endmodule

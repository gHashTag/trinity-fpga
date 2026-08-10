// Zeckendorf normaliser, 8-stage pipeline (3 compare-subtracts per stage).
//
// The combinational version answers the corollary but invites the obvious
// objection: 46 dependent stages in one cycle is the worst configuration
// for frequency, and pipelining trades that depth for registers and
// latency. This measures the trade instead of asserting it.
`default_nettype none
module zeck_pipe16_8 (
    input  wire            clk,
    input  wire [15:0]  x,
    output wire [22:0]  z
);
    reg  [15:0] r [0:8];
    reg  [22:0] d [0:8];
    wire [15:0] rw [0:23];
    wire [22:0] dw;
    integer i;
    always @(posedge clk) r[0] <= x;
    always @(posedge clk) d[0] <= 0;
    // --- pipeline stage 0: Fibonacci indices 22 down to 20 ---
    wire [15:0] s0_r [0:3];
    wire [22:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[22] = (s0_r[0] >= 16'd46368);
    assign s0_r[1] = s0_d[22] ? (s0_r[0] - 16'd46368) : s0_r[0];
    assign s0_d[21] = (s0_r[1] >= 16'd28657);
    assign s0_r[2] = s0_d[21] ? (s0_r[1] - 16'd28657) : s0_r[1];
    assign s0_d[20] = (s0_r[2] >= 16'd17711);
    assign s0_r[3] = s0_d[20] ? (s0_r[2] - 16'd17711) : s0_r[2];
    always @(posedge clk) begin
      r[1] <= s0_r[3];
      d[1] <= d[0] | ({23{1'b0}} | (s0_d[22] << 22)) | ({23{1'b0}} | (s0_d[21] << 21)) | ({23{1'b0}} | (s0_d[20] << 20));
    end
    // --- pipeline stage 1: Fibonacci indices 19 down to 17 ---
    wire [15:0] s1_r [0:3];
    wire [22:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[19] = (s1_r[0] >= 16'd10946);
    assign s1_r[1] = s1_d[19] ? (s1_r[0] - 16'd10946) : s1_r[0];
    assign s1_d[18] = (s1_r[1] >= 16'd6765);
    assign s1_r[2] = s1_d[18] ? (s1_r[1] - 16'd6765) : s1_r[1];
    assign s1_d[17] = (s1_r[2] >= 16'd4181);
    assign s1_r[3] = s1_d[17] ? (s1_r[2] - 16'd4181) : s1_r[2];
    always @(posedge clk) begin
      r[2] <= s1_r[3];
      d[2] <= d[1] | ({23{1'b0}} | (s1_d[19] << 19)) | ({23{1'b0}} | (s1_d[18] << 18)) | ({23{1'b0}} | (s1_d[17] << 17));
    end
    // --- pipeline stage 2: Fibonacci indices 16 down to 14 ---
    wire [15:0] s2_r [0:3];
    wire [22:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[16] = (s2_r[0] >= 16'd2584);
    assign s2_r[1] = s2_d[16] ? (s2_r[0] - 16'd2584) : s2_r[0];
    assign s2_d[15] = (s2_r[1] >= 16'd1597);
    assign s2_r[2] = s2_d[15] ? (s2_r[1] - 16'd1597) : s2_r[1];
    assign s2_d[14] = (s2_r[2] >= 16'd987);
    assign s2_r[3] = s2_d[14] ? (s2_r[2] - 16'd987) : s2_r[2];
    always @(posedge clk) begin
      r[3] <= s2_r[3];
      d[3] <= d[2] | ({23{1'b0}} | (s2_d[16] << 16)) | ({23{1'b0}} | (s2_d[15] << 15)) | ({23{1'b0}} | (s2_d[14] << 14));
    end
    // --- pipeline stage 3: Fibonacci indices 13 down to 11 ---
    wire [15:0] s3_r [0:3];
    wire [22:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[13] = (s3_r[0] >= 16'd610);
    assign s3_r[1] = s3_d[13] ? (s3_r[0] - 16'd610) : s3_r[0];
    assign s3_d[12] = (s3_r[1] >= 16'd377);
    assign s3_r[2] = s3_d[12] ? (s3_r[1] - 16'd377) : s3_r[1];
    assign s3_d[11] = (s3_r[2] >= 16'd233);
    assign s3_r[3] = s3_d[11] ? (s3_r[2] - 16'd233) : s3_r[2];
    always @(posedge clk) begin
      r[4] <= s3_r[3];
      d[4] <= d[3] | ({23{1'b0}} | (s3_d[13] << 13)) | ({23{1'b0}} | (s3_d[12] << 12)) | ({23{1'b0}} | (s3_d[11] << 11));
    end
    // --- pipeline stage 4: Fibonacci indices 10 down to 8 ---
    wire [15:0] s4_r [0:3];
    wire [22:0] s4_d;
    assign s4_r[0] = r[4];
    assign s4_d[10] = (s4_r[0] >= 16'd144);
    assign s4_r[1] = s4_d[10] ? (s4_r[0] - 16'd144) : s4_r[0];
    assign s4_d[9] = (s4_r[1] >= 16'd89);
    assign s4_r[2] = s4_d[9] ? (s4_r[1] - 16'd89) : s4_r[1];
    assign s4_d[8] = (s4_r[2] >= 16'd55);
    assign s4_r[3] = s4_d[8] ? (s4_r[2] - 16'd55) : s4_r[2];
    always @(posedge clk) begin
      r[5] <= s4_r[3];
      d[5] <= d[4] | ({23{1'b0}} | (s4_d[10] << 10)) | ({23{1'b0}} | (s4_d[9] << 9)) | ({23{1'b0}} | (s4_d[8] << 8));
    end
    // --- pipeline stage 5: Fibonacci indices 7 down to 5 ---
    wire [15:0] s5_r [0:3];
    wire [22:0] s5_d;
    assign s5_r[0] = r[5];
    assign s5_d[7] = (s5_r[0] >= 16'd34);
    assign s5_r[1] = s5_d[7] ? (s5_r[0] - 16'd34) : s5_r[0];
    assign s5_d[6] = (s5_r[1] >= 16'd21);
    assign s5_r[2] = s5_d[6] ? (s5_r[1] - 16'd21) : s5_r[1];
    assign s5_d[5] = (s5_r[2] >= 16'd13);
    assign s5_r[3] = s5_d[5] ? (s5_r[2] - 16'd13) : s5_r[2];
    always @(posedge clk) begin
      r[6] <= s5_r[3];
      d[6] <= d[5] | ({23{1'b0}} | (s5_d[7] << 7)) | ({23{1'b0}} | (s5_d[6] << 6)) | ({23{1'b0}} | (s5_d[5] << 5));
    end
    // --- pipeline stage 6: Fibonacci indices 4 down to 2 ---
    wire [15:0] s6_r [0:3];
    wire [22:0] s6_d;
    assign s6_r[0] = r[6];
    assign s6_d[4] = (s6_r[0] >= 16'd8);
    assign s6_r[1] = s6_d[4] ? (s6_r[0] - 16'd8) : s6_r[0];
    assign s6_d[3] = (s6_r[1] >= 16'd5);
    assign s6_r[2] = s6_d[3] ? (s6_r[1] - 16'd5) : s6_r[1];
    assign s6_d[2] = (s6_r[2] >= 16'd3);
    assign s6_r[3] = s6_d[2] ? (s6_r[2] - 16'd3) : s6_r[2];
    always @(posedge clk) begin
      r[7] <= s6_r[3];
      d[7] <= d[6] | ({23{1'b0}} | (s6_d[4] << 4)) | ({23{1'b0}} | (s6_d[3] << 3)) | ({23{1'b0}} | (s6_d[2] << 2));
    end
    // --- pipeline stage 7: Fibonacci indices 1 down to 0 ---
    wire [15:0] s7_r [0:2];
    wire [22:0] s7_d;
    assign s7_r[0] = r[7];
    assign s7_d[1] = (s7_r[0] >= 16'd2);
    assign s7_r[1] = s7_d[1] ? (s7_r[0] - 16'd2) : s7_r[0];
    assign s7_d[0] = (s7_r[1] >= 16'd1);
    assign s7_r[2] = s7_d[0] ? (s7_r[1] - 16'd1) : s7_r[1];
    always @(posedge clk) begin
      r[8] <= s7_r[2];
      d[8] <= d[7] | ({23{1'b0}} | (s7_d[1] << 1)) | ({23{1'b0}} | (s7_d[0] << 0));
    end
    assign z = d[8];
endmodule

// Zeckendorf normaliser, 4-stage pipeline (6 compare-subtracts per stage).
//
// The combinational version answers the corollary but invites the obvious
// objection: 46 dependent stages in one cycle is the worst configuration
// for frequency, and pipelining trades that depth for registers and
// latency. This measures the trade instead of asserting it.
`default_nettype none
module zeck_pipe16_4 (
    input  wire            clk,
    input  wire [15:0]  x,
    output wire [22:0]  z
);
    reg  [15:0] r [0:4];
    reg  [22:0] d [0:4];
    wire [15:0] rw [0:23];
    wire [22:0] dw;
    integer i;
    always @(posedge clk) r[0] <= x;
    always @(posedge clk) d[0] <= 0;
    // --- pipeline stage 0: Fibonacci indices 22 down to 17 ---
    wire [15:0] s0_r [0:6];
    wire [22:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[22] = (s0_r[0] >= 16'd46368);
    assign s0_r[1] = s0_d[22] ? (s0_r[0] - 16'd46368) : s0_r[0];
    assign s0_d[21] = (s0_r[1] >= 16'd28657);
    assign s0_r[2] = s0_d[21] ? (s0_r[1] - 16'd28657) : s0_r[1];
    assign s0_d[20] = (s0_r[2] >= 16'd17711);
    assign s0_r[3] = s0_d[20] ? (s0_r[2] - 16'd17711) : s0_r[2];
    assign s0_d[19] = (s0_r[3] >= 16'd10946);
    assign s0_r[4] = s0_d[19] ? (s0_r[3] - 16'd10946) : s0_r[3];
    assign s0_d[18] = (s0_r[4] >= 16'd6765);
    assign s0_r[5] = s0_d[18] ? (s0_r[4] - 16'd6765) : s0_r[4];
    assign s0_d[17] = (s0_r[5] >= 16'd4181);
    assign s0_r[6] = s0_d[17] ? (s0_r[5] - 16'd4181) : s0_r[5];
    always @(posedge clk) begin
      r[1] <= s0_r[6];
      d[1] <= d[0] | ({23{1'b0}} | (s0_d[22] << 22)) | ({23{1'b0}} | (s0_d[21] << 21)) | ({23{1'b0}} | (s0_d[20] << 20)) | ({23{1'b0}} | (s0_d[19] << 19)) | ({23{1'b0}} | (s0_d[18] << 18)) | ({23{1'b0}} | (s0_d[17] << 17));
    end
    // --- pipeline stage 1: Fibonacci indices 16 down to 11 ---
    wire [15:0] s1_r [0:6];
    wire [22:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[16] = (s1_r[0] >= 16'd2584);
    assign s1_r[1] = s1_d[16] ? (s1_r[0] - 16'd2584) : s1_r[0];
    assign s1_d[15] = (s1_r[1] >= 16'd1597);
    assign s1_r[2] = s1_d[15] ? (s1_r[1] - 16'd1597) : s1_r[1];
    assign s1_d[14] = (s1_r[2] >= 16'd987);
    assign s1_r[3] = s1_d[14] ? (s1_r[2] - 16'd987) : s1_r[2];
    assign s1_d[13] = (s1_r[3] >= 16'd610);
    assign s1_r[4] = s1_d[13] ? (s1_r[3] - 16'd610) : s1_r[3];
    assign s1_d[12] = (s1_r[4] >= 16'd377);
    assign s1_r[5] = s1_d[12] ? (s1_r[4] - 16'd377) : s1_r[4];
    assign s1_d[11] = (s1_r[5] >= 16'd233);
    assign s1_r[6] = s1_d[11] ? (s1_r[5] - 16'd233) : s1_r[5];
    always @(posedge clk) begin
      r[2] <= s1_r[6];
      d[2] <= d[1] | ({23{1'b0}} | (s1_d[16] << 16)) | ({23{1'b0}} | (s1_d[15] << 15)) | ({23{1'b0}} | (s1_d[14] << 14)) | ({23{1'b0}} | (s1_d[13] << 13)) | ({23{1'b0}} | (s1_d[12] << 12)) | ({23{1'b0}} | (s1_d[11] << 11));
    end
    // --- pipeline stage 2: Fibonacci indices 10 down to 5 ---
    wire [15:0] s2_r [0:6];
    wire [22:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[10] = (s2_r[0] >= 16'd144);
    assign s2_r[1] = s2_d[10] ? (s2_r[0] - 16'd144) : s2_r[0];
    assign s2_d[9] = (s2_r[1] >= 16'd89);
    assign s2_r[2] = s2_d[9] ? (s2_r[1] - 16'd89) : s2_r[1];
    assign s2_d[8] = (s2_r[2] >= 16'd55);
    assign s2_r[3] = s2_d[8] ? (s2_r[2] - 16'd55) : s2_r[2];
    assign s2_d[7] = (s2_r[3] >= 16'd34);
    assign s2_r[4] = s2_d[7] ? (s2_r[3] - 16'd34) : s2_r[3];
    assign s2_d[6] = (s2_r[4] >= 16'd21);
    assign s2_r[5] = s2_d[6] ? (s2_r[4] - 16'd21) : s2_r[4];
    assign s2_d[5] = (s2_r[5] >= 16'd13);
    assign s2_r[6] = s2_d[5] ? (s2_r[5] - 16'd13) : s2_r[5];
    always @(posedge clk) begin
      r[3] <= s2_r[6];
      d[3] <= d[2] | ({23{1'b0}} | (s2_d[10] << 10)) | ({23{1'b0}} | (s2_d[9] << 9)) | ({23{1'b0}} | (s2_d[8] << 8)) | ({23{1'b0}} | (s2_d[7] << 7)) | ({23{1'b0}} | (s2_d[6] << 6)) | ({23{1'b0}} | (s2_d[5] << 5));
    end
    // --- pipeline stage 3: Fibonacci indices 4 down to 0 ---
    wire [15:0] s3_r [0:5];
    wire [22:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[4] = (s3_r[0] >= 16'd8);
    assign s3_r[1] = s3_d[4] ? (s3_r[0] - 16'd8) : s3_r[0];
    assign s3_d[3] = (s3_r[1] >= 16'd5);
    assign s3_r[2] = s3_d[3] ? (s3_r[1] - 16'd5) : s3_r[1];
    assign s3_d[2] = (s3_r[2] >= 16'd3);
    assign s3_r[3] = s3_d[2] ? (s3_r[2] - 16'd3) : s3_r[2];
    assign s3_d[1] = (s3_r[3] >= 16'd2);
    assign s3_r[4] = s3_d[1] ? (s3_r[3] - 16'd2) : s3_r[3];
    assign s3_d[0] = (s3_r[4] >= 16'd1);
    assign s3_r[5] = s3_d[0] ? (s3_r[4] - 16'd1) : s3_r[4];
    always @(posedge clk) begin
      r[4] <= s3_r[5];
      d[4] <= d[3] | ({23{1'b0}} | (s3_d[4] << 4)) | ({23{1'b0}} | (s3_d[3] << 3)) | ({23{1'b0}} | (s3_d[2] << 2)) | ({23{1'b0}} | (s3_d[1] << 1)) | ({23{1'b0}} | (s3_d[0] << 0));
    end
    assign z = d[4];
endmodule

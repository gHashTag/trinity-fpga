// Zeckendorf normaliser, 2-stage pipeline (12 compare-subtracts per stage).
//
// The combinational version answers the corollary but invites the obvious
// objection: 46 dependent stages in one cycle is the worst configuration
// for frequency, and pipelining trades that depth for registers and
// latency. This measures the trade instead of asserting it.
`default_nettype none
module zeck_pipe16_2 (
    input  wire            clk,
    input  wire [15:0]  x,
    output wire [22:0]  z
);
    reg  [15:0] r [0:2];
    reg  [22:0] d [0:2];
    wire [15:0] rw [0:23];
    wire [22:0] dw;
    integer i;
    always @(posedge clk) r[0] <= x;
    always @(posedge clk) d[0] <= 0;
    // --- pipeline stage 0: Fibonacci indices 22 down to 11 ---
    wire [15:0] s0_r [0:12];
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
    assign s0_d[16] = (s0_r[6] >= 16'd2584);
    assign s0_r[7] = s0_d[16] ? (s0_r[6] - 16'd2584) : s0_r[6];
    assign s0_d[15] = (s0_r[7] >= 16'd1597);
    assign s0_r[8] = s0_d[15] ? (s0_r[7] - 16'd1597) : s0_r[7];
    assign s0_d[14] = (s0_r[8] >= 16'd987);
    assign s0_r[9] = s0_d[14] ? (s0_r[8] - 16'd987) : s0_r[8];
    assign s0_d[13] = (s0_r[9] >= 16'd610);
    assign s0_r[10] = s0_d[13] ? (s0_r[9] - 16'd610) : s0_r[9];
    assign s0_d[12] = (s0_r[10] >= 16'd377);
    assign s0_r[11] = s0_d[12] ? (s0_r[10] - 16'd377) : s0_r[10];
    assign s0_d[11] = (s0_r[11] >= 16'd233);
    assign s0_r[12] = s0_d[11] ? (s0_r[11] - 16'd233) : s0_r[11];
    always @(posedge clk) begin
      r[1] <= s0_r[12];
      d[1] <= d[0] | ({23{1'b0}} | (s0_d[22] << 22)) | ({23{1'b0}} | (s0_d[21] << 21)) | ({23{1'b0}} | (s0_d[20] << 20)) | ({23{1'b0}} | (s0_d[19] << 19)) | ({23{1'b0}} | (s0_d[18] << 18)) | ({23{1'b0}} | (s0_d[17] << 17)) | ({23{1'b0}} | (s0_d[16] << 16)) | ({23{1'b0}} | (s0_d[15] << 15)) | ({23{1'b0}} | (s0_d[14] << 14)) | ({23{1'b0}} | (s0_d[13] << 13)) | ({23{1'b0}} | (s0_d[12] << 12)) | ({23{1'b0}} | (s0_d[11] << 11));
    end
    // --- pipeline stage 1: Fibonacci indices 10 down to 0 ---
    wire [15:0] s1_r [0:11];
    wire [22:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[10] = (s1_r[0] >= 16'd144);
    assign s1_r[1] = s1_d[10] ? (s1_r[0] - 16'd144) : s1_r[0];
    assign s1_d[9] = (s1_r[1] >= 16'd89);
    assign s1_r[2] = s1_d[9] ? (s1_r[1] - 16'd89) : s1_r[1];
    assign s1_d[8] = (s1_r[2] >= 16'd55);
    assign s1_r[3] = s1_d[8] ? (s1_r[2] - 16'd55) : s1_r[2];
    assign s1_d[7] = (s1_r[3] >= 16'd34);
    assign s1_r[4] = s1_d[7] ? (s1_r[3] - 16'd34) : s1_r[3];
    assign s1_d[6] = (s1_r[4] >= 16'd21);
    assign s1_r[5] = s1_d[6] ? (s1_r[4] - 16'd21) : s1_r[4];
    assign s1_d[5] = (s1_r[5] >= 16'd13);
    assign s1_r[6] = s1_d[5] ? (s1_r[5] - 16'd13) : s1_r[5];
    assign s1_d[4] = (s1_r[6] >= 16'd8);
    assign s1_r[7] = s1_d[4] ? (s1_r[6] - 16'd8) : s1_r[6];
    assign s1_d[3] = (s1_r[7] >= 16'd5);
    assign s1_r[8] = s1_d[3] ? (s1_r[7] - 16'd5) : s1_r[7];
    assign s1_d[2] = (s1_r[8] >= 16'd3);
    assign s1_r[9] = s1_d[2] ? (s1_r[8] - 16'd3) : s1_r[8];
    assign s1_d[1] = (s1_r[9] >= 16'd2);
    assign s1_r[10] = s1_d[1] ? (s1_r[9] - 16'd2) : s1_r[9];
    assign s1_d[0] = (s1_r[10] >= 16'd1);
    assign s1_r[11] = s1_d[0] ? (s1_r[10] - 16'd1) : s1_r[10];
    always @(posedge clk) begin
      r[2] <= s1_r[11];
      d[2] <= d[1] | ({23{1'b0}} | (s1_d[10] << 10)) | ({23{1'b0}} | (s1_d[9] << 9)) | ({23{1'b0}} | (s1_d[8] << 8)) | ({23{1'b0}} | (s1_d[7] << 7)) | ({23{1'b0}} | (s1_d[6] << 6)) | ({23{1'b0}} | (s1_d[5] << 5)) | ({23{1'b0}} | (s1_d[4] << 4)) | ({23{1'b0}} | (s1_d[3] << 3)) | ({23{1'b0}} | (s1_d[2] << 2)) | ({23{1'b0}} | (s1_d[1] << 1)) | ({23{1'b0}} | (s1_d[0] << 0));
    end
    assign z = d[2];
endmodule

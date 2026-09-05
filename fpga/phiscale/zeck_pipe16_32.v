// Zeckendorf normaliser, 32-stage pipeline (1 compare-subtracts per stage).
// Stages past the last Fibonacci index pass their registers through, so the
// depth can exceed the number of compare-subtracts without leaving the
// output undriven -- which is how the first generator produced a design
// whose top digits had no driver.
`default_nettype none
module zeck_pipe16_32 (input wire clk, input wire [15:0] x, output wire [22:0] z);
    reg  [15:0] r [0:32];
    reg  [22:0] d [0:32];
    always @(posedge clk) begin r[0] <= x; d[0] <= 0; end
    wire [15:0] s0_r [0:1];
    wire [22:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[22] = (s0_r[0] >= 16'd46368);
    assign s0_r[1] = s0_d[22] ? (s0_r[0] - 16'd46368) : s0_r[0];
    always @(posedge clk) begin
      r[1] <= s0_r[1];
      d[1] <= d[0] | (s0_d & 23'd4194304);
    end
    wire [15:0] s1_r [0:1];
    wire [22:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[21] = (s1_r[0] >= 16'd28657);
    assign s1_r[1] = s1_d[21] ? (s1_r[0] - 16'd28657) : s1_r[0];
    always @(posedge clk) begin
      r[2] <= s1_r[1];
      d[2] <= d[1] | (s1_d & 23'd2097152);
    end
    wire [15:0] s2_r [0:1];
    wire [22:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[20] = (s2_r[0] >= 16'd17711);
    assign s2_r[1] = s2_d[20] ? (s2_r[0] - 16'd17711) : s2_r[0];
    always @(posedge clk) begin
      r[3] <= s2_r[1];
      d[3] <= d[2] | (s2_d & 23'd1048576);
    end
    wire [15:0] s3_r [0:1];
    wire [22:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[19] = (s3_r[0] >= 16'd10946);
    assign s3_r[1] = s3_d[19] ? (s3_r[0] - 16'd10946) : s3_r[0];
    always @(posedge clk) begin
      r[4] <= s3_r[1];
      d[4] <= d[3] | (s3_d & 23'd524288);
    end
    wire [15:0] s4_r [0:1];
    wire [22:0] s4_d;
    assign s4_r[0] = r[4];
    assign s4_d[18] = (s4_r[0] >= 16'd6765);
    assign s4_r[1] = s4_d[18] ? (s4_r[0] - 16'd6765) : s4_r[0];
    always @(posedge clk) begin
      r[5] <= s4_r[1];
      d[5] <= d[4] | (s4_d & 23'd262144);
    end
    wire [15:0] s5_r [0:1];
    wire [22:0] s5_d;
    assign s5_r[0] = r[5];
    assign s5_d[17] = (s5_r[0] >= 16'd4181);
    assign s5_r[1] = s5_d[17] ? (s5_r[0] - 16'd4181) : s5_r[0];
    always @(posedge clk) begin
      r[6] <= s5_r[1];
      d[6] <= d[5] | (s5_d & 23'd131072);
    end
    wire [15:0] s6_r [0:1];
    wire [22:0] s6_d;
    assign s6_r[0] = r[6];
    assign s6_d[16] = (s6_r[0] >= 16'd2584);
    assign s6_r[1] = s6_d[16] ? (s6_r[0] - 16'd2584) : s6_r[0];
    always @(posedge clk) begin
      r[7] <= s6_r[1];
      d[7] <= d[6] | (s6_d & 23'd65536);
    end
    wire [15:0] s7_r [0:1];
    wire [22:0] s7_d;
    assign s7_r[0] = r[7];
    assign s7_d[15] = (s7_r[0] >= 16'd1597);
    assign s7_r[1] = s7_d[15] ? (s7_r[0] - 16'd1597) : s7_r[0];
    always @(posedge clk) begin
      r[8] <= s7_r[1];
      d[8] <= d[7] | (s7_d & 23'd32768);
    end
    wire [15:0] s8_r [0:1];
    wire [22:0] s8_d;
    assign s8_r[0] = r[8];
    assign s8_d[14] = (s8_r[0] >= 16'd987);
    assign s8_r[1] = s8_d[14] ? (s8_r[0] - 16'd987) : s8_r[0];
    always @(posedge clk) begin
      r[9] <= s8_r[1];
      d[9] <= d[8] | (s8_d & 23'd16384);
    end
    wire [15:0] s9_r [0:1];
    wire [22:0] s9_d;
    assign s9_r[0] = r[9];
    assign s9_d[13] = (s9_r[0] >= 16'd610);
    assign s9_r[1] = s9_d[13] ? (s9_r[0] - 16'd610) : s9_r[0];
    always @(posedge clk) begin
      r[10] <= s9_r[1];
      d[10] <= d[9] | (s9_d & 23'd8192);
    end
    wire [15:0] s10_r [0:1];
    wire [22:0] s10_d;
    assign s10_r[0] = r[10];
    assign s10_d[12] = (s10_r[0] >= 16'd377);
    assign s10_r[1] = s10_d[12] ? (s10_r[0] - 16'd377) : s10_r[0];
    always @(posedge clk) begin
      r[11] <= s10_r[1];
      d[11] <= d[10] | (s10_d & 23'd4096);
    end
    wire [15:0] s11_r [0:1];
    wire [22:0] s11_d;
    assign s11_r[0] = r[11];
    assign s11_d[11] = (s11_r[0] >= 16'd233);
    assign s11_r[1] = s11_d[11] ? (s11_r[0] - 16'd233) : s11_r[0];
    always @(posedge clk) begin
      r[12] <= s11_r[1];
      d[12] <= d[11] | (s11_d & 23'd2048);
    end
    wire [15:0] s12_r [0:1];
    wire [22:0] s12_d;
    assign s12_r[0] = r[12];
    assign s12_d[10] = (s12_r[0] >= 16'd144);
    assign s12_r[1] = s12_d[10] ? (s12_r[0] - 16'd144) : s12_r[0];
    always @(posedge clk) begin
      r[13] <= s12_r[1];
      d[13] <= d[12] | (s12_d & 23'd1024);
    end
    wire [15:0] s13_r [0:1];
    wire [22:0] s13_d;
    assign s13_r[0] = r[13];
    assign s13_d[9] = (s13_r[0] >= 16'd89);
    assign s13_r[1] = s13_d[9] ? (s13_r[0] - 16'd89) : s13_r[0];
    always @(posedge clk) begin
      r[14] <= s13_r[1];
      d[14] <= d[13] | (s13_d & 23'd512);
    end
    wire [15:0] s14_r [0:1];
    wire [22:0] s14_d;
    assign s14_r[0] = r[14];
    assign s14_d[8] = (s14_r[0] >= 16'd55);
    assign s14_r[1] = s14_d[8] ? (s14_r[0] - 16'd55) : s14_r[0];
    always @(posedge clk) begin
      r[15] <= s14_r[1];
      d[15] <= d[14] | (s14_d & 23'd256);
    end
    wire [15:0] s15_r [0:1];
    wire [22:0] s15_d;
    assign s15_r[0] = r[15];
    assign s15_d[7] = (s15_r[0] >= 16'd34);
    assign s15_r[1] = s15_d[7] ? (s15_r[0] - 16'd34) : s15_r[0];
    always @(posedge clk) begin
      r[16] <= s15_r[1];
      d[16] <= d[15] | (s15_d & 23'd128);
    end
    wire [15:0] s16_r [0:1];
    wire [22:0] s16_d;
    assign s16_r[0] = r[16];
    assign s16_d[6] = (s16_r[0] >= 16'd21);
    assign s16_r[1] = s16_d[6] ? (s16_r[0] - 16'd21) : s16_r[0];
    always @(posedge clk) begin
      r[17] <= s16_r[1];
      d[17] <= d[16] | (s16_d & 23'd64);
    end
    wire [15:0] s17_r [0:1];
    wire [22:0] s17_d;
    assign s17_r[0] = r[17];
    assign s17_d[5] = (s17_r[0] >= 16'd13);
    assign s17_r[1] = s17_d[5] ? (s17_r[0] - 16'd13) : s17_r[0];
    always @(posedge clk) begin
      r[18] <= s17_r[1];
      d[18] <= d[17] | (s17_d & 23'd32);
    end
    wire [15:0] s18_r [0:1];
    wire [22:0] s18_d;
    assign s18_r[0] = r[18];
    assign s18_d[4] = (s18_r[0] >= 16'd8);
    assign s18_r[1] = s18_d[4] ? (s18_r[0] - 16'd8) : s18_r[0];
    always @(posedge clk) begin
      r[19] <= s18_r[1];
      d[19] <= d[18] | (s18_d & 23'd16);
    end
    wire [15:0] s19_r [0:1];
    wire [22:0] s19_d;
    assign s19_r[0] = r[19];
    assign s19_d[3] = (s19_r[0] >= 16'd5);
    assign s19_r[1] = s19_d[3] ? (s19_r[0] - 16'd5) : s19_r[0];
    always @(posedge clk) begin
      r[20] <= s19_r[1];
      d[20] <= d[19] | (s19_d & 23'd8);
    end
    wire [15:0] s20_r [0:1];
    wire [22:0] s20_d;
    assign s20_r[0] = r[20];
    assign s20_d[2] = (s20_r[0] >= 16'd3);
    assign s20_r[1] = s20_d[2] ? (s20_r[0] - 16'd3) : s20_r[0];
    always @(posedge clk) begin
      r[21] <= s20_r[1];
      d[21] <= d[20] | (s20_d & 23'd4);
    end
    wire [15:0] s21_r [0:1];
    wire [22:0] s21_d;
    assign s21_r[0] = r[21];
    assign s21_d[1] = (s21_r[0] >= 16'd2);
    assign s21_r[1] = s21_d[1] ? (s21_r[0] - 16'd2) : s21_r[0];
    always @(posedge clk) begin
      r[22] <= s21_r[1];
      d[22] <= d[21] | (s21_d & 23'd2);
    end
    wire [15:0] s22_r [0:1];
    wire [22:0] s22_d;
    assign s22_r[0] = r[22];
    assign s22_d[0] = (s22_r[0] >= 16'd1);
    assign s22_r[1] = s22_d[0] ? (s22_r[0] - 16'd1) : s22_r[0];
    always @(posedge clk) begin
      r[23] <= s22_r[1];
      d[23] <= d[22] | (s22_d & 23'd1);
    end
    always @(posedge clk) begin r[24] <= r[23]; d[24] <= d[23]; end
    always @(posedge clk) begin r[25] <= r[24]; d[25] <= d[24]; end
    always @(posedge clk) begin r[26] <= r[25]; d[26] <= d[25]; end
    always @(posedge clk) begin r[27] <= r[26]; d[27] <= d[26]; end
    always @(posedge clk) begin r[28] <= r[27]; d[28] <= d[27]; end
    always @(posedge clk) begin r[29] <= r[28]; d[29] <= d[28]; end
    always @(posedge clk) begin r[30] <= r[29]; d[30] <= d[29]; end
    always @(posedge clk) begin r[31] <= r[30]; d[31] <= d[30]; end
    always @(posedge clk) begin r[32] <= r[31]; d[32] <= d[31]; end
    assign z = d[32];
endmodule

// Zeckendorf normaliser, 32-stage pipeline (2 compare-subtracts per stage).
// Stages past the last Fibonacci index pass their registers through, so the
// depth can exceed the number of compare-subtracts without leaving the
// output undriven -- which is how the first generator produced a design
// whose top digits had no driver.
`default_nettype none
module zeck_pipe32_32 (input wire clk, input wire [31:0] x, output wire [45:0] z);
    reg  [31:0] r [0:32];
    reg  [45:0] d [0:32];
    always @(posedge clk) begin r[0] <= x; d[0] <= 0; end
    wire [31:0] s0_r [0:2];
    wire [45:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[45] = (s0_r[0] >= 32'd2971215073);
    assign s0_r[1] = s0_d[45] ? (s0_r[0] - 32'd2971215073) : s0_r[0];
    assign s0_d[44] = (s0_r[1] >= 32'd1836311903);
    assign s0_r[2] = s0_d[44] ? (s0_r[1] - 32'd1836311903) : s0_r[1];
    always @(posedge clk) begin
      r[1] <= s0_r[2];
      d[1] <= d[0] | (s0_d & 46'd52776558133248);
    end
    wire [31:0] s1_r [0:2];
    wire [45:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[43] = (s1_r[0] >= 32'd1134903170);
    assign s1_r[1] = s1_d[43] ? (s1_r[0] - 32'd1134903170) : s1_r[0];
    assign s1_d[42] = (s1_r[1] >= 32'd701408733);
    assign s1_r[2] = s1_d[42] ? (s1_r[1] - 32'd701408733) : s1_r[1];
    always @(posedge clk) begin
      r[2] <= s1_r[2];
      d[2] <= d[1] | (s1_d & 46'd13194139533312);
    end
    wire [31:0] s2_r [0:2];
    wire [45:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[41] = (s2_r[0] >= 32'd433494437);
    assign s2_r[1] = s2_d[41] ? (s2_r[0] - 32'd433494437) : s2_r[0];
    assign s2_d[40] = (s2_r[1] >= 32'd267914296);
    assign s2_r[2] = s2_d[40] ? (s2_r[1] - 32'd267914296) : s2_r[1];
    always @(posedge clk) begin
      r[3] <= s2_r[2];
      d[3] <= d[2] | (s2_d & 46'd3298534883328);
    end
    wire [31:0] s3_r [0:2];
    wire [45:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[39] = (s3_r[0] >= 32'd165580141);
    assign s3_r[1] = s3_d[39] ? (s3_r[0] - 32'd165580141) : s3_r[0];
    assign s3_d[38] = (s3_r[1] >= 32'd102334155);
    assign s3_r[2] = s3_d[38] ? (s3_r[1] - 32'd102334155) : s3_r[1];
    always @(posedge clk) begin
      r[4] <= s3_r[2];
      d[4] <= d[3] | (s3_d & 46'd824633720832);
    end
    wire [31:0] s4_r [0:2];
    wire [45:0] s4_d;
    assign s4_r[0] = r[4];
    assign s4_d[37] = (s4_r[0] >= 32'd63245986);
    assign s4_r[1] = s4_d[37] ? (s4_r[0] - 32'd63245986) : s4_r[0];
    assign s4_d[36] = (s4_r[1] >= 32'd39088169);
    assign s4_r[2] = s4_d[36] ? (s4_r[1] - 32'd39088169) : s4_r[1];
    always @(posedge clk) begin
      r[5] <= s4_r[2];
      d[5] <= d[4] | (s4_d & 46'd206158430208);
    end
    wire [31:0] s5_r [0:2];
    wire [45:0] s5_d;
    assign s5_r[0] = r[5];
    assign s5_d[35] = (s5_r[0] >= 32'd24157817);
    assign s5_r[1] = s5_d[35] ? (s5_r[0] - 32'd24157817) : s5_r[0];
    assign s5_d[34] = (s5_r[1] >= 32'd14930352);
    assign s5_r[2] = s5_d[34] ? (s5_r[1] - 32'd14930352) : s5_r[1];
    always @(posedge clk) begin
      r[6] <= s5_r[2];
      d[6] <= d[5] | (s5_d & 46'd51539607552);
    end
    wire [31:0] s6_r [0:2];
    wire [45:0] s6_d;
    assign s6_r[0] = r[6];
    assign s6_d[33] = (s6_r[0] >= 32'd9227465);
    assign s6_r[1] = s6_d[33] ? (s6_r[0] - 32'd9227465) : s6_r[0];
    assign s6_d[32] = (s6_r[1] >= 32'd5702887);
    assign s6_r[2] = s6_d[32] ? (s6_r[1] - 32'd5702887) : s6_r[1];
    always @(posedge clk) begin
      r[7] <= s6_r[2];
      d[7] <= d[6] | (s6_d & 46'd12884901888);
    end
    wire [31:0] s7_r [0:2];
    wire [45:0] s7_d;
    assign s7_r[0] = r[7];
    assign s7_d[31] = (s7_r[0] >= 32'd3524578);
    assign s7_r[1] = s7_d[31] ? (s7_r[0] - 32'd3524578) : s7_r[0];
    assign s7_d[30] = (s7_r[1] >= 32'd2178309);
    assign s7_r[2] = s7_d[30] ? (s7_r[1] - 32'd2178309) : s7_r[1];
    always @(posedge clk) begin
      r[8] <= s7_r[2];
      d[8] <= d[7] | (s7_d & 46'd3221225472);
    end
    wire [31:0] s8_r [0:2];
    wire [45:0] s8_d;
    assign s8_r[0] = r[8];
    assign s8_d[29] = (s8_r[0] >= 32'd1346269);
    assign s8_r[1] = s8_d[29] ? (s8_r[0] - 32'd1346269) : s8_r[0];
    assign s8_d[28] = (s8_r[1] >= 32'd832040);
    assign s8_r[2] = s8_d[28] ? (s8_r[1] - 32'd832040) : s8_r[1];
    always @(posedge clk) begin
      r[9] <= s8_r[2];
      d[9] <= d[8] | (s8_d & 46'd805306368);
    end
    wire [31:0] s9_r [0:2];
    wire [45:0] s9_d;
    assign s9_r[0] = r[9];
    assign s9_d[27] = (s9_r[0] >= 32'd514229);
    assign s9_r[1] = s9_d[27] ? (s9_r[0] - 32'd514229) : s9_r[0];
    assign s9_d[26] = (s9_r[1] >= 32'd317811);
    assign s9_r[2] = s9_d[26] ? (s9_r[1] - 32'd317811) : s9_r[1];
    always @(posedge clk) begin
      r[10] <= s9_r[2];
      d[10] <= d[9] | (s9_d & 46'd201326592);
    end
    wire [31:0] s10_r [0:2];
    wire [45:0] s10_d;
    assign s10_r[0] = r[10];
    assign s10_d[25] = (s10_r[0] >= 32'd196418);
    assign s10_r[1] = s10_d[25] ? (s10_r[0] - 32'd196418) : s10_r[0];
    assign s10_d[24] = (s10_r[1] >= 32'd121393);
    assign s10_r[2] = s10_d[24] ? (s10_r[1] - 32'd121393) : s10_r[1];
    always @(posedge clk) begin
      r[11] <= s10_r[2];
      d[11] <= d[10] | (s10_d & 46'd50331648);
    end
    wire [31:0] s11_r [0:2];
    wire [45:0] s11_d;
    assign s11_r[0] = r[11];
    assign s11_d[23] = (s11_r[0] >= 32'd75025);
    assign s11_r[1] = s11_d[23] ? (s11_r[0] - 32'd75025) : s11_r[0];
    assign s11_d[22] = (s11_r[1] >= 32'd46368);
    assign s11_r[2] = s11_d[22] ? (s11_r[1] - 32'd46368) : s11_r[1];
    always @(posedge clk) begin
      r[12] <= s11_r[2];
      d[12] <= d[11] | (s11_d & 46'd12582912);
    end
    wire [31:0] s12_r [0:2];
    wire [45:0] s12_d;
    assign s12_r[0] = r[12];
    assign s12_d[21] = (s12_r[0] >= 32'd28657);
    assign s12_r[1] = s12_d[21] ? (s12_r[0] - 32'd28657) : s12_r[0];
    assign s12_d[20] = (s12_r[1] >= 32'd17711);
    assign s12_r[2] = s12_d[20] ? (s12_r[1] - 32'd17711) : s12_r[1];
    always @(posedge clk) begin
      r[13] <= s12_r[2];
      d[13] <= d[12] | (s12_d & 46'd3145728);
    end
    wire [31:0] s13_r [0:2];
    wire [45:0] s13_d;
    assign s13_r[0] = r[13];
    assign s13_d[19] = (s13_r[0] >= 32'd10946);
    assign s13_r[1] = s13_d[19] ? (s13_r[0] - 32'd10946) : s13_r[0];
    assign s13_d[18] = (s13_r[1] >= 32'd6765);
    assign s13_r[2] = s13_d[18] ? (s13_r[1] - 32'd6765) : s13_r[1];
    always @(posedge clk) begin
      r[14] <= s13_r[2];
      d[14] <= d[13] | (s13_d & 46'd786432);
    end
    wire [31:0] s14_r [0:2];
    wire [45:0] s14_d;
    assign s14_r[0] = r[14];
    assign s14_d[17] = (s14_r[0] >= 32'd4181);
    assign s14_r[1] = s14_d[17] ? (s14_r[0] - 32'd4181) : s14_r[0];
    assign s14_d[16] = (s14_r[1] >= 32'd2584);
    assign s14_r[2] = s14_d[16] ? (s14_r[1] - 32'd2584) : s14_r[1];
    always @(posedge clk) begin
      r[15] <= s14_r[2];
      d[15] <= d[14] | (s14_d & 46'd196608);
    end
    wire [31:0] s15_r [0:2];
    wire [45:0] s15_d;
    assign s15_r[0] = r[15];
    assign s15_d[15] = (s15_r[0] >= 32'd1597);
    assign s15_r[1] = s15_d[15] ? (s15_r[0] - 32'd1597) : s15_r[0];
    assign s15_d[14] = (s15_r[1] >= 32'd987);
    assign s15_r[2] = s15_d[14] ? (s15_r[1] - 32'd987) : s15_r[1];
    always @(posedge clk) begin
      r[16] <= s15_r[2];
      d[16] <= d[15] | (s15_d & 46'd49152);
    end
    wire [31:0] s16_r [0:2];
    wire [45:0] s16_d;
    assign s16_r[0] = r[16];
    assign s16_d[13] = (s16_r[0] >= 32'd610);
    assign s16_r[1] = s16_d[13] ? (s16_r[0] - 32'd610) : s16_r[0];
    assign s16_d[12] = (s16_r[1] >= 32'd377);
    assign s16_r[2] = s16_d[12] ? (s16_r[1] - 32'd377) : s16_r[1];
    always @(posedge clk) begin
      r[17] <= s16_r[2];
      d[17] <= d[16] | (s16_d & 46'd12288);
    end
    wire [31:0] s17_r [0:2];
    wire [45:0] s17_d;
    assign s17_r[0] = r[17];
    assign s17_d[11] = (s17_r[0] >= 32'd233);
    assign s17_r[1] = s17_d[11] ? (s17_r[0] - 32'd233) : s17_r[0];
    assign s17_d[10] = (s17_r[1] >= 32'd144);
    assign s17_r[2] = s17_d[10] ? (s17_r[1] - 32'd144) : s17_r[1];
    always @(posedge clk) begin
      r[18] <= s17_r[2];
      d[18] <= d[17] | (s17_d & 46'd3072);
    end
    wire [31:0] s18_r [0:2];
    wire [45:0] s18_d;
    assign s18_r[0] = r[18];
    assign s18_d[9] = (s18_r[0] >= 32'd89);
    assign s18_r[1] = s18_d[9] ? (s18_r[0] - 32'd89) : s18_r[0];
    assign s18_d[8] = (s18_r[1] >= 32'd55);
    assign s18_r[2] = s18_d[8] ? (s18_r[1] - 32'd55) : s18_r[1];
    always @(posedge clk) begin
      r[19] <= s18_r[2];
      d[19] <= d[18] | (s18_d & 46'd768);
    end
    wire [31:0] s19_r [0:2];
    wire [45:0] s19_d;
    assign s19_r[0] = r[19];
    assign s19_d[7] = (s19_r[0] >= 32'd34);
    assign s19_r[1] = s19_d[7] ? (s19_r[0] - 32'd34) : s19_r[0];
    assign s19_d[6] = (s19_r[1] >= 32'd21);
    assign s19_r[2] = s19_d[6] ? (s19_r[1] - 32'd21) : s19_r[1];
    always @(posedge clk) begin
      r[20] <= s19_r[2];
      d[20] <= d[19] | (s19_d & 46'd192);
    end
    wire [31:0] s20_r [0:2];
    wire [45:0] s20_d;
    assign s20_r[0] = r[20];
    assign s20_d[5] = (s20_r[0] >= 32'd13);
    assign s20_r[1] = s20_d[5] ? (s20_r[0] - 32'd13) : s20_r[0];
    assign s20_d[4] = (s20_r[1] >= 32'd8);
    assign s20_r[2] = s20_d[4] ? (s20_r[1] - 32'd8) : s20_r[1];
    always @(posedge clk) begin
      r[21] <= s20_r[2];
      d[21] <= d[20] | (s20_d & 46'd48);
    end
    wire [31:0] s21_r [0:2];
    wire [45:0] s21_d;
    assign s21_r[0] = r[21];
    assign s21_d[3] = (s21_r[0] >= 32'd5);
    assign s21_r[1] = s21_d[3] ? (s21_r[0] - 32'd5) : s21_r[0];
    assign s21_d[2] = (s21_r[1] >= 32'd3);
    assign s21_r[2] = s21_d[2] ? (s21_r[1] - 32'd3) : s21_r[1];
    always @(posedge clk) begin
      r[22] <= s21_r[2];
      d[22] <= d[21] | (s21_d & 46'd12);
    end
    wire [31:0] s22_r [0:2];
    wire [45:0] s22_d;
    assign s22_r[0] = r[22];
    assign s22_d[1] = (s22_r[0] >= 32'd2);
    assign s22_r[1] = s22_d[1] ? (s22_r[0] - 32'd2) : s22_r[0];
    assign s22_d[0] = (s22_r[1] >= 32'd1);
    assign s22_r[2] = s22_d[0] ? (s22_r[1] - 32'd1) : s22_r[1];
    always @(posedge clk) begin
      r[23] <= s22_r[2];
      d[23] <= d[22] | (s22_d & 46'd3);
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

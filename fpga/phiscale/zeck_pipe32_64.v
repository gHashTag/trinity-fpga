// Zeckendorf normaliser, 64-stage pipeline (1 compare-subtracts per stage).
// Stages past the last Fibonacci index pass their registers through, so the
// depth can exceed the number of compare-subtracts without leaving the
// output undriven -- which is how the first generator produced a design
// whose top digits had no driver.
`default_nettype none
module zeck_pipe32_64 (input wire clk, input wire [31:0] x, output wire [45:0] z);
    reg  [31:0] r [0:64];
    reg  [45:0] d [0:64];
    always @(posedge clk) begin r[0] <= x; d[0] <= 0; end
    wire [31:0] s0_r [0:1];
    wire [45:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[45] = (s0_r[0] >= 32'd2971215073);
    assign s0_r[1] = s0_d[45] ? (s0_r[0] - 32'd2971215073) : s0_r[0];
    always @(posedge clk) begin
      r[1] <= s0_r[1];
      d[1] <= d[0] | (s0_d & 46'd35184372088832);
    end
    wire [31:0] s1_r [0:1];
    wire [45:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[44] = (s1_r[0] >= 32'd1836311903);
    assign s1_r[1] = s1_d[44] ? (s1_r[0] - 32'd1836311903) : s1_r[0];
    always @(posedge clk) begin
      r[2] <= s1_r[1];
      d[2] <= d[1] | (s1_d & 46'd17592186044416);
    end
    wire [31:0] s2_r [0:1];
    wire [45:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[43] = (s2_r[0] >= 32'd1134903170);
    assign s2_r[1] = s2_d[43] ? (s2_r[0] - 32'd1134903170) : s2_r[0];
    always @(posedge clk) begin
      r[3] <= s2_r[1];
      d[3] <= d[2] | (s2_d & 46'd8796093022208);
    end
    wire [31:0] s3_r [0:1];
    wire [45:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[42] = (s3_r[0] >= 32'd701408733);
    assign s3_r[1] = s3_d[42] ? (s3_r[0] - 32'd701408733) : s3_r[0];
    always @(posedge clk) begin
      r[4] <= s3_r[1];
      d[4] <= d[3] | (s3_d & 46'd4398046511104);
    end
    wire [31:0] s4_r [0:1];
    wire [45:0] s4_d;
    assign s4_r[0] = r[4];
    assign s4_d[41] = (s4_r[0] >= 32'd433494437);
    assign s4_r[1] = s4_d[41] ? (s4_r[0] - 32'd433494437) : s4_r[0];
    always @(posedge clk) begin
      r[5] <= s4_r[1];
      d[5] <= d[4] | (s4_d & 46'd2199023255552);
    end
    wire [31:0] s5_r [0:1];
    wire [45:0] s5_d;
    assign s5_r[0] = r[5];
    assign s5_d[40] = (s5_r[0] >= 32'd267914296);
    assign s5_r[1] = s5_d[40] ? (s5_r[0] - 32'd267914296) : s5_r[0];
    always @(posedge clk) begin
      r[6] <= s5_r[1];
      d[6] <= d[5] | (s5_d & 46'd1099511627776);
    end
    wire [31:0] s6_r [0:1];
    wire [45:0] s6_d;
    assign s6_r[0] = r[6];
    assign s6_d[39] = (s6_r[0] >= 32'd165580141);
    assign s6_r[1] = s6_d[39] ? (s6_r[0] - 32'd165580141) : s6_r[0];
    always @(posedge clk) begin
      r[7] <= s6_r[1];
      d[7] <= d[6] | (s6_d & 46'd549755813888);
    end
    wire [31:0] s7_r [0:1];
    wire [45:0] s7_d;
    assign s7_r[0] = r[7];
    assign s7_d[38] = (s7_r[0] >= 32'd102334155);
    assign s7_r[1] = s7_d[38] ? (s7_r[0] - 32'd102334155) : s7_r[0];
    always @(posedge clk) begin
      r[8] <= s7_r[1];
      d[8] <= d[7] | (s7_d & 46'd274877906944);
    end
    wire [31:0] s8_r [0:1];
    wire [45:0] s8_d;
    assign s8_r[0] = r[8];
    assign s8_d[37] = (s8_r[0] >= 32'd63245986);
    assign s8_r[1] = s8_d[37] ? (s8_r[0] - 32'd63245986) : s8_r[0];
    always @(posedge clk) begin
      r[9] <= s8_r[1];
      d[9] <= d[8] | (s8_d & 46'd137438953472);
    end
    wire [31:0] s9_r [0:1];
    wire [45:0] s9_d;
    assign s9_r[0] = r[9];
    assign s9_d[36] = (s9_r[0] >= 32'd39088169);
    assign s9_r[1] = s9_d[36] ? (s9_r[0] - 32'd39088169) : s9_r[0];
    always @(posedge clk) begin
      r[10] <= s9_r[1];
      d[10] <= d[9] | (s9_d & 46'd68719476736);
    end
    wire [31:0] s10_r [0:1];
    wire [45:0] s10_d;
    assign s10_r[0] = r[10];
    assign s10_d[35] = (s10_r[0] >= 32'd24157817);
    assign s10_r[1] = s10_d[35] ? (s10_r[0] - 32'd24157817) : s10_r[0];
    always @(posedge clk) begin
      r[11] <= s10_r[1];
      d[11] <= d[10] | (s10_d & 46'd34359738368);
    end
    wire [31:0] s11_r [0:1];
    wire [45:0] s11_d;
    assign s11_r[0] = r[11];
    assign s11_d[34] = (s11_r[0] >= 32'd14930352);
    assign s11_r[1] = s11_d[34] ? (s11_r[0] - 32'd14930352) : s11_r[0];
    always @(posedge clk) begin
      r[12] <= s11_r[1];
      d[12] <= d[11] | (s11_d & 46'd17179869184);
    end
    wire [31:0] s12_r [0:1];
    wire [45:0] s12_d;
    assign s12_r[0] = r[12];
    assign s12_d[33] = (s12_r[0] >= 32'd9227465);
    assign s12_r[1] = s12_d[33] ? (s12_r[0] - 32'd9227465) : s12_r[0];
    always @(posedge clk) begin
      r[13] <= s12_r[1];
      d[13] <= d[12] | (s12_d & 46'd8589934592);
    end
    wire [31:0] s13_r [0:1];
    wire [45:0] s13_d;
    assign s13_r[0] = r[13];
    assign s13_d[32] = (s13_r[0] >= 32'd5702887);
    assign s13_r[1] = s13_d[32] ? (s13_r[0] - 32'd5702887) : s13_r[0];
    always @(posedge clk) begin
      r[14] <= s13_r[1];
      d[14] <= d[13] | (s13_d & 46'd4294967296);
    end
    wire [31:0] s14_r [0:1];
    wire [45:0] s14_d;
    assign s14_r[0] = r[14];
    assign s14_d[31] = (s14_r[0] >= 32'd3524578);
    assign s14_r[1] = s14_d[31] ? (s14_r[0] - 32'd3524578) : s14_r[0];
    always @(posedge clk) begin
      r[15] <= s14_r[1];
      d[15] <= d[14] | (s14_d & 46'd2147483648);
    end
    wire [31:0] s15_r [0:1];
    wire [45:0] s15_d;
    assign s15_r[0] = r[15];
    assign s15_d[30] = (s15_r[0] >= 32'd2178309);
    assign s15_r[1] = s15_d[30] ? (s15_r[0] - 32'd2178309) : s15_r[0];
    always @(posedge clk) begin
      r[16] <= s15_r[1];
      d[16] <= d[15] | (s15_d & 46'd1073741824);
    end
    wire [31:0] s16_r [0:1];
    wire [45:0] s16_d;
    assign s16_r[0] = r[16];
    assign s16_d[29] = (s16_r[0] >= 32'd1346269);
    assign s16_r[1] = s16_d[29] ? (s16_r[0] - 32'd1346269) : s16_r[0];
    always @(posedge clk) begin
      r[17] <= s16_r[1];
      d[17] <= d[16] | (s16_d & 46'd536870912);
    end
    wire [31:0] s17_r [0:1];
    wire [45:0] s17_d;
    assign s17_r[0] = r[17];
    assign s17_d[28] = (s17_r[0] >= 32'd832040);
    assign s17_r[1] = s17_d[28] ? (s17_r[0] - 32'd832040) : s17_r[0];
    always @(posedge clk) begin
      r[18] <= s17_r[1];
      d[18] <= d[17] | (s17_d & 46'd268435456);
    end
    wire [31:0] s18_r [0:1];
    wire [45:0] s18_d;
    assign s18_r[0] = r[18];
    assign s18_d[27] = (s18_r[0] >= 32'd514229);
    assign s18_r[1] = s18_d[27] ? (s18_r[0] - 32'd514229) : s18_r[0];
    always @(posedge clk) begin
      r[19] <= s18_r[1];
      d[19] <= d[18] | (s18_d & 46'd134217728);
    end
    wire [31:0] s19_r [0:1];
    wire [45:0] s19_d;
    assign s19_r[0] = r[19];
    assign s19_d[26] = (s19_r[0] >= 32'd317811);
    assign s19_r[1] = s19_d[26] ? (s19_r[0] - 32'd317811) : s19_r[0];
    always @(posedge clk) begin
      r[20] <= s19_r[1];
      d[20] <= d[19] | (s19_d & 46'd67108864);
    end
    wire [31:0] s20_r [0:1];
    wire [45:0] s20_d;
    assign s20_r[0] = r[20];
    assign s20_d[25] = (s20_r[0] >= 32'd196418);
    assign s20_r[1] = s20_d[25] ? (s20_r[0] - 32'd196418) : s20_r[0];
    always @(posedge clk) begin
      r[21] <= s20_r[1];
      d[21] <= d[20] | (s20_d & 46'd33554432);
    end
    wire [31:0] s21_r [0:1];
    wire [45:0] s21_d;
    assign s21_r[0] = r[21];
    assign s21_d[24] = (s21_r[0] >= 32'd121393);
    assign s21_r[1] = s21_d[24] ? (s21_r[0] - 32'd121393) : s21_r[0];
    always @(posedge clk) begin
      r[22] <= s21_r[1];
      d[22] <= d[21] | (s21_d & 46'd16777216);
    end
    wire [31:0] s22_r [0:1];
    wire [45:0] s22_d;
    assign s22_r[0] = r[22];
    assign s22_d[23] = (s22_r[0] >= 32'd75025);
    assign s22_r[1] = s22_d[23] ? (s22_r[0] - 32'd75025) : s22_r[0];
    always @(posedge clk) begin
      r[23] <= s22_r[1];
      d[23] <= d[22] | (s22_d & 46'd8388608);
    end
    wire [31:0] s23_r [0:1];
    wire [45:0] s23_d;
    assign s23_r[0] = r[23];
    assign s23_d[22] = (s23_r[0] >= 32'd46368);
    assign s23_r[1] = s23_d[22] ? (s23_r[0] - 32'd46368) : s23_r[0];
    always @(posedge clk) begin
      r[24] <= s23_r[1];
      d[24] <= d[23] | (s23_d & 46'd4194304);
    end
    wire [31:0] s24_r [0:1];
    wire [45:0] s24_d;
    assign s24_r[0] = r[24];
    assign s24_d[21] = (s24_r[0] >= 32'd28657);
    assign s24_r[1] = s24_d[21] ? (s24_r[0] - 32'd28657) : s24_r[0];
    always @(posedge clk) begin
      r[25] <= s24_r[1];
      d[25] <= d[24] | (s24_d & 46'd2097152);
    end
    wire [31:0] s25_r [0:1];
    wire [45:0] s25_d;
    assign s25_r[0] = r[25];
    assign s25_d[20] = (s25_r[0] >= 32'd17711);
    assign s25_r[1] = s25_d[20] ? (s25_r[0] - 32'd17711) : s25_r[0];
    always @(posedge clk) begin
      r[26] <= s25_r[1];
      d[26] <= d[25] | (s25_d & 46'd1048576);
    end
    wire [31:0] s26_r [0:1];
    wire [45:0] s26_d;
    assign s26_r[0] = r[26];
    assign s26_d[19] = (s26_r[0] >= 32'd10946);
    assign s26_r[1] = s26_d[19] ? (s26_r[0] - 32'd10946) : s26_r[0];
    always @(posedge clk) begin
      r[27] <= s26_r[1];
      d[27] <= d[26] | (s26_d & 46'd524288);
    end
    wire [31:0] s27_r [0:1];
    wire [45:0] s27_d;
    assign s27_r[0] = r[27];
    assign s27_d[18] = (s27_r[0] >= 32'd6765);
    assign s27_r[1] = s27_d[18] ? (s27_r[0] - 32'd6765) : s27_r[0];
    always @(posedge clk) begin
      r[28] <= s27_r[1];
      d[28] <= d[27] | (s27_d & 46'd262144);
    end
    wire [31:0] s28_r [0:1];
    wire [45:0] s28_d;
    assign s28_r[0] = r[28];
    assign s28_d[17] = (s28_r[0] >= 32'd4181);
    assign s28_r[1] = s28_d[17] ? (s28_r[0] - 32'd4181) : s28_r[0];
    always @(posedge clk) begin
      r[29] <= s28_r[1];
      d[29] <= d[28] | (s28_d & 46'd131072);
    end
    wire [31:0] s29_r [0:1];
    wire [45:0] s29_d;
    assign s29_r[0] = r[29];
    assign s29_d[16] = (s29_r[0] >= 32'd2584);
    assign s29_r[1] = s29_d[16] ? (s29_r[0] - 32'd2584) : s29_r[0];
    always @(posedge clk) begin
      r[30] <= s29_r[1];
      d[30] <= d[29] | (s29_d & 46'd65536);
    end
    wire [31:0] s30_r [0:1];
    wire [45:0] s30_d;
    assign s30_r[0] = r[30];
    assign s30_d[15] = (s30_r[0] >= 32'd1597);
    assign s30_r[1] = s30_d[15] ? (s30_r[0] - 32'd1597) : s30_r[0];
    always @(posedge clk) begin
      r[31] <= s30_r[1];
      d[31] <= d[30] | (s30_d & 46'd32768);
    end
    wire [31:0] s31_r [0:1];
    wire [45:0] s31_d;
    assign s31_r[0] = r[31];
    assign s31_d[14] = (s31_r[0] >= 32'd987);
    assign s31_r[1] = s31_d[14] ? (s31_r[0] - 32'd987) : s31_r[0];
    always @(posedge clk) begin
      r[32] <= s31_r[1];
      d[32] <= d[31] | (s31_d & 46'd16384);
    end
    wire [31:0] s32_r [0:1];
    wire [45:0] s32_d;
    assign s32_r[0] = r[32];
    assign s32_d[13] = (s32_r[0] >= 32'd610);
    assign s32_r[1] = s32_d[13] ? (s32_r[0] - 32'd610) : s32_r[0];
    always @(posedge clk) begin
      r[33] <= s32_r[1];
      d[33] <= d[32] | (s32_d & 46'd8192);
    end
    wire [31:0] s33_r [0:1];
    wire [45:0] s33_d;
    assign s33_r[0] = r[33];
    assign s33_d[12] = (s33_r[0] >= 32'd377);
    assign s33_r[1] = s33_d[12] ? (s33_r[0] - 32'd377) : s33_r[0];
    always @(posedge clk) begin
      r[34] <= s33_r[1];
      d[34] <= d[33] | (s33_d & 46'd4096);
    end
    wire [31:0] s34_r [0:1];
    wire [45:0] s34_d;
    assign s34_r[0] = r[34];
    assign s34_d[11] = (s34_r[0] >= 32'd233);
    assign s34_r[1] = s34_d[11] ? (s34_r[0] - 32'd233) : s34_r[0];
    always @(posedge clk) begin
      r[35] <= s34_r[1];
      d[35] <= d[34] | (s34_d & 46'd2048);
    end
    wire [31:0] s35_r [0:1];
    wire [45:0] s35_d;
    assign s35_r[0] = r[35];
    assign s35_d[10] = (s35_r[0] >= 32'd144);
    assign s35_r[1] = s35_d[10] ? (s35_r[0] - 32'd144) : s35_r[0];
    always @(posedge clk) begin
      r[36] <= s35_r[1];
      d[36] <= d[35] | (s35_d & 46'd1024);
    end
    wire [31:0] s36_r [0:1];
    wire [45:0] s36_d;
    assign s36_r[0] = r[36];
    assign s36_d[9] = (s36_r[0] >= 32'd89);
    assign s36_r[1] = s36_d[9] ? (s36_r[0] - 32'd89) : s36_r[0];
    always @(posedge clk) begin
      r[37] <= s36_r[1];
      d[37] <= d[36] | (s36_d & 46'd512);
    end
    wire [31:0] s37_r [0:1];
    wire [45:0] s37_d;
    assign s37_r[0] = r[37];
    assign s37_d[8] = (s37_r[0] >= 32'd55);
    assign s37_r[1] = s37_d[8] ? (s37_r[0] - 32'd55) : s37_r[0];
    always @(posedge clk) begin
      r[38] <= s37_r[1];
      d[38] <= d[37] | (s37_d & 46'd256);
    end
    wire [31:0] s38_r [0:1];
    wire [45:0] s38_d;
    assign s38_r[0] = r[38];
    assign s38_d[7] = (s38_r[0] >= 32'd34);
    assign s38_r[1] = s38_d[7] ? (s38_r[0] - 32'd34) : s38_r[0];
    always @(posedge clk) begin
      r[39] <= s38_r[1];
      d[39] <= d[38] | (s38_d & 46'd128);
    end
    wire [31:0] s39_r [0:1];
    wire [45:0] s39_d;
    assign s39_r[0] = r[39];
    assign s39_d[6] = (s39_r[0] >= 32'd21);
    assign s39_r[1] = s39_d[6] ? (s39_r[0] - 32'd21) : s39_r[0];
    always @(posedge clk) begin
      r[40] <= s39_r[1];
      d[40] <= d[39] | (s39_d & 46'd64);
    end
    wire [31:0] s40_r [0:1];
    wire [45:0] s40_d;
    assign s40_r[0] = r[40];
    assign s40_d[5] = (s40_r[0] >= 32'd13);
    assign s40_r[1] = s40_d[5] ? (s40_r[0] - 32'd13) : s40_r[0];
    always @(posedge clk) begin
      r[41] <= s40_r[1];
      d[41] <= d[40] | (s40_d & 46'd32);
    end
    wire [31:0] s41_r [0:1];
    wire [45:0] s41_d;
    assign s41_r[0] = r[41];
    assign s41_d[4] = (s41_r[0] >= 32'd8);
    assign s41_r[1] = s41_d[4] ? (s41_r[0] - 32'd8) : s41_r[0];
    always @(posedge clk) begin
      r[42] <= s41_r[1];
      d[42] <= d[41] | (s41_d & 46'd16);
    end
    wire [31:0] s42_r [0:1];
    wire [45:0] s42_d;
    assign s42_r[0] = r[42];
    assign s42_d[3] = (s42_r[0] >= 32'd5);
    assign s42_r[1] = s42_d[3] ? (s42_r[0] - 32'd5) : s42_r[0];
    always @(posedge clk) begin
      r[43] <= s42_r[1];
      d[43] <= d[42] | (s42_d & 46'd8);
    end
    wire [31:0] s43_r [0:1];
    wire [45:0] s43_d;
    assign s43_r[0] = r[43];
    assign s43_d[2] = (s43_r[0] >= 32'd3);
    assign s43_r[1] = s43_d[2] ? (s43_r[0] - 32'd3) : s43_r[0];
    always @(posedge clk) begin
      r[44] <= s43_r[1];
      d[44] <= d[43] | (s43_d & 46'd4);
    end
    wire [31:0] s44_r [0:1];
    wire [45:0] s44_d;
    assign s44_r[0] = r[44];
    assign s44_d[1] = (s44_r[0] >= 32'd2);
    assign s44_r[1] = s44_d[1] ? (s44_r[0] - 32'd2) : s44_r[0];
    always @(posedge clk) begin
      r[45] <= s44_r[1];
      d[45] <= d[44] | (s44_d & 46'd2);
    end
    wire [31:0] s45_r [0:1];
    wire [45:0] s45_d;
    assign s45_r[0] = r[45];
    assign s45_d[0] = (s45_r[0] >= 32'd1);
    assign s45_r[1] = s45_d[0] ? (s45_r[0] - 32'd1) : s45_r[0];
    always @(posedge clk) begin
      r[46] <= s45_r[1];
      d[46] <= d[45] | (s45_d & 46'd1);
    end
    always @(posedge clk) begin r[47] <= r[46]; d[47] <= d[46]; end
    always @(posedge clk) begin r[48] <= r[47]; d[48] <= d[47]; end
    always @(posedge clk) begin r[49] <= r[48]; d[49] <= d[48]; end
    always @(posedge clk) begin r[50] <= r[49]; d[50] <= d[49]; end
    always @(posedge clk) begin r[51] <= r[50]; d[51] <= d[50]; end
    always @(posedge clk) begin r[52] <= r[51]; d[52] <= d[51]; end
    always @(posedge clk) begin r[53] <= r[52]; d[53] <= d[52]; end
    always @(posedge clk) begin r[54] <= r[53]; d[54] <= d[53]; end
    always @(posedge clk) begin r[55] <= r[54]; d[55] <= d[54]; end
    always @(posedge clk) begin r[56] <= r[55]; d[56] <= d[55]; end
    always @(posedge clk) begin r[57] <= r[56]; d[57] <= d[56]; end
    always @(posedge clk) begin r[58] <= r[57]; d[58] <= d[57]; end
    always @(posedge clk) begin r[59] <= r[58]; d[59] <= d[58]; end
    always @(posedge clk) begin r[60] <= r[59]; d[60] <= d[59]; end
    always @(posedge clk) begin r[61] <= r[60]; d[61] <= d[60]; end
    always @(posedge clk) begin r[62] <= r[61]; d[62] <= d[61]; end
    always @(posedge clk) begin r[63] <= r[62]; d[63] <= d[62]; end
    always @(posedge clk) begin r[64] <= r[63]; d[64] <= d[63]; end
    assign z = d[64];
endmodule

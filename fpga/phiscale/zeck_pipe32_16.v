// Zeckendorf normaliser, 16-stage pipeline (3 compare-subtracts per stage).
// Stages past the last Fibonacci index pass their registers through, so the
// depth can exceed the number of compare-subtracts without leaving the
// output undriven -- which is how the first generator produced a design
// whose top digits had no driver.
`default_nettype none
module zeck_pipe32_16 (input wire clk, input wire [31:0] x, output wire [45:0] z);
    reg  [31:0] r [0:16];
    reg  [45:0] d [0:16];
    always @(posedge clk) begin r[0] <= x; d[0] <= 0; end
    wire [31:0] s0_r [0:3];
    wire [45:0] s0_d;
    assign s0_r[0] = r[0];
    assign s0_d[45] = (s0_r[0] >= 32'd2971215073);
    assign s0_r[1] = s0_d[45] ? (s0_r[0] - 32'd2971215073) : s0_r[0];
    assign s0_d[44] = (s0_r[1] >= 32'd1836311903);
    assign s0_r[2] = s0_d[44] ? (s0_r[1] - 32'd1836311903) : s0_r[1];
    assign s0_d[43] = (s0_r[2] >= 32'd1134903170);
    assign s0_r[3] = s0_d[43] ? (s0_r[2] - 32'd1134903170) : s0_r[2];
    always @(posedge clk) begin
      r[1] <= s0_r[3];
      d[1] <= d[0] | (s0_d & 46'd61572651155456);
    end
    wire [31:0] s1_r [0:3];
    wire [45:0] s1_d;
    assign s1_r[0] = r[1];
    assign s1_d[42] = (s1_r[0] >= 32'd701408733);
    assign s1_r[1] = s1_d[42] ? (s1_r[0] - 32'd701408733) : s1_r[0];
    assign s1_d[41] = (s1_r[1] >= 32'd433494437);
    assign s1_r[2] = s1_d[41] ? (s1_r[1] - 32'd433494437) : s1_r[1];
    assign s1_d[40] = (s1_r[2] >= 32'd267914296);
    assign s1_r[3] = s1_d[40] ? (s1_r[2] - 32'd267914296) : s1_r[2];
    always @(posedge clk) begin
      r[2] <= s1_r[3];
      d[2] <= d[1] | (s1_d & 46'd7696581394432);
    end
    wire [31:0] s2_r [0:3];
    wire [45:0] s2_d;
    assign s2_r[0] = r[2];
    assign s2_d[39] = (s2_r[0] >= 32'd165580141);
    assign s2_r[1] = s2_d[39] ? (s2_r[0] - 32'd165580141) : s2_r[0];
    assign s2_d[38] = (s2_r[1] >= 32'd102334155);
    assign s2_r[2] = s2_d[38] ? (s2_r[1] - 32'd102334155) : s2_r[1];
    assign s2_d[37] = (s2_r[2] >= 32'd63245986);
    assign s2_r[3] = s2_d[37] ? (s2_r[2] - 32'd63245986) : s2_r[2];
    always @(posedge clk) begin
      r[3] <= s2_r[3];
      d[3] <= d[2] | (s2_d & 46'd962072674304);
    end
    wire [31:0] s3_r [0:3];
    wire [45:0] s3_d;
    assign s3_r[0] = r[3];
    assign s3_d[36] = (s3_r[0] >= 32'd39088169);
    assign s3_r[1] = s3_d[36] ? (s3_r[0] - 32'd39088169) : s3_r[0];
    assign s3_d[35] = (s3_r[1] >= 32'd24157817);
    assign s3_r[2] = s3_d[35] ? (s3_r[1] - 32'd24157817) : s3_r[1];
    assign s3_d[34] = (s3_r[2] >= 32'd14930352);
    assign s3_r[3] = s3_d[34] ? (s3_r[2] - 32'd14930352) : s3_r[2];
    always @(posedge clk) begin
      r[4] <= s3_r[3];
      d[4] <= d[3] | (s3_d & 46'd120259084288);
    end
    wire [31:0] s4_r [0:3];
    wire [45:0] s4_d;
    assign s4_r[0] = r[4];
    assign s4_d[33] = (s4_r[0] >= 32'd9227465);
    assign s4_r[1] = s4_d[33] ? (s4_r[0] - 32'd9227465) : s4_r[0];
    assign s4_d[32] = (s4_r[1] >= 32'd5702887);
    assign s4_r[2] = s4_d[32] ? (s4_r[1] - 32'd5702887) : s4_r[1];
    assign s4_d[31] = (s4_r[2] >= 32'd3524578);
    assign s4_r[3] = s4_d[31] ? (s4_r[2] - 32'd3524578) : s4_r[2];
    always @(posedge clk) begin
      r[5] <= s4_r[3];
      d[5] <= d[4] | (s4_d & 46'd15032385536);
    end
    wire [31:0] s5_r [0:3];
    wire [45:0] s5_d;
    assign s5_r[0] = r[5];
    assign s5_d[30] = (s5_r[0] >= 32'd2178309);
    assign s5_r[1] = s5_d[30] ? (s5_r[0] - 32'd2178309) : s5_r[0];
    assign s5_d[29] = (s5_r[1] >= 32'd1346269);
    assign s5_r[2] = s5_d[29] ? (s5_r[1] - 32'd1346269) : s5_r[1];
    assign s5_d[28] = (s5_r[2] >= 32'd832040);
    assign s5_r[3] = s5_d[28] ? (s5_r[2] - 32'd832040) : s5_r[2];
    always @(posedge clk) begin
      r[6] <= s5_r[3];
      d[6] <= d[5] | (s5_d & 46'd1879048192);
    end
    wire [31:0] s6_r [0:3];
    wire [45:0] s6_d;
    assign s6_r[0] = r[6];
    assign s6_d[27] = (s6_r[0] >= 32'd514229);
    assign s6_r[1] = s6_d[27] ? (s6_r[0] - 32'd514229) : s6_r[0];
    assign s6_d[26] = (s6_r[1] >= 32'd317811);
    assign s6_r[2] = s6_d[26] ? (s6_r[1] - 32'd317811) : s6_r[1];
    assign s6_d[25] = (s6_r[2] >= 32'd196418);
    assign s6_r[3] = s6_d[25] ? (s6_r[2] - 32'd196418) : s6_r[2];
    always @(posedge clk) begin
      r[7] <= s6_r[3];
      d[7] <= d[6] | (s6_d & 46'd234881024);
    end
    wire [31:0] s7_r [0:3];
    wire [45:0] s7_d;
    assign s7_r[0] = r[7];
    assign s7_d[24] = (s7_r[0] >= 32'd121393);
    assign s7_r[1] = s7_d[24] ? (s7_r[0] - 32'd121393) : s7_r[0];
    assign s7_d[23] = (s7_r[1] >= 32'd75025);
    assign s7_r[2] = s7_d[23] ? (s7_r[1] - 32'd75025) : s7_r[1];
    assign s7_d[22] = (s7_r[2] >= 32'd46368);
    assign s7_r[3] = s7_d[22] ? (s7_r[2] - 32'd46368) : s7_r[2];
    always @(posedge clk) begin
      r[8] <= s7_r[3];
      d[8] <= d[7] | (s7_d & 46'd29360128);
    end
    wire [31:0] s8_r [0:3];
    wire [45:0] s8_d;
    assign s8_r[0] = r[8];
    assign s8_d[21] = (s8_r[0] >= 32'd28657);
    assign s8_r[1] = s8_d[21] ? (s8_r[0] - 32'd28657) : s8_r[0];
    assign s8_d[20] = (s8_r[1] >= 32'd17711);
    assign s8_r[2] = s8_d[20] ? (s8_r[1] - 32'd17711) : s8_r[1];
    assign s8_d[19] = (s8_r[2] >= 32'd10946);
    assign s8_r[3] = s8_d[19] ? (s8_r[2] - 32'd10946) : s8_r[2];
    always @(posedge clk) begin
      r[9] <= s8_r[3];
      d[9] <= d[8] | (s8_d & 46'd3670016);
    end
    wire [31:0] s9_r [0:3];
    wire [45:0] s9_d;
    assign s9_r[0] = r[9];
    assign s9_d[18] = (s9_r[0] >= 32'd6765);
    assign s9_r[1] = s9_d[18] ? (s9_r[0] - 32'd6765) : s9_r[0];
    assign s9_d[17] = (s9_r[1] >= 32'd4181);
    assign s9_r[2] = s9_d[17] ? (s9_r[1] - 32'd4181) : s9_r[1];
    assign s9_d[16] = (s9_r[2] >= 32'd2584);
    assign s9_r[3] = s9_d[16] ? (s9_r[2] - 32'd2584) : s9_r[2];
    always @(posedge clk) begin
      r[10] <= s9_r[3];
      d[10] <= d[9] | (s9_d & 46'd458752);
    end
    wire [31:0] s10_r [0:3];
    wire [45:0] s10_d;
    assign s10_r[0] = r[10];
    assign s10_d[15] = (s10_r[0] >= 32'd1597);
    assign s10_r[1] = s10_d[15] ? (s10_r[0] - 32'd1597) : s10_r[0];
    assign s10_d[14] = (s10_r[1] >= 32'd987);
    assign s10_r[2] = s10_d[14] ? (s10_r[1] - 32'd987) : s10_r[1];
    assign s10_d[13] = (s10_r[2] >= 32'd610);
    assign s10_r[3] = s10_d[13] ? (s10_r[2] - 32'd610) : s10_r[2];
    always @(posedge clk) begin
      r[11] <= s10_r[3];
      d[11] <= d[10] | (s10_d & 46'd57344);
    end
    wire [31:0] s11_r [0:3];
    wire [45:0] s11_d;
    assign s11_r[0] = r[11];
    assign s11_d[12] = (s11_r[0] >= 32'd377);
    assign s11_r[1] = s11_d[12] ? (s11_r[0] - 32'd377) : s11_r[0];
    assign s11_d[11] = (s11_r[1] >= 32'd233);
    assign s11_r[2] = s11_d[11] ? (s11_r[1] - 32'd233) : s11_r[1];
    assign s11_d[10] = (s11_r[2] >= 32'd144);
    assign s11_r[3] = s11_d[10] ? (s11_r[2] - 32'd144) : s11_r[2];
    always @(posedge clk) begin
      r[12] <= s11_r[3];
      d[12] <= d[11] | (s11_d & 46'd7168);
    end
    wire [31:0] s12_r [0:3];
    wire [45:0] s12_d;
    assign s12_r[0] = r[12];
    assign s12_d[9] = (s12_r[0] >= 32'd89);
    assign s12_r[1] = s12_d[9] ? (s12_r[0] - 32'd89) : s12_r[0];
    assign s12_d[8] = (s12_r[1] >= 32'd55);
    assign s12_r[2] = s12_d[8] ? (s12_r[1] - 32'd55) : s12_r[1];
    assign s12_d[7] = (s12_r[2] >= 32'd34);
    assign s12_r[3] = s12_d[7] ? (s12_r[2] - 32'd34) : s12_r[2];
    always @(posedge clk) begin
      r[13] <= s12_r[3];
      d[13] <= d[12] | (s12_d & 46'd896);
    end
    wire [31:0] s13_r [0:3];
    wire [45:0] s13_d;
    assign s13_r[0] = r[13];
    assign s13_d[6] = (s13_r[0] >= 32'd21);
    assign s13_r[1] = s13_d[6] ? (s13_r[0] - 32'd21) : s13_r[0];
    assign s13_d[5] = (s13_r[1] >= 32'd13);
    assign s13_r[2] = s13_d[5] ? (s13_r[1] - 32'd13) : s13_r[1];
    assign s13_d[4] = (s13_r[2] >= 32'd8);
    assign s13_r[3] = s13_d[4] ? (s13_r[2] - 32'd8) : s13_r[2];
    always @(posedge clk) begin
      r[14] <= s13_r[3];
      d[14] <= d[13] | (s13_d & 46'd112);
    end
    wire [31:0] s14_r [0:3];
    wire [45:0] s14_d;
    assign s14_r[0] = r[14];
    assign s14_d[3] = (s14_r[0] >= 32'd5);
    assign s14_r[1] = s14_d[3] ? (s14_r[0] - 32'd5) : s14_r[0];
    assign s14_d[2] = (s14_r[1] >= 32'd3);
    assign s14_r[2] = s14_d[2] ? (s14_r[1] - 32'd3) : s14_r[1];
    assign s14_d[1] = (s14_r[2] >= 32'd2);
    assign s14_r[3] = s14_d[1] ? (s14_r[2] - 32'd2) : s14_r[2];
    always @(posedge clk) begin
      r[15] <= s14_r[3];
      d[15] <= d[14] | (s14_d & 46'd14);
    end
    wire [31:0] s15_r [0:1];
    wire [45:0] s15_d;
    assign s15_r[0] = r[15];
    assign s15_d[0] = (s15_r[0] >= 32'd1);
    assign s15_r[1] = s15_d[0] ? (s15_r[0] - 32'd1) : s15_r[0];
    always @(posedge clk) begin
      r[16] <= s15_r[1];
      d[16] <= d[15] | (s15_d & 46'd1);
    end
    assign z = d[16];
endmodule

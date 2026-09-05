// Zeckendorf re-encoder -- the transformation stage that non-closure forces.
//
// A product of Fibonacci integers is not in general a Fibonacci integer
// (F4*F4 = 9), so it leaves the representable set and must be returned to it.
// This is the greedy re-encoding: for each Fibonacci number from the top,
// subtract it if it fits. It is the straightforward transformation, not the
// cheapest conceivable one; what the corollary claims is that SOME stage is
// needed, and the closed path needs none at all.
//
// W=32: 46 Fibonacci numbers below 2^32, hence 46 compare-subtract stages.
`default_nettype none
module zeck_reenc32 (
    input  wire            clk,
    input  wire [31:0]  x,
    output reg  [45:0]  z      // Zeckendorf digits, no two adjacent
);
    wire [31:0] r [0:46];
    wire [45:0] d;
    assign r[0] = x;
    assign d[45] = (r[0] >= 32'd2971215073);
    assign r[1] = d[45] ? (r[0] - 32'd2971215073) : r[0];
    assign d[44] = (r[1] >= 32'd1836311903);
    assign r[2] = d[44] ? (r[1] - 32'd1836311903) : r[1];
    assign d[43] = (r[2] >= 32'd1134903170);
    assign r[3] = d[43] ? (r[2] - 32'd1134903170) : r[2];
    assign d[42] = (r[3] >= 32'd701408733);
    assign r[4] = d[42] ? (r[3] - 32'd701408733) : r[3];
    assign d[41] = (r[4] >= 32'd433494437);
    assign r[5] = d[41] ? (r[4] - 32'd433494437) : r[4];
    assign d[40] = (r[5] >= 32'd267914296);
    assign r[6] = d[40] ? (r[5] - 32'd267914296) : r[5];
    assign d[39] = (r[6] >= 32'd165580141);
    assign r[7] = d[39] ? (r[6] - 32'd165580141) : r[6];
    assign d[38] = (r[7] >= 32'd102334155);
    assign r[8] = d[38] ? (r[7] - 32'd102334155) : r[7];
    assign d[37] = (r[8] >= 32'd63245986);
    assign r[9] = d[37] ? (r[8] - 32'd63245986) : r[8];
    assign d[36] = (r[9] >= 32'd39088169);
    assign r[10] = d[36] ? (r[9] - 32'd39088169) : r[9];
    assign d[35] = (r[10] >= 32'd24157817);
    assign r[11] = d[35] ? (r[10] - 32'd24157817) : r[10];
    assign d[34] = (r[11] >= 32'd14930352);
    assign r[12] = d[34] ? (r[11] - 32'd14930352) : r[11];
    assign d[33] = (r[12] >= 32'd9227465);
    assign r[13] = d[33] ? (r[12] - 32'd9227465) : r[12];
    assign d[32] = (r[13] >= 32'd5702887);
    assign r[14] = d[32] ? (r[13] - 32'd5702887) : r[13];
    assign d[31] = (r[14] >= 32'd3524578);
    assign r[15] = d[31] ? (r[14] - 32'd3524578) : r[14];
    assign d[30] = (r[15] >= 32'd2178309);
    assign r[16] = d[30] ? (r[15] - 32'd2178309) : r[15];
    assign d[29] = (r[16] >= 32'd1346269);
    assign r[17] = d[29] ? (r[16] - 32'd1346269) : r[16];
    assign d[28] = (r[17] >= 32'd832040);
    assign r[18] = d[28] ? (r[17] - 32'd832040) : r[17];
    assign d[27] = (r[18] >= 32'd514229);
    assign r[19] = d[27] ? (r[18] - 32'd514229) : r[18];
    assign d[26] = (r[19] >= 32'd317811);
    assign r[20] = d[26] ? (r[19] - 32'd317811) : r[19];
    assign d[25] = (r[20] >= 32'd196418);
    assign r[21] = d[25] ? (r[20] - 32'd196418) : r[20];
    assign d[24] = (r[21] >= 32'd121393);
    assign r[22] = d[24] ? (r[21] - 32'd121393) : r[21];
    assign d[23] = (r[22] >= 32'd75025);
    assign r[23] = d[23] ? (r[22] - 32'd75025) : r[22];
    assign d[22] = (r[23] >= 32'd46368);
    assign r[24] = d[22] ? (r[23] - 32'd46368) : r[23];
    assign d[21] = (r[24] >= 32'd28657);
    assign r[25] = d[21] ? (r[24] - 32'd28657) : r[24];
    assign d[20] = (r[25] >= 32'd17711);
    assign r[26] = d[20] ? (r[25] - 32'd17711) : r[25];
    assign d[19] = (r[26] >= 32'd10946);
    assign r[27] = d[19] ? (r[26] - 32'd10946) : r[26];
    assign d[18] = (r[27] >= 32'd6765);
    assign r[28] = d[18] ? (r[27] - 32'd6765) : r[27];
    assign d[17] = (r[28] >= 32'd4181);
    assign r[29] = d[17] ? (r[28] - 32'd4181) : r[28];
    assign d[16] = (r[29] >= 32'd2584);
    assign r[30] = d[16] ? (r[29] - 32'd2584) : r[29];
    assign d[15] = (r[30] >= 32'd1597);
    assign r[31] = d[15] ? (r[30] - 32'd1597) : r[30];
    assign d[14] = (r[31] >= 32'd987);
    assign r[32] = d[14] ? (r[31] - 32'd987) : r[31];
    assign d[13] = (r[32] >= 32'd610);
    assign r[33] = d[13] ? (r[32] - 32'd610) : r[32];
    assign d[12] = (r[33] >= 32'd377);
    assign r[34] = d[12] ? (r[33] - 32'd377) : r[33];
    assign d[11] = (r[34] >= 32'd233);
    assign r[35] = d[11] ? (r[34] - 32'd233) : r[34];
    assign d[10] = (r[35] >= 32'd144);
    assign r[36] = d[10] ? (r[35] - 32'd144) : r[35];
    assign d[9] = (r[36] >= 32'd89);
    assign r[37] = d[9] ? (r[36] - 32'd89) : r[36];
    assign d[8] = (r[37] >= 32'd55);
    assign r[38] = d[8] ? (r[37] - 32'd55) : r[37];
    assign d[7] = (r[38] >= 32'd34);
    assign r[39] = d[7] ? (r[38] - 32'd34) : r[38];
    assign d[6] = (r[39] >= 32'd21);
    assign r[40] = d[6] ? (r[39] - 32'd21) : r[39];
    assign d[5] = (r[40] >= 32'd13);
    assign r[41] = d[5] ? (r[40] - 32'd13) : r[40];
    assign d[4] = (r[41] >= 32'd8);
    assign r[42] = d[4] ? (r[41] - 32'd8) : r[41];
    assign d[3] = (r[42] >= 32'd5);
    assign r[43] = d[3] ? (r[42] - 32'd5) : r[42];
    assign d[2] = (r[43] >= 32'd3);
    assign r[44] = d[2] ? (r[43] - 32'd3) : r[43];
    assign d[1] = (r[44] >= 32'd2);
    assign r[45] = d[1] ? (r[44] - 32'd2) : r[44];
    assign d[0] = (r[45] >= 32'd1);
    assign r[46] = d[0] ? (r[45] - 32'd1) : r[45];
    always @(posedge clk) z <= d;
endmodule

// Zeckendorf re-encoder -- the transformation stage that non-closure forces.
//
// A product of Fibonacci integers is not in general a Fibonacci integer
// (F4*F4 = 9), so it leaves the representable set and must be returned to it.
// This is the greedy re-encoding: for each Fibonacci number from the top,
// subtract it if it fits. It is the straightforward transformation, not the
// cheapest conceivable one; what the corollary claims is that SOME stage is
// needed, and the closed path needs none at all.
//
// W=16: 23 Fibonacci numbers below 2^16, hence 23 compare-subtract stages.
`default_nettype none
module zeck_reenc16 (
    input  wire            clk,
    input  wire [15:0]  x,
    output reg  [22:0]  z      // Zeckendorf digits, no two adjacent
);
    wire [15:0] r [0:23];
    wire [22:0] d;
    assign r[0] = x;
    assign d[22] = (r[0] >= 16'd46368);
    assign r[1] = d[22] ? (r[0] - 16'd46368) : r[0];
    assign d[21] = (r[1] >= 16'd28657);
    assign r[2] = d[21] ? (r[1] - 16'd28657) : r[1];
    assign d[20] = (r[2] >= 16'd17711);
    assign r[3] = d[20] ? (r[2] - 16'd17711) : r[2];
    assign d[19] = (r[3] >= 16'd10946);
    assign r[4] = d[19] ? (r[3] - 16'd10946) : r[3];
    assign d[18] = (r[4] >= 16'd6765);
    assign r[5] = d[18] ? (r[4] - 16'd6765) : r[4];
    assign d[17] = (r[5] >= 16'd4181);
    assign r[6] = d[17] ? (r[5] - 16'd4181) : r[5];
    assign d[16] = (r[6] >= 16'd2584);
    assign r[7] = d[16] ? (r[6] - 16'd2584) : r[6];
    assign d[15] = (r[7] >= 16'd1597);
    assign r[8] = d[15] ? (r[7] - 16'd1597) : r[7];
    assign d[14] = (r[8] >= 16'd987);
    assign r[9] = d[14] ? (r[8] - 16'd987) : r[8];
    assign d[13] = (r[9] >= 16'd610);
    assign r[10] = d[13] ? (r[9] - 16'd610) : r[9];
    assign d[12] = (r[10] >= 16'd377);
    assign r[11] = d[12] ? (r[10] - 16'd377) : r[10];
    assign d[11] = (r[11] >= 16'd233);
    assign r[12] = d[11] ? (r[11] - 16'd233) : r[11];
    assign d[10] = (r[12] >= 16'd144);
    assign r[13] = d[10] ? (r[12] - 16'd144) : r[12];
    assign d[9] = (r[13] >= 16'd89);
    assign r[14] = d[9] ? (r[13] - 16'd89) : r[13];
    assign d[8] = (r[14] >= 16'd55);
    assign r[15] = d[8] ? (r[14] - 16'd55) : r[14];
    assign d[7] = (r[15] >= 16'd34);
    assign r[16] = d[7] ? (r[15] - 16'd34) : r[15];
    assign d[6] = (r[16] >= 16'd21);
    assign r[17] = d[6] ? (r[16] - 16'd21) : r[16];
    assign d[5] = (r[17] >= 16'd13);
    assign r[18] = d[5] ? (r[17] - 16'd13) : r[17];
    assign d[4] = (r[18] >= 16'd8);
    assign r[19] = d[4] ? (r[18] - 16'd8) : r[18];
    assign d[3] = (r[19] >= 16'd5);
    assign r[20] = d[3] ? (r[19] - 16'd5) : r[19];
    assign d[2] = (r[20] >= 16'd3);
    assign r[21] = d[2] ? (r[20] - 16'd3) : r[20];
    assign d[1] = (r[21] >= 16'd2);
    assign r[22] = d[1] ? (r[21] - 16'd2) : r[21];
    assign d[0] = (r[22] >= 16'd1);
    assign r[23] = d[0] ? (r[22] - 16'd1) : r[22];
    always @(posedge clk) z <= d;
endmodule

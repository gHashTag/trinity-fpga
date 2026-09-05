// The same two lanes written so the tool can specialise them.
//
// mac_lane.v describes decode-then-multiply, which is what an RTL author writes
// and what yosys then builds: a general WW x 8 multiplier fed by a decoded
// operand. But the operand is one of eight values known at design time, so the
// "multiplier" is really a set of eight CONSTANT multiplications sharing partial
// results -- an MCM problem. Charging the arbitrary codebook for a general
// multiplier when a specialised datapath exists would overstate its cost, and
// the objection "you did not optimise it" would be fair.
//
// So both formats also get this form: select the PRODUCT, not the weight. The
// constants are written as literals and yosys shares subexpressions across the
// case arms. Neither format is hand-tuned; both get the same treatment.
//
// Prediction to hold the numbers against (csd.py): E2M1's eight magnitudes have
// only two distinct odd parts, 1 and 3, so the whole set needs ONE adder. The
// B=10 codebook has seven, so it needs SIX.
`default_nettype none

module mcm_lane_mxfp4 #(parameter integer AW = 8, parameter integer ACC = 32)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [3:0]            code,
    input  wire signed [AW-1:0]  a,
    output reg  signed [ACC-1:0] acc
);
    reg signed [AW+4:0] pm;
    always @(*) case (code[2:0])            // magnitudes in units of 0.5
      3'd0: pm = 0;      3'd1: pm =  1 * a;
      3'd2: pm =  2 * a; 3'd3: pm =  3 * a;
      3'd4: pm =  4 * a; 3'd5: pm =  6 * a;
      3'd6: pm =  8 * a; 3'd7: pm = 12 * a;
    endcase
    wire signed [AW+4:0] p = code[3] ? -pm : pm;
    always @(posedge clk)
        acc <= !rst_n ? {ACC{1'b0}} : acc + {{(ACC-AW-5){p[AW+4]}}, p};
endmodule

module mcm_lane_cb10 #(parameter integer AW = 8, parameter integer ACC = 32)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [3:0]            code,
    input  wire signed [AW-1:0]  a,
    output reg  signed [ACC-1:0] acc
);
    reg signed [AW+11:0] pm;
    always @(*) case (code[2:0])            // magnitudes in units of 2^-10
      3'd0: pm =    0;       3'd1: pm =   79 * a;
      3'd2: pm =  193 * a;   3'd3: pm =  321 * a;
      3'd4: pm =  477 * a;   3'd5: pm =  626 * a;
      3'd6: pm =  810 * a;   3'd7: pm = 1024 * a;
    endcase
    wire signed [AW+11:0] p = code[3] ? -pm : pm;
    always @(posedge clk)
        acc <= !rst_n ? {ACC{1'b0}} : acc + {{(ACC-AW-12){p[AW+11]}}, p};
endmodule
`default_nettype wire

// B=6 -- the width the perplexity gate actually selects. Magnitudes in units of
// 2^-6: 0, 5, 12, 20, 30, 39, 51, 64. Six distinct odd parts (1,3,5,15,39,51),
// so csd.py predicts FIVE shared adders against E2M1's one.
`default_nettype none
module mcm_lane_cb6 #(parameter integer AW = 8, parameter integer ACC = 32)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [3:0]            code,
    input  wire signed [AW-1:0]  a,
    output reg  signed [ACC-1:0] acc
);
    reg signed [AW+7:0] pm;
    always @(*) case (code[2:0])
      3'd0: pm =  0;       3'd1: pm =  5 * a;
      3'd2: pm = 12 * a;   3'd3: pm = 20 * a;
      3'd4: pm = 30 * a;   3'd5: pm = 39 * a;
      3'd6: pm = 51 * a;   3'd7: pm = 64 * a;
    endcase
    wire signed [AW+7:0] p = code[3] ? -pm : pm;
    always @(posedge clk)
        acc <= !rst_n ? {ACC{1'b0}} : acc + {{(ACC-AW-8){p[AW+7]}}, p};
endmodule
`default_nettype wire

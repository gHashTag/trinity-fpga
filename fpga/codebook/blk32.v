// A whole 32-element MX block, both element formats, plus the raw-weight
// reference -- so the amortisation question is answered by measurement.
//
// The question is whether an 8-entry table is "shared across the block". A
// combinational table is NOT a memory: a unit that decodes 32 elements in the
// same cycle instantiates 32 copies of it, and nothing is shared. What is shared
// is the E8M0 alignment, which enters once per block. These three tops make that
// countable: if the table were shared, blk32 would cost one decoder more than
// the raw reference; if it is replicated, it costs thirty-two.
`default_nettype none

module blk32_mxfp4 #(parameter integer AW = 8, parameter integer ACC = 32,
                     parameter integer OUT = 40)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [127:0]          codes,   // 32 x 4-bit elements
    input  wire [32*AW-1:0]      acts,
    input  wire [7:0]            e8m0,
    input  wire [7:0]            emax,
    output wire signed [OUT-1:0] y
);
    wire signed [ACC-1:0] t [0:62];
    genvar i, k;
    generate
      for (i = 0; i < 32; i = i + 1) begin : lane
        wire signed [4:0]  wv;
        mxfp4_decode d (.code(codes[i*4 +: 4]), .w(wv));
        wire signed [AW-1:0] av = acts[i*AW +: AW];
        wire signed [4+AW:0] p  = wv * av;
        assign t[i] = {{(ACC-5-AW){p[4+AW]}}, p};
      end
      for (k = 0; k < 31; k = k + 1) begin : tn
        assign t[32+k] = t[2*k] + t[2*k+1];
      end
    endgenerate
    reg signed [ACC-1:0] blk;
    always @(posedge clk) blk <= !rst_n ? {ACC{1'b0}} : t[62];
    blk_scale #(.ACC(ACC), .OUT(OUT)) sc
      (.clk(clk), .rst_n(rst_n), .blk(blk), .e8m0(e8m0), .emax(emax), .y(y));
endmodule

module blk32_cb #(parameter integer WW = 12, parameter integer AW = 8,
                  parameter integer ACC = 32, parameter integer OUT = 40)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [127:0]          codes,
    input  wire [32*AW-1:0]      acts,
    input  wire [7:0]            e8m0,
    input  wire [7:0]            emax,
    output wire signed [OUT-1:0] y
);
    wire signed [ACC-1:0] t [0:62];
    genvar i, k;
    generate
      for (i = 0; i < 32; i = i + 1) begin : lane
        wire signed [WW-1:0] wv;
        cb4_decode_b10 d (.code(codes[i*4 +: 4]), .w(wv));
        wire signed [AW-1:0]    av = acts[i*AW +: AW];
        wire signed [WW+AW-1:0] p  = wv * av;
        assign t[i] = {{(ACC-WW-AW){p[WW+AW-1]}}, p};
      end
      for (k = 0; k < 31; k = k + 1) begin : tn
        assign t[32+k] = t[2*k] + t[2*k+1];
      end
    endgenerate
    reg signed [ACC-1:0] blk;
    always @(posedge clk) blk <= !rst_n ? {ACC{1'b0}} : t[62];
    blk_scale #(.ACC(ACC), .OUT(OUT)) sc
      (.clk(clk), .rst_n(rst_n), .blk(blk), .e8m0(e8m0), .emax(emax), .y(y));
endmodule

// The same block with an UNCONSTRAINED WW-bit weight per lane: no codebook, no
// decode. The reference that says what the decode is worth inside a block.
module blk32_raw #(parameter integer WW = 5, parameter integer AW = 8,
                   parameter integer ACC = 32, parameter integer OUT = 40)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire [32*WW-1:0]      ws,
    input  wire [32*AW-1:0]      acts,
    input  wire [7:0]            e8m0,
    input  wire [7:0]            emax,
    output wire signed [OUT-1:0] y
);
    wire signed [ACC-1:0] t [0:62];
    genvar i, k;
    generate
      for (i = 0; i < 32; i = i + 1) begin : lane
        wire signed [WW-1:0]    wv = ws[i*WW +: WW];
        wire signed [AW-1:0]    av = acts[i*AW +: AW];
        wire signed [WW+AW-1:0] p  = wv * av;
        assign t[i] = {{(ACC-WW-AW){p[WW+AW-1]}}, p};
      end
      for (k = 0; k < 31; k = k + 1) begin : tn
        assign t[32+k] = t[2*k] + t[2*k+1];
      end
    endgenerate
    reg signed [ACC-1:0] blk;
    always @(posedge clk) blk <= !rst_n ? {ACC{1'b0}} : t[62];
    blk_scale #(.ACC(ACC), .OUT(OUT)) sc
      (.clk(clk), .rst_n(rst_n), .blk(blk), .e8m0(e8m0), .emax(emax), .y(y));
endmodule
`default_nettype wire

// The B=6 block, the width the perplexity gate selects.
`default_nettype none
module blk32_cb6 #(parameter integer AW = 8, parameter integer ACC = 32,
                   parameter integer OUT = 40)(
    input  wire clk, input wire rst_n,
    input  wire [127:0] codes, input wire [32*AW-1:0] acts,
    input  wire [7:0] e8m0, input wire [7:0] emax,
    output wire signed [OUT-1:0] y
);
    localparam integer WW = 8;
    wire signed [ACC-1:0] t [0:62];
    genvar i, k;
    generate
      for (i = 0; i < 32; i = i + 1) begin : lane
        wire signed [WW-1:0] wv;
        cb4_decode_b6 d (.code(codes[i*4 +: 4]), .w(wv));
        wire signed [AW-1:0]    av = acts[i*AW +: AW];
        wire signed [WW+AW-1:0] p  = wv * av;
        assign t[i] = {{(ACC-WW-AW){p[WW+AW-1]}}, p};
      end
      for (k = 0; k < 31; k = k + 1) begin : tn
        assign t[32+k] = t[2*k] + t[2*k+1];
      end
    endgenerate
    reg signed [ACC-1:0] blk;
    always @(posedge clk) blk <= !rst_n ? {ACC{1'b0}} : t[62];
    blk_scale #(.ACC(ACC), .OUT(OUT)) sc
      (.clk(clk), .rst_n(rst_n), .blk(blk), .e8m0(e8m0), .emax(emax), .y(y));
endmodule
`default_nettype wire

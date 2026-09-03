// A layer whose operands live on the chip, not on the pins.
//
// Every measurement in this directory has fed x and w through the interface,
// which made the pin count grow with fan-in: at N=32 the layer needs 332 input
// bits on a 206-pin package and place-and-route stops -- for BOTH arms, so it
// was never a property of the lattice, only of the harness.
//
// A deployed layer does not receive its weights from outside. They are stored.
// With x and w in on-chip memory the interface is an address and a result, and
// the layer is measurable at any fan-in the fabric holds.
//
// ARM is selected at elaboration so both are the same harness: 0 = the phi
// pipeline with scalar reconstruction, 1 = the multiplier.
`default_nettype none
module tern_layer_mem #(
    parameter integer N     = 32,   // fan-in
    parameter integer W     = 8,    // sample width
    parameter integer ACC   = 16,
    parameter integer KW    = 4,
    parameter integer K_MAX = 8,
    parameter integer SH    = 4,
    parameter integer ROWS  = 16,   // output elements held in memory
    parameter integer ARM   = 0     // 0 = phi, 1 = multiplier
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire [$clog2(ROWS)-1:0] row,     // which output element
    input  wire        [KW-1:0]    k,       // phi arm: the layer exponent
    input  wire signed [15:0]      alpha,   // multiplier arm: Q1.15 scale
    // Narrow load port. Weights and samples are written once, one lane at a
    // time, so the interface does not grow with fan-in.
    input  wire                    ld_en,
    input  wire [$clog2(ROWS)-1:0] ld_row,
    input  wire [$clog2(N)-1:0]    ld_lane,
    input  wire signed [W-1:0]     ld_x,
    input  wire        [1:0]       ld_w,
    input  wire                    ld_commit,
    output wire signed [W-1:0]     y,
    output wire                    out_valid
);
    // Operand memory, one ROW per word.
    //
    // Two failures got here, both of the same shape -- a number far too small
    // or far too large rather than an error.
    //
    // 1. No write port at all: yosys propagated the never-written memory as
    //    constant and pruned the design. The multiplier arm reported 12 logic
    //    cells at fan-in 64 and area stopped growing with N.
    // 2. One memory location PER LANE, read N at a time: that is N read ports,
    //    which synthesises to muxes rather than block RAM. At fan-in 64 it came
    //    to 23052 cells on a 7680-cell part, with zero RAM inferred.
    //
    // A parallel MAC needs the whole row in one cycle, so the row is one word.
    // Lanes are assembled in a register and committed once.
    reg signed [N*W-1:0] xmem [0:ROWS-1];
    reg        [2*N-1:0] wmem [0:ROWS-1];

    reg signed [N*W-1:0] xasm;
    reg        [2*N-1:0] wasm;
    always @(posedge clk) begin
        if (ld_en) begin
            xasm[ld_lane*W +: W] <= ld_x;
            wasm[ld_lane*2 +: 2] <= ld_w;
        end
        if (ld_commit) begin
            xmem[ld_row] <= xasm;
            wmem[ld_row] <= wasm;
        end
    end

    reg signed [N*W-1:0] xr;
    reg        [2*N-1:0] wr;
    reg                  fetched;

    always @(posedge clk) begin
        if (rst) begin
            xr <= {N*W{1'b0}};
            wr <= {2*N{1'b0}};
            fetched <= 1'b0;
        end else begin
            xr <= xmem[row];
            wr <= wmem[row];
            fetched <= start;
        end
    end

    wire signed [ACC-1:0] acc_a, acc_b;
    tern_node #(.N(N), .W(W), .ACC(ACC)) u_mac (
        .clk(clk), .x(xr), .w(wr), .acc_a(acc_a), .acc_b(acc_b));

    generate
        if (ARM == 0) begin : phi_arm
            wire signed [ACC-1:0] sa, sb;
            wire sv;
            scale_phi_pipe #(.ACC(ACC), .KW(KW), .K_MAX(K_MAX)) u_scale (
                .clk(clk), .rst(rst), .in_valid(fetched),
                .acc_a(acc_a), .acc_b(acc_b), .k(k),
                .out_a(sa), .out_b(sb), .out_valid(sv));
            zphi_to_scalar #(.ACC(ACC), .W(W), .SH(SH)) u_out (
                .clk(clk), .rst(rst), .in_valid(sv), .a(sa), .b(sb),
                .y(y), .out_valid(out_valid));
        end else begin : mul_arm
            // Same shape as tern_layer_mul.v: prod is combinational from the
            // registered accumulator, one element per cycle.
            wire signed [ACC+15:0] prod = acc_b * alpha;
            reg signed [W-1:0] yr;
            reg                vr;
            always @(posedge clk) begin
                if (rst) begin yr <= 0; vr <= 1'b0; end
                else begin
                    yr <= prod[ACC+15 -: W];
                    vr <= fetched;
                end
            end
            assign y = yr;
            assign out_valid = vr;
        end
    endgenerate
endmodule

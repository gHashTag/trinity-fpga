// Leave the lattice, once, at the layer boundary.
//
// A Z[phi] value is the pair (a, b) meaning a + b*phi, and carrying the pair is
// what makes the arithmetic exact. It is also what doubles the output width:
// at fan-in 16 the layer needed 217 pins on a 206-pin package and place-and-
// route stopped, with the logic at 10% utilisation.
//
// This reconstructs one number. phi is approximated as 207/128 -- three
// shift-adds, 0.05% off -- and the result is requantised to W bits.
//
// The rounding here is not a loss the lattice was preventing. The layer
// boundary is where a quantised pipeline requantises anyway, to feed the next
// layer's W-bit input; the lattice's job was to keep the ACCUMULATION exact up
// to this point, and it did.
`default_nettype none
module zphi_to_scalar #(
    parameter integer ACC = 16,
    parameter integer W   = 8,
    parameter integer SH  = 4     // output right-shift, the layer's requant
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire signed [ACC-1:0]   a,
    input  wire signed [ACC-1:0]   b,
    output reg  signed [W-1:0]     y,
    output reg                     out_valid
);
    // b * 207 = b*128 + b*64 + b*8 + b*4 + b*2 + b, then >> 7.
    // Written as shifts so no multiplier is inferred on any target.
    //
    // Split across two register stages. The first version summed all six terms
    // and the saturate in ONE combinational block, and it became the layer's
    // critical path: Fmax fell from 204 MHz to 72.57 MHz, which is the whole
    // advantage removed by the stage that was supposed to remove a pin problem.
    // Latency at a layer boundary is free; depth is not.
    wire signed [ACC+8:0] be = {{9{b[ACC-1]}}, b};
    wire signed [ACC+8:0] ae = {{9{a[ACC-1]}}, a};

    reg signed [ACC+8:0] p0, p1, a_d;
    reg                  v_d;
    always @(posedge clk) begin
        if (rst) begin
            p0 <= 0; p1 <= 0; a_d <= 0; v_d <= 1'b0;
        end else begin
            p0  <= (be <<< 7) + (be <<< 6);
            p1  <= (be <<< 3) + (be <<< 2) + (be <<< 1) + be;
            a_d <= ae;
            v_d <= in_valid;
        end
    end

    wire signed [ACC+8:0] sum = a_d + ((p0 + p1) >>> 7);

    localparam signed [ACC+8:0] HI =  (1 <<< (W-1)) - 1;
    localparam signed [ACC+8:0] LO = -(1 <<< (W-1));

    always @(posedge clk) begin
        if (rst) begin
            y <= {W{1'b0}};
            out_valid <= 1'b0;
        end else begin
            // Saturate rather than wrap: a wrapped output is a wrong answer
            // that looks like a plausible one.
            if ((sum >>> SH) > HI)      y <= HI[W-1:0];
            else if ((sum >>> SH) < LO) y <= LO[W-1:0];
            else                        y <= (sum >>> SH);
            out_valid <= v_d;
        end
    end
endmodule

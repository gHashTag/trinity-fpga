// MXFP4 element decode -- the incumbent.
//
// The OCP MX element E2M1 reserves no codes for Inf/NaN, so all eight magnitudes
// are finite: 0, 0.5, 1, 1.5, 2, 3, 4, 6. In units of 0.5 those are the integers
//
//     0, 1, 2, 3, 4, 6, 8, 12
//
// -- exactly four bits and no rounding anywhere. The factor 0.5 is a power of
// two, so it folds into the block's shared E8M0 exponent at no cost, and a
// decoder that emits the integer has emitted the whole value.
//
// The structure is the thing being claimed cheap: for e != 0 the magnitude is
// {1,m} << (e-1), a two-bit operand into a two-stage shifter; for e == 0 it is
// the mantissa bit alone. That is "wiring plus a shift", stated as RTL so it can
// be counted rather than asserted.
`default_nettype none
module mxfp4_decode (
    input  wire        [3:0] code,   // {sign, e[1:0], m}
    output wire signed [4:0] w       // two's complement, units of 0.5
);
    wire       s = code[3];
    wire [1:0] e = code[2:1];
    wire       m = code[0];
    wire [3:0] mag = (e == 2'b00) ? {3'b000, m}
                                  : ({2'b00, 1'b1, m} << (e - 2'b01));
    assign w = s ? -$signed({1'b0, mag}) : $signed({1'b0, mag});
endmodule
`default_nettype wire

// TNF decode at the same 10-bit-class width, for the cost comparison.
// TNF(2,3) is TRUE_LADDER[8]: 1 sign + 4 offset bits + 3 mantissa bits.
// Decode is field slicing plus one subtract: that is what fixed fields buy.
`default_nettype none
module tnf10_decode (
    input  wire [7:0]        raw,       // [sign | off(4) | mant(3)]
    output wire              is_zero,
    output wire              sgn,
    output wire signed [4:0] e,          // off - 4
    output wire [3:0]        sig         // (1 + m/8) * 8 = 8 + m
);
    wire [3:0] off = raw[6:3];
    assign is_zero = (off == 4'd0);
    assign sgn = raw[7];
    assign e = $signed({1'b0, off}) - 5'sd4;
    assign sig = {1'b1, raw[2:0]};
endmodule
`default_nettype wire

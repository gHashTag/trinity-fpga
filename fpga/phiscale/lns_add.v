// An honest LNS adder, built the way an LNS designer would build it.
//
// Our earlier row cited takum32_decode at 10,967 LUT and 84 RAMB36. That is a
// FORMAT DECODER, not an LNS adder, and quoting it against Z[phi] addition was
// the same error we made five times tonight: taking the competitor's number
// from a convenient place instead of building what it would build.
//
// In LNS a value is its logarithm.  Multiplication is exponent addition and is
// free.  Addition is the hard one:
//
//     log2(X + Y) = x + log2(1 + 2^(y-x)),   x >= y
//
// so it needs a table of f(d) = log2(1 + 2^-d) indexed by the exponent
// difference, plus a comparator, a subtractor and a final adder.  A real design
// truncates d: beyond about 2^-F the correction is below the LSB, so the table
// is bounded by the fractional width, not by the whole range.  That is the
// version built here.
module lns_add #(
    parameter integer IW = 5,           // integer part of the log
    parameter integer FW = 10,          // fractional part
    parameter integer TA = 8            // table address bits (truncated d)
)(
    input  wire                     clk,
    input  wire signed [IW+FW:0]    x,      // log2 X
    input  wire signed [IW+FW:0]    y,      // log2 Y
    output reg  signed [IW+FW:0]    s       // log2 (X + Y)
);
    localparam integer W = IW + FW + 1;
    reg [FW-1:0] tab [0:(1<<TA)-1];
    integer i;
    real d, v;
    initial for (i = 0; i < (1<<TA); i = i + 1) begin
        d = i * (1.0 / (1 << (TA - IW)));                 // exponent difference
        v = $ln(1.0 + $pow(2.0, -d)) / $ln(2.0);          // log2(1 + 2^-d)
        tab[i] = v * (1 << FW);
    end

    wire signed [W-1:0] hi   = (x >= y) ? x : y;
    wire signed [W-1:0] lo   = (x >= y) ? y : x;
    wire signed [W-1:0] diff = hi - lo;
    wire [TA-1:0] addr = (diff >= (1 << TA)) ? {TA{1'b1}} : diff[TA-1:0];
    wire [FW-1:0] corr = tab[addr];

    always @(posedge clk) s <= hi + {{(W-FW){1'b0}}, corr};
endmodule

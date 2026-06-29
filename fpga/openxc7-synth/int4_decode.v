// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/int4_decode.v
// INT4 signed -> INT32 sign-extension decode.
// Two's complement 4-bit: range [-8, +7].

`default_nettype none

module int4_decode (
    input  wire [3:0]  int4_in,
    output wire [31:0] int32_out,
    output wire        is_zero
);

    assign is_zero  = (int4_in == 4'd0);
    assign int32_out = {{28{int4_in[3]}}, int4_in};

endmodule

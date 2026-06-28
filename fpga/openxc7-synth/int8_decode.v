// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/int8_decode.v
// INT8 (signed 2's complement) -> 32-bit sign-extended output.

`default_nettype none

module int8_decode (
    input  wire [7:0]  int8_in,
    output wire [31:0] int32_out,
    output wire        is_zero
);

    assign int32_out = {{24{int8_in[7]}}, int8_in};
    assign is_zero   = (int8_in == 8'd0);

endmodule

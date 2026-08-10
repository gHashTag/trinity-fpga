// SPDX-License-Identifier: Apache-2.0
// binary32_decode — IEEE 754 binary32 (FP32) -> FP32 identity decode.
// binary32 IS FP32, so decode = passthrough (no arithmetic). This cell exercises
// the new 32-bit decode frame (4 code bytes) and proves the pipeline for the
// entire 32-bit-format column (posit32, int32, ibm_hfp32, etc.).
`default_nettype none
`timescale 1ns / 1ps

module binary32_decode (
    input  wire [31:0] binary32_in,
    output wire [31:0] fp32_out,
    output wire        is_zero
);

    assign fp32_out = binary32_in;  // identity: binary32 == FP32
    assign is_zero  = (binary32_in == 32'h00000000);

endmodule

`default_nettype wire

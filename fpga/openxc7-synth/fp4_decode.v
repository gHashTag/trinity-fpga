// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/fp4_decode.v
// FP4 E2M1 -> FP32 decode. 16-entry LUT per OCP MX spec.
// Format: 1 sign + 2 exp (bias=1) + 1 mantissa. No NaN, no Inf.

`default_nettype none

module fp4_decode (
    input  wire [3:0]  fp4_in,
    output reg  [31:0] fp32_out
);

    always @(*) begin
        case (fp4_in)
            4'h0: fp32_out = 32'h00000000;  // +0.0
            4'h1: fp32_out = 32'h3F000000;  // +0.5  (subnormal)
            4'h2: fp32_out = 32'h3F800000;  // +1.0
            4'h3: fp32_out = 32'h3FC00000;  // +1.5
            4'h4: fp32_out = 32'h40000000;  // +2.0
            4'h5: fp32_out = 32'h40400000;  // +3.0
            4'h6: fp32_out = 32'h40800000;  // +4.0
            4'h7: fp32_out = 32'h40C00000;  // +6.0
            4'h8: fp32_out = 32'h80000000;  // -0.0
            4'h9: fp32_out = 32'hBF000000;  // -0.5  (subnormal)
            4'hA: fp32_out = 32'hBF800000;  // -1.0
            4'hB: fp32_out = 32'hBFC00000;  // -1.5
            4'hC: fp32_out = 32'hC0000000;  // -2.0
            4'hD: fp32_out = 32'hC0400000;  // -3.0
            4'hE: fp32_out = 32'hC0800000;  // -4.0
            4'hF: fp32_out = 32'hC0C00000;  // -6.0
            default: fp32_out = 32'h00000000;
        endcase
    end

endmodule

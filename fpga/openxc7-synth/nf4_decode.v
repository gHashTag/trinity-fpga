// SPDX-License-Identifier: Apache-2.0
// tt-trinity-corona / src/rtl/nf4_decode.v
// NF4 (NormalFloat4, QLoRA) -> FP32 decode. 16-entry LUT.
// Values are quantiles of N(0,1) from bitsandbytes get_4bit_type("nf4").
// NOT a floating-point format; pure empirical lookup table.

`default_nettype none

module nf4_decode (
    input  wire [3:0]  nf4_in,
    output reg  [31:0] fp32_out
);

    always @(*) begin
        case (nf4_in)
            4'h0: fp32_out = 32'hBF800000;  // -1.0
            4'h1: fp32_out = 32'hBF3239B1;  // -0.6962
            4'h2: fp32_out = 32'hBF066B30;  // -0.5251
            4'h3: fp32_out = 32'hBECA32A0;  // -0.3949
            4'h4: fp32_out = 32'hBE91A24D;  // -0.2844
            4'h5: fp32_out = 32'hBE3D353F;  // -0.1848
            4'h6: fp32_out = 32'hBDBA7871;  // -0.0911
            4'h7: fp32_out = 32'h00000000;  //  0.0
            4'h8: fp32_out = 32'h3DA2FAFF;  // +0.0796
            4'h9: fp32_out = 32'h3E24CAE3;  // +0.1609
            4'hA: fp32_out = 32'h3E7C04DD;  // +0.2461
            4'hB: fp32_out = 32'h3EAD033A;  // +0.3379
            4'hC: fp32_out = 32'h3EE1A4B8;  // +0.4407
            4'hD: fp32_out = 32'h3F1007AB;  // +0.5626
            4'hE: fp32_out = 32'h3F3913B3;  // +0.7230
            4'hF: fp32_out = 32'h3F800000;  // +1.0
            default: fp32_out = 32'h00000000;
        endcase
    end

endmodule

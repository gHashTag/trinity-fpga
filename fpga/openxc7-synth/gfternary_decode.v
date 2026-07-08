`default_nettype none
`timescale 1ns / 1ps
// gfternary_decode — GFTernary 2-bit {-phi, 0, +phi} -> FP32 decode.
// Spec: gHashTag/t27 specs/numeric/gfternary.t27 + conformance/vectors/gfternary_conformance_v0.json
// Codes: 00=0, 01=+phi, 10=-phi, 11=reserved(duplicate +phi per conformance pack).
// phi = (1+sqrt(5))/2 = 1.6180339887498948 -> FP32 0x3FCF1BBD.
module gfternary_decode (
    input  wire [1:0]  gft_in,
    output reg  [31:0] fp32_out
);
    localparam [31:0] FP32_ZERO = 32'h00000000;
    localparam [31:0] FP32_PHI  = 32'h3FCF1BBD;  // +1.6180339887498948
    localparam [31:0] FP32_NPHI = 32'hBFCF1BBD;  // -1.6180339887498948
    always @(*) begin
        case (gft_in)
            2'b00: fp32_out = FP32_ZERO;
            2'b01: fp32_out = FP32_PHI;
            2'b10: fp32_out = FP32_NPHI;
            2'b11: fp32_out = FP32_PHI;  // reserved -> +phi (conformance pack)
        endcase
    end
endmodule
`default_nettype none

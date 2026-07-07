// SPDX-License-Identifier: Apache-2.0
// mxfp4_block_scale.v -- OCP Microscaling MXFP4 *block* decode core.
//
// Block = 32 x E2M1 elements + 1 shared E8M0 scale.
//   block_value[i] = fp4_decode(element[i]) * 2^(scale_e - 127)
//
// The single-element path reuses fp4_decode (E2M1, bit-identical to the proven
// fp4_e2m1 cell). The shared-E8M0 scaling is applied as an FP32 exponent-add
// (the scale is a pure power of two), so NO general FP multiplier is needed --
// this keeps the netlist routing-friendly on XC7A200T, unlike a barrel-shifter
// datapath. Reference: conformance/mxfp4_block_golden.py (single decode law).
//
// Semantics (mirrors the golden oracle exactly):
//   scale_e == 0xFF          -> every lane = FP32 qNaN (0x7FC00000)
//   element is +/-0          -> lane stays +/-0 regardless of scale
//   new_exp <= 0             -> flush to signed zero
//   new_exp >= 0xFF          -> signed Inf
//   otherwise                -> {sign, new_exp[7:0], frac}

`default_nettype none
`timescale 1ns / 1ps

module mxfp4_block_scale (
    input  wire [127:0] elements,   // 32 x 4-bit E2M1 codes, lane i = [4i +: 4]
    input  wire [7:0]   scale_e,    // shared E8M0 exponent (bias 127)
    output wire [1023:0] fp32_out   // 32 x 32-bit FP32, lane i = [32i +: 32]
);
    wire scale_nan = (scale_e == 8'hFF);
    // signed shift = scale_e - 127, range [-127, +127] -> 9-bit signed
    wire signed [8:0] shift = $signed({1'b0, scale_e}) - 9'sd127;

    genvar i;
    generate
        for (i = 0; i < 32; i = i + 1) begin : lane
            wire [31:0] elem;
            fp4_decode u_dec (.fp4_in(elements[4*i +: 4]), .fp32_out(elem));

            wire        sgn  = elem[31];
            wire [7:0]  eexp = elem[30:23];
            wire [22:0] frac = elem[22:0];
            wire        is_zero = (eexp == 8'h00) && (frac == 23'h0);

            // new exponent as signed to detect under/overflow
            wire signed [10:0] new_exp = $signed({3'b0, eexp}) + $signed({{2{shift[8]}}, shift});

            reg [31:0] lane_out;
            always @(*) begin
                if (scale_nan)
                    lane_out = 32'h7FC00000;              // NaN scale poisons lane
                else if (is_zero)
                    lane_out = elem;                      // +/-0 stays +/-0
                else if (new_exp <= 11'sd0)
                    lane_out = {sgn, 31'b0};              // underflow -> signed zero
                else if (new_exp >= 11'sd255)
                    lane_out = {sgn, 8'hFF, 23'b0};       // overflow -> signed Inf
                else
                    lane_out = {sgn, new_exp[7:0], frac};
            end

            assign fp32_out[32*i +: 32] = lane_out;
        end
    endgenerate
endmodule

`default_nettype wire

// SPDX-License-Identifier: Apache-2.0
// posit8_es2_decode — Posit8 (n=8, es=2) -> FP32 decode, Posit Standard 2022.
//
// Why this exists
// ---------------
// The catalogue's posit8 conformance pack declares "Posit Standard 2022, n=8, es=2",
// and matches SoftPosit exactly on all 255 comparable codes. The decode core the
// board proof used, external/tt-trinity-corona/src/rtl/posit8_decode.v, says in its
// own header "Posit8(es=0)". Those are different formats: at the same 8-bit code they
// disagree on 252 of 255 values, by up to five orders of magnitude, because
// posit(8,0) tops out at 2^6 = 64 while posit(8,2) reaches 2^24.
//
// So the silicon proved a format the pack does not describe. This core closes that.
//
// Why it is a wrapper and not new arithmetic
// ------------------------------------------
// At a fixed es, posit codes are prefix-coded: an n-bit posit is the (n+k)-bit posit
// with k zero bits appended. Measured rather than assumed --
//
//     posit8(es=2)[c] == posit16(es=2)[c << 8]   for all 256 codes, 0 differ
//
// against SoftPosit's positX family, which uses exactly this property itself by
// left-aligning an n-bit code in a 32-bit container.
//
// posit16_decode.v is already es = 2 and already correct, so the right implementation
// is to hand it the 8-bit code in the high bits and nothing else. No regime counter,
// no exponent path, no rounding decision is duplicated here -- duplicating them is
// how the two cores drifted apart in the first place.
//
// Verified in simulation against SoftPosit over all 256 codes; see
// fpga/openxc7-synth/tb_posit8_es2_decode.v.

`timescale 1ns / 1ps
`default_nettype none

module posit8_es2_decode (
    input  wire [7:0]  posit_in,
    output wire [31:0] fp32_out,
    output wire        is_zero,
    output wire        is_nar
);

    // The 8-bit code occupies the high byte; the low byte is absent, which is what
    // "a shorter posit" means at a fixed es.
    wire [15:0] widened = {posit_in, 8'b0};

    posit16_decode u_wide (
        .posit_in (widened),
        .fp32_out (fp32_out),
        .is_zero  (is_zero),
        .is_nar   (is_nar)
    );

endmodule

`default_nettype wire

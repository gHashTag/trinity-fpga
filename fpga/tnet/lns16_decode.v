// SPDX-License-Identifier: Apache-2.0
// lns16_decode — 16-bit LNS (1 sign + 15-bit signed log, scale 128) -> FP32 decode.
// Antilog via 128-entry LUT (2^(frac/128) -> FP32 mantissa). Deterministic.
`default_nettype none
`timescale 1ns / 1ps

module lns16_decode (
    input  wire [15:0] lns_in,
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire        sign      = lns_in[15];
    wire [14:0] log_field = lns_in[14:0];
    assign is_zero = (lns_in == 16'h0000);

    // Signed 15-bit log (2's complement). Scale: value = 2^(signed_log / 128).
    wire signed [14:0] signed_log = $signed(log_field);
    wire signed [7:0]  int_part   = signed_log >>> 7;   // arithmetic right shift
    wire [6:0]         frac_part  = log_field[6:0];     // low 7 bits (0..127)

    // 128-entry LUT: 2^(frac/128) -> FP32 mantissa (23 bits). All values in [1.0, 2.0).
    reg [22:0] frac_mant;
    always @(*) begin
        case (frac_part)
            7'd0: frac_mant = 23'h000000;
            7'd1: frac_mant = 23'h00b1ed;
            7'd2: frac_mant = 23'h0164d2;
            7'd3: frac_mant = 23'h0218af;
            7'd4: frac_mant = 23'h02cd87;
            7'd5: frac_mant = 23'h038359;
            7'd6: frac_mant = 23'h043a29;
            7'd7: frac_mant = 23'h04f1f6;
            7'd8: frac_mant = 23'h05aac3;
            7'd9: frac_mant = 23'h066491;
            7'd10: frac_mant = 23'h071f62;
            7'd11: frac_mant = 23'h07db35;
            7'd12: frac_mant = 23'h08980f;
            7'd13: frac_mant = 23'h0955ee;
            7'd14: frac_mant = 23'h0a14d5;
            7'd15: frac_mant = 23'h0ad4c6;
            7'd16: frac_mant = 23'h0b95c2;
            7'd17: frac_mant = 23'h0c57ca;
            7'd18: frac_mant = 23'h0d1adf;
            7'd19: frac_mant = 23'h0ddf04;
            7'd20: frac_mant = 23'h0ea43a;
            7'd21: frac_mant = 23'h0f6a81;
            7'd22: frac_mant = 23'h1031dc;
            7'd23: frac_mant = 23'h10fa4d;
            7'd24: frac_mant = 23'h11c3d3;
            7'd25: frac_mant = 23'h128e72;
            7'd26: frac_mant = 23'h135a2b;
            7'd27: frac_mant = 23'h1426ff;
            7'd28: frac_mant = 23'h14f4f0;
            7'd29: frac_mant = 23'h15c3ff;
            7'd30: frac_mant = 23'h16942d;
            7'd31: frac_mant = 23'h17657d;
            7'd32: frac_mant = 23'h1837f0;
            7'd33: frac_mant = 23'h190b88;
            7'd34: frac_mant = 23'h19e046;
            7'd35: frac_mant = 23'h1ab62b;
            7'd36: frac_mant = 23'h1b8d3a;
            7'd37: frac_mant = 23'h1c6573;
            7'd38: frac_mant = 23'h1d3eda;
            7'd39: frac_mant = 23'h1e196e;
            7'd40: frac_mant = 23'h1ef532;
            7'd41: frac_mant = 23'h1fd228;
            7'd42: frac_mant = 23'h20b051;
            7'd43: frac_mant = 23'h218faf;
            7'd44: frac_mant = 23'h227043;
            7'd45: frac_mant = 23'h23520f;
            7'd46: frac_mant = 23'h243516;
            7'd47: frac_mant = 23'h251958;
            7'd48: frac_mant = 23'h25fed7;
            7'd49: frac_mant = 23'h26e595;
            7'd50: frac_mant = 23'h27cd94;
            7'd51: frac_mant = 23'h28b6d5;
            7'd52: frac_mant = 23'h29a15b;
            7'd53: frac_mant = 23'h2a8d26;
            7'd54: frac_mant = 23'h2b7a3a;
            7'd55: frac_mant = 23'h2c6897;
            7'd56: frac_mant = 23'h2d583f;
            7'd57: frac_mant = 23'h2e4934;
            7'd58: frac_mant = 23'h2f3b79;
            7'd59: frac_mant = 23'h302f0e;
            7'd60: frac_mant = 23'h3123f6;
            7'd61: frac_mant = 23'h321a32;
            7'd62: frac_mant = 23'h3311c4;
            7'd63: frac_mant = 23'h340aaf;
            7'd64: frac_mant = 23'h3504f3;
            7'd65: frac_mant = 23'h360094;
            7'd66: frac_mant = 23'h36fd92;
            7'd67: frac_mant = 23'h37fbf0;
            7'd68: frac_mant = 23'h38fbaf;
            7'd69: frac_mant = 23'h39fcd2;
            7'd70: frac_mant = 23'h3aff5b;
            7'd71: frac_mant = 23'h3c034a;
            7'd72: frac_mant = 23'h3d08a4;
            7'd73: frac_mant = 23'h3e0f68;
            7'd74: frac_mant = 23'h3f179a;
            7'd75: frac_mant = 23'h40213b;
            7'd76: frac_mant = 23'h412c4d;
            7'd77: frac_mant = 23'h4238d2;
            7'd78: frac_mant = 23'h4346cd;
            7'd79: frac_mant = 23'h44563f;
            7'd80: frac_mant = 23'h45672a;
            7'd81: frac_mant = 23'h467991;
            7'd82: frac_mant = 23'h478d75;
            7'd83: frac_mant = 23'h48a2d8;
            7'd84: frac_mant = 23'h49b9be;
            7'd85: frac_mant = 23'h4ad226;
            7'd86: frac_mant = 23'h4bec15;
            7'd87: frac_mant = 23'h4d078c;
            7'd88: frac_mant = 23'h4e248c;
            7'd89: frac_mant = 23'h4f4319;
            7'd90: frac_mant = 23'h506334;
            7'd91: frac_mant = 23'h5184df;
            7'd92: frac_mant = 23'h52a81e;
            7'd93: frac_mant = 23'h53ccf1;
            7'd94: frac_mant = 23'h54f35b;
            7'd95: frac_mant = 23'h561b5e;
            7'd96: frac_mant = 23'h5744fd;
            7'd97: frac_mant = 23'h587039;
            7'd98: frac_mant = 23'h599d16;
            7'd99: frac_mant = 23'h5acb94;
            7'd100: frac_mant = 23'h5bfbb8;
            7'd101: frac_mant = 23'h5d2d82;
            7'd102: frac_mant = 23'h5e60f5;
            7'd103: frac_mant = 23'h5f9613;
            7'd104: frac_mant = 23'h60ccdf;
            7'd105: frac_mant = 23'h62055b;
            7'd106: frac_mant = 23'h633f89;
            7'd107: frac_mant = 23'h647b6d;
            7'd108: frac_mant = 23'h65b907;
            7'd109: frac_mant = 23'h66f85b;
            7'd110: frac_mant = 23'h68396a;
            7'd111: frac_mant = 23'h697c38;
            7'd112: frac_mant = 23'h6ac0c7;
            7'd113: frac_mant = 23'h6c0719;
            7'd114: frac_mant = 23'h6d4f30;
            7'd115: frac_mant = 23'h6e9910;
            7'd116: frac_mant = 23'h6fe4ba;
            7'd117: frac_mant = 23'h713231;
            7'd118: frac_mant = 23'h728177;
            7'd119: frac_mant = 23'h73d290;
            7'd120: frac_mant = 23'h75257d;
            7'd121: frac_mant = 23'h767a41;
            7'd122: frac_mant = 23'h77d0df;
            7'd123: frac_mant = 23'h79295a;
            7'd124: frac_mant = 23'h7a83b3;
            7'd125: frac_mant = 23'h7bdfed;
            7'd126: frac_mant = 23'h7d3e0c;
            7'd127: frac_mant = 23'h7e9e11;
            default:  frac_mant = 23'h7fffff;
        endcase
    end

    // FP32 exponent = 127 + int_part (9-bit to catch overflow/underflow).
    wire signed [8:0] fp32_exp = $signed(int_part) + 9'sd127;

    // Full mantissa with implicit leading 1 ({1'b1, frac_mant} as 24-bit).
    // For subnormal results (fp32_exp <= 0), this is shifted right with RNE
    // rounding to produce the FP32 subnormal field (FIX 2026-07-03 loop;
    // previously flushed ALL subnormals to signed zero -- see
    // fpga/FINDING_2026_07_03_lns16_subnormal_flush.md).
    wire [23:0] full_mant = {1'b1, frac_mant};

    // subnormal-rounding temporaries (declared at module level -- yosys rejects
    // block-local reg declarations outside SystemVerilog mode).
    reg [23:0] sv_sub;
    reg g_sub, r_sub, stb_sub, ru_sub;
    reg [23:0] sk_sub;

    always @(*) begin
        if (is_zero)
            fp32_out = 32'h00000000;
        else if (fp32_exp > 9'sd254)
            fp32_out = {sign, 8'hFF, 23'h000000};       // overflow -> Inf
        else if (fp32_exp < 9'sd1) begin
            // SUBNORMAL (FIX 2026-07-03): round full_mant into the 23-bit
            // subnormal field. lns16's int_part is 8-bit signed [-128,127] so
            // fp32_exp >= -1 -> only two subnormal cases: fp32_exp=0 (sh=1)
            // and fp32_exp=-1 (sh=2). Previously flushed ALL to signed zero.
            // See fpga/FINDING_2026_07_03_lns16_subnormal_flush.md.
            case (fp32_exp)
                9'sd0:  begin sv_sub = full_mant >> 1; g_sub = full_mant[0]; r_sub = 1'b0; stb_sub = 1'b0; end
                default: begin sv_sub = full_mant >> 2; g_sub = full_mant[1]; r_sub = full_mant[0]; stb_sub = 1'b0; end
            endcase
            ru_sub = g_sub & (r_sub | stb_sub | sv_sub[0]);
            sk_sub = sv_sub + (ru_sub ? 24'd1 : 24'd0);
            if (sk_sub >= 24'h800000)
                fp32_out = {sign, 8'h01, 23'h000000};   // rounded up to min normal
            else if (sk_sub == 0)
                fp32_out = {sign, 24'h0};               // rounded to signed zero
            else
                fp32_out = {sign, 8'h00, sk_sub[22:0]};  // subnormal field
        end
        else
            fp32_out = {sign, fp32_exp[7:0], frac_mant};
    end

endmodule

`default_nettype wire
`default_nettype none
`timescale 1ns / 1ps
// takum64_decode_pipelined — 6-stage pipelined version of takum64_decode.
// Same bit-exact decode law as takum64_decode.v (Hunhold 2024 logarithmic N=64 -> FP32).
// Splits the combinational datapath into registered stages to break routing cliff.
// Uses (* ram_style="distributed" *) for reliable BRAM init via $readmemh.
//
// Pipeline stages:
//   S1: extract -> ell_59 (70-bit)
//   S2: L_Q107 = ell_59 * C_Q48 (119-bit signed multiply) -> k, frac, f_hi, f_lo
//   S2.5: register f_hi_q2 (BRAM latency compensator)
//   S3: BRAM lookup tval + flo_ln2 = f_lo * LN2_Q48 -> corr
//   S4: Taylor corr_q2 + mant
//   S5: normalize + round + subnormal pack -> fp32_out
// Latency: 6 clock cycles.

module takum64_decode_pipelined (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [63:0] t64,
    output reg  [31:0] fp32_out
);
    localparam [47:0] C_Q48   = 48'd203041276517399;
    localparam [47:0] LN2_Q48 = 48'd195103586505167;
    localparam PMAX = 59;

    (* ram_style="distributed" *) reg [47:0] tbl [0:65535];
    initial $readmemh("fpga/openxc7-synth/takum32_2frac.mem", tbl);

    // ============================================================
    // Stage 1: extract fields, compute ell_59
    // ============================================================
    wire S1_S = t64[63]; wire S1_D = t64[62]; wire S1_R = t64[61:59];
    wire [3:0] S1_cidx = {S1_D, S1_R};
    reg signed [8:0] S1_cbias;
    always @* case (S1_cidx)
        4'd0:S1_cbias=-9'sd255; 4'd1:S1_cbias=-9'sd127; 4'd2:S1_cbias=-9'sd63; 4'd3:S1_cbias=-9'sd31;
        4'd4:S1_cbias=-9'sd15;  4'd5:S1_cbias=-9'sd7;   4'd6:S1_cbias=-9'sd3;  4'd7:S1_cbias=-9'sd1;
        4'd8:S1_cbias=9'sd0;    4'd9:S1_cbias=9'sd1;    4'd10:S1_cbias=9'sd3;  4'd11:S1_cbias=9'sd7;
        4'd12:S1_cbias=9'sd15;  4'd13:S1_cbias=9'sd31;  4'd14:S1_cbias=9'sd63; 4'd15:S1_cbias=9'sd127;
    endcase
    wire [2:0] S1_r_eff = S1_D ? S1_R : (3'd7 - S1_R);
    wire [6:0] S1_p = PMAX - {4'b0, S1_r_eff};
    wire [58:0] S1_lower = t64[58:0];
    wire [58:0] S1_M_u = S1_lower & ((59'h1 << S1_p) - 1);
    wire [58:0] S1_C_u = (S1_lower >> S1_p) & ((59'h1 << {3'b0, S1_r_eff}) - 1);
    wire signed [9:0] S1_c = $signed(S1_cbias) + $signed({49'b0, S1_C_u});
    wire signed [69:0] S1_c_sh = S1_c * 70'sd576460752303423488;
    wire signed [69:0] S1_m_sh = $signed({11'b0, S1_M_u << S1_r_eff});
    wire signed [69:0] S1_ell_59_full = S1_S ? -(S1_c_sh + S1_m_sh) : (S1_c_sh + S1_m_sh);
    wire S1_ell_sticky = |S1_ell_59_full[23:0];
    wire signed [69:0] S1_ell_59 = {S1_ell_59_full[69:24], S1_ell_sticky, 23'b0};

    reg signed [69:0] ell_59_q;
    reg [63:0]       t64_q1;
    always @(posedge clk) begin
        if (!rst_n) begin ell_59_q <= 70'sd0; t64_q1 <= 64'd0; end
        else begin ell_59_q <= S1_ell_59; t64_q1 <= t64; end
    end

    // ============================================================
    // Stage 2: L_Q107 = ell_59 * C_Q48, range-reduce
    // ============================================================
    wire signed [118:0] S2_L_Q107 = ell_59_q * $signed({1'b0, C_Q48});
    wire signed [12:0]  S2_k      = S2_L_Q107 >>> 107;
    wire [106:0]        S2_frac   = S2_L_Q107[106:0];
    wire [15:0]         S2_f_hi   = S2_frac[106:91];
    wire [90:0]         S2_f_lo_full = S2_frac[90:0];
    wire                S2_f_lo_sticky = |S2_f_lo_full[66:0];
    wire [90:0]         S2_f_lo   = {S2_f_lo_full[90:67], S2_f_lo_sticky, 66'b0};

    reg signed [12:0] k_q;
    reg [15:0]        f_hi_q;
    reg [90:0]        f_lo_q;
    reg [63:0]        t64_q2;
    always @(posedge clk) begin
        if (!rst_n) begin k_q<=13'sd0; f_hi_q<=16'd0; f_lo_q<=91'd0; t64_q2<=64'd0; end
        else begin k_q<=S2_k; f_hi_q<=S2_f_hi; f_lo_q<=S2_f_lo; t64_q2<=t64_q1; end
    end

    // ============================================================
    // Stage 2.5: register for BRAM latency
    // ============================================================
    reg [15:0]        f_hi_q2;
    reg [90:0]        f_lo_q2;
    reg signed [12:0] k_q2b;
    reg [63:0]        t64_q2b;
    always @(posedge clk) begin
        if (!rst_n) begin f_hi_q2<=16'd0; f_lo_q2<=91'd0; k_q2b<=13'sd0; t64_q2b<=64'd0; end
        else begin f_hi_q2<=f_hi_q; f_lo_q2<=f_lo_q; k_q2b<=k_q; t64_q2b<=t64_q2; end
    end

    // ============================================================
    // Stage 3: BRAM lookup + flo_ln2 multiply -> corr
    // ============================================================
    wire [47:0] S3_tval = tbl[f_hi_q2];
    wire signed [139:0] S3_flo_ln2 = $signed({49'b0, f_lo_q2}) * $signed({1'b0, LN2_Q48});
    wire [31:0] S3_corr = S3_flo_ln2 >>> 107;

    reg [47:0]        tval_q;
    reg [31:0]        corr_q;
    reg signed [12:0] k_q3;
    reg [63:0]        t64_q3;
    always @(posedge clk) begin
        if (!rst_n) begin tval_q<=48'd0; corr_q<=32'd0; k_q3<=13'sd0; t64_q3<=64'd0; end
        else begin tval_q<=S3_tval; corr_q<=S3_corr; k_q3<=k_q2b; t64_q3<=t64_q2b; end
    end

    // ============================================================
    // Stage 4: Taylor + mantissa
    // ============================================================
    wire [31:0] S4_corr_q2 = corr_q + ((corr_q * corr_q) >> 49);
    wire [79:0] S4_tp   = tval_q * S4_corr_q2;
    wire [48:0] S4_mant = {1'b0, tval_q} + S4_tp[79:48];

    reg [48:0]        mant_q;
    reg signed [12:0] k_q4;
    reg [63:0]        t64_q4;
    always @(posedge clk) begin
        if (!rst_n) begin mant_q<=49'd0; k_q4<=13'sd0; t64_q4<=64'd0; end
        else begin mant_q<=S4_mant; k_q4<=k_q3; t64_q4<=t64_q3; end
    end

    // ============================================================
    // Stage 5: normalize + round + subnormal pack + final select
    // ============================================================
    wire S5_S = t64_q4[63];
    reg [47:0]        S5_mn;
    reg signed [12:0] S5_e2;
    reg [24:0]        S5_m25;
    reg               S5_g, S5_r_b, S5_stb, S5_ru;
    reg [23:0]        S5_m24;
    reg [47:0]        S5_sv;
    reg               S5_sg, S5_sr_, S5_ss_, S5_sru;
    reg [23:0]        S5_sk;
    reg [31:0]        S5_fp32;
    always @* begin
        if (mant_q[48]) begin S5_mn = {1'b0, mant_q[48:1]}; S5_e2 = k_q4 + 13'sd1; end
        else begin S5_mn = mant_q[47:0]; S5_e2 = k_q4; end
        S5_m25 = {1'b0, S5_mn[47:24]}; S5_g = S5_mn[23]; S5_r_b = S5_mn[22]; S5_stb = |S5_mn[21:0];
        S5_ru = S5_g & (S5_r_b | S5_stb | S5_m25[0]);
        if (S5_ru) S5_m25 = S5_m25 + 1;
        if (S5_m25[24]) begin S5_m24 = 24'h800000; S5_e2 = S5_e2 + 13'sd1; end
        else S5_m24 = S5_m25[23:0];
        S5_fp32 = 32'h7FC00000;
        if (t64_q4 == 0)               S5_fp32 = 32'h00000000;
        else if (t64_q4 == 64'h8000000000000000) S5_fp32 = 32'h7FC00000;
        else if (S5_e2 > 13'sd127)     S5_fp32 = {S5_S, 8'hFF, 23'h0};
        else if (S5_e2 < -13'sd150)    S5_fp32 = {S5_S, 31'h0};
        else if (S5_e2 < -13'sd126) begin
            if (S5_e2 >= -13'sd150) begin
                S5_sv = S5_mn >> (-S5_e2 - 102);
                S5_sg = ((-S5_e2 - 102) >= 1) ? ((S5_mn >> ((-S5_e2 - 102) - 1)) & 1) : 0;
                S5_sr_ = ((-S5_e2 - 102) >= 2) ? ((S5_mn >> ((-S5_e2 - 102) - 2)) & 1) : 0;
                S5_ss_ = ((-S5_e2 - 102) >= 3) ? |(S5_mn & ((48'h1 << ((-S5_e2 - 102) - 2)) - 1)) : 0;
                S5_sru = S5_sg & (S5_sr_ | S5_ss_ | S5_sv[0]);
                S5_sk = {1'b0, S5_sv[22:0]} + (S5_sru ? 24'd1 : 24'd0);
                if (S5_sk >= 24'h800000) S5_fp32 = {S5_S, 8'd1, 23'h0};
                else if (S5_sk == 0)     S5_fp32 = {S5_S, 31'h0};
                else                     S5_fp32 = {S5_S, 8'h00, S5_sk[22:0]};
            end else S5_fp32 = {S5_S, 31'h0};
        end else S5_fp32 = {S5_S, S5_e2[7:0] + 8'd127, S5_m24[22:0]};
    end

    always @(posedge clk) begin
        if (!rst_n) fp32_out <= 32'd0;
        else        fp32_out <= S5_fp32;
    end
endmodule
`default_nettype none

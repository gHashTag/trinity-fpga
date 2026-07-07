`default_nettype none
`timescale 1ns / 1ps
// takum32_decode_pipelined — 5-stage pipelined version of takum32_decode.
// Same bit-exact decode law as takum32_decode.v (Hunhold 2024 logarithmic N=32 -> FP32),
// but splits the combinational datapath into 5 registered stages to break the
// routing cliff on XC7A200T (87-bit + 72-bit multiplies + BRAM lookup + barrel-shift
// were too wide for sa/heap placers to route in a single clock domain).
//
// Pipeline stages:
//   S1: extract S/D/R/M_u/C_u -> ell_27
//   S2: L_Q75 = ell_27 * C_Q48 (87-bit signed multiply) -> k, frac, f_hi, f_lo
//   S3: BRAM lookup tval = tbl[f_hi] + flo_ln2 = f_lo * LN2_Q48 -> corr
//   S4: Taylor corr_q2 + mant = tval + (tval * corr_q2 >> 48)
//   S5: normalize + round + subnormal pack -> fp32_out
//
// Latency: 5 clock cycles from t32 valid to fp32_out valid.
// Bit-exactness preserved via registered intermediate values (no algorithmic change).

module takum32_decode_pipelined (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] t32,
    output reg  [31:0] fp32_out
);
    localparam [47:0] C_Q48   = 48'd203041276517399; // log2(e)/2 * 2^48
    localparam [47:0] LN2_Q48 = 48'd195103586505167; // ln2 * 2^48

    // BRAM table: 2^(f_hi/2^16), 48-bit (same as combinational version)
    reg [47:0] tbl [0:65535];
    initial $readmemh("fpga/openxc7-synth/takum32_2frac.mem", tbl);

    // ============================================================
    // Stage 1: extract fields, compute ell_27
    // ============================================================
    wire S1_S = t32[31]; wire S1_D = t32[30]; wire S1_R = t32[29:27];
    wire [3:0] S1_cidx = {S1_D, S1_R};
    reg signed [8:0] S1_cbias;
    always @* case (S1_cidx)
        4'd0:S1_cbias=-9'sd255; 4'd1:S1_cbias=-9'sd127; 4'd2:S1_cbias=-9'sd63; 4'd3:S1_cbias=-9'sd31;
        4'd4:S1_cbias=-9'sd15;  4'd5:S1_cbias=-9'sd7;   4'd6:S1_cbias=-9'sd3;  4'd7:S1_cbias=-9'sd1;
        4'd8:S1_cbias=9'sd0;    4'd9:S1_cbias=9'sd1;    4'd10:S1_cbias=9'sd3;  4'd11:S1_cbias=9'sd7;
        4'd12:S1_cbias=9'sd15;  4'd13:S1_cbias=9'sd31;  4'd14:S1_cbias=9'sd63; 4'd15:S1_cbias=9'sd127;
    endcase
    wire [2:0] S1_r_eff = S1_D ? S1_R : (3'd7 - S1_R);
    wire [4:0] S1_p = 5'd27 - {2'b00, S1_r_eff};
    wire [26:0] S1_lower = t32[26:0];
    wire [26:0] S1_M_u = S1_lower & ((27'h1 << S1_p) - 1);
    wire [26:0] S1_C_u = (S1_lower >> S1_p) & ((27'h1 << {2'b00, S1_r_eff}) - 1);
    wire signed [9:0] S1_c = $signed(S1_cbias) + $signed({17'b0, S1_C_u});
    wire signed [37:0] S1_c_sh = S1_c * 38'sd134217728;
    wire signed [37:0] S1_m_sh = $signed({11'b0, S1_M_u << S1_r_eff});
    wire signed [37:0] S1_ell_27 = S1_S ? -(S1_c_sh + S1_m_sh) : (S1_c_sh + S1_m_sh);

    // Stage-1 registers
    reg signed [37:0] ell_27_q;
    reg [31:0]        t32_q1;   // carry through for special-case detection
    always @(posedge clk) begin
        if (!rst_n) begin
            ell_27_q <= 38'sd0;
            t32_q1   <= 32'd0;
        end else begin
            ell_27_q <= S1_ell_27;
            t32_q1   <= t32;
        end
    end

    // ============================================================
    // Stage 2: L_Q75 = ell_27 * C_Q48, range-reduce to k, frac, f_hi, f_lo
    // ============================================================
    wire signed [86:0] S2_L_Q75 = ell_27_q * $signed({1'b0, C_Q48});
    wire signed [11:0] S2_k      = S2_L_Q75 >>> 75;
    wire [74:0]        S2_frac   = S2_L_Q75[74:0];
    wire [15:0]        S2_f_hi   = S2_frac[74:59];
    wire [58:0]        S2_f_lo_full = S2_frac[58:0];
    wire               S2_f_lo_sticky = |S2_f_lo_full[34:0];
    wire [58:0]        S2_f_lo   = {S2_f_lo_full[58:35], S2_f_lo_sticky, 34'b0};

    reg signed [11:0] k_q;
    reg [15:0]        f_hi_q;
    reg [58:0]        f_lo_q;
    reg [31:0]        t32_q2;
    always @(posedge clk) begin
        if (!rst_n) begin
            k_q    <= 12'sd0;
            f_hi_q <= 16'd0;
            f_lo_q <= 59'd0;
            t32_q2 <= 32'd0;
        end else begin
            k_q    <= S2_k;
            f_hi_q <= S2_f_hi;
            f_lo_q <= S2_f_lo;
            t32_q2 <= t32_q1;
        end
    end

    // ============================================================
    // Stage 2.5: register f_hi_q for BRAM synchronous read
    // (yosys infers synchronous BRAM from tbl[f_hi_q], adding 1 cycle latency)
    // ============================================================
    reg [15:0] f_hi_q2;
    reg [58:0] f_lo_q2;
    reg signed [11:0] k_q2b;
    reg [31:0] t32_q2b;
    always @(posedge clk) begin
        if (!rst_n) begin
            f_hi_q2  <= 16'd0;
            f_lo_q2  <= 59'd0;
            k_q2b    <= 12'sd0;
            t32_q2b  <= 32'd0;
        end else begin
            f_hi_q2  <= f_hi_q;
            f_lo_q2  <= f_lo_q;
            k_q2b    <= k_q;
            t32_q2b  <= t32_q2;
        end
    end

    // ============================================================
    // Stage 3: BRAM lookup tval (synchronous read, 1 cycle) + flo_ln2 multiply
    // ============================================================
    wire [47:0] S3_tval = tbl[f_hi_q2];   // synchronous BRAM read (1 cycle)
    wire signed [107:0] S3_flo_ln2 = $signed({49'b0, f_lo_q2}) * $signed({1'b0, LN2_Q48});
    wire [31:0] S3_corr = S3_flo_ln2 >>> 75;

    reg [47:0]        tval_q;
    reg [31:0]        corr_q;
    reg signed [11:0] k_q3;
    reg [31:0]        t32_q3;
    always @(posedge clk) begin
        if (!rst_n) begin
            tval_q  <= 48'd0;
            corr_q  <= 32'd0;
            k_q3    <= 12'sd0;
            t32_q3  <= 32'd0;
        end else begin
            tval_q  <= S3_tval;
            corr_q  <= S3_corr;
            k_q3    <= k_q2b;
            t32_q3  <= t32_q2b;
        end
    end

    // ============================================================
    // Stage 4: Taylor corr_q2 + mantissa
    // ============================================================
    wire [31:0] S4_corr_q2 = corr_q + ((corr_q * corr_q) >> 49);
    wire [79:0] S4_tp   = tval_q * S4_corr_q2;
    wire [48:0] S4_mant = {1'b0, tval_q} + S4_tp[79:48];

    reg [48:0]        mant_q;
    reg signed [11:0] k_q4;
    reg [31:0]        t32_q4;
    always @(posedge clk) begin
        if (!rst_n) begin
            mant_q  <= 49'd0;
            k_q4    <= 12'sd0;
            t32_q4  <= 32'd0;
        end else begin
            mant_q  <= S4_mant;
            k_q4    <= k_q3;
            t32_q4  <= t32_q3;
        end
    end

    // ============================================================
    // Stage 5: normalize + round + subnormal pack + final select
    // (combinational from registered inputs, then registered output)
    // ============================================================
    wire S5_S = t32_q4[31];
    reg [47:0]        S5_mn;
    reg signed [11:0] S5_e2;
    reg [24:0]        S5_m25;
    reg               S5_g, S5_r_b, S5_stb, S5_ru;
    reg [23:0]        S5_m24;
    reg [47:0]        S5_sv;
    reg               S5_sg, S5_sr_, S5_ss_, S5_sru;
    reg [23:0]        S5_sk;
    reg [31:0]        S5_fp32;
    always @* begin
        if (mant_q[48]) begin S5_mn = {1'b0, mant_q[48:1]}; S5_e2 = k_q4 + 12'sd1; end
        else begin S5_mn = mant_q[47:0]; S5_e2 = k_q4; end
        S5_m25 = {1'b0, S5_mn[47:24]}; S5_g = S5_mn[23]; S5_r_b = S5_mn[22]; S5_stb = |S5_mn[21:0];
        S5_ru = S5_g & (S5_r_b | S5_stb | S5_m25[0]);
        if (S5_ru) S5_m25 = S5_m25 + 1;
        if (S5_m25[24]) begin S5_m24 = 24'h800000; S5_e2 = S5_e2 + 12'sd1; end
        else S5_m24 = S5_m25[23:0];
        S5_fp32 = 32'h7FC00000;
        if (t32_q4 == 0)               S5_fp32 = 32'h00000000;
        else if (t32_q4 == 32'h80000000) S5_fp32 = 32'h7FC00000;
        else if (S5_e2 > 12'sd127)     S5_fp32 = {S5_S, 8'hFF, 23'h0};
        else if (S5_e2 < -12'sd150)    S5_fp32 = {S5_S, 31'h0};
        else if (S5_e2 < -12'sd126) begin
            if (S5_e2 >= -12'sd150) begin
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

    // Registered output (Stage 5 -> output)
    always @(posedge clk) begin
        if (!rst_n) fp32_out <= 32'd0;
        else        fp32_out <= S5_fp32;
    end
endmodule
`default_nettype none

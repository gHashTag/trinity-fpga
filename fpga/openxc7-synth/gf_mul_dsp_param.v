`timescale 1ns / 1ps
// ============================================================================
// gf_mul_dsp_param.v — DSP48E1-ОБЁРТКА умножителя GoldenFloat GF{N}.
//
// НАЗНАЧЕНИЕ: идентична gf_mul_param.v по FP-логике (классификация, нормализация,
//   RNE, family-split overflow, gradual-underflow, zero/Inf/NaN-края), НО
//   произведение значащих ma_f*mb_f вычисляется ЯВНЫМ инстансом примитива
//   DSP48E1 (Xilinx 7-series), а НЕ поведенческим оператором `*`.
//
//   Пользователь выбрал: «Нужен явный DSP48E1-инстанс». Методология (двухуровневая)
//   выбрана по research mul_dsp48e1_research.md (см. ссылки ниже).
//
// ┌──────────────────────────────────────────────────────────────────────────┐
// │ СТАТУС ВЕРИФИКАЦИИ ЭТОГО ФАЙЛА: [ТРЕБУЕТ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ]            │
// │   UNISIM DSP48E1.v НЕ работает в iverilog/Verilator без Vivado (UG900).   │
// │   Поэтому эквивалентность DSP-версии доказывается ТОЛЬКО:                  │
// │     1) Vivado xsim co-simulation (gf_mul_param vs gf_mul_dsp_param,        │
// │        одинаковые векторы) — поведенческая UNISIM-симуляция;              │
// │     2) post-synthesis / post-implementation simulation;                   │
// │     3) on-hardware на реальных DSP48E1-срезах AX7203 (XC7A200T-2).        │
// │   В песочнице доказано ТОЛЬКО алгоритмическое ядро gf_mul_param.v          │
// │   [смоделировано, 2 оракула]. DSP-маппинг = 0 проверок на железе.          │
// └──────────────────────────────────────────────────────────────────────────┘
//
// Параметры DSP48E1 (UG479 §2; UG953):
//   DSP48E1 — 25×18 ЗНАКОВЫЙ умножитель: A[24:0] × B[17:0] -> 43-бит, до P[47:0].
//   USE_DPORT=FALSE   — предсумматор отключён (порт D игнорируется).
//   USE_MULT="MULTIPLY" — умножитель включён.
//   USE_SIMD="ONE48"  — один 48-бит ALU (без SIMD-разбиения).
//   AREG=1,BREG=1     — один входной регистр на каждый операнд.
//   MREG=1,PREG=1     — рекомендация Xilinx для Fmax (латентность 3 такта).
//   OPMODE=7'b000_01_01 (0x05): Z-mux=0, Y-mux=M, X-mux=M  -> P = A*B.
//   ALUMODE=4'b0000   — постсумматор = сложение (Z + (X:Y)).
//   INMODE=5'b00000   — обход предсумматора, прямые A/B.
//   ВСЕ сбросы (RSTA/RSTB/RSTM/RSTP/RSTCTRL/RSTALLCARRYIN/...) — ACTIVE-HIGH.
//
// ОГРАНИЧЕНИЕ ШИРИНЫ: значащие беззнаковые, ширина MF=MANT_BITS+1.
//   GF6..GF20 -> MF в [4..13] бит. Помещаются в B[17:0] и A[24:0] как
//   ПОЛОЖИТЕЛЬНЫЕ (старший бит знака = 0). Знак результата обрабатывается
//   ОТДЕЛЬНО (sa^sb), в DSP идут только МОДУЛИ значащих. Для GF24 (M14 -> MF=15)
//   тоже помещается, но GF24 требует отдельного ядра (см. бэклог) — здесь не цель.
//
// Honesty: Vasilev, ORCID 0009-0008-4294-6159, admin@t27.ai.
//   [требует подтверждения] на железе. encoding != compute != FPGA-bitexact.
//
// Источники:
//   UG479 7-Series DSP48E1:
//     https://www.fdi.ucm.es/profesor/mendias/das/docs/ug479_7Series_DSP48E1.pdf
//   UG953 Vivado 7-series Libraries (DSP48E1):
//     https://docs.amd.com/r/en-US/ug953-vivado-7series-libraries/DSP48E1
//   UG900 Logic Simulation (UNISIM требует Vivado):
//     https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_1/ug900-vivado-logic-simulation.pdf
//   Erratum 2606.05017 §5.5 (ширина произведения 2M+2): https://arxiv.org/abs/2606.05017
// ============================================================================
module gf_mul_dsp_param #(
    parameter EXP_BITS  = 6,
    parameter MANT_BITS = 9,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    parameter HAS_INF   = 0
)(
    input  wire                clk,
    input  wire                rst,        // ACTIVE-HIGH (как RST* у DSP48E1)
    input  wire                in_valid,
    input  wire [TOTAL-1:0]    in_a,
    input  wire [TOTAL-1:0]    in_b,
    output wire                in_ready,
    output reg                 out_valid,
    output reg  [TOTAL-1:0]    out_y,
    input  wire                out_ready
);
    localparam MF = MANT_BITS + 1;            // ширина значащей с implicit-битом
    localparam PW = 2*(MANT_BITS+1);          // ширина произведения [erratum 2M+2]

    // ----- извлечение полей операндов -----
    wire                  sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]   ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]  ma = in_a[MANT_BITS-1:0];
    wire                  sb = in_b[TOTAL-1];
    wire [EXP_BITS-1:0]   eb = in_b[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]  mb = in_b[MANT_BITS-1:0];

    wire a_denorm = (BIAS > 0) && (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
    wire b_denorm = (BIAS > 0) && (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});

    // значащие с implicit (модули, БЕЗ знака — знак обрабатывается отдельно)
    wire [MF-1:0] ma_f = a_denorm ? {1'b0, ma} : {1'b1, ma};
    wire [MF-1:0] mb_f = b_denorm ? {1'b0, mb} : {1'b1, mb};

    // ====================================================================
    //  ЯВНЫЙ DSP48E1-ИНСТАНС: prod = ma_f * mb_f  (25x18 signed, P = A*B)
    // ====================================================================
    //  Значащие беззнаковые -> подаём как положительные:
    //    A[24:0] = {25{1'b0}} с ma_f в младших; знаковый бит A[24]=0.
    //    B[17:0] = {18{1'b0}} с mb_f в младших; знаковый бит B[17]=0.
    //  P[47:0] -> младшие PW бит = произведение значащих.
    wire [47:0] dsp_p;
    wire [24:0] dsp_a = {{(25-MF){1'b0}}, ma_f};   // ширина MF <= 13 (GF20) <= 25 OK
    wire [17:0] dsp_b = {{(18-MF){1'b0}}, mb_f};   // ширина MF <= 13 <= 18 OK

    DSP48E1 #(
        .A_INPUT       ("DIRECT"),
        .B_INPUT       ("DIRECT"),
        .USE_DPORT     ("FALSE"),
        .USE_MULT      ("MULTIPLY"),
        .USE_SIMD      ("ONE48"),
        .AUTORESET_PATDET ("NO_RESET"),
        .MASK          (48'h3FFFFFFFFFFF),
        .PATTERN       (48'h000000000000),
        .SEL_MASK      ("MASK"),
        .SEL_PATTERN   ("PATTERN"),
        .USE_PATTERN_DETECT ("NO_PATDET"),
        // пайплайн-регистры: рекомендация Xilinx для Fmax (латентность 3 такта)
        .ACASCREG      (1),
        .ADREG         (0),
        .ALUMODEREG    (1),
        .AREG          (1),
        .BCASCREG      (1),
        .BREG          (1),
        .CARRYINREG    (1),
        .CARRYINSELREG (1),
        .CREG          (1),
        .DREG          (0),
        .INMODEREG     (1),
        .MREG          (1),
        .OPMODEREG     (1),
        .PREG          (1)
    ) u_dsp_mul (
        // ----- выход -----
        .P             (dsp_p),
        .PCOUT         (),
        // ----- каскадные выходы (не используются) -----
        .ACOUT         (), .BCOUT       (), .CARRYCASCOUT (), .MULTSIGNOUT (),
        .OVERFLOW      (), .PATTERNBDETECT (), .PATTERNDETECT (), .UNDERFLOW (),
        .CARRYOUT      (),
        // ----- входы данных -----
        .A             (dsp_a),
        .B             (dsp_b),
        .C             (48'b0),
        .D             (25'b0),
        .CARRYIN       (1'b0),
        // ----- каскадные входы (не используются) -----
        .ACIN          (30'b0),
        .BCIN          (18'b0),
        .PCIN          (48'b0),
        .CARRYCASCIN   (1'b0),
        .MULTSIGNIN    (1'b0),
        // ----- управление -----
        .ALUMODE       (4'b0000),         // P = Z + (X:Y) = 0 + M = A*B
        .INMODE        (5'b00000),        // обход предсумматора, прямые A/B
        .OPMODE        (7'b000_01_01),    // 0x05: Z=0, Y=M, X=M -> A*B
        .CARRYINSEL    (3'b000),
        // ----- clock enables (все включены) -----
        .CEA1          (1'b1), .CEA2     (1'b1),
        .CEAD          (1'b1),
        .CEALUMODE     (1'b1),
        .CEB1          (1'b1), .CEB2     (1'b1),
        .CEC           (1'b1),
        .CECARRYIN     (1'b1),
        .CECTRL        (1'b1),
        .CED           (1'b1),
        .CEINMODE      (1'b1),
        .CEM           (1'b1),
        .CEP           (1'b1),
        .CLK           (clk),
        // ----- сбросы: ВСЕ ACTIVE-HIGH, заведены на общий rst -----
        .RSTA          (rst), .RSTB      (rst),
        .RSTC          (rst), .RSTD      (rst),
        .RSTM          (rst), .RSTP      (rst),
        .RSTCTRL       (rst),
        .RSTALLCARRYIN (rst),
        .RSTALUMODE    (rst),
        .RSTINMODE     (rst)
    );

    // младшие PW бит P = произведение значащих (значащие беззнаковые -> P>=0)
    wire [PW-1:0] prod_dsp = dsp_p[PW-1:0];

    // ====================================================================
    //  FP-обвязка: ИДЕНТИЧНА gf_mul_param.v, но prod берётся из DSP.
    //  ВАЖНО: DSP даёт prod через 3 такта (AREG+MREG+PREG). Для bit-exact
    //  совпадения с однотактным behavioral-ядром операнды/знак/экспоненты,
    //  использованные в обвязке, должны быть ВЫРОВНЕНЫ по той же задержке.
    //  Ниже — конвейер задержки метаданных на DSP_LAT тактов.
    // ====================================================================
    localparam DSP_LAT = 3;   // AREG(1)+MREG(1)+PREG(1)

    // знак, denorm-флаги, экспоненты, спец-классы — задержать на DSP_LAT
    wire result_sign_c = sa ^ sb;
    wire a_zero_c = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
    wire b_zero_c = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
    wire a_special_c = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}});
    wire b_special_c = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}});
    wire a_inf_c = a_special_c && (ma == {MANT_BITS{1'b0}});
    wire b_inf_c = b_special_c && (mb == {MANT_BITS{1'b0}});
    wire a_nan_c = a_special_c && (ma != {MANT_BITS{1'b0}});
    wire b_nan_c = b_special_c && (mb != {MANT_BITS{1'b0}});
    wire signed [EXP_BITS+1:0] ea_eff_c = a_denorm ? 1 : $signed({2'b00, ea});
    wire signed [EXP_BITS+1:0] eb_eff_c = b_denorm ? 1 : $signed({2'b00, eb});

    // упакованный вектор метаданных для конвейера
    localparam MW = 1 /*sign*/ + 1 /*az*/ + 1 /*bz*/ + 1 /*ainf*/ + 1 /*binf*/
                  + 1 /*anan*/ + 1 /*bnan*/ + (EXP_BITS+2) /*ea_eff*/ + (EXP_BITS+2) /*eb_eff*/;
    wire [MW-1:0] meta_in = { result_sign_c, a_zero_c, b_zero_c, a_inf_c, b_inf_c,
                              a_nan_c, b_nan_c, ea_eff_c, eb_eff_c };

    reg  [MW-1:0] meta_pipe [0:DSP_LAT-1];
    integer pi;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            for (pi = 0; pi < DSP_LAT; pi = pi + 1)
                meta_pipe[pi] <= {MW{1'b0}};
        end else begin
            meta_pipe[0] <= meta_in;
            for (pi = 1; pi < DSP_LAT; pi = pi + 1)
                meta_pipe[pi] <= meta_pipe[pi-1];
        end
    end

    wire [MW-1:0] meta_q = meta_pipe[DSP_LAT-1];
    wire                       result_sign = meta_q[MW-1];
    wire                       a_zero = meta_q[MW-2];
    wire                       b_zero = meta_q[MW-3];
    wire                       a_inf  = meta_q[MW-4];
    wire                       b_inf  = meta_q[MW-5];
    wire                       a_nan  = meta_q[MW-6];
    wire                       b_nan  = meta_q[MW-7];
    wire signed [EXP_BITS+1:0] ea_eff = meta_q[2*(EXP_BITS+2)-1 -: (EXP_BITS+2)];
    wire signed [EXP_BITS+1:0] eb_eff = meta_q[(EXP_BITS+2)-1   -: (EXP_BITS+2)];

    // ----- спец-коды -----
    localparam [TOTAL-1:0] CODE_PINF  = {1'b0, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
    localparam [TOTAL-1:0] CODE_NINF  = {1'b1, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
    localparam [TOTAL-1:0] CODE_NAN   = {1'b0, {EXP_BITS{1'b1}}, {{(MANT_BITS-1){1'b0}}, 1'b1}};
    localparam [TOTAL-1:0] CODE_PZERO = {TOTAL{1'b0}};
    localparam [TOTAL-1:0] CODE_NZERO = {1'b1, {(TOTAL-1){1'b0}}};

    // ----- комбинаторная FP-упаковка (ТА ЖЕ логика, что в gf_mul_param.v) -----
    reg  [TOTAL-1:0]            result_packed;
    integer                     k;
    reg  [PW-1:0]              p;
    reg  signed [EXP_BITS+3:0] er;
    reg  [MANT_BITS+2:0]      mant_field;
    reg                        guard, round_b, sticky;
    reg  [MANT_BITS+1:0]      mant_rnd;     // MANT+2 bits: ловим rounding carry (fix: было MANT+1 -> wrap терял exp++)
    reg  signed [EXP_BITS+3:0] exp_field;
    integer                     msb;

    always @(*) begin
        result_packed = CODE_PZERO;
        p = prod_dsp; er = ea_eff + eb_eff - BIAS;
        guard = 1'b0; round_b = 1'b0; sticky = 1'b0;
        mant_field = {(MANT_BITS+3){1'b0}}; mant_rnd = {(MANT_BITS+2){1'b0}};
        exp_field = 0; msb = 0;

        if (a_nan || b_nan) begin
            result_packed = CODE_NAN;
        end else if ((a_inf && b_zero) || (b_inf && a_zero)) begin
            result_packed = CODE_NAN;
        end else if (a_inf || b_inf) begin
            result_packed = result_sign ? CODE_NINF : CODE_PINF;
        end else if (a_zero || b_zero) begin
            result_packed = result_sign ? CODE_NZERO : CODE_PZERO;
        end else begin
            msb = -1;
            for (k = PW-1; k >= 0; k = k - 1)
                if (p[k] && msb == -1) msb = k;

            if (msb < 0) begin
                result_packed = result_sign ? CODE_NZERO : CODE_PZERO;
            end else begin
                exp_field = er + (msb - 2*MANT_BITS);
                if (exp_field < 1) begin
                    result_packed = pack_denorm(result_sign, p, er - BIAS, msb);
                end else begin
                    mant_field = 0;
                    for (k = 0; k <= MANT_BITS; k = k + 1)
                        if (msb - MANT_BITS + k >= 0)
                            mant_field[k] = p[msb - MANT_BITS + k];
                    guard   = (msb - MANT_BITS - 1 >= 0) ? p[msb - MANT_BITS - 1] : 1'b0;
                    round_b = (msb - MANT_BITS - 2 >= 0) ? p[msb - MANT_BITS - 2] : 1'b0;
                    sticky  = 1'b0;
                    for (k = 0; k <= PW-1; k = k + 1)
                        if (k < msb - MANT_BITS - 2 && k >= 0)
                            sticky = sticky | p[k];
                    if (guard && (round_b || sticky || mant_field[0]))
                        mant_rnd = mant_field[MANT_BITS:0] + 1'b1;
                    else
                        mant_rnd = mant_field[MANT_BITS:0];
                    if (mant_rnd > {1'b1, {MANT_BITS{1'b1}}}) begin
                        mant_rnd = mant_rnd >> 1;
                        exp_field = exp_field + 1;
                    end
                    if (HAS_INF != 0) begin
                        if (exp_field >= $signed({1'b0, {EXP_BITS{1'b1}}}))
                            result_packed = result_sign ? CODE_NINF : CODE_PINF;
                        else
                            result_packed = {result_sign, exp_field[EXP_BITS-1:0],
                                             mant_rnd[MANT_BITS-1:0]};
                    end else begin
                        if (exp_field > $signed({1'b0, {EXP_BITS{1'b1}}}))
                            result_packed = {result_sign, {EXP_BITS{1'b1}}, {MANT_BITS{1'b1}}};
                        else
                            result_packed = {result_sign, exp_field[EXP_BITS-1:0],
                                             mant_rnd[MANT_BITS-1:0]};
                    end
                end
            end
        end
    end

    // ----- денормал-упаковка (ИДЕНТИЧНА gf_mul_param.v) -----
    function [TOTAL-1:0] pack_denorm;
        input                         sgn;
        input [PW-1:0]               pr;
        input signed [EXP_BITS+3:0]   er_real;
        input integer                 msb_in;
        integer p_sh, sh;
        reg [MANT_BITS+1:0]  mant_out;
        reg gd, st, lsbf;
        begin
            if (BIAS == 0) begin
                pack_denorm = sgn ? CODE_NZERO : CODE_PZERO;
            end else begin
                p_sh = er_real - MANT_BITS + BIAS - 1;
                if (p_sh >= 0) begin
                    mant_out = (pr << p_sh);
                    pack_denorm = pack_denorm_final(sgn, mant_out);
                end else begin
                    sh = -p_sh;
                    if (sh >= msb_in + 3) begin
                        pack_denorm = sgn ? CODE_NZERO : CODE_PZERO;
                    end else begin
                        gd = pr[sh-1];
                        st = 1'b0;
                        for (k = 0; k <= PW-1; k = k + 1)
                            if (k < sh-1 && k >= 0)
                                st = st | pr[k];
                        mant_out = pr >> sh;
                        lsbf = mant_out[0];
                        if (gd && (st || lsbf))
                            mant_out = mant_out + 1'b1;
                        pack_denorm = pack_denorm_final(sgn, mant_out);
                    end
                end
            end
        end
    endfunction

    function [TOTAL-1:0] pack_denorm_final;
        input                     sgn;
        input [MANT_BITS+1:0]    mout;
        begin
            if (mout >= (1 << MANT_BITS))
                pack_denorm_final = {sgn, {(EXP_BITS-1){1'b0}}, 1'b1, {MANT_BITS{1'b0}}};
            else if (mout == 0)
                pack_denorm_final = sgn ? CODE_NZERO : CODE_PZERO;
            else
                pack_denorm_final = {sgn, {EXP_BITS{1'b0}}, mout[MANT_BITS-1:0]};
        end
    endfunction

    // ----- AXI-Stream выходной регистр + valid с учётом DSP-латентности -----
    //   in_valid конвейеризуется на DSP_LAT тактов, чтобы out_valid поднимался
    //   когда соответствующий prod_dsp готов на выходе DSP48E1.
    reg  [DSP_LAT-1:0] vpipe;
    always @(posedge clk or posedge rst) begin
        if (rst) vpipe <= {DSP_LAT{1'b0}};
        else     vpipe <= { vpipe[DSP_LAT-2:0], (in_valid && in_ready) };
    end
    wire result_valid = vpipe[DSP_LAT-1];

    reg [TOTAL-1:0] out_reg;
    reg             out_valid_reg;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            out_reg <= {TOTAL{1'b0}}; out_valid_reg <= 1'b0;
        end else begin
            if (out_valid_reg && out_ready) out_valid_reg <= 1'b0;
            if (result_valid) begin
                out_reg <= result_packed; out_valid_reg <= 1'b1;
            end
        end
    end
    // ПРОСТОЙ ready: конвейер DSP не имеет back-pressure внутри -> допускаем приём,
    //   когда выход свободен. Для строгого AXI-стопа нужен skid-буфер (бэклог).
    assign in_ready  = ~out_valid_reg | out_ready;
    assign out_valid = out_valid_reg;
    always @(*) out_y = out_reg;
endmodule

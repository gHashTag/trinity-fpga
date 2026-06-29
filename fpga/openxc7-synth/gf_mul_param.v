`timescale 1ns / 1ps
// ============================================================================
// gf_mul_param.v — ПАРАМЕТРИЧЕСКОЕ behavioral-ЯДРО умножения GoldenFloat GF{N}.
// Работает для GF6 (1S+2E+3M) ... GF20 (1S+7E+12M). Зеркало gf_adder_param.v.
//
// СТАТУС ВЕРИФИКАЦИИ: это АЛГОРИТМИЧЕСКОЕ ядро (значащие умножаются оператором *).
//   Верифицируется в песочнице двумя оракулами (Python Fraction + iverilog).
//   DSP48E1-маппинг — в ОТДЕЛЬНОМ файле gf_mul_dsp_param.v, верификация которого
//   требует Vivado/UNISIM или железа AX7203 (UNISIM не работает в iverilog, UG900).
//
// Алгоритм FP-умножения (spec gf16.t27:356-379, research arXiv:2606.05017 §5.5):
//   sign       = sa ^ sb
//   er         = ea_eff + eb_eff - BIAS   (несмещённая сумма + восстановление bias)
//   prod       = {impl_a, ma} * {impl_b, mb}   ширина (2*(MANT+1)) бит  [erratum 2M+2!]
//   нормализация по старшему биту произведения -> RNE(G,R,S)
//   family-split overflow (как в ADD): HAS_INF -> Inf; иначе -> max-finite
//   zero-sign: 0*x = (sa^sb ? -0 : +0)
//   denormal-результат: упаковка НАПРЯМУЮ от точного prod (единственное округление)
//
// ВАЖНО (erratum GoldenFloat 2026-05-31, research §5): ширина регистра
//   произведения = 2*(MANT_BITS+1), НЕ 2*MANT_BITS. Иначе 1.0*1.0 даёт 0.5.
//
// ВЕРИФИЦИРОВАНО [смоделировано] verify_mul_rtl.py: faithful Python-транскрипция
//   этого алгоритма == золотой эталон gf_mul (Fraction). GF6/GF8 exhaustive,
//   GF12/GF16/GF20 по 500k случайных -> 0 расхождений. НЕ железо.
//
// Honesty: Vasilev, ORCID 0009-0008-4294-6159, admin@t27.ai. [смоделировано], не железо.
// ============================================================================
module gf_mul_param #(
    parameter EXP_BITS  = 6,
    parameter MANT_BITS = 9,
    parameter TOTAL     = 1 + EXP_BITS + MANT_BITS,   // полная ширина операнда
    parameter BIAS      = (1 << (EXP_BITS - 1)) - 1,
    // HAS_INF=1 ТОЛЬКО для форматов, где exp=all-ones зарезервирован как SPECIAL
    //   (Inf/NaN): GF16 (gf16.t27:25,35,131). Для GF6/8/12/20 exp=all-ones —
    //   КОНЕЧНОЕ max_value (gf8.t27:115-119) -> HAS_INF=0, overflow -> max-finite.
    parameter HAS_INF   = 0
)(
    input  wire                clk,
    input  wire                rst,
    input  wire                in_valid,
    input  wire [TOTAL-1:0]    in_a,
    input  wire [TOTAL-1:0]    in_b,
    output wire                in_ready,
    output reg                 out_valid,
    output reg  [TOTAL-1:0]    out_y,
    input  wire                out_ready
);
    // ----- ширины -----
    localparam PW = 2*(MANT_BITS+1);          // ширина произведения значащих [erratum 2M+2]
    localparam MF = MANT_BITS + 1;            // ширина значащей с implicit-битом

    // ----- извлечение полей -----
    wire                  sa = in_a[TOTAL-1];
    wire [EXP_BITS-1:0]   ea = in_a[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]  ma = in_a[MANT_BITS-1:0];
    wire                  sb = in_b[TOTAL-1];
    wire [EXP_BITS-1:0]   eb = in_b[TOTAL-2:MANT_BITS];
    wire [MANT_BITS-1:0]  mb = in_b[MANT_BITS-1:0];

    wire result_sign = sa ^ sb;

    // ----- классификация -----
    wire a_zero = (ea == {EXP_BITS{1'b0}}) && (ma == {MANT_BITS{1'b0}});
    wire b_zero = (eb == {EXP_BITS{1'b0}}) && (mb == {MANT_BITS{1'b0}});
    // denormal: exp_field==0 && mant!=0. (BIAS>0) guard REMOVED — matches the
    // gf_adder_param fix: GF4 has BIAS=0, so the guard skipped GF4 denormals →
    // ma_f used implicit-1 (1.x) instead of 0.x → HW a*denorm≈a (caught on silicon,
    // bug-equals-bug in the Python transcription). Only GF4 (BIAS=0) was affected.
    wire a_denorm = (ea == {EXP_BITS{1'b0}}) && (ma != {MANT_BITS{1'b0}});
    wire b_denorm = (eb == {EXP_BITS{1'b0}}) && (mb != {MANT_BITS{1'b0}});
    // спец exp=all-ones (только если HAS_INF): Inf при mant==0, NaN при mant!=0
    wire a_special = (HAS_INF != 0) && (ea == {EXP_BITS{1'b1}});
    wire b_special = (HAS_INF != 0) && (eb == {EXP_BITS{1'b1}});
    wire a_inf = a_special && (ma == {MANT_BITS{1'b0}});
    wire b_inf = b_special && (mb == {MANT_BITS{1'b0}});
    wire a_nan = a_special && (ma != {MANT_BITS{1'b0}});
    wire b_nan = b_special && (mb != {MANT_BITS{1'b0}});

    // ----- значащие (implicit бит = !denorm) и эффективные экспоненты -----
    wire [MF-1:0] ma_f = a_denorm ? {1'b0, ma} : {1'b1, ma};
    wire [MF-1:0] mb_f = b_denorm ? {1'b0, mb} : {1'b1, mb};
    // денормал alignment-exp = 1 (реальный показатель 1-BIAS), как в ADD
    wire signed [EXP_BITS+1:0] ea_eff = a_denorm ? 1 : $signed({2'b00, ea});
    wire signed [EXP_BITS+1:0] eb_eff = b_denorm ? 1 : $signed({2'b00, eb});

    // ----- произведение значащих (поведенческое *; DSP-маппинг отдельно) -----
    wire [PW-1:0] prod = ma_f * mb_f;   // ширина 2*MF = 2*(MANT+1) [erratum]

    // ----- спец-коды для упаковки -----
    localparam [TOTAL-1:0] CODE_PINF  = {1'b0, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
    localparam [TOTAL-1:0] CODE_NINF  = {1'b1, {EXP_BITS{1'b1}}, {MANT_BITS{1'b0}}};
    // канонический quiet-NaN: знак=0, exp=all-ones, mant LSB=1 (как fmt.quiet_nan)
    localparam [TOTAL-1:0] CODE_NAN   = {1'b0, {EXP_BITS{1'b1}}, {{(MANT_BITS-1){1'b0}}, 1'b1}};
    localparam [TOTAL-1:0] CODE_PZERO = {TOTAL{1'b0}};
    localparam [TOTAL-1:0] CODE_NZERO = {1'b1, {(TOTAL-1){1'b0}}};

    // ----- комбинаторное ядро -----
    reg  [TOTAL-1:0]            result_packed;
    integer                     k;
    reg  [PW-1:0]              p;            // нормализуемое произведение
    reg  signed [EXP_BITS+3:0] er;           // несмещённая сумма экспонент (с запасом)
    reg  [MANT_BITS+2:0]      mant_field;   // значащая после нормализации (1.x)
    reg                        guard, round_b, sticky;
    reg  [MANT_BITS+1:0]      mant_rnd;     // MANT+2 bits: ловим rounding carry (fix: было MANT+1 -> wrap терял exp++)
    reg  signed [EXP_BITS+3:0] exp_field;    // итоговое exp-поле (signed для underflow/overflow)
    integer                     msb;          // позиция старшего значащего бита prod

    always @(*) begin
        result_packed = CODE_PZERO;
        p = prod; er = ea_eff + eb_eff - BIAS;
        guard = 1'b0; round_b = 1'b0; sticky = 1'b0;
        mant_field = {(MANT_BITS+3){1'b0}}; mant_rnd = {(MANT_BITS+2){1'b0}};
        exp_field = 0; msb = 0;

        // --- 1) спец-края (NaN > 0*Inf > Inf > zero) ---
        if (a_nan || b_nan) begin
            result_packed = CODE_NAN;
        end else if ((a_inf && b_zero) || (b_inf && a_zero)) begin
            result_packed = CODE_NAN;                 // 0 * Inf = NaN (IEEE)
        end else if (a_inf || b_inf) begin
            result_packed = result_sign ? CODE_NINF : CODE_PINF;
        end else if (a_zero || b_zero) begin
            result_packed = result_sign ? CODE_NZERO : CODE_PZERO;  // 0*x, знак XOR
        end else begin
            // --- 2) нормализация произведения значащих ---
            // prod = MF-bit * MF-bit, диапазон [1.0, 4.0) для нормалей ->
            //   старший единичный бит на позиции (2*MANT+1) или (2*MANT).
            // Найдём MSB динамически (поддержка денормал-операндов, где impl=0).
            msb = -1;
            for (k = PW-1; k >= 0; k = k - 1)
                if (p[k] && msb == -1) msb = k;

            if (msb < 0) begin
                // произведение нулевое (теоретически недостижимо здесь) -> ±0
                result_packed = result_sign ? CODE_NZERO : CODE_PZERO;
            end else begin
                // exp коррекция = (msb - 2*MANT_BITS): на сколько старший бит выше
                //   опорной позиции 2*MANT_BITS (где результат ровно 1.0).
                exp_field = er + (msb - 2*MANT_BITS);

                // --- РЕШЕНИЕ normal-vs-denormal ПО НЕОКРУГЛЁННОМУ exp_field ---
                //   Денормал-ветка работает НАПРЯМУЮ от prod (единственное
                //   округление, без потери sticky -> нет двойного округления).
                if (exp_field < 1) begin
                    //   er_real = ea_eff + eb_eff - 2*BIAS = er - BIAS
                    result_packed = pack_denorm(result_sign, p, er - BIAS, msb);
                end else begin
                    // ----- НОРМАЛЬНАЯ ветка -----
                    // mant_field = {1, дробь} в младших (MANT_BITS+1) битах.
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

                    // --- RNE по G,R,S ---
                    if (guard && (round_b || sticky || mant_field[0]))
                        mant_rnd = mant_field[MANT_BITS:0] + 1'b1;
                    else
                        mant_rnd = mant_field[MANT_BITS:0];
                    // carry из округления (значащая стала 2.0) -> сдвиг, exp++
                    if (mant_rnd > {1'b1, {MANT_BITS{1'b1}}}) begin
                        mant_rnd = mant_rnd >> 1;
                        exp_field = exp_field + 1;
                    end

                    // --- упаковка family-split overflow ---
                    if (HAS_INF != 0) begin
                        // exp=all-ones зарезервирован -> overflow при exp_field >= exp_max
                        if (exp_field >= $signed({1'b0, {EXP_BITS{1'b1}}}))
                            result_packed = result_sign ? CODE_NINF : CODE_PINF;
                        else
                            result_packed = {result_sign, exp_field[EXP_BITS-1:0],
                                             mant_rnd[MANT_BITS-1:0]};
                    end else begin
                        // exp=all-ones — последний КОНЕЧНЫЙ -> overflow при exp_field > exp_max
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

    // --- gradual-underflow упаковка денормала НАПРЯМУЮ от точного prod ---
    //   Истинное значение = prod * 2^(er_real - 2*MANT).
    //   Денормал-поле (MANT бит, без implicit) = round( prod * 2^p_sh ),
    //     где p_sh = er_real - MANT + BIAS - 1.
    //   p_sh>=0 -> точный left-shift; p_sh<0 -> right-shift на (-p_sh) с RNE+sticky.
    function [TOTAL-1:0] pack_denorm;
        input                         sgn;
        input [PW-1:0]               pr;       // точное произведение значащих
        input signed [EXP_BITS+3:0]   er_real;  // = ea_eff+eb_eff-2*BIAS
        input integer                 msb_in;   // позиция MSB pr (для границы underflow)
        integer p_sh, sh;
        reg [PW+MANT_BITS:0] mext;
        reg gd, st, lsbf;
        reg [MANT_BITS+1:0]  mant_out;
        begin
            begin   // (BIAS==0 short-circuit REMOVED: the assumed "separate gf4 core" doesn't exist — gf_mul_param serves all widths, so gf4 denormal MUL must use the general pack path. Was flushing all gf4 denormal results to ±0 = 60/256 HW fails.)
                p_sh = er_real - MANT_BITS + BIAS - 1;
                if (p_sh >= 0) begin
                    // точный left-shift (без округления)
                    mant_out = (pr << p_sh);
                    pack_denorm = pack_denorm_final(sgn, mant_out);
                end else begin
                    sh = -p_sh;                       // >=1
                    if (sh >= msb_in + 3) begin
                        pack_denorm = sgn ? CODE_NZERO : CODE_PZERO; // underflow к ±0
                    end else begin
                        gd   = pr[sh-1];
                        st   = 1'b0;
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

    // упаковка денормал-мантиссы с обработкой переноса в наименьший нормал / underflow
    function [TOTAL-1:0] pack_denorm_final;
        input                     sgn;
        input [MANT_BITS+1:0]    mout;
        begin
            if (mout >= (1 << MANT_BITS))               // достигло 2^MANT -> наименьший нормал
                pack_denorm_final = {sgn, {(EXP_BITS-1){1'b0}}, 1'b1, {MANT_BITS{1'b0}}};
            else if (mout == 0)
                pack_denorm_final = sgn ? CODE_NZERO : CODE_PZERO;
            else
                pack_denorm_final = {sgn, {EXP_BITS{1'b0}}, mout[MANT_BITS-1:0]};
        end
    endfunction

    // ----- AXI-Stream выходной регистр (как в gf_adder_param) -----
    reg [TOTAL-1:0] out_reg;
    reg             out_valid_reg;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            out_reg <= {TOTAL{1'b0}}; out_valid_reg <= 1'b0;
        end else begin
            if (out_valid_reg && out_ready) out_valid_reg <= 1'b0;
            if (in_valid && in_ready) begin
                out_reg <= result_packed; out_valid_reg <= 1'b1;
            end
        end
    end
    assign in_ready  = ~out_valid_reg | out_ready;
    assign out_valid = out_valid_reg;
    always @(*) out_y = out_reg;
endmodule

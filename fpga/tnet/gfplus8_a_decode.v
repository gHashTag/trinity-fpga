// SPDX-License-Identifier: Apache-2.0
// gfplus8_a_decode — GF+A (adaptive) 8-бит контейнер -> FP32 decode.
// [prep для LUT-замера, вектор 4]. НЕ Tier-E: до UART-прогона на AX7203.
//
// Контейнер: 2-битный заголовок (pocket sel) выбирает один из 4 карманов класса-8:
//   00 = phi_e3m4  (1S+3E+4M, bias=3)     — φ-сплит
//   01 = e2m5      (1S+2E+5M, bias=1)     — узкая экспонента (лучший на гауссе)
//   10 = int8      (симметричный fixed)   — равномерная сетка (лучший на uniform)
//   11 = lns8      (логарифмический)       — тяжёлые хвосты (вектор 3, живой слот)
// Полезная нагрузка = 8-бит слово. Заголовок приходит отдельным сигналом pocket
// (в реальном контейнере хранится 1 раз на группу из K строк — см. gfplus_adaptive_v2.py).
//
// Все 4 карман-декодера раскрываются параллельно, финальный mux выбирает по pocket.
// Именно площадь (LUT) этого mux+4путей — предмет замера vs одиночный фикс-декодер.
`default_nettype none
`timescale 1ns / 1ps

module gfplus8_a_decode (
    input  wire [7:0]  word_in,   // 8-бит полезная нагрузка
    input  wire [1:0]  pocket,    // выбор кармана (заголовок)
    output reg  [31:0] fp32_out,
    output wire        is_zero
);
    wire sign = word_in[7];
    wire [6:0] mag = word_in[6:0];

    // ─────────── карман 00: phi_e3m4 (3E,4M,bias=3, has_inf=0) ───────────
    wire [2:0] p0_exp  = word_in[6:4];
    wire [3:0] p0_mant = word_in[3:0];
    wire p0_zero = (p0_exp == 3'd0) && (p0_mant == 4'd0);
    reg  [7:0]  p0_fexp; reg [22:0] p0_fmant;
    always @(*) begin
        if (p0_zero) begin p0_fexp = 8'h00; p0_fmant = 23'h0; end
        else if (p0_exp == 3'd0) begin
            casez (p0_mant)
                4'b1???: begin p0_fexp = 8'd124; p0_fmant = {p0_mant[2:0], 20'b0}; end
                4'b01??: begin p0_fexp = 8'd123; p0_fmant = {p0_mant[1:0], 21'b0}; end
                4'b001?: begin p0_fexp = 8'd122; p0_fmant = {p0_mant[0],   22'b0}; end
                default: begin p0_fexp = 8'd121; p0_fmant = 23'b0;               end
            endcase
        end else begin
            p0_fexp  = {5'b0, p0_exp} + 8'd124;   // exp-3+127
            p0_fmant = {p0_mant, 19'b0};
        end
    end
    wire [31:0] dec0 = {sign, p0_fexp, p0_fmant};

    // ─────────── карман 01: e2m5 (2E,5M,bias=1, has_inf=0) ───────────
    wire [1:0] p1_exp  = word_in[6:5];
    wire [4:0] p1_mant = word_in[4:0];
    wire p1_zero = (p1_exp == 2'd0) && (p1_mant == 5'd0);
    reg  [7:0]  p1_fexp; reg [22:0] p1_fmant;
    always @(*) begin
        if (p1_zero) begin p1_fexp = 8'h00; p1_fmant = 23'h0; end
        else if (p1_exp == 2'd0) begin
            casez (p1_mant)
                5'b1????: begin p1_fexp = 8'd126; p1_fmant = {p1_mant[3:0], 19'b0}; end
                5'b01???: begin p1_fexp = 8'd125; p1_fmant = {p1_mant[2:0], 20'b0}; end
                5'b001??: begin p1_fexp = 8'd124; p1_fmant = {p1_mant[1:0], 21'b0}; end
                5'b0001?: begin p1_fexp = 8'd123; p1_fmant = {p1_mant[0],   22'b0}; end
                default:  begin p1_fexp = 8'd122; p1_fmant = 23'b0;               end
            endcase
        end else begin
            p1_fexp  = {6'b0, p1_exp} + 8'd126;   // exp-1+127
            p1_fmant = {p1_mant, 18'b0};
        end
    end
    wire [31:0] dec1 = {sign, p1_fexp, p1_fmant};

    // ─────────── карман 10: int8 (симметричный, 7-бит магнитуда / 127) ───────────
    // value = mag/127 в [0,1]; FP32 = mag * 2^-7 (приближённо, нормализуем ведущей 1).
    reg  [7:0]  p2_fexp; reg [22:0] p2_fmant;
    wire p2_zero = (mag == 7'd0);
    always @(*) begin
        if (p2_zero) begin p2_fexp = 8'h00; p2_fmant = 23'h0; end
        else begin
            casez (mag)
                7'b1??????: begin p2_fexp = 8'd127; p2_fmant = {mag[5:0], 17'b0}; end // 1.x
                7'b01?????: begin p2_fexp = 8'd126; p2_fmant = {mag[4:0], 18'b0}; end
                7'b001????: begin p2_fexp = 8'd125; p2_fmant = {mag[3:0], 19'b0}; end
                7'b0001???: begin p2_fexp = 8'd124; p2_fmant = {mag[2:0], 20'b0}; end
                7'b00001??: begin p2_fexp = 8'd123; p2_fmant = {mag[1:0], 21'b0}; end
                7'b000001?: begin p2_fexp = 8'd122; p2_fmant = {mag[0],   22'b0}; end
                default:    begin p2_fexp = 8'd121; p2_fmant = 23'b0;             end
            endcase
        end
    end
    wire [31:0] dec2 = {sign, p2_fexp, p2_fmant};

    // ─────────── карман 11: lns8 (лог, 7-бит индекс; value = 2^(idx*step + LMIN)) ───────────
    // Прямая реализация: exp_field = LMIN_int + idx (линейно), mant = 0 (степень двойки-приближение).
    // step = 8/127 ~ 0.063; для LUT-замера достаточно exp-домена (mant=0 = грубая lns-сетка).
    wire [6:0] p3_idx = mag;
    wire p3_zero = (p3_idx == 7'd0);
    // exp8 = 127 - round((127-idx)*8/127); аппрокс: 127 - ((127-idx)>>4) - ((127-idx)>>6)
    wire [6:0] inv = 7'd127 - p3_idx;
    wire [7:0] shift = {1'b0, inv[6:4]} + {5'b0, inv[6:5]}; // ~inv*8/127 приближённо
    reg  [7:0] p3_fexp;
    always @(*) begin
        if (p3_zero) p3_fexp = 8'h00;
        else p3_fexp = 8'd127 - shift;
    end
    wire [31:0] dec3 = {sign, p3_fexp, 23'b0};

    // ─────────── финальный mux по заголовку ───────────
    always @(*) begin
        case (pocket)
            2'b00: fp32_out = dec0;
            2'b01: fp32_out = dec1;
            2'b10: fp32_out = dec2;
            default: fp32_out = dec3;
        endcase
    end

    assign is_zero = (pocket == 2'b00) ? p0_zero :
                     (pocket == 2'b01) ? p1_zero :
                     (pocket == 2'b10) ? p2_zero : p3_zero;

endmodule

`default_nettype wire

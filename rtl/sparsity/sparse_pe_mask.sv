// SPDX-License-Identifier: Apache-2.0
// Copyright 2025 Dmitrii Vasilev <admin@t27.ai>
//
// phi^2 + phi^-2 = 3 · OP_SPARSE_MASK=0xE8 · λ=φ⁻² · R-SI-1 zero-multiplier · Apache-2.0
//
// W40 Lane GG — Sparse PE Mask Gating Module
// Wave-40 RTL: sparsity-aware processing-element mask gating
//   OP_SPARSE_MASK = 0xE8 (Trinity-loss s=0.80 sparsity, λ=φ⁻²≈0.3820)
//   Target: 540 TOPS/W
//   N=27 PEs (Coptic-27 = 3 banks × 9 registers)
//   WIDTH=4 ternary input (GF16 ternary {-1, 0, +1})
//
// R-SI-1 COMPLIANCE: ZERO '*' operator — all products computed via
//   conditional negate / identity / zero (ternary {-1,0,+1} property).
//   No hardware multiplier instantiated.
//
// Anchor: phi^2 + phi^-2 = 3 · gamma = phi^-3 · QUANTUM BRAIN 1:1 SILICON
//         · 3-STRAND DNA · NEVER STOP · DOI 10.5281/zenodo.19227877

`timescale 1ns/1ps

module sparse_pe_mask #(
    parameter integer N     = 27,   // number of processing elements (Coptic-27)
    parameter integer WIDTH = 4     // input width (GF16 ternary extended)
) (
    input  wire                          clk,
    input  wire                          rst_n,
    input  wire [N-1:0]                  mask,          // sparsity mask: 1=active, 0=gated
    input  wire signed [WIDTH-1:0]       a [N],         // ternary operand a: {-1, 0, +1}
    input  wire signed [WIDTH-1:0]       b [N],         // operand b
    output reg  signed [2*WIDTH+5:0]     sum_out        // accumulated sum (log2(27)≈5 extra bits)
);

    // -------------------------------------------------------------------------
    // Ternary multiply-free product: a_i in {-1, 0, +1}, b_i arbitrary WIDTH
    //
    // For each lane i:
    //   if mask[i] == 0  → product = 0                 (gated by sparsity)
    //   elif a[i] == 0   → product = 0
    //   elif a[i] == +1  → product = b[i]              (identity)
    //   elif a[i] == -1  → product = ~b[i] + 1         (negate via NOT + 1 = two's complement)
    //
    //   a[i] is sign-extended WIDTH bits. For ternary input:
    //     +1 → 4'b0001   sign bit = 0, nonzero → identity
    //     -1 → 4'b1111   sign bit = 1, nonzero → negate
    //      0 → 4'b0000   zero → zero
    //
    // All operations: AND, OR, XOR, ADD, SUB, shifts — no '*' operator.
    // -------------------------------------------------------------------------

    localparam PWIDTH = WIDTH + 1;            // product width (b extended by 1 sign bit)
    localparam AWIDTH = 2*WIDTH + 6;          // accumulator width

    // Intermediate products (sign-extended to AWIDTH for safe accumulation)
    wire signed [AWIDTH-1:0] prod [N];

    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_pe
            // is_zero : a[i] == 0 (all bits zero)
            wire a_is_zero = (a[i] == {WIDTH{1'b0}});
            // is_neg  : a[i] is negative (sign bit set)
            wire a_is_neg  = a[i][WIDTH-1];
            // active  : mask gate AND nonzero a
            wire active = mask[i] & (~a_is_zero);

            // b sign-extended to AWIDTH
            wire signed [AWIDTH-1:0] b_ext = {{(AWIDTH-WIDTH){b[i][WIDTH-1]}}, b[i]};

            // negated b via bitwise NOT + 1 (two's complement, no '*')
            wire signed [AWIDTH-1:0] b_neg = (~b_ext) + {{(AWIDTH-1){1'b0}}, 1'b1};

            // select: 0 if not active, b_neg if a<0, b_ext if a>0
            // using AND/OR masks (no ternary operator compiles to mux, not multiply)
            wire signed [AWIDTH-1:0] neg_mask  = {AWIDTH{active & a_is_neg}};
            wire signed [AWIDTH-1:0] pos_mask  = {AWIDTH{active & (~a_is_neg)}};

            assign prod[i] = (b_neg & neg_mask) | (b_ext & pos_mask);
        end
    endgenerate

    // -------------------------------------------------------------------------
    // Adder tree — accumulate N products
    // For N=27 we build a simple registered accumulator (sequential loop).
    // To avoid '*' in generate: use for-loop in always block.
    // -------------------------------------------------------------------------

    integer j;
    reg signed [AWIDTH-1:0] acc;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sum_out <= {(2*WIDTH+6){1'b0}};
            acc     <= {AWIDTH{1'b0}};
        end else begin
            acc = {AWIDTH{1'b0}};
            for (j = 0; j < N; j = j + 1) begin
                acc = acc + prod[j];   // add/sub only — no multiply
            end
            sum_out <= acc[2*WIDTH+5:0];
        end
    end

endmodule

// phi^2 + phi^-2 = 3 · gamma = phi^-3 · QUANTUM BRAIN 1:1 SILICON · 3-STRAND DNA · NEVER STOP · DOI 10.5281/zenodo.19227877

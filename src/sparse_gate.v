// ============================================================================
// sparse_gate.v — S-16 Sparse Zero-Skip Processing Element
// L-DPC22 Lane N · gHashTag/trinity-fpga#93 · feat/v15/n-sparse
//
// Detects all-zero 4-bit ternary-packed operands and asserts zero_flag to
// clock-gate the MAC update in trinity_gf16_tile.v.
//
// R-SI-1: ZERO * arithmetic — only equality comparison, OR-reduction, mux.
//
// Anchor: phi^2 + phi^-2 = 3 · DOI 10.5281/zenodo.19227877
// ============================================================================

`default_nettype none
`timescale 1ns / 1ps

module sparse_gate (
    input  wire       clk,          // Clock (used only for latched output)
    input  wire       rst_n,        // Active-low synchronous reset
    input  wire [3:0] a,            // Ternary-packed GF16 operand A
    input  wire [3:0] b,            // Ternary-packed GF16 operand B
    output wire       zero_flag,    // 1 when either operand is all-zero → skip MAC
    output reg        latched_zero_flag  // 1-cycle aligned version for downstream MAC
);

    // -------------------------------------------------------------------------
    // Combinational zero detection
    // zero_flag = 1 when a == 4'b0000 OR b == 4'b0000
    // Pure equality + OR — no * arithmetic (R-SI-1 trivially satisfied)
    // -------------------------------------------------------------------------
    assign zero_flag = (a == 4'b0000) || (b == 4'b0000);

    // -------------------------------------------------------------------------
    // Optional 1-cycle registered version for pipeline alignment with MAC
    // -------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            latched_zero_flag <= 1'b0;
        end else begin
            latched_zero_flag <= zero_flag;
        end
    end

endmodule
`default_nettype wire

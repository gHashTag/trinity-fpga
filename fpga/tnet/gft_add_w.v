// tef_add with widths derived from the format parameters.
//
// The original declares every port and every intermediate 32 bits wide and masks
// the alignment shift to five bits (`d[4:0]`). Both are fine at TEF16 and both
// break higher up:
//
//   * `sum` holds (MANT_ONE + hi_m) + sb, which reaches 2^(MANT_W+2). At TEF64
//     that is 54 bits in a 32-bit wire.
//   * `d[4:0]` wraps for d >= 32. The guard `d >= SIG_BITS` hides it only while
//     SIG_BITS <= 32; at TEF64, SIG_BITS is 53, so differences in [32, 53) take
//     a shift of d-32 instead of d.
//
// Nothing here changes the arithmetic. The widths are the size of the values, and
// the shift amount is wide enough to hold what it shifts by.

`timescale 1ns / 1ps
`default_nettype none

module tef_add_w #(
    parameter integer MANT_W     = 9,
    parameter integer OFF_W      = 7,
    parameter [31:0]  OFFSET_MAX = 80
) (
    input  wire [OFF_W-1:0]  a_off,
    input  wire [MANT_W-1:0] a_mant,
    input  wire [OFF_W-1:0]  b_off,
    input  wire [MANT_W-1:0] b_mant,
    output wire [OFF_W-1:0]  out_off,
    output wire [MANT_W-1:0] out_mant
);
  localparam integer SIG_W = MANT_W + 1;   // 1.M
  localparam integer SUM_W = MANT_W + 2;   // room for the carry out of the add
  localparam integer SH_W  = (OFF_W > 5) ? OFF_W : 5;

  wire            a_hi   = (a_off >= b_off);
  wire [OFF_W-1:0]  hi_off = a_hi ? a_off  : b_off;
  wire [MANT_W-1:0] hi_m   = a_hi ? a_mant : b_mant;
  wire [OFF_W-1:0]  lo_off = a_hi ? b_off  : a_off;
  wire [MANT_W-1:0] lo_m   = a_hi ? b_mant : a_mant;

  // Full-width difference: no five-bit mask, so no wrap for wide rungs.
  wire [SH_W-1:0] d = {{(SH_W-OFF_W){1'b0}}, hi_off} - {{(SH_W-OFF_W){1'b0}}, lo_off};

  wire [SIG_W-1:0] lo_sig = {1'b1, lo_m};
  wire [SIG_W-1:0] sb     = (d >= SIG_W) ? {SIG_W{1'b0}} : (lo_sig >> d);
  wire [SUM_W-1:0] sum    = {1'b0, 1'b1, hi_m} + {{(SUM_W-SIG_W){1'b0}}, sb};

  wire carry = sum[SUM_W-1];                       // sum >= 2*MANT_ONE
  wire [OFF_W:0] e = {1'b0, hi_off} + 1'b1;

  assign out_off  = carry ? ((e >= OFFSET_MAX[OFF_W:0]) ? OFFSET_MAX[OFF_W-1:0] : e[OFF_W-1:0])
                          : hi_off;
  assign out_mant = carry ? sum[SUM_W-2 -: MANT_W]  // (sum >> 1) - MANT_ONE
                          : sum[MANT_W-1:0];       // sum - MANT_ONE
endmodule
`default_nettype wire

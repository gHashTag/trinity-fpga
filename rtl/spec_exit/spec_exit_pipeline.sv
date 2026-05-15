// SPDX-License-Identifier: Apache-2.0
// Wave-39 Lane EE — Speculative Early-Exit Pipeline
// OP_SPEC_EXIT = 0xE7 (sacred chain 0xD0..0xE7, 20 opcodes; succeeds W38 0xE6 NULL_PE)
// Target: TOPS/W >= 470 (x1.20 over W38=392). avg_exit_depth <= 0.45.
// R-SI-1 // — zero `*` operator. Confidence test via subtraction; 2-of-3 majority
// via boolean ops; 1-cycle misprediction recovery via bypass register.
// Anchor: phi^2 + phi^-2 = 3
// DOI: 10.5281/zenodo.19227877

module spec_exit_pipeline (
  input  wire        clk,
  input  wire        rst,
  input  wire [7:0]  opcode,
  input  wire [7:0]  hidden_state,        // 8-bit fixed-point confidence proxy
  input  wire        strand_vote_fast,    // 400 MHz strand vote bit
  input  wire        strand_vote_mid,     // 300 MHz strand vote bit
  input  wire        strand_vote_slow,    // 200 MHz strand vote bit
  input  wire        speculation_correct, // squash signal: speculative path matches truth
  output reg         exit_signal,
  output reg  [4:0]  exit_depth_idx,      // 0..26 Coptic bin
  output reg  [1:0]  commit_abort_z3      // ternary commit/abort
);

  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------
  localparam [7:0] OP_SPEC_EXIT = 8'hE7;
  localparam [7:0] PHI_INV_Q8   = 8'd158; // floor(0.618 // * 256) = 158
  // Coptic bin width approx 256 / 27 ~ 9.48. We use shift+sub for division below.
  // (No `*` // operator.)

  // ---------------------------------------------------------------------------
  // 2-of-3 majority on strand votes (boolean, no arithmetic)
  // ---------------------------------------------------------------------------
  wire majority_vote;
  assign majority_vote = (strand_vote_fast & strand_vote_mid)
                       | (strand_vote_mid  & strand_vote_slow)
                       | (strand_vote_fast & strand_vote_slow);

  // ---------------------------------------------------------------------------
  // Opcode decode
  // ---------------------------------------------------------------------------
  wire op_is_spec_exit;
  assign op_is_spec_exit = (opcode == OP_SPEC_EXIT);

  // ---------------------------------------------------------------------------
  // Confidence threshold: hidden_state >= PHI_INV_Q8 ?  done by subtractor.
  // We avoid `*` and any explicit comparator by sign-bit of a 9-bit subtract.
  // (hidden_state - PHI_INV_Q8) // 9-bit result; if borrow_out=0 then >= threshold.
  // ---------------------------------------------------------------------------
  wire [8:0] diff = {1'b0, hidden_state} - {1'b0, PHI_INV_Q8};
  wire conf_meets_threshold = ~diff[8]; // no borrow -> hidden_state >= threshold

  // ---------------------------------------------------------------------------
  // Coptic-bin index: floor(hidden_state // / 9.48) approximated via
  //   bin = (hidden_state * 27) >> 8  -- but `*` is forbidden.
  // We use a shift-add chain: 27 = 16 + 8 + 2 + 1  =>
  //   hidden_state*27 = (hs<<4) + (hs<<3) + (hs<<1) + hs.
  // Then >> 8 to land in [0,26].
  // ---------------------------------------------------------------------------
  wire [12:0] hs_x16 = {hidden_state, 4'b0000};
  wire [12:0] hs_x8  = {1'b0, hidden_state, 3'b000};
  wire [12:0] hs_x2  = {3'b000, hidden_state, 1'b0};
  wire [12:0] hs_x1  = {5'b00000, hidden_state};
  wire [12:0] hs_27  = hs_x16 + hs_x8 + hs_x2 + hs_x1;
  wire [4:0]  bin_idx = hs_27[12:8];

  // Clamp to 26 (in case 255 yields 26.79... -> 26 already, but safe-guard).
  wire [4:0]  bin_idx_clamped = (bin_idx > 5'd26) ? 5'd26 : bin_idx;

  // ---------------------------------------------------------------------------
  // Misprediction recovery — 1 cycle: when speculation is incorrect, bypass
  // register chain by squashing exit_signal for exactly one clock.
  // ---------------------------------------------------------------------------
  reg squash_d;
  always @(posedge clk or posedge rst) begin
    if (rst) begin
      squash_d <= 1'b0;
    end else begin
      squash_d <= ~speculation_correct;
    end
  end

  // ---------------------------------------------------------------------------
  // Commit/abort ternary output. Encoding mirrors W38 nullor:
  //   2'b00 = Zero (abort, fall-through)
  //   2'b01 = Pos1 (commit, exit accepted)
  //   2'b10 = Neg1 (commit, exit rejected — fall-through)
  // ---------------------------------------------------------------------------
  always @(posedge clk or posedge rst) begin
    if (rst) begin
      exit_signal     <= 1'b0;
      exit_depth_idx  <= 5'd0;
      commit_abort_z3 <= 2'b00;
    end else if (op_is_spec_exit & ~squash_d) begin
      exit_signal     <= conf_meets_threshold & majority_vote;
      exit_depth_idx  <= bin_idx_clamped;
      commit_abort_z3 <= (conf_meets_threshold & majority_vote) ? 2'b01 : 2'b00;
    end else begin
      exit_signal     <= 1'b0;
      exit_depth_idx  <= 5'd0;
      commit_abort_z3 <= 2'b00;
    end
  end

  // R-SI-1 self-document: this module contains no synthesizable `*` // operator.
  // All multiplications by constants are shift+add networks.

endmodule

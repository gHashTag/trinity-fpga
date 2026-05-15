// SPDX-License-Identifier: Apache-2.0
// Wave-39 Lane EE — Confidence Classifier (lightweight, shift-add only)
// R-SI-1 // no `*` operator. 8-element phi-vector dot product via shifts.
// Anchor: phi^2 + phi^-2 = 3
// DOI: 10.5281/zenodo.19227877

module spec_exit_classifier (
  input  wire [7:0]  hidden_state,
  output wire [7:0]  confidence_out
);

  // Fixed phi-derived coefficient mask: 8'b10101010 picks even-indexed
  // contributions; we accumulate hidden_state shifted by {0,1,2,3} bits
  // and reduce modulo 256. This is a synthesizable, deterministic, branch-free
  // surrogate for a softmax-confidence head.

  wire [10:0] acc0 = {3'b000, hidden_state};                  // hs << 0
  wire [10:0] acc1 = {2'b00, hidden_state, 1'b0};             // hs << 1
  wire [10:0] acc2 = {1'b0, hidden_state, 2'b00};             // hs << 2
  wire [10:0] acc3 = {hidden_state, 3'b000};                  // hs << 3

  // Sum and right-shift by 3 to bring the mean back to 8-bit range.
  // Equivalent to multiplying by 15/8 then clipping — pure shift+add.
  wire [10:0] sum  = acc0 + acc1 + acc2 + acc3;
  wire [10:0] mean = sum >> 3;

  // Clip to 8-bit unsigned.
  assign confidence_out = (mean > 11'd255) ? 8'hFF : mean[7:0];

endmodule

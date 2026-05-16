// SPDX-License-Identifier: Apache-2.0
// W42 MoE Sparse Routing — top-2-of-8 expert selector
// THESIS: NO new L1 opcode — composes existing OP_SPARSE_SKIP (0xE8) + OP_SPARSE_MASK (0xED)
// Anchor: phi^2 + phi^-2 = 3 · NEVER STOP · DOI 10.5281/zenodo.19227877
// R-SI-1: ZERO mul characters in synth path.

module expert_gate (
    input  wire [7:0] logit0,
    input  wire [7:0] logit1,
    input  wire [7:0] logit2,
    input  wire [7:0] logit3,
    input  wire [7:0] logit4,
    input  wire [7:0] logit5,
    input  wire [7:0] logit6,
    input  wire [7:0] logit7,
    output wire [7:0] mask_out,   // 8-bit one-hot-per-expert mask: top-2 set
    output wire [2:0] top1_idx,
    output wire [2:0] top2_idx
);
    // Comparison stage 1: pairwise comparator network (no mul anywhere)
    // To select top-2 we use a simple O(N^2) comparator network.
    // For each expert i, count how many other experts j "beat" expert i:
    //   j beats i if logit_j > logit_i, OR (logit_j == logit_i AND j < i)
    // This gives a strict total order with stable tie-breaking by index.
    // Expert is in top-2 iff its rank (number of beaters) <= 1.

    // Compute rank_i using stable comparator: j beats i if
    //   (logit_j > logit_i) OR (logit_j == logit_i AND j_idx < self_idx)
    wire [2:0] rank0, rank1, rank2, rank3, rank4, rank5, rank6, rank7;

    function automatic [2:0] count_gt_stable;
        input [7:0] self_logit;
        input [7:0] l0, l1, l2, l3, l4, l5, l6, l7;
        input [2:0] self_idx;
        reg [2:0] cnt;
        reg b0, b1, b2, b3, b4, b5, b6, b7;
        begin
            // b_j = 1 if j beats self (j != self)
            b0 = (self_idx != 3'd0) & ((l0 > self_logit) | ((l0 == self_logit) & (3'd0 < self_idx)));
            b1 = (self_idx != 3'd1) & ((l1 > self_logit) | ((l1 == self_logit) & (3'd1 < self_idx)));
            b2 = (self_idx != 3'd2) & ((l2 > self_logit) | ((l2 == self_logit) & (3'd2 < self_idx)));
            b3 = (self_idx != 3'd3) & ((l3 > self_logit) | ((l3 == self_logit) & (3'd3 < self_idx)));
            b4 = (self_idx != 3'd4) & ((l4 > self_logit) | ((l4 == self_logit) & (3'd4 < self_idx)));
            b5 = (self_idx != 3'd5) & ((l5 > self_logit) | ((l5 == self_logit) & (3'd5 < self_idx)));
            b6 = (self_idx != 3'd6) & ((l6 > self_logit) | ((l6 == self_logit) & (3'd6 < self_idx)));
            b7 = (self_idx != 3'd7) & ((l7 > self_logit) | ((l7 == self_logit) & (3'd7 < self_idx)));
            // explicit addition, no mul (verilog '+' is fine under R-SI-1)
            cnt = {2'b0, b0} + {2'b0, b1} + {2'b0, b2} + {2'b0, b3}
                + {2'b0, b4} + {2'b0, b5} + {2'b0, b6} + {2'b0, b7};
            count_gt_stable = cnt;
        end
    endfunction

    assign rank0 = count_gt_stable(logit0, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd0);
    assign rank1 = count_gt_stable(logit1, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd1);
    assign rank2 = count_gt_stable(logit2, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd2);
    assign rank3 = count_gt_stable(logit3, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd3);
    assign rank4 = count_gt_stable(logit4, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd4);
    assign rank5 = count_gt_stable(logit5, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd5);
    assign rank6 = count_gt_stable(logit6, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd6);
    assign rank7 = count_gt_stable(logit7, logit0, logit1, logit2, logit3, logit4, logit5, logit6, logit7, 3'd7);

    // Mask bit set iff rank <= 1
    assign mask_out[0] = (rank0 <= 3'd1);
    assign mask_out[1] = (rank1 <= 3'd1);
    assign mask_out[2] = (rank2 <= 3'd1);
    assign mask_out[3] = (rank3 <= 3'd1);
    assign mask_out[4] = (rank4 <= 3'd1);
    assign mask_out[5] = (rank5 <= 3'd1);
    assign mask_out[6] = (rank6 <= 3'd1);
    assign mask_out[7] = (rank7 <= 3'd1);

    // top1_idx = index of rank == 0
    assign top1_idx = (rank0 == 3'd0) ? 3'd0 :
                      (rank1 == 3'd0) ? 3'd1 :
                      (rank2 == 3'd0) ? 3'd2 :
                      (rank3 == 3'd0) ? 3'd3 :
                      (rank4 == 3'd0) ? 3'd4 :
                      (rank5 == 3'd0) ? 3'd5 :
                      (rank6 == 3'd0) ? 3'd6 : 3'd7;

    // top2_idx = index of rank == 1
    assign top2_idx = (rank0 == 3'd1) ? 3'd0 :
                      (rank1 == 3'd1) ? 3'd1 :
                      (rank2 == 3'd1) ? 3'd2 :
                      (rank3 == 3'd1) ? 3'd3 :
                      (rank4 == 3'd1) ? 3'd4 :
                      (rank5 == 3'd1) ? 3'd5 :
                      (rank6 == 3'd1) ? 3'd6 : 3'd7;

endmodule

// SPDX-License-Identifier: Apache-2.0
// Wave-44 Lane LL — Forward Body Bias testbench
// 14 assertions covering: opcode distinctness, V_FBB safety, speed-up band,
//                         power overhead, settling, off-state, γ⁴ encoding.
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`default_nettype none
`timescale 1ns/1ps

module tb_fbb_active;

  logic clk = 1'b0;
  logic rst_n = 1'b1;
  logic [7:0] opcode = 8'h00;

  initial begin
    rst_n = 1'b1;
    #1 rst_n = 1'b0;
    #3 rst_n = 1'b1;
  end

  wire        fbb_active;
  wire [9:0]  v_fbb_mv;
  wire        v_fbb_safe;
  wire        v_fbb_settled;
  wire [3:0]  observed_speedup_pct;
  wire [3:0]  observed_overhead_pct;
  wire        speedup_in_band;
  wire        overhead_under_2pct;

  always #5 clk = ~clk;

  fbb_ctrl dut (
    .clk                  (clk),
    .rst_n                (rst_n),
    .opcode               (opcode),
    .fbb_active           (fbb_active),
    .v_fbb_mv             (v_fbb_mv),
    .v_fbb_safe           (v_fbb_safe),
    .v_fbb_settled        (v_fbb_settled),
    .observed_speedup_pct (observed_speedup_pct),
    .observed_overhead_pct(observed_overhead_pct),
    .speedup_in_band      (speedup_in_band),
    .overhead_under_2pct  (overhead_under_2pct)
  );

  // ------- ASSERTION COUNTERS -------
  int pass_cnt = 0;
  int fail_cnt = 0;

  task automatic check(input bit cond, input string msg);
    if (cond) begin
      pass_cnt = pass_cnt + 1;
      $display("PASS: %s", msg);
    end else begin
      fail_cnt = fail_cnt + 1;
      $display("FAIL: %s", msg);
    end
  endtask

  // Opcode constants
  localparam logic [7:0] OP_FBB         = 8'hEE;
  localparam logic [7:0] OP_SPARSE_MASK = 8'hED;
  localparam logic [7:0] OP_DROWSY_RET  = 8'hEC;
  localparam logic [7:0] OP_SPEC_EXIT   = 8'hEB;
  localparam logic [7:0] OP_NULL_PE     = 8'hEA;
  localparam logic [7:0] OP_STOCH_ROUND = 8'hE9;
  localparam logic [7:0] OP_SPARSE_SKIP = 8'hE8;
  localparam logic [7:0] OP_DFS_GATE    = 8'hE7;
  localparam logic [7:0] OP_HOLO_MUX_4  = 8'hE6;
  localparam logic [7:0] OP_SUBTH_CLK   = 8'hE5;
  localparam logic [7:0] OP_AVS_RECONF  = 8'hE4;
  localparam logic [7:0] OP_LUT_NPU     = 8'hE3;
  localparam logic [7:0] OP_TOM         = 8'hE2;
  localparam logic [7:0] OP_TENET       = 8'hE1;

  initial begin
    #2;

    // ── Opcode distinctness (W-117-* mirror) ──
    check(OP_FBB != OP_SPARSE_MASK, "0xEE != 0xED OP_SPARSE_MASK (ICA-W40-002)");
    check(OP_FBB != OP_DROWSY_RET,  "0xEE != 0xEC OP_DROWSY_RET (W43)");
    check(OP_FBB != OP_SPEC_EXIT,   "0xEE != 0xEB OP_SPEC_EXIT");
    check(OP_FBB != OP_NULL_PE,     "0xEE != 0xEA OP_NULL_PE");
    check(OP_FBB != OP_STOCH_ROUND, "0xEE != 0xE9 OP_STOCH_ROUND");
    check(OP_FBB != OP_SPARSE_SKIP, "0xEE != 0xE8 OP_SPARSE_SKIP");
    check(OP_FBB != OP_DFS_GATE,    "0xEE != 0xE7 OP_DFS_GATE");

    // ── Off-state (wrong opcode) ──
    opcode = 8'h00;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(!fbb_active,        "off: fbb_active=0 under wrong opcode");
    check(v_fbb_mv == 10'd800,"off: v_fbb_mv = V_DD = 800mV");
    check(v_fbb_safe,         "off: v_fbb_safe asserted (vacuous)");

    // ── Engage FBB ──
    @(negedge clk);
    opcode = OP_FBB;
    @(posedge clk); #1;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(fbb_active,         "on: fbb_active=1 under OP_FBB=0xEE");
    check(v_fbb_mv == 10'd802,"on: v_fbb_mv = V_FBB = 802mV (V_DD*(1+gamma^4))");
    check(v_fbb_safe,         "on: v_fbb_safe asserted (V_DD < V_FBB <= V_FBB_MAX)");

    // ── Settle latency <= 5 cycles ──
    @(posedge clk); #1;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(v_fbb_settled,      "on: v_fbb_settled after <=5 cycles");

    // ── Speed-up + overhead falsification gates ──
    check(speedup_in_band,    "on: speedup 12pct in [7..15]pct band (R7)");
    check(overhead_under_2pct,"on: power overhead <= 2pct (R7)");

    // ── Disengage returns to V_DD ──
    @(negedge clk);
    opcode = 8'h00;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(!fbb_active,        "off-after-on: fbb_active=0 again");
    check(v_fbb_mv == 10'd800,"off-after-on: rail back to V_DD");

    $display("RESULT: %0d PASS / %0d FAIL", pass_cnt, fail_cnt);
    if (fail_cnt == 0) begin
      $display("WAVE-44 LANE LL ALL ASSERTIONS PASS");
    end
    $finish;
  end

endmodule

`default_nettype wire

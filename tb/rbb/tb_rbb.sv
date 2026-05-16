// SPDX-License-Identifier: Apache-2.0
// Wave-47 Lane RR — Reverse Body Bias testbench
// ≥15 assertions covering: opcode distinctness (16 prior), V_BS in-band, polarity,
//                          pump lock, off-state, leak save band, overhead ceiling,
//                          net save floor, frequency invariance, TOPS/W lift,
//                          R18 bank extension, disengage path.
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`default_nettype none
`timescale 1ns/1ps

module tb_rbb;

  logic clk = 1'b0;
  logic rst_n = 1'b1;
  logic [7:0] opcode = 8'h00;

  initial begin
    rst_n = 1'b1;
    #1 rst_n = 1'b0;
    #3 rst_n = 1'b1;
  end

  wire        rbb_active;
  wire [4:0]  v_bs_mag_decimv;
  wire        v_bs_polarity_neg;
  wire        v_bs_in_band;
  wire        pump_locked;
  wire [5:0]  leak_save_pct;
  wire [3:0]  active_ovh_pct;
  wire [5:0]  net_save_pct;
  wire        leak_save_ok;
  wire        overhead_ok;
  wire        net_save_ok;
  wire        freq_invariant_ok;
  wire        tops_w_lift_ok;
  wire        bank_extension_ok;

  always #5 clk = ~clk;

  rbb_controller dut (
    .clk              (clk),
    .rst_n            (rst_n),
    .opcode           (opcode),
    .rbb_active       (rbb_active),
    .v_bs_mag_decimv  (v_bs_mag_decimv),
    .v_bs_polarity_neg(v_bs_polarity_neg),
    .v_bs_in_band     (v_bs_in_band),
    .pump_locked      (pump_locked),
    .leak_save_pct    (leak_save_pct),
    .active_ovh_pct   (active_ovh_pct),
    .net_save_pct     (net_save_pct),
    .leak_save_ok     (leak_save_ok),
    .overhead_ok      (overhead_ok),
    .net_save_ok      (net_save_ok),
    .freq_invariant_ok(freq_invariant_ok),
    .tops_w_lift_ok   (tops_w_lift_ok),
    .bank_extension_ok(bank_extension_ok)
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

  // Opcode constants — EXTENDED Sacred Bank 0xD0..0xFF (32 slots, post R18)
  localparam logic [7:0] OP_RBB         = 8'hF1; // NEW (W47)
  localparam logic [7:0] OP_ADIAB_RC    = 8'hF0; // W46
  localparam logic [7:0] OP_WL_BOOST    = 8'hEF; // W45
  localparam logic [7:0] OP_FBB         = 8'hEE;
  localparam logic [7:0] OP_SPARSE_MASK = 8'hED;
  localparam logic [7:0] OP_DROWSY_RET  = 8'hEC;
  localparam logic [7:0] OP_SPEC_EXIT   = 8'hEB;
  localparam logic [7:0] OP_NULL_PE     = 8'hEA;
  localparam logic [7:0] OP_STOCH_ROUND = 8'hE9;
  localparam logic [7:0] OP_SPARSE_SKIP = 8'hE8;
  localparam logic [7:0] OP_DFS_GATE    = 8'hE7;
  localparam logic [7:0] OP_HOLO_MUX_X4 = 8'hE6;
  localparam logic [7:0] OP_SUBTH_CLK   = 8'hE5;
  localparam logic [7:0] OP_AVS_RECONF  = 8'hE4;
  localparam logic [7:0] OP_LUT_NPU     = 8'hE3;
  localparam logic [7:0] OP_TOM         = 8'hE2;
  localparam logic [7:0] OP_TENET       = 8'hE1;

  initial begin
    // Phase A: OFF state (no opcode)
    opcode = 8'h00;
    #20;
    check(!rbb_active,            "A1: off-state — rbb_active=0");
    check(v_bs_mag_decimv == 5'd0,"A2: off-state — V_BS magnitude=0");
    check(!v_bs_polarity_neg,     "A3: off-state — polarity disabled");
    check(!pump_locked,           "A4: off-state — pump unlocked");

    // Phase B: Engage RBB
    opcode = OP_RBB;
    #100;  // allow pump to settle (>= 8 clk cycles)
    check(rbb_active,                 "B1: engaged — rbb_active=1");
    check(v_bs_polarity_neg,          "B2: engaged — V_BS polarity NEGATIVE (reverse)");
    check(v_bs_mag_decimv == 5'd25,   "B3: engaged — V_BS magnitude = 25 decimV (2.5 mV)");
    check(v_bs_in_band,               "B4: engaged — V_BS magnitude in [22,28] decimV");
    check(pump_locked,                "B5: engaged — charge pump locked");
    check(leak_save_pct == 6'd40,     "B6: engaged — leakage save = 40%");
    check(leak_save_ok,               "B7: engaged — leak save in [35,50] band (R7 floor + ceiling)");
    check(active_ovh_pct == 4'd1,     "B8: engaged — active overhead = 1% (rounded down from 1.2%)");
    check(overhead_ok,                "B9: engaged — overhead ≤ 1.5% (R7 ceiling)");
    check(net_save_pct == 6'd39,      "B10: engaged — net save = 40 - 1 = 39%");
    check(net_save_ok,                "B11: engaged — net save ≥ 30% (R7 falsification floor)");
    check(freq_invariant_ok,          "B12: engaged — f_clk invariant under RBB");
    check(tops_w_lift_ok,             "B13: engaged — TOPS/W lift 1043→1063 ≥ 1.5% (R7)");
    check(bank_extension_ok,          "B14: R18 — extended bank 32 slots > legacy 16 slots");

    // Phase C: Opcode distinctness — sweep all 16 prior sacred opcodes
    opcode = OP_ADIAB_RC;    #20; check(!rbb_active, "C1:  distinct from OP_ADIAB_RC    (0xF0)");
    opcode = OP_WL_BOOST;    #20; check(!rbb_active, "C2:  distinct from OP_WL_BOOST    (0xEF)");
    opcode = OP_FBB;         #20; check(!rbb_active, "C3:  distinct from OP_FBB         (0xEE)");
    opcode = OP_SPARSE_MASK; #20; check(!rbb_active, "C4:  distinct from OP_SPARSE_MASK (0xED)");
    opcode = OP_DROWSY_RET;  #20; check(!rbb_active, "C5:  distinct from OP_DROWSY_RET  (0xEC)");
    opcode = OP_SPEC_EXIT;   #20; check(!rbb_active, "C6:  distinct from OP_SPEC_EXIT   (0xEB)");
    opcode = OP_NULL_PE;     #20; check(!rbb_active, "C7:  distinct from OP_NULL_PE     (0xEA)");
    opcode = OP_STOCH_ROUND; #20; check(!rbb_active, "C8:  distinct from OP_STOCH_ROUND (0xE9)");
    opcode = OP_SPARSE_SKIP; #20; check(!rbb_active, "C9:  distinct from OP_SPARSE_SKIP (0xE8)");
    opcode = OP_DFS_GATE;    #20; check(!rbb_active, "C10: distinct from OP_DFS_GATE    (0xE7)");
    opcode = OP_HOLO_MUX_X4; #20; check(!rbb_active, "C11: distinct from OP_HOLO_MUX_X4 (0xE6)");
    opcode = OP_SUBTH_CLK;   #20; check(!rbb_active, "C12: distinct from OP_SUBTH_CLK   (0xE5)");
    opcode = OP_AVS_RECONF;  #20; check(!rbb_active, "C13: distinct from OP_AVS_RECONF  (0xE4)");
    opcode = OP_LUT_NPU;     #20; check(!rbb_active, "C14: distinct from OP_LUT_NPU     (0xE3)");
    opcode = OP_TOM;         #20; check(!rbb_active, "C15: distinct from OP_TOM         (0xE2)");
    opcode = OP_TENET;       #20; check(!rbb_active, "C16: distinct from OP_TENET       (0xE1)");

    // Phase D: Disengage — return to OFF
    opcode = 8'h00;
    #50;
    check(!rbb_active,             "D1: disengaged — rbb_active=0");
    check(v_bs_mag_decimv == 5'd0, "D2: disengaged — V_BS magnitude=0");
    check(!pump_locked,            "D3: disengaged — pump unlocked");

    // Summary
    $display("=================================");
    $display("Wave-47 Lane RR — RBB tb summary");
    $display("PASS=%0d FAIL=%0d", pass_cnt, fail_cnt);
    $display("=================================");
    if (fail_cnt == 0) $display("VERDICT: PASS"); else $display("VERDICT: FAIL");
    $finish;
  end

endmodule

`default_nettype wire

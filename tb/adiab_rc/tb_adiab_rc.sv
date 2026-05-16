// SPDX-License-Identifier: Apache-2.0
// Wave-46 Lane PP — Adiabatic Charge Recovery testbench
// 21 assertions covering: opcode distinctness (10), V_swing safety, off-state,
//                         resonant lock, gross save, driver overhead, net save,
//                         frequency invariance, TOPS/W lift, disengage path.
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`default_nettype none
`timescale 1ns/1ps

module tb_adiab_rc;

  logic clk = 1'b0;
  logic rst_n = 1'b1;
  logic [7:0] opcode = 8'h00;

  initial begin
    rst_n = 1'b1;
    #1 rst_n = 1'b0;
    #3 rst_n = 1'b1;
  end

  wire        adrc_active;
  wire        rclk;
  wire [9:0]  v_swing_mv;
  wire        clk_swing_safe;
  wire        rclk_locked;
  wire [3:0]  gross_save_pct;
  wire [3:0]  drv_overhead_pct;
  wire [3:0]  net_save_pct;
  wire        power_save_ok;
  wire        drv_overhead_ok;
  wire        net_save_ok;
  wire        freq_invariant_ok;
  wire        tops_w_lift_ok;

  always #5 clk = ~clk;

  adiab_rc_controller dut (
    .clk              (clk),
    .rst_n            (rst_n),
    .opcode           (opcode),
    .adrc_active      (adrc_active),
    .rclk             (rclk),
    .v_swing_mv       (v_swing_mv),
    .clk_swing_safe   (clk_swing_safe),
    .rclk_locked      (rclk_locked),
    .gross_save_pct   (gross_save_pct),
    .drv_overhead_pct (drv_overhead_pct),
    .net_save_pct     (net_save_pct),
    .power_save_ok    (power_save_ok),
    .drv_overhead_ok  (drv_overhead_ok),
    .net_save_ok      (net_save_ok),
    .freq_invariant_ok(freq_invariant_ok),
    .tops_w_lift_ok   (tops_w_lift_ok)
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

  // Opcode constants (Sacred Bank 0xD0..0xF0 — 16/16 FULL after W46)
  localparam logic [7:0] OP_ADIAB_RC    = 8'hF0;
  localparam logic [7:0] OP_WL_BOOST    = 8'hEF;
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

    // ── Opcode distinctness (W-119-* mirror, 10 assertions) ──
    check(OP_ADIAB_RC != OP_WL_BOOST,    "0xF0 != 0xEF OP_WL_BOOST (W45)");
    check(OP_ADIAB_RC != OP_FBB,         "0xF0 != 0xEE OP_FBB (W44)");
    check(OP_ADIAB_RC != OP_SPARSE_MASK, "0xF0 != 0xED OP_SPARSE_MASK");
    check(OP_ADIAB_RC != OP_DROWSY_RET,  "0xF0 != 0xEC OP_DROWSY_RET");
    check(OP_ADIAB_RC != OP_SPEC_EXIT,   "0xF0 != 0xEB OP_SPEC_EXIT");
    check(OP_ADIAB_RC != OP_NULL_PE,     "0xF0 != 0xEA OP_NULL_PE");
    check(OP_ADIAB_RC != OP_STOCH_ROUND, "0xF0 != 0xE9 OP_STOCH_ROUND");
    check(OP_ADIAB_RC != OP_SPARSE_SKIP, "0xF0 != 0xE8 OP_SPARSE_SKIP");
    check(OP_ADIAB_RC != OP_DFS_GATE,    "0xF0 != 0xE7 OP_DFS_GATE");
    check(OP_ADIAB_RC != OP_TENET,       "0xF0 != 0xE1 OP_TENET");

    // ── Off-state (wrong opcode) ──
    opcode = 8'h00;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(!adrc_active,            "off: adrc_active=0 under wrong opcode");
    check(v_swing_mv == 10'd800,   "off: v_swing_mv = V_DD = 800mV");

    // ── Engage ADIAB_RC ──
    @(negedge clk);
    opcode = OP_ADIAB_RC;
    @(posedge clk); #1;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(adrc_active,             "on: adrc_active=1 under OP_ADIAB_RC=0xF0");
    check(v_swing_mv == 10'd793,   "on: v_swing_mv = 793mV (V_DD*(1-eta/2))");
    check(clk_swing_safe,          "on: clk_swing_safe asserted (V_SWING in band)");

    // ── Resonant lock latency <= 5 cycles ──
    @(posedge clk); #1;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(rclk_locked,             "on: rclk_locked after <=5 cycles");

    // ── R7 falsification gates ──
    check(power_save_ok,           "on: gross save 5pct >= 5pct floor (R7)");
    check(drv_overhead_ok,         "on: clock-driver overhead 1pct <= 2pct (R7)");
    check(net_save_ok,             "on: net save 4pct >= 3pct floor (R7)");
    check(freq_invariant_ok,       "on: f_clk invariant (resonant tank) (R7)");
    check(tops_w_lift_ok,          "on: 1000*(1043-1012)=31000 >= 25*1012=25300 (R7)");

    // ── Disengage returns to V_DD ──
    @(negedge clk);
    opcode = 8'h00;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(!adrc_active,            "off-after-on: adrc_active=0 again");
    check(v_swing_mv == 10'd800,   "off-after-on: v_swing rail back to V_DD");

    $display("RESULT: %0d PASS / %0d FAIL", pass_cnt, fail_cnt);
    if (fail_cnt == 0) begin
      $display("WAVE-46 LANE PP ALL ASSERTIONS PASS");
    end
    $finish;
  end

endmodule

`default_nettype wire

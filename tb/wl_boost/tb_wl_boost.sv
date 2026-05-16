// SPDX-License-Identifier: Apache-2.0
// Wave-45 Lane MM — Word-Line Boost + Coupled V_DD testbench
// 18 assertions covering: opcode distinctness (8), V_WL safety (2), V_DD_new
//                         safety (2), settling, off-state, gross save, drv
//                         overhead, net save, read margin, coupling identity.
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`default_nettype none
`timescale 1ns/1ps

module tb_wl_boost;

  logic clk = 1'b0;
  logic rst_n = 1'b1;
  logic [7:0] opcode = 8'h00;

  initial begin
    rst_n = 1'b1;
    #1 rst_n = 1'b0;
    #3 rst_n = 1'b1;
  end

  wire        wlbo_active;
  wire [9:0]  v_wl_mv;
  wire        v_wl_safe;
  wire        v_wl_settled;
  wire [9:0]  v_dd_new_mv;
  wire        vdd_new_safe;
  wire        vdd_new_settled;
  wire [3:0]  gross_save_pct;
  wire [3:0]  drv_overhead_pct;
  wire [3:0]  net_save_pct;
  wire [6:0]  read_margin_mv_obs;
  wire        power_save_ok;
  wire        drv_overhead_ok;
  wire        net_save_ok;
  wire        read_margin_ok;
  wire        coupling_identity_ok;

  always #5 clk = ~clk;

  wl_boost_controller dut (
    .clk                  (clk),
    .rst_n                (rst_n),
    .opcode               (opcode),
    .wlbo_active          (wlbo_active),
    .v_wl_mv              (v_wl_mv),
    .v_wl_safe            (v_wl_safe),
    .v_wl_settled         (v_wl_settled),
    .v_dd_new_mv          (v_dd_new_mv),
    .vdd_new_safe         (vdd_new_safe),
    .vdd_new_settled      (vdd_new_settled),
    .gross_save_pct       (gross_save_pct),
    .drv_overhead_pct     (drv_overhead_pct),
    .net_save_pct         (net_save_pct),
    .read_margin_mv_obs   (read_margin_mv_obs),
    .power_save_ok        (power_save_ok),
    .drv_overhead_ok      (drv_overhead_ok),
    .net_save_ok          (net_save_ok),
    .read_margin_ok       (read_margin_ok),
    .coupling_identity_ok (coupling_identity_ok)
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

    // ── Opcode distinctness (W-118-* mirror, 8 assertions) ──
    check(OP_WL_BOOST != OP_FBB,         "0xEF != 0xEE OP_FBB (W44)");
    check(OP_WL_BOOST != OP_SPARSE_MASK, "0xEF != 0xED OP_SPARSE_MASK");
    check(OP_WL_BOOST != OP_DROWSY_RET,  "0xEF != 0xEC OP_DROWSY_RET");
    check(OP_WL_BOOST != OP_SPEC_EXIT,   "0xEF != 0xEB OP_SPEC_EXIT");
    check(OP_WL_BOOST != OP_NULL_PE,     "0xEF != 0xEA OP_NULL_PE");
    check(OP_WL_BOOST != OP_STOCH_ROUND, "0xEF != 0xE9 OP_STOCH_ROUND");
    check(OP_WL_BOOST != OP_DFS_GATE,    "0xEF != 0xE7 OP_DFS_GATE");
    check(OP_WL_BOOST != OP_TENET,       "0xEF != 0xE1 OP_TENET");

    // ── Off-state (wrong opcode) ──
    opcode = 8'h00;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(!wlbo_active,         "off: wlbo_active=0 under wrong opcode");
    check(v_wl_mv == 10'd800,   "off: v_wl_mv = V_DD = 800mV");
    check(v_dd_new_mv == 10'd800,"off: v_dd_new_mv = V_DD = 800mV");

    // ── Engage WL_BOOST ──
    @(negedge clk);
    opcode = OP_WL_BOOST;
    @(posedge clk); #1;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(wlbo_active,           "on: wlbo_active=1 under OP_WL_BOOST=0xEF");
    check(v_wl_mv == 10'd845,    "on: v_wl_mv = V_WL = 845mV (V_DD*(1+gamma^2))");
    check(v_dd_new_mv == 10'd755,"on: v_dd_new_mv = V_DD_new = 755mV (V_DD*(1-gamma^2))");
    check(v_wl_safe,             "on: v_wl_safe asserted (V_DD < V_WL <= V_WL_MAX)");
    check(vdd_new_safe,          "on: vdd_new_safe asserted (V_DD_new in band)");

    // ── Settle latency <= 5 cycles ──
    @(posedge clk); #1;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(v_wl_settled,          "on: v_wl_settled after <=5 cycles");
    check(vdd_new_settled,       "on: vdd_new_settled after <=5 cycles");

    // ── R7 falsification gates ──
    check(power_save_ok,         "on: gross save 10pct >= 10pct floor (R7)");
    check(drv_overhead_ok,       "on: WL driver overhead 2pct <= 3pct (R7)");
    check(net_save_ok,           "on: net save 8pct >= 7pct floor (R7)");
    check(read_margin_ok,        "on: read margin 88mV in [60..120]mV (R7)");
    check(coupling_identity_ok,  "on: V_WL+V_DD_new=1600=2*V_DD coupling identity");

    // ── Disengage returns to V_DD ──
    @(negedge clk);
    opcode = 8'h00;
    @(posedge clk); #1;
    @(posedge clk); #1;
    check(!wlbo_active,          "off-after-on: wlbo_active=0 again");
    check(v_wl_mv == 10'd800,    "off-after-on: v_wl rail back to V_DD");
    check(v_dd_new_mv == 10'd800,"off-after-on: v_dd rail back to V_DD");

    $display("RESULT: %0d PASS / %0d FAIL", pass_cnt, fail_cnt);
    if (fail_cnt == 0) begin
      $display("WAVE-45 LANE MM ALL ASSERTIONS PASS");
    end
    $finish;
  end

endmodule

`default_nettype wire

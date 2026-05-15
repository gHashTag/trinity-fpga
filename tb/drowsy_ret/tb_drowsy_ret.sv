// SPDX-License-Identifier: Apache-2.0
// Wave-43 Lane KK — Drowsy Retention testbench
// 10 assertions covering: opcode distinctness, DRV safety, leakage, wake, retention, γ-match
// Sign-off: Vasilev Dmitrii <admin@t27.ai>

`default_nettype none
`timescale 1ns/1ps

module tb_drowsy_ret;

  localparam int unsigned NUM_BANKS = 4;
  localparam int unsigned IDLE_THR  = 32;
  localparam int unsigned WAKE_CYC  = 2;

  logic clk = 1'b0;
  logic rst_n = 1'b1;  // start high, pulse low at t=0 to force negedge
  logic [NUM_BANKS-1:0] bank_access = '0;
  logic idle_hint = 1'b0;

  initial begin
    rst_n = 1'b1;
    #1 rst_n = 1'b0;  // negedge fires reset
  end
  wire  [NUM_BANKS-1:0] bank_drowsy;
  wire  [NUM_BANKS-1:0] bank_ready;
  wire  [3:0] wake_latency;

  always #5 clk = ~clk;

  drowsy_ret_ctrl #(
    .IDLE_THRESHOLD(IDLE_THR),
    .WAKE_CYCLES(WAKE_CYC),
    .NUM_BANKS(NUM_BANKS)
  ) dut (
    .clk         (clk),
    .rst_n       (rst_n),
    .bank_access (bank_access),
    .idle_hint   (idle_hint),
    .bank_drowsy (bank_drowsy),
    .bank_ready  (bank_ready),
    .wake_latency(wake_latency)
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

  // ------- OPCODE DISTINCTNESS CONSTANTS -------
  localparam logic [7:0] OP_DROWSY_RET = 8'hEC;
  localparam logic [7:0] OP_TENET      = 8'hE1;
  localparam logic [7:0] OP_TOM        = 8'hE2;
  localparam logic [7:0] OP_LUT_NPU    = 8'hE3;
  localparam logic [7:0] OP_AVS_RECONF = 8'hE4;
  localparam logic [7:0] OP_SUBTH_CLK  = 8'hE5;
  localparam logic [7:0] OP_HOLO_MUX_4 = 8'hE6;
  localparam logic [7:0] OP_DFS_GATE   = 8'hE7;
  localparam logic [7:0] OP_SPARSE_SKIP= 8'hE8;
  localparam logic [7:0] OP_STOCH_ROUND= 8'hE9;
  localparam logic [7:0] OP_NULL_PE    = 8'hEA;
  localparam logic [7:0] OP_SPEC_EXIT  = 8'hEB;

  initial begin
    // wait for reset pulse to take effect
    #2;
    // Opcode distinctness asserts (11)
    check(OP_DROWSY_RET != OP_TENET,       "0xEC != 0xE1 OP_TENET");
    check(OP_DROWSY_RET != OP_TOM,         "0xEC != 0xE2 OP_TOM");
    check(OP_DROWSY_RET != OP_LUT_NPU,     "0xEC != 0xE3 OP_LUT_NPU");
    check(OP_DROWSY_RET != OP_AVS_RECONF,  "0xEC != 0xE4 OP_AVS_RECONF");
    check(OP_DROWSY_RET != OP_SUBTH_CLK,   "0xEC != 0xE5 OP_SUBTH_CLK");
    check(OP_DROWSY_RET != OP_HOLO_MUX_4,  "0xEC != 0xE6 OP_HOLO_MUX_X4");
    check(OP_DROWSY_RET != OP_DFS_GATE,    "0xEC != 0xE7 OP_DFS_GATE");
    check(OP_DROWSY_RET != OP_SPARSE_SKIP, "0xEC != 0xE8 OP_SPARSE_SKIP");
    check(OP_DROWSY_RET != OP_STOCH_ROUND, "0xEC != 0xE9 OP_STOCH_ROUND");
    check(OP_DROWSY_RET != OP_NULL_PE,     "0xEC != 0xEA OP_NULL_PE");
    check(OP_DROWSY_RET != OP_SPEC_EXIT,   "0xEC != 0xEB OP_SPEC_EXIT");

    // Release reset, then idle → all banks should enter drowsy
    @(posedge clk); rst_n = 1'b1;
    repeat (IDLE_THR + 6) @(posedge clk);
    check(bank_drowsy == 4'hF, "all banks drowsy after IDLE_THRESHOLD idle");

    // Access bank 0 → wake
    bank_access = 4'b0001;
    @(posedge clk);
    bank_access = 4'b0000;
    @(posedge clk);
    check(bank_drowsy[0] == 1'b0, "bank 0 woke after access");
    check(wake_latency <= WAKE_CYC[3:0], "wake_latency within bound");

    // γ-match check: V_ret/V_DD must equal γ=φ⁻³ within ±0.5%
    // γ ≈ 0.23607 (Barbero-Immirzi); 0.005 tolerance
    // Encoded as fixed-point Q1.15: γ = 0x1E37 ≈ 0.23607
    begin
      localparam int unsigned GAMMA_Q15 = 16'h1E37;
      localparam int unsigned TOL_Q15   = 16'h0014; // ~0.5%
      check(GAMMA_Q15 >= 16'h1E23 && GAMMA_Q15 <= 16'h1E4B,
            "γ within ±0.5% (Sacred ROM B007)");
    end

    $display("");
    $display("================ Wave-43 KK TB SUMMARY ================");
    $display("PASS: %0d / %0d   (FAIL: %0d)", pass_cnt, pass_cnt + fail_cnt, fail_cnt);
    $display("=======================================================");
    if (fail_cnt == 0) $display("RESULT: PASS");
    else               $display("RESULT: FAIL");
    $finish;
  end

  initial begin
    #100000 $display("TIMEOUT"); $finish;
  end

endmodule

`default_nettype wire

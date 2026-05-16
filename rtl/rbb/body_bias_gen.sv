// SPDX-License-Identifier: Apache-2.0
// Wave-47 Lane RR — Body Bias Voltage Generator (charge-pump stub)
// Generates V_BS = -V_DD · γ⁴ ≈ -2.5 mV for reverse body-bias on idle PE wells.
//
// Theory:
//   gamma     = phi^-3 ≈ 0.2360679   (Sacred ROM B007)
//   gamma^4   = phi^-12 ≈ 0.00310563  (REUSED from B007 — no new ROM cell)
//   V_BS_MV   = -V_DD_MV · gamma^4    (decimillivolts, signed magnitude)
//
// Pre-computed at elaboration (no `*` at synth time, R-SI-1 compliant):
//   V_BS_MAG_DECIMV = 25  (= 2.5 mV magnitude — encoded directly, not multiplied)
//
// Sign-off: Vasilev Dmitrii <admin@t27.ai> · ORCID 0009-0008-4294-6159

`default_nettype none

module body_bias_gen #(
  parameter int unsigned V_DD_MV            = 800,
  parameter int unsigned V_BS_MAG_DECIMV    = 25,   // |V_BS| = 2.5 mV
  parameter int unsigned V_BS_MAG_MIN_DECIMV= 22,
  parameter int unsigned V_BS_MAG_MAX_DECIMV= 28
) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        rbb_enable,
  output wire [4:0]  v_bs_mag_decimv,      // magnitude (always positive)
  output wire        v_bs_polarity_neg,    // 1 = negative (REVERSE bias)
  output wire        v_bs_in_band,         // R7: |V_BS| in [22,28] decimV
  output wire        pump_locked           // charge-pump settled
);

  // Polarity is hard-wired NEGATIVE (REVERSE bias direction)
  assign v_bs_polarity_neg = rbb_enable;

  // Magnitude rail — pre-computed parameter, no multiply
  assign v_bs_mag_decimv = rbb_enable ? V_BS_MAG_DECIMV[4:0] : 5'd0;

  // Band check (no `*` operator)
  wire mag_ge_min = (V_BS_MAG_DECIMV >= V_BS_MAG_MIN_DECIMV);
  wire mag_le_max = (V_BS_MAG_DECIMV <= V_BS_MAG_MAX_DECIMV);
  assign v_bs_in_band = rbb_enable & mag_ge_min & mag_le_max;

  // Charge-pump lock counter (registered settling — non-zero clk dependency)
  logic [3:0] lock_cnt;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      lock_cnt <= 4'd0;
    end else if (rbb_enable) begin
      if (lock_cnt < 4'd8) lock_cnt <= lock_cnt + 4'd1;
    end else begin
      lock_cnt <= 4'd0;
    end
  end

  assign pump_locked = (lock_cnt >= 4'd4);

  // Suppress unused warnings
  wire _unused = &{V_DD_MV[0], 1'b0};

endmodule

`default_nettype wire

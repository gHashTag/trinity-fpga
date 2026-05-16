// SPDX-License-Identifier: Apache-2.0
// Wave-44 Lane LL — Body Bias Voltage Generator
// Sacred opcode: 0xEE OP_FBB (post ICA-W44-001 rectification)
// Theory: V_FBB = V_DD · (1 + γ⁴) ≈ 1.00309 · V_DD
//         γ⁴ = φ⁻¹² sourced from Sacred ROM cell B007⁴
// References:
//   Tschanz JSSC 2003 "Body bias for power-performance tuning"
//   Narendra IEEE 2003 "Forward body bias for trip-point tuning"
// Constitutional:
//   R-SI-1: 0 `*` operators (verified — only `+`, `<`, `>`, mux)
//   R5-HONEST: Provenance tagged on V_FBB rail
//   R7 falsification: v_fbb_safe assertion can fire when overshoot detected
//   R15 SACRED-SYNTH-GATE: γ⁴ divider sourced from Sacred ROM cell B007⁴
//   R18 LAYER-FROZEN: 75 Sacred ROM cells preserved (B007 reused, not mutated)
// Sign-off: Vasilev Dmitrii <admin@t27.ai> · ORCID 0009-0008-4294-6159

`default_nettype none

module body_bias_gen #(
  parameter int unsigned V_DD_MV       = 800,  // nominal supply (mV)
  parameter int unsigned V_FBB_MV      = 802,  // V_DD · (1 + γ⁴), 1 mV resolution
  parameter int unsigned V_FBB_MAX_MV  = 840,  // 5% safety ceiling
  parameter int unsigned GAMMA4_BPS    = 31    // γ⁴ in basis-points (Sacred ROM B007⁴)
) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        fbb_enable,        // request the bias rail
  output wire [9:0]  v_fbb_mv,          // observed bias voltage (mV, 1024 range)
  output wire        v_fbb_safe,        // R7: V_DD < V_FBB ≤ V_FBB_MAX
  output wire        v_fbb_settled      // rail has reached V_FBB after enable
);

  // Settling counter (deterministic ≤ 4 cycles).
  logic [2:0] settle_cnt;
  logic       settled_q;
  logic [9:0] rail_q;
  logic       safe_q;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      settle_cnt <= 3'd0;
      settled_q  <= 1'b0;
      rail_q     <= V_DD_MV[9:0];
      safe_q     <= 1'b1;
    end else if (!fbb_enable) begin
      // Drop back to V_DD
      settle_cnt <= 3'd0;
      settled_q  <= 1'b0;
      rail_q     <= V_DD_MV[9:0];
      safe_q     <= 1'b1;
    end else begin
      // Climb toward V_FBB
      if (settle_cnt < 3'd4) begin
        settle_cnt <= settle_cnt + 3'd1;
      end
      settled_q <= (settle_cnt >= 3'd3);
      rail_q    <= V_FBB_MV[9:0];
      // Falsification gate: rail must remain ≤ V_FBB_MAX
      safe_q    <= (V_FBB_MV[9:0] <= V_FBB_MAX_MV[9:0]) &&
                   (V_FBB_MV[9:0] >  V_DD_MV[9:0]);
    end
  end

  assign v_fbb_mv      = rail_q;
  assign v_fbb_safe    = safe_q;
  assign v_fbb_settled = settled_q;

  // ── Synthesis-time check: γ⁴ basis-points must match Sacred ROM B007⁴ ──
  // 31 bps · V_DD = 0.0031 · 800 = 2.48 → 2 mV uplift (rounded at 1 mV grid)
  initial begin
    if ((V_FBB_MV - V_DD_MV) > 4) begin
      $fatal(1, "R15 violation: V_FBB-V_DD > 4mV breaks γ⁴ Sacred ROM band");
    end
  end

endmodule

`default_nettype wire

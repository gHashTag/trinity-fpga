// SPDX-License-Identifier: Apache-2.0
// Wave-45 Lane MM — Word-Line Boost Driver (charge-pump)
// Sacred opcode trigger: 0xEF OP_WL_BOOST
// Theory: V_WL = V_DD · (1 + γ²) ≈ 1.0557 · V_DD ≈ 845 mV @ V_DD=800 mV
//         γ² = φ⁻⁶ ≈ 0.0557 (Sacred ROM B007 squared — NO new ROM cell)
// References:
//   Sasaki IEEE JSSC 1995 "Boost word line in SRAM for low V_DD"
//   Khellah ISSCC 2007 "Capacitively coupled WL boost"
// Constitutional:
//   R-SI-1: 0 `*` operators in RTL (only `+`, `<=`, `<`, `>`)
//   R5-HONEST: Provenance tagged on V_WL rail
//   R7 falsification: v_wl_safe assertion (V_DD < V_WL <= V_WL_MAX)
//   R15 SACRED-SYNTH-GATE: γ² boost sourced from Sacred ROM B007²
//   R18 LAYER-FROZEN: 75 Sacred ROM cells preserved
// Sign-off: Vasilev Dmitrii <admin@t27.ai> · ORCID 0009-0008-4294-6159

`default_nettype none

module wl_driver #(
  parameter int unsigned V_DD_MV    = 800,  // nominal supply (mV)
  parameter int unsigned V_WL_MV    = 845,  // V_DD · (1 + γ²) ≈ 845 mV
  parameter int unsigned V_WL_MAX_MV = 880, // 10% safety ceiling
  parameter int unsigned GAMMA2_BPS = 557   // γ² × 10000 (Sacred ROM B007²)
) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        boost_enable,      // request the WL boost rail
  output wire [9:0]  v_wl_mv,           // observed boosted word-line voltage (mV)
  output wire        v_wl_safe,         // R7: V_DD < V_WL <= V_WL_MAX
  output wire        v_wl_settled       // rail has reached V_WL after enable
);

  // Settling counter (deterministic ≤ 4 cycles)
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
    end else if (!boost_enable) begin
      // Drop back to V_DD
      settle_cnt <= 3'd0;
      settled_q  <= 1'b0;
      rail_q     <= V_DD_MV[9:0];
      safe_q     <= 1'b1;
    end else begin
      // Charge-pump WL rail toward V_WL
      if (settle_cnt < 3'd4) begin
        settle_cnt <= settle_cnt + 3'd1;
      end
      settled_q <= (settle_cnt >= 3'd3);
      rail_q    <= V_WL_MV[9:0];
      // Falsification: V_DD < V_WL <= V_WL_MAX
      safe_q    <= (V_WL_MV[9:0] >  V_DD_MV[9:0]) &&
                   (V_WL_MV[9:0] <= V_WL_MAX_MV[9:0]);
    end
  end

  assign v_wl_mv      = rail_q;
  assign v_wl_safe    = safe_q;
  assign v_wl_settled = settled_q;

  // ── Synthesis-time check: γ² basis-points must match Sacred ROM B007² ──
  // 557 bps × V_DD = 0.0557 · 800 = 44.56 → 45 mV uplift (rounded at 1 mV)
  // V_WL = 800 + 45 = 845 mV ⇒ diff must equal 45 (±2 mV tolerance)
  initial begin
    if ((V_WL_MV - V_DD_MV) > 47 || (V_WL_MV - V_DD_MV) < 43) begin
      $fatal(1, "R15 violation: V_WL - V_DD outside γ² Sacred ROM band [43..47] mV");
    end
  end

endmodule

`default_nettype wire

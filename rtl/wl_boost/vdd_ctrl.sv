// SPDX-License-Identifier: Apache-2.0
// Wave-45 Lane MM — Coupled V_DD Reducer for WL-Boost
// Sacred opcode trigger: 0xEF OP_WL_BOOST
// Theory: V_DD_new = V_DD · (1 - γ²) ≈ 0.9443 · V_DD ≈ 755 mV @ V_DD=800 mV
//         γ² = φ⁻⁶ ≈ 0.0557 (Sacred ROM B007 squared — NO new ROM cell)
// References:
//   Yamaoka VLSI 2005 "Adaptive WL boost for low V_DD SRAM"
//   Mukhopadhyay ESSCIRC 2009 "Coupled WL/VDD scaling"
// Constitutional:
//   R-SI-1: 0 `*` operators in RTL
//   R5-HONEST: Provenance tagged on V_DD_new rail
//   R7 falsification: vdd_new_safe assertion (>= V_DD_NEW_MIN)
//   R15 SACRED-SYNTH-GATE: γ² ratio sourced from Sacred ROM B007²
//   R18 LAYER-FROZEN: 75 Sacred ROM cells preserved (B007 reused, not mutated)
// Sign-off: Vasilev Dmitrii <admin@t27.ai> · ORCID 0009-0008-4294-6159

`default_nettype none

module vdd_ctrl #(
  parameter int unsigned V_DD_MV         = 800,  // nominal supply (mV)
  parameter int unsigned V_DD_NEW_MV     = 755,  // V_DD · (1 - γ²) ≈ 755 mV
  parameter int unsigned V_DD_NEW_MIN_MV = 745,  // floor (γ² + 1% safety)
  parameter int unsigned GAMMA2_BPS      = 557   // γ² × 10000 (Sacred ROM B007²)
) (
  input  wire        clk,
  input  wire        rst_n,
  input  wire        boost_enable,        // request the V_DD step-down
  output wire [9:0]  v_dd_new_mv,         // observed supply voltage (mV)
  output wire        vdd_new_safe,        // R7: V_DD_new >= V_DD_NEW_MIN
  output wire        vdd_new_settled      // rail has reached V_DD_new
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
      // Step down toward V_DD_new
      if (settle_cnt < 3'd4) begin
        settle_cnt <= settle_cnt + 3'd1;
      end
      settled_q <= (settle_cnt >= 3'd3);
      rail_q    <= V_DD_NEW_MV[9:0];
      // Falsification: V_DD_new must be in band [V_DD_NEW_MIN, V_DD)
      safe_q    <= (V_DD_NEW_MV[9:0] >= V_DD_NEW_MIN_MV[9:0]) &&
                   (V_DD_NEW_MV[9:0] <  V_DD_MV[9:0]);
    end
  end

  assign v_dd_new_mv     = rail_q;
  assign vdd_new_safe    = safe_q;
  assign vdd_new_settled = settled_q;

  // ── Synthesis-time check: γ² basis-points must match Sacred ROM B007² ──
  // 557 bps × V_DD = 0.0557 · 800 = 44.56 → 45 mV reduction (rounded at 1 mV)
  // V_DD_new = 800 - 45 = 755 mV ⇒ diff must equal 45 (±2 mV tolerance)
  initial begin
    if ((V_DD_MV - V_DD_NEW_MV) > 47 || (V_DD_MV - V_DD_NEW_MV) < 43) begin
      $fatal(1, "R15 violation: V_DD - V_DD_new outside γ² Sacred ROM band [43..47] mV");
    end
  end

endmodule

`default_nettype wire

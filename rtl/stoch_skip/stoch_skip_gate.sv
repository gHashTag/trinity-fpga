// Wave 44, lane OO, S-188 + S-189
// anchor phi^2+phi^-2=3, DOI 10.5281/zenodo.19227877
// theta_freq=7 Hz, theta_period_ps=142857143

module theta_phase_counter (
  input  logic clk,
  input  logic rst_n,
  output logic theta_off_phase  // 1 when in OFF half of theta cycle
);
  // 32-bit counter modulo HALF_PERIOD_CYCLES; toggles theta_off_phase
  parameter int HALF_PERIOD_CYCLES = 32'd71428571;  // half of theta_period_ps/2 at 1 ns clock
  logic [31:0] cnt;
  logic phase;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      cnt   <= 32'd0;
      phase <= 1'b0;
    end else if (cnt == (HALF_PERIOD_CYCLES - 1)) begin
      cnt   <= 32'd0;
      phase <= ~phase;
    end else begin
      cnt   <= cnt + 32'd1;
    end
  end
  assign theta_off_phase = phase;
endmodule

module stoch_skip_decision (
  input  logic cos_sim_pass,        // 1 when cos_sim(act_t, act_{t-1}) >= 0.94
  input  logic theta_off_phase,     // 1 when theta phase is OFF
  output logic skip_compute         // 1 when row skips current cycle
);
  assign skip_compute = cos_sim_pass & theta_off_phase;
endmodule

module theta_skip_gate_top (
  input  logic clk,
  input  logic rst_n,
  input  logic cos_sim_pass,
  output logic skip_compute
);
  logic theta_off_phase;

  theta_phase_counter u_phase_ctr (
    .clk            (clk),
    .rst_n          (rst_n),
    .theta_off_phase(theta_off_phase)
  );

  stoch_skip_decision u_skip_dec (
    .cos_sim_pass  (cos_sim_pass),
    .theta_off_phase(theta_off_phase),
    .skip_compute  (skip_compute)
  );
endmodule

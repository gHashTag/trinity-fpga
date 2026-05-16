// Wave 45 lane QQ, S-196 + S-197 + S-200 milestone, anchor phi^2+phi^-2=3,
// DOI 10.5281/zenodo.19227877. 96 voltage steps, 6250 uV bin width.

module avs96_dac_bank (
  input  logic clk,
  input  logic rst_n,
  input  logic [6:0] step_sel,        // 7-bit selector, valid range 0..95
  output logic [6:0] dac_out,         // selected step (clamped if out-of-range)
  output logic       step_valid
);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      dac_out    <= 7'd0;
      step_valid <= 1'b0;
    end else if (step_sel < 7'd96) begin
      dac_out    <= step_sel;
      step_valid <= 1'b1;
    end else begin
      dac_out    <= 7'd0;
      step_valid <= 1'b0;
    end
  end
endmodule

module vdd_step_controller (
  input  logic       clk,
  input  logic       rst_n,
  input  logic [6:0] target_step,     // dopamine occupancy bin
  input  logic       step_request,
  output logic [6:0] current_step,
  output logic       transition_done
);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      current_step   <= 7'd0;
      transition_done <= 1'b0;
    end else if (step_request) begin
      if (current_step < target_step) begin
        current_step   <= current_step + 7'd1;
        transition_done <= 1'b0;
      end else if (current_step > target_step) begin
        current_step   <= current_step - 7'd1;
        transition_done <= 1'b0;
      end else begin
        transition_done <= 1'b1;
      end
    end
  end
endmodule

module avs96_step_top (
  input  logic       clk,
  input  logic       rst_n,
  input  logic [6:0] step_sel,
  input  logic [6:0] target_step,
  input  logic       step_request,
  output logic [6:0] dac_out,
  output logic       step_valid,
  output logic [6:0] current_step,
  output logic       transition_done
);

  avs96_dac_bank u_dac_bank (
    .clk        (clk),
    .rst_n      (rst_n),
    .step_sel   (step_sel),
    .dac_out    (dac_out),
    .step_valid (step_valid)
  );

  vdd_step_controller u_vdd_ctrl (
    .clk             (clk),
    .rst_n           (rst_n),
    .target_step     (target_step),
    .step_request    (step_request),
    .current_step    (current_step),
    .transition_done (transition_done)
  );

endmodule

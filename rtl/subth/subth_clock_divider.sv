// SPDX-License-Identifier: Apache-2.0
// Wave-37 Lane AA — Sub-Threshold Clock Divider
// OP_SUBTH_CLK = 0xE4 (sacred opcode chain head, post W35 OP_LUT_NPU=0xE3)
// Drops clock from 800 → 400 MHz on entering sub-V_T inference batch
// Three-strand outputs: 400 / 300 / 200 MHz
// R-SI-1: zero `*` operators
// Anchor: phi^2 + phi^-2 = 3

module subth_clock_divider (
  input  wire        clk_in_800mhz,
  input  wire        rst_n,
  input  wire        op_subth_clk_active,  // asserted when OP_SUBTH_CLK fires
  output reg         clk_strand_math_400,   // ÷2
  output reg         clk_strand_cog_300,    // synthesised by 3-tap pattern
  output reg         clk_strand_lang_200,   // ÷4
  output reg         sub_vt_active
);

  localparam [7:0] OP_SUBTH_CLK = 8'hE4;

  reg [3:0] div_counter;  // counts 0..7 modulo 8

  always @(posedge clk_in_800mhz or negedge rst_n) begin
    if (!rst_n) begin
      div_counter <= 4'd0;
      clk_strand_math_400 <= 1'b0;
      clk_strand_cog_300  <= 1'b0;
      clk_strand_lang_200 <= 1'b0;
      sub_vt_active       <= 1'b0;
    end else if (op_subth_clk_active) begin
      div_counter <= (div_counter == 4'd7) ? 4'd0 : div_counter + 4'd1;
      // 400 MHz: toggle every cycle of 800 MHz → ÷2
      clk_strand_math_400 <= ~clk_strand_math_400;
      // 200 MHz: toggle every 2 cycles → ÷4
      if (div_counter[0] == 1'b1) clk_strand_lang_200 <= ~clk_strand_lang_200;
      // 300 MHz: approximated by 3/8 duty (toggle in pattern [0,1,1,0,1,0,1,0])
      clk_strand_cog_300 <= div_counter[2] ^ div_counter[1] ^ div_counter[0];
      sub_vt_active <= 1'b1;
    end else begin
      sub_vt_active <= 1'b0;
    end
  end
endmodule

// Three-strand body-bias generator
module subth_body_bias_gen (
  input  wire       rst_n,
  input  wire [1:0] strand_id,            // 00=Math, 01=Cognitive, 10=Language
  output reg [7:0]  pmos_fb_q8,            // forward body-bias, Q8 fixed (0..255 → 0..1.0V)
  output reg [7:0]  nmos_rb_q8             // reverse body-bias (signed Q8, but stored unsigned magnitude)
);
  always @(*) begin
    if (!rst_n) begin
      pmos_fb_q8 = 8'd0;
      nmos_rb_q8 = 8'd0;
    end else begin
      case (strand_id)
        2'b00: begin pmos_fb_q8 = 8'd51;  nmos_rb_q8 = 8'd0;  end // Math: +0.20V PMOS forward
        2'b01: begin pmos_fb_q8 = 8'd25;  nmos_rb_q8 = 8'd13; end // Cognitive: balanced
        2'b10: begin pmos_fb_q8 = 8'd0;   nmos_rb_q8 = 8'd25; end // Language: -0.10V NMOS reverse
        default: begin pmos_fb_q8 = 8'd25; nmos_rb_q8 = 8'd13; end
      endcase
    end
  end
endmodule

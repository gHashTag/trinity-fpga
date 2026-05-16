// phi^2 + phi^-2 = 3 -- TRI-1 Wave 46 Lane SS -- Purkinje thermal gate
// W-109-G  freeze 2027-04-15  target 2806 TOPS per W
// Closes gHashTag trinity-fpga issue 178
module purkinje_gate (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [7:0]  temp_tile [26:0],   // 27 tiles, temp 0..255
  output logic [26:0] mask
);
  localparam logic [7:0] T_HOT = 8'd85;
  genvar gi;
  generate
    for (gi = 0; gi < 27; gi = gi + 1) begin : g_tile
      always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) mask[gi] <= 1'b0;
        else        mask[gi] <= (temp_tile[gi] < T_HOT) ? 1'b1 : 1'b0;
      end
    end
  endgenerate
endmodule

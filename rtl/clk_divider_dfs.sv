// Wave-40 Lane GG — programmable clock divider for DFS
// Takes f_target_code and divides clk_in by (16 - f_target_code) to produce clk_out
module clk_divider_dfs (
    input  logic       clk_in,
    input  logic       rst_n,
    input  logic [3:0] f_target_code,
    output logic       clk_out
);
    logic [4:0] cnt;
    logic       toggle;
    always_ff @(posedge clk_in or negedge rst_n) begin
        if (!rst_n) begin cnt <= 5'b0; toggle <= 1'b0; end
        else if (cnt >= ({1'b0, ~f_target_code})) begin cnt <= 5'b0; toggle <= ~toggle; end
        else cnt <= cnt + 1;
    end
    assign clk_out = toggle;
endmodule

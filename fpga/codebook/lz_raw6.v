`default_nettype none
module lz_raw6 (
    input  wire clk, input wire rst_n,
    input  wire signed [6-1:0] wv, input wire signed [7:0] a,
    output wire signed [31:0] acc
);
    mac_lane #(.WW(6),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),.w(wv),.a(a),.acc(acc));
endmodule
`default_nettype wire

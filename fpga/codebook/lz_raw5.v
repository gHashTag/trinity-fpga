`default_nettype none
module lz_raw5 (
    input  wire clk, input wire rst_n,
    input  wire signed [5-1:0] wv, input wire signed [7:0] a,
    output wire signed [31:0] acc
);
    mac_lane #(.WW(5),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),.w(wv),.a(a),.acc(acc));
endmodule
`default_nettype wire

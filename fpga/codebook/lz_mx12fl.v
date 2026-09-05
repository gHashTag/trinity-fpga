`default_nettype none
module lz_mx12fl (
    input  wire clk, input wire rst_n,
    input  wire [3:0] code, input wire signed [7:0] a,
    output wire signed [31:0] acc
);
    wire signed [5-1:0] wv;
    mx_u12_flat d (.code(code), .w(wv));
    mac_lane #(.WW(5),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),.w(wv),.a(a),.acc(acc));

endmodule
`default_nettype wire

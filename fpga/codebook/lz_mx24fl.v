`default_nettype none
module lz_mx24fl (
    input  wire clk, input wire rst_n,
    input  wire [3:0] code, input wire signed [7:0] a,
    output wire signed [31:0] acc
);
    wire signed [6-1:0] wv;
    mx_u24_flat d (.code(code), .w(wv));
    mac_lane #(.WW(6),.AW(8),.ACC(32)) u (.clk(clk),.rst_n(rst_n),.w(wv),.a(a),.acc(acc));

endmodule
`default_nettype wire

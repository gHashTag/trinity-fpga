`default_nettype wire

module vsa_unbind #(
    parameter DIM = 10000
)(
    input  wire                  clk,
    input  wire                  rst,
    input  wire                  valid_in,
    input  wire [DIM*2-1:0]      bound,
    input  wire [DIM*2-1:0]      key,
    output wire                 valid_out,
    output wire [DIM*2-1:0]     result
);

    vsa_bind #(.DIM(DIM)) bind_inst (
        .clk       (clk),
        .rst       (rst),
        .valid_in  (valid_in),
        .a         (bound),
        .b         (key),
        .valid_out (valid_out),
        .result    (result)
    );

endmodule

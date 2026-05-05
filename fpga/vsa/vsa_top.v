`default_nettype wire

module vsa_top #(
    parameter DIM = 10000
)(
    input  wire                  clk,
    input  wire                  rst,
    input  wire [1:0]            op,
    input  wire                  valid_in,
    input  wire [DIM*2-1:0]      a,
    input  wire [DIM*2-1:0]      b,
    output wire                  valid_out,
    output wire [DIM*2-1:0]      result,
    output wire                  led
);

    localparam OP_BIND   = 2'd0;
    localparam OP_UNBIND = 2'd1;
    localparam OP_BUNDLE = 2'd2;

    wire bind_valid,   bundle_valid;
    wire [DIM*2-1:0]   bind_result, bundle_result;

    vsa_bind #(.DIM(DIM)) u_bind (
        .clk(clk), .rst(rst), .valid_in(valid_in && op == OP_BIND),
        .a(a), .b(b), .valid_out(bind_valid), .result(bind_result)
    );

    vsa_bind #(.DIM(DIM)) u_unbind (
        .clk(clk), .rst(rst), .valid_in(valid_in && op == OP_UNBIND),
        .a(a), .b(b), .valid_out(), .result()
    );

    vsa_bundle #(.DIM(DIM)) u_bundle (
        .clk(clk), .rst(rst), .valid_in(valid_in && op == OP_BUNDLE),
        .a(a), .b(b), .valid_out(bundle_valid), .result(bundle_result)
    );

    reg [1:0] op_d;
    always @(posedge clk) begin
        if (rst)
            op_d <= 2'd0;
        else
            op_d <= op;
    end

    assign valid_out = bind_valid | bundle_valid;

    assign result = (op_d == OP_BUNDLE) ? bundle_result : bind_result;

    reg [23:0] blink;
    always @(posedge clk)
        blink <= blink + 1;

    assign led = blink[23];

endmodule

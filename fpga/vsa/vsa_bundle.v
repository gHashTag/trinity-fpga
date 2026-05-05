`default_nettype wire

module vsa_bundle #(
    parameter DIM = 10000
)(
    input  wire                  clk,
    input  wire                  rst,
    input  wire                  valid_in,
    input  wire [DIM*2-1:0]      a,
    input  wire [DIM*2-1:0]      b,
    output reg                   valid_out,
    output reg  [DIM*2-1:0]      result
);

    wire [1:0] trit_r [0:DIM-1];

    genvar i;
    generate
        for (i = 0; i < DIM; i = i + 1) begin : gen_bundle
            wire [1:0] a_t = a[i*2 +: 2];
            wire [1:0] b_t = b[i*2 +: 2];

            wire a_neg = (a_t == 2'b10);
            wire a_pos = (a_t == 2'b01);
            wire b_neg = (b_t == 2'b10);
            wire b_pos = (b_t == 2'b01);

            assign trit_r[i] = (a_neg && b_neg) ? 2'b10 :
                               (a_pos && b_pos) ? 2'b01 :
                               (a_t == 2'b00)   ? b_t   :
                               (b_t == 2'b00)   ? a_t   :
                                                   2'b00;
        end
    endgenerate

    integer j;
    always @(posedge clk) begin
        if (rst) begin
            valid_out <= 1'b0;
            for (j = 0; j < DIM; j = j + 1)
                result[j*2 +: 2] <= 2'b00;
        end else begin
            valid_out <= valid_in;
            for (j = 0; j < DIM; j = j + 1)
                result[j*2 +: 2] <= trit_r[j];
        end
    end

endmodule

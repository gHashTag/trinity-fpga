// APoT scale applier: alpha = sum of NT power-of-two terms, each signed.
// One cycle: NT barrel shifts and NT-1 adds.  This is the deployed state of
// the art for multiplier-free scales (Additive Powers-of-Two, ICLR 2020).
//
// NT = 2 is a single layer's scale.  NT = 4 is what TWO composed APoT-2 scales
// become, which is the case a chain without requantisation actually presents:
// a low-rank factorisation W = U*V, a folded conv+batchnorm, a residual branch.
module scale_apot #(
    parameter integer ACC = 32,
    parameter integer NT  = 2,          // number of power-of-two terms
    parameter integer SW  = 5           // shift amount width
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [ACC-1:0]   acc,
    input  wire        [NT*SW-1:0] sh,          // packed shift amounts
    input  wire        [NT-1:0]    sgn,         // per-term sign
    output reg  signed [ACC-1:0]   out,
    output reg                     done
);
    integer i;
    reg signed [ACC-1:0] sum;
    always @(*) begin
        sum = {ACC{1'b0}};
        for (i = 0; i < NT; i = i + 1)
            sum = sgn[i] ? (sum - (acc >>> sh[i*SW +: SW]))
                         : (sum + (acc >>> sh[i*SW +: SW]));
    end
    always @(posedge clk) begin
        if (rst) begin out <= 0; done <= 1'b0; end
        else begin done <= start; if (start) out <= sum; end
    end
endmodule

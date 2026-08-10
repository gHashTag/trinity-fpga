// phi^k with k known at synthesis time: the Fibonacci step unrolled K times.
//
// Fair counterpart to scale_apot_const.  Each step is one adder on the pair, so
// the unrolled cost is K adders -- linear in K, where APoT's constant-shift cost
// is flat.  Built to find out how badly that loses, not to argue it does not.
module scale_phi_const #(
    parameter integer ACC = 32,
    parameter integer K   = 8
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [ACC-1:0]   in_a,
    input  wire signed [ACC-1:0]   in_b,
    output reg  signed [ACC-1:0]   out_a,
    output reg  signed [ACC-1:0]   out_b,
    output reg                     done
);
    // divide by phi^K : (a,b) -> (b-a, a), unrolled
    reg signed [ACC-1:0] a [0:K];
    reg signed [ACC-1:0] b [0:K];
    integer i;
    always @(*) begin
        a[0] = in_a; b[0] = in_b;
        for (i = 0; i < K; i = i + 1) begin
            a[i+1] = b[i] - a[i];
            b[i+1] = a[i];
        end
    end
    always @(posedge clk) begin
        if (rst) begin out_a <= 0; out_b <= 0; done <= 1'b0; end
        else begin
            done <= start;
            if (start) begin out_a <= a[K]; out_b <= b[K]; end
        end
    end
endmodule

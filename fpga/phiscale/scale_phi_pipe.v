// The phi scale with the cycles taken back.
//
// scale_phi.v applies phi^k by iterating the Fibonacci step k times: one adder,
// k cycles. Measured against a real multiplier by place-and-route (FMAX.md), it
// is 2.58x smaller and 2.09x faster on the clock -- and 2.15x SLOWER per output
// element at the |k| = 8 a deployed layer needs, because the multiplier
// finishes in one cycle.
//
// This takes the cycles back. The step is unrolled into K_MAX pipeline stages;
// stage j applies (a,b) -> (b, a+b) when j < k and passes through otherwise.
// Latency is K_MAX cycles, throughput is one element per cycle -- the same as
// the multiplier -- and the multiplier still never appears.
//
// The closed-form "barrel" was rejected on purpose. phi^k = F(k-1) + F(k)*phi
// gives a' = a*F(k-1) + b*F(k) and b' = a*F(k) + b*F(k+1): two multiplications
// by Fibonacci constants, which puts back the operator this whole line exists
// to remove.
`default_nettype none
module scale_phi_pipe #(
    parameter integer ACC   = 16,
    parameter integer KW    = 4,
    parameter integer K_MAX = 8
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    in_valid,
    input  wire signed [ACC-1:0]   acc_a,
    input  wire signed [ACC-1:0]   acc_b,
    input  wire        [KW-1:0]    k,
    output wire signed [ACC-1:0]   out_a,
    output wire signed [ACC-1:0]   out_b,
    output wire                    out_valid
);
    // Stage 0 is the input register; stage j+1 holds the value after step j
    // has been considered.
    //
    // Each element of these arrays is driven by exactly ONE always block. The
    // first version reset the whole array in a separate block and drove
    // pa[j+1] from the generate loop as well -- two drivers on one variable.
    // Yosys pruned nearly all of it and reported 2 logic cells for an
    // eight-stage 16-bit pipeline, which is the shape a fold always has: a
    // number far too small rather than an error.
    reg signed [ACC-1:0] pa [0:K_MAX];
    reg signed [ACC-1:0] pb [0:K_MAX];
    reg        [KW-1:0]  pk [0:K_MAX];
    reg                  pv [0:K_MAX];

    genvar j;

    always @(posedge clk) begin
        if (rst) begin
            pa[0] <= {ACC{1'b0}};
            pb[0] <= {ACC{1'b0}};
            pk[0] <= {KW{1'b0}};
            pv[0] <= 1'b0;
        end else begin
            pa[0] <= acc_a;
            pb[0] <= acc_b;
            pk[0] <= k;
            pv[0] <= in_valid;
        end
    end

    generate
        for (j = 0; j < K_MAX; j = j + 1) begin : stage
            always @(posedge clk) begin
                if (rst) begin
                    pa[j+1] <= {ACC{1'b0}};
                    pb[j+1] <= {ACC{1'b0}};
                    pk[j+1] <= {KW{1'b0}};
                    pv[j+1] <= 1'b0;
                end else begin
                    // One adder and one mux. The comparison is against a
                    // constant index, so it costs nothing at synthesis.
                    if (pk[j] > j[KW-1:0]) begin
                        pa[j+1] <= pb[j];
                        pb[j+1] <= pa[j] + pb[j];
                    end else begin
                        pa[j+1] <= pa[j];
                        pb[j+1] <= pb[j];
                    end
                    pk[j+1] <= pk[j];
                    pv[j+1] <= pv[j];
                end
            end
        end
    endgenerate

    assign out_a     = pa[K_MAX];
    assign out_b     = pb[K_MAX];
    assign out_valid = pv[K_MAX];
endmodule

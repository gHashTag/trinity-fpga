// Arm B -- the scale applier the golden alphabet allows.
//
// A value is carried as an integer pair (a, b) standing for a + b*phi.  The
// layer scale is phi^k, and by phi^2 = phi + 1 multiplying by phi is
//
//     (a, b) -> (b, a + b)
//
// the Fibonacci step: ONE integer addition, no shift and no multiplier.  A
// runtime exponent k is applied by iterating the step k times, so the whole
// scale path is one adder, two registers and a counter.
//
// Exactness is not approximate here: Z[phi] is closed, so the pair is the
// value, not a rounding of it.  See derivations/golden_alphabet in
// gHashTag/trinity-s3ai for the machine-checked statement.
module scale_phi #(
    parameter integer ACC = 32,
    parameter integer KW  = 5           // exponent k, 0..31
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [ACC-1:0]   acc_a,      // a
    input  wire signed [ACC-1:0]   acc_b,      // b
    input  wire        [KW-1:0]    k,
    output reg  signed [ACC-1:0]   out_a,
    output reg  signed [ACC-1:0]   out_b,
    output reg                     done
);
    reg signed [ACC-1:0] a, b;
    reg        [KW-1:0]  cnt;
    reg                  busy;

    always @(posedge clk) begin
        if (rst) begin
            a <= 0; b <= 0; cnt <= 0; busy <= 1'b0; done <= 1'b0;
            out_a <= 0; out_b <= 0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                a <= acc_a; b <= acc_b; cnt <= k; busy <= 1'b1;
                if (k == 0) begin
                    out_a <= acc_a; out_b <= acc_b; done <= 1'b1; busy <= 1'b0;
                end
            end else if (busy) begin
                if (cnt == 0) begin
                    out_a <= a; out_b <= b; done <= 1'b1; busy <= 1'b0;
                end else begin
                    a   <= b;            // the Fibonacci step: one adder
                    b   <= a + b;
                    cnt <= cnt - 1'b1;
                end
            end
        end
    end
endmodule

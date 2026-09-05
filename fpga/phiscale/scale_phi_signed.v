// The deployable scale applier: phi^k for SIGNED k.
//
// Real layer scales are below one -- alpha = mean|W| is around 0.02, so
// k = round(log_phi alpha) is about -8.  The previous version implemented only
// the forward step and was therefore not the circuit a layer would use.
//
// Both directions are one add-class operation on the integer pair:
//
//     multiply by phi     (a, b) -> (b,     a + b)     since phi^2 = phi + 1
//     divide   by phi     (a, b) -> (b - a, a)         since phi^-1 = phi - 1
//
// Derivation of the inverse, so it is checkable rather than asserted:
//     (a + b*phi) * (phi - 1) = a*phi - a + b*phi^2 - b*phi
//                             = a*phi - a + b*(phi + 1) - b*phi
//                             = (b - a) + a*phi
//
// Exact in Z[phi] either way: the pair is the value, not a rounding of it.
module scale_phi_signed #(
    parameter integer ACC = 32,
    parameter integer KW  = 5           // magnitude of k, 0..31
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [ACC-1:0]   acc_a,
    input  wire signed [ACC-1:0]   acc_b,
    input  wire        [KW-1:0]    k_mag,
    input  wire                    k_neg,      // 1 = divide by phi^|k|
    output reg  signed [ACC-1:0]   out_a,
    output reg  signed [ACC-1:0]   out_b,
    output reg                     done
);
    reg signed [ACC-1:0] a, b;
    reg        [KW-1:0]  cnt;
    reg                  busy, dir;

    always @(posedge clk) begin
        if (rst) begin
            a <= 0; b <= 0; cnt <= 0; busy <= 1'b0; dir <= 1'b0;
            done <= 1'b0; out_a <= 0; out_b <= 0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                a <= acc_a; b <= acc_b; cnt <= k_mag; dir <= k_neg;
                if (k_mag == 0) begin
                    out_a <= acc_a; out_b <= acc_b; done <= 1'b1;
                end else busy <= 1'b1;
            end else if (busy) begin
                if (cnt == 0) begin
                    out_a <= a; out_b <= b; done <= 1'b1; busy <= 1'b0;
                end else begin
                    if (dir) begin a <= b - a; b <= a; end   // divide
                    else     begin a <= b;     b <= a + b; end // multiply
                    cnt <= cnt - 1'b1;
                end
            end
        end
    end
endmodule

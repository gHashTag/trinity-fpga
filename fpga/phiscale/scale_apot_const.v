// APoT with the shift amounts known at synthesis time.
//
// If a layer's scale is frozen after training, the shifts are CONSTANTS, and a
// constant shift in hardware is wiring -- it costs nothing.  This is the
// strongest case against our area claim, so we build it ourselves rather than
// wait for it to be raised.
module scale_apot_const #(
    parameter integer ACC = 32,
    parameter integer S0  = 5,          // constant shift, term 0
    parameter integer S1  = 9           // constant shift, term 1
)(
    input  wire                    clk,
    input  wire                    rst,
    input  wire                    start,
    input  wire signed [ACC-1:0]   acc,
    output reg  signed [ACC-1:0]   out,
    output reg                     done
);
    wire signed [ACC-1:0] sum = (acc >>> S0) + (acc >>> S1);   // wiring + 1 adder
    always @(posedge clk) begin
        if (rst) begin out <= 0; done <= 1'b0; end
        else begin done <= start; if (start) out <= sum; end
    end
endmodule

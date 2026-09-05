// Element decoder for the ladder r^2 = r^1 + 1  (r = 1.618034), 4-bit code.
//
// A weight of the ladder is r^-j. Applying it by ITERATION costs j steps, which
// is amortised over 32 weights when the ladder is a block scale and paid per
// weight when it is an element. So the element form is a table: 7 magnitudes
// x 2 integer coordinates, each 5 bits, plus sign and zero.
`default_nettype none
module elem_phi (input wire clk, input wire [3:0] code,
    output reg signed [9:0] coord, output reg zero, output reg neg);
    always @(posedge clk) begin
        neg  <= code[3];
        zero <= (code[2:0] == 3'd0);
        case (code[2:0])
            3'd0: coord <= {5'sd0, 5'sd1};
            3'd1: coord <= {5'sd1, 5'sd0};
            3'd2: coord <= {5'sd1, 5'sd1};
            3'd3: coord <= {5'sd2, 5'sd1};
            3'd4: coord <= {5'sd3, 5'sd2};
            3'd5: coord <= {5'sd5, 5'sd3};
            3'd6: coord <= {5'sd8, 5'sd5};
            default: coord <= 10'sd0;
        endcase
    end
endmodule

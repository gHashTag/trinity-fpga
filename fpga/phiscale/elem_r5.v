// Element decoder for the ladder r^5 = r^3 + 1  (r = 1.236506), 5-bit code.
//
// A weight of the ladder is r^-j. Applying it by ITERATION costs j steps, which
// is amortised over 32 weights when the ladder is a block scale and paid per
// weight when it is an element. So the element form is a table: 15 magnitudes
// x 5 integer coordinates, each 4 bits, plus sign and zero.
`default_nettype none
module elem_r5 (input wire clk, input wire [4:0] code,
    output reg signed [19:0] coord, output reg zero, output reg neg);
    always @(posedge clk) begin
        neg  <= code[4];
        zero <= (code[3:0] == 4'd0);
        case (code[3:0])
            4'd0: coord <= {4'sd0, 4'sd0, 4'sd0, 4'sd0, 4'sd1};
            4'd1: coord <= {4'sd0, 4'sd0, 4'sd0, 4'sd1, 4'sd0};
            4'd2: coord <= {4'sd0, 4'sd0, 4'sd1, 4'sd0, 4'sd0};
            4'd3: coord <= {4'sd0, 4'sd1, 4'sd0, 4'sd0, 4'sd0};
            4'd4: coord <= {4'sd1, 4'sd0, 4'sd0, 4'sd0, 4'sd0};
            4'd5: coord <= {4'sd0, 4'sd1, 4'sd0, 4'sd0, 4'sd1};
            4'd6: coord <= {4'sd1, 4'sd0, 4'sd0, 4'sd1, 4'sd0};
            4'd7: coord <= {4'sd0, 4'sd1, 4'sd1, 4'sd0, 4'sd1};
            4'd8: coord <= {4'sd1, 4'sd1, 4'sd0, 4'sd1, 4'sd0};
            4'd9: coord <= {4'sd1, 4'sd1, 4'sd1, 4'sd0, 4'sd1};
            4'd10: coord <= {4'sd1, 4'sd2, 4'sd0, 4'sd1, 4'sd1};
            4'd11: coord <= {4'sd2, 4'sd1, 4'sd1, 4'sd1, 4'sd1};
            4'd12: coord <= {4'sd1, 4'sd3, 4'sd1, 4'sd1, 4'sd2};
            4'd13: coord <= {4'sd3, 4'sd2, 4'sd1, 4'sd2, 4'sd1};
            4'd14: coord <= {4'sd2, 4'sd4, 4'sd2, 4'sd1, 4'sd3};
            default: coord <= 20'sd0;
        endcase
    end
endmodule

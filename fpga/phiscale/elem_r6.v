// Element decoder for the ladder r^6 = r^1 + 1  (r = 1.134724), 6-bit code.
//
// A weight of the ladder is r^-j. Applying it by ITERATION costs j steps, which
// is amortised over 32 weights when the ladder is a block scale and paid per
// weight when it is an element. So the element form is a table: 31 magnitudes
// x 6 integer coordinates, each 5 bits, plus sign and zero.
`default_nettype none
module elem_r6 (input wire clk, input wire [5:0] code,
    output reg signed [29:0] coord, output reg zero, output reg neg);
    always @(posedge clk) begin
        neg  <= code[5];
        zero <= (code[4:0] == 5'd0);
        case (code[4:0])
            5'd0: coord <= {5'sd0, 5'sd0, 5'sd0, 5'sd0, 5'sd0, 5'sd1};
            5'd1: coord <= {5'sd0, 5'sd0, 5'sd0, 5'sd0, 5'sd1, 5'sd0};
            5'd2: coord <= {5'sd0, 5'sd0, 5'sd0, 5'sd1, 5'sd0, 5'sd0};
            5'd3: coord <= {5'sd0, 5'sd0, 5'sd1, 5'sd0, 5'sd0, 5'sd0};
            5'd4: coord <= {5'sd0, 5'sd1, 5'sd0, 5'sd0, 5'sd0, 5'sd0};
            5'd5: coord <= {5'sd1, 5'sd0, 5'sd0, 5'sd0, 5'sd0, 5'sd0};
            5'd6: coord <= {5'sd0, 5'sd0, 5'sd0, 5'sd0, 5'sd1, 5'sd1};
            5'd7: coord <= {5'sd0, 5'sd0, 5'sd0, 5'sd1, 5'sd1, 5'sd0};
            5'd8: coord <= {5'sd0, 5'sd0, 5'sd1, 5'sd1, 5'sd0, 5'sd0};
            5'd9: coord <= {5'sd0, 5'sd1, 5'sd1, 5'sd0, 5'sd0, 5'sd0};
            5'd10: coord <= {5'sd1, 5'sd1, 5'sd0, 5'sd0, 5'sd0, 5'sd0};
            5'd11: coord <= {5'sd1, 5'sd0, 5'sd0, 5'sd0, 5'sd1, 5'sd1};
            5'd12: coord <= {5'sd0, 5'sd0, 5'sd0, 5'sd1, 5'sd2, 5'sd1};
            5'd13: coord <= {5'sd0, 5'sd0, 5'sd1, 5'sd2, 5'sd1, 5'sd0};
            5'd14: coord <= {5'sd0, 5'sd1, 5'sd2, 5'sd1, 5'sd0, 5'sd0};
            5'd15: coord <= {5'sd1, 5'sd2, 5'sd1, 5'sd0, 5'sd0, 5'sd0};
            5'd16: coord <= {5'sd2, 5'sd1, 5'sd0, 5'sd0, 5'sd1, 5'sd1};
            5'd17: coord <= {5'sd1, 5'sd0, 5'sd0, 5'sd1, 5'sd3, 5'sd2};
            5'd18: coord <= {5'sd0, 5'sd0, 5'sd1, 5'sd3, 5'sd3, 5'sd1};
            5'd19: coord <= {5'sd0, 5'sd1, 5'sd3, 5'sd3, 5'sd1, 5'sd0};
            5'd20: coord <= {5'sd1, 5'sd3, 5'sd3, 5'sd1, 5'sd0, 5'sd0};
            5'd21: coord <= {5'sd3, 5'sd3, 5'sd1, 5'sd0, 5'sd1, 5'sd1};
            5'd22: coord <= {5'sd3, 5'sd1, 5'sd0, 5'sd1, 5'sd4, 5'sd3};
            5'd23: coord <= {5'sd1, 5'sd0, 5'sd1, 5'sd4, 5'sd6, 5'sd3};
            5'd24: coord <= {5'sd0, 5'sd1, 5'sd4, 5'sd6, 5'sd4, 5'sd1};
            5'd25: coord <= {5'sd1, 5'sd4, 5'sd6, 5'sd4, 5'sd1, 5'sd0};
            5'd26: coord <= {5'sd4, 5'sd6, 5'sd4, 5'sd1, 5'sd1, 5'sd1};
            5'd27: coord <= {5'sd6, 5'sd4, 5'sd1, 5'sd1, 5'sd5, 5'sd4};
            5'd28: coord <= {5'sd4, 5'sd1, 5'sd1, 5'sd5, 5'sd10, 5'sd6};
            5'd29: coord <= {5'sd1, 5'sd1, 5'sd5, 5'sd10, 5'sd10, 5'sd4};
            5'd30: coord <= {5'sd1, 5'sd5, 5'sd10, 5'sd10, 5'sd5, 5'sd1};
            default: coord <= 30'sd0;
        endcase
    end
endmodule

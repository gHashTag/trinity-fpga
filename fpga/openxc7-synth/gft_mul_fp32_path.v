// fp32_path — what the board does today: decode both 2-bit codes to fp32,
// run a full fp32 multiplier, then threshold the result back to 2 bits.
// Transcribed from corona_compute_gfternary_mul_ax7203.v.
module fp32_path(input clk, input rst, input valid,
                 input [1:0] a, input [1:0] b, output reg [1:0] y);
    reg [31:0] fa, fb;
    always @(*) case(a) 2'b00: fa=32'h00000000; 2'b01: fa=32'h3FCF1BBD;
                        2'b10: fa=32'hBFCF1BBD; default: fa=32'h3FCF1BBD; endcase
    always @(*) case(b) 2'b00: fb=32'h00000000; 2'b01: fb=32'h3FCF1BBD;
                        2'b10: fb=32'hBFCF1BBD; default: fb=32'h3FCF1BBD; endcase
    wire [31:0] r; wire ov, ir;
    gf_mul_param #(.EXP_BITS(8), .MANT_BITS(23), .HAS_INF(1)) u (
        .clk(clk), .rst(rst), .in_valid(valid), .in_a(fa), .in_b(fb),
        .in_ready(ir), .out_valid(ov), .out_y(r), .out_ready(1'b1));
    always @(*) begin
        if (r == 32'h00000000) y = 2'd0;
        else if (r[31]) y = (r >= 32'hBF000000) ? 2'd2 : 2'd0;
        else if (r >= 32'h3F800000) y = 2'd1;
        else if (r >= 32'h3E800000) y = 2'd1;
        else y = 2'd0;
    end
endmodule

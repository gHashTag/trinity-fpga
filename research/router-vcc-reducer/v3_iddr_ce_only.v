// v3 — CE tied high, R/S from ports. Narrows which tie matters.
module top (input wire clk, input wire d, input wire r, input wire s,
            output wire q1, output wire q2);
    IDDR #(.DDR_CLK_EDGE("SAME_EDGE"), .INIT_Q1(1'b0), .INIT_Q2(1'b0), .SRTYPE("SYNC"))
      u (.C(clk), .CE(1'b1), .D(d), .R(r), .S(s), .Q1(q1), .Q2(q2));
endmodule

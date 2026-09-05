// v5 — IDDR with R/S tied, CE from a port. The complement of v3.
module top (input wire clk, input wire d, input wire ce, output wire q1, output wire q2);
    IDDR #(.DDR_CLK_EDGE("SAME_EDGE"), .INIT_Q1(1'b0), .INIT_Q2(1'b0), .SRTYPE("SYNC"))
      u (.C(clk), .CE(ce), .D(d), .R(1'b0), .S(1'b0), .Q1(q1), .Q2(q2));
endmodule

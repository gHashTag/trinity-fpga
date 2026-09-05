// v2 — same IDDR, but CE/R/S come from ports. Isolates the constant tie
// from the primitive: if this passes, the trigger is the constant network.
module top (input wire clk, input wire d, input wire ce, input wire r, input wire s,
            output wire q1, output wire q2);
    IDDR #(.DDR_CLK_EDGE("SAME_EDGE"), .INIT_Q1(1'b0), .INIT_Q2(1'b0), .SRTYPE("SYNC"))
      u (.C(clk), .CE(ce), .D(d), .R(r), .S(s), .Q1(q1), .Q2(q2));
endmodule

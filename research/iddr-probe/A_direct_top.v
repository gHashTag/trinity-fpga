// Build A -- IDDR with D taken STRAIGHT FROM THE PAD (no IDELAYE2).
// This is the IFFDELMUXE3 "direct" position, i.e. P1.
module top (
    input  wire clk,
    input  wire d,
    output wire q1,
    output wire q2
);
    IDDR #(
        .DDR_CLK_EDGE("SAME_EDGE"),
        .INIT_Q1(1'b0), .INIT_Q2(1'b0),
        .SRTYPE("SYNC")
    ) u_iddr (
        .C(clk), .CE(1'b1), .D(d), .R(1'b0), .S(1'b0),
        .Q1(q1), .Q2(q2)
    );
endmodule


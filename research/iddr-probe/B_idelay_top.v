// Build B -- IDENTICAL to A except D reaches the IDDR through an IDELAYE2.
// This is the IFFDELMUXE3 "idelay" position, i.e. P0.
// Same pins as A on purpose: the ONLY intended difference between the two
// bitstreams is the mux position.
module top (
    input  wire clk,
    input  wire d,
    output wire q1,
    output wire q2
);
    wire d_dly;

    (* IODELAY_GROUP = "iddr_probe" *)
    IDELAYE2 #(
        .IDELAY_TYPE("FIXED"),
        .IDELAY_VALUE(0),
        .DELAY_SRC("IDATAIN"),
        .HIGH_PERFORMANCE_MODE("FALSE"),
        .SIGNAL_PATTERN("DATA"),
        .REFCLK_FREQUENCY(200.0)
    ) u_dly (
        .C(1'b0), .CE(1'b0), .INC(1'b0), .LD(1'b0), .LDPIPEEN(1'b0),
        .REGRST(1'b0), .CINVCTRL(1'b0), .CNTVALUEIN(5'b0),
        .DATAIN(1'b0), .IDATAIN(d),
        .DATAOUT(d_dly), .CNTVALUEOUT()
    );

    (* IODELAY_GROUP = "iddr_probe" *)
    IDELAYCTRL u_idelayctrl (.REFCLK(clk), .RST(1'b0), .RDY());

    IDDR #(
        .DDR_CLK_EDGE("SAME_EDGE"),
        .INIT_Q1(1'b0), .INIT_Q2(1'b0),
        .SRTYPE("SYNC")
    ) u_iddr (
        .C(clk), .CE(1'b1), .D(d_dly), .R(1'b0), .S(1'b0),
        .Q1(q1), .Q2(q2)
    );
endmodule


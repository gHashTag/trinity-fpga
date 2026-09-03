// BUFR probe A -- BUFR_DIVIDE("5").
//
// Purpose: force the router across the pseudo-pip that carries the BUFR
// configuration,
//
//     HCLK_IOI_RCLK_OUT<i> -> HCLK_IOI_RCLK_BEFORE_DIV<i>
//
// so the emitted FASM contains BUFR_Y<y>.BUFR_DIVIDE.*, and the divide setting
// can be read out of the bitstream instead of assumed.
//
// The clock is taken from a clock-capable pin, buffered by BUFR, and used to
// clock an ODDR -- an OLOGIC flop, which lives in the IOI tile that the
// regional clock feeds. A fabric flip-flop would be reached through a BUFG and
// would not exercise the RCLK path at all; the ODDR is what pulls the clock
// into the I/O column.
//
// Paired with bufr_bypass_top.v, which is identical apart from
// BUFR_DIVIDE("BYPASS"). The two FASMs differ in exactly the bits under test.
//
// On silicon the output pin toggles at BUFR_O/2 (the ODDR halves it), so the
// two builds are distinguishable with a scope or a counter:
//   BYPASS : 100 MHz / 1 / 2 = 50 MHz
//   D5     : 100 MHz / 5 / 2 = 10 MHz
// A five-to-one ratio needs no calibration to be convincing.

module top (
    input  wire clk,
    output wire clk_out
);
    wire clk_ibuf;
    wire bufr_o;

    IBUF ibuf_inst (
        .I (clk),
        .O (clk_ibuf)
    );

    // CE and CLR must be driven; a BUFR held in reset emits nothing and the
    // probe would look like a routing failure.
    BUFR #(
        .BUFR_DIVIDE ("5"),
        .SIM_DEVICE  ("7SERIES")
    ) bufr_inst (
        .I   (clk_ibuf),
        .CE  (1'b1),
        .CLR (1'b0),
        .O   (bufr_o)
    );

    // Clocked from the regional clock, so it must be placed in an IOI tile
    // reachable from this BUFR.
    ODDR #(
        .DDR_CLK_EDGE ("SAME_EDGE"),
        .INIT         (1'b0),
        .SRTYPE       ("SYNC")
    ) oddr_inst (
        .C  (bufr_o),
        .CE (1'b1),
        .D1 (1'b1),
        .D2 (1'b0),
        .R  (1'b0),
        .S  (1'b0),
        .Q  (clk_out)
    );
endmodule

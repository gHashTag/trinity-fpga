// BUFIO probe -- the untested half of nextpnr-xilinx#149.
//
// The BUFR probes cover the divide ladder. Neither instantiates a BUFIO, so
// "BUFIO is not packed" has never been exercised by them. This is the same
// shape with BUFIO in place of BUFR: clock-capable pad, IBUF, BUFIO, ODDR in
// the IOI tile the I/O clock feeds.
//
// BUFIO has no divider and no CE/CLR -- it is the undivided I/O clock buffer,
// so a pass here says the cell packs and places, nothing about BUFR_DIVIDE.

module top (
    input  wire clk,
    output wire clk_out
);
    wire clk_ibuf;
    wire bufio_o;

    IBUF ibuf_inst (
        .I (clk),
        .O (clk_ibuf)
    );

    BUFIO bufio_inst (
        .I (clk_ibuf),
        .O (bufio_o)
    );

    ODDR #(
        .DDR_CLK_EDGE ("SAME_EDGE"),
        .INIT         (1'b0),
        .SRTYPE       ("SYNC")
    ) oddr_inst (
        .C  (bufio_o),
        .CE (1'b1),
        .D1 (1'b1),
        .D2 (1'b0),
        .R  (1'b0),
        .S  (1'b0),
        .Q  (clk_out)
    );
endmodule

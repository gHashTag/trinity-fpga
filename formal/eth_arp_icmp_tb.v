`default_nettype none
`timescale 1ns / 1ps

// =============================================================================
// eth_arp_icmp_tb -- step E3 design against the KSZ9031 frame model
// =============================================================================
// Driven by conformance/eth_arp_icmp_ax7203.py (--sim, --gate): it writes the
// frames of one scenario into a stimulus file (+STIM=...), runs this bench,
// and parses the "TXF ", "UART|" and "TB " lines. The design runs on the
// STARTUPE2 mock (14 ns CFGMCLK, 71.4 MHz); the model links at 100M full
// duplex after auto-negotiation and then plays the stimulus.
//
// Scaled parameters (RTL run; the gate run bakes the same values in by chparam):
//   RST_LOG2 6   ->   896 ns PHY reset   (model demands >= MIN_RST_NS  800)
//   WAIT_LOG2 7  ->  1792 ns before MDIO (model demands >= MIN_WAIT_NS 1500)
//   MDC_LOG2 5   ->   448 ns MDC period  (model demands >= 400, the real limit)
//   POLL_LOG2 17 ->  1.84 ms per poll, WIN_LOG2 12 -> 57.3 us RXC window
//   NOLINK_POLLS 4
// The frame logic has no scaled timer: it runs on RXC at the real 25 MHz.
//
// Pin delays, transport, applied here between design and model:
//   TXC_DLY_PS / TXD_DLY_PS on the design's TXC and on its TXD/TX_CTL. The
//   design delays TXD/TX_CTL through TX_DLY LUT1 stages; in the RTL run those
//   are zero-delay models, so TXD_DLY_PS (default 3000) stands in for them.
//   With both 0 the data changes on the TXC falling edge and the model must
//   flag it (the negative test).
//   RXC_DLY_PS / RXD_DLY_PS are passed to the model (receive side).
//
// End: STIM_TAIL_US after the model has played the whole stimulus, the bench
// waits for LINES_AFTER more complete report lines (the last one holds the
// final counters), then prints
//   TB model_errors=.. mdio_frames=.. mdio_x=.. tx_frames=.. uart_framing=.. lines=..
// =============================================================================
module eth_arp_icmp_tb;
    parameter integer NEVER_LINK  = 0;
    parameter [4:0]   MODEL_ADDR  = 5'd1;
    parameter integer LINES_AFTER = 2;
    parameter integer BIT_NS      = 840;      // BAUD_DIV 60 x 14 ns
    parameter integer TIMEOUT_US  = 60000;
    parameter integer STIM_TAIL_US = 300;
    parameter integer TXC_DLY_PS  = 0;
    parameter integer TXD_DLY_PS  = 3000;
    parameter integer RXC_DLY_PS  = 1200;
    parameter integer RXD_DLY_PS  = 0;

    reg        rst_n = 1'b0;
    wire       uart_tx, eth_rst_n, eth_mdc, eth_rxc, eth_rxctl, eth_txc, eth_txctl;
    wire [3:0] eth_rxd, eth_txd;
    wire       eth_mdio;
    pullup (eth_mdio);                        // the board's MDIO pull-up
    wire [31:0] m_errors, m_frames, m_txf;
    wire        m_done;

`ifdef GATE
    eth_arp_icmp_ax7203 dut (
`else
    eth_arp_icmp_ax7203 #(.RST_LOG2(6), .WAIT_LOG2(7), .POLL_LOG2(17),
        .WIN_LOG2(12), .NOLINK_POLLS(4)) dut (
`endif
        .rst_n(rst_n), .uart_tx(uart_tx), .eth_rst_n(eth_rst_n),
        .eth_mdc(eth_mdc), .eth_mdio(eth_mdio),
        .eth_rxc(eth_rxc), .eth_rxctl(eth_rxctl), .eth_rxd(eth_rxd),
        .eth_txc(eth_txc), .eth_txctl(eth_txctl), .eth_txd(eth_txd));

    // transport delays on the transmit pins
    reg       p_txc = 1'b0, p_txctl = 1'b0;
    reg [3:0] p_txd = 4'd0;
    always @(eth_txc)   p_txc   <= #(TXC_DLY_PS / 1000.0) eth_txc;
    always @(eth_txctl) p_txctl <= #(TXD_DLY_PS / 1000.0) eth_txctl;
    always @(eth_txd)   p_txd   <= #(TXD_DLY_PS / 1000.0) eth_txd;

    ksz9031_frame_model #(.ADDR(MODEL_ADDR), .AN_NS(500000),
        .NEVER_LINK(NEVER_LINK), .MIN_RST_NS(800), .MIN_WAIT_NS(1500),
        .RXC_DLY_PS(RXC_DLY_PS), .RXD_DLY_PS(RXD_DLY_PS)) phy (
        .rst_n(eth_rst_n), .mdc(eth_mdc), .mdio(eth_mdio),
        .rxc(eth_rxc), .rxctl(eth_rxctl), .rxd(eth_rxd),
        .txc(p_txc), .txctl(p_txctl), .txd(p_txd),
        .errors(m_errors), .frames_ok(m_frames), .tx_frames(m_txf),
        .stim_done(m_done));

    // ------------------------------------------------------------ pin checks
    integer mdio_x = 0;
    always @(eth_mdio)
        if ($time > 100 && eth_mdio !== 1'b0 && eth_mdio !== 1'b1) begin
            mdio_x = mdio_x + 1;
            $display("TB ERROR: MDIO=%b at %0t", eth_mdio, $time);
        end

    // ------------------------------------------------------------ UART receiver
    integer   nlines = 0, uart_framing = 0, k;
    reg [7:0] ch;
    reg [8*200-1:0] line = 0;
    always @(negedge uart_tx) begin : rx
        #(BIT_NS / 2);
        if (uart_tx !== 1'b0) uart_framing = uart_framing + 1;
        for (k = 0; k < 8; k = k + 1) begin
            #(BIT_NS);
            ch[k] = uart_tx;
        end
        #(BIT_NS);
        if (uart_tx !== 1'b1) uart_framing = uart_framing + 1;
        if (ch == 8'h0A) begin
            $display("UART|%0s", line);
            line   = 0;
            nlines = nlines + 1;
        end else if (ch != 8'h0D) begin
            line = {line[8*199-1:0], ch};
        end
    end

    // ------------------------------------------------------------ run
    integer n0;
    initial begin
        #200 rst_n = 1'b1;
        wait (m_done === 1'b1);
        $display("TB stim_done t=%0d", $time);
        #(STIM_TAIL_US * 1000.0);
        n0 = nlines;
        wait (nlines >= n0 + LINES_AFTER);
        #1000;
        $display("TB model_errors=%0d mdio_frames=%0d mdio_x=%0d tx_frames=%0d uart_framing=%0d lines=%0d",
                 m_errors, m_frames, mdio_x, m_txf, uart_framing, nlines);
        $finish;
    end
    initial begin
        #(TIMEOUT_US * 1000.0);
        $display("TB TIMEOUT lines=%0d", nlines);
        $finish;
    end
endmodule

`default_nettype wire

`default_nettype none
`timescale 1ns / 1ps

// =============================================================================
// eth_phy_status_tb -- step E2 design against the KSZ9031 status model
// =============================================================================
// Driven by conformance/eth_phy_status_ax7203.py (--sim, --gate); it parses the
// "UART|" and "TB " lines. The design runs on the STARTUPE2 mock (14 ns
// CFGMCLK, 71.4 MHz: faster than the fastest board chip, 68.7 MHz, so every
// "at least N ns" check here is harder than on the board).
//
// Scaled parameters (RTL run; the gate run bakes the same values in by chparam):
//   RST_LOG2 6   ->   896 ns PHY reset   (model demands >= MIN_RST_NS  800)
//   WAIT_LOG2 7  ->  1792 ns before MDIO (model demands >= MIN_WAIT_NS 1500)
//   MDC_LOG2 5   ->   448 ns MDC period  (model demands >= 400, the real limit)
//   POLL_LOG2 17 ->  1.84 ms per poll, WIN_LOG2 12 -> 57.3 us RXC window
//   NOLINK_POLLS 4
// The full-size values are checked against the datasheet by the Python side
// (--static), at the fastest measured CFGMCLK.
//
// Checks, printed on the last line:
//   model_errors  everything ksz9031_status_model counts (reset, MDC, X, frame)
//   mdio_x        MDIO not 0/1 at any time after 100 ns (contention, float)
//   contention    (RTL only) design and model both enable their MDIO driver
//   tx_nonzero    a transmit pin left 0 (TX_CTL high would make the PHY send)
//   uart_framing  a start bit that did not hold, or a stop bit that was not 1
// =============================================================================
module eth_phy_status_tb;
    parameter integer NEVER_LINK = 0;
    parameter [4:0]   MODEL_ADDR = 5'd1;
    parameter integer LINES      = 6;
    parameter integer BIT_NS     = 840;       // BAUD_DIV 60 x 14 ns
    parameter integer TIMEOUT_US = 40000;

    reg        rst_n = 1'b0;
    wire       uart_tx, eth_rst_n, eth_mdc, eth_rxc, eth_rxctl, eth_txc, eth_txctl;
    wire [3:0] eth_rxd, eth_txd;
    wire       eth_mdio;
    pullup (eth_mdio);                        // the board's MDIO pull-up
    wire [31:0] m_errors, m_frames;

`ifdef GATE
    eth_phy_status_ax7203 dut (
`else
    eth_phy_status_ax7203 #(.RST_LOG2(6), .WAIT_LOG2(7), .POLL_LOG2(17),
        .WIN_LOG2(12), .NOLINK_POLLS(4)) dut (
`endif
        .rst_n(rst_n), .uart_tx(uart_tx), .eth_rst_n(eth_rst_n),
        .eth_mdc(eth_mdc), .eth_mdio(eth_mdio),
        .eth_rxc(eth_rxc), .eth_rxctl(eth_rxctl), .eth_rxd(eth_rxd),
        .eth_txc(eth_txc), .eth_txctl(eth_txctl), .eth_txd(eth_txd));

    ksz9031_status_model #(.ADDR(MODEL_ADDR), .AN_NS(500000),
        .NEVER_LINK(NEVER_LINK), .MIN_RST_NS(800), .MIN_WAIT_NS(1500)) phy (
        .rst_n(eth_rst_n), .mdc(eth_mdc), .mdio(eth_mdio),
        .rxc(eth_rxc), .rxctl(eth_rxctl), .rxd(eth_rxd),
        .errors(m_errors), .frames_ok(m_frames));

    // ------------------------------------------------------------ pin checks
    integer mdio_x = 0, tx_nonzero = 0, contention = 0;
    always @(eth_mdio)
        if ($time > 100 && eth_mdio !== 1'b0 && eth_mdio !== 1'b1) begin
            mdio_x = mdio_x + 1;
            $display("TB ERROR: MDIO=%b at %0t", eth_mdio, $time);
        end
    always @(eth_txc or eth_txctl or eth_txd)
        if ($time > 100 && {eth_txc, eth_txctl, eth_txd} !== 6'd0)
            tx_nonzero = tx_nonzero + 1;
`ifndef GATE
    always @(posedge dut.mclk)
        if (dut.mdio_oe && phy.drive) contention = contention + 1;
`endif

    // ------------------------------------------------------------ UART receiver
    integer   nlines = 0, uart_framing = 0, k;
    reg [7:0] ch;
    reg [8*160-1:0] line = 0;
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
            line = {line[8*159-1:0], ch};
        end
    end

    // ------------------------------------------------------------ run
    initial begin
        #200 rst_n = 1'b1;
        wait (nlines >= LINES);
        #1000;
        $display("TB model_errors=%0d mdio_frames=%0d mdio_x=%0d contention=%0d tx_nonzero=%0d uart_framing=%0d lines=%0d",
                 m_errors, m_frames, mdio_x, contention, tx_nonzero, uart_framing, nlines);
        $finish;
    end
    initial begin
        #(TIMEOUT_US * 1000.0);
        $display("TB TIMEOUT lines=%0d", nlines);
        $finish;
    end
endmodule

`default_nettype wire

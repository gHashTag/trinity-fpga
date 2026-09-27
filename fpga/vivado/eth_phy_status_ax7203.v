`default_nettype none

// =============================================================================
// eth_phy_status_ax7203 -- Ethernet step E2: bring up the KSZ9031 PHY, report it
// =============================================================================
// conformance/NODE_ETHERNET_PLAN.md, step E2. Not flashed; the TRI-NET node
// stays on the board. Everything here runs on STARTUPE2 CFGMCLK (65.6-68.7 MHz
// measured), like the node, so no board oscillator is involved.
//
//  1. Hold the PHY in reset (eth_rst_n, D16) for 2^RST_LOG2 cycles (~15 ms),
//     release it, wait 2^WAIT_LOG2 cycles (~31 ms) before the first MDIO access.
//     The FPGA drives this pin, so a stuck PHY can be reset from the design
//     (fpga-synth skill, "Reconfiguration is not a reset").
//  2. MDIO clause 22, MDC = mclk / 2^MDC_LOG2 (~2.1 MHz, KSZ9031 max 2.5 MHz):
//     - read register 2 at PHY addresses 0..31; a PHY that pulls the second
//       turnaround bit low sets its bit in `pm` (answer map);
//     - read PHYID (2, 3) at PHY_ADDR;
//     - advertise 100M only: register 9 &= ~0x0300 (no 1000BASE-T),
//       register 4 &= ~0x0060 (no 10BASE-T), each read back;
//     - BMCR |= 0x1200 (auto-negotiation enable + restart).
//  3. Every 2^POLL_LOG2 cycles (~0.5 s): BMSR twice (bit 2 latches low, so the
//     second read is the current link), register 0x1F (speed/duplex), BMCR;
//     then one text line on uart_tx (N15) at mclk / BAUD_DIV (~1.14 Mbaud).
//  4. If NOLINK_POLLS polls in a row see no link, go back to step 1 and count
//     the retry in `rt` (saturating at 0xFF, never wrapped).
//
// The RGMII receive side is only listened to, on its own clock eth_rxc (B17):
//  - in-band status: RXD[3:0] sampled on rising RXC while RX_CTL is low
//    (RXD[0] link, RXD[2:1] speed 00/01/10 = 10/100/1000, RXD[3] full duplex);
//    RXC runs without a link, so RXC alone is no link evidence (skill, probe);
//  - RXC edges per 2^WIN_LOG2 mclk cycles (125, 25 or 2.5 MHz tells the mode);
//  - RX_CTL rising edges = frame starts seen.
// The transmit pins are driven low: TX_CTL = 0 means the PHY sends nothing.
//
// Report line (120 bytes, every field hex; see eth_phy_status_ax7203.py):
//   E2 n=#### rt=## pm=######## id=######## g9=####>#### a4=####>#### cr=####
//   sr=####/#### pc=#### ib=## rc=###### fr=####\r\n        (one line, no break)
// ib: first digit bit 1 = a PHY answered the last BMSR read at PHY_ADDR (TA
// low), bit 0 = in-band status seen; second digit = last in-band RXD[3:0].
// Link, for the retry logic, is BMSR bit 2 from a read that had a PHY behind it.
// =============================================================================

`timescale 1ns / 1ps

module eth_phy_status_ax7203 #(
    parameter integer RST_LOG2     = 20,   // PHY reset pulse, 2^20 / 67 MHz ~ 15.6 ms
    parameter integer WAIT_LOG2    = 21,   // after release, before MDIO ~ 31 ms
    parameter integer POLL_LOG2    = 25,   // poll + report period ~ 0.5 s
    parameter integer WIN_LOG2     = 20,   // RXC counting window ~ 15.6 ms
    parameter integer MDC_LOG2     = 5,    // MDC = mclk / 32 ~ 2.1 MHz
    parameter integer BAUD_DIV     = 60,   // same divider as the node (~1144744 host rate)
    parameter integer NOLINK_POLLS = 30,   // ~15 s without link -> PHY reset again
    parameter [4:0]   PHY_ADDR     = 5'd1  // ssdm4 bring-up: PHYID answered at address 1
)(
    input  wire       rst_n,        // T6, key, active low
    output reg        uart_tx = 1'b1,   // N15
    output reg        eth_rst_n = 1'b0, // D16, PHY hardware reset, active low
    output wire       eth_mdc,      // B16
    inout  wire       eth_mdio,     // B15
    input  wire       eth_rxc,      // B17 (SRCC)
    input  wire       eth_rxctl,    // A15
    input  wire [3:0] eth_rxd,      // A16 B18 C18 C19
    output wire       eth_txc,      // E18
    output wire       eth_txctl,    // F18
    output wire [3:0] eth_txd       // C20 D20 A19 A18
);

    // ---------------------------------------------------------------- clocking
    wire mclk, eos;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startup (
        .CFGCLK(), .CFGMCLK(mclk), .EOS(eos),
        .CLK(1'b0), .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b0), .PACK(1'b0),
        .USRCCLKO(1'b0), .USRCCLKTS(1'b0), .USRDONEO(1'b0), .USRDONETS(1'b0));

    reg [1:0] rst_s = 2'b11;
    always @(posedge mclk) rst_s <= {rst_s[0], ~rst_n | ~eos};
    wire rst = rst_s[1];

    assign eth_txc   = 1'b0;
    assign eth_txctl = 1'b0;
    assign eth_txd   = 4'd0;

    // --------------------------------------------------------------- MDIO pins
    wire mdio_o, mdio_oe, mdio_i;
    IOBUF u_mdio (.IO(eth_mdio), .I(mdio_o), .T(~mdio_oe), .O(mdio_i));

    reg         m_start = 1'b0, m_wr = 1'b0;
    reg  [4:0]  m_phy = 5'd0, m_reg = 5'd0;
    reg  [15:0] m_wdata = 16'd0;
    wire        m_busy, m_done, m_ta0;
    wire [15:0] m_rdata;
    eth_mdio_c22 #(.DIV_LOG2(MDC_LOG2)) u_mdio_master (
        .clk(mclk), .rst(rst),
        .start(m_start), .wr(m_wr), .phy(m_phy), .regad(m_reg), .wdata(m_wdata),
        .busy(m_busy), .done(m_done), .rdata(m_rdata), .ta0(m_ta0),
        .mdc(eth_mdc), .mdio_o(mdio_o), .mdio_oe(mdio_oe), .mdio_i(mdio_i));

    // ----------------------------------------------------- RGMII receive (RXC)
    wire rxc;
    BUFG u_rxc_bufg (.I(eth_rxc), .O(rxc));

    reg [3:0]  ib_q    = 4'd0;
    reg        ib_seen = 1'b0;
    reg        rxctl_q = 1'b0;
    reg [23:0] rc_bin  = 24'd0, rc_gray = 24'd0;
    reg [15:0] fr_bin  = 16'd0, fr_gray = 16'd0;
    always @(posedge rxc) begin
        rc_bin  <= rc_bin + 24'd1;
        rc_gray <= rc_bin ^ (rc_bin >> 1);
        rxctl_q <= eth_rxctl;
        if (!eth_rxctl) begin
            ib_q    <= eth_rxd;
            ib_seen <= 1'b1;
        end
        if (eth_rxctl && !rxctl_q) fr_bin <= fr_bin + 16'd1;
        fr_gray <= fr_bin ^ (fr_bin >> 1);
    end

    // ---------------------------------------------- into mclk (2-FF, Gray)
    reg [4:0]  ib_s1 = 5'd0, ib_s2 = 5'd0, ib_s3 = 5'd0, ib_m = 5'd0;
    reg [23:0] rc_s1 = 24'd0, rc_s2 = 24'd0;
    reg [15:0] fr_s1 = 16'd0, fr_s2 = 16'd0;
    always @(posedge mclk) begin
        ib_s1 <= {ib_seen, ib_q};
        ib_s2 <= ib_s1;
        ib_s3 <= ib_s2;
        if (ib_s2 == ib_s3) ib_m <= ib_s3;      // take only a value held two cycles
        rc_s1 <= rc_gray; rc_s2 <= rc_s1;
        fr_s1 <= fr_gray; fr_s2 <= fr_s1;
    end

    function [23:0] gray2bin24(input [23:0] g);
        integer i;
        begin
            gray2bin24[23] = g[23];
            for (i = 22; i >= 0; i = i - 1) gray2bin24[i] = gray2bin24[i+1] ^ g[i];
        end
    endfunction
    function [15:0] gray2bin16(input [15:0] g);
        integer i;
        begin
            gray2bin16[15] = g[15];
            for (i = 14; i >= 0; i = i - 1) gray2bin16[i] = gray2bin16[i+1] ^ g[i];
        end
    endfunction

    wire [23:0] rc_now = gray2bin24(rc_s2);
    reg  [23:0] rc_prev = 24'd0, rc_delta = 24'd0;
    reg  [WIN_LOG2-1:0] win = {WIN_LOG2{1'b0}};
    always @(posedge mclk) begin
        win <= win + 1'b1;
        if (&win) begin
            rc_delta <= rc_now - rc_prev;
            rc_prev  <= rc_now;
        end
    end

    // ------------------------------------------------------------- sequencer
    localparam [1:0] PH_RST = 2'd0, PH_WAIT = 2'd1, PH_RUN = 2'd2, PH_IDLE = 2'd3;
    localparam [5:0] OP_POLL = 6'd42, OP_LAST = 6'd45;

    reg [1:0]  ph = PH_RST;
    reg [5:0]  op = 6'd0;
    reg        issued = 1'b0;
    reg [POLL_LOG2-1:0] tmr = {POLL_LOG2{1'b0}};
    reg [7:0]  nolink = 8'd0;
    reg [7:0]  rt = 8'd0;
    reg [15:0] nrep = 16'd0;
    reg [31:0] pm = 32'd0, id = 32'd0;
    reg [15:0] g9b = 16'd0, g9a = 16'd0, a4b = 16'd0, a4a = 16'd0;
    reg [15:0] cr = 16'd0, sr1 = 16'd0, sr2 = 16'd0, pc = 16'd0;
    reg        sr_ok = 1'b0;               // the second BMSR read had a PHY behind it
    reg        rep_go = 1'b0;

    always @(posedge mclk) begin
        m_start <= 1'b0;
        rep_go  <= 1'b0;
        if (rst) begin
            ph <= PH_RST; tmr <= 0; op <= 6'd0; issued <= 1'b0;
            eth_rst_n <= 1'b0; nolink <= 8'd0;
        end else case (ph)
            PH_RST: begin
                eth_rst_n <= 1'b0;
                tmr <= tmr + 1'b1;
                if (tmr[RST_LOG2-1:0] == {RST_LOG2{1'b1}}) begin ph <= PH_WAIT; tmr <= 0; end
            end
            PH_WAIT: begin
                eth_rst_n <= 1'b1;
                tmr <= tmr + 1'b1;
                if (tmr[WAIT_LOG2-1:0] == {WAIT_LOG2{1'b1}}) begin
                    ph <= PH_RUN; tmr <= 0; op <= 6'd0; issued <= 1'b0; pm <= 32'd0;
                end
            end
            PH_RUN: begin
                if (!issued && !m_busy) begin
                    issued  <= 1'b1;
                    m_start <= 1'b1;
                    m_wr    <= 1'b0;
                    m_phy   <= PHY_ADDR;
                    m_wdata <= 16'd0;
                    case (op)
                        6'd32: m_reg <= 5'd2;
                        6'd33: m_reg <= 5'd3;
                        6'd34, 6'd36: m_reg <= 5'd9;
                        6'd35: begin m_reg <= 5'd9; m_wr <= 1'b1; m_wdata <= g9b & ~16'h0300; end
                        6'd37, 6'd39: m_reg <= 5'd4;
                        6'd38: begin m_reg <= 5'd4; m_wr <= 1'b1; m_wdata <= a4b & ~16'h0060; end
                        6'd40, 6'd45: m_reg <= 5'd0;
                        6'd41: begin m_reg <= 5'd0; m_wr <= 1'b1; m_wdata <= cr | 16'h1200; end
                        6'd42, 6'd43: m_reg <= 5'd1;
                        6'd44: m_reg <= 5'd31;
                        default: begin m_reg <= 5'd2; m_phy <= op[4:0]; end   // 0..31: scan
                    endcase
                end else if (m_done) begin
                    issued <= 1'b0;
                    case (op)
                        6'd32: id[31:16] <= m_rdata;
                        6'd33: id[15:0]  <= m_rdata;
                        6'd34: g9b <= m_rdata;
                        6'd36: g9a <= m_rdata;
                        6'd37: a4b <= m_rdata;
                        6'd39: a4a <= m_rdata;
                        6'd40, 6'd45: cr <= m_rdata;
                        6'd42: sr1 <= m_rdata;
                        6'd43: begin sr2 <= m_rdata; sr_ok <= m_ta0; end
                        6'd44: pc  <= m_rdata;
                        6'd35, 6'd38, 6'd41: ;
                        default: pm[op[4:0]] <= m_ta0;
                    endcase
                    if (op == OP_LAST) begin
                        ph <= PH_IDLE; tmr <= 0; rep_go <= 1'b1;
                        nrep <= nrep + 16'd1;
                    end else begin
                        op <= op + 6'd1;
                    end
                end
            end
            PH_IDLE: begin
                tmr <= tmr + 1'b1;
                if (&tmr) begin
                    if (sr_ok && sr2[2]) begin     // an empty bus reads 0xFFFF: not a link
                        nolink <= 8'd0;
                        ph <= PH_RUN; op <= OP_POLL;
                    end else if (nolink == NOLINK_POLLS - 1) begin
                        nolink <= 8'd0;
                        if (rt != 8'hFF) rt <= rt + 8'd1;
                        ph <= PH_RST; tmr <= 0;
                    end else begin
                        nolink <= nolink + 8'd1;
                        ph <= PH_RUN; op <= OP_POLL;
                    end
                end
            end
        endcase
    end

    // ------------------------------------------------------------ report line
    localparam integer TPL_LEN = 120;
    localparam [8*TPL_LEN-1:0] TPL = {
        "E2 n=#### rt=## pm=######## id=######## g9=####>#### a4=####>#### cr=#### ",
        "sr=####/#### pc=#### ib=## rc=###### fr=####", 8'h0D, 8'h0A};
    localparam integer NIB = 66;

    wire [23:0] fr_now = {8'd0, gray2bin16(fr_s2)};
    reg  [4*NIB-1:0] snap = {4*NIB{1'b0}};
    reg  [6:0]  ci = 7'd0;
    reg         sending = 1'b0;
    reg  [9:0]  txsh = 10'h3FF;
    reg  [3:0]  txbit = 4'd0;
    reg  [7:0]  bcnt = 8'd0;

    wire [7:0] tch = TPL[8*(TPL_LEN-1-ci) +: 8];
    wire [3:0] nib = snap[4*NIB-1 -: 4];
    wire [7:0] hex = (nib < 4'd10) ? (8'h30 + nib) : (8'h37 + nib);
    wire [7:0] outc = (tch == "#") ? hex : tch;

    always @(posedge mclk) begin
        if (rst) begin
            sending <= 1'b0; uart_tx <= 1'b1; txsh <= 10'h3FF; txbit <= 4'd0; bcnt <= 8'd0;
        end else begin
            uart_tx <= txsh[0];
            if (!sending) begin
                if (rep_go) begin
                    snap <= {nrep, rt, pm, id, g9b, g9a, a4b, a4a, cr, sr1, sr2, pc,
                             2'd0, sr_ok, ib_m[4], ib_m[3:0], rc_delta, fr_now[15:0]};
                    ci <= 7'd0; sending <= 1'b1; txbit <= 4'd10; bcnt <= 8'd0;
                end
            end else if (bcnt != 8'd0) begin
                bcnt <= bcnt - 8'd1;
            end else if (txbit == 4'd10) begin
                // load the next character (start bit first)
                if (ci == TPL_LEN) begin
                    sending <= 1'b0;
                end else begin
                    txsh  <= {1'b1, outc, 1'b0};
                    if (tch == "#") snap <= {snap[4*NIB-5:0], 4'd0};
                    ci    <= ci + 7'd1;
                    txbit <= 4'd0;
                    bcnt  <= BAUD_DIV - 1;
                end
            end else begin
                txsh  <= {1'b1, txsh[9:1]};
                txbit <= txbit + 4'd1;
                bcnt  <= (txbit == 4'd9) ? 8'd0 : BAUD_DIV - 1;
            end
        end
    end
endmodule

// -----------------------------------------------------------------------------
// eth_mdio_c22 -- one clause-22 MDIO frame per `start`
// -----------------------------------------------------------------------------
// Frame: 32 x 1 preamble, ST 01, OP (10 read / 01 write), PHYAD, REGAD, TA,
// 16 data bits: 64 MDC periods. A period starts with MDC low; the master
// changes MDIO there and MDC rises at mid-period, when the PHY samples. For a
// read the master releases MDIO from bit 46 (TA) on and samples one cycle
// before each rising edge; the PHY launched that bit after the previous rising
// edge (half a period plus earlier). ta0 = second TA bit was low: a PHY
// answered (a bus with nobody on it floats high through the pull-up).
module eth_mdio_c22 #(
    parameter integer DIV_LOG2 = 5
)(
    input  wire        clk,
    input  wire        rst,
    input  wire        start,
    input  wire        wr,
    input  wire [4:0]  phy,
    input  wire [4:0]  regad,
    input  wire [15:0] wdata,
    output reg         busy = 1'b0,
    output reg         done = 1'b0,
    output reg  [15:0] rdata = 16'd0,
    output reg         ta0 = 1'b0,
    output reg         mdc = 1'b0,
    output reg         mdio_o = 1'b1,
    output reg         mdio_oe = 1'b0,
    input  wire        mdio_i
);
    localparam [DIV_LOG2-1:0] HALF = {1'b1, {(DIV_LOG2-1){1'b0}}};
    reg [DIV_LOG2-1:0] div = {DIV_LOG2{1'b0}};
    reg [6:0]  bitn = 7'd0;
    reg [63:0] sh = 64'd0;
    reg        wr_r = 1'b0;
    reg [1:0]  mi_s = 2'b11;

    always @(posedge clk) begin
        mi_s <= {mi_s[0], mdio_i};
        done <= 1'b0;
        if (rst) begin
            busy <= 1'b0; mdc <= 1'b0; mdio_oe <= 1'b0; mdio_o <= 1'b1;
            div <= 0; bitn <= 7'd0;
        end else if (!busy) begin
            mdc <= 1'b0; mdio_oe <= 1'b0;
            if (start) begin
                busy <= 1'b1; div <= 0; bitn <= 7'd0; wr_r <= wr;
                sh <= {32'hFFFF_FFFF, 2'b01, (wr ? 2'b01 : 2'b10), phy, regad,
                       (wr ? 2'b10 : 2'b11), (wr ? wdata : 16'hFFFF)};
            end
        end else begin
            div <= div + 1'b1;
            if (div == 0) begin
                mdc <= 1'b0;
                if (bitn == 7'd64) begin
                    busy <= 1'b0; done <= 1'b1; mdio_oe <= 1'b0;
                end else begin
                    mdio_o  <= sh[63];
                    mdio_oe <= wr_r || (bitn < 7'd46);
                    sh      <= {sh[62:0], 1'b0};
                end
            end
            if (div == HALF - 1'b1 && !wr_r) begin
                if (bitn == 7'd47) ta0 <= ~mi_s[1];
                if (bitn >= 7'd48 && bitn < 7'd64) rdata <= {rdata[14:0], mi_s[1]};
            end
            if (div == HALF && bitn != 7'd64) mdc <= 1'b1;
            if (&div) bitn <= bitn + 7'd1;
        end
    end
endmodule

`default_nettype wire

`default_nettype none

// =============================================================================
// eth_arp_icmp_ax7203 -- Ethernet step E3: answer ARP and ping at 192.168.1.222
// =============================================================================
// conformance/NODE_ETHERNET_PLAN.md, step E3. Built and simulated, NOT flashed.
// The PHY bring-up, the MDIO poll and the report are E2's
// (eth_phy_status_ax7203.v), unchanged except for the added report fields.
// On top of that, on the PHY's own receive clock:
//
//  1. Receive: RXD/RX_CTL are sampled on the FALLING edge of RXC. At 100M the
//     RGMII nibble is 40 ns long and the PHY changes it near the rising edge
//     (edge aligned; the KSZ9031 adds an internal RX clock delay of about
//     1.2 ns by default, a figure taken from the Linux micrel driver, not
//     from the datasheet). The falling edge is mid-nibble: about +-20 ns of
//     margin whatever that delay really is, where a rising-edge sample would
//     have 1-2 ns and no constraint in this flow to hold it. The samples move
//     to the rising edge half a period later (20 ns at 100M).
//     A second, rising-edge copy of RXD is compared with the falling-edge one
//     inside every frame; mismatches count in `ed` (0 means a rising-edge
//     sample would have worked too; not 0 means this choice mattered).
//  2. Frame check: preamble 5..5 D, bytes low nibble first, CRC-32 per nibble
//     (residue 0xDEBB20E3), >= 64 bytes, whole bytes. The IPv4 header checksum
//     and the ICMP checksum are summed as the bytes go by. Bad FCS: dropped,
//     counted in `fe`. Good FCS but a bad IP or ICMP checksum on a packet for
//     us: dropped, counted in `ce`.
//  3. Answered, everything else ignored:
//     - ARP request (Ethernet/IPv4, op 1), to broadcast or to MAC, target IP;
//     - ICMP echo request (type 8 code 0) to MAC and IP, IPv4 without options,
//       not a fragment, whole datagram in the frame and in one buffer slot.
//     The frame is stored in a 2-slot buffer (2 x 2^SLOT_LOG2 bytes, one
//     RAMB36 at the default 2 KiB per slot: ping payloads up to 1472 bytes).
//     E2 used no BRAM, and neither does the node: this is the first RAMB in a
//     bitstream from this flow on this board. A request that finds both slots
//     busy is counted but not answered.
//  4. Transmit: the reply is built from a template plus bytes of the stored
//     request, padded to 60 bytes; the new IP header checksum, the ICMP
//     checksum and the FCS come from the hardware. Preamble 15 x 5 + D,
//     at least 24 idle nibbles (12 bytes) between frames. TTL = 64.
//
// Transmit clock: TXC is RXC, inverted. At a 100M link RXC is the recovered
// 25 MHz of the link partner (within 100 ppm by 802.3), and the PHY re-times
// transmit data into its own 25 MHz through a FIFO, so this is within spec;
// CFGMCLK (65.6-68.7 MHz, not a 25 MHz multiple, +-5 % chip to chip) is not,
// and the 200 MHz oscillator has never been used on this board in this flow.
// No ODDR: at 100M RGMII carries the same nibble on both TXC edges, so plain
// flip-flops do (an ODDR has no simulation model in yosys' cells_sim.v and
// nothing in this flow has proven it on the board). TXC itself is two
// flip-flops XNORed: tq_p toggles on the rising edge, tq_n copies it on the
// falling edge, so TXC is ~RXC delayed by clock-to-out + one LUT, with no
// clock net used as data.
// Skew: TXD and TX_CTL leave flip-flops on the RXC rising edge, i.e. at the
// TXC falling edge. The PHY takes TX_EN on the TXC rising edge (mid-nibble,
// ~20 ns margin) and TX_EN xor TX_ER on the falling edge; its default TX
// internal delay is 0 ns (micrel driver again). If TX_CTL fell before the PHY
// sampled that falling edge, the last FCS nibble would be sent as an error.
// So every TX data pin goes through TX_DLY kept LUT1 stages (~0.3-1 ns each):
// data changes some ns AFTER the falling edge, well before the next rising
// one. The simulation checks setup/hold at the model's pins; only the board
// shows the real route delays.
// No link: RXC keeps running (125 MHz on the KSZ9031), so TXC does too, while
// TX_CTL is held low: the transmitter starts only while the in-band status
// on RXD (RX_CTL low) has read 0xB (link, 100M, full duplex) four nibbles in
// a row, and it aborts, and the buffer is emptied, when that stops.
// The frame logic needs 25 MHz; at 125 MHz (no link) it only sees idle input.
//
// Report line (189 bytes, every field hex; see eth_arp_icmp_ax7203.py):
//   E3 n=#### rt=## pm=######## id=######## g9=####>#### a4=####>#### cr=####
//   sr=####/#### pc=#### ib=## rc=###### fr=#### rx=#### fe=#### ce=####
//   aq=#### ar=#### eq=#### er=#### ed=#### lk=#\r\n     (one line, no break)
// E2's fields as in E2. rx frames received (preamble + SFD seen), fe FCS
// errors, ce checksum errors, aq ARP requests for us, ar ARP replies sent,
// eq echo requests for us, er echo replies sent, ed see 1., lk transmitter
// enabled (in-band 0xB). Counters are 16-bit and wrap.
// =============================================================================

`timescale 1ns / 1ps

module eth_arp_icmp_ax7203 #(
    parameter integer RST_LOG2     = 20,   // PHY reset pulse, 2^20 / 67 MHz ~ 15.6 ms
    parameter integer WAIT_LOG2    = 21,   // after release, before MDIO ~ 31 ms
    parameter integer POLL_LOG2    = 25,   // poll + report period ~ 0.5 s
    parameter integer WIN_LOG2     = 20,   // RXC counting window ~ 15.6 ms
    parameter integer MDC_LOG2     = 5,    // MDC = mclk / 32 ~ 2.1 MHz
    parameter integer BAUD_DIV     = 60,   // same divider as the node (~1144744 host rate)
    parameter integer NOLINK_POLLS = 30,   // ~15 s without link -> PHY reset again
    parameter [4:0]   PHY_ADDR     = 5'd1, // ssdm4 bring-up: PHYID answered at address 1
    parameter [47:0]  MAC          = 48'h02_00_5E_F9_00_01,      // locally administered
    parameter [31:0]  IP           = {8'd192, 8'd168, 8'd1, 8'd222},
    parameter [7:0]   TTL          = 8'd64,
    parameter integer SLOT_LOG2    = 11,   // 2 x 2 KiB buffer = one RAMB36
    parameter integer TX_DLY       = 10    // LUT1 stages on each TX data pin
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

    // --------------------------------------------------------------- MDIO pins
    wire mdio_o, mdio_oe, mdio_i;
    IOBUF u_mdio (.IO(eth_mdio), .I(mdio_o), .T(~mdio_oe), .O(mdio_i));

    reg         m_start = 1'b0, m_wr = 1'b0;
    reg  [4:0]  m_phy = 5'd0, m_reg = 5'd0;
    reg  [15:0] m_wdata = 16'd0;
    wire        m_busy, m_done, m_ta0;
    wire [15:0] m_rdata;
    eth3_mdio_c22 #(.DIV_LOG2(MDC_LOG2)) u_mdio_master (
        .clk(mclk), .rst(rst),
        .start(m_start), .wr(m_wr), .phy(m_phy), .regad(m_reg), .wdata(m_wdata),
        .busy(m_busy), .done(m_done), .rdata(m_rdata), .ta0(m_ta0),
        .mdc(eth_mdc), .mdio_o(mdio_o), .mdio_oe(mdio_oe), .mdio_i(mdio_i));

    // ----------------------------------------------------- RGMII receive (RXC)
    wire rxc;
    BUFG u_rxc_bufg (.I(eth_rxc), .O(rxc));

    // E2's rising-edge listeners, unchanged: ib, rc, fr of the report.
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

    // Frame path: falling-edge sample (mid-nibble), then the rising edge.
    reg [3:0] rxd_n = 4'd0;
    reg       rxctl_n = 1'b0;
    always @(negedge rxc) begin
        rxd_n   <= eth_rxd;
        rxctl_n <= eth_rxctl;
    end
    reg [3:0] rd = 4'd0, rxd_p1 = 4'd0, rxd_p2 = 4'd0;
    reg       rdv = 1'b0, rdv_q = 1'b0;
    always @(posedge rxc) begin
        rd     <= rxd_n;                     // nibble k, sampled mid-nibble
        rdv    <= rxctl_n;                   // RX_DV xor RX_ER (an error ends the frame)
        rdv_q  <= rdv;
        rxd_p1 <= eth_rxd;                   // nibble k, sampled at its start (diagnostic)
        rxd_p2 <= rxd_p1;                    // aligned with rd
    end

    // In-band status, from the same samples: 0xB four nibbles in a row = link.
    reg [3:0] ib_last = 4'd0, ibn = 4'd0;
    reg [1:0] ib_cnt  = 2'd0;
    reg       link_ok = 1'b0;
    always @(posedge rxc) begin
        if (!rdv) begin
            ib_last <= rd;
            if (rd != ib_last)       ib_cnt <= 2'd0;
            else if (ib_cnt != 2'd3) ib_cnt <= ib_cnt + 2'd1;
            else                     ibn    <= rd;
        end
        link_ok <= (ibn == 4'hB);
    end

    // ------------------------------------------------------------ helpers
    // CRC-32 (reflected 0xEDB88320) over one nibble, bit 0 first.
    function [31:0] crc_nib(input [31:0] c, input [3:0] d);
        integer k;
        begin
            crc_nib = c;
            for (k = 0; k < 4; k = k + 1)
                crc_nib = (crc_nib[0] ^ d[k]) ? ((crc_nib >> 1) ^ 32'hEDB88320) : (crc_nib >> 1);
        end
    endfunction
    // Ones' complement sum, carry kept in bit 16 and added on the next step.
    function [16:0] csum(input [16:0] s, input [11:0] i, input [7:0] b);
        csum = {1'b0, s[15:0]} + {16'd0, s[16]} + (i[0] ? {9'd0, b} : {1'b0, b, 8'd0});
    endfunction
    function [15:0] fold(input [16:0] s);
        reg [16:0] t;
        begin
            t    = {1'b0, s[15:0]} + {16'd0, s[16]};
            fold = t[15:0] + {15'd0, t[16]};
        end
    endfunction
    function [7:0] mac_byte(input [2:0] i);
        case (i)
            3'd0: mac_byte = MAC[47:40];
            3'd1: mac_byte = MAC[39:32];
            3'd2: mac_byte = MAC[31:24];
            3'd3: mac_byte = MAC[23:16];
            3'd4: mac_byte = MAC[15:8];
            default: mac_byte = MAC[7:0];
        endcase
    endfunction
    function [7:0] ip_byte(input [1:0] i);
        case (i)
            2'd0: ip_byte = IP[31:24];
            2'd1: ip_byte = IP[23:16];
            2'd2: ip_byte = IP[15:8];
            default: ip_byte = IP[7:0];
        endcase
    endfunction
    // {checked, value} of byte i in an ARP request for IP
    function [8:0] arp_exp(input [11:0] i);
        case (i)
            12'd12: arp_exp = {1'b1, 8'h08};   // type ARP
            12'd13: arp_exp = {1'b1, 8'h06};
            12'd14: arp_exp = {1'b1, 8'h00};   // HTYPE Ethernet
            12'd15: arp_exp = {1'b1, 8'h01};
            12'd16: arp_exp = {1'b1, 8'h08};   // PTYPE IPv4
            12'd17: arp_exp = {1'b1, 8'h00};
            12'd18: arp_exp = {1'b1, 8'h06};   // HLEN, PLEN
            12'd19: arp_exp = {1'b1, 8'h04};
            12'd20: arp_exp = {1'b1, 8'h00};   // OPER request
            12'd21: arp_exp = {1'b1, 8'h01};
            12'd38: arp_exp = {1'b1, IP[31:24]};  // TPA
            12'd39: arp_exp = {1'b1, IP[23:16]};
            12'd40: arp_exp = {1'b1, IP[15:8]};
            12'd41: arp_exp = {1'b1, IP[7:0]};
            default: arp_exp = 9'd0;
        endcase
    endfunction
    // {checked, value}: IPv4 without options, then the echo-request fields
    function [8:0] ip4_exp(input [11:0] i);
        case (i)
            12'd12: ip4_exp = {1'b1, 8'h08};
            12'd13: ip4_exp = {1'b1, 8'h00};
            12'd14: ip4_exp = {1'b1, 8'h45};
            default: ip4_exp = 9'd0;
        endcase
    endfunction
    function [8:0] echo_exp(input [11:0] i);
        case (i)
            12'd21: echo_exp = {1'b1, 8'h00};  // fragment offset low (bits 20 below)
            12'd23: echo_exp = {1'b1, 8'h01};  // protocol ICMP
            12'd30: echo_exp = {1'b1, IP[31:24]};
            12'd31: echo_exp = {1'b1, IP[23:16]};
            12'd32: echo_exp = {1'b1, IP[15:8]};
            12'd33: echo_exp = {1'b1, IP[7:0]};
            12'd34: echo_exp = {1'b1, 8'h08};  // echo request
            12'd35: echo_exp = {1'b1, 8'h00};  // code 0
            default: echo_exp = 9'd0;
        endcase
    endfunction

    // ------------------------------------------------------------- buffer
    localparam integer SLOT = 1 << SLOT_LOG2;
    (* ram_style = "block" *) reg [7:0] mem [0:2*SLOT-1];
    wire                 m_we;
    wire [SLOT_LOG2:0]   m_wa, m_ra;
    wire [7:0]           m_wd;
    reg  [7:0]           m_q = 8'd0;
    always @(posedge rxc) begin
        if (m_we) mem[m_wa] <= m_wd;
        m_q <= mem[m_ra];
    end

    // Slot state: pend = holds a request waiting for (or in) transmission.
    reg  [1:0]  pend = 2'b00;
    reg         wslot = 1'b0;            // next slot the receiver fills
    reg         t_slot = 1'b0;           // next slot the transmitter sends
    reg  [1:0]  s_kind = 2'b00;          // 0 ARP, 1 ICMP
    reg  [23:0] s_len = 24'd0;           // reply bytes before padding, per slot
    reg  [31:0] s_cip = 32'd0, s_cic = 32'd0;   // reply IP / ICMP checksums
    reg         t_free = 1'b0;           // transmitter is done reading t_slot

    // ------------------------------------------------------------- receiver
    localparam [1:0] R_PRE = 2'd0, R_DATA = 2'd1, R_SKIP = 2'd2;
    reg [1:0]  r_st  = R_PRE;
    reg        r_5   = 1'b0;             // a preamble 5 seen
    reg        r_h   = 1'b0;             // next nibble is a high nibble
    reg [3:0]  r_lo  = 4'd0;
    reg [11:0] r_n   = 12'd0;            // bytes so far incl. FCS, saturating
    reg [31:0] r_crc = 32'hFFFF_FFFF;
    reg        r_wok = 1'b0;             // the slot was free at SFD
    reg        f_uc = 1'b0, f_bc = 1'b0, f_ip4 = 1'b0, f_echo = 1'b0, f_arp = 1'b0;
    reg [15:0] r_tl  = 16'd0;            // IPv4 total length
    reg [16:0] s_iph = 17'd0, s_rep = 17'd0, s_icm = 17'd0, s_icr = 17'd0;
    reg        i_rx = 1'b0, i_fe = 1'b0, i_ce = 1'b0, i_aq = 1'b0, i_eq = 1'b0, i_ed = 1'b0;

    wire [7:0]  r_b   = {rd, r_lo};
    wire [16:0] r_end = 17'd14 + {1'b0, r_tl};          // end of the IP datagram
    wire [11:0] r_nd  = r_n - 12'd4;                    // bytes without the FCS
    wire [8:0]  e_arp = arp_exp(r_n), e_ip4 = ip4_exp(r_n), e_ech = echo_exp(r_n);
    wire        in_ip  = (r_n >= 12'd14) && (r_n <= 12'd33);
    wire        in_rep = in_ip && !(r_n >= 12'd22 && r_n <= 12'd25);
    wire        in_icm = (r_n >= 12'd34) && ({5'd0, r_n} < r_end);
    wire        in_icr = (r_n >= 12'd38) && ({5'd0, r_n} < r_end);

    assign m_we = (r_st == R_DATA) && rdv && r_h && r_wok && (r_n < SLOT);
    assign m_wa = {wslot, r_n[SLOT_LOG2-1:0]};
    assign m_wd = r_b;

    // verdict, valid on the first idle nibble after the frame
    wire v_fcs = (r_crc == 32'hDEBB20E3) && !r_h && (r_n >= 12'd64);
    wire v_len = (r_tl >= 16'd28) && (r_end <= {5'd0, r_nd}) && (r_end <= SLOT);
    wire v_iph = (fold(s_iph) == 16'hFFFF);
    wire v_icm = (fold(s_icm) == 16'hFFFF);
    wire v_arp = v_fcs && f_arp && (f_uc || f_bc);
    wire v_ech = v_fcs && f_uc && f_ip4 && f_echo && v_len;
    wire v_ping = v_ech && v_iph && v_icm;
    wire v_ce  = v_fcs && f_uc && f_ip4 && (!v_iph || (f_echo && v_len && !v_icm));
    wire v_take = r_wok && link_ok && (v_arp || v_ping);

    always @(posedge rxc) begin
        i_rx <= 1'b0; i_fe <= 1'b0; i_ce <= 1'b0; i_aq <= 1'b0; i_eq <= 1'b0;
        i_ed <= rdv && rdv_q && (rd != rxd_p2);
        case (r_st)
            R_PRE: begin
                if (!rdv) r_5 <= 1'b0;
                else if (rd == 4'h5) r_5 <= 1'b1;
                else if (rd == 4'hD && r_5) begin
                    r_st  <= R_DATA;
                    r_h   <= 1'b0;
                    r_n   <= 12'd0;
                    r_crc <= 32'hFFFF_FFFF;
                    r_wok <= !pend[wslot];
                    f_uc  <= 1'b1; f_bc <= 1'b1; f_ip4 <= 1'b1; f_echo <= 1'b1; f_arp <= 1'b1;
                    r_tl  <= 16'd0;
                    s_iph <= 17'd0; s_rep <= {1'b0, TTL, 8'h01}; s_icm <= 17'd0; s_icr <= 17'd0;
                end else r_st <= R_SKIP;
            end
            R_SKIP: if (!rdv) begin r_st <= R_PRE; r_5 <= 1'b0; end
            default: begin                                          // R_DATA
                if (rdv) begin
                    r_crc <= crc_nib(r_crc, rd);
                    if (!r_h) begin
                        r_lo <= rd; r_h <= 1'b1;
                    end else begin
                        r_h <= 1'b0;
                        if (r_n != 12'hFFF) r_n <= r_n + 12'd1;
                        if (r_n < 12'd6) begin
                            if (r_b != mac_byte(r_n[2:0])) f_uc <= 1'b0;
                            if (r_b != 8'hFF)              f_bc <= 1'b0;
                        end
                        if (e_arp[8] && r_b != e_arp[7:0]) f_arp  <= 1'b0;
                        if (e_ip4[8] && r_b != e_ip4[7:0]) f_ip4  <= 1'b0;
                        if (e_ech[8] && r_b != e_ech[7:0]) f_echo <= 1'b0;
                        if (r_n == 12'd20 && r_b[5:0] != 6'd0) f_echo <= 1'b0;  // MF, offset high
                        if (r_n == 12'd16) r_tl[15:8] <= r_b;
                        if (r_n == 12'd17) r_tl[7:0]  <= r_b;
                        if (in_ip)  s_iph <= csum(s_iph, r_n, r_b);
                        if (in_rep) s_rep <= csum(s_rep, r_n, r_b);
                        if (in_icm) s_icm <= csum(s_icm, r_n, r_b);
                        if (in_icr) s_icr <= csum(s_icr, r_n, r_b);
                    end
                end else begin
                    r_st <= R_PRE; r_5 <= 1'b0;
                    i_rx <= 1'b1;
                    i_fe <= !v_fcs;
                    i_ce <= v_ce;
                    i_aq <= v_arp;
                    i_eq <= v_ping;
                end
            end
        endcase

        // slots: the transmitter frees, the receiver takes; no link empties both
        if (t_free) pend[t_slot] <= 1'b0;
        if (r_st == R_DATA && !rdv && v_take) begin
            pend[wslot]        <= 1'b1;
            wslot              <= ~wslot;
            s_kind[wslot]      <= v_ping;
            s_len[12*wslot +: 12]  <= v_ping ? r_end[11:0] : 12'd42;
            s_cip[16*wslot +: 16]  <= ~fold(s_rep);
            s_cic[16*wslot +: 16]  <= ~fold(s_icr);
        end
        if (!link_ok) begin pend <= 2'b00; wslot <= 1'b0; end
    end

    // ---------------------------------------------------------- transmitter
    localparam [2:0] T_IDLE = 3'd0, T_PRE = 3'd1, T_DATA = 3'd2, T_FCS = 3'd3, T_IFG = 3'd4;
    localparam [4:0] IFG_NIB = 5'd24;    // idle nibbles between frames (12 bytes)
    reg [2:0]  t_st   = T_IDLE;
    reg        t_kind = 1'b0;
    reg [11:0] t_rl   = 12'd0;           // reply bytes before padding
    reg [11:0] t_len  = 12'd0;           // bytes before the FCS, >= 60
    reg [15:0] t_cip  = 16'd0, t_cic = 16'd0;
    reg [11:0] t_i    = 12'd0;           // byte on the wire; 0xFFF in the preamble
    reg        t_h    = 1'b0;
    reg [7:0]  t_b    = 8'd0;
    reg [4:0]  t_c    = 5'd0;
    reg [31:0] t_crc  = 32'hFFFF_FFFF, t_fcs = 32'd0;
    reg [3:0]  txd_q  = 4'd0;
    reg        txctl_q = 1'b0;
    reg        i_ar = 1'b0, i_er = 1'b0;

    // byte j of the reply: where it comes from in the stored request
    function [11:0] rmap(input k, input [11:0] j);
        if (!k) rmap = (j < 12'd6) ? j + 12'd22 : j - 12'd10;   // THA/TPA <- SHA/SPA
        else if (j < 12'd6) rmap = j + 12'd6;                  // dst MAC <- src MAC
        else if (j >= 12'd30 && j < 12'd34) rmap = j - 12'd4;  // dst IP <- src IP
        else rmap = j;                                         // header, id, seq, data
    endfunction
    function [7:0] tbyte(input k, input [11:0] j, input [7:0] m, input [11:0] rl,
                         input [15:0] cip, input [15:0] cic);
        if (j >= rl) tbyte = 8'h00;                                       // padding
        else if (j >= 12'd6 && j < 12'd12) tbyte = mac_byte(j - 12'd6);   // src MAC
        else if (!k) begin
            if (j >= 12'd22 && j < 12'd28)      tbyte = mac_byte(j - 12'd22);  // SHA
            else if (j >= 12'd28 && j < 12'd32) tbyte = ip_byte(j - 12'd28);   // SPA
            else case (j)
                12'd12: tbyte = 8'h08; 12'd13: tbyte = 8'h06;
                12'd14: tbyte = 8'h00; 12'd15: tbyte = 8'h01;
                12'd16: tbyte = 8'h08; 12'd17: tbyte = 8'h00;
                12'd18: tbyte = 8'h06; 12'd19: tbyte = 8'h04;
                12'd20: tbyte = 8'h00; 12'd21: tbyte = 8'h02;   // OPER reply
                default: tbyte = m;                             // dst MAC, THA, TPA
            endcase
        end else begin
            if (j >= 12'd26 && j < 12'd30) tbyte = ip_byte(j - 12'd26);      // src IP
            else case (j)
                12'd12: tbyte = 8'h08; 12'd13: tbyte = 8'h00;
                12'd22: tbyte = TTL;   12'd23: tbyte = 8'h01;
                12'd24: tbyte = cip[15:8]; 12'd25: tbyte = cip[7:0];
                12'd34: tbyte = 8'h00; 12'd35: tbyte = 8'h00;   // echo reply, code 0
                12'd36: tbyte = cic[15:8]; 12'd37: tbyte = cic[7:0];
                default: tbyte = m;
            endcase
        end
    endfunction

    wire [11:0] t_nx  = t_i + 12'd1;
    wire [11:0] t_ra  = rmap(t_kind, t_nx);
    assign m_ra = {t_slot, t_ra[SLOT_LOG2-1:0]};
    wire [7:0]  t_nb  = tbyte(t_kind, t_nx, m_q, t_rl, t_cip, t_cic);
    wire [3:0]  t_nib = t_h ? t_b[7:4] : t_b[3:0];
    wire [11:0] s_len_t = s_len[12*t_slot +: 12];

    always @(posedge rxc) begin
        t_free <= 1'b0; i_ar <= 1'b0; i_er <= 1'b0;
        if (!link_ok) begin
            t_st <= T_IDLE; t_slot <= 1'b0; txctl_q <= 1'b0; txd_q <= 4'd0;
        end else case (t_st)
            T_IDLE: begin
                txctl_q <= 1'b0; txd_q <= 4'd0;
                if (pend[t_slot]) begin
                    t_kind <= s_kind[t_slot];
                    t_rl   <= s_len_t;
                    t_len  <= (s_len_t < 12'd60) ? 12'd60 : s_len_t;
                    t_cip  <= s_cip[16*t_slot +: 16];
                    t_cic  <= s_cic[16*t_slot +: 16];
                    t_i    <= 12'hFFF;
                    t_c    <= 5'd0;
                    t_st   <= T_PRE;
                end
            end
            T_PRE: begin                                   // 15 x 5, then D
                txctl_q <= 1'b1;
                txd_q   <= (t_c == 5'd15) ? 4'hD : 4'h5;
                t_c     <= t_c + 5'd1;
                if (t_c == 5'd15) begin
                    t_b <= t_nb; t_i <= t_nx; t_h <= 1'b0;
                    t_crc <= 32'hFFFF_FFFF;
                    t_st <= T_DATA;
                end
            end
            T_DATA: begin
                txctl_q <= 1'b1;
                txd_q   <= t_nib;
                t_crc   <= crc_nib(t_crc, t_nib);
                t_h     <= ~t_h;
                if (t_h) begin
                    if (t_i == t_len - 12'd1) begin
                        t_fcs  <= ~crc_nib(t_crc, t_nib);
                        t_free <= 1'b1;
                        t_c    <= 5'd0;
                        t_st   <= T_FCS;
                    end else begin
                        t_b <= t_nb; t_i <= t_nx;
                    end
                end
            end
            T_FCS: begin                                   // low nibble of byte 0 first
                txctl_q <= 1'b1;
                txd_q   <= t_fcs[3:0];
                t_fcs   <= t_fcs >> 4;
                t_c     <= t_c + 5'd1;
                if (t_c == 5'd7) begin
                    i_ar <= !t_kind; i_er <= t_kind;
                    t_c  <= 5'd0;
                    t_st <= T_IFG;
                end
            end
            default: begin                                 // T_IFG; T_IDLE adds one more
                txctl_q <= 1'b0; txd_q <= 4'd0;
                t_c <= t_c + 5'd1;
                if (t_c == IFG_NIB - 5'd2) begin
                    t_slot <= ~t_slot;
                    t_st   <= T_IDLE;
                end
            end
        endcase
    end

    // ------------------------------------------------------- RGMII transmit pins
    reg tq_p = 1'b0, tq_n = 1'b0;
    always @(posedge rxc) tq_p <= ~tq_p;
    always @(negedge rxc) tq_n <= tq_p;
    (* keep *) LUT2 #(.INIT(4'b1001)) u_txc (.O(eth_txc), .I0(tq_p), .I1(tq_n));   // ~RXC

    wire [4:0] tx_raw = {txctl_q, txd_q};
    wire [4:0] tx_pin;
    genvar gi, gj;
    generate
        for (gi = 0; gi < 5; gi = gi + 1) begin : g_txdly
            wire [TX_DLY:0] c;
            assign c[0] = tx_raw[gi];
            for (gj = 0; gj < TX_DLY; gj = gj + 1) begin : g_stage
                (* keep *) LUT1 #(.INIT(2'b10)) u_buf (.O(c[gj+1]), .I0(c[gj]));
            end
            assign tx_pin[gi] = c[TX_DLY];
        end
    endgenerate
    assign eth_txctl = tx_pin[4];
    assign eth_txd   = tx_pin[3:0];

    // ------------------------------------------------------------- counters
    // 0 rx, 1 fe, 2 ce, 3 aq, 4 ar, 5 eq, 6 er, 7 ed; Gray-coded for mclk.
    wire [7:0]   inc = {i_ed, i_er, i_eq, i_ar, i_aq, i_ce, i_fe, i_rx};
    reg  [127:0] cnt = 128'd0, cnt_g = 128'd0;
    integer q;
    always @(posedge rxc)
        for (q = 0; q < 8; q = q + 1) begin
            if (inc[q]) cnt[16*q +: 16] <= cnt[16*q +: 16] + 16'd1;
            cnt_g[16*q +: 16] <= cnt[16*q +: 16] ^ (cnt[16*q +: 16] >> 1);
        end

    // ---------------------------------------------- into mclk (2-FF, Gray)
    reg [4:0]  ib_s1 = 5'd0, ib_s2 = 5'd0, ib_s3 = 5'd0, ib_m = 5'd0;
    reg [23:0] rc_s1 = 24'd0, rc_s2 = 24'd0;
    reg [15:0] fr_s1 = 16'd0, fr_s2 = 16'd0;
    reg [127:0] cn_s1 = 128'd0, cn_s2 = 128'd0;
    reg [1:0]  lk_s = 2'd0;
    always @(posedge mclk) begin
        ib_s1 <= {ib_seen, ib_q};
        ib_s2 <= ib_s1;
        ib_s3 <= ib_s2;
        if (ib_s2 == ib_s3) ib_m <= ib_s3;      // take only a value held two cycles
        rc_s1 <= rc_gray; rc_s2 <= rc_s1;
        fr_s1 <= fr_gray; fr_s2 <= fr_s1;
        cn_s1 <= cnt_g;   cn_s2 <= cn_s1;
        lk_s  <= {lk_s[0], link_ok};
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
    localparam integer TPL_LEN = 189;
    localparam [8*TPL_LEN-1:0] TPL = {
        "E3 n=#### rt=## pm=######## id=######## g9=####>#### a4=####>#### cr=#### ",
        "sr=####/#### pc=#### ib=## rc=###### fr=#### ",
        "rx=#### fe=#### ce=#### aq=#### ar=#### eq=#### er=#### ed=#### lk=#", 8'h0D, 8'h0A};
    localparam integer NIB = 99;

    wire [23:0]  fr_now = {8'd0, gray2bin16(fr_s2)};
    wire [127:0] cn_now;
    generate
        for (gi = 0; gi < 8; gi = gi + 1) begin : g_cn
            assign cn_now[16*gi +: 16] = gray2bin16(cn_s2[16*gi +: 16]);
        end
    endgenerate
    reg  [4*NIB-1:0] snap = {4*NIB{1'b0}};
    reg  [7:0]  ci = 8'd0;
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
                             2'd0, sr_ok, ib_m[4], ib_m[3:0], rc_delta, fr_now[15:0],
                             cn_now[15:0], cn_now[31:16], cn_now[47:32], cn_now[63:48],
                             cn_now[79:64], cn_now[95:80], cn_now[111:96], cn_now[127:112],
                             3'd0, lk_s[1]};
                    ci <= 8'd0; sending <= 1'b1; txbit <= 4'd10; bcnt <= 8'd0;
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
                    ci    <= ci + 8'd1;
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
// eth3_mdio_c22 -- one clause-22 MDIO frame per `start` (E2's eth_mdio_c22,
// copied unchanged under its own name so E2 and E3 can be compiled together)
// -----------------------------------------------------------------------------
// Frame: 32 x 1 preamble, ST 01, OP (10 read / 01 write), PHYAD, REGAD, TA,
// 16 data bits: 64 MDC periods. A period starts with MDC low; the master
// changes MDIO there and MDC rises at mid-period, when the PHY samples. For a
// read the master releases MDIO from bit 46 (TA) on and samples one cycle
// before each rising edge; the PHY launched that bit after the previous rising
// edge (half a period plus earlier). ta0 = second TA bit was low: a PHY
// answered (a bus with nobody on it floats high through the pull-up).
module eth3_mdio_c22 #(
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

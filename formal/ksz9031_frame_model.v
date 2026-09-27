`default_nettype none
`timescale 1ns / 1ps

// =============================================================================
// ksz9031_frame_model -- behavioural KSZ9031RNX for step E3 (frames both ways)
// =============================================================================
// Step E2's ksz9031_status_model (MDIO register file, reset and MDC checks,
// auto-negotiation), unchanged, with its dummy frames replaced by:
//
//  - Receive: frames from a stimulus file, +STIM=<file> ($readmemh, 16-bit
//    words): 00NN one byte (low nibble first, RX_CTL high), 1nnn nnn idle
//    nibbles (RX_CTL low, in-band status on RXD), 30N one lone nibble N with
//    RX_CTL high (a frame that ends mid-byte), F000 end. Played from
//    STIM_DELAY_NS after the link comes up (or after STIM_NOLINK_NS with
//    NEVER_LINK), one nibble per RXC period; stim_done goes high at F000.
//    Data changes on the rising edge of an internal clock; RXC leaves the model
//    RXC_DLY_PS after it and RXD/RX_CTL RXD_DLY_PS after it (default 1200 / 0:
//    the KSZ9031's internal RX clock delay as the Linux micrel driver states
//    it, "RGMII_IDRX = 1.2ns"; not checked against the datasheet).
//  - Transmit: TXD/TX_CTL are taken on both TXC edges, as the PHY does. For
//    every frame (TX_CTL high) it prints one line
//      TXF t=<ns> ifg=<idle nibbles before it> nib=<n> data=<nibbles, wire order>
//    (and, for each played frame, RXE t=<ns> at the clk_i edge after its last nibble)
//    and it counts as errors:
//      TX_CTL different on the two edges of a nibble (TX_ER, or a race),
//      TXD different on the two edges while TX_CTL is high (at 100M the
//      nibble is the same on both),
//      a TXD/TX_CTL change within TSU_PS before or THO_PS after a TXC edge,
//      a TXC period other than 40 ns while TX_CTL is high,
//      TX_CTL high without a 100M full-duplex link.
//
// Checks carried over from E2, also counted in `errors`:
//  - MDC edges while the PHY is held in reset, or sooner than MIN_WAIT_NS
//    after reset release; a reset pulse shorter than MIN_RST_NS;
//  - an MDC period below MIN_MDC_NS (KSZ9031: 2.5 MHz max -> 400 ns);
//  - X on MDIO at an MDC rising edge (both ends driving, or nobody and no pull);
//  - a malformed frame (ST not 01, opcode not read/write).
// =============================================================================
module ksz9031_frame_model #(
    parameter [4:0]   ADDR           = 5'd1,
    parameter integer AN_NS          = 100000,
    parameter integer NEVER_LINK     = 0,
    parameter integer MIN_RST_NS     = 10000000,
    parameter integer MIN_WAIT_NS    = 100000,
    parameter integer MIN_MDC_NS     = 400,
    parameter integer DLY_NS         = 40,      // MDC rising edge to MDIO out
    parameter integer RXC_DLY_PS     = 1200,    // RXC after the internal clock
    parameter integer RXD_DLY_PS     = 0,       // RXD/RX_CTL after the internal clock
    parameter integer TSU_PS         = 1000,    // TXD/TX_CTL setup before a TXC edge
    parameter integer THO_PS         = 1000,    // and hold after it
    parameter integer STIM_DELAY_NS  = 2000,
    parameter integer STIM_NOLINK_NS = 3000000,
    parameter integer STIM_MAX       = 65536,
    parameter integer TXF_MAX        = 4096     // nibbles kept per TX frame
)(
    input  wire       rst_n,
    input  wire       mdc,
    inout  wire       mdio,
    output reg        rxc   = 1'b0,
    output reg        rxctl = 1'b0,
    output reg  [3:0] rxd   = 4'd0,
    input  wire       txc,
    input  wire       txctl,
    input  wire [3:0] txd,
    output reg [31:0] errors = 32'd0,
    output reg [31:0] frames_ok = 32'd0,
    output reg [31:0] tx_frames = 32'd0,
    output reg        stim_done = 1'b0
);
    reg [15:0] r0 = 16'h1140, r4 = 16'h01E1, r9 = 16'h0300, r1f = 16'h0000;
    reg        link = 1'b0, lat = 1'b0, anc = 1'b0;
    reg [1:0]  spd = 2'b00;
    reg        fdx = 1'b0;
    reg        drive = 1'b0, dval = 1'b1;
    integer    st = 0, ones = 0, n = 0;        // MDIO slave state
    assign mdio = drive ? dval : 1'bz;

    realtime t_rst_fall = 0, t_rst_rise = -1, t_mdc = -1;

    task err(input [8*48-1:0] what);
        begin
            errors = errors + 1;
            $display("MODEL ERROR at %0t: %0s", $time, what);
        end
    endtask

    // ------------------------------------------------------------- reset
    always @(rst_n) begin
        if (rst_n === 1'b0) begin
            t_rst_fall = $realtime;
            r0 = 16'h1140; r4 = 16'h01E1; r9 = 16'h0300; r1f = 16'h0000;
            link = 1'b0; lat = 1'b0; anc = 1'b0; spd = 2'b00; fdx = 1'b0;
            drive = 1'b0; st = 0; n = 0; ones = 0;
        end else if (rst_n === 1'b1) begin
            if ($realtime - t_rst_fall < MIN_RST_NS) err("PHY reset pulse too short");
            t_rst_rise = $realtime;
        end
    end

    // --------------------------------------------------------- auto-negotiation
    event an_go;
    integer an_gen = 0;
    always @(an_go) begin : an_proc
        integer my;
        my = an_gen;
        #(AN_NS);
        if (my == an_gen && rst_n === 1'b1 && !NEVER_LINK) begin
            if (r9[9:8] != 2'b00)  begin spd = 2'b10; fdx = 1'b1; r1f = 16'h0048; end
            else if (r4[8])        begin spd = 2'b01; fdx = 1'b1; r1f = 16'h0028; end
            else if (r4[7])        begin spd = 2'b01; fdx = 1'b0; r1f = 16'h0020; end
            else if (r4[6])        begin spd = 2'b00; fdx = 1'b1; r1f = 16'h0018; end
            else                   begin spd = 2'b00; fdx = 1'b0; r1f = 16'h0010; end
            link = 1'b1; anc = 1'b1;
        end
    end

    // --------------------------------------------------------------- MDIO
    reg [11:0] hdr = 12'd0;
    reg [17:0] wsh = 18'd0;
    reg [15:0] rsh = 16'd0;
    reg        me = 1'b0;
    reg [4:0]  ra = 5'd0;
    reg        b;

    function [15:0] rd_reg(input [4:0] a);
        case (a)
            5'd0:  rd_reg = r0;
            5'd1:  rd_reg = 16'h7949 | (lat ? 16'h0004 : 16'h0) | (anc ? 16'h0020 : 16'h0);
            5'd2:  rd_reg = 16'h0022;
            5'd3:  rd_reg = 16'h1622;
            5'd4:  rd_reg = r4;
            5'd9:  rd_reg = r9;
            5'd31: rd_reg = r1f;
            default: rd_reg = 16'h0000;
        endcase
    endfunction

    always @(posedge mdc) begin
        if (rst_n !== 1'b1) err("MDC edge while PHY in reset");
        else if ($realtime - t_rst_rise < MIN_WAIT_NS) err("MDIO access too soon after reset");
        if (t_mdc >= 0 && $realtime - t_mdc < MIN_MDC_NS) err("MDC period too short");
        t_mdc = $realtime;
        b = mdio;
        if (b !== 1'b0 && b !== 1'b1) err("MDIO is X at MDC rise");
        case (st)
            0: begin                                   // preamble, then ST bit 1 (0)
                if (b === 1'b1) ones = ones + 1;
                else begin
                    if (ones >= 32) st = 1; else err("ST without 32-bit preamble");
                    ones = 0;
                end
            end
            1: begin                                   // ST bit 2 (1)
                if (b === 1'b1) begin st = 2; n = 0; end
                else begin err("bad ST"); st = 0; end
            end
            2: begin                                   // OP, PHYAD, REGAD
                hdr = {hdr[10:0], b}; n = n + 1;
                if (n == 12) begin
                    me = (hdr[9:5] == ADDR) || (hdr[9:5] == 5'd0);
                    ra = hdr[4:0];
                    n = 0;
                    if (hdr[11:10] == 2'b10) begin     // read: TA z0, then data
                        st = 4;
                        if (me) begin
                            rsh = rd_reg(ra);
                            if (ra == 5'd1) lat = link; // latch-low re-arms on read
                        end
                    end else if (hdr[11:10] == 2'b01) st = 3;
                    else begin err("bad opcode"); st = 0; end
                end
            end
            3: begin                                   // write: TA 10 + 16 data
                wsh = {wsh[16:0], b}; n = n + 1;
                if (n == 18) begin
                    if (wsh[17:16] != 2'b10) err("bad write TA");
                    if (me) begin
                        case (ra)
                            5'd0: begin
                                r0 = wsh[15:0] & ~16'h8200;           // reset, restart self-clear
                                if (wsh[12] && wsh[9]) begin
                                    link = 1'b0; lat = 1'b0; anc = 1'b0; r1f = 16'h0;
                                    an_gen = an_gen + 1;
                                    -> an_go;
                                end
                            end
                            5'd4: r4 = wsh[15:0];
                            5'd9: r9 = wsh[15:0];
                            default: ;
                        endcase
                    end
                    frames_ok = frames_ok + 1;
                    st = 0; n = 0;
                end
            end
            4: begin                                   // read: rising edges of bits 46..63
                n = n + 1;                             // the master let go at the start of bit 46
                if (n == 1) begin                      // launch TA's second bit (0)
                    if (me) begin drive <= #(DLY_NS) 1'b1; dval <= #(DLY_NS) 1'b0; end
                end else if (n <= 17) begin            // launch data bit 17-n (15 first)
                    if (me) dval <= #(DLY_NS) rsh[17 - n];
                end else begin                         // after bit 63's edge: let go
                    if (me) drive <= #(DLY_NS) 1'b0;
                    frames_ok = frames_ok + 1;
                    st = 0; n = 0;
                end
            end
        endcase
    end

    // ------------------------------------------------------ RGMII receive side
    // clk_i is the PHY's own receive clock; the pins see it delayed.
    reg     clk_i = 1'b0;
    integer half_ns = 4;
    always begin
        #(half_ns) clk_i = ~clk_i;
    end
    always @* begin
        if (!link || spd == 2'b10) half_ns = 4;
        else if (spd == 2'b01)     half_ns = 20;
        else                       half_ns = 200;
    end
    always @(clk_i) rxc <= #(RXC_DLY_PS / 1000.0) clk_i;

    reg [15:0] stim [0:STIM_MAX-1];
    reg [8*256-1:0] stim_file;
    integer sp = 0, gap = 0;
    reg     playing = 1'b0, half = 1'b0;
    reg     n_dv = 1'b0, n_dv_q = 1'b0;
    reg [3:0] n_d = 4'd0;
    realtime t_link = -1;
    initial begin
        if ($value$plusargs("STIM=%s", stim_file)) $readmemh(stim_file, stim);
        else begin stim[0] = 16'hF000; end
    end
    always @(posedge link) t_link = $realtime;

    always @(posedge clk_i) begin
        if (!playing && !stim_done) begin
            if ((link && t_link >= 0 && $realtime - t_link >= STIM_DELAY_NS) ||
                (NEVER_LINK && $realtime >= STIM_NOLINK_NS))
                playing = 1'b1;
        end
        // next nibble
        n_dv = 1'b0;
        n_d  = {fdx & link, link ? spd : 2'b00, link};    // in-band status
        if (playing) begin
            if (gap > 0) gap = gap - 1;
            else if (stim[sp][15:12] == 4'h0) begin
                n_dv = 1'b1;
                n_d  = half ? stim[sp][7:4] : stim[sp][3:0];
                if (half) sp = sp + 1;
                half = ~half;
            end else if (stim[sp][15:8] == 8'h30) begin
                n_dv = 1'b1;
                n_d  = stim[sp][3:0];
                sp = sp + 1;
            end else if (stim[sp][15:12] == 4'h1) begin
                gap = stim[sp][11:0] - 1;
                sp = sp + 1;
                if (gap < 0) gap = 0;
            end else begin                          // F000 or anything else: end
                playing   = 1'b0;
                stim_done = 1'b1;
            end
        end
        if (n_dv_q && !n_dv) $display("RXE t=%0d", $rtoi($realtime));   // end of a played frame
        n_dv_q = n_dv;
        rxctl <= #(RXD_DLY_PS / 1000.0) n_dv;
        rxd   <= #(RXD_DLY_PS / 1000.0) n_d;
    end

    // ----------------------------------------------------- RGMII transmit side
    realtime t_tx_chg = -1, t_txc_edge = -1, t_txc_rise = -1;
    reg      ctl_r = 1'b0, ctl_f = 1'b0;
    reg [3:0] d_r = 4'd0, d_f = 4'd0;
    reg      have_r = 1'b0, in_frame = 1'b0;
    reg [3:0] txf [0:TXF_MAX-1];
    integer  tn = 0, idle = 0, j;
    realtime t_frame = 0;

    wire tx_on = link && spd == 2'b01 && fdx;
    always @(txctl or txd) begin
        if (tx_on && t_txc_edge >= 0 && $realtime - t_txc_edge < THO_PS / 1000.0 &&
            (in_frame || txctl === 1'b1))
            err("TXD/TX_CTL hold violated at a TXC edge");
        t_tx_chg = $realtime;
    end
    always @(posedge txc) begin
        if (tx_on && (in_frame || txctl === 1'b1)) begin
            if (t_tx_chg >= 0 && $realtime - t_tx_chg < TSU_PS / 1000.0)
                err("TXD/TX_CTL setup violated at TXC rise");
            if (txctl === 1'b1 && t_txc_rise >= 0 &&
                ($realtime - t_txc_rise < 39.5 || $realtime - t_txc_rise > 40.5))
                err("TXC period not 40 ns during a frame");
        end
        if (txctl === 1'b1 && !tx_on) err("TX_CTL high without a 100M FD link");
        if (txctl !== 1'b0 && txctl !== 1'b1 && rst_n === 1'b1 && link) err("TX_CTL is X");
        t_txc_edge = $realtime;
        t_txc_rise = $realtime;
        ctl_r  = txctl;
        d_r    = txd;
        have_r = 1'b1;
    end
    always @(negedge txc) begin
        if (tx_on && (in_frame || txctl === 1'b1) &&
            t_tx_chg >= 0 && $realtime - t_tx_chg < TSU_PS / 1000.0)
            err("TXD/TX_CTL setup violated at TXC fall");
        t_txc_edge = $realtime;
        ctl_f = txctl;
        d_f   = txd;
        if (have_r) begin
            have_r = 1'b0;
            if (ctl_r !== ctl_f && tx_on) err("TX_CTL differs on the two TXC edges");
            if (ctl_r === 1'b1 && d_r !== d_f) err("TXD differs on the two TXC edges");
            if (ctl_r === 1'b1) begin
                if (!in_frame) begin
                    in_frame = 1'b1; tn = 0; t_frame = $realtime;
                end
                if (tn < TXF_MAX) txf[tn] = d_r;
                tn = tn + 1;
            end else begin
                if (in_frame) begin
                    in_frame = 1'b0;
                    tx_frames = tx_frames + 1;
                    $write("TXF t=%0d ifg=%0d nib=%0d data=", $rtoi(t_frame), idle, tn);
                    for (j = 0; j < tn && j < TXF_MAX; j = j + 1) $write("%h", txf[j]);
                    $write("\n");
                    idle = 0;
                end
                idle = idle + 1;
            end
        end
    end
endmodule

`default_nettype wire

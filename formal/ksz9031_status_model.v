`default_nettype none
`timescale 1ns / 1ps

// =============================================================================
// ksz9031_status_model -- behavioural KSZ9031RNX, only what step E2 touches
// =============================================================================
// Not a PHY: a register file behind a clause-22 MDIO slave, plus an RGMII
// receive side that shows in-band status and a frame now and then.
//
//  - Answers at ADDR and at address 0 (the KSZ9031 treats 0 as broadcast by
//    default), so the design's address scan should find exactly bits 0 and ADDR.
//  - Reset values from the ssdm4 bring-up log: PHYID 0x0022/0x1622,
//    BMCR 0x1140, BMSR 0x796D with link; register 4 0x01E1, register 9 0x0300.
//  - BMSR bit 2 latches low (a read returns the latch, then the latch takes
//    the current link), as on the chip; bit 5 = auto-negotiation complete.
//  - Writing BMCR with bits 12 and 9 set restarts auto-negotiation: the link
//    drops, and AN_NS later it comes up at the best advertised mode
//    (1000 if register 9 bits 9:8, else 100FD/100HD/10FD/10HD from register 4).
//    Register 0x1F then reads 0x0048 / 0x0028 / 0x0020 / 0x0018 / 0x0010.
//  - RXC is 125 MHz with no link (it runs without a link on the chip too),
//    125 / 25 / 2.5 MHz with one. RX_CTL low carries in-band status
//    {duplex, speed[1:0], link}; with a link, a 72-cycle "frame" every 500 RXC.
//
// Checks, counted in `errors` (each also printed):
//  - MDC edges while the PHY is held in reset, or sooner than MIN_WAIT_NS
//    after reset release; a reset pulse shorter than MIN_RST_NS;
//  - an MDC period below MIN_MDC_NS (KSZ9031: 2.5 MHz max -> 400 ns);
//  - X on MDIO at an MDC rising edge (both ends driving, or nobody and no pull);
//  - a malformed frame (ST not 01, opcode not read/write).
// =============================================================================
module ksz9031_status_model #(
    parameter [4:0]   ADDR        = 5'd1,
    parameter integer AN_NS       = 100000,
    parameter integer NEVER_LINK  = 0,
    parameter integer MIN_RST_NS  = 10000000,
    parameter integer MIN_WAIT_NS = 100000,
    parameter integer MIN_MDC_NS  = 400,
    parameter integer DLY_NS      = 40      // MDC rising edge to MDIO out
)(
    input  wire       rst_n,
    input  wire       mdc,
    inout  wire       mdio,
    output reg        rxc   = 1'b0,
    output reg        rxctl = 1'b0,
    output reg  [3:0] rxd   = 4'd0,
    output reg [31:0] errors = 32'd0,
    output reg [31:0] frames_ok = 32'd0
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
    integer half_ns = 4;
    always begin
        #(half_ns) rxc = ~rxc;
    end
    always @* begin
        if (!link || spd == 2'b10) half_ns = 4;
        else if (spd == 2'b01)     half_ns = 20;
        else                       half_ns = 200;
    end

    integer rcnt = 0;
    always @(negedge rxc) begin
        rcnt = (rcnt == 499) ? 0 : rcnt + 1;
        if (link && rcnt < 72) begin
            rxctl <= 1'b1; rxd <= 4'h5;
        end else begin
            rxctl <= 1'b0; rxd <= {fdx & link, link ? spd : 2'b00, link};
        end
    end
endmodule

`default_nettype wire

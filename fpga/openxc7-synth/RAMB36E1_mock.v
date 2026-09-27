`timescale 1ns / 1ps

// =============================================================================
// RAMB36E1_mock -- behavioural RAMB36E1 for iverilog gate-level runs
// =============================================================================
// yosys's cells_sim.v declares RAMB36E1 with its ports, parameters and a
// specify block, but with no behaviour: the outputs float, so a netlist that
// maps a memory onto the primitive reads X from it. This mock gives it the
// behaviour of UG473 for the subset yosys's memory mapping emits for a plain
// synchronous memory:
//   RAM_MODE "TDP", DOA_REG = DOB_REG = 0, no cascade, no ECC, INIT_FILE
//   "NONE", every INIT_xx / INITP_xx / INIT_A/B / SRVAL_A/B zero, no inverted
//   pins; per port READ_WIDTH and WRITE_WIDTH each 0 (unused), 1, 2, 4, 9, 18
//   or 36; WRITE_FIRST only with equal read and write widths.
// A configuration outside the subset stops the run ($finish) rather than guess.
//
// Addressing (UG473, RAMB36 aspect ratios): ADDR[14:0] is a bit address into
// the 32 Kib data array; a port of data width w (1, 2, 4, 8, 16, 32) ignores
// the low log2(w) bits. Parity (4 Kib): byte k of the data array owns parity
// bit k. ADDR[15] matters only in cascade and is ignored here.
// Write enables: WE[0] for widths up to 9, WE[j] per byte j for 18 and 36.
// Output bits a port's width does not use read 0.
//
// Port against port: memory writes are non-blocking, so a read on the other
// port at the same edge returns the old data (the same-clock READ_FIRST case).
// Every such overlap is printed and counted in `collisions`, and if the
// writing port is not READ_FIRST the read data becomes X.
//
// Used by conformance/eth_arp_icmp_ax7203.py --gate, which drops the empty
// RAMB36E1 from a copy of cells_sim.v and compiles this one instead.
// =============================================================================
module RAMB36E1 #(
    parameter integer DOA_REG = 0,
    parameter integer DOB_REG = 0,
    parameter EN_ECC_READ = "FALSE",
    parameter EN_ECC_WRITE = "FALSE",
    parameter INIT_A = 36'h0,
    parameter INIT_B = 36'h0,
    parameter INIT_FILE = "NONE",
    parameter RAM_EXTENSION_A = "NONE",
    parameter RAM_EXTENSION_B = "NONE",
    parameter RAM_MODE = "TDP",
    parameter RDADDR_COLLISION_HWCONFIG = "DELAYED_WRITE",
    parameter integer READ_WIDTH_A = 0,
    parameter integer READ_WIDTH_B = 0,
    parameter RSTREG_PRIORITY_A = "RSTREG",
    parameter RSTREG_PRIORITY_B = "RSTREG",
    parameter SIM_COLLISION_CHECK = "ALL",
    parameter SIM_DEVICE = "VIRTEX6",
    parameter SRVAL_A = 36'h0,
    parameter SRVAL_B = 36'h0,
    parameter WRITE_MODE_A = "WRITE_FIRST",
    parameter WRITE_MODE_B = "WRITE_FIRST",
    parameter integer WRITE_WIDTH_A = 0,
    parameter integer WRITE_WIDTH_B = 0,
    parameter IS_CLKARDCLK_INVERTED = 1'b0,
    parameter IS_CLKBWRCLK_INVERTED = 1'b0,
    parameter IS_ENARDEN_INVERTED = 1'b0,
    parameter IS_ENBWREN_INVERTED = 1'b0,
    parameter IS_RSTRAMARSTRAM_INVERTED = 1'b0,
    parameter IS_RSTRAMB_INVERTED = 1'b0,
    parameter IS_RSTREGARSTREG_INVERTED = 1'b0,
    parameter IS_RSTREGB_INVERTED = 1'b0,
    parameter [255:0] INIT_00 = 256'h0, INIT_01 = 256'h0, INIT_02 = 256'h0, INIT_03 = 256'h0,
    parameter [255:0] INIT_04 = 256'h0, INIT_05 = 256'h0, INIT_06 = 256'h0, INIT_07 = 256'h0,
    parameter [255:0] INIT_08 = 256'h0, INIT_09 = 256'h0, INIT_0A = 256'h0, INIT_0B = 256'h0,
    parameter [255:0] INIT_0C = 256'h0, INIT_0D = 256'h0, INIT_0E = 256'h0, INIT_0F = 256'h0,
    parameter [255:0] INIT_10 = 256'h0, INIT_11 = 256'h0, INIT_12 = 256'h0, INIT_13 = 256'h0,
    parameter [255:0] INIT_14 = 256'h0, INIT_15 = 256'h0, INIT_16 = 256'h0, INIT_17 = 256'h0,
    parameter [255:0] INIT_18 = 256'h0, INIT_19 = 256'h0, INIT_1A = 256'h0, INIT_1B = 256'h0,
    parameter [255:0] INIT_1C = 256'h0, INIT_1D = 256'h0, INIT_1E = 256'h0, INIT_1F = 256'h0,
    parameter [255:0] INIT_20 = 256'h0, INIT_21 = 256'h0, INIT_22 = 256'h0, INIT_23 = 256'h0,
    parameter [255:0] INIT_24 = 256'h0, INIT_25 = 256'h0, INIT_26 = 256'h0, INIT_27 = 256'h0,
    parameter [255:0] INIT_28 = 256'h0, INIT_29 = 256'h0, INIT_2A = 256'h0, INIT_2B = 256'h0,
    parameter [255:0] INIT_2C = 256'h0, INIT_2D = 256'h0, INIT_2E = 256'h0, INIT_2F = 256'h0,
    parameter [255:0] INIT_30 = 256'h0, INIT_31 = 256'h0, INIT_32 = 256'h0, INIT_33 = 256'h0,
    parameter [255:0] INIT_34 = 256'h0, INIT_35 = 256'h0, INIT_36 = 256'h0, INIT_37 = 256'h0,
    parameter [255:0] INIT_38 = 256'h0, INIT_39 = 256'h0, INIT_3A = 256'h0, INIT_3B = 256'h0,
    parameter [255:0] INIT_3C = 256'h0, INIT_3D = 256'h0, INIT_3E = 256'h0, INIT_3F = 256'h0,
    parameter [255:0] INIT_40 = 256'h0, INIT_41 = 256'h0, INIT_42 = 256'h0, INIT_43 = 256'h0,
    parameter [255:0] INIT_44 = 256'h0, INIT_45 = 256'h0, INIT_46 = 256'h0, INIT_47 = 256'h0,
    parameter [255:0] INIT_48 = 256'h0, INIT_49 = 256'h0, INIT_4A = 256'h0, INIT_4B = 256'h0,
    parameter [255:0] INIT_4C = 256'h0, INIT_4D = 256'h0, INIT_4E = 256'h0, INIT_4F = 256'h0,
    parameter [255:0] INIT_50 = 256'h0, INIT_51 = 256'h0, INIT_52 = 256'h0, INIT_53 = 256'h0,
    parameter [255:0] INIT_54 = 256'h0, INIT_55 = 256'h0, INIT_56 = 256'h0, INIT_57 = 256'h0,
    parameter [255:0] INIT_58 = 256'h0, INIT_59 = 256'h0, INIT_5A = 256'h0, INIT_5B = 256'h0,
    parameter [255:0] INIT_5C = 256'h0, INIT_5D = 256'h0, INIT_5E = 256'h0, INIT_5F = 256'h0,
    parameter [255:0] INIT_60 = 256'h0, INIT_61 = 256'h0, INIT_62 = 256'h0, INIT_63 = 256'h0,
    parameter [255:0] INIT_64 = 256'h0, INIT_65 = 256'h0, INIT_66 = 256'h0, INIT_67 = 256'h0,
    parameter [255:0] INIT_68 = 256'h0, INIT_69 = 256'h0, INIT_6A = 256'h0, INIT_6B = 256'h0,
    parameter [255:0] INIT_6C = 256'h0, INIT_6D = 256'h0, INIT_6E = 256'h0, INIT_6F = 256'h0,
    parameter [255:0] INIT_70 = 256'h0, INIT_71 = 256'h0, INIT_72 = 256'h0, INIT_73 = 256'h0,
    parameter [255:0] INIT_74 = 256'h0, INIT_75 = 256'h0, INIT_76 = 256'h0, INIT_77 = 256'h0,
    parameter [255:0] INIT_78 = 256'h0, INIT_79 = 256'h0, INIT_7A = 256'h0, INIT_7B = 256'h0,
    parameter [255:0] INIT_7C = 256'h0, INIT_7D = 256'h0, INIT_7E = 256'h0, INIT_7F = 256'h0,
    parameter [255:0] INITP_00 = 256'h0, INITP_01 = 256'h0, INITP_02 = 256'h0, INITP_03 = 256'h0,
    parameter [255:0] INITP_04 = 256'h0, INITP_05 = 256'h0, INITP_06 = 256'h0, INITP_07 = 256'h0,
    parameter [255:0] INITP_08 = 256'h0, INITP_09 = 256'h0, INITP_0A = 256'h0, INITP_0B = 256'h0,
    parameter [255:0] INITP_0C = 256'h0, INITP_0D = 256'h0, INITP_0E = 256'h0, INITP_0F = 256'h0
) (
    output        CASCADEOUTA,
    output        CASCADEOUTB,
    output [31:0] DOADO,
    output [31:0] DOBDO,
    output [3:0]  DOPADOP,
    output [3:0]  DOPBDOP,
    output [7:0]  ECCPARITY,
    output [8:0]  RDADDRECC,
    output        SBITERR,
    output        DBITERR,
    input         ENARDEN,
    input         CLKARDCLK,
    input         RSTRAMARSTRAM,
    input         RSTREGARSTREG,
    input         CASCADEINA,
    input         REGCEAREGCE,
    input         ENBWREN,
    input         CLKBWRCLK,
    input         RSTRAMB,
    input         RSTREGB,
    input         CASCADEINB,
    input         REGCEB,
    input         INJECTDBITERR,
    input         INJECTSBITERR,
    input  [15:0] ADDRARDADDR,
    input  [15:0] ADDRBWRADDR,
    input  [31:0] DIADI,
    input  [31:0] DIBDI,
    input  [3:0]  DIPADIP,
    input  [3:0]  DIPBDIP,
    input  [3:0]  WEA,
    input  [7:0]  WEBWE
);
    reg        d [0:32767];                 // data array, bit addressed
    reg        p [0:4095];                  // parity array, one bit per data byte
    reg [31:0] doa = 32'd0, dob = 32'd0;
    reg [3:0]  dopa = 4'd0, dopb = 4'd0;
    assign DOADO = doa, DOPADOP = dopa, DOBDO = dob, DOPBDOP = dopb;
    assign CASCADEOUTA = 1'b0, CASCADEOUTB = 1'b0, SBITERR = 1'b0, DBITERR = 1'b0;
    assign ECCPARITY = 8'd0, RDADDRECC = 9'd0;

    function integer dbits(input integer w);   // data bits of a port width
        dbits = (w == 9) ? 8 : (w == 18) ? 16 : (w == 36) ? 32 : w;
    endfunction
    function integer pbits(input integer w);   // parity bits of a port width
        pbits = (w == 9) ? 1 : (w == 18) ? 2 : (w == 36) ? 4 : 0;
    endfunction
    function ok_w(input integer w);
        ok_w = w == 0 || w == 1 || w == 2 || w == 4 || w == 9 || w == 18 || w == 36;
    endfunction

    integer i, collisions = 0;
    initial begin
        for (i = 0; i < 32768; i = i + 1) d[i] = 1'b0;
        for (i = 0; i < 4096; i = i + 1) p[i] = 1'b0;
        if (RAM_MODE != "TDP" || DOA_REG != 0 || DOB_REG != 0
            || EN_ECC_READ != "FALSE" || EN_ECC_WRITE != "FALSE" || INIT_FILE != "NONE"
            || RAM_EXTENSION_A != "NONE" || RAM_EXTENSION_B != "NONE"
            || !ok_w(READ_WIDTH_A) || !ok_w(READ_WIDTH_B)
            || !ok_w(WRITE_WIDTH_A) || !ok_w(WRITE_WIDTH_B)
            || (WRITE_MODE_A == "WRITE_FIRST" && READ_WIDTH_A != 0 && WRITE_WIDTH_A != 0
                && READ_WIDTH_A != WRITE_WIDTH_A)
            || (WRITE_MODE_B == "WRITE_FIRST" && READ_WIDTH_B != 0 && WRITE_WIDTH_B != 0
                && READ_WIDTH_B != WRITE_WIDTH_B)
            || INIT_A != 0 || INIT_B != 0 || SRVAL_A != 0 || SRVAL_B != 0
            || IS_CLKARDCLK_INVERTED != 0 || IS_CLKBWRCLK_INVERTED != 0
            || IS_ENARDEN_INVERTED != 0 || IS_ENBWREN_INVERTED != 0
            || IS_RSTRAMARSTRAM_INVERTED != 0 || IS_RSTRAMB_INVERTED != 0
            || IS_RSTREGARSTREG_INVERTED != 0 || IS_RSTREGB_INVERTED != 0
            || |{INIT_00, INIT_01, INIT_02, INIT_03, INIT_04, INIT_05, INIT_06, INIT_07,
                 INIT_08, INIT_09, INIT_0A, INIT_0B, INIT_0C, INIT_0D, INIT_0E, INIT_0F,
                 INIT_10, INIT_11, INIT_12, INIT_13, INIT_14, INIT_15, INIT_16, INIT_17,
                 INIT_18, INIT_19, INIT_1A, INIT_1B, INIT_1C, INIT_1D, INIT_1E, INIT_1F,
                 INIT_20, INIT_21, INIT_22, INIT_23, INIT_24, INIT_25, INIT_26, INIT_27,
                 INIT_28, INIT_29, INIT_2A, INIT_2B, INIT_2C, INIT_2D, INIT_2E, INIT_2F,
                 INIT_30, INIT_31, INIT_32, INIT_33, INIT_34, INIT_35, INIT_36, INIT_37,
                 INIT_38, INIT_39, INIT_3A, INIT_3B, INIT_3C, INIT_3D, INIT_3E, INIT_3F,
                 INIT_40, INIT_41, INIT_42, INIT_43, INIT_44, INIT_45, INIT_46, INIT_47,
                 INIT_48, INIT_49, INIT_4A, INIT_4B, INIT_4C, INIT_4D, INIT_4E, INIT_4F,
                 INIT_50, INIT_51, INIT_52, INIT_53, INIT_54, INIT_55, INIT_56, INIT_57,
                 INIT_58, INIT_59, INIT_5A, INIT_5B, INIT_5C, INIT_5D, INIT_5E, INIT_5F,
                 INIT_60, INIT_61, INIT_62, INIT_63, INIT_64, INIT_65, INIT_66, INIT_67,
                 INIT_68, INIT_69, INIT_6A, INIT_6B, INIT_6C, INIT_6D, INIT_6E, INIT_6F,
                 INIT_70, INIT_71, INIT_72, INIT_73, INIT_74, INIT_75, INIT_76, INIT_77,
                 INIT_78, INIT_79, INIT_7A, INIT_7B, INIT_7C, INIT_7D, INIT_7E, INIT_7F,
                 INITP_00, INITP_01, INITP_02, INITP_03, INITP_04, INITP_05, INITP_06, INITP_07,
                 INITP_08, INITP_09, INITP_0A, INITP_0B, INITP_0C, INITP_0D, INITP_0E, INITP_0F}) begin
            $display("RAMB36E1_mock %m: configuration outside the modelled subset");
            $finish;
        end
    end

    // Last access per port, for the same-edge collision check.
    time    ra_t = ~64'd0, wa_t = ~64'd0, rb_t = ~64'd0, wb_t = ~64'd0;
    integer ra_lo, ra_hi, wa_lo, wa_hi, rb_lo, rb_hi, wb_lo, wb_hi;

    // ------------------------------------------------------------ port A
    always @(posedge CLKARDCLK) if (ENARDEN) begin : pa
        integer rb, wb, k;
        reg        wr;
        reg [31:0] q;
        reg [3:0]  qp;
        rb = ADDRARDADDR[14:0] & ~(dbits(READ_WIDTH_A) - 1);
        wb = ADDRARDADDR[14:0] & ~(dbits(WRITE_WIDTH_A) - 1);
        wr = WRITE_WIDTH_A != 0 && (WRITE_WIDTH_A <= 9 ? WEA[0] : |WEA);
        q = doa;
        qp = dopa;
        if (READ_WIDTH_A != 0 && !(wr && WRITE_MODE_A == "NO_CHANGE")) begin
            q = 32'd0;
            qp = 4'd0;
            for (k = 0; k < dbits(READ_WIDTH_A); k = k + 1) q[k] = d[rb + k];
            for (k = 0; k < pbits(READ_WIDTH_A); k = k + 1) qp[k] = p[(rb >> 3) + k];
            if (wr && WRITE_MODE_A == "WRITE_FIRST") begin
                for (k = 0; k < dbits(READ_WIDTH_A); k = k + 1)
                    if (READ_WIDTH_A <= 9 || WEA[k >> 3]) q[k] = DIADI[k];
                for (k = 0; k < pbits(READ_WIDTH_A); k = k + 1)
                    if (READ_WIDTH_A <= 9 || WEA[k]) qp[k] = DIPADIP[k];
            end
        end
        if (wr) begin
            for (k = 0; k < dbits(WRITE_WIDTH_A); k = k + 1)
                if (WRITE_WIDTH_A <= 9 || WEA[k >> 3]) d[wb + k] <= DIADI[k];
            for (k = 0; k < pbits(WRITE_WIDTH_A); k = k + 1)
                if (WRITE_WIDTH_A <= 9 || WEA[k]) p[(wb >> 3) + k] <= DIPADIP[k];
        end
        if (RSTRAMARSTRAM) begin
            q = 32'd0;
            qp = 4'd0;
        end
        if (READ_WIDTH_A != 0) begin
            ra_t = $time; ra_lo = rb; ra_hi = rb + dbits(READ_WIDTH_A) - 1;
        end
        if (wr) begin
            wa_t = $time; wa_lo = wb; wa_hi = wb + dbits(WRITE_WIDTH_A) - 1;
        end
        // port B already ran at this edge: A reads what B writes, or B read what A writes
        if (READ_WIDTH_A != 0 && wb_t == $time && ra_lo <= wb_hi && wb_lo <= ra_hi) begin
            collisions = collisions + 1;
            $display("RAMB36E1_mock %m: A reads bits %0d..%0d while B writes them, t=%0t", ra_lo, ra_hi, $time);
            if (WRITE_MODE_B != "READ_FIRST") begin q = 32'bx; qp = 4'bx; end
        end
        if (wr && rb_t == $time && rb_lo <= wa_hi && wa_lo <= rb_hi) begin
            collisions = collisions + 1;
            $display("RAMB36E1_mock %m: B reads bits %0d..%0d while A writes them, t=%0t", rb_lo, rb_hi, $time);
            if (WRITE_MODE_A != "READ_FIRST") begin dob <= 32'bx; dopb <= 4'bx; end
        end
        doa  <= q;
        dopa <= qp;
    end

    // ------------------------------------------------------------ port B
    always @(posedge CLKBWRCLK) if (ENBWREN) begin : pb
        integer rb, wb, k;
        reg        wr;
        reg [31:0] q;
        reg [3:0]  qp;
        rb = ADDRBWRADDR[14:0] & ~(dbits(READ_WIDTH_B) - 1);
        wb = ADDRBWRADDR[14:0] & ~(dbits(WRITE_WIDTH_B) - 1);
        wr = WRITE_WIDTH_B != 0 && (WRITE_WIDTH_B <= 9 ? WEBWE[0] : |WEBWE[3:0]);
        q = dob;
        qp = dopb;
        if (READ_WIDTH_B != 0 && !(wr && WRITE_MODE_B == "NO_CHANGE")) begin
            q = 32'd0;
            qp = 4'd0;
            for (k = 0; k < dbits(READ_WIDTH_B); k = k + 1) q[k] = d[rb + k];
            for (k = 0; k < pbits(READ_WIDTH_B); k = k + 1) qp[k] = p[(rb >> 3) + k];
            if (wr && WRITE_MODE_B == "WRITE_FIRST") begin
                for (k = 0; k < dbits(READ_WIDTH_B); k = k + 1)
                    if (READ_WIDTH_B <= 9 || WEBWE[k >> 3]) q[k] = DIBDI[k];
                for (k = 0; k < pbits(READ_WIDTH_B); k = k + 1)
                    if (READ_WIDTH_B <= 9 || WEBWE[k]) qp[k] = DIPBDIP[k];
            end
        end
        if (wr) begin
            for (k = 0; k < dbits(WRITE_WIDTH_B); k = k + 1)
                if (WRITE_WIDTH_B <= 9 || WEBWE[k >> 3]) d[wb + k] <= DIBDI[k];
            for (k = 0; k < pbits(WRITE_WIDTH_B); k = k + 1)
                if (WRITE_WIDTH_B <= 9 || WEBWE[k]) p[(wb >> 3) + k] <= DIPBDIP[k];
        end
        if (RSTRAMB) begin
            q = 32'd0;
            qp = 4'd0;
        end
        if (READ_WIDTH_B != 0) begin
            rb_t = $time; rb_lo = rb; rb_hi = rb + dbits(READ_WIDTH_B) - 1;
        end
        if (wr) begin
            wb_t = $time; wb_lo = wb; wb_hi = wb + dbits(WRITE_WIDTH_B) - 1;
        end
        // port A already ran at this edge
        if (READ_WIDTH_B != 0 && wa_t == $time && rb_lo <= wa_hi && wa_lo <= rb_hi) begin
            collisions = collisions + 1;
            $display("RAMB36E1_mock %m: B reads bits %0d..%0d while A writes them, t=%0t", rb_lo, rb_hi, $time);
            if (WRITE_MODE_A != "READ_FIRST") begin q = 32'bx; qp = 4'bx; end
        end
        if (wr && ra_t == $time && ra_lo <= wb_hi && wb_lo <= ra_hi) begin
            collisions = collisions + 1;
            $display("RAMB36E1_mock %m: A reads bits %0d..%0d while B writes them, t=%0t", ra_lo, ra_hi, $time);
            if (WRITE_MODE_B != "READ_FIRST") begin doa <= 32'bx; dopa <= 4'bx; end
        end
        dob  <= q;
        dopb <= qp;
    end
endmodule

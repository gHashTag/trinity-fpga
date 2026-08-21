`default_nettype none
// W840: do two IDENTICAL instances of one function agree on the die?
// LAYOUT v3, DESIGN 14.
//
// W839 measured, on three designs and two arithmetic forms, that clauses
// comparing one DUT instance against another fail on silicon while clauses
// comparing against a constant hold -- with the arithmetic excluded by proof and
// by Icarus, and timing excluded by a measured 3.7x margin (T604/T605a). The
// mechanism was not identified and this file exists to narrow it by one step.
//
// THE READING W839 PUBLISHED HAS A COMPETITOR, AND I OWE IT A TEST. Both failing
// clauses in design 12 needed `live` to hold its seeded value; both passing ones
// did not -- `c_zero` returns 0 for any `live` because the guard fires, and
// `c_gold` has no `live` at all. So "instance vs constant" and "depends on the
// counter's value" fit the same four bits. Only one thing separates them:
//
//     `smul` is exactly commutative for EVERY input (T605: the operands enter
//     only through (512+am)*(512+bm), ao+bo and sa^sb). So a wrong `live` cannot
//     make c_comm false -- both instances would be wrong in the same way.
//
// That argument rescues the instance reading for c_comm and leaves c_ind fitting
// either story. Hence the control this bench has never had:
//
//   u_self_a and u_self_b are the SAME function with the SAME operand order.
//   Nothing distinguishes them but their existence as two instances.
//
// FORECASTS REGISTERED BEFORE SYNTHESIS:
//   c_init   1   -- register INIT survives the flow. Evidence: design 12's
//                   c_zero and c_gold are sticky registers seeded 1'b1 with no
//                   path that ever sets them, and both read back 1.
//   c_self   1   -- two identical instances must agree, or the flow duplicates
//                   incorrectly, which would be a far larger finding than the
//                   one being chased.
//   c_comm   0   -- reproducing W839 on the smallest design that can carry it.
//
// WHAT EACH OUTCOME MEANS:
//   c_self=1, c_comm=0  the divergence is ORDER-DEPENDENT: swapping operands
//                       produces a netlist that is not equivalent. Next step is
//                       a netlist diff of u_comm_a against u_comm_b.
//   c_self=0            the flow miscompiles DUPLICATION itself, independent of
//                       operands. Every multi-instance verdict on this bench is
//                       void, including W838's and W832's sweeps.
//   c_self=1, c_comm=1  W839's failures were not about instances at all, and the
//                       `live`-value reading wins. c_init then says whether the
//                       counter's seed is why.
//
// c_init is a register written NOWHERE. If the openXC7 flow drops FDRE INIT
// values, it reads back zero and the whole `live`-value story gains its
// mechanism; if it reads back its seed, that story loses it. Either way the
// answer is worth one clause, and no build so far has asked.
//
// /8: six GftSmul instances. A single multiply measured Fmax 32.87/47.37 MHz
// through the stage repaired in T603, against 8.85 MHz declared -- so the margin
// here is known rather than assumed, for the first time on this bench.
//
// WORD v3: {16'hA5A5, 4'd3, 6'd14, c_init, c_self, c_comm, c_ind, beat, ok}
module gft_dup_folded_jtag #(parameter integer JTAG_CHAIN_N = 3);

    wire cfgmclk;
    STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(10.0)) startup (
        .CFGCLK(), .CFGMCLK(cfgmclk), .EOS(), .PREQ(),
        .CLK(1'b0), .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b0),
        .PACK(1'b0), .USRCCLKO(1'b0), .USRCCLKTS(1'b0),
        .USRDONEO(1'b1), .USRDONETS(1'b1));

    reg [2:0] dv = 3'd0;
    always @(posedge cfgmclk) dv <= dv + 3'd1;
    wire slowclk;
    BUFG bufg_slow (.I(dv[2]), .O(slowclk));

    reg [3:0] rstc = 4'd0;
    wire rst_n = (rstc == 4'hF);
    always @(posedge slowclk) if (rstc != 4'hF) rstc <= rstc + 4'd1;

    localparam [31:0] TWO = 32'd20992;   // 2.0

    // ---- the INIT probe: seeded, and written by nothing ----
    // 0x5A5A1234 is not the shift register's magic and not any TNF constant, so
    // a match cannot come from a neighbouring net being read by mistake.
    reg [31:0] initprobe = 32'h5A5A1234;

    reg [23:0] pre  = 24'd0;
    reg        beat = 1'b0;
    reg [31:0] live = 32'd20480;
    always @(posedge slowclk) begin
        pre <= pre + 24'd1;
        if (pre == 24'd0) begin
            beat <= ~beat;
            live <= live + 32'd1;
        end
    end

    wire y1, y2, y3, y4, y5;
    wire [31:0] r_self_a, r_self_b, r_comm_a, r_comm_b, r_ind;

    // ---- THE CONTROL: identical function, identical operand order ----
    GftSmul u_self_a (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(live), .b(TWO), .ready(y1), .result(r_self_a));
    GftSmul u_self_b (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(live), .b(TWO), .ready(y2), .result(r_self_b));

    // ---- THE TEST: identical function, operands swapped ----
    GftSmul u_comm_a (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(live), .b(TWO), .ready(y3), .result(r_comm_a));
    GftSmul u_comm_b (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(TWO), .b(live), .ready(y4), .result(r_comm_b));

    // ---- liveness, so nothing above can be a folded constant (T534) ----
    GftSmul u_ind (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(live), .b(live), .ready(y5), .result(r_ind));

    wire init_ok = (initprobe == 32'h5A5A1234);
    wire self_ok = (r_self_a == r_self_b);
    wire comm_ok = (r_comm_a == r_comm_b);
    wire ind_ok  = (r_ind != 32'd0);

    reg sig = 1'b0;
    reg c_init = 1'b1, c_self = 1'b1, c_comm = 1'b1, c_ind = 1'b1;
    reg [4:0] settle = 5'd0;
    always @(posedge slowclk) begin
        if (rst_n && settle != 5'h1F) settle <= settle + 5'd1;
        if (settle == 5'h1F) begin
            if (!init_ok) c_init <= 1'b0;
            if (!self_ok) c_self <= 1'b0;
            if (!comm_ok) c_comm <= 1'b0;
            if (!ind_ok)  c_ind  <= 1'b0;
            sig <= c_init & c_self & c_comm & c_ind
                 & init_ok & self_ok & comm_ok & ind_ok;
        end
    end
    wire ok = sig;

    wire drck, sel, shift, capture, tdi;
    wire tdo;
    BSCANE2 #(.JTAG_CHAIN(JTAG_CHAIN_N)) bscan (
        .CAPTURE(capture), .DRCK(drck), .RESET(), .RUNTEST(), .SEL(sel),
        .SHIFT(shift), .TCK(), .TDI(tdi), .TMS(), .UPDATE(), .TDO(tdo));
    reg [31:0] sr = 32'hA5A533BC;
    always @(posedge drck)
        if (sel) begin
            if (capture) sr <= {16'hA5A5, 4'd3, 6'd14,
                                c_init, c_self, c_comm, c_ind,
                                beat, ok};
            else if (shift) sr <= {tdi, sr[31:1]};
        end
    assign tdo = sr[0];
endmodule
`default_nettype wire

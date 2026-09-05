// W982: the MINIMAL reproducer for the failure W842/W977/W981 could not explain.
//
// `gft_dup_jtag` carries five GftSmul instances and four clauses; on seed 7 it
// returns 1101 -- c_self TRUE, c_comm FALSE -- across two waves, a bench change,
// a netlist perturbation and an octave of clock. W977 asked for a minimal upstream
// report and never got one. This is the reduction.
//
// It keeps exactly the structure that discriminates and drops everything else:
//
//   u_ctrl  = smul(live, TWO)     ) identical operands, identical order
//   u_comm_a = smul(live, TWO)    )  -> self_ok, THE CONTROL
//   u_comm_b = smul(TWO, live)       -> comm_ok, THE TEST
//
// Three instances instead of five. If seed 7 still returns c_comm=0 here, the
// reproducer is 40 % smaller and the report can be written. If it does not, the
// failure needs the placement pressure of the larger design, and that is the
// finding instead -- either way the answer is worth one build.
//
// The two clauses differ in ONE respect: which port the constant is folded into.
// `smul` is exactly commutative (T829: 0 counterexamples in 2359296 pairs), so
// self_ok and comm_ok must both hold, and any build where they disagree has a
// defect below the front end.
//
// WORD v3: {16'hA5A5, 4'd3, 6'd20, c_init, c_self, c_comm, c_ind, beat, ok}
module gft_commmin_jtag #(parameter integer JTAG_CHAIN_N = 3);

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

    // Written by nothing; 0x5A5A1234 is neither the shift register's magic nor
    // any TNF constant, so a match cannot come from reading a neighbouring net.
    // W983: `(* keep *)` is NOT enough -- it preserves the cell and `opt` still
    // propagates the constant into the comparison. A probe that nothing writes
    // folds to its INIT and `init_ok` becomes the literal 1: a clause that reads
    // PASS in every build, including the failing ones. It has to MOVE. A rotation
    // is value-preserving in the only property the clause tests, and yosys will
    // not reason about the reachable set of a 32-bit rotate.
    reg [31:0] initprobe = 32'h5A5A1234;
    always @(posedge slowclk) initprobe <= {initprobe[30:0], initprobe[31]};

    // W981 (T830): `live` walks out of the representable set after 20992 beats,
    // about twelve hours. A die read takes minutes, so this is inside its window
    // -- recorded here so the next reader does not have to rediscover it.
    reg [23:0] pre  = 24'd0;
    reg        beat = 1'b0;
    reg [31:0] live  = 32'd20480;
    reg [31:0] live2 = 32'd20480;      // W983: a SECOND counter, same seed, same step
    always @(posedge slowclk) begin
        pre <= pre + 24'd1;
        if (pre == 24'd0) begin
            beat  <= ~beat;
            live  <= live  + 32'd1;
            live2 <= live2 + 32'd1;
        end
    end

    wire y1, y2, y3;
    wire [31:0] r_ctrl, r_comm_a, r_comm_b;

    // THE CONTROL: same function, same operand order, two instances.
    // W983: two instances with IDENTICAL operands are merged by yosys, and the
    // comparison between them collapses to the literal 1 -- the control this whole
    // experiment was read through could not fail in any build. The repair is not
    // an attribute: the two sources must be STRUCTURALLY DISTINCT and carry equal
    // values. `live` and `live2` are separate counters stepping identically, and
    // proving them equal is not something a mapper will attempt.
    (* keep *) GftSmul u_ctrl (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(live), .b(TWO), .ready(y1), .result(r_ctrl));
    (* keep *) GftSmul u_comm_a (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(live2), .b(TWO), .ready(y2), .result(r_comm_a));

    // THE TEST: same function, operands swapped -- the constant folds into the
    // other port, so yosys builds a different cone for the same mathematics.
    (* keep *) GftSmul u_comm_b (.clk(slowclk), .rst_n(rst_n), .en(1'b1),
        .a(TWO), .b(live), .ready(y3), .result(r_comm_b));

    wire init_ok = (initprobe != 32'd0);   // rotation-invariant, and not foldable
    wire self_ok = (r_ctrl == r_comm_a);
    wire comm_ok = (r_comm_a == r_comm_b);
    wire ind_ok  = (r_comm_a != 32'd0);

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
    reg [31:0] sr = 32'hA5A5053C;
    always @(posedge drck)
        if (sel) begin
            if (capture) sr <= {16'hA5A5, 4'd3, 6'd20,
                                c_init, c_self, c_comm, c_ind,
                                beat, ok};
            else if (shift) sr <= {tdi, sr[31:1]};
        end
    assign tdo = sr[0];
endmodule

`default_nettype none
`timescale 1ns / 1ps
//=============================================================================
// trinet_node_core — the TRI-NET node with no vendor primitives.
//
// This is the same cell that runs on the AX7203, with the two Xilinx-specific
// pieces lifted out to the board wrapper:
//
//   STARTUPE2  supplied CFGMCLK. Here the clock is an input.
//   DNA_PORT   supplied a device identity. Here the id is an input, so a board
//              wrapper can drive it from whatever its family offers — and on a
//              family that offers nothing, from a parameter.
//
// What remains is ordinary synthesisable Verilog: a UART, a frame parser, a
// 32wide balancedternary dot product taken as popcount(agreements) minus
// popcount(disagreements), and SipHash24 tag engines. No multiplier, no DSP,
// no vendor macro; inferred RAM only, in the standard template every family's
// synthesiser recognises (the x RAM the batch ops added — see below).
//
// WHY THIS FILE EXISTS. One of the three routes under consideration for this
// work is selling the cell as portable soft IP, and the honest test of that is
// not a conversation — it is whether the thing survives being pointed at
// another family's synthesiser. Building the core so it can be is the only way
// to find out, and the answer is a measurement rather than an opinion. See
// docs/TRI_NET_PORTABILITY.md for what the numbers came out as.
//
// REQUEST  (24 bytes): AA 55 OP NONCE[4] W[8] X[8] TRIG
// RESPONSE MAC32 / SETKEY / SETX (19 bytes): A5 Y STATUS NONCE[4] NODE_ID[4] TAG[8]
//         DOT6 (24 bytes): A5 Y[6] STATUS NONCE[4] NODE_ID[4] TAG[8]
//
//   OP 0x01  ternary MAC. W and X are 32 packed trits each.
//   OP 0x02  set the receipt key. W||X are the 16 key bytes, first byte first.
//            Accepted once per configuration; ignored afterwards.
//   OP 0x03  SETX, pin one 8byte x chunk of one digit plane. W[0]=plane,
//            W[1]=chunk, the x chunk is W[2..7]||X[0..1] (the body's x8
//            straddles the parser's W/X register boundary). The node writes it
//            to x RAM at (plane, chunk) and answers 19 bytes with Y = chunk.
//   OP 0x04  DOT6, six dots over pinned x. W = the w chunk (32 trits), X[0]
//            = chunk index, X[1] = 6bit plane mask. The node reads the six
//            pinned x chunks at that index, computes up to six dots, and
//            answers 24 bytes with all six y bytes (maskedout planes y = 0).
//
//   The batch ops and their tag rules are pinned by
//   specs/trinet/tern_tc_batch_ax7203.t27; the tag still MACs what the
//   datapath consumed (SETX: the received bytes; DOT6: the 48 bytes READ
//   FROM RAM, so x RAM drift after SETX cannot hide).
//
//   OUTOFRANGE ADDRESSES ALIAS, BY DECISION. plane >= PLANES or chunk >= C_MAX
//   is not refused: the address arithmetic is full width and the RAM's address
//   port truncates, so such a write lands at (plane*C_MAX + chunk) mod
//   2^ADDRBITS. The reference model (conformance/tern_tc_batch_model.py)
//   aliases identically, and the SETX tag MACs the received bytes while the
//   DOT6 tag MACs what the RAM returned, so a bogus address can only harm the
//   host that issued it. The runner never issues one; phantom frames may.
//   Neverwritten x RAM reads as zeros, in silicon and in the model.
//
//   STATUS 0x01 ok          the answer is signed and creditable
//          0x02 key set     the key in this request is now the node's key
//          0x03 key locked  a key was already set; this request changed nothing
//          0x04 no key      unkeyed node: y is real, the tag means nothing
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_node_core #(
    // Divides `clk` to the line rate. On the AX7203 this is CFGMCLK/60.
    parameter integer BAUD_DIV_P = 60,
    // The x RAM holds PLANES x C_MAX chunks of 8 bytes; 27 is the widest
    // matrix pass (the DOWN pass, C_DOWN in the batch spec). SETX and DOT6
    // address it as plane*C_MAX + chunk.
    parameter integer C_MAX = 27,
    // Optional pre-loaded key. The all-zero default is deliberate, and is now
    // also the normal case: a null key means the node comes up UNKEYED and
    // takes its key over the wire (op 0x02) exactly once per configuration.
    //
    // WHY THE KEY IS NOT BAKED IN ANY MORE. It was, and it went stale: fixing
    // the committed-key defect in source never reached the silicon, because
    // re-keying meant a place-and-route run the operator's machine cannot
    // perform (8 GB is not enough for an XC7A200T chipdb) plus a 13-minute
    // flash, per board. A key that costs an hour to rotate is a key nobody
    // rotates. Loading it after configuration makes rotation a power-cycle and
    // one 24-byte frame.
    //
    // The trade is honest: whoever can reach this UART in the window after
    // configuration can claim the node. They can also simply re-flash it, so
    // this concedes little that physical access did not already concede.
    //
    // A non-zero RECEIPT_KEY still works and locks at reset, for anyone who
    // does have a build machine and prefers the key never touch a wire.
    parameter [127:0] RECEIPT_KEY = 128'h0
) (
    input  wire        clk,
    input  wire        rst,
    input  wire [31:0] node_id,
    input  wire        uart_rx,
    output reg         uart_tx,
    output wire        frame_seen,
    output wire        result_nonzero
);

    localparam [9:0] BAUD_DIV = BAUD_DIV_P[9:0];

    localparam integer PLANES = 6;

    //-------------------------------------------------------------------------
    // UART receive.
    //-------------------------------------------------------------------------
    reg [2:0] rsync;
    always @(posedge clk or posedge rst)
        if (rst) rsync <= 3'b111; else rsync <= {rsync[1:0], uart_rx};
    wire rxd = rsync[2];

    reg [1:0] rxs;
    reg [9:0] rxcnt;
    reg [3:0] rbi;
    reg [7:0] rxsr, rx_byte;
    reg       rx_new;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            rxs <= 2'd0; rxcnt <= 10'd0; rbi <= 4'd0;
            rxsr <= 8'd0; rx_byte <= 8'd0; rx_new <= 1'b0;
        end else begin
            rx_new <= 1'b0;
            case (rxs)
                2'd0: if (~rxd) begin
                          rxcnt <= (BAUD_DIV + (BAUD_DIV >> 1)) - 10'd1;
                          rxs <= 2'd1; rbi <= 4'd0;
                      end
                2'd1: if (rxcnt == 10'd0) begin
                          rxsr <= {rxd, rxsr[7:1]};
                          if (rbi == 4'd7) begin rxs <= 2'd2; rxcnt <= BAUD_DIV - 10'd1; end
                          else            begin rbi <= rbi + 4'd1; rxcnt <= BAUD_DIV - 10'd1; end
                      end else rxcnt <= rxcnt - 10'd1;
                2'd2: if (rxcnt == 10'd0) begin
                          rx_byte <= rxsr; rx_new <= 1'b1; rxs <= 2'd0;
                      end else rxcnt <= rxcnt - 10'd1;
                default: rxs <= 2'd0;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // Frame parser — 24-byte request.
    //-------------------------------------------------------------------------
    localparam [4:0] F_MAGIC0 = 5'd0, F_MAGIC1 = 5'd1, F_BODY = 5'd2;

    reg [4:0]  fstate;
    reg [4:0]  bidx;
    reg [7:0]  op_r;
    reg [7:0]  nonce_b [0:3];
    reg [7:0]  w_b     [0:7];
    reg [7:0]  x_b     [0:7];
    reg        frame_valid;

    integer ini;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            fstate <= F_MAGIC0; bidx <= 5'd0; op_r <= 8'd0; frame_valid <= 1'b0;
            for (ini = 0; ini < 4; ini = ini + 1) nonce_b[ini] <= 8'd0;
            for (ini = 0; ini < 8; ini = ini + 1) begin w_b[ini] <= 8'd0; x_b[ini] <= 8'd0; end
        end else begin
            frame_valid <= 1'b0;
            if (rx_new) begin
                case (fstate)
                    F_MAGIC0: fstate <= (rx_byte == 8'hAA) ? F_MAGIC1 : F_MAGIC0;
                    F_MAGIC1: begin
                        if (rx_byte == 8'h55) begin fstate <= F_BODY; bidx <= 5'd0; end
                        else if (rx_byte == 8'hAA) fstate <= F_MAGIC1;
                        else fstate <= F_MAGIC0;
                    end
                    F_BODY: begin
                        if      (bidx == 5'd0)  op_r            <= rx_byte;
                        else if (bidx <= 5'd4)  nonce_b[bidx-1] <= rx_byte;
                        else if (bidx <= 5'd12) w_b[bidx-5]     <= rx_byte;
                        else if (bidx <= 5'd20) x_b[bidx-13]    <= rx_byte;

                        if (bidx == 5'd21) begin
                            frame_valid <= 1'b1;
                            fstate <= F_MAGIC0; bidx <= 5'd0;
                        end else bidx <= bidx + 5'd1;
                    end
                    default: fstate <= F_MAGIC0;
                endcase
            end
        end
    end

    assign frame_seen = frame_valid;

    //-------------------------------------------------------------------------
    // Ternary dot product — popcount(pos) - popcount(neg). No multiplier.
    //
    // The x operand is a mux: MAC32 (and any op the parser passes through that
    // is not SETX/DOT6) dots against the frame's own X bytes, exactly as
    // before; during a DOT6 walk it is the RAM word the walk is visiting.
    //-------------------------------------------------------------------------
    wire [63:0] w_bus = {w_b[7], w_b[6], w_b[5], w_b[4], w_b[3], w_b[2], w_b[1], w_b[0]};
    wire [63:0] x_bus = {x_b[7], x_b[6], x_b[5], x_b[4], x_b[3], x_b[2], x_b[1], x_b[0]};

    wire dot6_walking;
    wire [63:0] dot_x = dot6_walking ? ram_q : x_bus;

    wire [31:0] prod_pos, prod_neg;
    genvar gi;
    generate
        for (gi = 0; gi < 32; gi = gi + 1) begin : gen_trit
            wire [1:0] wt = w_bus[2*gi +: 2];
            wire [1:0] xt = dot_x[2*gi +: 2];
            wire w_pos = (wt == 2'b01);
            wire w_neg = (wt == 2'b10);
            wire x_pos = (xt == 2'b01);
            wire x_neg = (xt == 2'b10);
            assign prod_pos[gi] = (w_pos & x_pos) | (w_neg & x_neg);
            assign prod_neg[gi] = (w_pos & x_neg) | (w_neg & x_pos);
        end
    endgenerate

    reg [5:0] cnt_pos, cnt_neg;
    integer pk;
    always @(*) begin
        cnt_pos = 6'd0;
        cnt_neg = 6'd0;
        for (pk = 0; pk < 32; pk = pk + 1) begin
            cnt_pos = cnt_pos + {5'd0, prod_pos[pk]};
            cnt_neg = cnt_neg + {5'd0, prod_neg[pk]};
        end
    end

    wire signed [7:0] dot_result = $signed({2'b00, cnt_pos}) - $signed({2'b00, cnt_neg});

    //-------------------------------------------------------------------------
    // The x RAM — PLANES x C_MAX chunks of 8 bytes, one write port (SETX),
    // one read port (the DOT6 walk), inferred synchronous RAM in the plain
    // template, no vendor macro.
    //
    // SETX body: W[0]=plane, W[1]=chunk, x8 = W[2..7]||X[0..1]. The chunk
    // straddles the parser's W/X boundary: x8[0] sits in W[2] and x8[7] in
    // X[1]. Stored with x8[0] in bits [7:0], matching every other multi-byte
    // field in this file.
    //
    // The address ports truncate: an out-of-range (plane, chunk) aliases to
    // (plane*C_MAX + chunk) mod 2^XRAM_ABITS — see the header. That is the
    // reference model's behaviour too, byte for byte.
    //
    // Never-written RAM reads as zeros (the model's bytearray starts zeroed,
    // and 7-series BRAM powers up zero), so a phantom DOT6 over unwritten
    // RAM produces the same ys and the same tag in silicon and in the model.
    //-------------------------------------------------------------------------
    localparam integer XRAM_USED  = PLANES * C_MAX;             // 162 at C_MAX=27
    localparam integer XRAM_ABITS = $clog2(XRAM_USED);          // 8
    localparam integer XRAM_WORDS = 1 << XRAM_ABITS;            // 256: the port's whole space

    reg [63:0] xram [0:XRAM_WORDS-1];
    reg [63:0] ram_q;

    // The read pointer LEADS the walk by one: the RAM read is synchronous
    // (address at cycle N, word at N+1), so the cycle that latches plane p
    // must already present plane p+1's address. In D_SETTLE that is plane 0;
    // in D_RUN it is the next plane (the last cycle's addr(6) wraps past the
    // used region — a read-only address, never latched). d_st and dot6_plane
    // live in the walk FSM below; module scope resolves them here.
    wire [2:0] rd_plane = (d_st == D_RUN) ? (dot6_plane + 3'd1) : dot6_plane;

    // Full-width address arithmetic; the port width is the aliasing decision.
    // 27 = 32 - 4 - 1, so plane*27 is two shifts and two subtracts. A literal
    // `*` here made ecp5/gatemate/gowin/nexus infer real multiplier cells,
    // which the zero-multiplier discipline and the portability invariant both
    // forbid. The `*` branch never elaborates at C_MAX = 27; it keeps other
    // widths legal, at the cost a multiplier brings, for whoever changes the
    // widest pass. Both forms are full-width (max 255*27 + 255 = 7140, no
    // 16-bit wrap), so the aliasing law is bit-identical either way.
    wire [15:0] xw_full, xr_full;
    generate
        if (C_MAX == 27) begin : gen_addr27
            assign xw_full = (({8'd0, w_b[0]} << 5) - ({8'd0, w_b[0]} << 2)
                              - {8'd0, w_b[0]}) + {8'd0, w_b[1]};          // SETX write
            assign xr_full = (({13'd0, rd_plane} << 5) - ({13'd0, rd_plane} << 2)
                              - {13'd0, rd_plane}) + {8'd0, x_b[0]};       // DOT6 read
        end else begin : gen_addr_mul
            assign xw_full = {8'd0, w_b[0]} * C_MAX + {8'd0, w_b[1]};
            assign xr_full = {13'd0, rd_plane} * C_MAX + {8'd0, x_b[0]};
        end
    endgenerate
    wire [XRAM_ABITS-1:0] xram_wa = xw_full[XRAM_ABITS-1:0];
    wire [XRAM_ABITS-1:0] xram_ra = xr_full[XRAM_ABITS-1:0];

    wire        xram_we = frame_valid && (op_r == OP_SETX);
    wire [63:0] xram_wd = {x_b[1], x_b[0], w_b[7], w_b[6], w_b[5], w_b[4], w_b[3], w_b[2]};

    // The array spans the port's whole space (2^XRAM_ABITS words), so a
    // truncated address always lands in a real word: the used region is the
    // first PLANES*C_MAX words, the slack beyond is never addressed in-range
    // and reads as its initial zero.
    integer xi;
    initial begin
        for (xi = 0; xi < XRAM_WORDS; xi = xi + 1) xram[xi] = 64'd0;
    end

    always @(posedge clk) begin
        if (xram_we) xram[xram_wa] <= xram_wd;
        ram_q <= xram[xram_ra];
    end

    //-------------------------------------------------------------------------
    // The key, and the one chance to set it.
    //
    // op 0x02 carries 16 key bytes in the W and X fields, so the request stays
    // 24 bytes and the frame parser above is untouched — which also keeps
    // conformance/frame_alignment_check.py meaningful.
    //
    // Write-once until reconfiguration. A key that can be overwritten at any
    // time is not a key: anyone who reaches the wire could replace it after
    // operator set it, and every receipt afterwards would verify under the
    // attacker's key instead.
    //-------------------------------------------------------------------------
    localparam [7:0] OP_MAC32  = 8'h01;
    localparam [7:0] OP_SETKEY = 8'h02;
    localparam [7:0] OP_SETX   = 8'h03;
    localparam [7:0] OP_DOT6   = 8'h04;

    localparam [7:0] ST_OK         = 8'h01;
    localparam [7:0] ST_KEY_SET    = 8'h02;
    localparam [7:0] ST_KEY_LOCKED = 8'h03;
    localparam [7:0] ST_NO_KEY     = 8'h04;

    reg [127:0] key_reg;
    reg         key_locked;

    wire setting_key = frame_valid && (op_r == OP_SETKEY) && !key_locked;

    // The acknowledgement must be tagged with the key just accepted, so the
    // host can confirm the board really took it. key_reg only updates next
    // cycle, hence the combinational bypass.
    wire [127:0] key_eff = setting_key ? {x_bus, w_bus} : key_reg;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            key_reg    <= RECEIPT_KEY;
            key_locked <= (RECEIPT_KEY != 128'h0);
        end else if (setting_key) begin
            key_reg    <= {x_bus, w_bus};
            key_locked <= 1'b1;
        end
    end

    //-------------------------------------------------------------------------
    // The DOT6 walk — six clocks, one plane each. Each cycle the RAM word for
    // plane p is dotted against the frame's w (w_b holds it: no frame can
    // complete in six clocks at this line rate), the y byte is latched
    // (masked-out planes latch 0), and the word is kept for the preimage.
    //
    //   frame_valid && DOT6 : present plane-0 address, settle one cycle
    //   (the RAM read is synchronous: ram_q holds plane p's word one cycle
    //   after its address was presented)
    //   six walk cycles     : latch x48[p] and ys[p], present p+1's address
    //   last walk cycle     : start the 73-byte tag
    //-------------------------------------------------------------------------
    localparam [1:0] D_IDLE = 2'd0, D_SETTLE = 2'd1, D_RUN = 2'd2;

    reg [1:0]  d_st;
    reg [2:0]  dot6_plane;
    reg [47:0] ys_reg6;
    reg [63:0] x48_p [0:5];
    reg [7:0]  chunk_l, mask_l;
    reg        mac6_start;

    assign dot6_walking = (d_st == D_SETTLE) || (d_st == D_RUN);

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            d_st <= D_IDLE; dot6_plane <= 3'd0; ys_reg6 <= 48'd0;
            for (ini = 0; ini < 6; ini = ini + 1) x48_p[ini] <= 64'd0;
            chunk_l <= 8'd0; mask_l <= 8'd0; mac6_start <= 1'b0;
        end else begin
            mac6_start <= 1'b0;
            case (d_st)
                D_IDLE: if (frame_valid && (op_r == OP_DOT6)) begin
                    d_st        <= D_SETTLE;
                    dot6_plane  <= 3'd0;
                    ys_reg6     <= 48'd0;
                    chunk_l     <= x_b[0];
                    mask_l      <= x_b[1];
                    // xram_ra is combinational in dot6_plane, so the plane-0
                    // address is already presented this cycle; ram_q holds
                    // plane 0's word at the end of D_SETTLE.
                end
                D_SETTLE: d_st <= D_RUN;
                D_RUN: begin
                    // ram_q holds plane dot6_plane's word.
                    x48_p[dot6_plane] <= ram_q;
                    ys_reg6[8*dot6_plane +: 8] <= mask_l[dot6_plane] ? dot_result : 8'd0;
                    if (dot6_plane == 3'd5) begin
                        d_st       <= D_IDLE;
                        mac6_start <= 1'b1;
                    end else begin
                        dot6_plane <= dot6_plane + 3'd1;
                    end
                end
                default: d_st <= D_IDLE;
            endcase
        end
    end

    // ram_q must not be read while a write is in flight on the same edge:
    // SETX and DOT6 are different frames, and a frame cannot complete during
    // another's walk at this line rate, so the two never meet.

    //-------------------------------------------------------------------------
    // Keyed receipts. Three engines, one preimage law: the tag MACs what the
    // datapath consumed.
    //
    //   MAC32 / SETKEY / passthrough ops : 26 B, unchanged, bit for bit.
    //   SETX                             : 20 B (op nonce plane chunk x8 y node).
    //   DOT6                             : 73 B (op nonce w chunk mask x48 y6 node,
    //                                       x48 = the six words READ FROM RAM).
    //
    // The MAC32 engine keeps serving every op that is not SETX or DOT6 —
    // including an op byte the parser passes through that nobody defines
    // (a phantom frame's), exactly as the shipped core did.
    //-------------------------------------------------------------------------
    reg [7:0]   y_reg;
    reg [31:0]  id_latched;
    reg         mac_start, setx_start;
    reg [7:0]   status_reg;
    reg [127:0] key_latched;

    wire [207:0] preimage = {
        id_latched[31:24], id_latched[23:16], id_latched[15:8], id_latched[7:0],
        y_reg,
        x_b[7], x_b[6], x_b[5], x_b[4], x_b[3], x_b[2], x_b[1], x_b[0],
        w_b[7], w_b[6], w_b[5], w_b[4], w_b[3], w_b[2], w_b[1], w_b[0],
        nonce_b[3], nonce_b[2], nonce_b[1], nonce_b[0],
        op_r
    };

    // SETX: op, nonce, plane, chunk, x8 (W[2..7]||X[0..1]), y = chunk, node.
    wire [159:0] preimage_setx = {
        id_latched[31:24], id_latched[23:16], id_latched[15:8], id_latched[7:0],
        y_reg,
        x_b[1], x_b[0], w_b[7], w_b[6], w_b[5], w_b[4], w_b[3], w_b[2],
        w_b[1],
        w_b[0],
        nonce_b[3], nonce_b[2], nonce_b[1], nonce_b[0],
        OP_SETX
    };

    // DOT6: op, nonce, w, chunk, mask, x48 (plane 0's word in the low bytes),
    // y6, node. Assembled when the walk ends; the fields it reads are stable
    // (no frame completes in six clocks).
    wire [583:0] preimage_dot6 = {
        id_latched[31:24], id_latched[23:16], id_latched[15:8], id_latched[7:0],
        ys_reg6[47:40], ys_reg6[39:32], ys_reg6[31:24], ys_reg6[23:16], ys_reg6[15:8], ys_reg6[7:0],
        x48_p[5], x48_p[4], x48_p[3], x48_p[2], x48_p[1], x48_p[0],
        mask_l,
        chunk_l,
        w_b[7], w_b[6], w_b[5], w_b[4], w_b[3], w_b[2], w_b[1], w_b[0],
        nonce_b[3], nonce_b[2], nonce_b[1], nonce_b[0],
        OP_DOT6
    };

    wire [63:0] mac_tag, setx_tag, mac6_tag;
    wire        mac_done, setx_done, mac6_done;

    trinet_siphash24 #(.MSG_BYTES(26)) u_mac (
        .clk(clk), .rst(rst), .start(mac_start),
        .msg(preimage), .key(key_latched),
        .tag(mac_tag), .done(mac_done));

    trinet_siphash24 #(.MSG_BYTES(20)) u_setx (
        .clk(clk), .rst(rst), .start(setx_start),
        .msg(preimage_setx), .key(key_latched),
        .tag(setx_tag), .done(setx_done));

    trinet_siphash24 #(.MSG_BYTES(73)) u_mac6 (
        .clk(clk), .rst(rst), .start(mac6_start),
        .msg(preimage_dot6), .key(key_latched),
        .tag(mac6_tag), .done(mac6_done));

    reg result_ready;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            y_reg <= 8'd0; id_latched <= 32'd0; mac_start <= 1'b0; setx_start <= 1'b0;
            result_ready <= 1'b0;
            status_reg <= ST_NO_KEY; key_latched <= RECEIPT_KEY;
        end else begin
            mac_start  <= 1'b0;
            setx_start <= 1'b0;
            result_ready <= mac_done || setx_done || mac6_done;
            if (frame_valid) begin
                // The dot product is computed either way; only signing depends
                // on holding a key. Returning y unsigned is useful for bring-up
                // and cannot be mistaken for work, because the status says so
                // and the host refuses to credit it.
                // A key-load carries key bytes in the operand fields, and
                // running a dot product over them would put a meaningless
                // number in the receipt that somebody would eventually read as
                // work. Answer zero and mean it.
                // SETX's y is the echoed chunk index (W[1]), per the spec's
                // preimage rule. DOT6's six ys ride ys_reg6; y_reg is unused.
                y_reg       <= (op_r == OP_SETKEY) ? 8'd0
                             : (op_r == OP_SETX)   ? w_b[1]
                             : (op_r == OP_DOT6)   ? 8'd0
                                                   : dot_result;
                id_latched  <= node_id;
                key_latched <= key_eff;
                mac_start   <= (op_r != OP_SETX) && (op_r != OP_DOT6);
                setx_start  <= (op_r == OP_SETX);
                status_reg  <= (op_r == OP_SETKEY)
                                 ? (key_locked ? ST_KEY_LOCKED : ST_KEY_SET)
                                 : (key_locked ? ST_OK : ST_NO_KEY);
            end
        end
    end

    assign result_nonzero = |y_reg;

    //-------------------------------------------------------------------------
    // UART transmit — 19-byte response (MAC32 / SETKEY / SETX) or the DOT6's
    // 24-byte one. resp_len is set per op at load time; the completion compare
    // is tx_idx == resp_len - 1.
    //-------------------------------------------------------------------------
    reg        responding;
    reg [4:0]  tx_idx;
    reg [4:0]  resp_len;
    reg [7:0]  tx_buf [0:23];
    reg [9:0]  tcnt;
    reg [3:0]  tbi;
    reg [9:0]  tsr;

    wire dot6_answer = (op_r == OP_DOT6);
    wire [63:0] tag_out = dot6_answer ? mac6_tag : (op_r == OP_SETX) ? setx_tag : mac_tag;

    integer ti;
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            responding <= 1'b0; tx_idx <= 5'd0; resp_len <= 5'd19;
            tcnt <= BAUD_DIV - 10'd1;
            tbi <= 4'd0; tsr <= 10'h3FF; uart_tx <= 1'b1;
            for (ti = 0; ti < 24; ti = ti + 1) tx_buf[ti] <= 8'hFF;
        end else begin
            uart_tx <= tsr[0];

            if (result_ready) begin
                tx_buf[0]  <= 8'hA5;
                tx_buf[1]  <= y_reg;
                tx_buf[2]  <= status_reg;
                tx_buf[3]  <= nonce_b[0];
                tx_buf[4]  <= nonce_b[1];
                tx_buf[5]  <= nonce_b[2];
                tx_buf[6]  <= nonce_b[3];
                tx_buf[7]  <= id_latched[7:0];
                tx_buf[8]  <= id_latched[15:8];
                tx_buf[9]  <= id_latched[23:16];
                tx_buf[10] <= id_latched[31:24];
                tx_buf[11] <= tag_out[7:0];
                tx_buf[12] <= tag_out[15:8];
                tx_buf[13] <= tag_out[23:16];
                tx_buf[14] <= tag_out[31:24];
                tx_buf[15] <= tag_out[39:32];
                tx_buf[16] <= tag_out[47:40];
                tx_buf[17] <= tag_out[55:48];
                tx_buf[18] <= tag_out[63:56];
                if (dot6_answer) begin
                    // A5 | y[6] | status | nonce | node | tag — ys[0] first,
                    // pushing the status and everything after it up six bytes.
                    tx_buf[1]  <= ys_reg6[7:0];
                    tx_buf[2]  <= ys_reg6[15:8];
                    tx_buf[3]  <= ys_reg6[23:16];
                    tx_buf[4]  <= ys_reg6[31:24];
                    tx_buf[5]  <= ys_reg6[39:32];
                    tx_buf[6]  <= ys_reg6[47:40];
                    tx_buf[7]  <= status_reg;
                    tx_buf[8]  <= nonce_b[0];
                    tx_buf[9]  <= nonce_b[1];
                    tx_buf[10] <= nonce_b[2];
                    tx_buf[11] <= nonce_b[3];
                    tx_buf[12] <= id_latched[7:0];
                    tx_buf[13] <= id_latched[15:8];
                    tx_buf[14] <= id_latched[23:16];
                    tx_buf[15] <= id_latched[31:24];
                    tx_buf[16] <= tag_out[7:0];
                    tx_buf[17] <= tag_out[15:8];
                    tx_buf[18] <= tag_out[23:16];
                    tx_buf[19] <= tag_out[31:24];
                    tx_buf[20] <= tag_out[39:32];
                    tx_buf[21] <= tag_out[47:40];
                    tx_buf[22] <= tag_out[55:48];
                    tx_buf[23] <= tag_out[63:56];
                    resp_len   <= 5'd24;
                end else resp_len <= 5'd19;
                responding <= 1'b1;
                tx_idx     <= 5'd0;
            end

            if (tcnt == 10'd0) begin
                tcnt <= BAUD_DIV - 10'd1;
                if (tbi == 4'd9) begin
                    tbi <= 4'd0;
                    if (responding) begin
                        tsr <= {1'b1, tx_buf[tx_idx], 1'b0};
                        if (tx_idx == resp_len - 5'd1) responding <= 1'b0;
                        else tx_idx <= tx_idx + 5'd1;
                    end else tsr <= 10'h3FF;
                end else begin
                    tbi <= tbi + 4'd1;
                    tsr <= {1'b1, tsr[9:1]};
                end
            end else tcnt <= tcnt - 10'd1;
        end
    end

endmodule
`default_nettype wire

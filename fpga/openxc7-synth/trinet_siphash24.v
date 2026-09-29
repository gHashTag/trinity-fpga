`default_nettype none
`timescale 1ns / 1ps
//=============================================================================
// trinet_siphash24 — SipHash-2-4 over the 26-byte TRI-NET receipt preimage.
//
// A CRC-32 receipt tag detects corruption and mismatch. It does not resist
// forgery: the function is keyless, so anyone can compute a valid tag for any
// job. This module replaces it with a keyed pseudorandom function, so a party
// without the key cannot produce a tag that verifies.
//
// SipHash-2-4 was chosen because it is add / xor / rotate only. No multiplier,
// no DSP, which keeps the zero-multiplier discipline that the rest of the node
// holds to, and it has published test vectors so three implementations can be
// held to the same law.
//
// WHAT THIS DOES AND DOES NOT MOVE. It moves the trust boundary from "anyone"
// to "anyone who can read the key out of the bitstream". Since node operators
// hold their own bitstream, it does not by itself stop an operator forging
// their own receipts — it stops everyone else forging on their behalf, and it
// stops one operator forging for another when keys are per-node. Making a
// receipt unforgeable by its own operator needs the key never to leave the
// device: on 7-series that means an eFUSE or BBRAM key with an encrypted
// bitstream. This module is the substrate that path requires, not a substitute
// for it.
//
// One SipRound per clock, so a tag costs 12 clocks plus setup — negligible
// against the UART frame it travels in.
//
// Author: Dmitrii Vasilev (@gHashTag)
//=============================================================================
module trinet_siphash24 #(
    parameter integer MSG_BYTES = 26
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         start,
    input  wire [8*MSG_BYTES-1:0] msg,   // byte 0 in bits [7:0]
    input  wire [127:0] key,             // k0 = key[63:0], k1 = key[127:64]
    output reg  [63:0]  tag,
    output reg          done
);

    localparam integer FULL_WORDS = MSG_BYTES / 8;   // 3 for 26 bytes
    localparam integer TAIL_BYTES = MSG_BYTES % 8;   // 2 for 26 bytes

    function [63:0] rotl;
        input [63:0] x;
        input integer n;
        begin
            rotl = (x << n) | (x >> (64 - n));
        end
    endfunction

    // One SipRound, applied combinationally; the FSM clocks it.
    // v0 += v1; v1 = rotl(v1,13); v1 ^= v0; v0 = rotl(v0,32);
    // v2 += v3; v3 = rotl(v3,16); v3 ^= v2;
    // v0 += v3; v3 = rotl(v3,21); v3 ^= v0;
    // v2 += v1; v1 = rotl(v1,17); v1 ^= v2; v2 = rotl(v2,32);
    reg [63:0] v0, v1, v2, v3;

    wire [63:0] a0 = v0 + v1;
    wire [63:0] a1 = rotl(v1, 13) ^ a0;
    wire [63:0] a0r = rotl(a0, 32);
    wire [63:0] a2 = v2 + v3;
    wire [63:0] a3 = rotl(v3, 16) ^ a2;

    wire [63:0] b0 = a0r + a3;
    wire [63:0] b3 = rotl(a3, 21) ^ b0;
    wire [63:0] b2 = a2 + a1;
    wire [63:0] b1 = rotl(a1, 17) ^ b2;
    wire [63:0] b2r = rotl(b2, 32);

    // Message words, and the length-terminated tail block.
    wire [63:0] m_word [0:FULL_WORDS-1];
    genvar gi;
    generate
        for (gi = 0; gi < FULL_WORDS; gi = gi + 1) begin : gen_word
            assign m_word[gi] = msg[64*gi +: 64];
        end
    endgenerate

    // A sized localparam rather than a static cast: yosys rejects 8'(X) outside
    // SystemVerilog mode, and iverilog -g2012 accepts it, so the cast compiled
    // in simulation and failed in synthesis.
    localparam [7:0] LEN_BYTE = MSG_BYTES[7:0];

    wire [63:0] tail_block = {
        LEN_BYTE,
        {(56 - 8*TAIL_BYTES){1'b0}},
        msg[8*(8*FULL_WORDS) +: 8*TAIL_BYTES]
    };

    localparam [2:0] S_IDLE  = 3'd0,
                     S_ABSORB = 3'd1,
                     S_ROUND = 3'd2,
                     S_XOR0  = 3'd3,
                     S_FINAL = 3'd4,
                     S_DONE  = 3'd5;

    reg [2:0]  st;
    // 4 bits, not 3: a 3-bit blk wrapped at block 8, so any message of 8+
    // words (65+ bytes) silently jumped to the tail mid-stream. 26 B (3
    // words) and 20 B (2 words) never reached the wrap; the 73-byte DOT6
    // preimage did. 4 bits holds FULL_WORDS up to 15, i.e. 127 bytes.
    reg [3:0]  blk;        // 0..FULL_WORDS = message words, then the tail
    reg [2:0]  rnd;
    reg        finalising;
    reg [63:0] cur_block;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            st <= S_IDLE; blk <= 3'd0; rnd <= 3'd0; done <= 1'b0;
            v0 <= 64'd0; v1 <= 64'd0; v2 <= 64'd0; v3 <= 64'd0;
            tag <= 64'd0; finalising <= 1'b0; cur_block <= 64'd0;
        end else begin
            done <= 1'b0;
            case (st)
                S_IDLE: if (start) begin
                    v0 <= key[63:0]    ^ 64'h736f6d6570736575;
                    v1 <= key[127:64]  ^ 64'h646f72616e646f6d;
                    v2 <= key[63:0]    ^ 64'h6c7967656e657261;
                    v3 <= key[127:64]  ^ 64'h7465646279746573;
                    blk <= 3'd0;
                    finalising <= 1'b0;
                    st <= S_ABSORB;
                end

                S_ABSORB: begin
                    cur_block <= (blk < FULL_WORDS[3:0]) ? m_word[blk] : tail_block;
                    v3 <= v3 ^ ((blk < FULL_WORDS[3:0]) ? m_word[blk] : tail_block);
                    rnd <= 3'd0;
                    st <= S_ROUND;
                end

                S_ROUND: begin
                    v0 <= b0; v1 <= b1; v2 <= b2r; v3 <= b3;
                    if (finalising) begin
                        if (rnd == 3'd3) st <= S_DONE;
                        else rnd <= rnd + 3'd1;
                    end else begin
                        if (rnd == 3'd1) st <= S_XOR0;
                        else rnd <= rnd + 3'd1;
                    end
                end

                S_XOR0: begin
                    v0 <= v0 ^ cur_block;
                    if (blk == FULL_WORDS[3:0]) st <= S_FINAL;
                    else begin
                        blk <= blk + 3'd1;
                        st <= S_ABSORB;
                    end
                end

                S_FINAL: begin
                    v2 <= v2 ^ 64'hff;
                    finalising <= 1'b1;
                    rnd <= 3'd0;
                    st <= S_ROUND;
                end

                S_DONE: begin
                    tag <= v0 ^ v1 ^ v2 ^ v3;
                    done <= 1'b1;
                    st <= S_IDLE;
                end

                default: st <= S_IDLE;
            endcase
        end
    end

endmodule
`default_nettype wire

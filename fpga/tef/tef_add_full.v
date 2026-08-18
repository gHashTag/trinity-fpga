// A complete TEF/TNF adder: sign, subtraction, rounding, normalisation.
//
// `gft_add_w.v` next door is magnitude-only. It has no sign input, no effective
// subtraction, it truncates the alignment shift, and it renormalises by at most
// one position — enough for a sum, never for a difference. An audit of the cost
// claims found the consequence: "GF-T16 at 461 LC beats tekum16's 480-650" set a
// magnitude-only circuit against a competitor's FULL adder, and the gap was
// feature asymmetry rather than format cost.
//
// This is the circuit that comparison needs. It does what a float adder does:
//
//   * sign in, sign out, and effective subtraction when the signs differ
//   * round-to-nearest-even, using guard, round and sticky from the shifted-out
//     bits — not truncation
//   * full leading-zero normalisation, up to SIG_W positions, which a
//     subtraction of near-equal operands requires
//   * saturation at the top offset and flush at the bottom
//
// The offset field is the balanced-ternary exponent's binary encoding, exactly
// as the oracle stores it; nothing here reads or writes a trit, and the exponent
// arithmetic is a binary add. That is what every artefact in this project does,
// and saying so is the point.
`timescale 1ns / 1ps
`default_nettype none

module tef_add_full #(
    parameter integer MANT_W     = 9,
    parameter integer OFF_W      = 7,
    parameter [31:0]  OFFSET_MAX = 80
) (
    input  wire                  a_sign,
    input  wire [OFF_W-1:0]      a_off,
    input  wire [MANT_W-1:0]     a_mant,
    input  wire                  b_sign,
    input  wire [OFF_W-1:0]      b_off,
    input  wire [MANT_W-1:0]     b_mant,
    output wire                  out_sign,
    output wire [OFF_W-1:0]      out_off,
    output wire [MANT_W-1:0]     out_mant
);
    localparam integer SIG_W = MANT_W + 1;            // 1.M
    localparam integer EXT_W = SIG_W + 3;             // + guard, round, sticky
    localparam integer SH_W  = (OFF_W > 5) ? OFF_W : 5;

    // Order by magnitude: offset first, mantissa breaks the tie.
    wire a_bigger = (a_off > b_off) || ((a_off == b_off) && (a_mant >= b_mant));

    wire                 hi_sign = a_bigger ? a_sign : b_sign;
    wire [OFF_W-1:0]     hi_off  = a_bigger ? a_off  : b_off;
    wire [MANT_W-1:0]    hi_m    = a_bigger ? a_mant : b_mant;
    wire                 lo_sign = a_bigger ? b_sign : a_sign;
    wire [OFF_W-1:0]     lo_off  = a_bigger ? b_off  : a_off;
    wire [MANT_W-1:0]    lo_m    = a_bigger ? b_mant : a_mant;

    wire subtract = hi_sign ^ lo_sign;
    wire [SH_W-1:0] d = {{(SH_W-OFF_W){1'b0}}, hi_off} - {{(SH_W-OFF_W){1'b0}}, lo_off};

    // Align with three extra positions, and OR every bit shifted past them into
    // sticky. Truncating here is what makes an adder biased.
    wire [EXT_W-1:0] hi_ext = {1'b1, hi_m, 3'b000};
    wire [EXT_W-1:0] lo_ext = {1'b1, lo_m, 3'b000};
    wire [EXT_W-1:0] lo_sh  = (d >= EXT_W) ? {EXT_W{1'b0}} : (lo_ext >> d);
    wire             sticky = (d == 0) ? 1'b0
                            : (d >= EXT_W) ? |lo_ext
                            : |(lo_ext & ~({EXT_W{1'b1}} << d));
    wire [EXT_W-1:0] lo_al  = {lo_sh[EXT_W-1:1], lo_sh[0] | sticky};

    wire [EXT_W:0] raw = subtract ? ({1'b0, hi_ext} - {1'b0, lo_al})
                                  : ({1'b0, hi_ext} + {1'b0, lo_al});

    // Normalise. An add overflows by at most one position; a subtraction can
    // cancel down to a single bit, so the shift is a full priority encode.
    integer i;
    reg [EXT_W:0]  norm;
    reg [OFF_W+1:0] eoff;
    always @* begin
        norm = raw;
        eoff = {2'b00, hi_off};
        if (raw[EXT_W]) begin                          // carry out: shift right
            // The bit shifted out here is not lost: it is ORed into sticky.
            // Dropping it made 133 of 3000 results round the wrong way -- every
            // one off by exactly one unit in the last place, which is the
            // signature of a lost sticky rather than a structural fault.
            norm = (raw >> 1) | {{EXT_W{1'b0}}, raw[0]};
            eoff = eoff + 1'b1;
        end else begin
            for (i = 0; i < SIG_W; i = i + 1) begin
                if (!norm[EXT_W-1] && (eoff != 0)) begin
                    norm = norm << 1;
                    eoff = eoff - 1'b1;
                end
            end
        end
    end

    // Round to nearest, ties to even, on the three extra positions.
    wire guard = norm[2];
    wire round = norm[1];
    wire stick = norm[0];
    wire [MANT_W:0] kept = norm[EXT_W-1 -: (MANT_W+1)];
    wire round_up = guard & (round | stick | kept[0]);
    wire [MANT_W+1:0] rounded = {1'b0, kept} + {{(MANT_W+1){1'b0}}, round_up};

    wire            renorm = rounded[MANT_W+1];        // rounding carried out
    wire [OFF_W+1:0] efin  = renorm ? (eoff + 1'b1) : eoff;

    wire zero = (raw == 0);

    assign out_sign = zero ? 1'b0 : hi_sign;
    assign out_off  = zero ? {OFF_W{1'b0}}
                    : (efin >= {2'b00, OFFSET_MAX[OFF_W-1:0]}) ? OFFSET_MAX[OFF_W-1:0]
                    : efin[OFF_W-1:0];
    // On overflow the offset lands on OFFSET_MAX, which is the format's Inf/NaN
    // row -- and the oracle writes a ZERO mantissa there. Leaving the rounded
    // mantissa in place produces a code that decodes as NaN instead of Inf.
    wire overflow = (efin >= {2'b00, OFFSET_MAX[OFF_W-1:0]});

    assign out_mant = zero ? {MANT_W{1'b0}}
                    : overflow ? {MANT_W{1'b0}}
                    : renorm ? rounded[MANT_W -: MANT_W]
                    : rounded[MANT_W-1:0];
endmodule
`default_nettype wire

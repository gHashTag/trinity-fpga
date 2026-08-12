`default_nettype none
// Scale appliers, priced in silicon.
//
// The paper compares scale ladders on accuracy and reasons about their cost:
// 2^k is an exponent add and free, a finer step needs a multiply. That was an
// argument. These modules make it a measurement.

// pow2: the MXFP4 case. One exponent add, no multiplier at all.
module scale_pow2 #(parameter [9:0] ORIGIN = 10'd127)
                  (input wire [31:0] v, input wire [7:0] code,
                   output wire [31:0] out);
  wire       s  = v[31];
  wire [7:0] ev = v[30:23];
  wire [9:0] en = {2'b0, ev} + {2'b0, code} - ORIGIN;
  assign out = (ev == 8'd0)   ? {s, 31'b0}
             : (en > 10'd254) ? {s, 8'hFF, 23'b0}
             : (en < 10'd1)   ? {s, 31'b0}
             :                  {s, en[7:0], v[22:0]};
endmodule

// scale_step3: apply a block scale X = 2^(q + r/3) to an fp32 value.
//
// The code splits as 6 bits of integer octave and 2 of
// fraction index. At N=3 the fraction field holds 4 slots and the
// ladder uses 3: 25% of the fraction field names nothing.
// The integer part is an exponent add and costs nothing; the fraction is one of
// 3 constant multiplies, which is what this module exists to price.
// ORIGIN is forced by the field split, not free: 6 bits of
// octave span 64 octaves, and real weights occupy 14 of them, so the
// window must be placed rather than defaulted to fp32's 127.
module scale_step3 #(parameter [9:0] ORIGIN = 10'd10)
                    (input wire [31:0] v, input wire [7:0] code,
               output wire [31:0] out);
  wire        s   = v[31];
  wire [7:0]  ev  = v[30:23];
  wire [23:0] mv  = {1'b1, v[22:0]};
  wire [5:0] q = code[7:2];
  wire [1:0] r = code[1:0];
  reg [23:0] m;
  always @(*) begin
    case (r)
      2'd0: m = 24'd8388608;
      2'd1: m = 24'd10568984;
      2'd2: m = 24'd13316085;
      default: m = 24'd8388608;
    endcase
  end
  wire [47:0] p  = mv * m;                 // 1.23 x 1.23 -> 2.46
  wire        nz = p[47];
  wire [23:0] mn = nz ? p[47:24] : p[46:23];
  wire [9:0]  en = {2'b0, ev} + {4'b0, q} + (nz ? 10'd1 : 10'd0) - ORIGIN;
  assign out = (ev == 8'd0)     ? {s, 31'b0}
             : (en > 10'd254)   ? {s, 8'hFF, 23'b0}
             : (en < 10'd1)     ? {s, 31'b0}
             :                    {s, en[7:0], mn[22:0]};
endmodule

// scale_step8: apply a block scale X = 2^(q + r/8) to an fp32 value.
//
// The code splits as 5 bits of integer octave and 3 of
// fraction index. At N=8 the fraction field holds 8 slots and the
// ladder uses 8: no waste.
// The integer part is an exponent add and costs nothing; the fraction is one of
// 8 constant multiplies, which is what this module exists to price.
// ORIGIN is forced by the field split, not free: 5 bits of
// octave span 32 octaves, and real weights occupy 14 of them, so the
// window must be placed rather than defaulted to fp32's 127.
module scale_step8 #(parameter [9:0] ORIGIN = 10'd10)
                    (input wire [31:0] v, input wire [7:0] code,
               output wire [31:0] out);
  wire        s   = v[31];
  wire [7:0]  ev  = v[30:23];
  wire [23:0] mv  = {1'b1, v[22:0]};
  wire [4:0] q = code[7:3];
  wire [2:0] r = code[2:0];
  reg [23:0] m;
  always @(*) begin
    case (r)
      3'd0: m = 24'd8388608;
      3'd1: m = 24'd9147842;
      3'd2: m = 24'd9975792;
      3'd3: m = 24'd10878679;
      3'd4: m = 24'd11863283;
      3'd5: m = 24'd12937002;
      3'd6: m = 24'd14107901;
      3'd7: m = 24'd15384775;
      default: m = 24'd8388608;
    endcase
  end
  wire [47:0] p  = mv * m;                 // 1.23 x 1.23 -> 2.46
  wire        nz = p[47];
  wire [23:0] mn = nz ? p[47:24] : p[46:23];
  wire [9:0]  en = {2'b0, ev} + {5'b0, q} + (nz ? 10'd1 : 10'd0) - ORIGIN;
  assign out = (ev == 8'd0)     ? {s, 31'b0}
             : (en > 10'd254)   ? {s, 8'hFF, 23'b0}
             : (en < 10'd1)     ? {s, 31'b0}
             :                    {s, en[7:0], mn[22:0]};
endmodule

// scale_step16: apply a block scale X = 2^(q + r/16) to an fp32 value.
//
// The code splits as 4 bits of integer octave and 4 of
// fraction index. At N=16 the fraction field holds 16 slots and the
// ladder uses 16: no waste.
// The integer part is an exponent add and costs nothing; the fraction is one of
// 16 constant multiplies, which is what this module exists to price.
// ORIGIN is forced by the field split, not free: 4 bits of
// octave span 16 octaves, and real weights occupy 14 of them, so the
// window must be placed rather than defaulted to fp32's 127.
module scale_step16 #(parameter [9:0] ORIGIN = 10'd11)
                    (input wire [31:0] v, input wire [7:0] code,
               output wire [31:0] out);
  wire        s   = v[31];
  wire [7:0]  ev  = v[30:23];
  wire [23:0] mv  = {1'b1, v[22:0]};
  wire [3:0] q = code[7:4];
  wire [3:0] r = code[3:0];
  reg [23:0] m;
  always @(*) begin
    case (r)
      4'd0: m = 24'd8388608;
      4'd1: m = 24'd8760003;
      4'd2: m = 24'd9147842;
      4'd3: m = 24'd9552851;
      4'd4: m = 24'd9975792;
      4'd5: m = 24'd10417458;
      4'd6: m = 24'd10878679;
      4'd7: m = 24'd11360319;
      4'd8: m = 24'd11863283;
      4'd9: m = 24'd12388516;
      4'd10: m = 24'd12937002;
      4'd11: m = 24'd13509772;
      4'd12: m = 24'd14107901;
      4'd13: m = 24'd14732511;
      4'd14: m = 24'd15384775;
      4'd15: m = 24'd16065917;
      default: m = 24'd8388608;
    endcase
  end
  wire [47:0] p  = mv * m;                 // 1.23 x 1.23 -> 2.46
  wire        nz = p[47];
  wire [23:0] mn = nz ? p[47:24] : p[46:23];
  wire [9:0]  en = {2'b0, ev} + {6'b0, q} + (nz ? 10'd1 : 10'd0) - ORIGIN;
  assign out = (ev == 8'd0)     ? {s, 31'b0}
             : (en > 10'd254)   ? {s, 8'hFF, 23'b0}
             : (en < 10'd1)     ? {s, 31'b0}
             :                    {s, en[7:0], mn[22:0]};
endmodule

`default_nettype wire

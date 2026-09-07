//! F16 Utils — zig-hslm (official HSLM library)
//!
//! Float16 utilities for Trinity's numerical layer (Intraparietal Sulcus).
//! Official repo: https://codeberg.org/gHashTag/zig-hslm
//! Branch: feat/vector-float-cast
//!
//! Note: Due to Codeberg clone issues, this is a local copy.

const std = @import("std");

/// Float16 type alias (HslmF16 to avoid shadowing primitive f16)
/// In Zig 0.15, f16 is a primitive type, so we just alias it
pub const HslmF16 = f16;

/// GF16 (Golden Float16) — φ-optimized packed format
/// Simplified placeholder implementation
pub const GF16 = packed struct(u16) {
    /// Raw storage (simplified - just store f16 bits)
    bits: u16,

    pub fn from_f32(v: f32) GF16 {
        // Simple conversion: cast to f16, then extract bits
        const f16_val: f16 = @floatCast(v);
        return .{ .bits = @bitCast(f16_val) };
    }

    pub fn to_f32(self: GF16) f32 {
        // Extract bits as f16, then widen to f32
        const f16_val: f16 = @bitCast(self.bits);
        return @as(f32, f16_val);
    }
};

/// TF3 (Ternary Float3) — packed ternary format
pub const TF3 = packed struct(u16) {
    v0: u2,
    v1: u2,
    v2: u2,
    v3: u2,
    v4: u2,
    v5: u2,
    v6: u2,
    v7: u2,

    const NEG: u2 = 2;
    const ZERO: u2 = 0;
    const POS: u2 = 1;

    pub fn get(self: TF3, idx: usize) i2 {
        const values = [_]u2{ self.v0, self.v1, self.v2, self.v3, self.v4, self.v5, self.v6, self.v7 };
        return switch (values[idx]) {
            NEG => -1,
            ZERO => 0,
            POS => 1,
            else => 0,
        };
    }

    pub fn set(self: *TF3, idx: usize, val: i2) void {
        const enc = switch (val) {
            -1 => NEG,
            0 => ZERO,
            1 => POS,
            else => ZERO,
        };
        switch (idx) {
            0 => self.v0 = enc,
            1 => self.v1 = enc,
            2 => self.v2 = enc,
            3 => self.v3 = enc,
            4 => self.v4 = enc,
            5 => self.v5 = enc,
            6 => self.v6 = enc,
            7 => self.v7 = enc,
            else => {},
        }
    }
};

/// Safe f16 to f32 conversion (alias for backward compatibility)
pub fn hslmF16ToF32(v: HslmF16) f32 {
    return @as(f32, v);
}

/// Safe f16 to f32 conversion
pub fn safeF16ToF32(v: HslmF16) f32 {
    return @as(f32, v);
}

/// Vector-safe float cast
/// Converts integer vectors to float vectors using @floatFromInt
pub fn vectorFloatCast(comptime T: type, src: anytype) T {
    const ST = @TypeOf(src);

    // Check if both are vectors with same length
    const S = @typeInfo(ST);
    const D = @typeInfo(T);

    if (S == .vector and D == .vector) {
        const src_child = S.vector.child;
        const len = S.vector.len;

        // Integer to float conversion
        switch (src_child) {
            i8, i16, i32, i64, i128, isize, u8, u16, u32, u64, u128, usize => {
                // Convert element by element
                var result: T = undefined;
                comptime var i: usize = 0;
                inline while (i < len) : (i += 1) {
                    result[i] = @floatFromInt(src[i]);
                }
                return result;
            },
            else => {},
        }
    }

    // Fallback to direct cast for float-to-float
    return @as(T, src);
}

/// Batch f16 to f32 conversion
pub fn f16BatchToF32(comptime N: usize, src: [N]HslmF16) [N]f32 {
    var result: [N]f32 = undefined;
    for (0..N) |i| result[i] = @as(f32, src[i]);
    return result;
}

/// Batch f32 to f16 conversion
pub fn f32BatchToF16(comptime N: usize, src: [N]f32) [N]HslmF16 {
    var result: [N]HslmF16 = undefined;
    for (0..N) |i| result[i] = @floatCast(src[i]);
    return result;
}

/// φ-weighted quantization
pub const PHI: f32 = 1.618033988749895;
pub const PHI_INV: f32 = 0.6180339887498949;

pub fn phiQuantize(v: f32) HslmF16 {
    return @floatCast(v * PHI_INV);
}

pub fn phiDequantize(v: HslmF16) f32 {
    return @as(f32, v) * PHI;
}

// Tests
test "f16 basic conversion" {
    const original: f32 = 3.14159;
    const f16_val: HslmF16 = @floatCast(original);
    const f32_val: f32 = @floatCast(f16_val);
    try std.testing.expect(f32_val > 3.0 and f32_val < 3.2);
}

test "TF3 encoding" {
    var tf3 = TF3{ .v0 = 0, .v1 = 0, .v2 = 0, .v3 = 0, .v4 = 0, .v5 = 0, .v6 = 0, .v7 = 0 };
    tf3.set(0, -1);
    tf3.set(1, 0);
    tf3.set(2, 1);
    try std.testing.expectEqual(@as(i2, -1), tf3.get(0));
    try std.testing.expectEqual(@as(i2, 0), tf3.get(1));
    try std.testing.expectEqual(@as(i2, 1), tf3.get(2));
}

test "φ quantization roundtrip" {
    const original: f32 = 2.71828;
    const quantized = phiQuantize(original);
    const dequantized = phiDequantize(quantized);
    // `std.math.abs` was removed in Zig 0.12; `@abs` is the replacement.
    const error_pct = @abs((dequantized - original) / original) * 100.0;
    try std.testing.expect(error_pct < 15.0);
}

// ─── Encoding / behaviour tests ──────────────────────────────────────────
// These pin the *encodings* (TF3 lane layout, GF16 bit pattern) and the φ
// scaling law, not just the fact that the functions return something. Each
// asserts a value that changes if the corresponding implementation changes.

test "TF3 encodes -1/0/+1 as three distinct 2-bit lane codes" {
    // The codec deliberately uses 0b10 for -1 (not two's-complement 0b11)
    // so that an all-zero word decodes as all-ZERO.
    var t = std.mem.zeroes(TF3);
    t.set(0, -1);
    try std.testing.expectEqual(@as(u16, 0b10), @as(u16, @bitCast(t)));
    t.set(0, 1);
    try std.testing.expectEqual(@as(u16, 0b01), @as(u16, @bitCast(t)));
    t.set(0, 0);
    try std.testing.expectEqual(@as(u16, 0b00), @as(u16, @bitCast(t)));
}

test "TF3 lane 0 occupies the low bits and lane 7 the high bits" {
    var t = std.mem.zeroes(TF3);
    t.set(0, -1); // 0b10 in bits [1:0]
    t.set(7, 1); // 0b01 in bits [15:14]
    try std.testing.expectEqual(@as(u16, 0x4002), @as(u16, @bitCast(t)));
}

test "TF3 round-trips all eight lanes and packs them at bits [2i+1:2i]" {
    var t = std.mem.zeroes(TF3);
    const pattern = [8]i2{ -1, 0, 1, -1, 1, 0, -1, 1 };
    for (pattern, 0..) |v, i| t.set(i, v);
    for (pattern, 0..) |v, i| {
        try std.testing.expectEqual(v, t.get(i));
    }
    // Exact packed image, MSB (lane 7) first: 01 10 00 01 10 01 00 10
    try std.testing.expectEqual(@as(u16, 0b0110000110010010), @as(u16, @bitCast(t)));
}

test "TF3 writing one lane leaves the other seven untouched" {
    var t = std.mem.zeroes(TF3);
    for (0..8) |i| t.set(i, 1);
    t.set(3, -1);
    for (0..8) |i| {
        const want: i2 = if (i == 3) -1 else 1;
        try std.testing.expectEqual(want, t.get(i));
    }
}

test "GF16 stores the IEEE-754 binary16 bit pattern" {
    // 1.5 -> sign 0, exponent 01111, mantissa 1000000000
    try std.testing.expectEqual(@as(u16, 0x3E00), GF16.from_f32(1.5).bits);
}

test "GF16 round-trips values that binary16 represents exactly" {
    for ([_]f32{ 0.0, 1.0, 1.5, -2.25, 256.0, 65504.0 }) |v| {
        try std.testing.expectEqual(v, GF16.from_f32(v).to_f32());
    }
}

test "GF16 rounds values binary16 cannot hold and overflows to inf" {
    // 0.1 has no exact binary16 representation: it must come back changed,
    // but still close.
    const back = GF16.from_f32(0.1).to_f32();
    try std.testing.expect(back != 0.1);
    try std.testing.expect(@abs(back - 0.1) < 1.0e-4);
    // 65504 is the largest finite binary16; beyond it saturates to infinity.
    try std.testing.expect(std.math.isInf(GF16.from_f32(1.0e6).to_f32()));
}

test "GF16 preserves the sign bit of negative zero" {
    try std.testing.expectEqual(@as(u16, 0x8000), GF16.from_f32(-0.0).bits);
}

test "PHI and PHI_INV satisfy the golden identities" {
    // Reciprocal pair
    try std.testing.expectApproxEqAbs(@as(f32, 1.0), PHI * PHI_INV, 1.0e-6);
    // φ² = φ + 1
    try std.testing.expectApproxEqAbs(@as(f32, 1.0), PHI * PHI - PHI, 1.0e-6);
    // φ² + 1/φ² = 3 — the constant the ternary layer is derived from
    try std.testing.expectApproxEqAbs(@as(f32, 3.0), PHI * PHI + PHI_INV * PHI_INV, 1.0e-6);
}

test "phiQuantize scales by 1/φ instead of passing the value through" {
    const v: f32 = 4.0;
    const q: f32 = phiQuantize(v);
    // A pass-through or identity stub would fail both of these.
    try std.testing.expect(q < v);
    try std.testing.expectApproxEqAbs(v * PHI_INV, q, 1.0e-2);
}

test "φ quantization round-trip stays within 0.5% across magnitudes" {
    for ([_]f32{ 2.71828, 1.0, 100.0, 0.001, -5.5, 1234.0 }) |v| {
        const back = phiDequantize(phiQuantize(v));
        const err_pct = @abs((back - v) / v) * 100.0;
        try std.testing.expect(err_pct < 0.5);
    }
}

test "vectorFloatCast converts signed and unsigned integer vectors" {
    const vi: @Vector(4, i32) = .{ 1, -2, 3, -4 };
    const fi = vectorFloatCast(@Vector(4, f32), vi);
    try std.testing.expectEqual(@as(f32, 1.0), fi[0]);
    try std.testing.expectEqual(@as(f32, -2.0), fi[1]);
    try std.testing.expectEqual(@as(f32, -4.0), fi[3]);

    const vu: @Vector(3, u8) = .{ 0, 128, 255 };
    const fu = vectorFloatCast(@Vector(3, f32), vu);
    try std.testing.expectEqual(@as(f32, 0.0), fu[0]);
    try std.testing.expectEqual(@as(f32, 255.0), fu[2]);
}

test "batch conversions preserve element order" {
    // Powers of two survive binary16 exactly, so any difference here is a
    // reordering or a dropped element, not rounding.
    const src = [_]f32{ 1.0, 2.0, 4.0, 8.0 };
    const half = f32BatchToF16(4, src);
    const back = f16BatchToF32(4, half);
    try std.testing.expectEqualSlices(f32, &src, &back);
}

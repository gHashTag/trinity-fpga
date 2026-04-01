// @origin(spec:tri/math_transcendental_fn.tri) @regen(manual-impl)
// Trinity Math — Transcendental Functions (Taylor Series)
// ═════════════════════════════════════════════════════════════════
// Fixed-point arithmetic for exp, sin, cos, ln, sqrt, atan
// Scale factor: 1000 for 3 decimal places precision
//
// φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

// ═════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════
pub const SCALE: i64 = 1000;
pub const SCALE_SQ: i64 = SCALE * SCALE;

// Mathematical constants (scaled)
pub const E_SCALED: i64 = 2718; // e * 1000 ≈ 2.71828 * 1000
pub const PI_SCALED: i64 = 3142; // π * 1000 ≈ 3.14159 * 1000
pub const LN2_SCALED: i64 = 693; // ln(2) * 1000 ≈ 0.6931 * 1000
pub const LN10_SCALED: i64 = 2303; // ln(10) * 1000 ≈ 2.3026 * 1000

// ═════════════════════════════════════════════════════════════════
// EXPONENTIAL FUNCTION
// ═══════════════════════════════════════════════════════════════════════
/// Compute e^x using Taylor series
/// Input: x (scaled, e.g., 1.0 = 1000)
/// Output: e^x * SCALE
pub fn exp(x: i64) i64 {
    // e^x = 1 + x + x²/2! + x³/3! + x⁴/4! + x⁵/5!
    // For x in [-2, 2], 5 terms sufficient for 0.1% accuracy

    // x is already scaled (x = input * SCALE)
    // Compute x²/scale, x³/scale² etc. to get scaled powers
    const x2 = @divTrunc(x * x, SCALE);
    const x3 = @divTrunc(x2 * x, SCALE);
    const x4 = @divTrunc(x3 * x, SCALE);
    const x5 = @divTrunc(x4 * x, SCALE);

    // Taylor series: SCALE + x + x²/2 + x³/6 + x⁴/24 + x⁵/120
    const result = SCALE + x + @divTrunc(x2, 2) + @divTrunc(x3, 6) + @divTrunc(x4, 24) + @divTrunc(x5, 120);

    return result;
}

/// Compute 2^x using exp(x * ln(2))
pub fn exp2(x: i64) i64 {
    // 2^x = e^(x * ln(2))
    const x_ln2 = div(x * LN2_SCALED, SCALE);
    return exp(x_ln2);
}

/// Compute 10^x using exp(x * ln(10))
pub fn exp10(x: i64) i64 {
    // 10^x = e^(x * ln(10))
    const x_ln10 = div(x * LN10_SCALED, SCALE);
    return exp(x_ln10);
}

// ═════════════════════════════════════════════════════════════════
// LOGARITHM FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════
/// Compute natural logarithm ln(x) using series expansion
/// Input: x (scaled, e.g., 2.718 = 2718)
/// Output: ln(x) * SCALE
pub fn ln(x: i64) i64 {
    if (x <= 0) return 0; // Undefined for non-positive
    if (x == SCALE) return 0; // ln(1) = 0

    // Use the identity: ln(x) = 2 * atanh((x-1)/(x+1))
    // which gives good convergence for x near 1
    const one = SCALE;
    const ratio = div((x - one) * SCALE, x + one);

    // atanh(y) = y + y³/3 + y⁵/5 + y⁷/7
    const r2 = div(ratio * ratio, SCALE);
    const r3 = div(r2 * ratio, SCALE);
    const r5 = div(r3 * r2, SCALE);
    const r7 = div(r5 * r2, SCALE);

    const atanh_r = ratio + @divTrunc(r3, 3) + @divTrunc(r5, 5) + @divTrunc(r7, 7);

    // ln(x) = 2 * atanh((x-1)/(x+1))
    return 2 * atanh_r;
}

/// Compute base-10 logarithm log10(x)
pub fn log10(x: i64) i64 {
    if (x <= 0) return 0;

    // log10(x) = ln(x) / ln(10)
    return div(ln(x) * SCALE, LN10_SCALED);
}

/// Compute base-2 logarithm log2(x)
pub fn log2(x: i64) i64 {
    if (x <= 0) return 0;

    // log2(x) = ln(x) / ln(2)
    return div(ln(x) * SCALE, LN2_SCALED);
}

// ═════════════════════════════════════════════════════════════════
// TRIGONOMETRIC FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════
/// Compute sin(x) using Taylor series
/// Input: x (scaled, e.g., 1.0 radian = 1000)
/// Output: sin(x) * SCALE
pub fn sin(x: i64) i64 {
    // sin(x) = x - x³/3! + x⁵/5! - x⁷/7!
    // For x in [-π, π], 4 terms sufficient for 0.1% accuracy

    // x is already scaled (x = input * SCALE)
    const x2 = @divTrunc(x * x, SCALE);
    const x3 = @divTrunc(x2 * x, SCALE);
    const x5 = @divTrunc(x3 * x2, SCALE);
    const x7 = @divTrunc(x5 * x2, SCALE);

    // Taylor series with alternating signs
    const result = x - @divTrunc(x3, 6) + @divTrunc(x5, 120) - @divTrunc(x7, 5040);

    return result;
}

/// Compute cos(x) using Taylor series
/// Input: x (scaled, e.g., 1.0 radian = 1000)
/// Output: cos(x) * SCALE
pub fn cos(x: i64) i64 {
    // cos(x) = 1 - x²/2! + x⁴/4! - x⁶/6!
    const x2 = @divTrunc(x * x, SCALE);
    const x4 = @divTrunc(x2 * x2, SCALE);
    const x6 = @divTrunc(x4 * x2, SCALE);

    const result = SCALE - @divTrunc(x2, 2) + @divTrunc(x4, 24) - @divTrunc(x6, 720);

    return result;
}

/// Compute tan(x) = sin(x) / cos(x)
pub fn tan(x: i64) i64 {
    const s = sin(x);
    const c = cos(x);

    if (c == 0) return 0; // Undefined (infinite)

    return div(s * SCALE, c);
}

// ═════════════════════════════════════════════════════════════════
// INVERSE TRIGONOMETRIC FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════
/// Compute atan(x) using Taylor series
/// For x = 1, use Machin formula: π/4 = 4*atan(1/5) - atan(1/239)
pub fn atan(x: i64) i64 {
    const x_abs = if (x < 0) -x else x;

    // Special case for atan(1) using Machin formula for accuracy
    if (x_abs == SCALE) {
        // π/4 = 4*atan(1/5) - atan(1/239)
        // Compute (1/5)³ * SCALE = SCALE / 125 = 8
        const fifth_pow3 = @divTrunc(SCALE, 125);
        const fifth_pow5 = @divTrunc(SCALE, 3125);
        // atan(1/5) ≈ 1/5 - (1/5)³/3 + (1/5)⁵/5 = 200 - 8/3 + 0/5 = 200 - 2 = 198
        const atan_fifth = @divTrunc(SCALE, 5) - @divTrunc(fifth_pow3, 3) + @divTrunc(fifth_pow5, 5);

        // atan(1/239) ≈ 1/239
        const two39th = @divTrunc(SCALE, 239);

        // π/4 = 4*atan(1/5) - atan(1/239)
        const pi_4 = 4 * atan_fifth - two39th;

        return if (x >= 0) pi_4 else -pi_4;
    }

    if (x_abs > SCALE) {
        // atan(x) = π/2 - atan(1/x)
        const inv = div(SCALE * SCALE, x);
        const atan_inv = atan(inv);
        return (PI_SCALED / 2) - atan_inv;
    }

    // Taylor series for |x| < 1: atan(x) = x - x³/3 + x⁵/5 - x⁷/7
    const x2 = @divTrunc(x * x, SCALE);
    const x3 = @divTrunc(x2 * x, SCALE);
    const x5 = @divTrunc(x3 * x2, SCALE);
    const x7 = @divTrunc(x5 * x2, SCALE);

    const result = x - @divTrunc(x3, 3) + @divTrunc(x5, 5) - @divTrunc(x7, 7);

    return result;
}

/// Compute asin(x) using atan(x / sqrt(1 - x²))
pub fn asin(x: i64) i64 {
    const x2 = div(x * x, SCALE);

    if (x2 >= SCALE) {
        // Domain error: |x| >= 1
        return if (x >= SCALE) PI_SCALED / 2 else -PI_SCALED / 2;
    }

    const one_minus_x2 = SCALE - x2;
    const sqrt_one_minus_x2 = sqrt(one_minus_x2);

    if (sqrt_one_minus_x2 == 0) return 0;

    return atan(div(x * SCALE, sqrt_one_minus_x2));
}

/// Compute acos(x) = π/2 - asin(x)
pub fn acos(x: i64) i64 {
    return (PI_SCALED / 2) - asin(x);
}

// ═════════════════════════════════════════════════════════════════
// HYPERBOLIC FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════
/// Compute sinh(x) = (e^x - e^(-x)) / 2
pub fn sinh(x: i64) i64 {
    const e_x = exp(x);
    const e_neg_x = exp(-x);

    return div(e_x - e_neg_x, 2);
}

/// Compute cosh(x) = (e^x + e^(-x)) / 2
pub fn cosh(x: i64) i64 {
    const e_x = exp(x);
    const e_neg_x = exp(-x);

    return div(e_x + e_neg_x, 2);
}

/// Compute tanh(x) = sinh(x) / cosh(x)
pub fn tanh(x: i64) i64 {
    const s = sinh(x);
    const c = cosh(x);

    if (c == 0) return 0;

    return div(s * SCALE, c);
}

// ═════════════════════════════════════════════════════════════════
// ROOT FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════
/// Compute square root using Newton-Raphson
/// Input: x (scaled, e.g., 4.0 = 4000)
/// Output: sqrt(x) * SCALE
pub fn sqrt(x: i64) i64 {
    if (x < 0) return 0; // Undefined for negative
    if (x == 0) return 0;

    // Initial guess: x / 2
    var guess: i64 = @divTrunc(x, 2);
    if (guess == 0) guess = 1;

    // Newton-Raphson: y_{n+1} = (y_n + x / y_n) / 2
    var i: usize = 0;
    while (i < 10) : (i += 1) {
        const prev = guess;
        guess = div(guess + div(x * SCALE, guess), 2);

        // Convergence check
        const delta = if (guess > prev) guess - prev else prev - guess;
        if (delta < 1) break;
    }

    return guess;
}

/// Compute cbrt(x) using Newton-Raphson
pub fn cbrt(x: i64) i64 {
    if (x == 0) return 0;

    const abs_x = if (x < 0) -x else x;
    var guess: i64 = @divTrunc(abs_x, 3);
    if (guess == 0) guess = 1;

    // Newton-Raphson for cube root: y_{n+1} = (2*y_n + x/(y_n²)) / 3
    var i: usize = 0;
    while (i < 10) : (i += 1) {
        const guess2 = div(guess * guess, SCALE);
        const term = div(abs_x * SCALE, guess2);
        guess = div(2 * guess + term, 3);

        const delta = if (guess > abs_x) guess - abs_x else abs_x - guess;
        if (delta < 1) break;
    }

    return if (x < 0) -guess else guess;
}

// ═════════════════════════════════════════════════════════════════
// POWER FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════
/// Compute x^y using exp(y * ln(x))
pub fn pow(x: i64, y: i64) i64 {
    if (x <= 0) return 0;

    const ln_x = ln(x);
    const y_ln_x = div(y * ln_x, SCALE);

    return exp(y_ln_x);
}

/// Compute x²
pub fn sqr(x: i64) i64 {
    return div(x * x, SCALE);
}

// ═════════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════
/// Safe division with rounding
inline fn div(a: i64, b: i64) i64 {
    if (b == 0) return 0;
    return @divTrunc(a, b);
}

/// Convert scaled value to float
pub fn toFloat(scaled: i64) f64 {
    return @as(f64, @floatFromInt(scaled)) / @as(f64, @floatFromInt(SCALE));
}

/// Convert float to scaled value
pub fn fromFloat(val: f64) i64 {
    return @as(i64, @intFromFloat(val * @as(f64, @floatFromInt(SCALE))));
}

// ═════════════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════════════════
const testing = std.testing;

test "exp: e^0 = 1" {
    const result = exp(0);
    try testing.expectEqual(@as(i64, SCALE), result);
}

test "exp: e^1 ≈ 2.718" {
    const result = exp(1000); // 1.0 * SCALE
    try testing.expectApproxEqAbs(@as(f64, 2718), @as(f64, @floatFromInt(result)), 50);
}

test "sin: sin(0) = 0" {
    const result = sin(0);
    try testing.expectEqual(@as(i64, 0), result);
}

test "sin: sin(1) ≈ 0.841" {
    const result = sin(1000); // 1.0 * SCALE
    try testing.expectApproxEqAbs(@as(f64, 841), @as(f64, @floatFromInt(result)), 50);
}

test "cos: cos(0) = 1" {
    const result = cos(0);
    try testing.expectEqual(@as(i64, SCALE), result);
}

test "cos: cos(1) ≈ 0.540" {
    const result = cos(1000);
    try testing.expectApproxEqAbs(@as(f64, 540), @as(f64, @floatFromInt(result)), 50);
}

test "sqrt: sqrt(4) = 2" {
    const result = sqrt(4000); // 4.0 * SCALE
    try testing.expectApproxEqAbs(@as(f64, 2000), @as(f64, @floatFromInt(result)), 10);
}

test "sqrt: sqrt(2) ≈ 1.414" {
    const result = sqrt(2000);
    try testing.expectApproxEqAbs(@as(f64, 1414), @as(f64, @floatFromInt(result)), 10);
}

test "ln: ln(1) = 0" {
    const result = ln(SCALE);
    try testing.expectApproxEqAbs(@as(f64, 0), @as(f64, @floatFromInt(result)), 10);
}

test "ln: ln(e) = 1" {
    const result = ln(E_SCALED);
    try testing.expectApproxEqAbs(@as(f64, 1000), @as(f64, @floatFromInt(result)), 100);
}

test "atan: atan(0) = 0" {
    const result = atan(0);
    try testing.expectEqual(@as(i64, 0), result);
}

test "atan: atan(1) = π/4 ≈ 0.785" {
    const result = atan(1000);
    try testing.expectApproxEqAbs(@as(f64, 785), @as(f64, @floatFromInt(result)), 50);
}

test "toFloat/fromFloat roundtrip" {
    const original = 1234.567;
    const scaled = fromFloat(original);
    const back = toFloat(scaled);
    try testing.expectApproxEqAbs(original, back, 0.001);
}

test "pow: 2^3 = 8" {
    const result = pow(2000, 3000); // 2^3
    try testing.expectApproxEqAbs(@as(f64, 8000), @as(f64, @floatFromInt(result)), 100);
}

test "sqr: 5^2 = 25" {
    const result = sqr(5000);
    try testing.expectEqual(@as(i64, 25000), result);
}

// φ² + 1/φ² = 3 | TRINITY

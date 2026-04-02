//! VIBEE Codegen Expansion Tests — GELU, Tanh, Sigmoid, Conv2D, MaxPool2D
//! Tests for newly added algorithm implementations
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

// ============================================================================
// GELU Activation
// ============================================================================

pub const GELUConfig = struct {
    approximate: bool,
};

pub fn forward_gelu(input: []const f32, output: []f32, config: GELUConfig) void {
    const SQRT_2_OVER_PI: f32 = 0.7978845608;
    const GELU_CONST: f32 = 0.044715;

    if (config.approximate) {
        for (input, 0..) |x, i| {
            const x_cubed = x * x * x;
            const tanh_arg = SQRT_2_OVER_PI * (x + GELU_CONST * x_cubed);
            const tanh_val = std.math.tanh(tanh_arg);
            output[i] = 0.5 * x * (1.0 + tanh_val);
        }
    } else {
        // Exact computation not available - use approximation
        for (input, 0..) |x, i| {
            const x_cubed = x * x * x;
            const tanh_arg = SQRT_2_OVER_PI * (x + GELU_CONST * x_cubed);
            const tanh_val = std.math.tanh(tanh_arg);
            output[i] = 0.5 * x * (1.0 + tanh_val);
        }
    }
}

test "GELU approximate activation" {
    const input = [_]f32{ -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0 };
    var output: [7]f32 = undefined;

    const config = GELUConfig{ .approximate = true };
    forward_gelu(&input, &output, config);

    // GELU(0) should be 0 (x * Phi(x), Phi(0) = 0.5)
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.0), output[3], tolerance);

    // GELU is positive for positive inputs, negative for negative
    try std.testing.expect(output[0] < 0); // -2.0
    try std.testing.expect(output[1] < 0); // -1.0
    try std.testing.expect(output[2] < 0); // -0.5
    try std.testing.expect(output[4] > 0); // 0.5
    try std.testing.expect(output[5] > 0); // 1.0
    try std.testing.expect(output[6] > 0); // 2.0

    // GELU(x) should be close to x for large x
    try std.testing.expect(output[6] > 1.8); // GELU(2) ≈ 1.954

    std.debug.print("\n✓ GELU approximate test passed\n", .{});
    std.debug.print("  Output: {any}\n", .{output});
}

test "GELU consistency" {
    const input = [_]f32{ -2.0, -1.0, 0.0, 1.0, 2.0 };
    var output1: [5]f32 = undefined;
    var output2: [5]f32 = undefined;

    const config = GELUConfig{ .approximate = true };

    forward_gelu(&input, &output1, config);
    forward_gelu(&input, &output2, config);

    // Same config should produce same results
    const tolerance: f32 = 0.001;
    for (output1, output2) |o1, o2| {
        try std.testing.expectApproxEqRel(o1, o2, tolerance);
    }

    std.debug.print("\n✓ GELU consistency test passed\n", .{});
}

// ============================================================================
// Tanh Activation
// ============================================================================

pub fn forward_tanh(input: []const f32, output: []f32) void {
    for (input, 0..) |x, i| {
        output[i] = std.math.tanh(x);
    }
}

pub fn backward_tanh(grad_output: []const f32, output: []const f32, grad_input: []f32) void {
    for (grad_output, 0..) |g, i| {
        const tanh_x = output[i];
        grad_input[i] = g * (1.0 - tanh_x * tanh_x);
    }
}

test "Tanh activation" {
    const input = [_]f32{ -2.0, -1.0, 0.0, 1.0, 2.0 };
    var output: [5]f32 = undefined;

    forward_tanh(&input, &output);

    // tanh(0) = 0
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.0), output[2], tolerance);

    // tanh is bounded in (-1, 1)
    for (output) |o| {
        try std.testing.expect(o > -1.0 and o < 1.0);
    }

    // tanh is symmetric: tanh(-x) = -tanh(x)
    try std.testing.expectApproxEqRel(-output[0], output[4], tolerance); // tanh(-2) ≈ -tanh(2)
    try std.testing.expectApproxEqRel(-output[1], output[3], tolerance); // tanh(-1) ≈ -tanh(1)

    // tanh(1) ≈ 0.761594
    try std.testing.expectApproxEqRel(@as(f32, 0.761594), output[3], tolerance);

    std.debug.print("\n✓ Tanh activation test passed\n", .{});
    std.debug.print("  Output: {any}\n", .{output});
}

test "Tanh backward" {
    const input = [_]f32{ -1.0, 0.0, 1.0 };
    var output: [3]f32 = undefined;
    var grad_input: [3]f32 = undefined;
    const grad_output = [_]f32{ 1.0, 1.0, 1.0 };

    forward_tanh(&input, &output);
    backward_tanh(&grad_output, &output, &grad_input);

    // Derivative at 0 is 1
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 1.0), grad_input[1], tolerance);

    // Derivative at ±1 is less than 1
    try std.testing.expect(grad_input[0] > 0 and grad_input[0] < 1);
    try std.testing.expect(grad_input[2] > 0 and grad_input[2] < 1);

    std.debug.print("\n✓ Tanh backward test passed\n", .{});
}

// ============================================================================
// Sigmoid Activation
// ============================================================================

pub fn forward_sigmoid(input: []const f32, output: []f32) void {
    for (input, 0..) |x, i| {
        if (x >= 0) {
            const exp_neg_x = @exp(-x);
            output[i] = 1.0 / (1.0 + exp_neg_x);
        } else {
            const exp_x = @exp(x);
            output[i] = exp_x / (1.0 + exp_x);
        }
    }
}

pub fn backward_sigmoid(grad_output: []const f32, output: []const f32, grad_input: []f32) void {
    for (grad_output, 0..) |g, i| {
        const sigmoid_x = output[i];
        grad_input[i] = g * sigmoid_x * (1.0 - sigmoid_x);
    }
}

test "Sigmoid activation" {
    const input = [_]f32{ -5.0, -2.0, -1.0, 0.0, 1.0, 2.0, 5.0 };
    var output: [7]f32 = undefined;

    forward_sigmoid(&input, &output);

    // sigmoid(0) = 0.5
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.5), output[3], tolerance);

    // sigmoid is bounded in (0, 1)
    for (output) |o| {
        try std.testing.expect(o > 0.0 and o < 1.0);
    }

    // sigmoid(-inf) → 0, sigmoid(inf) → 1
    try std.testing.expect(output[0] < 0.01); // sigmoid(-5) ≈ 0.0067
    try std.testing.expect(output[6] > 0.99); // sigmoid(5) ≈ 0.9933

    // sigmoid(1) ≈ 0.7311
    try std.testing.expectApproxEqRel(@as(f32, 0.7311), output[4], 0.01);

    std.debug.print("\n✓ Sigmoid activation test passed\n", .{});
    std.debug.print("  Output: {any}\n", .{output});
}

test "Sigmoid backward" {
    const input = [_]f32{ -1.0, 0.0, 1.0 };
    var output: [3]f32 = undefined;
    var grad_input: [3]f32 = undefined;
    const grad_output = [_]f32{ 1.0, 1.0, 1.0 };

    forward_sigmoid(&input, &output);
    backward_sigmoid(&grad_output, &output, &grad_input);

    // Derivative at 0 is 0.25 (sigmoid(0) = 0.5, 0.5 * 0.5 = 0.25)
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.25), grad_input[1], tolerance);

    // Derivative is maximized at 0
    try std.testing.expect(grad_input[0] < grad_input[1]);
    try std.testing.expect(grad_input[2] < grad_input[1]);

    std.debug.print("\n✓ Sigmoid backward test passed\n", .{});
}

// ============================================================================
// Conv2D Layer
// ============================================================================

pub const Conv2DConfig = struct {
    in_channels: u32,
    out_channels: u32,
    kernel_size: u32,
    stride: u32,
    padding: u32,
    has_bias: bool,
};

pub fn forward_conv2d(input: []const f32, weights: []const f32, bias: []const f32, output: []f32, config: Conv2DConfig, batch_size: u32, in_h: u32, in_w: u32, out_h: u32, out_w: u32) void {
    const in_c = config.in_channels;
    const out_c = config.out_channels;
    const k = config.kernel_size;
    const s = config.stride;
    const p = config.padding;

    for (0..batch_size) |b| {
        for (0..out_c) |oc| {
            for (0..out_h) |oy| {
                for (0..out_w) |ox| {
                    var sum: f32 = if (config.has_bias) bias[oc] else 0;

                    for (0..in_c) |ic| {
                        for (0..k) |ky| {
                            for (0..k) |kx| {
                                const iy = @as(i32, @intCast(oy *% s +% ky)) -% @as(i32, @intCast(p));
                                const ix = @as(i32, @intCast(ox *% s +% kx)) -% @as(i32, @intCast(p));

                                if (iy >= 0 and iy < @as(i32, @intCast(in_h)) and
                                    ix >= 0 and ix < @as(i32, @intCast(in_w)))
                                {
                                    const iu = @as(usize, @intCast(iy));
                                    const iu2 = @as(usize, @intCast(ix));
                                    const in_idx = ((b * in_c + ic) * in_h + iu) * in_w + iu2;
                                    const w_idx = ((oc * in_c + ic) * k + ky) * k + kx;
                                    sum += input[in_idx] * weights[w_idx];
                                }
                            }
                        }
                    }

                    const out_idx = ((b * out_c + oc) * out_h + oy) * out_w + ox;
                    output[out_idx] = sum;
                }
            }
        }
    }
}

test "Conv2D 1x1 kernel" {
    // 1x1 conv is same as dense layer per spatial position
    const batch_size: u32 = 1;
    const in_c: u32 = 2;
    const out_c: u32 = 1;
    const k: u32 = 1;
    const s: u32 = 1;
    const p: u32 = 0;
    const in_h: u32 = 2;
    const in_w: u32 = 2;
    const out_h: u32 = 2;
    const out_w: u32 = 2;

    // Input: [1, 2, 2, 2] = 8 elements
    const input = [_]f32{
        // Batch 0, Channel 0
        1.0, 2.0,
        3.0, 4.0,
        // Batch 0, Channel 1
        5.0, 6.0,
        7.0, 8.0,
    };

    // Weights: [1, 2, 1, 1] = [out_c, in_c, k, k] = 2 elements
    const weights = [_]f32{
        // Out channel 0, In channel 0, kernel 1x1
        0.5,
        // Out channel 0, In channel 1, kernel 1x1
        0.3,
    };

    const bias = [_]f32{1.0};

    var output: [4]f32 = undefined;

    const config = Conv2DConfig{
        .in_channels = in_c,
        .out_channels = out_c,
        .kernel_size = k,
        .stride = s,
        .padding = p,
        .has_bias = true,
    };

    forward_conv2d(&input, &weights, &bias, &output, config, batch_size, in_h, in_w, out_h, out_w);

    // Expected: output = input * weight + bias
    // Position (0,0): 1.0*0.5 + 5.0*0.3 + 1.0 = 0.5 + 1.5 + 1.0 = 3.0
    // Position (0,1): 2.0*0.5 + 6.0*0.3 + 1.0 = 1.0 + 1.8 + 1.0 = 3.8
    // Position (1,0): 3.0*0.5 + 7.0*0.3 + 1.0 = 1.5 + 2.1 + 1.0 = 4.6
    // Position (1,1): 4.0*0.5 + 8.0*0.3 + 1.0 = 2.0 + 2.4 + 1.0 = 5.4
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 3.0), output[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 3.8), output[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 4.6), output[2], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 5.4), output[3], tolerance);

    std.debug.print("\n✓ Conv2D 1x1 kernel test passed\n", .{});
    std.debug.print("  Output: {any}\n", .{output});
}

test "Conv2D 3x3 kernel with padding" {
    const batch_size: u32 = 1;
    const in_c: u32 = 1;
    const out_c: u32 = 1;
    const k: u32 = 3;
    const s: u32 = 1;
    const p: u32 = 1;
    const in_h: u32 = 3;
    const in_w: u32 = 3;
    const out_h: u32 = 3;
    const out_w: u32 = 3;

    // Input: 3x3
    const input = [_]f32{
        1.0, 2.0, 3.0,
        4.0, 5.0, 6.0,
        7.0, 8.0, 9.0,
    };

    // 3x3 averaging kernel (all 1/9)
    var weights: [9]f32 = undefined;
    for (&weights) |*w| {
        w.* = 1.0 / 9.0;
    }

    const bias = [_]f32{0.0};

    var output: [9]f32 = undefined;

    const config = Conv2DConfig{
        .in_channels = in_c,
        .out_channels = out_c,
        .kernel_size = k,
        .stride = s,
        .padding = p,
        .has_bias = true,
    };

    forward_conv2d(&input, &weights, &bias, &output, config, batch_size, in_h, in_w, out_h, out_w);

    // Center position should be average of all input values = 5.0
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 5.0), output[4], tolerance);

    // Corner positions will have different averages due to padding
    try std.testing.expect(output[0] > 0 and output[0] < 5.0);

    std.debug.print("\n✓ Conv2D 3x3 kernel test passed\n", .{});
}

test "Conv2D stride 2" {
    const batch_size: u32 = 1;
    const in_c: u32 = 1;
    const out_c: u32 = 1;
    const k: u32 = 2;
    const s: u32 = 2;
    const p: u32 = 0;
    const in_h: u32 = 4;
    const in_w: u32 = 4;
    const out_h: u32 = 2;
    const out_w: u32 = 2;

    // Input: 4x4
    const input = [_]f32{
        1.0,  2.0,  3.0,  4.0,
        5.0,  6.0,  7.0,  8.0,
        9.0,  10.0, 11.0, 12.0,
        13.0, 14.0, 15.0, 16.0,
    };

    // 2x2 identity kernel
    const weights = [_]f32{
        1.0, 0.0,
        0.0, 0.0,
    };

    const bias = [_]f32{0.0};

    var output: [4]f32 = undefined;

    const config = Conv2DConfig{
        .in_channels = in_c,
        .out_channels = out_c,
        .kernel_size = k,
        .stride = s,
        .padding = p,
        .has_bias = true,
    };

    forward_conv2d(&input, &weights, &bias, &output, config, batch_size, in_h, in_w, out_h, out_w);

    // With stride 2 and identity kernel, output should pick top-left corners
    // Output[0,0] = input[0,0] = 1.0
    // Output[0,1] = input[0,2] = 3.0
    // Output[1,0] = input[2,0] = 9.0
    // Output[1,1] = input[2,2] = 11.0
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 1.0), output[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 3.0), output[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 9.0), output[2], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 11.0), output[3], tolerance);

    std.debug.print("\n✓ Conv2D stride 2 test passed\n", .{});
}

// ============================================================================
// MaxPool2D Layer
// ============================================================================

pub const MaxPool2DConfig = struct {
    kernel_size: u32,
    stride: u32,
    padding: u32,
};

pub fn forward_maxpool2d(input: []const f32, output: []f32, config: MaxPool2DConfig, batch_size: u32, channels: u32, in_h: u32, in_w: u32, out_h: u32, out_w: u32) void {
    const k = config.kernel_size;
    const s = config.stride;
    const p = config.padding;

    for (0..batch_size) |b| {
        for (0..channels) |c| {
            for (0..out_h) |oy| {
                for (0..out_w) |ox| {
                    var max_val: f32 = -std.math.inf(f32);

                    for (0..k) |ky| {
                        for (0..k) |kx| {
                            const iy = @as(i32, @intCast(oy *% s +% ky)) -% @as(i32, @intCast(p));
                            const ix = @as(i32, @intCast(ox *% s +% kx)) -% @as(i32, @intCast(p));

                            if (iy >= 0 and iy < @as(i32, @intCast(in_h)) and
                                ix >= 0 and ix < @as(i32, @intCast(in_w)))
                            {
                                const iu = @as(usize, @intCast(iy));
                                const iu2 = @as(usize, @intCast(ix));
                                const in_idx = ((b * channels + c) * in_h + iu) * in_w + iu2;
                                if (input[in_idx] > max_val) {
                                    max_val = input[in_idx];
                                }
                            }
                        }
                    }

                    const out_idx = ((b * channels + c) * out_h + oy) * out_w + ox;
                    output[out_idx] = max_val;
                }
            }
        }
    }
}

test "MaxPool2D 2x2" {
    const batch_size: u32 = 1;
    const channels: u32 = 1;
    const k: u32 = 2;
    const s: u32 = 2;
    const p: u32 = 0;
    const in_h: u32 = 4;
    const in_w: u32 = 4;
    const out_h: u32 = 2;
    const out_w: u32 = 2;

    // Input: 4x4
    const input = [_]f32{
        1.0,  2.0,  3.0,  4.0,
        5.0,  6.0,  7.0,  8.0,
        9.0,  10.0, 11.0, 12.0,
        13.0, 14.0, 15.0, 16.0,
    };

    var output: [4]f32 = undefined;

    const config = MaxPool2DConfig{
        .kernel_size = k,
        .stride = s,
        .padding = p,
    };

    forward_maxpool2d(&input, &output, config, batch_size, channels, in_h, in_w, out_h, out_w);

    // Expected: max of each 2x2 window
    // Top-left: max(1,2,5,6) = 6
    // Top-right: max(3,4,7,8) = 8
    // Bottom-left: max(9,10,13,14) = 14
    // Bottom-right: max(11,12,15,16) = 16
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 6.0), output[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 8.0), output[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 14.0), output[2], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 16.0), output[3], tolerance);

    std.debug.print("\n✓ MaxPool2D 2x2 test passed\n", .{});
    std.debug.print("  Output: {any}\n", .{output});
}

test "MaxPool2D with padding" {
    const batch_size: u32 = 1;
    const channels: u32 = 1;
    const k: u32 = 3;
    const s: u32 = 1;
    const p: u32 = 1;
    const in_h: u32 = 3;
    const in_w: u32 = 3;
    const out_h: u32 = 3;
    const out_w: u32 = 3;

    // Input: 3x3
    const input = [_]f32{
        1.0, 2.0, 3.0,
        4.0, 5.0, 6.0,
        7.0, 8.0, 9.0,
    };

    var output: [9]f32 = undefined;

    const config = MaxPool2DConfig{
        .kernel_size = k,
        .stride = s,
        .padding = p,
    };

    forward_maxpool2d(&input, &output, config, batch_size, channels, in_h, in_w, out_h, out_w);

    // Center should still be 9 (max of center position)
    // Edge positions affected by padding (which adds 0s)
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 9.0), output[4], tolerance);

    std.debug.print("\n✓ MaxPool2D padding test passed\n", .{});
}

test "MaxPool2D preserves maximum" {
    const batch_size: u32 = 1;
    const channels: u32 = 1;
    const k: u32 = 2;
    const s: u32 = 2;
    const p: u32 = 0;
    const in_h: u32 = 2;
    const in_w: u32 = 2;
    const out_h: u32 = 1;
    const out_w: u32 = 1;

    const input = [_]f32{ 100.0, -50.0, -25.0, 75.0 };
    var output: [1]f32 = undefined;

    const config = MaxPool2DConfig{
        .kernel_size = k,
        .stride = s,
        .padding = p,
    };

    forward_maxpool2d(&input, &output, config, batch_size, channels, in_h, in_w, out_h, out_w);

    // Max of [100, -50, -25, 75] is 100
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 100.0), output[0], tolerance);

    std.debug.print("\n✓ MaxPool2D preserves max test passed\n", .{});
}

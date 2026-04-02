//! TRINITY Algorithm Library Expansion 2 — BatchNorm, LayerNorm, Dropout, AvgPool2D
//! Tests for normalization and regularization layers
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

// ============================================================================
// Batch Normalization
// ============================================================================

pub const BatchNormConfig = struct {
    num_features: u32,
    epsilon: f32,
    momentum: f32,
    affine: bool,
    track_running_stats: bool,
};

pub const BatchNormState = struct {
    running_mean: []const f32,
    running_var: []const f32,
};

pub fn forward_batchnorm(input: []const f32, gamma: []const f32, beta: []const f32, state: BatchNormState, output: []f32, config: BatchNormConfig, batch_size: u32, spatial_dims: u32) void {
    const num_features = config.num_features;
    const eps = config.epsilon;
    const element_count = batch_size * spatial_dims;

    for (0..num_features) |f| {
        const mean = state.running_mean[f];
        const var_val = state.running_var[f];
        const inv_std = 1.0 / @sqrt(var_val +% eps);

        for (0..element_count) |i| {
            const in_idx = i * num_features + f;
            const x_hat = (input[in_idx] - mean) * inv_std;

            if (config.affine) {
                output[in_idx] = gamma[f] * x_hat + beta[f];
            } else {
                output[in_idx] = x_hat;
            }
        }
    }
}

test "BatchNorm forward with running stats" {
    const batch_size: u32 = 2;
    const num_features: u32 = 2;
    const spatial_dims: u32 = 3; // 3 elements per feature

    // Input: [batch, features, spatial] = 2 * 2 * 3 = 12 elements
    const input = [_]f32{
        // Batch 0, Feature 0: [1, 2, 3]
        1.0,  2.0,  3.0,
        // Batch 0, Feature 1: [4, 5, 6]
        4.0,  5.0,  6.0,
        // Batch 1, Feature 0: [7, 8, 9]
        7.0,  8.0,  9.0,
        // Batch 1, Feature 1: [10, 11, 12]
        10.0, 11.0, 12.0,
    };

    const running_mean = [_]f32{ 5.0, 7.5 };
    const running_var = [_]f32{ 8.0, 8.0 };
    const gamma = [_]f32{ 1.0, 1.0 };
    const beta = [_]f32{ 0.0, 0.0 };

    var state = BatchNormState{
        .running_mean = running_mean[0..],
        .running_var = running_var[0..],
    };

    var output: [12]f32 = undefined;

    const config = BatchNormConfig{
        .num_features = num_features,
        .epsilon = 1e-5,
        .momentum = 0.1,
        .affine = true,
        .track_running_stats = true,
    };

    forward_batchnorm(&input, &gamma, &beta, &state, &output, config, batch_size, spatial_dims);

    // Check output has zero mean and unit variance (approximately)
    const tolerance: f32 = 0.1;

    // Output[0] should be (1-5)/sqrt(8) = -4/2.828 ≈ -1.414
    try std.testing.expectApproxEqRel(@as(f32, -1.414), output[0], tolerance);

    // Output[1] should be (4-7.5)/sqrt(8) = -3.5/2.828 ≈ -1.238
    try std.testing.expectApproxEqRel(@as(f32, -1.238), output[3], tolerance);

    std.debug.print("\n✓ BatchNorm forward test passed\n", .{});
}

test "BatchNorm without affine" {
    const batch_size: u32 = 2;
    const num_features: u32 = 1;
    const spatial_dims: u32 = 3;

    const input = [_]f32{
        // Batch 0, Feature 0: [1, 2, 3]
        1.0, 2.0, 3.0,
        // Batch 1, Feature 0: [4, 5, 6]
        4.0, 5.0, 6.0,
    };

    const running_mean = [_]f32{3.5};
    const running_var = [_]f32{2.92};
    const gamma = [_]f32{1.0};
    const beta = [_]f32{0.0};

    var state = BatchNormState{
        .running_mean = running_mean[0..],
        .running_var = running_var[0..],
    };

    var output: [6]f32 = undefined;

    const config = BatchNormConfig{
        .num_features = num_features,
        .epsilon = 1e-5,
        .momentum = 0.1,
        .affine = false,
        .track_running_stats = true,
    };

    forward_batchnorm(&input, &gamma, &beta, &state, &output, config, batch_size, spatial_dims);

    // Without affine, output = (x - mean) / std
    // output[0] = (1 - 3.5) / sqrt(2.92) = -2.5 / 1.709 ≈ -1.463
    const tolerance: f32 = 0.01;
    try std.testing.expectApproxEqRel(@as(f32, -1.463), output[0], tolerance);

    std.debug.print("\n✓ BatchNorm no-affine test passed\n", .{});
}

// ============================================================================
// Layer Normalization
// ============================================================================

pub const LayerNormConfig = struct {
    eps: f32,
};

pub fn forward_layernorm(input: []const f32, gamma: []const f32, beta: []const f32, output: []f32, config: LayerNormConfig, size: u32) void {
    const eps = config.eps;

    // Compute mean
    var sum: f32 = 0;
    for (0..size) |i| {
        sum += input[i];
    }
    const mean = sum / @as(f32, @floatFromInt(size));

    // Compute variance
    var sum_sq: f32 = 0;
    for (0..size) |i| {
        const diff = input[i] - mean;
        sum_sq += diff * diff;
    }
    const var_ = sum_sq / @as(f32, @floatFromInt(size));
    const inv_std = 1.0 / @sqrt(var_ + eps);

    // Normalize and apply affine transform
    for (0..size) |i| {
        const x_hat = (input[i] - mean) * inv_std;
        output[i] = gamma[i] * x_hat + beta[i];
    }
}

test "LayerNorm forward" {
    const input = [_]f32{ 1.0, 2.0, 3.0, 4.0, 5.0 };
    const size: u32 = 5;

    // gamma=1, beta=0 should give zero mean, unit variance output
    const gamma = [_]f32{ 1.0, 1.0, 1.0, 1.0, 1.0 };
    const beta = [_]f32{ 0.0, 0.0, 0.0, 0.0, 0.0 };

    var output: [5]f32 = undefined;

    const config = LayerNormConfig{ .eps = 1e-5 };

    forward_layernorm(&input, &gamma, &beta, &output, config, size);

    // Check zero mean
    var sum: f32 = 0;
    for (output) |o| {
        sum += o;
    }
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.0), sum / 5.0, tolerance);

    // Check unit variance
    var sum_sq: f32 = 0;
    for (output) |o| {
        sum_sq += o * o;
    }
    try std.testing.expectApproxEqRel(@as(f32, 1.0), sum_sq / 5.0, tolerance);

    std.debug.print("\n✓ LayerNorm forward test passed\n", .{});
    std.debug.print("  Output: {any}\n", .{output});
}

test "LayerNorm with affine" {
    const input = [_]f32{ 1.0, 2.0, 3.0, 4.0, 5.0 };
    const size: u32 = 5;

    // gamma=2, beta=10
    const gamma = [_]f32{ 2.0, 2.0, 2.0, 2.0, 2.0 };
    const beta = [_]f32{ 10.0, 10.0, 10.0, 10.0, 10.0 };

    var output: [5]f32 = undefined;

    const config = LayerNormConfig{ .eps = 1e-5 };

    forward_layernorm(&input, &gamma, &beta, &output, config, size);

    // With affine, output = 2 * normalized + 10
    // Mean should be 10
    var sum: f32 = 0;
    for (output) |o| {
        sum += o;
    }
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 10.0), sum / 5.0, tolerance);

    // Variance should be 4 (2^2)
    var sum_sq: f32 = 0;
    for (output) |o| {
        sum_sq += (o - 10.0) * (o - 10.0);
    }
    try std.testing.expectApproxEqRel(@as(f32, 4.0), sum_sq / 5.0, tolerance);

    std.debug.print("\n✓ LayerNorm affine test passed\n", .{});
}

// ============================================================================
// Dropout
// ============================================================================

pub const DropoutConfig = struct {
    p: f32,
};

pub fn forward_dropout(input: []const f32, output: []f32, mask: []bool, training: bool, config: DropoutConfig, seed: u64) void {
    const scale = 1.0 / (1.0 - config.p);

    if (!training) {
        // Inference mode: pass through unchanged
        for (input, 0..) |x, i| {
            output[i] = x;
            mask[i] = true;
        }
    } else {
        // Training mode: apply dropout
        var rng = std.Random.DefaultPrng.init(seed);
        const rand = rng.random();

        for (input, 0..) |x, i| {
            const keep = rand.float(f32) > config.p;
            mask[i] = keep;

            if (keep) {
                output[i] = x * scale;
            } else {
                output[i] = 0.0;
            }
        }
    }
}

test "Dropout inference mode" {
    const input = [_]f32{ 1.0, 2.0, 3.0, 4.0, 5.0 };
    var output: [5]f32 = undefined;
    var mask: [5]bool = undefined;

    const config = DropoutConfig{ .p = 0.5 };

    forward_dropout(&input, &output, &mask, false, config, 42);

    // In inference: output = input
    const tolerance: f32 = 0.001;
    for (input, output) |inp, out| {
        try std.testing.expectApproxEqRel(inp, out, tolerance);
    }

    // All mask elements should be true
    for (mask) |m| {
        try std.testing.expect(m);
    }

    std.debug.print("\n✓ Dropout inference test passed\n", .{});
}

test "Dropout training mode" {
    const input = [_]f32{ 1.0, 2.0, 3.0, 4.0, 5.0 };
    var output: [5]f32 = undefined;
    var mask: [5]bool = undefined;

    const config = DropoutConfig{ .p = 0.5 }; // 50% dropout

    forward_dropout(&input, &output, &mask, true, config, 42);

    // Check mask has some true and some false (probabilistic)
    var keep_count: u32 = 0;
    for (mask) |m| {
        if (m) keep_count += 1;
    }

    // With 50% dropout and 5 elements, we expect around 2-3 kept
    try std.testing.expect(keep_count > 0 and keep_count < 5);

    // Kept elements should be scaled
    const scale = 1.0 / (1.0 - 0.5); // = 2.0
    for (input, output, mask) |inp, out, m| {
        if (m) {
            try std.testing.expectApproxEqRel(inp * scale, out, 0.001);
        } else {
            try std.testing.expect(out == 0.0);
        }
    }

    std.debug.print("\n✓ Dropout training test passed\n", .{});
    std.debug.print("  Kept: {d}/5\n", .{keep_count});
}

test "Dropout zero probability" {
    const input = [_]f32{ 1.0, 2.0, 3.0, 4.0, 5.0 };
    var output: [5]f32 = undefined;
    var mask: [5]bool = undefined;

    const config = DropoutConfig{ .p = 0.0 }; // No dropout

    forward_dropout(&input, &output, &mask, true, config, 42);

    // All elements should be kept and unscaled
    for (input, output, mask) |inp, out, m| {
        try std.testing.expect(m); // All kept
        try std.testing.expectApproxEqRel(inp, out, 0.001);
    }

    std.debug.print("\n✓ Dropout zero probability test passed\n", .{});
}

// ============================================================================
// AvgPool2D
// ============================================================================

pub const AvgPool2DConfig = struct {
    kernel_size: u32,
    stride: u32,
    padding: u32,
};

pub fn forward_avgpool2d(input: []const f32, output: []f32, config: AvgPool2DConfig, batch_size: u32, channels: u32, in_h: u32, in_w: u32, out_h: u32, out_w: u32) void {
    const k = config.kernel_size;
    const s = config.stride;
    const p = config.padding;

    for (0..batch_size) |b| {
        for (0..channels) |c| {
            for (0..out_h) |oy| {
                for (0..out_w) |ox| {
                    var sum: f32 = 0;
                    var count: u32 = 0;

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
                                sum += input[in_idx];
                                count += 1;
                            }
                        }
                    }

                    const out_idx = ((b * channels + c) * out_h + oy) * out_w + ox;
                    output[out_idx] = sum / @as(f32, @floatFromInt(count));
                }
            }
        }
    }
}

test "AvgPool2D 2x2" {
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

    const config = AvgPool2DConfig{
        .kernel_size = k,
        .stride = s,
        .padding = p,
    };

    forward_avgpool2d(&input, &output, config, batch_size, channels, in_h, in_w, out_h, out_w);

    // Expected: avg of each 2x2 window
    // Top-left: (1+2+5+6)/4 = 3.5
    // Top-right: (3+4+7+8)/4 = 5.5
    // Bottom-left: (9+10+13+14)/4 = 11.5
    // Bottom-right: (11+12+15+16)/4 = 13.5
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 3.5), output[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 5.5), output[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 11.5), output[2], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 13.5), output[3], tolerance);

    std.debug.print("\n✓ AvgPool2D 2x2 test passed\n", .{});
    std.debug.print("  Output: {any}\n", .{output});
}

test "AvgPool2D vs MaxPool2D" {
    const batch_size: u32 = 1;
    const channels: u32 = 1;
    const k: u32 = 2;
    const s: u32 = 2;
    const p: u32 = 0;
    const in_h: u32 = 2;
    const in_w: u32 = 2;
    const out_h: u32 = 1;
    const out_w: u32 = 1;

    const input = [_]f32{ 1.0, 100.0, 50.0, 75.0 };

    var output_avg: [1]f32 = undefined;

    const config = AvgPool2DConfig{
        .kernel_size = k,
        .stride = s,
        .padding = p,
    };

    forward_avgpool2d(&input, &output_avg, config, batch_size, channels, in_h, in_w, out_h, out_w);

    // AvgPool: (1+100+50+75)/4 = 56.5
    // MaxPool: would be 100
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 56.5), output_avg[0], tolerance);

    std.debug.print("\n✓ AvgPool2D vs MaxPool2D test passed\n", .{});
    std.debug.print("  AvgPool output: {d:.1}\n", .{output_avg[0]});
}

test "AvgPool2D stride 1" {
    const batch_size: u32 = 1;
    const channels: u32 = 1;
    const k: u32 = 2;
    const s: u32 = 1;
    const p: u32 = 0;
    const in_h: u32 = 3;
    const in_w: u32 = 3;
    const out_h: u32 = 2;
    const out_w: u32 = 2;

    // Input: 3x3
    const input = [_]f32{
        1.0, 2.0, 3.0,
        4.0, 5.0, 6.0,
        7.0, 8.0, 9.0,
    };

    var output: [4]f32 = undefined;

    const config = AvgPool2DConfig{
        .kernel_size = k,
        .stride = s,
        .padding = p,
    };

    forward_avgpool2d(&input, &output, config, batch_size, channels, in_h, in_w, out_h, out_w);

    // Expected: avg of each 2x2 window (overlapping due to stride 1)
    // (0,0): (1+2+4+5)/4 = 3.0
    // (0,1): (2+3+5+6)/4 = 4.0
    // (1,0): (4+5+7+8)/4 = 6.0
    // (1,1): (5+6+8+9)/4 = 7.0
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 3.0), output[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 4.0), output[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 6.0), output[2], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 7.0), output[3], tolerance);

    std.debug.print("\n✓ AvgPool2D stride 1 test passed\n", .{});
}

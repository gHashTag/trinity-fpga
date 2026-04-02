//! VIBEE Codegen Phase 2 — Integration Tests
//! Tests Dense + ReLU + Softmax → MLP
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

// Import generated types (would come from .tri specs)
pub const ActivationType = enum {
    None,
    ReLU,
    GELU,
    Sigmoid,
    Tanh,
    Softmax,
};

pub const DenseConfig = struct {
    input_size: u32,
    output_size: u32,
    has_bias: bool,
    activation: ActivationType,
};

pub const ReLUConfig = struct {
    negative_slope: f32,
    inplace: bool,
};

pub const SoftmaxConfig = struct {
    temperature: f32,
    axis: u32,
    stable: bool,
};

// Generated implementations
pub fn forward_dense(input: []const f32, weights: []const f32, bias: []const f32, output: []f32, config: DenseConfig) void {
    const input_size = config.input_size;
    const output_size = config.output_size;

    for (0..output_size) |output_j| {
        var sum: f32 = if (config.has_bias) bias[output_j] else 0;

        for (0..input_size) |input_i| {
            const weight_idx = input_i * output_size + output_j;
            sum += input[input_i] * weights[weight_idx];
        }

        output[output_j] = sum;
    }
}

pub fn forward_relu(input: []const f32, output: []f32, config: ReLUConfig) void {
    const ZERO: f32 = 0;
    const alpha: f32 = config.negative_slope;

    for (input, 0..) |x, i| {
        if (alpha == 0) {
            output[i] = if (x > ZERO) x else ZERO;
        } else {
            output[i] = if (x > ZERO) x else x * alpha;
        }
    }
}

pub fn forward_softmax(logits: []const f32, output: []f32, config: SoftmaxConfig) void {
    const n = logits.len;
    if (n == 0) return;

    // Find max for numerical stability
    var max_val: f32 = logits[0];
    for (logits[1..]) |logit| {
        if (logit > max_val) max_val = logit;
    }

    const temp = config.temperature;
    var exp_sum: f32 = 0;

    // Compute exp(x - max) / temp and sum
    for (logits, 0..) |logit, i| {
        const shifted = if (config.stable) logit - max_val else logit;
        const exp_val = @exp(shifted / temp);
        output[i] = exp_val;
        exp_sum += exp_val;
    }

    // Normalize
    const inv_sum = 1.0 / exp_sum;
    for (output) |*out| {
        out.* *= inv_sum;
    }
}

// Simple MLP: Input(4) → Dense(8) → ReLU → Dense(3) → Softmax
pub const MLPConfig = struct {
    input_size: u32,
    hidden_size: u32,
    output_size: u32,
};

pub fn MLP(comptime config: MLPConfig) type {
    return struct {
        // Layer 1 weights: input_size × hidden_size
        layer1_weights: [config.input_size * config.hidden_size]f32,
        layer1_bias: [config.hidden_size]f32,
        layer1_output: [config.hidden_size]f32,
        layer1_activated: [config.hidden_size]f32,

        // Layer 2 weights: hidden_size × output_size
        layer2_weights: [config.hidden_size * config.output_size]f32,
        layer2_bias: [config.output_size]f32,
        layer2_output: [config.output_size]f32,
        final_output: [config.output_size]f32,

        dense1_config: DenseConfig,
        relu_config: ReLUConfig,
        dense2_config: DenseConfig,
        softmax_config: SoftmaxConfig,

        const Self = @This();

        pub fn init() Self {
            var self: Self = undefined;

            // Initialize configs
            self.dense1_config = DenseConfig{
                .input_size = config.input_size,
                .output_size = config.hidden_size,
                .has_bias = true,
                .activation = .ReLU,
            };

            self.relu_config = ReLUConfig{
                .negative_slope = 0.0, // Standard ReLU
                .inplace = false,
            };

            self.dense2_config = DenseConfig{
                .input_size = config.hidden_size,
                .output_size = config.output_size,
                .has_bias = true,
                .activation = .None, // Softmax applied separately
            };

            self.softmax_config = SoftmaxConfig{
                .temperature = 1.0,
                .axis = 0,
                .stable = true,
            };

            // Initialize with small random weights
            var rng = std.Random.DefaultPrng.init(42);
            const rand = rng.random();

            for (&self.layer1_weights) |*w| {
                w.* = (rand.float(f32) - 0.5) * 0.1;
            }
            for (&self.layer1_bias) |*b| {
                b.* = 0.0;
            }
            for (&self.layer2_weights) |*w| {
                w.* = (rand.float(f32) - 0.5) * 0.1;
            }
            for (&self.layer2_bias) |*b| {
                b.* = 0.0;
            }

            return self;
        }

        pub fn forward(self: *Self, input: []const f32) []f32 {
            // Layer 1: Dense
            forward_dense(input, &self.layer1_weights, &self.layer1_bias, &self.layer1_output, self.dense1_config);

            // Layer 1: ReLU
            forward_relu(&self.layer1_output, &self.layer1_activated, self.relu_config);

            // Layer 2: Dense
            forward_dense(&self.layer1_activated, &self.layer2_weights, &self.layer2_bias, &self.layer2_output, self.dense2_config);

            // Output: Softmax
            forward_softmax(&self.layer2_output, &self.final_output, self.softmax_config);

            return &self.final_output;
        }
    };
}

test "MLP integration: Dense + ReLU + Softmax" {
    const config = MLPConfig{
        .input_size = 4,
        .hidden_size = 8,
        .output_size = 3,
    };

    var mlp = MLP(config).init();

    // Test input
    const input = [_]f32{ 0.1, 0.2, 0.3, 0.4 };
    const output = mlp.forward(&input);

    // Check output shape
    try std.testing.expectEqual(@as(usize, 3), output.len);

    // Check output is a valid probability distribution (sum ≈ 1.0)
    var sum: f32 = 0;
    for (output) |o| {
        try std.testing.expect(o > 0); // All probabilities positive
        try std.testing.expect(o < 1); // All probabilities < 1
        sum += o;
    }

    // Sum should be approximately 1.0
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 1.0), sum, tolerance);

    std.debug.print("\n✓ MLP integration test passed\n", .{});
    std.debug.print("  Input: {any}\n", .{input});
    std.debug.print("  Output (probabilities): {any}\n", .{output});
    std.debug.print("  Sum: {d:.6}\n", .{sum});
}

test "Dense layer standalone" {
    const config = DenseConfig{
        .input_size = 2,
        .output_size = 3,
        .has_bias = true,
        .activation = .None,
    };

    const weights = [_]f32{ 0.1, 0.2, 0.3, 0.4, 0.5, 0.6 };
    const bias = [_]f32{ 0.1, 0.2, 0.3 };
    const input = [_]f32{ 1.0, 2.0 };
    var output: [3]f32 = undefined;

    forward_dense(&input, &weights, &bias, &output, config);

    // Expected: [0.1*1 + 0.4*2 + 0.1, 0.2*1 + 0.5*2 + 0.2, 0.3*1 + 0.6*2 + 0.3]
    //           = [0.1 + 0.8 + 0.1, 0.2 + 1.0 + 0.2, 0.3 + 1.2 + 0.3]
    //           = [1.0, 1.4, 1.8]
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 1.0), output[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 1.4), output[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 1.8), output[2], tolerance);

    std.debug.print("\n✓ Dense layer test passed\n", .{});
}

test "ReLU activation standalone" {
    const config = ReLUConfig{
        .negative_slope = 0.0,
        .inplace = false,
    };

    const input = [_]f32{ -1.0, 0.0, 1.0, 2.0 };
    var output: [4]f32 = undefined;

    forward_relu(&input, &output, config);

    try std.testing.expectEqual(@as(f32, 0.0), output[0]);
    try std.testing.expectEqual(@as(f32, 0.0), output[1]);
    try std.testing.expectEqual(@as(f32, 1.0), output[2]);
    try std.testing.expectEqual(@as(f32, 2.0), output[3]);

    std.debug.print("\n✓ ReLU activation test passed\n", .{});
}

test "Softmax standalone" {
    const config = SoftmaxConfig{
        .temperature = 1.0,
        .axis = 0,
        .stable = true,
    };

    const logits = [_]f32{ 1.0, 2.0, 3.0 };
    var output: [3]f32 = undefined;

    forward_softmax(&logits, &output, config);

    // Check probabilities sum to 1
    var sum: f32 = 0;
    for (output) |o| {
        try std.testing.expect(o > 0);
        sum += o;
    }

    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 1.0), sum, tolerance);

    // Largest logit should get largest probability
    try std.testing.expect(output[2] > output[1]);
    try std.testing.expect(output[1] > output[0]);

    std.debug.print("\n✓ Softmax test passed\n", .{});
}

test "Leaky ReLU" {
    const config = ReLUConfig{
        .negative_slope = 0.01,
        .inplace = false,
    };

    const input = [_]f32{ -10.0, -1.0, 0.0, 1.0, 10.0 };
    var output: [5]f32 = undefined;

    forward_relu(&input, &output, config);

    try std.testing.expectApproxEqRel(@as(f32, -0.1), output[0], 0.001);
    try std.testing.expectApproxEqRel(@as(f32, -0.01), output[1], 0.001);
    try std.testing.expectEqual(@as(f32, 0.0), output[2]);
    try std.testing.expectEqual(@as(f32, 1.0), output[3]);
    try std.testing.expectEqual(@as(f32, 10.0), output[4]);

    std.debug.print("\n✓ Leaky ReLU test passed\n", .{});
}

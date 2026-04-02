// @origin(spec:vibee_codegen_tests.tri) @regen(manual-impl)
// ═══════════════════════════════════════════════════════════════════════════════
// VIBEE CODEGEN TESTS — Phase 1, 2, 3
// ═══════════════════════════════════════════════════════════════════════════════
//
// Tests the VIBEE codegen pipeline:
// - Phase 1: Extract types and implementations from .tri specs
// - Phase 2: Integration tests (Dense+ReLU+Softmax → MLP)
// - Phase 3: Build verification and semantic equivalence
//
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");

// ============================================================================
// TYPES (from .tri specs)
// ============================================================================

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

pub const SGDConfig = struct {
    learning_rate: f32,
    momentum: f32,
    weight_decay: f32,
    dampening: f32,
    nesterov: bool,
};

pub const SGDState = struct {
    velocity: []f32,
};

pub const MSELossConfig = struct {
    reduction: []const u8,
};

// ============================================================================
// IMPLEMENTATIONS (from .tri specs)
// ============================================================================

// Dense layer
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

// ReLU activation
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

pub fn backward_relu(grad_output: []const f32, input: []const f32, grad_input: []f32, config: ReLUConfig) void {
    const ZERO: f32 = 0;
    const alpha: f32 = config.negative_slope;

    for (grad_output, 0..) |g, i| {
        if (alpha == 0) {
            grad_input[i] = if (input[i] > ZERO) g else ZERO;
        } else {
            grad_input[i] = if (input[i] > ZERO) g else g * alpha;
        }
    }
}

// Softmax
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

pub fn backward_softmax(grad_output: []const f32, probabilities: []const f32, grad_input: []f32, _: SoftmaxConfig) void {
    // Compute dot product: sum(p * g)
    var dot_product: f32 = 0;
    for (probabilities, 0..) |p, i| {
        dot_product += p * grad_output[i];
    }

    // grad_input = p * (g - dot_product)
    for (probabilities, 0..) |p, i| {
        grad_input[i] = p * (grad_output[i] - dot_product);
    }
}

// MSE Loss
pub fn forward_mse_loss(predictions: []const f32, targets: []const f32) f32 {
    const n = predictions.len;
    if (n == 0) return 0;

    var sum_loss: f32 = 0;
    for (predictions, 0..) |pred, i| {
        const diff = pred - targets[i];
        sum_loss += diff * diff;
    }

    return sum_loss / @as(f32, @floatFromInt(n));
}

pub fn backward_mse_loss(predictions: []const f32, targets: []const f32, grad_input: []f32) void {
    const n = predictions.len;
    if (n == 0) return;

    const scale = 2.0 / @as(f32, @floatFromInt(n));
    for (predictions, 0..) |pred, i| {
        grad_input[i] = scale * (pred - targets[i]);
    }
}

// SGD optimizer
pub fn init_sgd(state: SGDState, _: u32, config: SGDConfig) void {
    if (config.momentum > 0) {
        @memset(state.velocity, 0);
    }
}

pub fn update_sgd(params: []f32, grads: []const f32, state: SGDState, config: SGDConfig) void {
    const lr = config.learning_rate;
    const momentum = config.momentum;
    const wd = config.weight_decay;

    if (momentum > 0 and state.velocity.len > 0) {
        // Momentum or Nesterov
        const n = @min(params.len, state.velocity.len);
        for (0..n) |i| {
            const d_p = grads[i] + wd * params[i];
            const p = &params[i];
            const vel = &state.velocity[i];

            if (config.nesterov) {
                // Nesterov: look-ahead position
                p.* += momentum * vel.*;
                vel.* = momentum * vel.* - lr * d_p;
                p.* += vel.*;
            } else {
                // Standard momentum
                vel.* = momentum * vel.* - lr * d_p;
                p.* += vel.*;
            }
        }
    } else {
        // Plain SGD
        const n = params.len;
        for (0..n) |i| {
            const d_p = grads[i] + wd * params[i];
            params[i] -= lr * d_p;
        }
    }
}

// ============================================================================
// SEMANTIC EQUIVALENCE TESTS
// ============================================================================

// Reference implementations (simple, readable versions)
const ReferenceImpl = struct {
    pub fn mse_loss_ref(predictions: []const f32, targets: []const f32) f32 {
        var sum: f32 = 0;
        for (predictions, targets) |p, t| {
            const diff = p - t;
            sum += diff * diff;
        }
        return sum / @as(f32, @floatFromInt(predictions.len));
    }

    pub fn softmax_ref(logits: []const f32, output: []f32) void {
        // Numerically stable softmax
        var max_val: f32 = logits[0];
        for (logits) |l| {
            if (l > max_val) max_val = l;
        }

        var sum: f32 = 0;
        for (logits, 0..) |l, i| {
            const exp_val = @exp(l - max_val);
            output[i] = exp_val;
            sum += exp_val;
        }

        for (output) |*o| {
            o.* /= sum;
        }
    }

    pub fn dense_forward_ref(input: []const f32, weights: []const f32, bias: []const f32, output: []f32, output_size: u32) void {
        for (0..output_size) |j| {
            var sum: f32 = bias[j];
            for (input, 0..) |x, i| {
                sum += x * weights[i * output_size + j];
            }
            output[j] = sum;
        }
    }

    pub fn relu_ref(input: []const f32, output: []f32) void {
        for (input, 0..) |x, i| {
            output[i] = if (x > 0) x else 0;
        }
    }

    pub fn sgd_update_ref(params: []f32, grads: []const f32, lr: f32) void {
        for (params, grads) |*p, g| {
            p.* -= lr * g;
        }
    }
};

test "Semantic equivalence: MSE loss" {
    const predictions = [_]f32{ 1.0, 2.0, 3.0, 4.0, 5.0 };
    const targets = [_]f32{ 1.1, 2.2, 2.9, 4.1, 4.8 };

    // Generated implementation
    const gen_loss = forward_mse_loss(&predictions, &targets);

    // Reference implementation
    const ref_loss = ReferenceImpl.mse_loss_ref(&predictions, &targets);

    // Should be exactly equal (same algorithm)
    try std.testing.expectEqual(ref_loss, gen_loss);

    std.debug.print("\n✓ MSE loss semantic equivalence verified\n", .{});
}

test "Semantic equivalence: Softmax" {
    const logits = [_]f32{ 1.0, 2.0, 3.0, 4.0 };
    var gen_output: [4]f32 = undefined;
    var ref_output: [4]f32 = undefined;

    // Generated implementation
    const config = SoftmaxConfig{
        .temperature = 1.0,
        .axis = 0,
        .stable = true,
    };
    forward_softmax(&logits, &gen_output, config);

    // Reference implementation
    ReferenceImpl.softmax_ref(&logits, &ref_output);

    // Check element-wise equality
    const tolerance: f32 = 0.000001;
    for (gen_output, ref_output) |g, r| {
        try std.testing.expectApproxEqRel(r, g, tolerance);
    }

    std.debug.print("\n✓ Softmax semantic equivalence verified\n", .{});
}

test "Semantic equivalence: Dense layer" {
    const input = [_]f32{ 1.0, 2.0 };
    const weights = [_]f32{ 0.1, 0.2, 0.3, 0.4 };
    const bias = [_]f32{ 0.5, 0.6 };
    const output_size: u32 = 2;

    var gen_output: [2]f32 = undefined;
    var ref_output: [2]f32 = undefined;

    // Generated implementation
    const config = DenseConfig{
        .input_size = 2,
        .output_size = 2,
        .has_bias = true,
        .activation = .None,
    };
    forward_dense(&input, &weights, &bias, &gen_output, config);

    // Reference implementation
    ReferenceImpl.dense_forward_ref(&input, &weights, &bias, &ref_output, output_size);

    // Check element-wise equality
    const tolerance: f32 = 0.000001;
    for (gen_output, ref_output) |g, r| {
        try std.testing.expectApproxEqRel(r, g, tolerance);
    }

    std.debug.print("\n✓ Dense layer semantic equivalence verified\n", .{});
}

test "Semantic equivalence: ReLU" {
    const input = [_]f32{ -2.0, -1.0, 0.0, 1.0, 2.0 };
    var gen_output: [5]f32 = undefined;
    var ref_output: [5]f32 = undefined;

    // Generated implementation
    const config = ReLUConfig{
        .negative_slope = 0.0,
        .inplace = false,
    };
    forward_relu(&input, &gen_output, config);

    // Reference implementation
    ReferenceImpl.relu_ref(&input, &ref_output);

    // Check element-wise equality
    for (gen_output, ref_output) |g, r| {
        try std.testing.expectEqual(r, g);
    }

    std.debug.print("\n✓ ReLU semantic equivalence verified\n", .{});
}

test "Semantic equivalence: SGD update" {
    const initial_params = [_]f32{ 1.0, 2.0, 3.0 };
    const grads = [_]f32{ 0.1, 0.2, 0.3 };
    const lr: f32 = 0.01;

    var gen_params: [3]f32 = initial_params;
    var ref_params: [3]f32 = initial_params;

    // Generated implementation
    var velocity: [3]f32 = undefined;
    const state = SGDState{ .velocity = &velocity };
    const config = SGDConfig{
        .learning_rate = lr,
        .momentum = 0.0,
        .weight_decay = 0.0,
        .dampening = 0.0,
        .nesterov = false,
    };
    update_sgd(&gen_params, &grads, state, config);

    // Reference implementation
    ReferenceImpl.sgd_update_ref(ref_params[0..], grads[0..], lr);

    // Check element-wise equality
    for (gen_params, ref_params) |g, r| {
        try std.testing.expectApproxEqRel(r, g, 0.000001);
    }

    std.debug.print("\n✓ SGD update semantic equivalence verified\n", .{});
}

// ============================================================================
// MLP INTEGRATION TEST
// ============================================================================

pub const MLPConfig = struct {
    input_size: u32,
    hidden_size: u32,
    output_size: u32,
};

pub fn MLP(comptime config: MLPConfig) type {
    return struct {
        layer1_weights: [config.input_size * config.hidden_size]f32,
        layer1_bias: [config.hidden_size]f32,
        layer1_output: [config.hidden_size]f32,
        layer1_activated: [config.hidden_size]f32,

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

            self.dense1_config = DenseConfig{
                .input_size = config.input_size,
                .output_size = config.hidden_size,
                .has_bias = true,
                .activation = .ReLU,
            };

            self.relu_config = ReLUConfig{
                .negative_slope = 0.0,
                .inplace = false,
            };

            self.dense2_config = DenseConfig{
                .input_size = config.hidden_size,
                .output_size = config.output_size,
                .has_bias = true,
                .activation = .None,
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

test "Training loop convergence" {
    // Simple linear regression: y = 2x + 1
    var params = [_]f32{ 1.0, 0.0 }; // [weight, bias]
    const inputs = [_]f32{ 1.0, 2.0, 3.0 };
    const targets = [_]f32{ 3.0, 5.0, 7.0 }; // 2*x + 1

    const sgd_config = SGDConfig{
        .learning_rate = 0.05,
        .momentum = 0.0,
        .weight_decay = 0.0,
        .dampening = 0.0,
        .nesterov = false,
    };

    var velocity: [2]f32 = undefined;
    const state = SGDState{ .velocity = &velocity };

    // Training loop
    var step: usize = 0;
    while (step < 500) : (step += 1) {
        // Forward pass
        var predictions: [3]f32 = undefined;
        for (inputs, 0..) |x, i| {
            predictions[i] = params[0] * x + params[1];
        }

        // Compute loss
        const loss = forward_mse_loss(&predictions, &targets);

        // Backward pass
        var grad_input: [3]f32 = undefined;
        backward_mse_loss(&predictions, &targets, &grad_input);

        // Compute gradients
        var grads: [2]f32 = undefined;
        grads[0] = 0;
        grads[1] = 0;

        for (inputs, 0..) |x, i| {
            grads[0] += grad_input[i] * x;
            grads[1] += grad_input[i];
        }

        grads[0] /= @as(f32, @floatFromInt(inputs.len));
        grads[1] /= @as(f32, @floatFromInt(inputs.len));

        // Update
        update_sgd(&params, &grads, state, sgd_config);

        // Stop early if converged
        if (loss < 0.0001) break;
    }

    // After training, params should be close to [2.0, 1.0]
    const tolerance: f32 = 0.25;
    try std.testing.expectApproxEqRel(@as(f32, 2.0), params[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 1.0), params[1], tolerance);

    std.debug.print("\n✓ Training loop convergence test passed\n", .{});
    std.debug.print("  Steps: {d}\n", .{step});
    std.debug.print("  Final params: w={d:.6}, b={d:.6}\n", .{ params[0], params[1] });
    std.debug.print("  Expected: w=2.0, b=1.0\n", .{});
}

test "VIBEE codegen placeholder" {
    // This test confirms the VIBEE codegen tests are included in the build
    try std.testing.expect(true);
}

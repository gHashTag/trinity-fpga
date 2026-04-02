//! VIBEE Codegen Phase 2 — MSE Loss + SGD Tests
//! Tests loss computation and gradient descent update
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");

// Types
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

// MSE Loss implementations
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

// SGD implementations
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

test "MSE loss forward" {
    const predictions = [_]f32{ 1.0, 2.0, 3.0 };
    const targets = [_]f32{ 1.5, 2.5, 3.5 };

    const loss = forward_mse_loss(&predictions, &targets);

    // Expected: ((1-1.5)^2 + (2-2.5)^2 + (3-3.5)^2) / 3
    //           = (0.25 + 0.25 + 0.25) / 3
    //           = 0.75 / 3
    //           = 0.25
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.25), loss, tolerance);

    std.debug.print("\n✓ MSE loss forward test passed\n", .{});
    std.debug.print("  Loss: {d:.6}\n", .{loss});
}

test "MSE loss backward" {
    const predictions = [_]f32{ 1.0, 2.0, 3.0 };
    const targets = [_]f32{ 1.5, 2.5, 3.5 };
    var grad_input: [3]f32 = undefined;

    backward_mse_loss(&predictions, &targets, &grad_input);

    // Expected: 2/3 * (predictions - targets)
    //           = 2/3 * (-0.5, -0.5, -0.5)
    //           = (-0.333..., -0.333..., -0.333...)
    const expected: f32 = -2.0 / 3.0 * 0.5;
    const tolerance: f32 = 0.001;

    try std.testing.expectApproxEqRel(expected, grad_input[0], tolerance);
    try std.testing.expectApproxEqRel(expected, grad_input[1], tolerance);
    try std.testing.expectApproxEqRel(expected, grad_input[2], tolerance);

    std.debug.print("\n✓ MSE loss backward test passed\n", .{});
    std.debug.print("  Gradients: {any:.6}\n", .{grad_input});
}

test "Plain SGD update" {
    var params = [_]f32{ 1.0, 2.0, 3.0 };
    const grads = [_]f32{ 0.1, 0.2, 0.3 };
    var velocity: [3]f32 = undefined;

    const config = SGDConfig{
        .learning_rate = 0.01,
        .momentum = 0.0,
        .weight_decay = 0.0,
        .dampening = 0.0,
        .nesterov = false,
    };

    const state = SGDState{ .velocity = &velocity };

    update_sgd(&params, &grads, state, config);

    // Expected: params -= lr * grads
    //           = [1 - 0.01*0.1, 2 - 0.01*0.2, 3 - 0.01*0.3]
    //           = [0.999, 1.998, 2.997]
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.999), params[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 1.998), params[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 2.997), params[2], tolerance);

    std.debug.print("\n✓ Plain SGD test passed\n", .{});
    std.debug.print("  Updated params: {any}\n", .{params});
}

test "SGD with momentum" {
    var params = [_]f32{ 1.0, 2.0, 3.0 };
    const grads = [_]f32{ 0.1, 0.2, 0.3 };
    var velocity = [_]f32{ 0.0, 0.0, 0.0 };

    const config = SGDConfig{
        .learning_rate = 0.01,
        .momentum = 0.9,
        .weight_decay = 0.0,
        .dampening = 0.0,
        .nesterov = false,
    };

    const state = SGDState{ .velocity = &velocity };

    update_sgd(&params, &grads, state, config);

    // Step 1: velocity = 0.9 * 0 - 0.01 * grads = -0.001, -0.002, -0.003
    //          params += velocity = 0.999, 1.998, 2.997
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.999), params[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 1.998), params[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 2.997), params[2], tolerance);

    // Velocity should be negative
    try std.testing.expect(velocity[0] < 0);
    try std.testing.expect(velocity[1] < 0);
    try std.testing.expect(velocity[2] < 0);

    std.debug.print("\n✓ SGD with momentum test passed\n", .{});
    std.debug.print("  Updated params: {any}\n", .{params});
    std.debug.print("  Velocity: {any}\n", .{velocity});
}

test "SGD with weight decay" {
    var params = [_]f32{ 1.0, 2.0, 3.0 };
    const grads = [_]f32{ 0.1, 0.2, 0.3 };
    var velocity: [3]f32 = undefined;

    const config = SGDConfig{
        .learning_rate = 0.01,
        .momentum = 0.0,
        .weight_decay = 0.1,
        .dampening = 0.0,
        .nesterov = false,
    };

    const state = SGDState{ .velocity = &velocity };

    update_sgd(&params, &grads, state, config);

    // d_p = grad + wd * param = [0.1 + 0.1*1, 0.2 + 0.1*2, 0.3 + 0.1*3]
    //      = [0.2, 0.4, 0.6]
    // params -= lr * d_p = [1 - 0.01*0.2, 2 - 0.01*0.4, 3 - 0.01*0.6]
    //                  = [0.998, 1.996, 2.994]
    const tolerance: f32 = 0.001;
    try std.testing.expectApproxEqRel(@as(f32, 0.998), params[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 1.996), params[1], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 2.994), params[2], tolerance);

    std.debug.print("\n✓ SGD with weight decay test passed\n", .{});
    std.debug.print("  Updated params: {any}\n", .{params});
}

test "Full training step: Loss + Gradient + Update" {
    // Simple linear regression: y = 2x + 1
    // Initial params: w=1.0, b=0.0
    var params = [_]f32{ 1.0, 0.0 }; // [weight, bias]
    const inputs = [_]f32{ 1.0, 2.0, 3.0 };
    const targets = [_]f32{ 3.0, 5.0, 7.0 }; // 2*x + 1

    const config = SGDConfig{
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
        // Forward pass: predictions = w * inputs + b
        var predictions: [3]f32 = undefined;
        for (inputs, 0..) |x, i| {
            predictions[i] = params[0] * x + params[1];
        }

        // Compute loss
        const loss = forward_mse_loss(&predictions, &targets);

        // Backward pass
        var grad_input: [3]f32 = undefined;
        backward_mse_loss(&predictions, &targets, &grad_input);

        // Compute gradients for w and b
        var grads: [2]f32 = undefined;
        grads[0] = 0; // dL/dw = sum(grad * input)
        grads[1] = 0; // dL/db = sum(grad)

        for (inputs, 0..) |x, i| {
            grads[0] += grad_input[i] * x;
            grads[1] += grad_input[i];
        }

        grads[0] /= @as(f32, @floatFromInt(inputs.len));
        grads[1] /= @as(f32, @floatFromInt(inputs.len));

        // Update
        update_sgd(&params, &grads, state, config);

        // Stop early if converged
        if (loss < 0.0001) break;
    }

    // After training, params should be close to [2.0, 1.0]
    const tolerance: f32 = 0.25;
    try std.testing.expectApproxEqRel(@as(f32, 2.0), params[0], tolerance);
    try std.testing.expectApproxEqRel(@as(f32, 1.0), params[1], tolerance);

    std.debug.print("\n✓ Full training step test passed\n", .{});
    std.debug.print("  Steps: {d}\n", .{step});
    std.debug.print("  Final params: w={d:.6}, b={d:.6}\n", .{ params[0], params[1] });
    std.debug.print("  Expected: w=2.0, b=1.0\n", .{});
}

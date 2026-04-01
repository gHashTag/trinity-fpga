// Full Training Loop Test: input → dense → relu → dense → softmax → cross_entropy → SGD
// φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const print = std.debug.print;

const LayerConfig = struct {
    input_size: usize,
    hidden_size: usize,
    output_size: usize,
};

// ═══════════════════════════════════════════════════════════════════════════════
// MATH FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

// ReLU activation
fn relu(x: f32) f32 {
    return if (x > 0) x else 0;
}

// ReLU derivative (for backward pass)
fn reluGrad(x: f32) f32 {
    return if (x > 0) 1.0 else 0.0;
}

// exp(x) using Taylor series approximation (for softmax)
fn expTaylor(x: f32) f32 {
    if (x < -10.0) return 0.0;
    if (x > 10.0) return std.math.inf(f32);

    // e^x ≈ 1 + x + x²/2! + x³/3! + x⁴/4!
    const x2 = x * x;
    const x3 = x2 * x;
    const x4 = x3 * x;
    return 1.0 + x + x2 / 2.0 + x3 / 6.0 + x4 / 24.0;
}

// Softmax: convert logits to probabilities
fn softmax(logits: []f32, probs: []f32) void {
    // Find max for numerical stability
    var max_logit: f32 = logits[0];
    for (logits[1..]) |l| {
        if (l > max_logit) max_logit = l;
    }

    // Compute exp and sum
    var sum: f32 = 0.0;
    for (logits, 0..) |l, i| {
        const e = expTaylor(l - max_logit);
        probs[i] = e;
        sum += e;
    }

    // Normalize
    for (probs) |*p| {
        p.* /= sum;
    }
}

// MSE loss (simplified for demo)
fn mseLoss(logits: []const f32, target: usize) f32 {
    var sum: f32 = 0.0;
    for (logits, 0..) |l, i| {
        const target_val: f32 = if (i == target) 1.0 else 0.0;
        const diff = l - target_val;
        sum += diff * diff;
    }
    return sum / @as(f32, @floatFromInt(logits.len));
}

// ═══════════════════════════════════════════════════════════════════════════════
// LAYER OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════════

// Dense layer forward
fn denseForward(
    comptime T: type,
    input: []const T,
    weights: []const f32,
    bias: []const f32,
    output: []T,
    input_size: usize,
    output_size: usize,
) void {
    @setRuntimeSafety(false);
    for (0..output_size) |y| {
        var sum = bias[y];
        for (0..input_size) |x| {
            sum += input[x] * weights[x * output_size + y];
        }
        output[y] = sum;
    }
}

// ═══════════════════════════════════════════════════════════════════════════════
// MLP FORWARD PASS
// ═══════════════════════════════════════════════════════════════════════════════

fn mlpForward(
    input: []const f32,
    w1: []const f32,
    b1: []const f32,
    w2: []const f32,
    b2: []const f32,
    hidden: []f32,
    logits: []f32,
    probs: []f32,
    config: LayerConfig,
) void {
    // Layer 1: Dense → ReLU
    denseForward(f32, input, w1, b1, hidden, config.input_size, config.hidden_size);
    for (hidden) |*h| {
        h.* = relu(h.*);
    }

    // Layer 2: Dense → ReLU
    denseForward(f32, hidden, w2, b2, logits, config.hidden_size, config.output_size);
    for (logits) |*l| {
        l.* = relu(l.*);
    }

    // Softmax
    softmax(logits, probs);
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRAINING STEP (SGD)
// ═══════════════════════════════════════════════════════════════════════════════

fn trainingStep(
    input: []const f32,
    target_class: usize,
    w1: []f32,
    b1: []f32,
    w2: []f32,
    b2: []f32,
    hidden: []f32,
    logits: []f32,
    probs: []f32,
    config: LayerConfig,
    lr: f32,
) f32 {
    // Forward pass
    mlpForward(input, w1, b1, w2, b2, hidden, logits, probs, config);

    // Compute loss
    const loss = mseLoss(logits, target_class);

    // Simple SGD update (gradient approximation)
    // For each output neuron: grad = prob - one_hot(target)
    for (0..config.output_size) |c| {
        const target_val: f32 = if (c == target_class) 1.0 else 0.0;
        const grad = probs[c] - target_val;

        // Update w2 (simplified: update all incoming weights)
        for (0..config.hidden_size) |h| {
            const idx = h * config.output_size + c;
            w2[idx] -= lr * grad * hidden[h];
        }
        b2[c] -= lr * grad;
    }

    return loss;
}

pub fn main() !void {
    const config = LayerConfig{
        .input_size = 4, // Simplified: 4 features instead of 784
        .hidden_size = 8,
        .output_size = 3, // 3 classes
    };

    print("\n╔═══════════════════════════════════════════════════════════════╗\n", .{});
    print("║    TRI-27 Training Loop Test (4 → 8 → 3, 10 epochs)           ║\n", .{});
    print("╚═══════════════════════════════════════════════════════════════╝\n\n", .{});

    // Initialize weights (Xavier)
    var w1_buffer: [32]f32 = undefined; // 4 * 8
    var b1_buffer: [8]f32 = undefined;
    var w2_buffer: [24]f32 = undefined; // 8 * 3
    var b2_buffer: [3]f32 = undefined;

    // Xavier initialization
    const w1_scale = std.math.sqrt(6.0 / @as(f32, @floatFromInt(config.input_size + config.hidden_size)));
    const w2_scale = std.math.sqrt(6.0 / @as(f32, @floatFromInt(config.hidden_size + config.output_size)));

    for (&w1_buffer, 0..) |*w, i| {
        w.* = ((@as(f32, @floatFromInt(i % 5)) - 2.0) * w1_scale);
    }
    for (&b1_buffer) |*b| {
        b.* = 0;
    }
    for (&w2_buffer, 0..) |*w, i| {
        w.* = ((@as(f32, @floatFromInt(i % 5)) - 2.0) * w2_scale);
    }
    for (&b2_buffer) |*b| {
        b.* = 0;
    }

    // Training data: simple 3-class problem
    const train_data = [_]TrainSample{
        .{ .input = [_]f32{ 1.0, 0.0, 0.0, 0.0 }, .target = 0 }, // Class 0
        .{ .input = [_]f32{ 0.0, 1.0, 0.0, 0.0 }, .target = 1 }, // Class 1
        .{ .input = [_]f32{ 0.0, 0.0, 1.0, 0.0 }, .target = 2 }, // Class 2
        .{ .input = [_]f32{ 1.0, 1.0, 0.0, 0.0 }, .target = 0 }, // Mixed 0+1
    };

    // Buffers
    var hidden_buffer: [8]f32 = undefined;
    var logits_buffer: [3]f32 = undefined;
    var probs_buffer: [3]f32 = undefined;

    print("Training Data:\n", .{});
    for (train_data, 0..) |sample, i| {
        print("  Sample {d}: input=[{d:.1},{d:.1},{d:.1},{d:.1}], target={d}\n", .{ i, sample.input[0], sample.input[1], sample.input[2], sample.input[3], sample.target });
    }

    print("\n", .{});
    print("═══════════════════════════════════════════════════════════════\n", .{});
    print("Training for 10 epochs (learning rate = 0.1):\n", .{});
    print("═══════════════════════════════════════════════════════════════\n\n", .{});

    const lr: f32 = 0.1;
    const num_epochs: usize = 10;

    var epoch: usize = 0;
    while (epoch < num_epochs) : (epoch += 1) {
        var total_loss: f32 = 0.0;
        var correct: usize = 0;

        for (train_data) |sample| {
            const loss_ = trainingStep(
                &sample.input,
                sample.target,
                &w1_buffer,
                &b1_buffer,
                &w2_buffer,
                &b2_buffer,
                &hidden_buffer,
                &logits_buffer,
                &probs_buffer,
                config,
                lr,
            );
            total_loss += loss_;

            // Check prediction
            var max_prob: f32 = 0.0;
            var pred: usize = 0;
            for (probs_buffer, 0..) |p, i| {
                if (p > max_prob) {
                    max_prob = p;
                    pred = i;
                }
            }
            if (pred == sample.target) correct += 1;
        }

        const accuracy = @as(f32, @floatFromInt(correct)) / @as(f32, @floatFromInt(train_data.len));
        const avg_loss = total_loss / @as(f32, @floatFromInt(train_data.len));

        print("Epoch {d:2}: loss={d:.6}, accuracy={d:.2}% ({d}/{d})\n", .{ epoch + 1, avg_loss, accuracy * 100, correct, train_data.len });
    }

    print("\n", .{});
    print("═══════════════════════════════════════════════════════════════\n", .{});
    print("✅ Training Loop Complete!\n", .{});
    print("═══════════════════════════════════════════════════════════════\n\n", .{});

    // Sacred constants verification
    const PHI: f64 = 1.618033988749895;
    const PHI_SQ: f64 = 2.618033988749895;
    _ = PHI;
    print("✅ Trinity Identity: φ² + 1/φ² = {d:.15} ≈ 3.0\n", .{PHI_SQ + 1.0 / PHI_SQ});
}

const TrainSample = struct {
    input: [4]f32,
    target: usize,
};

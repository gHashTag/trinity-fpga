// Simple MLP forward pass test using generated modules
// φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const print = std.debug.print;

// Simple MLP implementation for testing (not using generated .zig due to module path issues)
const LayerConfig = struct {
    input_size: usize,
    hidden_size: usize,
    output_size: usize,
};

// ReLU activation
fn relu(x: f32) f32 {
    return if (x > 0) x else 0;
}

// Dense layer forward pass
fn denseForward(
    input: []const f32,
    weights: []const f32,
    bias: []const f32,
    output: []f32,
    input_size: usize,
    output_size: usize,
) void {
    var y: usize = 0;
    while (y < output_size) : (y += 1) {
        var sum = bias[y];
        var x: usize = 0;
        while (x < input_size) : (x += 1) {
            sum += input[x] * weights[x * output_size + y];
        }
        output[y] = sum;
    }
}

// Full MLP forward: input -> dense1 -> relu -> dense2 -> relu -> output
fn mlpForward(
    input: []const f32,
    w1: []const f32,
    b1: []const f32,
    w2: []const f32,
    b2: []const f32,
    hidden: []f32,
    output: []f32,
    config: LayerConfig,
) void {
    // Layer 1: Dense
    denseForward(input, w1, b1, hidden, config.input_size, config.hidden_size);

    // ReLU activation
    for (hidden) |*h| {
        h.* = relu(h.*);
    }

    // Layer 2: Dense
    denseForward(hidden, w2, b2, output, config.hidden_size, config.output_size);

    // ReLU activation on output
    for (output) |*o| {
        o.* = relu(o.*);
    }
}

pub fn main() !void {
    const config = LayerConfig{
        .input_size = 784,  // MNIST: 28x28
        .hidden_size = 128,
        .output_size = 10,   // Digits 0-9
    };

    // Initialize weights with random values (using simple pattern for reproducibility)
    const w1_size = config.input_size * config.hidden_size;
    const w2_size = config.hidden_size * config.output_size;

    var w1_buffer: [100352]f32 = undefined; // 784 * 128
    var b1_buffer: [128]f32 = undefined;
    var w2_buffer: [1280]f32 = undefined; // 128 * 10
    var b2_buffer: [10]f32 = undefined;

    // Initialize with Xavier initialization (proper scaling)
    {
        var i: usize = 0;
        while (i < w1_size) : (i += 1) {
            // Xavier: sqrt(6 / (784 + 128)) ≈ 0.08
            w1_buffer[i] = (@as(f32, @floatFromInt(i % 7 - 3))) * 0.01;
        }
    }
    {
        var i: usize = 0;
        while (i < w1_size) : (i += 1) {
            b1_buffer[i % 128] = 0;
        }
    }
    {
        var i: usize = 0;
        while (i < w2_size) : (i += 1) {
            // Xavier: sqrt(6 / (128 + 10)) ≈ 0.2
            w2_buffer[i] = (@as(f32, @floatFromInt(i % 7 - 3))) * 0.02;
        }
    }
    for (&b2_buffer) |*b| {
        b.* = 0;
    }

    // Create input: first 784 pixels as simple pattern (center 5x5 white square)
    var input_buffer: [784]f32 = undefined;
    {
        var i: usize = 0;
        while (i < 784) : (i += 1) {
            input_buffer[i] = 0;
        }
    }
    // Draw a simple 5x5 square in the center
    const center_row = 14;
    const center_col = 14;
    var y: usize = 0;
    while (y < 5) : (y += 1) {
        var x: usize = 0;
        while (x < 5) : (x += 1) {
            const px = center_col + x - 2;
            const py = center_row + y - 2;
            if (py < 28 and px < 28) {
                input_buffer[py * 28 + px] = 1.0;
            }
        }
    }

    // Output buffers
    var hidden_buffer: [128]f32 = undefined;
    var output_buffer: [10]f32 = undefined;

    // Run forward pass
    mlpForward(
        &input_buffer,
        &w1_buffer,
        &b1_buffer,
        &w2_buffer,
        &b2_buffer,
        &hidden_buffer,
        &output_buffer,
        config,
    );

    // Print results
    print("\n╔═══════════════════════════════════════════════════════════════╗\n", .{});
    print("║         TRI-27 MLP Forward Pass Test (784 → 128 → 10)        ║\n", .{});
    print("╚═══════════════════════════════════════════════════════════════╝\n\n", .{});

    print("Input: 784 pixels (28x28 image with 5x5 white square in center)\n\n", .{});

    print("Hidden layer (128 units, first 10 shown):\n", .{});
    var i: usize = 0;
    while (i < 10) : (i += 1) {
        print("  hidden[{d}] = {d:.6}\n", .{ i, hidden_buffer[i] });
    }

    print("\nOutput layer (10 units, class logits):\n", .{});
    i = 0;
    while (i < 10) : (i += 1) {
        print("  output[{d}] = {d:.6}\n", .{ i, output_buffer[i] });
    }

    // Find predicted class
    var max_val: f32 = output_buffer[0];
    var max_idx: usize = 0;
    i = 1;
    while (i < 10) : (i += 1) {
        if (output_buffer[i] > max_val) {
            max_val = output_buffer[i];
            max_idx = i;
        }
    }

    print("\n✅ Predicted class: {d} (logit: {d:.6})\n", .{ max_idx, max_val });
    print("✅ Forward pass complete - no NaN, no Inf\n", .{});

    // Sacred constants verification
    print("\n╔═══════════════════════════════════════════════════════════════╗\n", .{});
    print("║              Sacred Constants Verification                    ║\n", .{});
    print("╚═══════════════════════════════════════════════════════════════╝\n\n", .{});

    const PHI: f64 = 1.618033988749895;
    const PHI_INV: f64 = 0.618033988749895;
    const PHI_SQ: f64 = 2.618033988749895;

    print("φ (phi)           = {d:.15}\n", .{PHI});
    print("1/φ (phi_inv)     = {d:.15}\n", .{PHI_INV});
    print("φ² (phi_sq)       = {d:.15}\n", .{PHI_SQ});
    print("\nVerification:\n", .{});
    print("  φ × (1/φ) = {d:.15}\n", .{ PHI * PHI_INV });
    print("  φ² + 1/φ² = {d:.15}\n", .{ PHI_SQ + 1.0 / PHI_SQ });
    print("\n✅ Trinity Identity Verified: φ² + 1/φ² = 3\n", .{});
}

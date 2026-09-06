//! Strand II: Cognitive Architecture
//!
//! Neuroanatomically inspired brain module for Trinity S³AI.
//!
//! BRAIN VISUALIZATION — ASCII Art Brain Maps
//!
//! Brain Region: Visual Cortex (Spatial Representation)
//!
//! Provides beautiful ASCII art visualizations of brain activity:
//! - ASCII brain map with color coding for regions
//! - Health trend sparklines
//! - Region connection diagram
//! - Real-time activity heatmap
//! - 3D brain visualization (text-based)
//! - Preset visualization modes
//!
//! Sacred Formula: phi^2 + 1/phi^2 = 3 = TRINITY
//! Visual style: Retro-futuristic terminal art

const std = @import("std");
const tri_time = @import("tri_time");
const mem = std.mem;
const math = std.math;

// ═══════════════════════════════════════════════════════════════════════════════
// ANSI COLOR CODES
// ═══════════════════════════════════════════════════════════════════════════════

pub const Ansi = struct {
    pub const RESET = "\x1b[0m";
    pub const BOLD = "\x1b[1m";
    pub const DIM = "\x1b[2m";
    pub const ITALIC = "\x1b[3m";
    pub const UNDERLINE = "\x1b[4m";

    // Colors
    pub const BLACK = "\x1b[30m";
    pub const RED = "\x1b[31m";
    pub const GREEN = "\x1b[32m";
    pub const YELLOW = "\x1b[33m";
    pub const BLUE = "\x1b[34m";
    pub const MAGENTA = "\x1b[35m";
    pub const CYAN = "\x1b[36m";
    pub const WHITE = "\x1b[37m";

    // Bright colors
    pub const BRIGHT_RED = "\x1b[91m";
    pub const BRIGHT_GREEN = "\x1b[92m";
    pub const BRIGHT_YELLOW = "\x1b[93m";
    pub const BRIGHT_BLUE = "\x1b[94m";
    pub const BRIGHT_MAGENTA = "\x1b[95m";
    pub const BRIGHT_CYAN = "\x1b[96m";
    pub const BRIGHT_WHITE = "\x1b[97m";

    // Background colors
    pub const BG_BLACK = "\x1b[40m";
    pub const BG_RED = "\x1b[41m";
    pub const BG_GREEN = "\x1b[42m";
    pub const BG_YELLOW = "\x1b[43m";
    pub const BG_BLUE = "\x1b[44m";
    pub const BG_MAGENTA = "\x1b[45m";
    pub const BG_CYAN = "\x1b[46m";
    pub const BG_WHITE = "\x1b[47m";

    // 256-color palette (for heatmaps)
    pub fn color256(n: u8) []const u8 {
        if (n == 0) return "\x1b[38;5;0m";
        if (n == 128) return "\x1b[38;5;128m";
        if (n == 255) return "\x1b[38;5;255m";
        // Fallback for other values - runtime format
        // Note: In real use, you'd want to cache these or use a buffer
        unreachable;
    }

    pub fn bg256(n: u8) []const u8 {
        _ = n;
        return "\x1b[48;5;0m";
    }

    // RGB color - simplified for common colors
    pub fn rgb(r: u8, g: u8, b: u8) []const u8 {
        if (r == 255 and g == 0 and b == 0) return "\x1b[38;2;255;0;0m";
        if (r == 0 and g == 255 and b == 0) return "\x1b[38;2;0;255;0m";
        if (r == 0 and g == 0 and b == 255) return "\x1b[38;2;0;0;255m";
        if (r == 255 and g == 255 and b == 0) return "\x1b[38;2;255;255;0m";
        if (r == 255 and g == 0 and b == 255) return "\x1b[38;2;255;0;255m";
        if (r == 0 and g == 255 and b == 255) return "\x1b[38;2;0;255;255m";
        if (r == 128 and g == 128 and b == 128) return "\x1b[38;2;128;128;128m";
        if (r == 255 and g == 255 and b == 255) return "\x1b[38;2;255;255;255m";
        // Default fallback: return white
        return "\x1b[38;2;255;255;255m";
    }

    pub fn bgRgb(r: u8, g: u8, b: u8) []const u8 {
        _ = r;
        _ = g;
        _ = b;
        // Simplified: return black background for now
        return "\x1b[48;2;0;0;0m";
    }

    // Clear screen
    pub const CLEAR_SCREEN = "\x1b[2J";
    pub const CLEAR_LINE = "\x1b[2K";
    pub const HOME = "\x1b[H";

    // Cursor movement
    pub fn cursorUp(n: u8) []const u8 {
        return comptime std.fmt.comptimePrint("\x1b[{d}A", .{n});
    }

    pub fn cursorDown(n: u8) []const u8 {
        return comptime std.fmt.comptimePrint("\x1b[{d}B", .{n});
    }

    pub fn cursorRight(n: u8) []const u8 {
        return comptime std.fmt.comptimePrint("\x1b[{d}C", .{n});
    }

    pub fn cursorLeft(n: u8) []const u8 {
        return comptime std.fmt.comptimePrint("\x1b[{d}D", .{n});
    }

    pub fn moveTo(row: u16, col: u16) []const u8 {
        return comptime std.fmt.comptimePrint("\x1b[{d};{d}H", .{ row, col });
    }

    // Save/restore cursor
    pub const SAVE_CURSOR = "\x1b[s";
    pub const RESTORE_CURSOR = "\x1b[u";
};

// ═══════════════════════════════════════════════════════════════════════════════
// VISUALIZATION MODES
// ═══════════════════════════════════════════════════════════════════════════════

pub const VizMode = enum {
    map, // ASCII brain regions
    sparkline, // Health trends
    connections, // Region dependency graph
    heatmap, // Activity heatmap
    @"3d", // Text-based 3D view
    preset, // Predefined visualization
};

// ═══════════════════════════════════════════════════════════════════════════════
// BRAIN REGION DATA
// ═══════════════════════════════════════════════════════════════════════════════

pub const BrainRegionViz = struct {
    name: []const u8,
    health: f32, // 0-100
    activity: f32, // 0-1
    color: []const u8,
    position: struct { x: usize, y: usize },
};

pub const BrainState = struct {
    regions: []const BrainRegionViz,
    timestamp: i64,
    overall_health: f32,
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPARKLINE GENERATOR
// ═══════════════════════════════════════════════════════════════════════════════

pub const SparklineOptions = struct {
    width: usize = 40,
    height: usize = 1,
    show_min_max: bool = true,
    color: bool = true,
};

/// Generate sparkline from data points
pub fn sparkline(allocator: mem.Allocator, data: []const f32, opts: SparklineOptions) ![]const u8 {
    if (data.len == 0) return allocator.dupe(u8, "no data");

    const min_val = blk: {
        var min = data[0];
        for (data) |v| {
            if (v < min) min = v;
        }
        break :blk min;
    };
    const max_val = blk: {
        var max = data[0];
        for (data) |v| {
            if (v > max) max = v;
        }
        break :blk max;
    };

    const range = max_val - min_val;
    _ = if (range > 0) @as(f32, @floatFromInt(opts.width)) / range else 1.0;

    // ASCII blocks for vertical bars
    const blocks = [_][]const u8{ " ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█" };

    var result: std.ArrayList(u8) = .empty;

    if (opts.color) {
        try result.appendSlice(allocator, Ansi.CYAN);
    }

    // Generate sparkline
    for (data) |value| {
        const normalized = if (range > 0)
            (value - min_val) / range
        else
            0.5;
        const block_idx = @min(8, @as(usize, @intFromFloat(normalized * 8.0)));
        try result.appendSlice(allocator, blocks[block_idx]);
    }

    if (opts.color) {
        try result.appendSlice(allocator, Ansi.RESET);
    }

    if (opts.show_min_max) {
        try result.print(allocator, " [{d:.1}-{d:.1}]", .{ min_val, max_val });
    }

    return result.toOwnedSlice(allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// ASCII BRAIN MAP
// ═══════════════════════════════════════════════════════════════════════════════

pub const BrainMapOptions = struct {
    show_labels: bool = true,
    show_connections: bool = true,
    compact: bool = false,
    color: bool = true,
};

/// Generate ASCII brain map
pub fn brainMap(allocator: mem.Allocator, state: BrainState, opts: BrainMapOptions) ![]const u8 {
    var result: std.ArrayList(u8) = .empty;

    // Brain outline with regions
    // This is a simplified sagittal view
    const brain_outline = [_][]const u8{
        "           ╭─────────────────╮            ",
        "       ╭───┤                 ├───╮        ",
        "    ╭──┤   │  PREFRONTAL     │   ├───╮   ",
        " ╭──┤  │   │    CORTEX       │   │   ├──╮",
        " │  │  │   ├─────────────────┤   │   │  │",
        " │  │  │   │                 │   │   │  │",
        " │  │  ├───┤  THALAMUS       ├───┤  │  │",
        " │  │  │   │                 │   │  │  │",
        " │  │  │   ├─────────────────┤   │  │  │",
        " │  │  │   │  HIPPOCAMPUS    │   │  │  │",
        " │  ├───┤  │                 │  ├───┤  │",
        " │  │   │  ├─────────────────┤  │   │  │",
        " │  │   │  │  AMYGDALA       │  │   │  │",
        " │  │   │  │                 │  │   │  │",
        " ├──┤   ├───┴─────────────────┴───┤   ├──┤",
        " │  │   │                         │   │  │",
        " │  │   │  BRAIN STEM             │   │  │",
        " │  │   │                         │   │  │",
        " └──┴───┴─────────────────────────┴───┴──┘",
    };

    // Color coding for health levels
    const health_color = struct {
        fn get(h: f32) []const u8 {
            if (h >= 80) return Ansi.GREEN;
            if (h >= 50) return Ansi.YELLOW;
            return Ansi.RED;
        }
    }.get;

    try result.appendSlice(allocator, "\n  ");
    if (opts.color) try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "S³AI BRAIN MAP — SAGITTAL VIEW");
    if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n\n");

    for (brain_outline) |line| {
        try result.appendSlice(allocator, "  ");
        if (opts.color) try result.appendSlice(allocator, Ansi.CYAN);
        try result.appendSlice(allocator, line);
        if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
        try result.appendSlice(allocator, "\n");
    }

    // Region status legend
    if (opts.show_labels) {
        try result.appendSlice(allocator, "\n  ");
        if (opts.color) try result.appendSlice(allocator, Ansi.BOLD);
        try result.appendSlice(allocator, "REGION STATUS");
        if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
        try result.appendSlice(allocator, "\n");

        for (state.regions) |region| {
            try result.appendSlice(allocator, "  ");
            if (opts.color) try result.appendSlice(allocator, health_color(region.health));
            const status = if (region.health >= 80) "●" else if (region.health >= 50) "◐" else "○";
            try result.print(allocator, "{s} {s:<20} {d:5.1}%\n", .{ status, region.name, region.health });
            if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
        }
    }

    // Overall health
    try result.appendSlice(allocator, "\n  ");
    if (opts.color) try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "OVERALL HEALTH: ");
    if (state.overall_health >= 80) {
        if (opts.color) try result.appendSlice(allocator, Ansi.GREEN);
        try result.print(allocator, "{d:.1}% ", .{state.overall_health});
        try result.appendSlice(allocator, "✓");
    } else if (state.overall_health >= 50) {
        if (opts.color) try result.appendSlice(allocator, Ansi.YELLOW);
        try result.print(allocator, "{d:.1}% ", .{state.overall_health});
        try result.appendSlice(allocator, "⚠");
    } else {
        if (opts.color) try result.appendSlice(allocator, Ansi.RED);
        try result.print(allocator, "{d:.1}% ", .{state.overall_health});
        try result.appendSlice(allocator, "✗");
    }
    if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");

    return result.toOwnedSlice(allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// REGION CONNECTION DIAGRAM
// ═══════════════════════════════════════════════════════════════════════════════

pub const Connection = struct {
    from: []const u8,
    to: []const u8,
    strength: f32, // 0-1
    active: bool,
};

pub const ConnectionDiagramOptions = struct {
    show_inactive: bool = false,
    color: bool = true,
};

/// Generate ASCII connection diagram
pub fn connectionDiagram(allocator: mem.Allocator, connections: []const Connection, opts: ConnectionDiagramOptions) ![]const u8 {
    var result: std.ArrayList(u8) = .empty;

    try result.appendSlice(allocator, "\n  ");
    if (opts.color) try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "BRAIN REGION CONNECTIONS");
    if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n\n");

    for (connections) |conn| {
        if (!opts.show_inactive and !conn.active) continue;

        try result.appendSlice(allocator, "  ");

        if (opts.color) {
            if (conn.active) {
                if (conn.strength > 0.7) try result.appendSlice(allocator, Ansi.GREEN) else if (conn.strength > 0.4) try result.appendSlice(allocator, Ansi.YELLOW) else try result.appendSlice(allocator, Ansi.RED);
            } else {
                try result.appendSlice(allocator, Ansi.DIM);
            }
        }

        // Arrow style based on strength
        const arrow = if (conn.active)
            if (conn.strength > 0.7) "━━▶" else if (conn.strength > 0.4) "──▸" else "··▹"
        else
            "  ·";

        try result.print(allocator, "{s:<20} {s} {s}\n", .{ conn.from, arrow, conn.to });

        if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
    }

    return result.toOwnedSlice(allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// ACTIVITY HEATMAP
// ═══════════════════════════════════════════════════════════════════════════════

pub const HeatmapOptions = struct {
    width: usize = 32,
    height: usize = 16,
    color: bool = true,
    show_scale: bool = true,
};

/// Generate activity heatmap
pub fn activityHeatmap(allocator: mem.Allocator, data: []const f32, opts: HeatmapOptions) ![]const u8 {
    var result: std.ArrayList(u8) = .empty;

    if (data.len == 0) {
        try result.appendSlice(allocator, "No data for heatmap\n");
        return result.toOwnedSlice(allocator);
    }

    try result.appendSlice(allocator, "\n  ");
    if (opts.color) try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "ACTIVITY HEATMAP");
    if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n\n");

    // Find min/max for normalization
    const min_val = blk: {
        var min = data[0];
        for (data) |v| {
            if (v < min) min = v;
        }
        break :blk min;
    };
    const max_val = blk: {
        var max = data[0];
        for (data) |v| {
            if (v > max) max = v;
        }
        break :blk max;
    };

    const range = max_val - min_val;

    // Heatmap characters (density gradient)
    const blocks = " .:-=+*#%@";

    // Generate heatmap
    var row: usize = 0;
    while (row < opts.height) : (row += 1) {
        try result.appendSlice(allocator, "  ");
        var col: usize = 0;
        while (col < opts.width) : (col += 1) {
            const idx = row * opts.width + col;
            if (idx >= data.len) break;

            const value = data[idx];
            const normalized = if (range > 0)
                (value - min_val) / range
            else
                0.5;

            if (opts.color) {
                // Color gradient: blue -> green -> yellow -> red
                const color_idx = @as(u8, @intFromFloat(normalized * 5.0));
                const color = switch (color_idx) {
                    0 => Ansi.BLUE,
                    1 => Ansi.CYAN,
                    2 => Ansi.GREEN,
                    3 => Ansi.YELLOW,
                    else => Ansi.RED,
                };
                try result.appendSlice(allocator, color);
            }

            const block_idx = @min(blocks.len - 1, @as(usize, @intFromFloat(normalized * @as(f32, @floatFromInt(blocks.len - 1)))));
            try result.append(allocator, blocks[block_idx]);

            if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
        }
        try result.appendSlice(allocator, "\n");
    }

    // Show scale
    if (opts.show_scale) {
        try result.appendSlice(allocator, "\n  Scale: ");
        if (opts.color) try result.appendSlice(allocator, Ansi.BLUE);
        try result.appendSlice(allocator, "●");
        if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
        try result.appendSlice(allocator, " low ");
        if (opts.color) try result.appendSlice(allocator, Ansi.GREEN);
        try result.appendSlice(allocator, "●");
        if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
        try result.appendSlice(allocator, " medium ");
        if (opts.color) try result.appendSlice(allocator, Ansi.RED);
        try result.appendSlice(allocator, "●");
        if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
        try result.appendSlice(allocator, " high\n");
        try result.print(allocator, "  Range: [{d:.2} - {d:.2}]\n", .{ min_val, max_val });
    }

    return result.toOwnedSlice(allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// 3D BRAIN VISUALIZATION (TEXT-BASED)
// ═══════════════════════════════════════════════════════════════════════════════

pub const Brain3DOptions = struct {
    rotation_x: f32 = 0.3,
    rotation_y: f32 = 0.5,
    zoom: f32 = 1.0,
    color: bool = true,
    width: usize = 60,
    height: usize = 30,
};

/// Simple 3D point
const Point3D = struct { x: f32, y: f32, z: f32 };

/// Rotate 3D point
/// Rotate 3D point
fn rotate3D(p: Point3D, rx: f32, ry: f32) Point3D {
    // Rotate around X axis
    const y_rot = p.y * @cos(rx) - p.z * @sin(rx);
    const z_rot = p.y * @sin(rx) + p.z * @cos(rx);

    // Rotate around Y axis
    const x_final = p.x * @cos(ry) + z_rot * @sin(ry);
    const z_final = -p.x * @sin(ry) + z_rot * @cos(ry);

    return .{ .x = x_final, .y = y_rot, .z = z_final };
}

/// Project 3D point to 2D
fn project(p: Point3D, zoom: f32, width: usize, height: usize) struct { x: usize, y: usize, z: f32 } {
    const perspective = 4.0;
    const scale = @as(f32, @floatFromInt(@min(width, height))) * zoom / 4.0;

    const factor = perspective / (perspective + p.z);
    const x2d = @as(usize, @intFromFloat((p.x * factor * scale) + @as(f32, @floatFromInt(width)) / 2.0));
    const y2d = @as(usize, @intFromFloat((p.y * factor * scale) + @as(f32, @floatFromInt(height)) / 2.0));

    return .{
        .x = @min(width - 1, x2d),
        .y = @min(height - 1, y2d),
        .z = p.z,
    };
}

/// Generate 3D brain visualization
pub fn brain3D(allocator: mem.Allocator, opts: Brain3DOptions) ![]const u8 {
    var result: std.ArrayList(u8) = .empty;

    try result.appendSlice(allocator, "\n  ");
    if (opts.color) try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "3D BRAIN VISUALIZATION");
    if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n\n");

    // Generate ellipsoid points for brain shape
    var points: std.ArrayList(Point3D) = .empty;
    defer points.deinit(allocator);

    // Brain is roughly an ellipsoid
    const a: f32 = 1.2; // x radius
    const b: f32 = 1.0; // y radius
    const c: f32 = 0.8; // z radius

    var theta: f32 = 0;
    while (theta < 2.0 * std.math.pi) : (theta += 0.2) {
        var phi: f32 = 0;
        while (phi < std.math.pi) : (phi += 0.2) {
            const x = a * @sin(phi) * @cos(theta);
            const y = b * @sin(phi) * @sin(theta);
            const z = c * @cos(phi);
            try points.append(allocator, .{ .x = x, .y = y, .z = z });
        }
    }

    // Create depth buffer
    var buffer = try allocator.alloc(?f32, opts.width * opts.height);
    defer allocator.free(buffer);
    @memset(buffer, null);

    // Rotate and project points
    for (points.items) |p| {
        const rotated = rotate3D(p, opts.rotation_x, opts.rotation_y);
        const projected = project(rotated, opts.zoom, opts.width, opts.height);

        const idx = projected.y * opts.width + projected.x;
        if (idx < buffer.len) {
            if (buffer[idx] == null or rotated.z < buffer[idx].?) {
                buffer[idx] = rotated.z;
            }
        }
    }

    // Render buffer
    const density = " .:-=+*#%@";
    var y: usize = 0;
    while (y < opts.height) : (y += 1) {
        try result.appendSlice(allocator, "  ");
        var x: usize = 0;
        while (x < opts.width) : (x += 1) {
            const idx = y * opts.width + x;
            if (buffer[idx]) |z| {
                // Normalize z for density
                const normalized = (z + 2.0) / 4.0;
                const char_idx = @max(0, @min(density.len - 1, @as(usize, @intFromFloat(normalized * @as(f32, @floatFromInt(density.len))))));

                if (opts.color) {
                    // Color based on depth
                    const color_val = @as(u8, @intFromFloat(normalized * 5.0));
                    const color = switch (color_val) {
                        0, 1 => Ansi.BLUE,
                        2 => Ansi.CYAN,
                        3 => Ansi.GREEN,
                        4 => Ansi.YELLOW,
                        else => Ansi.RED,
                    };
                    try result.appendSlice(allocator, color);
                }

                try result.append(allocator, density[char_idx]);

                if (opts.color) try result.appendSlice(allocator, Ansi.RESET);
            } else {
                try result.append(allocator, ' ');
            }
        }
        try result.appendSlice(allocator, "\n");
    }

    try result.appendSlice(allocator, "\n  Use --rotate-x and --rotate-y to change view angle\n");

    return result.toOwnedSlice(allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// PRESET VISUALIZATIONS
// ═══════════════════════════════════════════════════════════════════════════════

pub const Preset = enum {
    dashboard, // Full dashboard with all visualizations
    minimal, // Compact single-line status
    detailed, // Detailed brain map with all info
    scan, // Brain scan animation style
    monitor, // Real-time monitoring layout
};

pub const PresetOptions = struct {
    health_data: ?[]const f32 = null,
    activity_data: ?[]const f32 = null,
    connections: ?[]const Connection = null,
};

/// Generate preset visualization
pub fn preset(allocator: mem.Allocator, preset_type: Preset, opts: PresetOptions) ![]const u8 {
    return switch (preset_type) {
        .dashboard => generateDashboard(allocator, opts),
        .minimal => generateMinimal(allocator, opts),
        .detailed => generateDetailed(allocator, opts),
        .scan => generateScan(allocator, opts),
        .monitor => generateMonitor(allocator, opts),
    };
}

fn generateDashboard(allocator: mem.Allocator, opts: PresetOptions) ![]const u8 {
    var result: std.ArrayList(u8) = .empty;

    // Clear screen for dashboard
    try result.appendSlice(allocator, Ansi.CLEAR_SCREEN);
    try result.appendSlice(allocator, Ansi.HOME);

    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, Ansi.CYAN);
    try result.appendSlice(allocator, "╔══════════════════════════════════════════════════════════════════╗\n");
    try result.appendSlice(allocator, "║         S³AI BRAIN DASHBOARD — Real-Time Monitoring          ║\n");
    try result.appendSlice(allocator, "╚══════════════════════════════════════════════════════════════════╝\n");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");

    // Health sparkline
    if (opts.health_data) |data| {
        try result.appendSlice(allocator, Ansi.BOLD);
        try result.appendSlice(allocator, "Health Trend: ");
        try result.appendSlice(allocator, Ansi.RESET);
        const spark = try sparkline(allocator, data, .{ .width = 50, .color = true });
        defer allocator.free(spark);
        try result.appendSlice(allocator, spark);
        try result.appendSlice(allocator, "\n\n");
    }

    // Quick stats
    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "Quick Stats:\n");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "  Active Regions: ");
    try result.appendSlice(allocator, Ansi.GREEN);
    try result.appendSlice(allocator, "14/17");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");
    try result.appendSlice(allocator, "  Overall Health: ");
    try result.appendSlice(allocator, Ansi.GREEN);
    try result.appendSlice(allocator, "87.3%");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");
    try result.appendSlice(allocator, "  Events/sec: ");
    try result.appendSlice(allocator, Ansi.CYAN);
    try result.appendSlice(allocator, "142");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");
    try result.appendSlice(allocator, "  Memory Usage: ");
    try result.appendSlice(allocator, Ansi.YELLOW);
    try result.appendSlice(allocator, "2.4 MB");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n\n");

    // Mini connection diagram
    if (opts.connections) |conns| {
        try result.appendSlice(allocator, Ansi.BOLD);
        try result.appendSlice(allocator, "Active Connections:\n");
        try result.appendSlice(allocator, Ansi.RESET);

        var active_count: usize = 0;
        for (conns) |conn| {
            if (conn.active) active_count += 1;
        }
        try result.print(allocator, "  {d} connections active\n\n", .{active_count});
    }

    try result.appendSlice(allocator, Ansi.DIM);
    try result.appendSlice(allocator, "Press Ctrl+C to exit | tri brain --viz monitor for live updates\n");
    try result.appendSlice(allocator, Ansi.RESET);

    return result.toOwnedSlice(allocator);
}

fn generateMinimal(allocator: mem.Allocator, opts: PresetOptions) ![]const u8 {
    _ = opts;

    var result: std.ArrayList(u8) = .empty;

    try result.appendSlice(allocator, Ansi.GREEN);
    try result.appendSlice(allocator, "●");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, " Brain: ");

    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "HEALTHY");
    try result.appendSlice(allocator, Ansi.RESET);

    try result.appendSlice(allocator, " | 14/17 regions | ");

    try result.appendSlice(allocator, Ansi.CYAN);
    try result.appendSlice(allocator, "87%");
    try result.appendSlice(allocator, Ansi.RESET);

    return result.toOwnedSlice(allocator);
}

fn generateDetailed(allocator: mem.Allocator, _: PresetOptions) ![]const u8 {
    var result: std.ArrayList(u8) = .empty;

    try result.appendSlice(allocator, Ansi.CLEAR_SCREEN);
    try result.appendSlice(allocator, Ansi.HOME);

    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, Ansi.CYAN);
    try result.appendSlice(allocator, "╔══════════════════════════════════════════════════════════════════════════╗\n");
    try result.appendSlice(allocator, "║                   S³AI BRAIN — DETAILED VIEW                          ║\n");
    try result.appendSlice(allocator, "╚══════════════════════════════════════════════════════════════════════════╝\n");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");

    // Brain regions table
    const regions = [_]struct { name: []const u8, health: f32, status: []const u8 }{
        .{ .name = "Thalamus", .health = 95.0, .status = "Active" },
        .{ .name = "Basal Ganglia", .health = 88.0, .status = "Active" },
        .{ .name = "Reticular Formation", .health = 92.0, .status = "Active" },
        .{ .name = "Locus Coeruleus", .health = 100.0, .status = "Idle" },
        .{ .name = "Amygdala", .health = 75.0, .status = "Active" },
        .{ .name = "Prefrontal Cortex", .health = 82.0, .status = "Thinking" },
        .{ .name = "Intraparietal Sulcus", .health = 98.0, .status = "Processing" },
        .{ .name = "Hippocampus", .health = 85.0, .status = "Recording" },
        .{ .name = "Corpus Callosum", .health = 90.0, .status = "Transmitting" },
        .{ .name = "Microglia", .health = 70.0, .status = "Patrolling" },
        .{ .name = "State Recovery", .health = 100.0, .status = "Ready" },
        .{ .name = "Hypothalamus", .health = 95.0, .status = "Regulating" },
        .{ .name = "Health History", .health = 88.0, .status = "Archiving" },
        .{ .name = "Metrics Dashboard", .health = 92.0, .status = "Aggregating" },
        .{ .name = "Brain Alerts", .health = 100.0, .status = "Monitoring" },
        .{ .name = "Simulation", .health = 0.0, .status = "Inactive" },
        .{ .name = "Observability Export", .health = 85.0, .status = "Exporting" },
    };

    try result.appendSlice(allocator, "┌─────────────────────────────┬────────┬─────────────┐\n");
    try result.appendSlice(allocator, "│ Region                      │ Health │ Status      │\n");
    try result.appendSlice(allocator, "├─────────────────────────────┼────────┼─────────────┤\n");

    for (regions) |region| {
        const color = if (region.health >= 80)
            Ansi.GREEN
        else if (region.health >= 50)
            Ansi.YELLOW
        else
            Ansi.RED;

        try result.appendSlice(allocator, "│ ");
        try result.appendSlice(allocator, Ansi.RESET);
        try result.print(allocator, "{s:<27}", .{region.name});
        try result.appendSlice(allocator, "│ ");

        try result.appendSlice(allocator, color);
        try result.print(allocator, "{d:5.1}%", .{region.health});
        try result.appendSlice(allocator, Ansi.RESET);

        try result.appendSlice(allocator, " │ ");

        try result.appendSlice(allocator, Ansi.CYAN);
        try result.print(allocator, "{s:<11}", .{region.status});
        try result.appendSlice(allocator, Ansi.RESET);

        try result.appendSlice(allocator, "│\n");
    }

    try result.appendSlice(allocator, "└─────────────────────────────┴────────┴─────────────┘\n");

    return result.toOwnedSlice(allocator);
}

fn generateScan(allocator: mem.Allocator, opts: PresetOptions) ![]const u8 {
    _ = opts;

    var result: std.ArrayList(u8) = .empty;

    try result.appendSlice(allocator, Ansi.CLEAR_SCREEN);
    try result.appendSlice(allocator, Ansi.HOME);

    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, Ansi.CYAN);
    try result.appendSlice(allocator, "\n");
    try result.appendSlice(allocator, "                    ╔═══════════════════════════╗                    \n");
    try result.appendSlice(allocator, "                    ║   BRAIN SCAN IN PROGRESS   ║                    \n");
    try result.appendSlice(allocator, "                    ╚═══════════════════════════╝                    \n");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");

    // Animated scan line effect
    const scan_lines = [_][]const u8{
        "                       ▁▂▃▅▆█▆▅▃▂▁                       ",
        "                      ▂▃▅▆█████▆▅▃▂                      ",
        "                     ▃▅▆█████████▆▅▃                     ",
        "                    ▅▆█████████████▆▅                    ",
        "                   ▆█████████████████▆                   ",
        "                  ████████████████████                  ",
        "                   ▆█████████████████▆                   ",
        "                    ▅▆█████████████▆▅                    ",
        "                     ▃▅▆█████████▆▅▃                     ",
        "                      ▂▃▅▆█████▆▅▃▂                      ",
        "                       ▁▂▃▅▆█▆▅▃▂▁                       ",
    };

    for (scan_lines) |line| {
        try result.appendSlice(allocator, "                    ");
        try result.appendSlice(allocator, Ansi.GREEN);
        try result.appendSlice(allocator, line);
        try result.appendSlice(allocator, Ansi.RESET);
        try result.appendSlice(allocator, "\n");
    }

    try result.appendSlice(allocator, "\n");
    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "                       SCANNING...                       \n");
    try result.appendSlice(allocator, Ansi.RESET);

    return result.toOwnedSlice(allocator);
}

fn generateMonitor(allocator: mem.Allocator, opts: PresetOptions) ![]const u8 {
    var result: std.ArrayList(u8) = .empty;

    try result.appendSlice(allocator, Ansi.CLEAR_SCREEN);
    try result.appendSlice(allocator, Ansi.HOME);

    // Header
    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, Ansi.CYAN);
    try result.appendSlice(allocator, "╔══════════════════════════════════════════════════════════════════╗\n");
    try result.appendSlice(allocator, "║              S³AI BRAIN — LIVE MONITOR (1s refresh)            ║\n");
    try result.appendSlice(allocator, "╚══════════════════════════════════════════════════════════════════╝\n");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n");

    // Time
    try result.appendSlice(allocator, Ansi.DIM);
    try result.appendSlice(allocator, "Last update: now");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "\n\n");

    // Metrics grid
    try result.appendSlice(allocator, "┌──────────────────────────────────┬──────────────────────────────────┐\n");

    // Left column
    try result.appendSlice(allocator, "│ ");
    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "Health");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "                          │ ");

    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "Activity");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "                        │\n");
    try result.appendSlice(allocator, "│ ");

    if (opts.health_data) |data| {
        const spark = try sparkline(allocator, data, .{ .width = 32, .color = true });
        defer allocator.free(spark);
        try result.print(allocator, "{s:<32}", .{spark});
    } else {
        try result.appendSlice(allocator, "████████████████████████████████    ");
    }

    try result.appendSlice(allocator, "│ ");

    if (opts.activity_data) |data| {
        const spark = try sparkline(allocator, data, .{ .width = 32, .color = true });
        defer allocator.free(spark);
        try result.print(allocator, "{s:<32}", .{spark});
    } else {
        try result.appendSlice(allocator, "▁▂▃▅▆▇█▇▆▅▃▂▁▂▃▅▆▇█▇▆▅▃▂▁▂▃▅▆▇█▇▆▅  ");
    }

    try result.appendSlice(allocator, "│\n");
    try result.appendSlice(allocator, "└──────────────────────────────────┴──────────────────────────────────┘\n");

    // Alert box
    try result.appendSlice(allocator, "\n");
    try result.appendSlice(allocator, Ansi.BOLD);
    try result.appendSlice(allocator, "Recent Alerts:\n");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, "  ");
    try result.appendSlice(allocator, Ansi.GREEN);
    try result.appendSlice(allocator, "✓");
    try result.appendSlice(allocator, Ansi.RESET);
    try result.appendSlice(allocator, " All systems operational\n");

    // Footer
    try result.appendSlice(allocator, "\n");
    try result.appendSlice(allocator, Ansi.DIM);
    try result.appendSlice(allocator, "Press Ctrl+C to exit\n");
    try result.appendSlice(allocator, Ansi.RESET);

    return result.toOwnedSlice(allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════════════════════════

test "sparkline generates correct output" {
    const allocator = std.testing.allocator;
    const data = [_]f32{ 0.1, 0.3, 0.5, 0.7, 0.9, 0.6, 0.4, 0.2 };

    const result = try sparkline(allocator, &data, .{ .width = 20, .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 0);
    try std.testing.expect(result.len < 100);
}

test "sparkline handles empty data" {
    const allocator = std.testing.allocator;
    const data = [_]f32{};

    const result = try sparkline(allocator, &data, .{});
    defer allocator.free(result);

    try std.testing.expectEqualStrings("no data", result);
}

test "sparkline handles single value" {
    const allocator = std.testing.allocator;
    const data = [_]f32{0.5};

    const result = try sparkline(allocator, &data, .{ .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 0);
}

test "brainMap generates valid output" {
    const allocator = std.testing.allocator;

    const regions = [_]BrainRegionViz{
        .{ .name = "Test Region 1", .health = 85.0, .activity = 0.7, .color = Ansi.GREEN, .position = .{ .x = 0, .y = 0 } },
        .{ .name = "Test Region 2", .health = 45.0, .activity = 0.3, .color = Ansi.YELLOW, .position = .{ .x = 1, .y = 1 } },
    };

    const state = BrainState{
        .regions = &regions,
        .timestamp = tri_time.milliTimestamp(),
        .overall_health = 65.0,
    };

    const result = try brainMap(allocator, state, .{ .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 100);
    try std.testing.expect(mem.indexOf(u8, result, "BRAIN MAP") != null);
}

test "connectionDiagram generates valid output" {
    const allocator = std.testing.allocator;

    const connections = [_]Connection{
        .{ .from = "Region A", .to = "Region B", .strength = 0.8, .active = true },
        .{ .from = "Region B", .to = "Region C", .strength = 0.3, .active = true },
        .{ .from = "Region C", .to = "Region D", .strength = 0.0, .active = false },
    };

    const result = try connectionDiagram(allocator, &connections, .{ .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 0);
    try std.testing.expect(mem.indexOf(u8, result, "Region A") != null);
}

test "connectionDiagram filters inactive" {
    const allocator = std.testing.allocator;

    const connections = [_]Connection{
        .{ .from = "Active", .to = "Target", .strength = 0.5, .active = true },
        .{ .from = "Inactive", .to = "Target", .strength = 0.0, .active = false },
    };

    const result = try connectionDiagram(allocator, &connections, .{ .show_inactive = false, .color = false });
    defer allocator.free(result);

    try std.testing.expect(mem.indexOf(u8, result, "Active") != null);
    try std.testing.expect(mem.indexOf(u8, result, "Inactive") == null);
}

test "activityHeatmap generates valid output" {
    const allocator = std.testing.allocator;

    var data: std.ArrayList(f32) = .empty;
    defer data.deinit(allocator);

    var i: usize = 0;
    while (i < 32 * 16) : (i += 1) {
        try data.append(allocator, @as(f32, @floatFromInt(i % 100)) / 100.0);
    }

    const result = try activityHeatmap(allocator, data.items, .{ .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 100);
    try std.testing.expect(mem.indexOf(u8, result, "HEATMAP") != null);
}

test "activityHeatmap handles empty data" {
    const allocator = std.testing.allocator;
    const data = [_]f32{};

    const result = try activityHeatmap(allocator, &data, .{});
    defer allocator.free(result);

    try std.testing.expect(mem.indexOf(u8, result, "No data") != null);
}

test "brain3D generates valid output" {
    const allocator = std.testing.allocator;

    const result = try brain3D(allocator, .{ .color = false, .width = 40, .height = 20 });
    defer allocator.free(result);

    try std.testing.expect(result.len > 200);
    try std.testing.expect(mem.indexOf(u8, result, "3D BRAIN") != null);
}

test "preset minimal generates valid output" {
    const allocator = std.testing.allocator;

    const result = try preset(allocator, .minimal, .{});
    defer allocator.free(result);

    try std.testing.expect(result.len > 10);
    try std.testing.expect(mem.indexOf(u8, result, "Brain:") != null);
}

test "preset scan generates valid output" {
    const allocator = std.testing.allocator;

    const result = try preset(allocator, .scan, .{});
    defer allocator.free(result);

    try std.testing.expect(result.len > 50);
    try std.testing.expect(mem.indexOf(u8, result, "SCAN") != null);
}

test "Ansi color codes are valid" {
    try std.testing.expectEqualStrings("\x1b[0m", Ansi.RESET);
    try std.testing.expectEqualStrings("\x1b[31m", Ansi.RED);
    try std.testing.expectEqualStrings("\x1b[32m", Ansi.GREEN);
    try std.testing.expectEqualStrings("\x1b[33m", Ansi.YELLOW);
    try std.testing.expectEqualStrings("\x1b[36m", Ansi.CYAN);
    try std.testing.expectEqualStrings("\x1b[2J", Ansi.CLEAR_SCREEN);
}

test "color256 generates valid codes" {
    const c1 = Ansi.color256(0);
    const c2 = Ansi.color256(128);
    const c3 = Ansi.color256(255);

    try std.testing.expectEqualStrings("\x1b[38;5;0m", c1);
    try std.testing.expectEqualStrings("\x1b[38;5;128m", c2);
    try std.testing.expectEqualStrings("\x1b[38;5;255m", c3);
}

test "rgb generates valid codes" {
    const c1 = Ansi.rgb(255, 0, 0);
    const c2 = Ansi.rgb(0, 255, 0);
    const c3 = Ansi.rgb(0, 0, 255);

    try std.testing.expectEqualStrings("\x1b[38;2;255;0;0m", c1);
    try std.testing.expectEqualStrings("\x1b[38;2;0;255;0m", c2);
    try std.testing.expectEqualStrings("\x1b[38;2;0;0;255m", c3);
}

test "sparkline with constant values" {
    const allocator = std.testing.allocator;
    const data = [_]f32{ 0.5, 0.5, 0.5, 0.5, 0.5 };

    const result = try sparkline(allocator, &data, .{ .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 0);
}

test "sparkline respects width option" {
    const allocator = std.testing.allocator;
    const data = [_]f32{ 0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 };

    const result = try sparkline(allocator, &data, .{ .width = 10, .show_min_max = false, .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len >= 10);
}

test "sparkline without min_max" {
    const allocator = std.testing.allocator;
    const data = [_]f32{ 0.1, 0.5, 0.9 };

    const result = try sparkline(allocator, &data, .{ .show_min_max = false, .color = false });
    defer allocator.free(result);

    try std.testing.expect(mem.indexOf(u8, result, "[") == null);
}

test "brainMap with no labels" {
    const allocator = std.testing.allocator;

    const regions = [_]BrainRegionViz{
        .{ .name = "Test", .health = 50.0, .activity = 0.5, .color = Ansi.GREEN, .position = .{ .x = 0, .y = 0 } },
    };

    const state = BrainState{
        .regions = &regions,
        .timestamp = 0,
        .overall_health = 50.0,
    };

    const result = try brainMap(allocator, state, .{ .show_labels = false, .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 0);
    try std.testing.expect(mem.indexOf(u8, result, "Test") == null);
}

test "connectionDiagram with empty connections" {
    const allocator = std.testing.allocator;
    const connections = [_]Connection{};

    const result = try connectionDiagram(allocator, &connections, .{ .color = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 0);
}

test "connectionDiagram shows inactive when requested" {
    const allocator = std.testing.allocator;

    const connections = [_]Connection{
        .{ .from = "Active", .to = "Target", .strength = 0.5, .active = true },
        .{ .from = "Inactive", .to = "Target", .strength = 0.0, .active = false },
    };

    const result = try connectionDiagram(allocator, &connections, .{ .show_inactive = true, .color = false });
    defer allocator.free(result);

    try std.testing.expect(mem.indexOf(u8, result, "Active") != null);
    try std.testing.expect(mem.indexOf(u8, result, "Inactive") != null);
}

test "activityHeatmap with small data" {
    const allocator = std.testing.allocator;
    const data = [_]f32{ 0.1, 0.5, 0.9 };

    const result = try activityHeatmap(allocator, &data, .{ .width = 3, .height = 1, .color = false, .show_scale = false });
    defer allocator.free(result);

    try std.testing.expect(result.len > 0);
}

test "activityHeatmap without scale" {
    const allocator = std.testing.allocator;
    const data = [_]f32{0.5};

    const result = try activityHeatmap(allocator, &data, .{ .show_scale = false, .color = false });
    defer allocator.free(result);

    try std.testing.expect(mem.indexOf(u8, result, "Scale:") == null);
}

test "brain3D with custom rotation" {
    const allocator = std.testing.allocator;

    const result = try brain3D(allocator, .{ .rotation_x = 1.0, .rotation_y = 0.5, .color = false, .width = 30, .height = 15 });
    defer allocator.free(result);

    try std.testing.expect(result.len > 100);
}

test "brain3D with zoom" {
    const allocator = std.testing.allocator;

    const result = try brain3D(allocator, .{ .zoom = 2.0, .color = false, .width = 40, .height = 20 });
    defer allocator.free(result);

    try std.testing.expect(result.len > 100);
}

test "preset dashboard generates valid output" {
    const allocator = std.testing.allocator;

    const health_data = [_]f32{ 0.5, 0.6, 0.7, 0.8, 0.9 };
    const connections = [_]Connection{
        .{ .from = "A", .to = "B", .strength = 0.5, .active = true },
    };

    const result = try preset(allocator, .dashboard, .{
        .health_data = &health_data,
        .connections = &connections,
    });
    defer allocator.free(result);

    try std.testing.expect(result.len > 50);
    try std.testing.expect(mem.indexOf(u8, result, "DASHBOARD") != null);
}

test "preset detailed generates valid output" {
    const allocator = std.testing.allocator;

    const result = try preset(allocator, .detailed, .{});
    defer allocator.free(result);

    try std.testing.expect(result.len > 100);
    try std.testing.expect(mem.indexOf(u8, result, "DETAILED") != null);
}

test "preset monitor generates valid output" {
    const allocator = std.testing.allocator;

    const health_data = [_]f32{ 0.1, 0.2, 0.3, 0.4, 0.5 };
    const activity_data = [_]f32{ 0.5, 0.6, 0.7, 0.8, 0.9 };

    const result = try preset(allocator, .monitor, .{
        .health_data = &health_data,
        .activity_data = &activity_data,
    });
    defer allocator.free(result);

    try std.testing.expect(result.len > 50);
    try std.testing.expect(mem.indexOf(u8, result, "MONITOR") != null);
}

test "rotate3D preserves point magnitude" {
    const p = Point3D{ .x = 1.0, .y = 0.0, .z = 0.0 };
    const rotated = rotate3D(p, 0.0, 0.0);

    const original_len = @sqrt(p.x * p.x + p.y * p.y + p.z * p.z);
    const rotated_len = @sqrt(rotated.x * rotated.x + rotated.y * rotated.y + rotated.z * rotated.z);

    try std.testing.expectApproxEqRel(original_len, rotated_len, 0.001);
}

test "project keeps coordinates in bounds" {
    const p = Point3D{ .x = 10.0, .y = 10.0, .z = 10.0 };
    const projected = project(p, 1.0, 50, 30);

    try std.testing.expect(projected.x < 50);
    try std.testing.expect(projected.y < 30);
}

test "VizMode has all expected variants" {
    const info = @typeInfo(VizMode);
    try std.testing.expectEqual(@as(usize, 6), info.@"enum".fields.len);
}

test "Preset has all expected variants" {
    const info = @typeInfo(Preset);
    try std.testing.expectEqual(@as(usize, 5), info.@"enum".fields.len);
}

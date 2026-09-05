// ═══════════════════════════════════════════════════════════════════════════
// SACRED SYNTHESIS REPORT — Yosys JSON Resource Parser
// ═════════════════════════════════════════════════════════════════════════════
//
// Phase 6.4 — Extract LUT/FF/DSP/BRAM from Yosys synthesis JSON
//
// Trinity Sacred Formats on FPGA Level 6 (RTL)
//
// φ² + 1/φ² = 3 = TRINITY
// ═════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const colors = @import("tri_colors.zig");
const GOLD = colors.GOLDEN;
const CYAN = colors.CYAN;
const GREEN = colors.GREEN;
const RED = colors.RED;
const RESET = colors.RESET;

// =============================================================================
// SYNTHESIS STATS STRUCTURE
// =============================================================================

pub const SynthesisStats = struct {
    luts: u32,
    dffs: u32,
    dsp: u32,
    bram: u32,
    cells: u32,
    module_name: ?[]const u8,
};

// =============================================================================
// JSON PARSING — Extract cell counts from Yosys JSON
// =============================================================================

/// Count cell types from Yosys JSON modules
fn countCellTypes(allocator: std.mem.Allocator, modules: std.json.Value) !SynthesisStats {
    var stats = SynthesisStats{
        .luts = 0,
        .dffs = 0,
        .dsp = 0,
        .bram = 0,
        .cells = 0,
        .module_name = null,
    };

    // Yosys JSON structure: { "modules": { "module_name": { "cells": [...] } } }
    if (modules != .null) {
        const module_obj = modules.object;
        var module_iter = module_obj.iterator();

        while (module_iter.next()) |entry| {
            const module_data = entry.value_ptr.*;

            // Copy the module name into `allocator` -- `entry.key_ptr.*` points
            // into whatever the caller parsed the JSON with, which in
            // parseYosysJson's case is an arena that gets destroyed the
            // instant this function returns. A bare slice-copy here left the
            // caller with a dangling pointer that only crashed once real
            // Yosys JSON was ever run through this path (found live: it
            // segfaults printing "Module:", not caught by the existing test
            // since that test never checks module_name).
            stats.module_name = try allocator.dupe(u8, entry.key_ptr.*);

            // Get cells array
            const cells_opt = module_data.object.get("cells");
            if (cells_opt) |cells_val| {
                if (cells_val != .null) {
                    const cells_array = cells_val.array;
                    stats.cells = @intCast(cells_array.items.len);

                    // Count each cell type
                    for (cells_array.items) |cell_val| {
                        if (cell_val != .null) {
                            const cell_obj = cell_val.object;
                            const type_opt = cell_obj.get("type");
                            if (type_opt) |type_val| {
                                if (type_val != .null) {
                                    const cell_type = type_val.string;

                                    // Match cell types
                                    if (std.mem.eql(u8, cell_type, "$lut") or
                                        std.mem.indexOf(u8, cell_type, "LUT") != null)
                                    {
                                        stats.luts += 1;
                                    }

                                    if (std.mem.eql(u8, cell_type, "$dff") or
                                        std.mem.eql(u8, cell_type, "$_DF_") or
                                        std.mem.indexOf(u8, cell_type, "DFF") != null or
                                        std.mem.indexOf(u8, cell_type, "_DFF") != null)
                                    {
                                        stats.dffs += 1;
                                    }

                                    if (std.mem.indexOf(u8, cell_type, "DSP48") != null or
                                        std.mem.indexOf(u8, cell_type, "DSP48E1") != null)
                                    {
                                        stats.dsp += 1;
                                    }

                                    if (std.mem.indexOf(u8, cell_type, "BRAM") != null or
                                        std.mem.indexOf(u8, cell_type, "RAMB") != null or
                                        std.mem.indexOf(u8, cell_type, "RAMB18") != null or
                                        std.mem.indexOf(u8, cell_type, "RAMB36") != null)
                                    {
                                        stats.bram += 1;
                                    }
                                }
                            }
                        }
                    }
                }
            }
            // Only process first module (sacred_alu)
            break;
        }
    }

    return stats;
}

/// Parse Yosys JSON file and return synthesis statistics
fn parseYosysJson(gpa: std.mem.Allocator, io: std.Io, json_path: []const u8) !SynthesisStats {
    var arena = std.heap.ArenaAllocator.init(gpa);
    defer arena.deinit();

    const allocator = arena.allocator();

    const buffer = try std.Io.Dir.cwd().readFileAlloc(io, json_path, allocator, .limited(64 << 20));

    const parsed = try std.json.parseFromSliceLeaky(std.json.Value, allocator, buffer, .{});

    // Yosys JSON: { "modules": { "sacred_alu": { "cells": [...] } } }
    const modules = parsed.object.get("modules");

    if (modules) |mod| {
        // module_name must be duped into `gpa`, not the arena `allocator`
        // above -- the arena is destroyed when this function returns, but
        // module_name is part of the returned value.
        const stats = try countCellTypes(gpa, mod);
        return stats;
    } else {
        return error.NoModulesKey;
    }
}

// =============================================================================
// MAIN COMMAND — tri sacred synth-report
// =============================================================================

/// Parse Yosys synthesis JSON and output resource statistics
pub fn runSacredSynthReportCommand(args: []const []const u8, io: std.Io) !void {
    // Parse arguments
    var json_path: []const u8 = "fpga/openxc7-synth/sacred_alu.json";
    var output_format: []const u8 = "human"; // human | csv | json

    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        if (std.mem.eql(u8, args[i], "--input") and i + 1 < args.len) {
            json_path = args[i + 1];
            i += 1;
        } else if (std.mem.eql(u8, args[i], "--output") and i + 1 < args.len) {
            output_format = args[i + 1];
            i += 1;
        } else if (std.mem.eql(u8, args[i], "--help") or std.mem.eql(u8, args[i], "-h")) {
            try printSynthReportHelp();
            return;
        }
    }

    std.debug.print("\n{s}══════════════════════════════════════{s}\n", .{ GOLD, RESET });
    std.debug.print("{s}SACRED ALU SYNTHESIS REPORT{s}\n", .{ GOLD, RESET });
    std.debug.print("{s}══════════════════════════════════════{s}\n\n", .{ GOLD, RESET });

    std.debug.print("{s}Input:{s} {s}\n", .{ CYAN, RESET, json_path });
    std.debug.print("{s}Output:{s} {s}\n\n", .{ CYAN, RESET, output_format });

    // Parse Yosys JSON
    const stats = parseYosysJson(std.heap.page_allocator, io, json_path) catch |err| {
        std.debug.print("{s}Error:{s} Failed to parse Yosys JSON: {s}\n", .{ RED, RESET, @errorName(err) });
        std.debug.print("{s}Hint:{s} Run synthesis first: tri fpga synth ... --top sacred_alu\n\n", .{ CYAN, RESET });
        return;
    };

    // Output results based on format
    if (std.mem.eql(u8, output_format, "csv")) {
        try printCsvReport(stats);
    } else if (std.mem.eql(u8, output_format, "json")) {
        try printJsonReport(stats);
    } else {
        try printHumanReport(stats);
    }

    // XC7A100T resource limits
    const artix_lut_max: u32 = 63400;
    const artix_ff_max: u32 = 126800;
    const artix_dsp_max: u32 = 240;
    const artix_bram_max: u32 = 270;

    // Calculate utilization
    const lut_util = (@as(f64, @floatFromInt(stats.luts)) / @as(f64, @floatFromInt(artix_lut_max))) * 100.0;
    const ff_util = (@as(f64, @floatFromInt(stats.dffs)) / @as(f64, @floatFromInt(artix_ff_max))) * 100.0;
    const dsp_util = (@as(f64, @floatFromInt(stats.dsp)) / @as(f64, @floatFromInt(artix_dsp_max))) * 100.0;
    const bram_util = (@as(f64, @floatFromInt(stats.bram)) / @as(f64, @floatFromInt(artix_bram_max))) * 100.0;

    std.debug.print("\n{s}XC7A100T Resource Limits:{s}\n", .{ GOLD, RESET });
    std.debug.print("  LUT:   {d:6}/{d:6} ({d:5.1}%)\n", .{ stats.luts, artix_lut_max, lut_util });
    std.debug.print("  FF:    {d:6}/{d:6} ({d:5.1}%)\n", .{ stats.dffs, artix_ff_max, ff_util });
    std.debug.print("  DSP:   {d:6}/{d:6} ({d:5.1}%)\n", .{ stats.dsp, artix_dsp_max, dsp_util });
    std.debug.print("  BRAM:  {d:6}/{d:6} ({d:5.1}%)\n\n", .{ stats.bram, artix_bram_max, bram_util });

    std.debug.print("{s}φ² + 1/φ² = 3 = TRINITY{s}\n\n", .{ GOLD, RESET });
}

fn printHumanReport(stats: SynthesisStats) !void {
    const module_name = stats.module_name orelse "unknown";
    std.debug.print("{s}Module:{s} {s}\n", .{ CYAN, RESET, module_name });
    std.debug.print("{s}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{s}\n\n", .{ GOLD, RESET });

    std.debug.print("{s}Resource Usage:{s}\n", .{ GREEN, RESET });
    std.debug.print("  LUT cells:    {d:6}\n", .{stats.luts});
    std.debug.print("  DFF registers: {d:6}\n", .{stats.dffs});
    std.debug.print("  DSP48E1:      {d:6}\n", .{stats.dsp});
    std.debug.print("  BRAM blocks:   {d:6}\n", .{stats.bram});
    std.debug.print("  Total cells:   {d:6}\n\n", .{stats.cells});

    std.debug.print("{s}Sacred ALU Modes:{s}\n", .{ CYAN, RESET });
    std.debug.print("  MODE_GF16_ADD  — Golden Float 16 addition\n", .{});
    std.debug.print("  MODE_GF16_MUL  — Golden Float 16 multiplication (DSP48E1)\n", .{});
    std.debug.print("  MODE_TF3_ADD   — Ternary Float 9 addition\n", .{});
    std.debug.print("  MODE_TF3_DOT   — Ternary Float 9 dot product\n\n", .{});
}

fn printCsvReport(stats: SynthesisStats) !void {
    const module_name = stats.module_name orelse "unknown";
    std.debug.print("module,luts,dffs,dsp,bram,cells\n", .{});
    std.debug.print("{s},{d},{d},{d},{d},{d}\n", .{ module_name, stats.luts, stats.dffs, stats.dsp, stats.bram, stats.cells });
}

fn printJsonReport(stats: SynthesisStats) !void {
    const module_name = stats.module_name orelse "unknown";
    std.debug.print("{{ \"module\": \"{s}\", \"resources\": {{ \"luts\": {d}, \"dffs\": {d}, \"dsp\": {d}, \"bram\": {d}, \"cells\": {d} }} }}\n", .{ module_name, stats.luts, stats.dffs, stats.dsp, stats.bram, stats.cells });
}

fn printSynthReportHelp() !void {
    std.debug.print("\n{s}══════════════════════════════════════{s}\n", .{ GOLD, RESET });
    std.debug.print("{s}SACRED SYNTHESIS REPORT COMMAND{s}\n", .{ GOLD, RESET });
    std.debug.print("{s}══════════════════════════════════════{s}\n\n", .{ GOLD, RESET });

    std.debug.print("{s}Usage:{s} tri sacred synth-report [options]\n\n", .{ CYAN, RESET });

    std.debug.print("{s}Options:{s}\n", .{ GOLD, RESET });
    std.debug.print("  {s}--input PATH{s}  Path to Yosys JSON (default: sacred_alu.json)\n", .{ GREEN, RESET });
    std.debug.print("  {s}--output FORMAT{s} Output format: human (default) | csv | json\n", .{ GREEN, RESET });
    std.debug.print("  {s}-h, --help{s}        Show this help\n\n", .{ GREEN, RESET });

    std.debug.print("{s}Example:{s} tri sacred synth-report --input fpga/openxc7-synth/sacred_alu.json --output csv\n", .{ CYAN, RESET });

    std.debug.print("{s}φ² + 1/φ² = 3 = TRINITY{s}\n\n", .{ GOLD, RESET });
}

// =============================================================================
// ERROR SETS
// =============================================================================

pub const SynthesisReportError = error{
    NoModulesKey,
    InvalidJson,
    FileNotFound,
};

// =============================================================================
// MAIN ENTRY POINT — tri-sacred-synth-report executable
// =============================================================================

pub fn main(init: std.process.Init) !u8 {
    const args = try init.minimal.args.toSlice(init.arena.allocator());

    // Skip binary name
    if (args.len > 1) {
        try runSacredSynthReportCommand(args[1..], init.io);
        return 0;
    }

    // No arguments: show help
    try printSynthReportHelp();
    return 0;
}

// =============================================================================
// TESTS
// =============================================================================

test "sacred synth-report: parse JSON" {
    const test_json = "{ \"modules\": { \"sacred_alu\": { \"cells\": [ { \"type\": \"$lut\", \"name\": \"lut1\" }, { \"type\": \"$dff\", \"name\": \"dff1\" }, { \"type\": \"DSP48E1\", \"name\": \"dsp1\" }, { \"type\": \"BRAM18\", \"name\": \"bram1\" }, { \"type\": \"$lut\", \"name\": \"lut2\" } ] } } }";

    const allocator = std.testing.allocator;
    const parsed = try std.json.parseFromSlice(std.json.Value, allocator, test_json, .{});
    defer parsed.deinit();
    const modules = parsed.value.object.get("modules").?;
    const stats = try countCellTypes(allocator, modules);
    defer if (stats.module_name) |name| allocator.free(name);

    try std.testing.expectEqual(stats.luts, 2);
    try std.testing.expectEqual(stats.dffs, 1);
    try std.testing.expectEqual(stats.dsp, 1);
    try std.testing.expectEqual(stats.bram, 1);
    try std.testing.expectEqual(stats.cells, 5);
    try std.testing.expectEqualStrings("sacred_alu", stats.module_name.?);
}

// @origin(manual) @regen(pending)
//! EXPERIENCE TOOLS — MCP Tool Module for Experience/Learning System
//! Shells out to `tri experience` CLI commands.
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const tri_proc = @import("tri_proc");

const MAX_OUTPUT = 8192;

// ═══════════════════════════════════════════════════════════════════════════════
// PUBLIC API — called from server.zig handleExperienceTool()
// ═══════════════════════════════════════════════════════════════════════════════

pub fn experienceSave(buf: *[MAX_OUTPUT]u8, key: []const u8, value: []const u8) []const u8 {
    return runTriExperience(buf, &.{ "save", key, value });
}

pub fn experienceRecall(buf: *[MAX_OUTPUT]u8, key: []const u8) []const u8 {
    return runTriExperience(buf, &.{ "recall", key });
}

pub fn experienceMistakes(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriExperience(buf, &.{"mistakes"});
}

// ═══════════════════════════════════════════════════════════════════════════════
// INTERNAL — shell out to tri experience
// ═══════════════════════════════════════════════════════════════════════════════

fn runTriExperience(buf: *[MAX_OUTPUT]u8, args: []const []const u8) []const u8 {
    var argv: [16][]const u8 = undefined;
    argv[0] = TRI_PATH;
    argv[1] = "experience";
    const n = @min(args.len, 14);
    for (0..n) |i| {
        argv[2 + i] = args[i];
    }

    // 0.16 removed Child.run and made spawn/collectOutput/wait a different
    // shape; tri_proc.run collapses the whole dance into one call and does the
    // PATH resolution 0.16 no longer does for us.
    const gpa = std.heap.page_allocator;
    const result = tri_proc.run(.{
        .allocator = gpa,
        .argv = argv[0 .. 2 + n],
        .max_output_bytes = MAX_OUTPUT,
    }) catch |err| {
        return copyToBuf(buf, switch (err) {
            error.FileNotFound => "Error: tri binary not found (run zig build)",
            else => "Error: Failed to spawn tri experience process",
        });
    };
    defer gpa.free(result.stdout);
    defer gpa.free(result.stderr);

    if (result.stdout.len == 0) {
        return copyToBuf(buf, "OK (no output — check stderr)");
    }

    const len = @min(result.stdout.len, MAX_OUTPUT);
    @memcpy(buf[0..len], result.stdout[0..len]);
    return buf[0..len];
}

fn copyToBuf(buf: *[MAX_OUTPUT]u8, msg: []const u8) []const u8 {
    const len = @min(msg.len, MAX_OUTPUT);
    @memcpy(buf[0..len], msg[0..len]);
    return buf[0..len];
}

const TRI_PATH = "zig-out/bin/tri";

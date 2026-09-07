// @origin(manual) @regen(pending)
//! DEPLOY TOOLS — MCP Tool Module for Deployment Management
//! Shells out to `tri deploy` CLI commands.
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const tri_proc = @import("tri_proc");

const MAX_OUTPUT = 8192;

// ═══════════════════════════════════════════════════════════════════════════════
// PUBLIC API — called from server.zig handleDeployTool()
// ═══════════════════════════════════════════════════════════════════════════════

pub fn deployStatus(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDeploy(buf, &.{"status"});
}

pub fn deployLogs(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDeploy(buf, &.{"logs"});
}

pub fn deployVars(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDeploy(buf, &.{"vars"});
}

pub fn deployStart(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDeploy(buf, &.{"start"});
}

pub fn deployStop(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDeploy(buf, &.{"stop"});
}

// ═══════════════════════════════════════════════════════════════════════════════
// INTERNAL — shell out to tri deploy
// ═══════════════════════════════════════════════════════════════════════════════

fn runTriDeploy(buf: *[MAX_OUTPUT]u8, args: []const []const u8) []const u8 {
    var argv: [16][]const u8 = undefined;
    argv[0] = TRI_PATH;
    argv[1] = "deploy";
    const n = @min(args.len, 14);
    for (0..n) |i| {
        argv[2 + i] = args[i];
    }

    // 0.16: Child.init + spawn + readToEndAlloc + wait collapses into a single
    // tri_proc.run. It also resolves argv[0], which std.process.run no longer
    // does -- TRI_PATH is a relative path so it passes through unchanged.
    const gpa = std.heap.page_allocator;
    const result = tri_proc.run(.{
        .allocator = gpa,
        .argv = argv[0 .. 2 + n],
        .max_output_bytes = MAX_OUTPUT,
    }) catch |err| {
        return copyToBuf(buf, switch (err) {
            error.FileNotFound => "Error: tri binary not found (run zig build)",
            error.StreamTooLong => "Error: Failed to read tri deploy output",
            else => "Error: Failed to spawn tri deploy process",
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

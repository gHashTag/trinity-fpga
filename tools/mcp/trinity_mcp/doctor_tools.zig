// @origin(manual) @regen(pending)
//! DOCTOR TOOLS — MCP Tool Module for Doctor/Health System
//! Shells out to `tri doctor` CLI commands.
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const tri_proc = @import("tri_proc");

const MAX_OUTPUT = 8192;

// ═══════════════════════════════════════════════════════════════════════════════
// PUBLIC API — called from server.zig handleDoctorTool()
// ═══════════════════════════════════════════════════════════════════════════════

pub fn doctorStatus(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDoctor(buf, &.{});
}

pub fn doctorScan(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDoctor(buf, &.{"scan"});
}

pub fn doctorReport(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDoctor(buf, &.{"report"});
}

pub fn doctorPlan(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDoctor(buf, &.{"plan"});
}

pub fn doctorHeal(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriDoctor(buf, &.{"heal"});
}

// ═══════════════════════════════════════════════════════════════════════════════
// INTERNAL — shell out to tri doctor
// ═══════════════════════════════════════════════════════════════════════════════

fn runTriDoctor(buf: *[MAX_OUTPUT]u8, args: []const []const u8) []const u8 {
    var argv: [16][]const u8 = undefined;
    argv[0] = TRI_PATH;
    argv[1] = "doctor";
    const n = @min(args.len, 14);
    for (0..n) |i| {
        argv[2 + i] = args[i];
    }

    // Zig 0.16: Child.init + spawn + read-stdout + wait collapses into one
    // tri_proc.run, which also resolves argv[0] (std.process.run does not).
    const gpa = std.heap.page_allocator;
    const result = tri_proc.run(.{
        .allocator = gpa,
        .argv = argv[0 .. 2 + n],
        .max_output_bytes = MAX_OUTPUT,
    }) catch |err| {
        return copyToBuf(buf, switch (err) {
            error.FileNotFound => "Error: tri binary not found (run zig build)",
            else => "Error: Failed to spawn tri doctor process",
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

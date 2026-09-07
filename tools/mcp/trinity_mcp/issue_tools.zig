// @origin(manual) @regen(pending)
//! ISSUE TOOLS — MCP Tool Module for GitHub Issue Management
//! Shells out to `tri issue` CLI commands.
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const tri_proc = @import("tri_proc");

const MAX_OUTPUT = 8192;

// ═══════════════════════════════════════════════════════════════════════════════
// PUBLIC API — called from server.zig handleIssueTool()
// ═══════════════════════════════════════════════════════════════════════════════

pub fn issueList(buf: *[MAX_OUTPUT]u8) []const u8 {
    return runTriIssue(buf, &.{"list"});
}

pub fn issueView(buf: *[MAX_OUTPUT]u8, number: []const u8) []const u8 {
    return runTriIssue(buf, &.{ "view", number });
}

pub fn issueCreate(buf: *[MAX_OUTPUT]u8, title: []const u8, body: []const u8) []const u8 {
    if (body.len > 0) {
        return runTriIssue(buf, &.{ "create", title, body });
    }
    return runTriIssue(buf, &.{ "create", title });
}

pub fn issueComment(buf: *[MAX_OUTPUT]u8, number: []const u8, body: []const u8) []const u8 {
    return runTriIssue(buf, &.{ "comment", number, body });
}

pub fn issueClose(buf: *[MAX_OUTPUT]u8, number: []const u8) []const u8 {
    return runTriIssue(buf, &.{ "close", number });
}

pub fn issueAssign(buf: *[MAX_OUTPUT]u8, number: []const u8, user: []const u8) []const u8 {
    return runTriIssue(buf, &.{ "assign", number, user });
}

pub fn issueDecompose(buf: *[MAX_OUTPUT]u8, number: []const u8) []const u8 {
    return runTriIssue(buf, &.{ "decompose", number });
}

// ═══════════════════════════════════════════════════════════════════════════════
// INTERNAL — shell out to tri issue
// ═══════════════════════════════════════════════════════════════════════════════

fn runTriIssue(buf: *[MAX_OUTPUT]u8, args: []const []const u8) []const u8 {
    var argv: [16][]const u8 = undefined;
    argv[0] = TRI_PATH;
    argv[1] = "issue";
    const n = @min(args.len, 14);
    for (0..n) |i| {
        argv[2 + i] = args[i];
    }

    // 0.16 has neither Child.collectOutput nor File.readToEndAlloc, so the
    // init/spawn/read/wait sequence collapses into a single tri_proc.run.
    const gpa = std.heap.page_allocator;
    const result = tri_proc.run(.{
        .allocator = gpa,
        .argv = argv[0 .. 2 + n],
        .max_output_bytes = MAX_OUTPUT,
    }) catch |err| {
        return copyToBuf(buf, switch (err) {
            error.FileNotFound => "Error: tri binary not found (run zig build)",
            else => "Error: Failed to spawn tri issue process",
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

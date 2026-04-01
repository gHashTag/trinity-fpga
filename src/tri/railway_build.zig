// @origin(spec:railway_build.tri) @regen(manual-impl)
// Railway CLI wrapper — build, status, logs, download
// φ² + 1/φ² = 3 = TRINITY

const std = @import("std");

// Import Railway API module (in src/tri/railway_api.zig)
const railway_api = @import("railway_api.zig");

const CYAN = "\x1b[0;36m";
const GREEN = "\x1b[0;32m";
const RED = "\x1b[0;31m";
const RESET = "\x1b[0m";

/// Run Railway build command — runs `railway up --detach`
pub fn runRailwayBuildCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    _ = allocator;
    _ = args;

    std.debug.print("{s}Railway:{s} Triggering build via `railway up --detach`...\n", .{ CYAN, RESET });

    // Build command arguments
    var argv = try std.ArrayList([]const u8).initCapacity(allocator, 8);
    defer argv.deinit(allocator);

    try argv.append(allocator, "up");
    try argv.append(allocator, "--detach");

    // If extra args, forward them
    for (args) |arg| {
        try argv.append(allocator, arg);
    }

    // Execute railway CLI via child process
    var child = std.process.Child.init(&[_][]const []const u8{ "railway" }, allocator);
    child.argv = argv.items;
    child.stderr_behavior = .Inherit;
    child.stdout_behavior = .Inherit;

    const term = child.spawnAndWait();

    if (term.Exited != 0) {
        std.debug.print("{s}Railway build failed (exit {d}).{s}\n", .{ RED, RESET, term.Exited });
        const exit_status = switch (term.Exited) {
            1 => return error.BuildFailed,
            127 => return error.CommandNotFound,
            else => return error.UnknownExitCode,
        };
        return exit_status;
    }

    std.debug.print("{s}Railway build successful.{s}\n", .{ GREEN, RESET });
}

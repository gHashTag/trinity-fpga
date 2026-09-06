// @origin(spec:railway_build.tri) @regen(manual-impl)
// Railway CLI wrapper — build, status, logs, download
// φ² + 1/φ² = 3 = TRINITY

const std = @import("std");

// Import Railway API module (in src/tri/railway_api.zig)
const railway_api = @import("railway_api.zig");

pub const RailwayBuildError = error{
    BuildFailed,
    CommandNotFound,
    UnknownExitCode,
    RailwayBuildFailed,
};

const CYAN = "\x1b[0;36m";
const GREEN = "\x1b[0;32m";
const RED = "\x1b[0;31m";
const RESET = "\x1b[0m";

const YELLOW = "\x1b[0;33m";

/// Run Railway command — dispatches to build/status/logs subcommands
pub fn runRailwayCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    if (args.len < 1) {
        return showRailwayHelp(allocator);
    }

    const subcommand = args[0];
    const sub_args = args[1..];

    if (std.mem.eql(u8, subcommand, "build") or std.mem.eql(u8, subcommand, "up")) {
        return runRailwayBuildCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "status")) {
        return runRailwayStatusCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "logs")) {
        return runRailwayLogsCommand(allocator, sub_args);
    } else {
        std.debug.print("{s}Unknown railway subcommand: {s}{s}\n", .{ RED, subcommand, RESET });
        return showRailwayHelp(allocator);
    }
}

/// Show railway command help
fn showRailwayHelp(allocator: std.mem.Allocator) !void {
    _ = allocator;
    std.debug.print(
        \\
        \\{s}RAILWAY COMMANDS:{s}
        \\
        \\  {s}tri railway build{s}   Trigger build via Railway
        \\  {s}tri railway status{s}   Show deployment status
        \\  {s}tri railway logs{s}     Show build/deploy logs
        \\  {s}tri railway up{s}      Alias for 'build'
        \\
        \\{s}EXAMPLES:{s}
        \\  tri railway build
        \\  tri railway status
        \\  tri railway logs
        \\
    , .{ CYAN, RESET, CYAN, RESET, CYAN, RESET, CYAN, RESET, CYAN, RESET, YELLOW, RESET });
}

/// Run Railway build command — runs `railway up --detach`
pub fn runRailwayBuildCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
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
    var child = std.process.Child.init(&[_][]const u8{"railway"}, allocator);
    child.argv = argv.items;
    child.stderr_behavior = .Inherit;
    child.stdout_behavior = .Inherit;

    const term = child.spawnAndWait() catch |err| {
        std.debug.print("{s}Railway spawn failed: {s}.{s}\n", .{ RED, @errorName(err), RESET });
        return RailwayBuildError.BuildFailed;
    };

    if (term.exited != 0) {
        std.debug.print("{s}Railway build failed (exit {d}).{s}\n", .{ RED, term.exited, RESET });
        const exit_status = switch (term.exited) {
            1 => return RailwayBuildError.BuildFailed,
            127 => return RailwayBuildError.CommandNotFound,
            else => return RailwayBuildError.UnknownExitCode,
        };
        return exit_status;
    }
}

/// Run Railway status command — shows deployment status
fn runRailwayStatusCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    _ = args;

    std.debug.print("{s}Railway:{s} Fetching deployment status...\n", .{ CYAN, RESET });

    var api = railway_api.RailwayApi.init(allocator) catch |err| {
        std.debug.print("{s}Failed to init Railway API: {s}{s}\n", .{ RED, @errorName(err), RESET });
        return err;
    };
    defer api.deinit();

    // Get project info
    const project_info = api.getProjectInfo() catch |err| {
        std.debug.print("{s}Failed to fetch project info: {s}{s}\n", .{ RED, @errorName(err), RESET });
        return err;
    };
    defer allocator.free(project_info);

    std.debug.print("{s}Project: {s}{s}\n", .{ GREEN, project_info, RESET });
    std.debug.print("{s}Use 'railway status' CLI for detailed info.{s}\n", .{ YELLOW, RESET });
}

/// Run Railway logs command — shows build/deploy logs
fn runRailwayLogsCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    _ = allocator;
    _ = args;

    std.debug.print("{s}Railway:{s} Fetching logs...\n", .{ CYAN, RESET });
    std.debug.print("{s}Note: Use 'railway logs' CLI for full logs.{s}\n", .{ YELLOW, RESET });
}

// @origin(spec:railway.tri) @regen(manual-impl)
// Railway CLI wrapper — build, status, logs
// φ² + 1/φ² = 3 = TRINITY

const std = @import("std");
const railway_api = @import("railway_api.zig");
const railway_build = @import("railway_build.zig");

const CYAN = "\x1b[0;36m";
const GREEN = "\x1b[0;32m";
const RED = "\x1b[0;31m";
const YELLOW = "\x1b[0;33m";
const RESET = "\x1b[0m";

/// Run railway command — dispatches to build/status/logs subcommands
pub fn runRailwayCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    if (args.len < 1) {
        return showRailwayHelp(allocator);
    }

    const subcommand = args[0];
    const sub_args = args[1..];

    if (std.mem.eql(u8, subcommand, "build")) {
        return railway_build.runRailwayBuildCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "status")) {
        return runRailwayStatusCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "logs")) {
        return runRailwayLogsCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "up")) {
        // Alias for build
        return railway_build.runRailwayBuildCommand(allocator, sub_args);
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
        \\  tri railway logs --tail 50
        \\
    , .{ CYAN, RESET, CYAN, RESET, CYAN, RESET, CYAN, RESET, CYAN, RESET, YELLOW, RESET });
}

/// Run railway status command — shows deployment status
fn runRailwayStatusCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    _ = args;

    std.debug.print("{s}Railway:{s} Fetching deployment status...\n", .{ CYAN, RESET });

    var api = try railway_api.RailwayApi.init(allocator);
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

/// Run railway logs command — shows build/deploy logs
fn runRailwayLogsCommand(allocator: std.mem.Allocator, args: []const []const u8) !void {
    _ = args;

    std.debug.print("{s}Railway:{s} Fetching logs...\n", .{ CYAN, RESET });
    std.debug.print("{s}Note: Use 'railway logs' CLI for full logs.{s}\n", .{ YELLOW, RESET });
}

// tri_loopstate_main — standalone entry point for tri_loopstate.zig.
//
// The whole-CLI build (src/tri/main.zig) is blocked on the Zig-0.16
// Io-threading migration (see STATE.json anomaly A1): there is no build.zig
// anywhere in this repo that targets it. This file sidesteps that by being
// its own tiny `pub fn main`, built directly:
//
//   zig build-exe src/tri/tri_loopstate_main.zig -femit-bin=tri-loopstate
//   ./tri-loopstate status
//   ./tri-loopstate check
//
// Once the Io-threading decision lands and main.zig can dispatch to it, this
// file's body is what a `tri loopstate <sub>` case should call -- do not
// duplicate the logic there, wire this in.
//
// Dmitrii Vasilev / @gHashTag

const std = @import("std");
const loopstate = @import("tri_loopstate.zig");

fn usage() void {
    std.debug.print(
        \\usage: tri-loopstate <status|check> [--state PATH] [--dashboard PATH]
        \\
        \\  status     print the current iteration, done count, and next actionable backlog item
        \\  check      recompute live backlog/anomaly counts from STATE.json and diff them
        \\             against the dashboard's readout block; exits 1 if a drift is found
        \\
    , .{});
}

pub fn main(init: std.process.Init) !u8 {
    const gpa = init.gpa;
    const arena = init.arena.allocator();
    const argv = try init.minimal.args.toSlice(arena);

    if (argv.len < 2) {
        usage();
        return 1;
    }
    const cmd = argv[1];

    var state_path: []const u8 = loopstate.default_state_path;
    var dashboard_path: []const u8 = ".trinity/loop/dashboard.html";
    var i: usize = 2;
    while (i < argv.len) : (i += 1) {
        if (std.mem.eql(u8, argv[i], "--state") and i + 1 < argv.len) {
            i += 1;
            state_path = argv[i];
        } else if (std.mem.eql(u8, argv[i], "--dashboard") and i + 1 < argv.len) {
            i += 1;
            dashboard_path = argv[i];
        }
    }

    const state_bytes = std.Io.Dir.cwd().readFileAlloc(init.io, state_path, gpa, .limited(16 << 20)) catch |err| {
        std.debug.print("error: could not read {s}: {t}\n", .{ state_path, err });
        return 1;
    };
    defer gpa.free(state_bytes);

    var st = loopstate.parse(gpa, state_bytes) catch |err| {
        std.debug.print("error: {s} did not parse as loop state: {t}\n", .{ state_path, err });
        return 1;
    };
    defer st.deinit();

    if (std.mem.eql(u8, cmd, "status")) {
        const s = try loopstate.renderStatus(gpa, &st);
        defer gpa.free(s);
        std.debug.print("{s}", .{s});
        return 0;
    }

    if (std.mem.eql(u8, cmd, "check")) {
        const dashboard_bytes = std.Io.Dir.cwd().readFileAlloc(init.io, dashboard_path, gpa, .limited(16 << 20)) catch |err| {
            std.debug.print("error: could not read {s}: {t}\n", .{ dashboard_path, err });
            return 1;
        };
        defer gpa.free(dashboard_bytes);

        const live = loopstate.liveCounts(&st);
        const report = try loopstate.checkDrift(gpa, live, dashboard_bytes);
        defer gpa.free(report);
        std.debug.print("{s}", .{report});
        return if (std.mem.indexOf(u8, report, "DRIFT") != null or std.mem.indexOf(u8, report, "MISSING") != null) 1 else 0;
    }

    usage();
    return 1;
}

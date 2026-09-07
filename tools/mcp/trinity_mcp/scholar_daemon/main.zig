// main.zig — Entry point for Scholar research agent daemon
//
// Usage:
//   zig build scholar-agent          # Run with defaults
//   zig build scholar-agent -- --single-shot   # Run once and exit
//
// Environment variables:
//   SCHOLAR_SLEEP_INTERVAL — Seconds between wakes (default: 600)
//   SCHOLAR_MAX_WAKES      — Max wake cycles, 0=infinite (default: 0)
//   PROJECT_ROOT           — Project root path (auto-detected if unset)
//   TELEGRAM_BOT_TOKEN     — Telegram bot token (optional)
//   TELEGRAM_CHAT_ID       — Telegram chat ID (optional)
//
const std = @import("std");
const tri_env = @import("tri_env");
const tri_proc = @import("tri_proc");
const scholar_loop = @import("scholar_loop.zig");
const telegram = @import("telegram");

/// Takes std.process.Init.Minimal -- `{ environ, args }`, which std/start.zig
/// accepts directly. 0.16 removed std.process.argsAlloc, so `--single-shot`
/// can only be seen through the runtime-supplied argument vector.
pub fn main(init: std.process.Init.Minimal) !void {
    var gpa = std.heap.DebugAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const sleep_s: []const u8 = tri_env.getPosix("SCHOLAR_SLEEP_INTERVAL") orelse "600";
    const wakes_s: []const u8 = tri_env.getPosix("SCHOLAR_MAX_WAKES") orelse "0";

    const sleep_interval = std.fmt.parseInt(u64, sleep_s, 10) catch 600;
    const max_wakes = std.fmt.parseInt(u32, wakes_s, 10) catch 0;

    const tg_token: []const u8 = tri_env.getPosix("TELEGRAM_BOT_TOKEN") orelse "";
    const tg_chat_id: []const u8 = tri_env.getPosix("TELEGRAM_CHAT_ID") orelse "";
    const tg_enabled = tg_token.len > 0 and tg_chat_id.len > 0;

    // Detect project root
    const project_root = blk: {
        if (tri_env.getPosix("PROJECT_ROOT")) |root| break :blk @as([]const u8, root);
        const result = tri_proc.run(.{
            .allocator = allocator,
            .argv = &.{ "git", "rev-parse", "--show-toplevel" },
        }) catch {
            std.debug.print("[scholar] ERROR: Cannot detect project root. Set PROJECT_ROOT.\n", .{});
            std.process.exit(1);
        };
        defer allocator.free(result.stderr);
        if (result.stdout.len == 0) {
            std.debug.print("[scholar] ERROR: Not in a git repository.\n", .{});
            std.process.exit(1);
        }
        break :blk std.mem.trimEnd(u8, result.stdout, &std.ascii.whitespace);
    };

    var single_shot = false;
    const args = try init.args.toSlice(allocator);
    defer allocator.free(args);
    for (args) |arg| {
        if (std.mem.eql(u8, arg, "--single-shot")) {
            single_shot = true;
        }
    }

    std.debug.print(
        \\[scholar] Scholar Research Agent v1.0.0
        \\[scholar] SCAN → RESEARCH → FEED MU → NOTIFY
        \\[scholar] ---
        \\
    , .{});

    if (tg_enabled) {
        std.debug.print("[scholar] Telegram: enabled\n", .{});
    } else {
        std.debug.print("[scholar] Telegram: disabled\n", .{});
    }

    std.debug.print("[scholar] Sleep interval: {d}s, Max wakes: {d}\n", .{ sleep_interval, max_wakes });

    try scholar_loop.run(allocator, .{
        .project_root = project_root,
        .sleep_interval_s = sleep_interval,
        .max_wakes = max_wakes,
        .single_shot = single_shot,
        .tg_config = .{
            .bot_token = tg_token,
            .chat_id = tg_chat_id,
            .enabled = tg_enabled,
        },
    });
}

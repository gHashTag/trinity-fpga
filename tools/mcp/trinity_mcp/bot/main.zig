// main.zig — TRI BOT entry point
// Telegram bot as Claude Code CLI remote control
const std = @import("std");
const tri_env = @import("tri_env");
const bot_loop = @import("bot_loop.zig");
const telegram_api = @import("telegram_api.zig");

pub fn main() !void {
    var gpa = std.heap.DebugAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    // Read configuration from environment
    const bot_token = tri_env.getPosix("TELEGRAM_BOT_TOKEN") orelse {
        std.debug.print("[tri-bot] ERROR: TELEGRAM_BOT_TOKEN not set\n", .{});
        return error.MissingConfig;
    };
    const chat_id = tri_env.getPosix("TELEGRAM_CHAT_ID") orelse {
        std.debug.print("[tri-bot] ERROR: TELEGRAM_CHAT_ID not set\n", .{});
        return error.MissingConfig;
    };
    const project_root = tri_env.getPosix("PROJECT_ROOT") orelse
        tri_env.getPosix("TRINITY_PROJECT_ROOT") orelse ".";
    const api_key = tri_env.getPosix("ANTHROPIC_API_KEY") orelse {
        std.debug.print("[tri-bot] ERROR: ANTHROPIC_API_KEY not set\n", .{});
        return error.MissingConfig;
    };

    const api_base_url = tri_env.getPosix("ANTHROPIC_BASE_URL") orelse "https://api.anthropic.com";

    const max_turns_str = tri_env.getPosix("MAX_TURNS") orelse "10";
    const max_turns = std.fmt.parseInt(u32, max_turns_str, 10) catch 10;

    const config = telegram_api.BotConfig{
        .bot_token = bot_token,
        .chat_id = chat_id,
        .project_root = project_root,
        .api_key = api_key,
        .api_base_url = api_base_url,
        .max_turns = max_turns,
    };

    std.debug.print(
        \\[tri-bot] TRI BOT v2.0.0 (Direct API)
        \\[tri-bot] Chat ID: {s}
        \\[tri-bot] Project: {s}
        \\[tri-bot] Max turns: {d}
        \\
    , .{ chat_id, project_root, max_turns });

    // Run the bot loop (never returns)
    bot_loop.run(allocator, config);
}

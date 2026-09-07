const std = @import("std");
const tri_io = @import("tri_io");
const EpisodeRequest = @import("episode_handler.zig").EpisodeRequest;

pub const EpisodeLogger = struct {
    logs_dir: []const u8,

    pub fn init(logs_dir: []const u8) EpisodeLogger {
        return .{ .logs_dir = logs_dir };
    }

    pub fn log(self: *EpisodeLogger, allocator: std.mem.Allocator, ep: EpisodeRequest) !void {
        const io = tri_io.get();

        // Create directory if missing
        std.Io.Dir.cwd().createDirPath(io, self.logs_dir) catch {};

        // Build path: .trinity/logs/agent-gamma.jsonl
        var path_buf: [256]u8 = undefined;
        const path = try std.fmt.bufPrint(&path_buf, "{s}/agent-{s}.jsonl", .{
            self.logs_dir,
            ep.agent,
        });

        // Open file for append (truncate=false preserves existing content)
        const file = try std.Io.Dir.cwd().createFile(io, path, .{ .truncate = false });
        defer file.close(io);

        // 0.16 has no seek-then-write on File: read the end offset once and
        // place both writes positionally from there.
        const end = try file.length(io);

        // Write JSON + newline using Stringify API
        const json_str = try std.json.Stringify.valueAlloc(allocator, ep, .{});
        defer allocator.free(json_str);
        try file.writePositionalAll(io, json_str, end);
        try file.writePositionalAll(io, "\n", end + json_str.len);
    }
};

// memory.zig — Persistent memory for tri-api
// Stores learnings in ~/.tri-api/MEMORY.md, loads first 200 lines into system prompt.
// Issue #67: Phase 8 Context Management
const std = @import("std");

const tri_env = @import("tri_env");
const tri_io = @import("tri_io");
const max_lines = 200;
const max_file_size = 256 * 1024; // 256KB

pub const Memory = struct {
    allocator: std.mem.Allocator,
    base_dir: [512]u8 = undefined,
    base_dir_len: usize = 0,

    pub fn init(allocator: std.mem.Allocator) Memory {
        var mem = Memory{ .allocator = allocator };

        // Resolve ~/.tri-api/
        if (tri_env.getPosix("HOME")) |home| {
            if (std.fmt.bufPrint(&mem.base_dir, "{s}/.tri-api", .{home})) |path| {
                mem.base_dir_len = path.len;
            } else |_| {}
        }

        return mem;
    }

    /// Load first 200 lines from MEMORY.md. Caller owns memory.
    pub fn load(self: *Memory) ?[]const u8 {
        if (self.base_dir_len == 0) return null;

        const io = tri_io.get();

        var path_buf: [560]u8 = undefined;
        const path = std.fmt.bufPrint(&path_buf, "{s}/MEMORY.md", .{self.base_dir[0..self.base_dir_len]}) catch return null;

        // 0.16 removed File.readToEndAlloc; the whole-file read lives on the
        // directory now. cwd() with an absolute path is exactly what
        // openFileAbsolute does internally.
        const content = std.Io.Dir.cwd().readFileAlloc(io, path, self.allocator, .limited(max_file_size)) catch return null;

        // Limit to first 200 lines
        var line_count: u32 = 0;
        var end: usize = 0;
        while (end < content.len) : (end += 1) {
            if (content[end] == '\n') {
                line_count += 1;
                if (line_count >= max_lines) {
                    end += 1;
                    break;
                }
            }
        }

        if (end < content.len) {
            // Truncate to 200 lines
            const truncated = self.allocator.dupe(u8, content[0..end]) catch {
                self.allocator.free(content);
                return null;
            };
            self.allocator.free(content);
            return truncated;
        }

        return content;
    }

    /// Append a learning entry with timestamp.
    pub fn append(self: *Memory, text: []const u8) void {
        if (self.base_dir_len == 0) return;
        if (text.len == 0) return;

        const io = tri_io.get();

        // Ensure directory exists
        const dir_path = self.base_dir[0..self.base_dir_len];
        std.Io.Dir.createDirAbsolute(io, dir_path, .default_dir) catch |err| {
            std.log.debug("memory: failed to create dir {s}: {}", .{ dir_path, err });
        };

        var path_buf: [560]u8 = undefined;
        const path = std.fmt.bufPrint(&path_buf, "{s}/MEMORY.md", .{dir_path}) catch return;

        // Open for appending (create if needed)
        const file = std.Io.Dir.createFileAbsolute(io, path, .{ .truncate = false }) catch return;
        defer file.close(io);

        // 0.16 has no File.seekFromEnd. Append by writing positionally from the
        // current end of file instead; the offset advances by hand.
        var offset: u64 = file.length(io) catch |err| blk: {
            std.log.warn("memory: length failed for MEMORY.md: {}", .{err});
            break :blk 0;
        };

        // Write entry with separator
        const separator = "\n---\n";
        file.writePositionalAll(io, separator, offset) catch |write_err| {
            std.log.warn("memory: failed to write separator to MEMORY.md: {}", .{write_err});
        };
        offset += separator.len;
        file.writePositionalAll(io, text, offset) catch |write_err| {
            std.log.warn("memory: failed to write text to MEMORY.md: {}", .{write_err});
        };
        offset += text.len;
        file.writePositionalAll(io, "\n", offset) catch |write_err| {
            std.log.warn("memory: failed to write newline to MEMORY.md: {}", .{write_err});
        };
    }
};

// ─── Tests ───────────────────────────────────────────────────────────────────

test "Memory init" {
    const allocator = std.testing.allocator;
    const mem = Memory.init(allocator);
    // Should resolve base_dir if HOME is set
    if (tri_env.getPosix("HOME")) |_| {
        try std.testing.expect(mem.base_dir_len > 0);
    }
}
